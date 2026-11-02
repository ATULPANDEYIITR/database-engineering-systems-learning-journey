#include <algorithm>
#include <chrono>
#include <functional>
#include <iomanip>
#include <iostream>
#include <optional>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

using Value = std::string;

struct Row {
    std::unordered_map<std::string, Value> fields;

    const Value& at(const std::string& key) const {
        auto it = fields.find(key);
        if (it == fields.end()) {
            throw std::runtime_error("Unknown column: " + key);
        }
        return it->second;
    }
};

struct Table {
    std::string name;
    std::vector<std::string> columns;
    std::vector<Row> rows;
    std::unordered_map<std::string,
        std::unordered_map<Value, std::vector<std::size_t>>> indexes;

    void validate() const {
        if (name.empty() || columns.empty()) {
            throw std::invalid_argument("Table requires a name and columns.");
        }

        for (const auto& row : rows) {
            if (row.fields.size() != columns.size()) {
                throw std::invalid_argument("Row has an invalid column count.");
            }
            for (const auto& column : columns) {
                if (!row.fields.contains(column)) {
                    throw std::invalid_argument(
                        "Row is missing column: " + column
                    );
                }
            }
        }
    }

    void build_index(const std::string& column) {
        if (std::find(columns.begin(), columns.end(), column) == columns.end()) {
            throw std::invalid_argument("Cannot index unknown column.");
        }

        auto& index = indexes[column];
        for (std::size_t position = 0; position < rows.size(); ++position) {
            index[rows[position].at(column)].push_back(position);
        }
    }
};

struct ExecutionStats {
    std::size_t input_rows{0};
    std::size_t output_rows{0};
};

class Operator {
public:
    virtual ~Operator() = default;
    virtual std::vector<Row> execute() = 0;
    virtual std::string explain(std::size_t indent = 0) const = 0;

    const ExecutionStats& stats() const {
        return stats_;
    }

protected:
    ExecutionStats stats_;
};

class SeqScan final : public Operator {
public:
    SeqScan(const Table& table, std::string alias)
        : table_(table), alias_(std::move(alias)) {}

    std::vector<Row> execute() override {
        std::vector<Row> output;
        output.reserve(table_.rows.size());

        for (const auto& source : table_.rows) {
            ++stats_.input_rows;
            Row row;

            for (const auto& column : table_.columns) {
                row.fields.emplace(
                    alias_ + "." + column,
                    source.at(column)
                );
            }

            output.push_back(std::move(row));
        }

        stats_.output_rows = output.size();
        return output;
    }

    std::string explain(std::size_t indent = 0) const override {
        return std::string(indent, ' ') +
               "Seq Scan on " + table_.name;
    }

private:
    const Table& table_;
    std::string alias_;
};

class IndexScan final : public Operator {
public:
    IndexScan(
        const Table& table,
        std::string column,
        Value value,
        std::string alias
    )
        : table_(table),
          column_(std::move(column)),
          value_(std::move(value)),
          alias_(std::move(alias)) {

        if (!table_.indexes.contains(column_)) {
            throw std::invalid_argument(
                "Required index does not exist on " + column_
            );
        }
    }

    std::vector<Row> execute() override {
        std::vector<Row> output;
        const auto& index = table_.indexes.at(column_);

        auto position_it = index.find(value_);
        if (position_it == index.end()) {
            return output;
        }

        for (const auto position : position_it->second) {
            ++stats_.input_rows;
            Row row;

            for (const auto& column : table_.columns) {
                row.fields.emplace(
                    alias_ + "." + column,
                    table_.rows[position].at(column)
                );
            }

            output.push_back(std::move(row));
        }

        stats_.output_rows = output.size();
        return output;
    }

    std::string explain(std::size_t indent = 0) const override {
        return std::string(indent, ' ') +
               "Index Scan on " + table_.name +
               " using " + column_ + " = " + value_;
    }

private:
    const Table& table_;
    std::string column_;
    Value value_;
    std::string alias_;
};

