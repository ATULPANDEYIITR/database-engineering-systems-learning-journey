import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.TreeMap;

/*
 * PostgreSQL Fundamentals: enterprise environment registry.
 *
 * Java 17 or later:
 *   javac PostgresFundamentals.java
 *   java PostgresFundamentals
 *
 * The registry models the configuration and validation layer around a
 * PostgreSQL deployment. It does not replace the actual PostgreSQL server.
 */

public class PostgresFundamentals {

    enum Privilege {
        CONNECT,
        CREATE,
        USAGE,
        SELECT,
        INSERT,
        UPDATE,
        DELETE
    }

    record ConnectionProfile(
            String host,
            int port,
            String database,
            String username,
            String applicationName
    ) {
        ConnectionProfile {
            if (host == null || host.isBlank()) {
                throw new IllegalArgumentException("Host must not be empty");
            }
            if (port < 1 || port > 65535) {
                throw new IllegalArgumentException("Invalid TCP port");
            }
            requireIdentifier(database, "database");
            requireIdentifier(username, "username");
            if (applicationName == null || applicationName.isBlank()) {
                throw new IllegalArgumentException("Application name is required");
            }
        }

        String display() {
            return "host=" + host
                    + " port=" + port
                    + " dbname=" + database
                    + " user=" + username
                    + " application_name=" + applicationName;
        }
    }

    static final class Role {
        private final String name;
        private final boolean canLogin;
        private final boolean superuser;
        private final Set<String> memberships = new LinkedHashSet<>();

        Role(String name, boolean canLogin, boolean superuser) {
            requireIdentifier(name, "role");
            this.name = name;
            this.canLogin = canLogin;
            this.superuser = superuser;
        }

        String name() {
            return name;
        }

        boolean canLogin() {
            return canLogin;
        }

        boolean superuser() {
            return superuser;
        }

        void inheritMembership(String roleName) {
            requireIdentifier(roleName, "membership role");
            if (roleName.equals(name)) {
                throw new IllegalArgumentException("A role cannot inherit itself");
            }
            memberships.add(roleName);
        }

        Set<String> memberships() {
            return Set.copyOf(memberships);
        }
    }

    static final class Relation {
        private final String name;
        private final List<String> columns;
        private long estimatedRows;

        Relation(String name, List<String> columns, long estimatedRows) {
            requireIdentifier(name, "relation");
            if (columns == null || columns.isEmpty()) {
                throw new IllegalArgumentException("A relation needs columns");
            }
            if (estimatedRows < 0) {
                throw new IllegalArgumentException("Row estimate cannot be negative");
            }
            this.name = name;
            this.columns = List.copyOf(columns);
            this.estimatedRows = estimatedRows;
        }

        String name() {
            return name;
        }

        List<String> columns() {
            return columns;
        }

        long estimatedRows() {
            return estimatedRows;
        }
    }

    static final class Schema {
        private final String name;
        private final Map<String, Relation> relations = new LinkedHashMap<>();

        Schema(String name) {
            requireIdentifier(name, "schema");
            this.name = name;
        }

        void createRelation(Relation relation) {
            Objects.requireNonNull(relation);
            if (relations.putIfAbsent(relation.name(), relation) != null) {
                throw new IllegalStateException(
                        "Relation already exists: " + name + "." + relation.name()
                );
            }
        }

        String name() {
            return name;
        }

        Map<String, Relation> relations() {
            return Map.copyOf(relations);
        }
    }

    static final class Database {
        private final String name;
        private final String owner;
        private final Map<String, Schema> schemas = new LinkedHashMap<>();
        private final Map<String, Set<Privilege>> grants = new LinkedHashMap<>();

        Database(String name, String owner) {
            requireIdentifier(name, "database");
            requireIdentifier(owner, "database owner");
            this.name = name;
            this.owner = owner;
            schemas.put("public", new Schema("public"));
        }

        void createSchema(String schemaName) {
            Schema schema = new Schema(schemaName);
            if (schemas.putIfAbsent(schemaName, schema) != null) {
                throw new IllegalStateException("Schema already exists: " + schemaName);
            }
        }

        Schema schema(String schemaName) {
            Schema result = schemas.get(schemaName);
            if (result == null) {
                throw new IllegalArgumentException("Unknown schema: " + schemaName);
            }
            return result;
        }

        void grant(String roleName, Privilege... privileges) {
            requireIdentifier(roleName, "grantee");
            Set<Privilege> current =
                    grants.computeIfAbsent(roleName, ignored ->
                            new LinkedHashSet<>());
            for (Privilege privilege : privileges) {
                current.add(Objects.requireNonNull(privilege));
            }
        }

        boolean hasPrivilege(String roleName, Privilege privilege) {
            return grants.getOrDefault(roleName, Set.of()).contains(privilege);
        }

        String name() {
            return name;
        }

        String owner() {
            return owner;
        }

        Map<String, Schema> schemas() {
            return Map.copyOf(schemas);
        }
    }

    static final class Environment {
        private final Map<String, Role> roles = new TreeMap<>();
        private final Map<String, Database> databases = new TreeMap<>();

        void createRole(Role role) {
            if (roles.putIfAbsent(role.name(), role) != null) {
                throw new IllegalStateException("Role already exists: " + role.name());
            }
        }

        void createDatabase(String name, String owner) {
            if (!roles.containsKey(owner)) {
                throw new IllegalArgumentException("Unknown owner role: " + owner);
            }
            Database database = new Database(name, owner);
            if (databases.putIfAbsent(name, database) != null) {
                throw new IllegalStateException("Database already exists: " + name);
            }
        }

