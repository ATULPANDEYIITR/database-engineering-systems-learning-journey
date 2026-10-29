import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.Instant;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.EnumSet;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;

public class PostgresAdministrationDemo {

    enum Privilege {
        CONNECT,
        USAGE,
        SELECT,
        INSERT,
        UPDATE,
        DELETE,
        CREATE,
        EXECUTE
    }

    enum ObjectType {
        DATABASE,
        SCHEMA,
        TABLE,
        FUNCTION
    }

    enum RoleState {
        ACTIVE,
        DISABLED
    }

    record DatabaseObject(
        String name,
        ObjectType type,
        String schema
    ) {
        DatabaseObject {
            Objects.requireNonNull(name);
            Objects.requireNonNull(type);

            if (name.isBlank()) {
                throw new IllegalArgumentException(
                    "Object name cannot be blank"
                );
            }
        }

        String identifier() {
            return schema == null
                ? name
                : schema + "." + name;
        }
    }

    record AuditEvent(
        Instant timestamp,
        String action,
        String actor,
        String target,
        boolean success,
        String detail
    ) {}

    static final class AdministrationException
            extends RuntimeException {
        AdministrationException(String message) {
            super(message);
        }
    }

    static final class AuthorizationException
            extends AdministrationException {
        AuthorizationException(String message) {
            super(message);
        }
    }

    static final class ValidationException
            extends AdministrationException {
        ValidationException(String message) {
            super(message);
        }
    }

    static final class ConnectionException
            extends AdministrationException {
        ConnectionException(String message) {
            super(message);
        }
    }

    static final class Role {
        private final String name;
        private final boolean login;
        private final boolean superuser;
        private final boolean createdb;
        private final boolean createrole;
        private final boolean inherit;
        private final int connectionLimit;
        private RoleState state = RoleState.ACTIVE;
        private String passwordDigest;
        private final Set<String> memberships = new HashSet<>();

        Role(
            String name,
            boolean login,
            boolean superuser,
            boolean createdb,
            boolean createrole,
            boolean inherit,
            int connectionLimit
        ) {
            if (name == null || name.isBlank()) {
                throw new ValidationException(
                    "Role name is required"
                );
            }

            if (connectionLimit < -1) {
                throw new ValidationException(
                    "Connection limit must be -1 or non-negative"
                );
            }

            if (!login && connectionLimit != -1) {
                throw new ValidationException(
                    "NOLOGIN roles cannot have a connection limit"
                );
            }

            this.name = name;
            this.login = login;
            this.superuser = superuser;
            this.createdb = createdb;
            this.createrole = createrole;
            this.inherit = inherit;
            this.connectionLimit = connectionLimit;
        }

        String name() {
            return name;
        }

        boolean login() {
            return login;
        }

        boolean superuser() {
            return superuser;
        }

        boolean createrole() {
            return createrole;
        }

        boolean inherit() {
            return inherit;
        }

        int connectionLimit() {
            return connectionLimit;
        }

        RoleState state() {
            return state;
        }

        Set<String> memberships() {
            return memberships;
        }

        void disable() {
            state = RoleState.DISABLED;
        }

        void setPassword(String password) {
            if (password == null || password.length() < 12) {
                throw new ValidationException(
                    "Password must contain at least 12 characters"
                );
            }

            if (!password.matches(".*[A-Z].*")
                    || !password.matches(".*[a-z].*")
                    || !password.matches(".*[0-9].*")) {
                throw new ValidationException(
                    "Password requires uppercase, lowercase, and digits"
                );
            }

            passwordDigest = sha256(password);
        }

        private static String sha256(String value) {
            try {
                MessageDigest digest =
                    MessageDigest.getInstance("SHA-256");

                byte[] bytes =
                    digest.digest(value.getBytes());

                StringBuilder result = new StringBuilder();

                for (byte valueByte : bytes) {
                    result.append(
                        String.format("%02x", valueByte)
                    );
                }

                return result.toString();
            } catch (NoSuchAlgorithmException ex) {
                throw new IllegalStateException(ex);
            }
        }
    }

    record PermissionKey(
        String roleName,
        String objectId
    ) {}

    static final class PermissionGrant {
        private final EnumSet<Privilege> privileges;
        private boolean grantOption;