class Filter final : public Operator {
public:
    Filter(
        std::unique_ptr<Operator> child,
        std::function<bool(const Row&)> predicate,
        std::string description
    )
        : child_(std::move(child)),
          predicate_(std::move(predicate)),
          description_(std::move(description)) {}

    std::vector<Row> execute() override {
        std::vector<Row> input = child_->execute();
        stats_.input_rows = input.size();

        std::vector<Row> output;
        for (const auto& row : input) {
            if (predicate_(row)) {
                output.push_back(row);
            }
        }

        stats_.output_rows = output.size();
        return output;
    }

    std::string explain(std::size_t indent = 0) const override {
        return std::string(indent, ' ') +
               "Filter: " + description_ + "\n" +
               child_->explain(indent + 2);
    }

private:
    std::unique_ptr<Operator> child_;
    std::function<bool(const Row&)> predicate_;
    std::string description_;
};

class HashJoin final : public Operator {
public:
    HashJoin(
        std::unique_ptr<Operator> left,
        std::unique_ptr<Operator> right,
        std::string left_key,
        std::string right_key
    )
        : left_(std::move(left)),
          right_(std::move(right)),
          left_key_(std::move(left_key)),
          right_key_(std::move(right_key)) {}

    std::vector<Row> execute() override {
        const auto right_rows = right_->execute();
        const auto left_rows = left_->execute();

        stats_.input_rows = right_rows.size() + left_rows.size();

        std::unordered_map<Value, std::vector<const Row*>> hash_table;

        for (const auto& row : right_rows) {
            hash_table[row.at(right_key_)].push_back(&row);
        }

        std::vector<Row> output;

        for (const auto& left_row : left_rows) {
            auto it = hash_table.find(left_row.at(left_key_));
            if (it == hash_table.end()) {
                continue;
            }

            for (const Row* right_row : it->second) {
                Row result = left_row;

                for (const auto& [key, value] : right_row->fields) {
                    if (result.fields.contains(key)) {
                        throw std::runtime_error(
                            "Ambiguous join output column: " + key
                        );
                    }
                    result.fields.emplace(key, value);
                }

                output.push_back(std::move(result));
            }
        }

        stats_.output_rows = output.size();
        return output;
    }

    std::string explain(std::size_t indent = 0) const override {
        return std::string(indent, ' ') +
               "Hash Join " + left_key_ + " = " + right_key_ + "\n" +
               left_->explain(indent + 2) + "\n" +
               right_->explain(indent + 2);
    }

private:
    std::unique_ptr<Operator> left_;
    std::unique_ptr<Operator> right_;
    std::string left_key_;
    std::string right_key_;
};

class Sort final : public Operator {
public:
    Sort(std::unique_ptr<Operator> child, std::string key)
        : child_(std::move(child)), key_(std::move(key)) {}

    std::vector<Row> execute() override {
        auto rows = child_->execute();
        stats_.input_rows = rows.size();

        std::sort(
            rows.begin(),
            rows.end(),
            [&](const Row& a, const Row& b) {
                return a.at(key_) > b.at(key_);
            }
        );

        stats_.output_rows = rows.size();
        return rows;
    }

    std::string explain(std::size_t indent = 0) const override {
        return std::string(indent, ' ') +
               "Sort DESC: " + key_ + "\n" +
               child_->explain(indent + 2);
    }

private:
    std::unique_ptr<Operator> child_;
    std::string key_;
};

class Limit final : public Operator {
public:
    Limit(std::unique_ptr<Operator> child, std::size_t limit)
        : child_(std::move(child)), limit_(limit) {}

    std::vector<Row> execute() override {
        auto rows = child_->execute();
        stats_.input_rows = rows.size();

        if (rows.size() > limit_) {
            rows.resize(limit_);
        }

        stats_.output_rows = rows.size();
        return rows;
    }

