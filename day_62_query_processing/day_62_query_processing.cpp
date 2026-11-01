#include <algorithm>
#include <cctype>
#include <exception>
#include <iomanip>
#include <iostream>
#include <optional>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <variant>
#include <vector>

enum class TokenType {
    Keyword,
    Identifier,
    Number,
    String,
    Operator,
    Symbol,
    End
};

struct Token {
    TokenType type;
    std::string value;
    std::size_t position;
};

class QueryError : public std::runtime_error {
public:
    using std::runtime_error::runtime_error;
};

class LexicalError : public QueryError {
public:
    using QueryError::QueryError;
};

class ParseError : public QueryError {
public:
    using QueryError::QueryError;
};

class SemanticError : public QueryError {
public:
    using QueryError::QueryError;
};

using Value = std::variant<long long, std::string>;

struct Condition {
    std::string column;
    std::string op;
    Value value;
};

struct SelectItem {
    std::string expression;
    std::optional<std::string> alias;
};

struct Query {
    std::vector<SelectItem> columns;
    std::string table;
    std::vector<Condition> conditions;
    std::optional<std::string> orderBy;
    bool descending = false;
    std::optional<std::size_t> limit;
};

struct Row {
    std::unordered_map<std::string, Value> values;
};

struct Table {
    std::string name;
    std::vector<std::string> columns;
    std::vector<Row> rows;
};

class Lexer {
    static bool isIdentifierStart(char c) {
        return std::isalpha(static_cast<unsigned char>(c)) || c == '_';
    }

    static bool isIdentifierChar(char c) {
        return std::isalnum(static_cast<unsigned char>(c)) || c == '_';
    }

    static bool isKeyword(const std::string& value) {
        static const std::unordered_set<std::string> keywords{
            "SELECT", "FROM", "WHERE", "AND", "ORDER",
            "BY", "ASC", "DESC", "LIMIT", "AS"
        };
        return keywords.contains(value);
    }

public:
    std::vector<Token> tokenize(const std::string& sql) const {
        std::vector<Token> tokens;

        for (std::size_t i = 0; i < sql.size();) {
            if (std::isspace(static_cast<unsigned char>(sql[i]))) {
                ++i;
                continue;
            }

            if (sql[i] == '\'') {
                const auto start = i++;
                std::string value;

                while (i < sql.size()) {
                    if (sql[i] == '\'' && i + 1 < sql.size() &&
                        sql[i + 1] == '\'') {
                        value += '\'';
                        i += 2;
                    } else if (sql[i] == '\'') {
                        ++i;
                        break;
                    } else {
                        value += sql[i++];
                    }
                }

                if (i > sql.size() || sql[i - 1] != '\'') {
                    throw LexicalError("Unterminated string literal");
                }

                tokens.push_back({TokenType::String, value, start});
                continue;
            }

            if (std::isdigit(static_cast<unsigned char>(sql[i]))) {
                const auto start = i;
                while (i < sql.size() &&
                       std::isdigit(static_cast<unsigned char>(sql[i]))) {
                    ++i;
                }
                tokens.push_back({
                    TokenType::Number,
                    sql.substr(start, i - start),
                    start
                });
                continue;
            }

            if (isIdentifierStart(sql[i])) {
                const auto start = i;
                while (i < sql.size() && isIdentifierChar(sql[i])) ++i;

                std::string value = sql.substr(start, i - start);
                std::string upper = value;
                std::transform(
                    upper.begin(), upper.end(), upper.begin(),
                    [](unsigned char c) { return std::toupper(c); }
                );

                tokens.push_back({
                    isKeyword(upper) ? TokenType::Keyword
                                     : TokenType::Identifier,
                    isKeyword(upper) ? upper : value,
                    start
                });
                continue;
            }

            const std::string two =
                i + 1 < sql.size() ? sql.substr(i, 2) : "";

            if (two == ">=" || two == "<=" ||
                two == "!=" || two == "<>") {
                tokens.push_back({TokenType::Operator, two, i});
                i += 2;
                continue;
            }

            if (sql[i] == '=' || sql[i] == '>' || sql[i] == '<') {
                tokens.push_back({
                    TokenType::Operator,
                    std::string(1, sql[i]),
                    i
                });
                ++i;
                continue;
            }

            if (std::string(",;*()").find(sql[i]) != std::string::npos) {
                tokens.push_back({
                    TokenType::Symbol,
                    std::string(1, sql[i]),
                    i
                });
                ++i;
                continue;
            }

            throw LexicalError(
                "Unsupported character at position " +
                std::to_string(i)
            );
        }

        tokens.push_back({TokenType::End, "", sql.size()});
        return tokens;
    }
};

class Parser {
    const std::vector<Token>& tokens;
    std::size_t index = 0;

    const Token& current() const {
        return tokens[index];
    }

    Token consume() {
        return tokens[index++];
    }