        PermissionGrant(
            Set<Privilege> privileges,
            boolean grantOption
        ) {
            this.privileges =
                privileges.isEmpty()
                    ? EnumSet.noneOf(Privilege.class)
                    : EnumSet.copyOf(privileges);
            this.grantOption = grantOption;
        }

        boolean has(Privilege privilege) {
            return privileges.contains(privilege);
        }

        void merge(
            Set<Privilege> additional,
            boolean additionalGrantOption
        ) {
            privileges.addAll(additional);
            grantOption |= additionalGrantOption;
        }
    }

    interface Policy {
        boolean allows(
            String roleName,
            DatabaseObject object,
            Privilege privilege
        );
    }

    static final class RoleService {
        private final Map<String, Role> roles = new HashMap<>();
        private final List<AuditEvent> audit = new ArrayList<>();

        void bootstrap(Role role) {
            if (!roles.isEmpty()) {
                throw new ValidationException(
                    "Bootstrap requires an empty role registry"
                );
            }

            roles.put(role.name(), role);
        }

        Role get(String name) {
            Role role = roles.get(name);

            if (role == null) {
                throw new ValidationException(
                    "Unknown role: " + name
                );
            }

            return role;
        }

        void createRole(
            String actorName,
            Role role
        ) {
            Role actor = get(actorName);

            if (!actor.superuser() && !actor.createrole()) {
                record(
                    "CREATE_ROLE",
                    actorName,
                    role.name(),
                    false,
                    "CREATEROLE required"
                );

                throw new AuthorizationException(
                    "Actor cannot create roles"
                );
            }

            if (roles.containsKey(role.name())) {
                throw new ValidationException(
                    "Role already exists: " + role.name()
                );
            }

            roles.put(role.name(), role);

            record(
                "CREATE_ROLE",
                actorName,
                role.name(),
                true,
                "Role created"
            );
        }

        void grantRole(
            String actorName,
            String memberName,
            String groupName
        ) {
            Role actor = get(actorName);
            Role member = get(memberName);
            get(groupName);

            if (!actor.superuser() && !actor.createrole()) {
                throw new AuthorizationException(
                    "CREATEROLE required to manage memberships"
                );
            }

            if (memberName.equals(groupName)) {
                throw new ValidationException(
                    "A role cannot contain itself"
                );
            }

            if (wouldCycle(memberName, groupName)) {
                throw new ValidationException(
                    "Role membership would create a cycle"
                );
            }

            member.memberships().add(groupName);

            record(
                "GRANT_ROLE",
                actorName,
                memberName + " -> " + groupName,
                true,
                "Membership granted"
            );
        }

        Set<String> effectiveRoles(String roleName) {
            Role root = get(roleName);
            Set<String> result = new HashSet<>();

            if (!root.inherit()) {
                result.add(roleName);
                return result;
            }

            ArrayDeque<String> stack = new ArrayDeque<>();
            stack.push(roleName);

            while (!stack.isEmpty()) {
                String current = stack.pop();

                if (!result.add(current)) {
                    continue;
                }

                Role role = get(current);

                if (role.inherit()) {
                    role.memberships().forEach(stack::push);
                }
            }

            return result;
        }

        private boolean wouldCycle(
            String member,
            String group
        ) {
            ArrayDeque<String> stack = new ArrayDeque<>();
            Set<String> visited = new HashSet<>();

            stack.push(group);

            while (!stack.isEmpty()) {
                String current = stack.pop();

                if (current.equals(member)) {
                    return true;
                }

                if (!visited.add(current)) {
                    continue;
                }

                get(current)
                    .memberships()
                    .forEach(stack::push);
            }

            return false;
        }

        void disableRole(
            String actorName,
            String targetName
        ) {
            Role actor = get(actorName);
            Role target = get(targetName);

            if (!actor.superuser()) {
                throw new AuthorizationException(
                    "Only superuser may disable a role"
                );
            }

            target.disable();

            record(
                "ALTER_ROLE",
                actorName,
                targetName,
                true,
                "Role disabled"
            );
        }