        void validateConnection(ConnectionProfile profile) {
            Database database = databases.get(profile.database());
            if (database == null) {
                throw new IllegalArgumentException(
                        "Target database does not exist: " + profile.database()
                );
            }

            Role role = roles.get(profile.username());
            if (role == null || !role.canLogin()) {
                throw new SecurityException(
                        "Role is missing or cannot log in: " + profile.username()
                );
            }

            if (!role.superuser()
                    && !profile.username().equals(database.owner())
                    && !database.hasPrivilege(profile.username(), Privilege.CONNECT)) {
                throw new SecurityException(
                        "CONNECT privilege is not granted on " + database.name()
                );
            }
        }

        Database database(String name) {
            Database database = databases.get(name);
            if (database == null) {
                throw new IllegalArgumentException("Database not found: " + name);
            }
            return database;
        }

        Map<String, Role> roles() {
            return Map.copyOf(roles);
        }

        Map<String, Database> databases() {
            return Map.copyOf(databases);
        }
    }

    static final class ConnectionRegistry {
        private final Map<String, Integer> activeConnections = new LinkedHashMap<>();
        private final Map<String, Integer> limits = new LinkedHashMap<>();

        void setLimit(String database, int limit) {
            if (limit < 1) {
                throw new IllegalArgumentException("Connection limit must be positive");
            }
            limits.put(database, limit);
        }

        void open(String database) {
            int current = activeConnections.getOrDefault(database, 0);
            int limit = limits.getOrDefault(database, 100);
            if (current >= limit) {
                throw new IllegalStateException(
                        "Connection capacity reached for " + database
                );
            }
            activeConnections.put(database, current + 1);
        }

        void close(String database) {
            int current = activeConnections.getOrDefault(database, 0);
            if (current == 0) {
                throw new IllegalStateException("No connection to close");
            }
            activeConnections.put(database, current - 1);
        }
    }

    private static void requireIdentifier(String value, String description) {
        if (value == null || !value.matches("[A-Za-z_][A-Za-z0-9_]*")) {
            throw new IllegalArgumentException("Invalid " + description + " identifier");
        }
    }

    private static void printCatalogView(Environment environment) {
        System.out.println("\nConfigured database inventory");
        environment.databases().values().stream()
                .sorted(Comparator.comparing(Database::name))
                .forEach(database -> {
                    System.out.println(
                            database.name() + " owner=" + database.owner()
                    );
                    database.schemas().values().stream()
                            .sorted(Comparator.comparing(Schema::name))
                            .forEach(schema -> {
                                System.out.println("  schema=" + schema.name());
                                schema.relations().values().forEach(relation ->
                                        System.out.println(
                                                "    relation=" + relation.name()
                                                + " columns=" + relation.columns()
                                                + " estimatedRows="
                                                + relation.estimatedRows()
                                        )
                                );
                            });
                });
    }

    public static void main(String[] args) {
        try {
            Environment environment = new Environment();

            environment.createRole(new Role("postgres", true, true));
            environment.createRole(new Role("plant_owner", true, false));
            environment.createRole(new Role("quality_reader", true, false));
            environment.createRole(new Role("schema_migrator", true, false));

            environment.createDatabase("plant_operations", "plant_owner");
            environment.createDatabase("quality_reporting", "postgres");

            Database plant = environment.database("plant_operations");
            plant.createSchema("operations");
            plant.createSchema("quality");

            plant.schema("operations").createRelation(
                    new Relation(
                            "assets",
                            List.of("asset_id", "asset_code", "location"),
                            12500
                    )
            );
            plant.schema("quality").createRelation(
                    new Relation(
                            "inspection_results",
                            List.of("inspection_id", "asset_id", "result"),
                            870000
                    )
            );

            plant.grant(
                    "quality_reader",
                    Privilege.CONNECT,
                    Privilege.USAGE,
                    Privilege.SELECT
            );

            ConnectionProfile readerConnection = new ConnectionProfile(
                    "localhost",
                    5432,
                    "plant_operations",
                    "quality_reader",
                    "quality-dashboard"
            );

            environment.validateConnection(readerConnection);
            System.out.println("Validated profile: " + readerConnection.display());

            printCatalogView(environment);

            System.out.println("\nRejected connection profile");
            try {
                environment.validateConnection(
                        new ConnectionProfile(
                                "localhost", 5432, "plant_operations",
                                "unknown_login", "inventory-service"
                        )
                );
            } catch (SecurityException | IllegalArgumentException exception) {
                System.out.println(exception.getMessage());
            }

            ConnectionRegistry registry = new ConnectionRegistry();
            registry.setLimit("plant_operations", 2);
            registry.open("plant_operations");
            registry.open("plant_operations");

            try {
                registry.open("plant_operations");
            } catch (IllegalStateException exception) {
                System.out.println("Expected capacity failure: " + exception.getMessage());
            }

            registry.close("plant_operations");
            registry.close("plant_operations");

            System.out.println("\nEquivalent PostgreSQL inspection commands");
            System.out.println("\\conninfo");
            System.out.println("\\l");
            System.out.println("\\dn");
            System.out.println("\\dt operations.*");
            System.out.println("SELECT current_database(), current_user;");
            System.out.println("SHOW server_version;");
            System.out.println("SHOW search_path;");

            System.out.println("\nEnterprise registry demonstration completed.");
        } catch (RuntimeException exception) {
            System.err.println("Configuration failure: " + exception.getMessage());
            System.exit(1);
        }
    }
}
