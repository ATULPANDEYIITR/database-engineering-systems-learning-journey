#include <algorithm>
#include <iomanip>
#include <iostream>
#include <map>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

/*
 * PostgreSQL Table Engineering: warehouse schema design review.
 *
 * C++17 case study:
 * Model the structure of a warehouse inventory database before DDL
 * deployment. Validate identifiers, column definitions, constraints,
 * foreign-key references, and migration dependencies.
 *
 * This is an offline schema-planning engine. It does not pretend to execute
 * PostgreSQL statements; actual execution belongs to a PostgreSQL driver
 * or migration service.
 */

enum class ConstraintKind {
    PrimaryKey,
    Unique,
    NotNull,
    Check,
    ForeignKey,
    Default
};

std::string toString(ConstraintKind kind) {
    switch (kind) {
        case ConstraintKind::PrimaryKey: return "PRIMARY KEY";
        case ConstraintKind::Unique: return "UNIQUE";
        case ConstraintKind::NotNull: return "NOT NULL";
        case ConstraintKind::Check: return "CHECK";
        case ConstraintKind::ForeignKey: return "FOREIGN KEY";
        case ConstraintKind::Default: return "DEFAULT";
    }

    throw std::logic_error("Unknown constraint kind");
}

bool validIdentifier(const std::string& identifier) {
    if (identifier.empty() ||
        !(identifier[0] >= 'a' && identifier[0] <= 'z')) {
        return false;
    }

    return std::all_of(
        identifier.begin() + 1,
        identifier.end(),
        [](unsigned char ch) {
            return (ch >= 'a' && ch <= 'z') ||
                   (ch >= '0' && ch <= '9') ||
                   ch == '_';
        }
    );
}

struct Column {
    std::string name;
    std::string type;
    bool nullable;
    std::string defaultExpression;
};

struct ForeignKey {
    std::string name;
    std::string sourceTable;
    std::string sourceColumn;
    std::string targetTable;
    std::string targetColumn;
    std::string onDelete;
};

struct Table {
    std::string name;
    std::vector<Column> columns;
    std::vector<std::string> primaryKey;
    std::vector<std::vector<std::string>> uniqueKeys;
    std::vector<std::string> checks;
};

class Schema {
private:
    std::map<std::string, Table> tables;
    std::vector<ForeignKey> foreignKeys;

public:
    void addTable(Table table) {
        if (!validIdentifier(table.name)) {
            throw std::invalid_argument("Invalid table name: " + table.name);
        }

        if (tables.count(table.name) != 0) {
            throw std::invalid_argument("Duplicate table: " + table.name);
        }

        std::set<std::string> columnNames;

        for (const auto& column : table.columns) {
            if (!validIdentifier(column.name)) {
                throw std::invalid_argument(
                    "Invalid column name: " + column.name
                );
            }

            if (!columnNames.insert(column.name).second) {
                throw std::invalid_argument(
                    "Duplicate column " + column.name +
                    " in table " + table.name
                );
            }

            if (column.type != "BIGINT" &&
                column.type != "INTEGER" &&
                column.type != "TEXT" &&
                column.type != "BOOLEAN" &&
                column.type != "NUMERIC(12,2)" &&
                column.type != "TIMESTAMPTZ") {
                throw std::invalid_argument(
                    "Unsupported type: " + column.type
                );
            }
        }

        if (table.primaryKey.empty()) {
            throw std::invalid_argument(
                "Table requires a primary key: " + table.name
            );
        }

        for (const auto& keyColumn : table.primaryKey) {
            if (!columnNames.count(keyColumn)) {
                throw std::invalid_argument(
                    "Primary key references missing column: " + keyColumn
                );
            }
        }

        for (const auto& key : table.uniqueKeys) {
            if (key.empty()) {
                throw std::invalid_argument("Unique key cannot be empty");
            }

            for (const auto& columnName : key) {
                if (!columnNames.count(columnName)) {
                    throw std::invalid_argument(
                        "Unique key references missing column: " + columnName
                    );
                }
            }
        }

        tables.emplace(table.name, std::move(table));
    }

    void addForeignKey(ForeignKey key) {
        if (tables.count(key.sourceTable) == 0 ||
            tables.count(key.targetTable) == 0) {
            throw std::invalid_argument(
                "Foreign key references a table not yet registered"
            );
        }

        const auto& source = tables.at(key.sourceTable);
        const auto& target = tables.at(key.targetTable);

        const auto sourceColumn = std::find_if(
            source.columns.begin(), source.columns.end(),
            [&](const Column& column) {
                return column.name == key.sourceColumn;
            }
        );

        const auto targetColumn = std::find_if(
            target.columns.begin(), target.columns.end(),
            [&](const Column& column) {
                return column.name == key.targetColumn;
            }
        );

        if (sourceColumn == source.columns.end() ||
            targetColumn == target.columns.end()) {
            throw std::invalid_argument(
                "Foreign key references an unknown column"
            );
        }

        if (sourceColumn->type != targetColumn->type) {
            throw std::invalid_argument(
                "Foreign key column types must be compatible"
            );
        }

        // PostgreSQL requires a referenced key to be backed by a suitable
        // unique or primary-key constraint.
        bool targetIsUnique =
            target.primaryKey == std::vector<std::string>{key.targetColumn};

        for (const auto& uniqueKey : target.uniqueKeys) {
            if (uniqueKey == std::vector<std::string>{key.targetColumn}) {
                targetIsUnique = true;
            }
        }

        if (!targetIsUnique) {
            throw std::invalid_argument(
                "Referenced column must be a primary or unique key"
            );
        }

        if (key.onDelete != "RESTRICT" &&
            key.onDelete != "CASCADE" &&
            key.onDelete != "SET NULL") {
            throw std::invalid_argument(
                "Unsupported ON DELETE action"
            );
        }

        if (key.onDelete == "SET NULL" && !sourceColumn->nullable) {
            throw std::invalid_argument(
                "ON DELETE SET NULL requires a nullable source column"
            );
        }

        foreignKeys.push_back(std::move(key));
    }

