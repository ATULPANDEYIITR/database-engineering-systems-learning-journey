import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.Set;

public class QueryProcessingEngine {

    enum TokenType {
        KEYWORD, IDENTIFIER, NUMBER, STRING, OPERATOR, SYMBOL, EOF
    }

    record Token(TokenType type, String value, int position) {}

    static class QueryException extends RuntimeException {
        QueryException(String message) {
            super(message);
        }
    }

    static class LexicalException extends QueryException {
        LexicalException(String message) {
            super(message);
        }
    }

    static class ParseException extends QueryException {
        ParseException(String message) {
            super(message);
        }
    }

    static class SemanticException extends QueryException {
        SemanticException(String message) {
            super(message);
        }
    }

    enum ReviewLikeState {
        PARSED,
        ANALYZED,
        REWRITTEN,
        PLANNED,
        EXECUTED
    }

    record SelectItem(String expression, Optional<String> alias) {}

    record Condition(String column, String operator, Object value) {}

    record Query(
            List<SelectItem> columns,
            String table,
            List<Condition> conditions,
            Optional<String> orderBy,
            boolean descending,
            Optional<Integer> limit
    ) {}

    record Row(Map<String, Object> values) {
        Row {
            values = Map.copyOf(values);
        }
    }

    record Table(
            String name,
            List<String> columns,
            List<Row> rows
    ) {}

    interface QueryPolicy {
        void validate(Query query, Table table);
    }

    static final class StrictQueryPolicy implements QueryPolicy {
        @Override
        public void validate(Query query, Table table) {
            Set<String> known = new HashSet<>(table.columns());

            for (SelectItem item : query.columns()) {
                if (!item.expression().equals("*") &&
                    !known.contains(item.expression())) {
                    throw new SemanticException(
                            "Unknown projection column: "
                                    + item.expression()
                    );
                }
            }

            for (Condition condition : query.conditions()) {
                if (!known.contains(condition.column())) {
                    throw new SemanticException(
                            "Unknown predicate column: "
                                    + condition.column()
                    );
                }
            }

            query.orderBy().ifPresent(column -> {
                if (!known.contains(column)) {
                    throw new SemanticException(
                            "Unknown ORDER BY column: " + column
                    );
                }
            });

            query.limit().ifPresent(limit -> {
                if (limit < 0) {
                    throw new SemanticException(
                            "LIMIT cannot be negative"
                    );
                }
            });
        }
    }

    static final class Lexer {
        private static final Set<String> KEYWORDS = Set.of(
                "SELECT", "FROM", "WHERE", "AND",
                "ORDER", "BY", "ASC", "DESC", "LIMIT", "AS"
        );