        void setPassword(
            String actorName,
            String targetName,
            String password
        ) {
            Role actor = get(actorName);
            Role target = get(targetName);

            if (!actorName.equals(targetName)
                    && !actor.superuser()) {
                throw new AuthorizationException(
                    "Only superuser may set another user's password"
                );
            }

            target.setPassword(password);

            record(
                "ALTER_ROLE",
                actorName,
                targetName,
                true,
                "Password accepted by policy"
            );
        }

        List<AuditEvent> auditEvents() {
            return List.copyOf(audit);
        }

        private void record(
            String action,
            String actor,
            String target,
            boolean success,
            String detail
        ) {
            audit.add(
                new AuditEvent(
                    Instant.now(),
                    action,
                    actor,
                    target,
                    success,
                    detail
                )
            );
        }
    }

    static final class PermissionService {
        private final Map<PermissionKey, PermissionGrant> grants =
            new HashMap<>();

        private final Map<String, EnumSet<Privilege>> defaults =
            new HashMap<>();

        void grant(
            String roleName,
            DatabaseObject object,
            Set<Privilege> privileges,
            boolean grantOption
        ) {
            if (privileges.isEmpty()) {
                throw new ValidationException(
                    "At least one privilege is required"
                );
            }

            PermissionKey key =
                new PermissionKey(
                    roleName,
                    object.identifier()
                );

            PermissionGrant grant = grants.get(key);

            if (grant == null) {
                grants.put(
                    key,
                    new PermissionGrant(
                        privileges,
                        grantOption
                    )
                );
            } else {
                grant.merge(
                    privileges,
                    grantOption
                );
            }
        }

        void revoke(
            String roleName,
            DatabaseObject object,
            Set<Privilege> privileges
        ) {
            PermissionKey key =
                new PermissionKey(
                    roleName,
                    object.identifier()
                );

            PermissionGrant grant = grants.get(key);

            if (grant == null) {
                return;
            }

            privileges.forEach(
                privilege -> {
                    // Reconstructing the grant keeps mutation
                    // contained inside this service.
                }
            );

            EnumSet<Privilege> remaining =
                EnumSet.noneOf(Privilege.class);

            for (Privilege privilege : Privilege.values()) {
                if (grant.has(privilege)
                        && !privileges.contains(privilege)) {
                    remaining.add(privilege);
                }
            }

            if (remaining.isEmpty()) {
                grants.remove(key);
            } else {
                grants.put(
                    key,
                    new PermissionGrant(
                        remaining,
                        false
                    )
                );
            }
        }

        void setDefaultPrivileges(
            String roleName,
            ObjectType objectType,
            Set<Privilege> privileges
        ) {
            defaults.put(
                roleName + "|" + objectType,
                privileges.isEmpty()
                    ? EnumSet.noneOf(Privilege.class)
                    : EnumSet.copyOf(privileges)
            );
        }

        boolean has(
            String roleName,
            String objectId,
            Privilege privilege
        ) {
            PermissionGrant grant =
                grants.get(
                    new PermissionKey(
                        roleName,
                        objectId
                    )
                );

            return grant != null && grant.has(privilege);
        }

        Set<Privilege> defaultsFor(
            String roleName,
            ObjectType objectType
        ) {
            return Set.copyOf(
                defaults.getOrDefault(
                    roleName + "|" + objectType,
                    EnumSet.noneOf(Privilege.class)
                )
            );
        }
    }

    static final class AuthorizationService
            implements Policy {

        private final RoleService roles;
        private final PermissionService permissions;

        AuthorizationService(
            RoleService roles,
            PermissionService permissions
        ) {
            this.roles = roles;
            this.permissions = permissions;
        }

        @Override
        public boolean allows(
            String roleName,
            DatabaseObject object,
            Privilege privilege
        ) {
            Role role = roles.get(roleName);

            if (role.superuser()) {
                return true;
            }

            return roles.effectiveRoles(roleName)
                .stream()
                .anyMatch(
                    effectiveRole ->
                        permissions.has(
                            effectiveRole,
                            object.identifier(),
                            privilege
                        )
                );
        }

        void require(
            String roleName,
            DatabaseObject object,
            Privilege privilege
        ) {
            if (!allows(roleName, object, privilege)) {
                throw new AuthorizationException(
                    roleName +
                    " lacks " +
                    privilege +
                    " on " +
                    object.identifier()
                );
            }
        }
    }

