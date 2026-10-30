import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;
import java.util.Properties;
import java.util.concurrent.ThreadLocalRandom;

/*
 * Enterprise PostgreSQL command service.
 *
 * Commands:
 *   java PostgresOperations
 *   java PostgresOperations self-test
 *   java PostgresOperations health
 *   java PostgresOperations reserve ORDER_ID WAREHOUSE_ID
 *   java PostgresOperations fulfill ORDER_ID
 *   java PostgresOperations cancel ORDER_ID
 *
 * Live database access uses the PostgreSQL JDBC driver at runtime.
 * The source itself compiles against Java 17 without third-party imports.
 */

public class PostgresOperations {

    private static final int MAX_ATTEMPTS = 3;

    @FunctionalInterface
    interface SqlWork<T> {
        T execute(Connection connection) throws SQLException;
    }

    interface ConnectionProvider {
        Connection open() throws SQLException;
    }

    static final class DatabaseConfiguration {
        private final String url;
        private final Properties properties;

        DatabaseConfiguration(String url, Properties properties) {
            if (url == null || !url.startsWith("jdbc:postgresql:")) {
                throw new IllegalArgumentException(
                    "PGJDBC_URL must be a PostgreSQL JDBC URL"
                );
            }

            this.url = url;
            this.properties = new Properties();
            this.properties.putAll(properties);
        }

        static DatabaseConfiguration fromEnvironment() {
            String url = System.getenv("PGJDBC_URL");

            if (url == null || url.isBlank()) {
                throw new IllegalStateException(
                    "Set PGJDBC_URL before running a live database command"
                );
            }

            Properties properties = new Properties();

            String user = System.getenv("PGUSER");
            String password = System.getenv("PGPASSWORD");

            if (user != null && !user.isBlank()) {
                properties.setProperty("user", user);
            }

            if (password != null && !password.isBlank()) {
                properties.setProperty("password", password);
            }

            // Bound connection setup and socket waiting. Query execution
            // also receives server-side statement and lock timeouts.
            properties.setProperty("connectTimeout", "5");
            properties.setProperty("socketTimeout", "20");
            properties.setProperty(
                "ApplicationName",
                "postgres-enterprise-operations"
            );

            return new DatabaseConfiguration(url, properties);
        }

        ConnectionProvider createProvider() {
            return () -> DriverManager.getConnection(url, properties);
        }
    }

    static final class RetryPolicy {
        private final int maximumAttempts;

        RetryPolicy(int maximumAttempts) {
            if (maximumAttempts < 1 || maximumAttempts > 5) {
                throw new IllegalArgumentException(
                    "maximumAttempts must be between 1 and 5"
                );
            }
            this.maximumAttempts = maximumAttempts;
        }

        boolean shouldRetry(String sqlState, int completedAttempt) {
            if (completedAttempt >= maximumAttempts || sqlState == null) {
                return false;
            }

            // PostgreSQL transaction rollback errors:
            // 40001 = serialization_failure
            // 40P01 = deadlock_detected
            return sqlState.equals("40001") ||
                   sqlState.equals("40P01");
        }

        int maximumAttempts() {
            return maximumAttempts;
        }
    }

    static final class TransactionExecutor {
        private final ConnectionProvider provider;
        private final RetryPolicy retryPolicy;

        TransactionExecutor(
            ConnectionProvider provider,
            RetryPolicy retryPolicy
        ) {
            this.provider = provider;
            this.retryPolicy = retryPolicy;
        }

        <T> T execute(SqlWork<T> work) throws SQLException {
            SQLException lastRetryableFailure = null;

            for (int attempt = 1;
                 attempt <= retryPolicy.maximumAttempts();
                 attempt++) {

                try (Connection connection = provider.open()) {
                    connection.setAutoCommit(false);
                    connection.setTransactionIsolation(
                        Connection.TRANSACTION_READ_COMMITTED
                    );

                    try {
                        configureTransaction(connection);

                        T result = work.execute(connection);
                        connection.commit();
                        return result;
                    } catch (SQLException exception) {
                        rollbackWithoutMasking(connection, exception);

                        if (!retryPolicy.shouldRetry(
                                exception.getSQLState(), attempt)) {
                            throw exception;
                        }

                        lastRetryableFailure = exception;
                    } catch (RuntimeException exception) {
                        rollbackWithoutMasking(connection, exception);
                        throw exception;
                    }
                }

                if (attempt < retryPolicy.maximumAttempts()) {
                    waitBeforeRetry(attempt);
                }
            }

            throw lastRetryableFailure != null
                ? lastRetryableFailure
                : new SQLException("Transaction attempts exhausted");
        }