        List<Token> tokenize(String sql) {
            List<Token> result = new ArrayList<>();
            int i = 0;

            while (i < sql.length()) {
                char ch = sql.charAt(i);

                if (Character.isWhitespace(ch)) {
                    i++;
                    continue;
                }

                if (ch == '\'') {
                    int start = i++;
                    StringBuilder value = new StringBuilder();

                    while (i < sql.length()) {
                        if (sql.charAt(i) == '\'' &&
                            i + 1 < sql.length() &&
                            sql.charAt(i + 1) == '\'') {
                            value.append('\'');
                            i += 2;
                        } else if (sql.charAt(i) == '\'') {
                            i++;
                            break;
                        } else {
                            value.append(sql.charAt(i++));
                        }
                    }

                    if (i > sql.length() ||
                        sql.charAt(i - 1) != '\'') {
                        throw new LexicalException(
                                "Unterminated string at " + start
                        );
                    }

                    result.add(new Token(
                            TokenType.STRING,
                            value.toString(),
                            start
                    ));
                    continue;
                }

                if (Character.isDigit(ch)) {
                    int start = i;
                    while (i < sql.length() &&
                           Character.isDigit(sql.charAt(i))) {
                        i++;
                    }

                    result.add(new Token(
                            TokenType.NUMBER,
                            sql.substring(start, i),
                            start
                    ));
                    continue;
                }

                if (Character.isLetter(ch) || ch == '_') {
                    int start = i;

                    while (i < sql.length() &&
                           (Character.isLetterOrDigit(sql.charAt(i)) ||
                            sql.charAt(i) == '_')) {
                        i++;
                    }

                    String value = sql.substring(start, i);
                    String upper = value.toUpperCase();

                    result.add(new Token(
                            KEYWORDS.contains(upper)
                                    ? TokenType.KEYWORD
                                    : TokenType.IDENTIFIER,
                            KEYWORDS.contains(upper) ? upper : value,
                            start
                    ));
                    continue;
                }

                String two = i + 1 < sql.length()
                        ? sql.substring(i, i + 2)
                        : "";

                if (Set.of(">=", "<=", "!=", "<>").contains(two)) {
                    result.add(new Token(
                            TokenType.OPERATOR,
                            two,
                            i
                    ));
                    i += 2;
                    continue;
                }

                if ("=<>".indexOf(ch) >= 0) {
                    result.add(new Token(
                            TokenType.OPERATOR,
                            String.valueOf(ch),
                            i
                    ));
                    i++;
                    continue;
                }

                if (",;*()".indexOf(ch) >= 0) {
                    result.add(new Token(
                            TokenType.SYMBOL,
                            String.valueOf(ch),
                            i
                    ));
                    i++;
                    continue;
                }

                throw new LexicalException(
                        "Unsupported character at " + i
                );
            }

            result.add(new Token(TokenType.EOF, "", sql.length()));
            return result;
        }
    }

    static final class Parser {
        private final List<Token> tokens;
        private int index;

        Parser(List<Token> tokens) {
            this.tokens = tokens;
        }

        private Token current() {
            return tokens.get(index);
        }

        private Token consume() {
            return tokens.get(index++);
        }

        private void expect(String value) {
            if (!current().value().equals(value)) {
                throw new ParseException(
                        "Expected " + value +
                                " at " + current().position()
                );
            }
            consume();
        }

        private String identifier() {
            if (current().type() != TokenType.IDENTIFIER) {
                throw new ParseException(
                        "Expected identifier at "
                                + current().position()
                );
            }
            return consume().value();
        }

        private Condition condition() {
            String column = identifier();

            if (current().type() != TokenType.OPERATOR) {
                throw new ParseException(
                        "Expected comparison operator"
                );
            }

            String operator = consume().value();
            Token value = consume();

            Object actual;

            switch (value.type()) {
                case NUMBER -> actual = Integer.parseInt(value.value());
                case STRING, IDENTIFIER -> actual = value.value();
                default -> throw new ParseException(
                        "Invalid comparison value"
                );
            }

            return new Condition(column, operator, actual);
        }

        Query parse() {
            expect("SELECT");

            List<SelectItem> columns = new ArrayList<>();

            if (current().value().equals("*")) {
                consume();
                columns.add(
                        new SelectItem("*", Optional.empty())
                );
            } else {
                while (true) {
                    String expression = identifier();
                    Optional<String> alias = Optional.empty();

                    if (current().value().equals("AS")) {
                        consume();
                        alias = Optional.of(identifier());
                    }

                    columns.add(
                            new SelectItem(expression, alias)
                    );

                    if (!current().value().equals(",")) {
                        break;
                    }
                    consume();
                }
            }

            expect("FROM");
            String table = identifier();

            List<Condition> conditions = new ArrayList<>();

            if (current().value().equals("WHERE")) {
                consume();
                conditions.add(condition());

                while (current().value().equals("AND")) {
                    consume();
                    conditions.add(condition());
                }
            }

            Optional<String> orderBy = Optional.empty();
            boolean descending = false;

            if (current().value().equals("ORDER")) {
                consume();
                expect("BY");
                orderBy = Optional.of(identifier());

                if (current().value().equals("DESC")) {
                    descending = true;
                    consume();
                } else if (current().value().equals("ASC")) {
                    consume();
                }
            }

            Optional<Integer> limit = Optional.empty();

            if (current().value().equals("LIMIT")) {
                consume();

                if (current().type() != TokenType.NUMBER) {
                    throw new ParseException(
                            "LIMIT requires a number"
                    );
                }

                limit = Optional.of(
                        Integer.parseInt(consume().value())
                );
            }

            if (current().value().equals(";")) {
                consume();
            }

            if (current().type() != TokenType.EOF) {
                throw new ParseException(
                        "Unexpected token " + current().value()
                );
            }

            return new Query(
                    List.copyOf(columns),
                    table,
                    List.copyOf(conditions),
                    orderBy,
                    descending,
                    limit
            );
        }
    }

