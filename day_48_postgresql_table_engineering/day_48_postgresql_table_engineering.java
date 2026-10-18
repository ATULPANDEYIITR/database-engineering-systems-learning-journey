import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.regex.Pattern;

/*
 * PostgreSQL Table Engineering: enterprise schema governance.
 *
 * Java 17+
 *
 * Models table definitions, migration plans, schema compatibility checks,
 * relational constraints, and deployment state for a product catalog.
 *
 * This program performs offline validation. Database execution would require
 * a JDBC PostgreSQL driver and an explicit migration deployment layer.
 */

public class TableEngineering {
    private static final Pattern IDENTIFIER =
            Pattern.compile("[a-z][a-z0-9_]*");

    enum DataType {
        BIGINT,
        INTEGER,
        TEXT,
        BOOLEAN,
        NUMERIC_12_2,
        TIMESTAMPTZ
    }

    enum ConstraintType {
        PRIMARY_KEY,
        UNIQUE,
        NOT_NULL,
        CHECK,
        FOREIGN_KEY,
        DEFAULT
    }

    enum MigrationState {
        PLANNED,
        VALIDATED,
        APPLIED,
        FAILED
    }

    record ColumnDefinition(
            String name,
            DataType type,
            boolean nullable,
            String defaultExpression
    ) {
        ColumnDefinition {
            Objects.requireNonNull(name);
            Objects.requireNonNull(type);

            if (!IDENTIFIER.matcher(name).matches()) {
                throw new IllegalArgumentException(
                        "Invalid column identifier: " + name
                );
            }

            if (defaultExpression != null &&
                    defaultExpression.contains(";")) {
                throw new IllegalArgumentException(
                        "Default expression contains a semicolon"
                );
            }
        }
    }

    record ForeignKeyDefinition(
            String name,
            String sourceTable,
            String sourceColumn,
            String targetTable,
            String targetColumn,
            boolean sourceNullable
    ) {
        ForeignKeyDefinition {
            Objects.requireNonNull(name);
            Objects.requireNonNull(sourceTable);
            Objects.requireNonNull(sourceColumn);
            Objects.requireNonNull(targetTable);
            Objects.requireNonNull(targetColumn);

            if (!IDENTIFIER.matcher(name).matches() ||
                    !IDENTIFIER.matcher(sourceTable).matches() ||
                    !IDENTIFIER.matcher(sourceColumn).matches() ||
                    !IDENTIFIER.matcher(targetTable).matches() ||
                    !IDENTIFIER.matcher(targetColumn).matches()) {
                throw new IllegalArgumentException(
                        "Foreign key contains an invalid identifier"
                );
            }
        }
    }

    static final class TableDefinition {
        private final String name;
        private final Map<String, ColumnDefinition> columns =
                new HashMap<>();
        private final List<List<String>> uniqueKeys = new ArrayList<>();
        private final List<String> primaryKey = new ArrayList<>();
        private final List<String> checks = new ArrayList<>();

        TableDefinition(String name) {
            if (!IDENTIFIER.matcher(name).matches()) {
                throw new IllegalArgumentException(
                        "Invalid table identifier: " + name
                );
            }
            this.name = name;
        }

        TableDefinition addColumn(ColumnDefinition column) {
            if (columns.putIfAbsent(column.name(), column) != null) {
                throw new IllegalArgumentException(
                        "Duplicate column " + column.name()
                                + " in table " + name
                );
            }
            return this;
        }

        TableDefinition primaryKey(String... names) {
            if (names.length == 0) {
                throw new IllegalArgumentException(
                        "Primary key cannot be empty"
                );
            }

            primaryKey.clear();
            primaryKey.addAll(List.of(names));
            return this;
        }

        TableDefinition unique(String... names) {
            if (names.length == 0) {
                throw new IllegalArgumentException(
                        "Unique key cannot be empty"
                );
            }

            uniqueKeys.add(List.of(names));
            return this;
        }