        private static void configureTransaction(
            Connection connection
        ) throws SQLException {
            try (Statement statement = connection.createStatement()) {
                statement.execute(
                    "SET LOCAL statement_timeout = '5s'"
                );
                statement.execute(
                    "SET LOCAL lock_timeout = '2s'"
                );
            }
        }

        private static void rollbackWithoutMasking(
            Connection connection,
            Exception original
        ) {
            try {
                connection.rollback();
            } catch (SQLException rollbackFailure) {
                original.addSuppressed(rollbackFailure);
            }
        }

        private static void waitBeforeRetry(int attempt)
            throws SQLException {
            long baseDelay = Math.min(200L * (1L << (attempt - 1)), 1000L);
            long jitter = ThreadLocalRandom.current().nextLong(0, 101);

            try {
                Thread.sleep(baseDelay + jitter);
            } catch (InterruptedException exception) {
                Thread.currentThread().interrupt();
                throw new SQLException(
                    "Transaction retry interrupted",
                    exception
                );
            }
        }
    }

    record ServerHealth(
        String database,
        int serverVersionNumber,
        boolean replica
    ) {
        ServerHealth {
            if (database == null || database.isBlank()) {
                throw new IllegalArgumentException(
                    "Database name cannot be empty"
                );
            }
            if (serverVersionNumber <= 0) {
                throw new IllegalArgumentException(
                    "Invalid PostgreSQL server version"
                );
            }
        }

        String formattedVersion() {
            int major = serverVersionNumber / 10000;
            int minor = (serverVersionNumber / 100) % 100;

            if (major >= 10) {
                return Integer.toString(major);
            }

            return major + "." + minor;
        }
    }

    static final class PostgreSqlHealthService {
        private final ConnectionProvider provider;

        PostgreSqlHealthService(ConnectionProvider provider) {
            this.provider = provider;
        }

        ServerHealth inspect() throws SQLException {
            String sql = """
                SELECT current_database(),
                       current_setting('server_version_num')::integer,
                       pg_is_in_recovery()
                """;

            try (Connection connection = provider.open();
                 Statement statement = connection.createStatement();
                 ResultSet result = statement.executeQuery(sql)) {

                if (!result.next()) {
                    throw new SQLException(
                        "PostgreSQL health query returned no rows"
                    );
                }

                return new ServerHealth(
                    result.getString(1),
                    result.getInt(2),
                    result.getBoolean(3)
                );
            }
        }
    }

    static final class OrderCommandService {
        private final TransactionExecutor transactions;

        OrderCommandService(TransactionExecutor transactions) {
            this.transactions = transactions;
        }

        void reserve(long orderId, long warehouseId)
            throws SQLException {
            requirePositive(orderId, "orderId");
            requirePositive(warehouseId, "warehouseId");

            transactions.execute(connection -> {
                try (PreparedStatement statement =
                         connection.prepareStatement(
                             "SELECT app.reserve_order(?, ?)"
                         )) {
                    statement.setLong(1, orderId);
                    statement.setLong(2, warehouseId);
                    statement.execute();
                }
                return null;
            });
        }

        void fulfill(long orderId) throws SQLException {
            requirePositive(orderId, "orderId");

            transactions.execute(connection -> {
                try (PreparedStatement statement =
                         connection.prepareStatement(
                             "SELECT app.fulfill_order(?)"
                         )) {
                    statement.setLong(1, orderId);
                    statement.execute();
                }
                return null;
            });
        }

        void cancel(long orderId) throws SQLException {
            requirePositive(orderId, "orderId");

            transactions.execute(connection -> {
                try (PreparedStatement statement =
                         connection.prepareStatement(
                             "SELECT app.cancel_order(?)"
                         )) {
                    statement.setLong(1, orderId);
                    statement.execute();
                }
                return null;
            });
        }

        private static void requirePositive(long value, String name) {
            if (value <= 0) {
                throw new IllegalArgumentException(
                    name + " must be greater than zero"
                );
            }
        }
    }