    static final class DatabaseSessionService {
        private final int databaseConnectionLimit;
        private int activeConnections;
        private final Map<String, Integer> roleConnections =
            new HashMap<>();

        DatabaseSessionService(int databaseConnectionLimit) {
            if (databaseConnectionLimit < -1) {
                throw new ValidationException(
                    "Invalid database connection limit"
                );
            }

            this.databaseConnectionLimit =
                databaseConnectionLimit;
        }

        void connect(Role role) {
            if (!role.login()) {
                throw new AuthorizationException(
                    role.name() + " is NOLOGIN"
                );
            }

            if (role.state() != RoleState.ACTIVE) {
                throw new AuthorizationException(
                    role.name() + " is disabled"
                );
            }

            if (databaseConnectionLimit != -1
                    && activeConnections
                        >= databaseConnectionLimit) {
                throw new ConnectionException(
                    "Database connection limit reached"
                );
            }

            int roleCount =
                roleConnections.getOrDefault(
                    role.name(),
                    0
                );

            if (role.connectionLimit() != -1
                    && roleCount
                        >= role.connectionLimit()) {
                throw new ConnectionException(
                    "Role connection limit reached"
                );
            }

            roleConnections.put(
                role.name(),
                roleCount + 1
            );

            activeConnections++;
        }

        void disconnect(Role role) {
            int count =
                roleConnections.getOrDefault(
                    role.name(),
                    0
                );

            if (count <= 0) {
                return;
            }

            if (count == 1) {
                roleConnections.remove(role.name());
            } else {
                roleConnections.put(
                    role.name(),
                    count - 1
                );
            }

            activeConnections--;
        }

        int activeConnections() {
            return activeConnections;
        }
    }