    void printReport() const {
        std::cout << "\nWarehouse schema report\n";

        for (const auto& [tableName, table] : tables) {
            std::cout << "\nCREATE TABLE " << tableName << ":\n";

            for (const auto& column : table.columns) {
                std::cout << "  " << column.name << " " << column.type;

                if (!column.nullable) {
                    std::cout << " NOT NULL";
                }

                if (!column.defaultExpression.empty()) {
                    std::cout << " DEFAULT "
                              << column.defaultExpression;
                }

                std::cout << '\n';
            }

            std::cout << "  PRIMARY KEY (";
            for (std::size_t i = 0; i < table.primaryKey.size(); ++i) {
                if (i > 0) std::cout << ", ";
                std::cout << table.primaryKey[i];
            }
            std::cout << ")\n";

            for (const auto& key : table.uniqueKeys) {
                std::cout << "  UNIQUE (";
                for (std::size_t i = 0; i < key.size(); ++i) {
                    if (i > 0) std::cout << ", ";
                    std::cout << key[i];
                }
                std::cout << ")\n";
            }

            for (const auto& check : table.checks) {
                std::cout << "  CHECK (" << check << ")\n";
            }
        }

        std::cout << "\nForeign key relationships:\n";
        for (const auto& key : foreignKeys) {
            std::cout << "  " << key.name << ": "
                      << key.sourceTable << "." << key.sourceColumn
                      << " -> "
                      << key.targetTable << "." << key.targetColumn
                      << " ON DELETE " << key.onDelete << '\n';
        }
    }

    std::string generateForeignKeyDDL() const {
        std::ostringstream sql;

        for (const auto& key : foreignKeys) {
            sql << "ALTER TABLE inventory." << key.sourceTable
                << " ADD CONSTRAINT " << key.name
                << " FOREIGN KEY (" << key.sourceColumn << ")"
                << " REFERENCES inventory." << key.targetTable
                << " (" << key.targetColumn << ")"
                << " ON DELETE " << key.onDelete << ";\n";
        }

        return sql.str();
    }
};

int main() {
    try {
        Schema schema;

        schema.addTable(Table{
            "categories",
            {
                {"category_id", "BIGINT", false, ""},
                {"category_name", "TEXT", false, ""}
            },
            {"category_id"},
            {{"category_name"}},
            {"length(btrim(category_name)) > 0"}
        });

        schema.addTable(Table{
            "products",
            {
                {"product_id", "BIGINT", false, ""},
                {"sku", "TEXT", false, ""},
                {"product_name", "TEXT", false, ""},
                {"category_id", "BIGINT", true, ""},
                {"unit_price", "NUMERIC(12,2)", false, "0.00"},
                {"stock_quantity", "INTEGER", false, "0"},
                {"active", "BOOLEAN", false, "TRUE"}
            },
            {"product_id"},
            {{"sku"}},
            {
                "length(btrim(sku)) > 0",
                "length(btrim(product_name)) > 0",
                "unit_price >= 0",
                "stock_quantity >= 0"
            }
        });

        schema.addTable(Table{
            "orders",
            {
                {"order_id", "BIGINT", false, ""},
                {"customer_id", "BIGINT", false, ""},
                {"order_status", "TEXT", false, "'pending'"}
            },
            {"order_id"},
            {},
            {
                "order_status IN ('pending', 'confirmed', 'shipped', "
                "'delivered', 'cancelled')"
            }
        });

        schema.addTable(Table{
            "customers",
            {
                {"customer_id", "BIGINT", false, ""},
                {"email", "TEXT", false, ""},
                {"full_name", "TEXT", false, ""}
            },
            {"customer_id"},
            {{"email"}},
            {
                "length(btrim(email)) > 0",
                "length(btrim(full_name)) > 0"
            }
        });

        schema.addForeignKey(ForeignKey{
            "fk_products_category",
            "products", "category_id",
            "categories", "category_id",
            "SET NULL"
        });

        schema.addForeignKey(ForeignKey{
            "fk_orders_customer",
            "orders", "customer_id",
            "customers", "customer_id",
            "RESTRICT"
        });

        schema.printReport();

        std::cout << "\nGenerated relationship DDL:\n"
                  << schema.generateForeignKeyDDL();

        // Demonstrate that the planner rejects a foreign key to a non-unique
        // business column rather than generating invalid PostgreSQL DDL.
        try {
            schema.addForeignKey(ForeignKey{
                "fk_invalid_product_name",
                "products", "product_name",
                "categories", "category_name",
                "RESTRICT"
            });
        } catch (const std::exception& error) {
            std::cout << "\nRejected invalid relationship: "
                      << error.what() << '\n';
        }

        try {
            Table invalidTable{
                "invalid_table",
                {
                    {"product_id", "BIGINT", false, ""},
                    {"product_id", "TEXT", false, ""}
                },
                {"product_id"},
                {},
                {}
            };

            schema.addTable(std::move(invalidTable));
        } catch (const std::exception& error) {
            std::cout << "Rejected invalid table: "
                      << error.what() << '\n';
        }

        std::cout
            << "\nPlanning complete. The output is a design report, "
            << "not proof that a database migration has executed.\n";
    } catch (const std::exception& error) {
        std::cerr << "Schema planning failed: "
                  << error.what() << '\n';
        return 1;
    }

    return 0;
}