    private static void runSelfTest() {
        RetryPolicy policy = new RetryPolicy(MAX_ATTEMPTS);

        require(
            policy.shouldRetry("40001", 1),
            "Serialization failure should be retried"
        );

        require(
            policy.shouldRetry("40P01", 1),
            "Deadlock should be retried"
        );

        require(
            !policy.shouldRetry("23505", 1),
            "Unique constraint violations must not be retried"
        );

        require(
            !policy.shouldRetry("40001", MAX_ATTEMPTS),
            "Retry limit must be enforced"
        );

        ServerHealth health = new ServerHealth(
            "orders",
            160004,
            false
        );

        require(
            health.formattedVersion().equals("16"),
            "Major version formatting failed"
        );

        boolean rejected = false;

        try {
            new ServerHealth("", 160004, false);
        } catch (IllegalArgumentException exception) {
            rejected = true;
        }

        require(rejected, "Invalid health record was accepted");

        System.out.println("Self-test passed.");
        System.out.println("Retry policy, validation and domain checks passed.");
    }

    private static void require(boolean condition, String message) {
        if (!condition) {
            throw new IllegalStateException(message);
        }
    }

    private static long parsePositiveLong(
        String value,
        String argumentName
    ) {
        try {
            long parsed = Long.parseLong(value);

            if (parsed <= 0) {
                throw new IllegalArgumentException(
                    argumentName + " must be greater than zero"
                );
            }

            return parsed;
        } catch (NumberFormatException exception) {
            throw new IllegalArgumentException(
                argumentName + " must be a valid integer",
                exception
            );
        }
    }

    private static void printUsage() {
        System.out.println("""
            PostgreSQL enterprise operations

            Commands:
              self-test
              health
              reserve ORDER_ID WAREHOUSE_ID
              fulfill ORDER_ID
              cancel ORDER_ID

            Live database configuration:
              PGJDBC_URL
              PGUSER
              PGPASSWORD

            The PostgreSQL JDBC driver must be available on the runtime classpath.
            """);
    }

    public static void main(String[] args) {
        String command = args.length == 0 ? "self-test" : args[0];

        try {
            if (command.equals("self-test")) {
                runSelfTest();
                return;
            }

            if (command.equals("help") || command.equals("--help")) {
                printUsage();
                return;
            }

            DatabaseConfiguration configuration =
                DatabaseConfiguration.fromEnvironment();

            ConnectionProvider provider =
                configuration.createProvider();

            if (command.equals("health")) {
                if (args.length != 1) {
                    throw new IllegalArgumentException(
                        "health does not accept additional arguments"
                    );
                }

                ServerHealth health =
                    new PostgreSqlHealthService(provider).inspect();

                System.out.println("Database: " + health.database());
                System.out.println(
                    "PostgreSQL version: " + health.formattedVersion()
                );
                System.out.println(
                    "Server role: " +
                    (health.replica() ? "standby" : "primary")
                );
                return;
            }

            RetryPolicy retryPolicy = new RetryPolicy(MAX_ATTEMPTS);
            TransactionExecutor executor =
                new TransactionExecutor(provider, retryPolicy);
            OrderCommandService orders =
                new OrderCommandService(executor);

            switch (command) {
                case "reserve" -> {
                    if (args.length != 3) {
                        throw new IllegalArgumentException(
                            "reserve requires ORDER_ID and WAREHOUSE_ID"
                        );
                    }

                    orders.reserve(
                        parsePositiveLong(args[1], "ORDER_ID"),
                        parsePositiveLong(args[2], "WAREHOUSE_ID")
                    );
                }
                case "fulfill" -> {
                    if (args.length != 2) {
                        throw new IllegalArgumentException(
                            "fulfill requires ORDER_ID"
                        );
                    }

                    orders.fulfill(
                        parsePositiveLong(args[1], "ORDER_ID")
                    );
                }
                case "cancel" -> {
                    if (args.length != 2) {
                        throw new IllegalArgumentException(
                            "cancel requires ORDER_ID"
                        );
                    }

                    orders.cancel(
                        parsePositiveLong(args[1], "ORDER_ID")
                    );
                }
                default -> {
                    printUsage();
                    throw new IllegalArgumentException(
                        "Unsupported command: " + command
                    );
                }
            }

            System.out.println(
                "PostgreSQL order operation completed successfully."
            );

        } catch (SQLException exception) {
            String state = exception.getSQLState();
            System.err.println(
                "DATABASE ERROR: SQLSTATE=" +
                (state == null ? "unknown" : state)
            );
            System.err.println(
                "Check database connectivity, privileges, transaction "
                + "state and server logs."
            );
            System.exitCode = 1;
        } catch (IllegalArgumentException | IllegalStateException exception) {
            System.err.println("ERROR: " + exception.getMessage());
            System.exitCode = 1;
        }
    }
}