        TableDefinition check(String expression) {
            if (expression == null || expression.isBlank()) {
                throw new IllegalArgumentException(
                        "CHECK expression cannot be empty"
                );
            }
            checks.add(expression);
            return this;
        }

        void validate() {
            if (primaryKey.isEmpty()) {
                throw new IllegalStateException(
                        "Missing primary key on " + name
                );
            }

            for (String columnName : primaryKey) {
                ColumnDefinition column = columns.get(columnName);
                if (column == null) {
                    throw new IllegalStateException(
                            "Primary key references missing column "
                                    + columnName
                    );
                }

                if (column.nullable()) {
                    throw new IllegalStateException(
                            "Primary key column cannot be nullable: "
                                    + columnName
                    );
                }
            }

            for (List<String> key : uniqueKeys) {
                for (String columnName : key) {
                    if (!columns.containsKey(columnName)) {
                        throw new IllegalStateException(
                                "Unique key references missing column "
                                        + columnName
                        );
                    }
                }
            }
        }

        boolean isSingleColumnUnique(String columnName) {
            if (primaryKey.equals(List.of(columnName))) {
                return true;
            }

            return uniqueKeys.contains(List.of(columnName));
        }

        ColumnDefinition column(String name) {
            return columns.get(name);
        }

        String name() {
            return name;
        }

        void print() {
            System.out.println("\nTable: " + name);

            columns.values().stream()
                    .sorted((a, b) -> a.name().compareTo(b.name()))
                    .forEach(column -> System.out.printf(
                            "  %-18s %-14s nullable=%-5s default=%s%n",
                            column.name(),
                            column.type(),
                            column.nullable(),
                            column.defaultExpression()
                    ));

            System.out.println("  PRIMARY KEY " + primaryKey);
            uniqueKeys.forEach(key ->
                    System.out.println("  UNIQUE " + key)
            );
            checks.forEach(check ->
                    System.out.println("  CHECK (" + check + ")")
            );
        }
    }

    static final class Migration {
        private final String version;
        private final String description;
        private final List<String> statements;
        private MigrationState state = MigrationState.PLANNED;

        Migration(
                String version,
                String description,
                List<String> statements
        ) {
            if (version == null || !version.matches("[0-9]{3}")) {
                throw new IllegalArgumentException(
                        "Migration version must contain three digits"
                );
            }

            if (description == null || description.isBlank()) {
                throw new IllegalArgumentException(
                        "Migration description is required"
                );
            }

            if (statements == null || statements.isEmpty()) {
                throw new IllegalArgumentException(
                        "Migration requires SQL statements"
                );
            }

            this.version = version;
            this.description = description;
            this.statements = List.copyOf(statements);
        }

        void validate() {
            for (String statement : statements) {
                if (statement == null || statement.isBlank()) {
                    state = MigrationState.FAILED;
                    throw new IllegalStateException(
                            "Migration contains an empty statement"
                    );
                }
            }

            state = MigrationState.VALIDATED;
        }

        void markApplied() {
            if (state != MigrationState.VALIDATED) {
                throw new IllegalStateException(
                        "Only validated migrations can be marked applied"
                );
            }
            state = MigrationState.APPLIED;
        }

        String version() {
            return version;
        }

        MigrationState state() {
            return state;
        }

        void print() {
            System.out.printf(
                    "%s | %s | %s | %d statements%n",
                    version,
                    description,
                    state,
                    statements.size()
            );
        }
    }

    static final class SchemaRegistry {
        private final Map<String, TableDefinition> tables =
                new HashMap<>();
        private final Set<String> foreignKeyNames = new HashSet<>();

        void register(TableDefinition table) {
            table.validate();

            if (tables.putIfAbsent(table.name(), table) != null) {
                throw new IllegalArgumentException(
                        "Table already registered: " + table.name()
                );
            }
        }