    std::string explain(std::size_t indent = 0) const override {
        return std::string(indent, ' ') +
               "Limit: " + std::to_string(limit_) + "\n" +
               child_->explain(indent + 2);
    }

private:
    std::unique_ptr<Operator> child_;
    std::size_t limit_;
};

static Row make_row(
    std::initializer_list<std::pair<const std::string, Value>> values
) {
    Row row;
    for (const auto& [key, value] : values) {
        row.fields.emplace(key, value);
    }
    return row;
}

static Table make_customers() {
    Table table{
        "customers",
        {"id", "name", "status"},
        {
            make_row({{"id", "1"}, {"name", "Asha"}, {"status", "active"}}),
            make_row({{"id", "2"}, {"name", "Bharat"}, {"status", "active"}}),
            make_row({{"id", "3"}, {"name", "Chen"}, {"status", "inactive"}}),
            make_row({{"id", "4"}, {"name", "Divya"}, {"status", "active"}})
        }
    };

    table.validate();
    table.build_index("status");
    return table;
}

static Table make_orders() {
    Table table{
        "orders",
        {"id", "customer_id", "total"},
        {
            make_row({{"id", "101"}, {"customer_id", "1"}, {"total", "450"}}),
            make_row({{"id", "102"}, {"customer_id", "1"}, {"total", "1200"}}),
            make_row({{"id", "103"}, {"customer_id", "2"}, {"total", "900"}}),
            make_row({{"id", "104"}, {"customer_id", "3"}, {"total", "2500"}}),
            make_row({{"id", "105"}, {"customer_id", "4"}, {"total", "1750"}})
        }
    };

    table.validate();
    table.build_index("customer_id");
    return table;
}

int main() {
    try {
        Table customers = make_customers();
        Table orders = make_orders();

        // Predicate pushdown is represented by the index scan before joining.
        auto customer_scan = std::make_unique<IndexScan>(
            customers, "status", "active", "c"
        );

        auto order_scan = std::make_unique<SeqScan>(
            orders, "o"
        );

        auto join = std::make_unique<HashJoin>(
            std::move(customer_scan),
            std::move(order_scan),
            "c.id",
            "o.customer_id"
        );

        auto filter = std::make_unique<Filter>(
            std::move(join),
            [](const Row& row) {
                return std::stod(row.at("o.total")) >= 800.0;
            },
            "o.total >= 800"
        );

        auto sort = std::make_unique<Sort>(
            std::move(filter),
            "o.total"
        );

        auto plan = std::make_unique<Limit>(
            std::move(sort),
            3
        );

        std::cout << "EXECUTION PLAN\n";
        std::cout << plan->explain() << "\n\n";

        const auto started = std::chrono::steady_clock::now();
        const auto result = plan->execute();
        const auto ended = std::chrono::steady_clock::now();

        std::cout << "RESULT SET\n";
        std::cout << "customer_id | customer_name | order_id | total\n";

        for (const auto& row : result) {
            std::cout
                << row.at("c.id") << " | "
                << row.at("c.name") << " | "
                << row.at("o.id") << " | "
                << row.at("o.total") << '\n';
        }

        const auto elapsed =
            std::chrono::duration<double, std::milli>(ended - started).count();

        std::cout << "\nRows returned: " << result.size() << '\n';
        std::cout << std::fixed << std::setprecision(3)
                  << "Execution time: " << elapsed << " ms\n";

        if (result.size() > 3) {
            throw std::runtime_error("LIMIT invariant violated.");
        }

        for (const auto& row : result) {
            if (std::stod(row.at("o.total")) < 800.0) {
                throw std::runtime_error("Filter invariant violated.");
            }
        }

        try {
            IndexScan invalid(customers, "name", "Asha", "c");
        } catch (const std::invalid_argument& error) {
            std::cout << "\nValidation failure handled: "
                      << error.what() << '\n';
        }
    } catch (const std::exception& error) {
        std::cerr << "Execution failure: " << error.what() << '\n';
        return 1;
    }

    return 0;
}