    void expect(const std::string& value) {
        if (current().value != value) {
            throw ParseError(
                "Expected " + value + " at position " +
                std::to_string(current().position)
            );
        }
        consume();
    }

    std::string identifier() {
        if (current().type != TokenType::Identifier) {
            throw ParseError(
                "Expected identifier at position " +
                std::to_string(current().position)
            );
        }
        return consume().value;
    }

    Condition condition() {
        Condition result;
        result.column = identifier();

        if (current().type != TokenType::Operator) {
            throw ParseError("Expected comparison operator");
        }
        result.op = consume().value;

        const Token value = consume();

        if (value.type == TokenType::Number) {
            result.value = std::stoll(value.value);
        } else if (value.type == TokenType::String ||
                   value.type == TokenType::Identifier) {
            result.value = value.value;
        } else {
            throw ParseError("Invalid comparison value");
        }

        return result;
    }

public:
    explicit Parser(const std::vector<Token>& tokens) : tokens(tokens) {}

    Query parse() {
        Query query;
        expect("SELECT");

        if (current().value == "*") {
            consume();
            query.columns.push_back({"*", std::nullopt});
        } else {
            while (true) {
                SelectItem item;
                item.expression = identifier();

                if (current().value == "AS") {
                    consume();
                    item.alias = identifier();
                }

                query.columns.push_back(item);

                if (current().value != ",") break;
                consume();
            }
        }

        expect("FROM");
        query.table = identifier();

        if (current().value == "WHERE") {
            consume();
            query.conditions.push_back(condition());

            while (current().value == "AND") {
                consume();
                query.conditions.push_back(condition());
            }
        }

        if (current().value == "ORDER") {
            consume();
            expect("BY");

            query.orderBy = identifier();

            if (current().value == "DESC") {
                query.descending = true;
                consume();
            } else if (current().value == "ASC") {
                consume();
            }
        }

        if (current().value == "LIMIT") {
            consume();

            if (current().type != TokenType::Number) {
                throw ParseError("LIMIT requires a number");
            }

            query.limit = static_cast<std::size_t>(
                std::stoull(consume().value)
            );
        }

        if (current().value == ";") consume();

        if (current().type != TokenType::End) {
            throw ParseError("Unexpected token: " + current().value);
        }

        return query;
    }
};

class Catalog {
    std::unordered_map<std::string, Table> tables;

public:
    void registerTable(Table table) {
        if (tables.contains(table.name)) {
            throw SemanticError("Duplicate table: " + table.name);
        }
        tables.emplace(table.name, std::move(table));
    }

    const Table& table(const std::string& name) const {
        auto it = tables.find(name);
        if (it == tables.end()) {
            throw SemanticError("Unknown table: " + name);
        }
        return it->second;
    }
};

class Planner {
    const Catalog& catalog;

public:
    explicit Planner(const Catalog& catalog) : catalog(catalog) {}

    void analyze(const Query& query) const {
        const Table& table = catalog.table(query.table);
        const std::unordered_set<std::string> columns(
            table.columns.begin(), table.columns.end()
        );

        for (const auto& item : query.columns) {
            if (item.expression != "*" &&
                !columns.contains(item.expression)) {
                throw SemanticError(
                    "Unknown projection column: " + item.expression
                );
            }
        }

        for (const auto& condition : query.conditions) {
            if (!columns.contains(condition.column)) {
                throw SemanticError(
                    "Unknown predicate column: " + condition.column
                );
            }
        }

        if (query.orderBy && !columns.contains(*query.orderBy)) {
            throw SemanticError(
                "Unknown ordering column: " + *query.orderBy
            );
        }
    }

    std::vector<std::string> physicalPlan(const Query& query) const {
        std::vector<std::string> plan{
            "TableScan(" + query.table + ")"
        };

        if (!query.conditions.empty()) {
            plan.push_back("PredicateFilter");
        }

        if (query.orderBy) {
            plan.push_back(
                "Sort(" + *query.orderBy +
                (query.descending ? " DESC)" : " ASC)")
            );
        }

        if (query.limit) {
            plan.push_back("Limit(" + std::to_string(*query.limit) + ")");
        }

        plan.push_back("Projection");
        return plan;
    }
};

bool compareValue(
    const Value& left,
    const std::string& op,
    const Value& right
) {
    if (left.index() != right.index()) return false;

    if (std::holds_alternative<long long>(left)) {
        const auto a = std::get<long long>(left);
        const auto b = std::get<long long>(right);

        if (op == "=") return a == b;
        if (op == "!=" || op == "<>") return a != b;
        if (op == ">") return a > b;
        if (op == "<") return a < b;
        if (op == ">=") return a >= b;
        if (op == "<=") return a <= b;
    } else {
        const auto& a = std::get<std::string>(left);
        const auto& b = std::get<std::string>(right);

        if (op == "=") return a == b;
        if (op == "!=" || op == "<>") return a != b;
        if (op == ">") return a > b;
        if (op == "<") return a < b;
        if (op == ">=") return a >= b;
        if (op == "<=") return a <= b;
    }

    throw SemanticError("Unsupported comparison operator: " + op);
}