        void registerForeignKey(
                ForeignKeyDefinition foreignKey
        ) {
            if (!foreignKeyNames.add(foreignKey.name())) {
                throw new IllegalArgumentException(
                        "Duplicate constraint name: " + foreignKey.name()
                );
            }

            TableDefinition source = tables.get(
                    foreignKey.sourceTable()
            );
            TableDefinition target = tables.get(
                    foreignKey.targetTable()
            );

            if (source == null || target == null) {
                foreignKeyNames.remove(foreignKey.name());
                throw new IllegalArgumentException(
                        "Foreign key references an unknown table"
                );
            }

            ColumnDefinition sourceColumn =
                    source.column(foreignKey.sourceColumn());
            ColumnDefinition targetColumn =
                    target.column(foreignKey.targetColumn());

            if (sourceColumn == null || targetColumn == null) {
                foreignKeyNames.remove(foreignKey.name());
                throw new IllegalArgumentException(
                        "Foreign key references an unknown column"
                );
            }

            if (sourceColumn.type() != targetColumn.type()) {
                foreignKeyNames.remove(foreignKey.name());
                throw new IllegalArgumentException(
                        "Foreign key column types are incompatible"
                );
            }

            if (!target.isSingleColumnUnique(
                    foreignKey.targetColumn())) {
                foreignKeyNames.remove(foreignKey.name());
                throw new IllegalArgumentException(
                        "Referenced column must be unique"
                );
            }

            if (foreignKey.sourceNullable() != sourceColumn.nullable()) {
                foreignKeyNames.remove(foreignKey.name());
                throw new IllegalArgumentException(
                        "Foreign key nullability does not match the column"
                );
            }

            System.out.printf(
                    "Registered %s: %s.%s -> %s.%s%n",
                    foreignKey.name(),
                    foreignKey.sourceTable(),
                    foreignKey.sourceColumn(),
                    foreignKey.targetTable(),
                    foreignKey.targetColumn()
            );
        }

        void print() {
            tables.values().stream()
                    .sorted((a, b) ->
                            a.name().compareTo(b.name()))
                    .forEach(TableDefinition::print);
        }
    }

    private static List<Migration> createMigrationPlan() {
        return List.of(
                new Migration(
                        "001",
                        "Create category and product tables",
                        List.of(
                                """
                                CREATE TABLE inventory.categories (
                                  category_id BIGINT
                                    GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                                  category_name TEXT NOT NULL UNIQUE,
                                  CONSTRAINT ck_category_name
                                    CHECK (length(btrim(category_name)) > 0)
                                )
                                """,
                                """
                                CREATE TABLE inventory.products (
                                  product_id BIGINT
                                    GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                                  sku TEXT NOT NULL UNIQUE,
                                  product_name TEXT NOT NULL,
                                  category_id BIGINT,
                                  unit_price NUMERIC(12,2)
                                    NOT NULL DEFAULT 0,
                                  stock_quantity INTEGER
                                    NOT NULL DEFAULT 0,
                                  CONSTRAINT ck_product_price
                                    CHECK (unit_price >= 0),
                                  CONSTRAINT ck_product_stock
                                    CHECK (stock_quantity >= 0),
                                  CONSTRAINT fk_product_category
                                    FOREIGN KEY (category_id)
                                    REFERENCES inventory.categories(category_id)
                                    ON DELETE SET NULL
                                )
                                """
                        )
                ),
                new Migration(
                        "002",
                        "Add product audit metadata",
                        List.of(
                                """
                                ALTER TABLE inventory.products
                                  ADD COLUMN description TEXT
                                    NOT NULL DEFAULT ''
                                """,
                                """
                                ALTER TABLE inventory.products
                                  ADD COLUMN updated_at TIMESTAMPTZ
                                    NOT NULL DEFAULT CURRENT_TIMESTAMP
                                """
                        )
                )
        );
    }