    static final class Catalog {
        private final Map<String, Table> tables = new HashMap<>();

        void register(Table table) {
            if (tables.containsKey(table.name())) {
                throw new SemanticException(
                        "Duplicate table " + table.name()
                );
            }
            tables.put(table.name(), table);
        }

        Table resolve(String name) {
            Table table = tables.get(name);
            if (table == null) {
                throw new SemanticException(
                        "Unknown table " + name
                );
            }
            return table;
        }
    }

    static final class Planner {
        private final Catalog catalog;
        private final QueryPolicy policy;

        Planner(Catalog catalog, QueryPolicy policy) {
            this.catalog = catalog;
            this.policy = policy;
        }

        Query rewrite(Query query) {
            List<Condition> rewritten = query.conditions()
                    .stream()
                    .filter(condition ->
                            !(condition.operator().equals("=") &&
                              condition.column().equals("id") &&
                              condition.value() instanceof String &&
                              ((String) condition.value()).isEmpty()))
                    .toList();

            return new Query(
                    query.columns(),
                    query.table(),
                    rewritten,
                    query.orderBy(),
                    query.descending(),
                    query.limit()
            );
        }

        List<String> physicalPlan(Query query) {
            List<String> plan = new ArrayList<>();
            plan.add("TableScan(" + query.table() + ")");

            if (!query.conditions().isEmpty()) {
                plan.add("PredicateFilter");
            }

            query.orderBy().ifPresent(column ->
                    plan.add(
                            "Sort(" + column +
                                    (query.descending()
                                            ? " DESC)"
                                            : " ASC)")
                    )
            );

            query.limit().ifPresent(limit ->
                    plan.add("Limit(" + limit + ")")
            );

            plan.add("Projection");
            return List.copyOf(plan);
        }

        void validate(Query query) {
            policy.validate(query, catalog.resolve(query.table()));
        }
    }

    static final class ExecutionService {
        private final Catalog catalog;

        ExecutionService(Catalog catalog) {
            this.catalog = catalog;
        }

        private boolean compare(
                Object left,
                String operator,
                Object right
        ) {
            if (left instanceof Number &&
                right instanceof Number) {
                long a = ((Number) left).longValue();
                long b = ((Number) right).longValue();

                return switch (operator) {
                    case "=" -> a == b;
                    case "!=", "<>" -> a != b;
                    case ">" -> a > b;
                    case "<" -> a < b;
                    case ">=" -> a >= b;
                    case "<=" -> a <= b;
                    default -> throw new SemanticException(
                            "Unsupported operator " + operator
                    );
                };
            }

            if (left instanceof String &&
                right instanceof String) {
                int result = ((String) left)
                        .compareTo((String) right);

                return switch (operator) {
                    case "=" -> result == 0;
                    case "!=", "<>" -> result != 0;
                    case ">" -> result > 0;
                    case "<" -> result < 0;
                    case ">=" -> result >= 0;
                    case "<=" -> result <= 0;
                    default -> throw new SemanticException(
                            "Unsupported operator " + operator
                    );
                };
            }

            return false;
        }