class Executor {
    const Catalog& catalog;

public:
    explicit Executor(const Catalog& catalog) : catalog(catalog) {}

    std::vector<Row> execute(const Query& query) const {
        const Table& table = catalog.table(query.table);
        std::vector<Row> rows = table.rows;

        for (const auto& condition : query.conditions) {
            rows.erase(
                std::remove_if(
                    rows.begin(),
                    rows.end(),
                    [&](const Row& row) {
                        return !compareValue(
                            row.values.at(condition.column),
                            condition.op,
                            condition.value
                        );
                    }
                ),
                rows.end()
            );
        }

        if (query.orderBy) {
            const std::string column = *query.orderBy;

            std::sort(
                rows.begin(),
                rows.end(),
                [&](const Row& a, const Row& b) {
                    const Value& left = a.values.at(column);
                    const Value& right = b.values.at(column);

                    bool result = false;

                    if (std::holds_alternative<long long>(left)) {
                        result = std::get<long long>(left) <
                                 std::get<long long>(right);
                    } else {
                        result = std::get<std::string>(left) <
                                 std::get<std::string>(right);
                    }

                    return query.descending ? !result : result;
                }
            );
        }

        if (query.limit && rows.size() > *query.limit) {
            rows.resize(*query.limit);
        }

        return rows;
    }
};

std::string valueToString(const Value& value) {
    if (std::holds_alternative<long long>(value)) {
        return std::to_string(std::get<long long>(value));
    }
    return std::get<std::string>(value);
}

void printResults(
    const Query& query,
    const std::vector<Row>& rows
) {
    if (query.columns.size() == 1 &&
        query.columns.front().expression == "*") {
        for (const auto& row : rows) {
            for (const auto& [key, value] : row.values) {
                std::cout << key << "=" << valueToString(value) << " ";
            }
            std::cout << '\n';
        }
        return;
    }

    for (const auto& row : rows) {
        for (const auto& item : query.columns) {
            std::cout
                << (item.alias ? *item.alias : item.expression)
                << "="
                << valueToString(row.values.at(item.expression))
                << " ";
        }
        std::cout << '\n';
    }
}

Catalog buildCatalog() {
    Catalog catalog;

    Table employees{
        "employees",
        {"id", "name", "department", "salary"},
        {}
    };

    employees.rows = {
        {{{"id", 1}, {"name", "Asha"}, {"department", "R&D"}, {"salary", 92000}}},
        {{{"id", 2}, {"name", "Ravi"}, {"department", "Security"}, {"salary", 81000}}},
        {{{"id", 3}, {"name", "Meera"}, {"department", "R&D"}, {"salary", 105000}}},
        {{{"id", 4}, {"name", "Kabir"}, {"department", "Platform"}, {"salary", 76000}}},
        {{{"id", 5}, {"name", "Nisha"}, {"department", "Security"}, {"salary", 97000}}}
    };

    catalog.registerTable(std::move(employees));
    return catalog;
}

int main() {
    try {
        const Catalog catalog = buildCatalog();
        const Lexer lexer;
        const Planner planner(catalog);
        const Executor executor(catalog);

        const std::vector<std::string> queries{
            "SELECT name, salary FROM employees "
            "WHERE salary >= 90000 ORDER BY salary DESC LIMIT 3",

            "SELECT name AS employee, department FROM employees "
            "WHERE department = 'Security'"
        };

        for (const auto& sql : queries) {
            std::cout << "\nSQL: " << sql << "\n";

            const auto tokens = lexer.tokenize(sql);
            const Parser parser(tokens);
            const Query query = parser.parse();

            planner.analyze(query);

            std::cout << "PLAN: ";
            for (const auto& operation : planner.physicalPlan(query)) {
                std::cout << operation << " ";
            }
            std::cout << "\n";

            const auto rows = executor.execute(query);
            std::cout << "ROWS: " << rows.size() << "\n";
            printResults(query, rows);
        }

        try {
            const auto tokens = lexer.tokenize(
                "SELECT missing FROM employees"
            );
            const Parser parser(tokens);
            const Query query = parser.parse();
            planner.analyze(query);
        } catch (const QueryError& error) {
            std::cout
                << "\nExpected semantic failure: "
                << error.what() << "\n";
        }

        try {
            const auto tokens = lexer.tokenize(
                "SELECT name FROM unknown"
            );
            const Parser parser(tokens);
            const Query query = parser.parse();
            planner.analyze(query);
        } catch (const QueryError& error) {
            std::cout
                << "Expected catalog failure: "
                << error.what() << "\n";
        }
    } catch (const std::exception& error) {
        std::cerr << "Fatal query-processing error: "
                  << error.what() << '\n';
        return 1;
    }

    return 0;
}