    private static void demonstrateConstraints() {
        System.out.println("\nConstraint responsibilities:");

        Map<ConstraintType, String> responsibilities = Map.of(
                ConstraintType.PRIMARY_KEY,
                "Identifies a row and disallows NULL key values.",
                ConstraintType.UNIQUE,
                "Prevents duplicate values or duplicate key combinations.",
                ConstraintType.NOT_NULL,
                "Rejects missing mandatory attributes.",
                ConstraintType.CHECK,
                "Restricts values according to a Boolean expression.",
                ConstraintType.FOREIGN_KEY,
                "Requires a matching referenced key when the FK is non-NULL.",
                ConstraintType.DEFAULT,
                "Supplies a value when an insert omits a column."
        );

        responsibilities.forEach((type, explanation) ->
                System.out.println(type + ": " + explanation)
        );

        System.out.println(
                "PostgreSQL CHECK constraints do not reject UNKNOWN by "
                        + "themselves. Combine CHECK with NOT NULL where "
                        + "missing values are prohibited."
        );
    }

    public static void main(String[] args) {
        try {
            SchemaRegistry registry = new SchemaRegistry();

            TableDefinition categories = new TableDefinition("categories")
                    .addColumn(new ColumnDefinition(
                            "category_id", DataType.BIGINT, false, null))
                    .addColumn(new ColumnDefinition(
                            "category_name", DataType.TEXT, false, null))
                    .primaryKey("category_id")
                    .unique("category_name")
                    .check("length(btrim(category_name)) > 0");

            TableDefinition products = new TableDefinition("products")
                    .addColumn(new ColumnDefinition(
                            "product_id", DataType.BIGINT, false, null))
                    .addColumn(new ColumnDefinition(
                            "sku", DataType.TEXT, false, null))
                    .addColumn(new ColumnDefinition(
                            "product_name", DataType.TEXT, false, null))
                    .addColumn(new ColumnDefinition(
                            "category_id", DataType.BIGINT, true, null))
                    .addColumn(new ColumnDefinition(
                            "unit_price", DataType.NUMERIC_12_2,
                            false, "0.00"))
                    .addColumn(new ColumnDefinition(
                            "stock_quantity", DataType.INTEGER,
                            false, "0"))
                    .primaryKey("product_id")
                    .unique("sku")
                    .check("unit_price >= 0")
                    .check("stock_quantity >= 0");

            TableDefinition customers = new TableDefinition("customers")
                    .addColumn(new ColumnDefinition(
                            "customer_id", DataType.BIGINT, false, null))
                    .addColumn(new ColumnDefinition(
                            "email", DataType.TEXT, false, null))
                    .primaryKey("customer_id")
                    .unique("email");

            registry.register(categories);
            registry.register(products);
            registry.register(customers);

            registry.registerForeignKey(new ForeignKeyDefinition(
                    "fk_product_category",
                    "products", "category_id",
                    "categories", "category_id",
                    true
            ));

            registry.print();
            demonstrateConstraints();

            System.out.println("\nMigration deployment plan:");
            List<Migration> migrations = createMigrationPlan();

            String previousVersion = null;

            for (Migration migration : migrations) {
                if (previousVersion != null &&
                        migration.version().compareTo(previousVersion) <= 0) {
                    throw new IllegalStateException(
                            "Migration versions are not strictly increasing"
                    );
                }

                migration.validate();
                migration.print();
                previousVersion = migration.version();
            }

            // Offline validation must not be mistaken for database execution.
            System.out.println(
                    "\nMigrations are validated, not applied. A real "
                            + "deployment must execute each version "
                            + "transactionally and record its checksum."
            );

            try {
                new ColumnDefinition(
                        "sku; DROP TABLE products",
                        DataType.TEXT,
                        false,
                        null
                );
            } catch (IllegalArgumentException error) {
                System.out.println(
                        "Rejected unsafe identifier: " + error.getMessage()
                );
            }

            try {
                migrations.get(0).markApplied();
            } catch (IllegalStateException error) {
                System.out.println(
                        "State transition rejected: " + error.getMessage()
                );
            }
        } catch (RuntimeException error) {
            System.err.println(
                    "Schema governance error: " + error.getMessage()
            );
            System.exit(1);
        }
    }
}