        List<Row> execute(Query query) {
            List<Row> rows = new ArrayList<>(
                    catalog.resolve(query.table()).rows()
            );

            for (Condition condition : query.conditions()) {
                rows.removeIf(row -> !compare(
                        row.values().get(condition.column()),
                        condition.operator(),
                        condition.value()
                ));
            }

            query.orderBy().ifPresent(column -> {
                Comparator<Row> comparator =
                        Comparator.comparing(
                                row -> (Comparable) row.values()
                                        .get(column)
                        );

                if (query.descending()) {
                    comparator = comparator.reversed();
                }

                rows.sort(comparator);
            });

            if (query.limit().isPresent() &&
                rows.size() > query.limit().get()) {
                rows = new ArrayList<>(
                        rows.subList(0, query.limit().get())
                );
            }

            return rows;
        }
    }

    static Catalog createCatalog() {
        Catalog catalog = new Catalog();

        List<Row> rows = List.of(
                new Row(Map.of(
                        "id", 1,
                        "name", "Asha",
                        "department", "R&D",
                        "salary", 92000
                )),
                new Row(Map.of(
                        "id", 2,
                        "name", "Ravi",
                        "department", "Security",
                        "salary", 81000
                )),
                new Row(Map.of(
                        "id", 3,
                        "name", "Meera",
                        "department", "R&D",
                        "salary", 105000
                )),
                new Row(Map.of(
                        "id", 4,
                        "name", "Kabir",
                        "department", "Platform",
                        "salary", 76000
                )),
                new Row(Map.of(
                        "id", 5,
                        "name", "Nisha",
                        "department", "Security",
                        "salary", 97000
                ))
        );

        catalog.register(
                new Table(
                        "employees",
                        List.of(
                                "id",
                                "name",
                                "department",
                                "salary"
                        ),
                        rows
                )
        );

        return catalog;
    }

    static void printResult(
            Query query,
            List<Row> rows
    ) {
        if (query.columns().size() == 1 &&
            query.columns().getFirst().expression().equals("*")) {
            rows.forEach(row -> System.out.println(row.values()));
            return;
        }

        for (Row row : rows) {
            Map<String, Object> projected = new HashMap<>();

            for (SelectItem item : query.columns()) {
                projected.put(
                        item.alias().orElse(item.expression()),
                        row.values().get(item.expression())
                );
            }

            System.out.println(projected);
        }
    }

    static void process(
            String sql,
            Lexer lexer,
            Planner planner,
            ExecutionService executor
    ) {
        System.out.println("\nSQL: " + sql);

        List<Token> tokens = lexer.tokenize(sql);
        Query parsed = new Parser(tokens).parse();

        planner.validate(parsed);

        Query rewritten = planner.rewrite(parsed);

        System.out.println(
                "PLAN: " +
                        String.join(
                                " -> ",
                                planner.physicalPlan(rewritten)
                        )
        );

        List<Row> result = executor.execute(rewritten);

        System.out.println("ROWS: " + result.size());
        printResult(rewritten, result);
    }

    public static void main(String[] args) {
        Catalog catalog = createCatalog();
        Lexer lexer = new Lexer();
        Planner planner = new Planner(
                catalog,
                new StrictQueryPolicy()
        );
        ExecutionService executor =
                new ExecutionService(catalog);

        try {
            process(
                    "SELECT name, salary FROM employees " +
                            "WHERE salary >= 90000 " +
                            "ORDER BY salary DESC LIMIT 3",
                    lexer,
                    planner,
                    executor
            );

            process(
                    "SELECT name AS employee, department " +
                            "FROM employees " +
                            "WHERE department = 'Security'",
                    lexer,
                    planner,
                    executor
            );

            process(
                    "SELECT missing FROM employees",
                    lexer,
                    planner,
                    executor
            );
        } catch (QueryException exception) {
            System.out.println(
                    "\nExpected query failure: " +
                            exception.getMessage()
            );
        }
    }
}