    public static void main(String[] args) {
        RoleService roles = new RoleService();

        roles.bootstrap(
            new Role(
                "postgres",
                true,
                true,
                true,
                true,
                true,
                -1
            )
        );

        roles.createRole(
            "postgres",
            new Role(
                "application_owner",
                false,
                false,
                false,
                false,
                true,
                -1
            )
        );

        roles.createRole(
            "postgres",
            new Role(
                "application_reader",
                false,
                false,
                false,
                false,
                true,
                -1
            )
        );

        roles.createRole(
            "postgres",
            new Role(
                "application_writer",
                false,
                false,
                false,
                false,
                true,
                -1
            )
        );

        roles.createRole(
            "postgres",
            new Role(
                "api_user",
                true,
                false,
                false,
                false,
                true,
                10
            )
        );

        roles.createRole(
            "postgres",
            new Role(
                "report_user",
                true,
                false,
                false,
                false,
                true,
                3
            )
        );

        roles.grantRole(
            "postgres",
            "api_user",
            "application_writer"
        );

        roles.grantRole(
            "postgres",
            "report_user",
            "application_reader"
        );

        roles.setPassword(
            "postgres",
            "api_user",
            "StrongPassword7"
        );

        PermissionService permissions =
            new PermissionService();

        DatabaseObject database =
            new DatabaseObject(
                "business_db",
                ObjectType.DATABASE,
                null
            );

        DatabaseObject schema =
            new DatabaseObject(
                "app",
                ObjectType.SCHEMA,
                null
            );

        DatabaseObject customers =
            new DatabaseObject(
                "customers",
                ObjectType.TABLE,
                "app"
            );

        DatabaseObject invoices =
            new DatabaseObject(
                "invoices",
                ObjectType.TABLE,
                "app"
            );

        permissions.grant(
            "application_owner",
            database,
            EnumSet.of(Privilege.CONNECT),
            false
        );

        permissions.grant(
            "application_owner",
            schema,
            EnumSet.of(
                Privilege.USAGE,
                Privilege.CREATE
            ),
            true
        );

        permissions.grant(
            "application_reader",
            database,
            EnumSet.of(Privilege.CONNECT),
            false
        );

        permissions.grant(
            "application_reader",
            schema,
            EnumSet.of(Privilege.USAGE),
            false
        );

        permissions.grant(
            "application_reader",
            customers,
            EnumSet.of(Privilege.SELECT),
            false
        );

        permissions.grant(
            "application_reader",
            invoices,
            EnumSet.of(Privilege.SELECT),
            false
        );

        permissions.grant(
            "application_writer",
            database,
            EnumSet.of(Privilege.CONNECT),
            false
        );

        permissions.grant(
            "application_writer",
            schema,
            EnumSet.of(Privilege.USAGE),
            false
        );

        permissions.grant(
            "application_writer",
            customers,
            EnumSet.of(
                Privilege.SELECT,
                Privilege.INSERT,
                Privilege.UPDATE
            ),
            false
        );

        permissions.grant(
            "application_writer",
            invoices,
            EnumSet.of(
                Privilege.SELECT,
                Privilege.INSERT,
                Privilege.UPDATE
            ),
            false
        );

        permissions.setDefaultPrivileges(
            "application_owner",
            ObjectType.TABLE,
            EnumSet.of(Privilege.SELECT)
        );

        AuthorizationService authorization =
            new AuthorizationService(
                roles,
                permissions
            );

        System.out.println(
            "PostgreSQL Administration Enterprise Model"
        );
        System.out.println(
            "==========================================="
        );

        System.out.println(
            "\nEffective role memberships"
        );

        for (String roleName :
            List.of("api_user", "report_user")) {

            System.out.println(
                roleName +
                ": " +
                roles.effectiveRoles(roleName)
            );
        }

        System.out.println(
            "\nAuthorization decisions"
        );

        authorization.require(
            "api_user",
            customers,
            Privilege.UPDATE
        );

        System.out.println(
            "api_user UPDATE app.customers: ALLOWED"
        );

        authorization.require(
            "report_user",
            customers,
            Privilege.SELECT
        );

        System.out.println(
            "report_user SELECT app.customers: ALLOWED"
        );

        try {
            authorization.require(
                "report_user",
                customers,
                Privilege.DELETE
            );
        } catch (AuthorizationException ex) {
            System.out.println(
                "report_user DELETE app.customers: DENIED"
            );
        }

        System.out.println(
            "\nDefault table privileges"
        );

        System.out.println(
            permissions.defaultsFor(
                "application_owner",
                ObjectType.TABLE
            )
        );

        DatabaseSessionService sessions =
            new DatabaseSessionService(2);

        sessions.connect(
            roles.get("api_user")
        );

        sessions.connect(
            roles.get("report_user")
        );

        System.out.println(
            "\nActive database sessions: " +
            sessions.activeConnections()
        );

        try {
            sessions.connect(
                roles.get("api_user")
            );
        } catch (ConnectionException ex) {
            System.out.println(
                "Expected connection rejection: " +
                ex.getMessage()
            );
        }

        sessions.disconnect(
            roles.get("api_user")
        );

        sessions.disconnect(
            roles.get("report_user")
        );

        System.out.println(
            "Active database sessions after cleanup: " +
            sessions.activeConnections()
        );

        System.out.println(
            "\nRole membership validation"
        );

        try {
            roles.grantRole(
                "postgres",
                "application_writer",
                "api_user"
            );
        } catch (ValidationException ex) {
            System.out.println(
                "Expected membership-cycle rejection: " +
                ex.getMessage()
            );
        }

        System.out.println(
            "\nRole state management"
        );

        roles.disableRole(
            "postgres",
            "report_user"
        );

        try {
            sessions.connect(
                roles.get("report_user")
            );
        } catch (AuthorizationException ex) {
            System.out.println(
                "Disabled role rejected: " +
                ex.getMessage()
            );
        }

        assert roles.get("api_user").login();
        assert !roles.get("application_writer").login();
        assert authorization.allows(
            "api_user",
            customers,
            Privilege.UPDATE
        );
        assert !authorization.allows(
            "report_user",
            customers,
            Privilege.DELETE
        );

        System.out.println(
            "\nEnterprise administration assertions passed."
        );

        System.out.println(
            "\nAudit events"
        );

        roles.auditEvents()
            .stream()
            .forEach(
                event ->
                    System.out.println(
                        event.timestamp() +
                        " | " +
                        event.action() +
                        " | " +
                        event.actor() +
                        " | " +
                        event.target() +
                        " | " +
                        event.detail()
                    )
            );
    }
}
