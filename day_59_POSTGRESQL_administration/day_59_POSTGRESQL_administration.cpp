#include <algorithm>
#include <exception>
#include <iostream>
#include <map>
#include <set>
#include <stdexcept>
#include <string>
#include <vector>

using namespace std;

enum class Privilege {
    Connect,
    Usage,
    Select,
    Insert,
    Update,
    Delete,
    Create,
    Execute
};

enum class ObjectType {
    Database,
    Schema,
    Table,
    Function
};

enum class ReviewState {
    Open,
    Closed
};

string toString(Privilege privilege) {
    switch (privilege) {
        case Privilege::Connect: return "CONNECT";
        case Privilege::Usage: return "USAGE";
        case Privilege::Select: return "SELECT";
        case Privilege::Insert: return "INSERT";
        case Privilege::Update: return "UPDATE";
        case Privilege::Delete: return "DELETE";
        case Privilege::Create: return "CREATE";
        case Privilege::Execute: return "EXECUTE";
    }
    return "UNKNOWN";
}

struct DatabaseObject {
    string name;
    ObjectType type;
    string schema;

    string identifier() const {
        return schema.empty() ? name : schema + "." + name;
    }
};

struct Role {
    string name;
    bool login{false};
    bool superuser{false};
    bool createdb{false};
    bool createrole{false};
    bool inherit{true};
    int connectionLimit{-1};

    set<string> memberships;

    void validate() const {
        if (name.empty()) {
            throw invalid_argument("Role name cannot be empty");
        }

        if (connectionLimit < -1) {
            throw invalid_argument(
                "Connection limit must be -1 or non-negative"
            );
        }

        if (!login && connectionLimit != -1) {
            throw invalid_argument(
                "NOLOGIN roles should not have a connection limit"
            );
        }
    }
};

struct Grant {
    set<Privilege> privileges;
    bool grantOption{false};
};

class AuditLog {
public:
    struct Event {
        string action;
        string actor;
        string target;
        bool success;
        string detail;
    };

    void add(
        const string& action,
        const string& actor,
        const string& target,
        bool success,
        const string& detail
    ) {
        events.push_back({
            action,
            actor,
            target,
            success,
            detail
        });
    }

    void print() const {
        cout << "\nAudit log\n";
        cout << "---------\n";

        for (const auto& event : events) {
            cout
                << event.action
                << " | "
                << (event.success ? "SUCCESS" : "DENIED")
                << " | actor=" << event.actor
                << " | target=" << event.target
                << " | " << event.detail
                << '\n';
        }
    }

private:
    vector<Event> events;
};

class RoleDirectory {
public:
    explicit RoleDirectory(AuditLog& audit)
        : audit(audit) {}

    void addBootstrapRole(const Role& role) {
        if (!roles.empty()) {
            throw logic_error(
                "Bootstrap role can only be added to an empty directory"
            );
        }

        role.validate();
        roles.emplace(role.name, role);
    }

    void createRole(
        const string& actorName,
        const Role& role
    ) {
        const Role& actor = get(actorName);

        if (!actor.superuser && !actor.createrole) {
            audit.add(
                "CREATE_ROLE",
                actorName,
                role.name,
                false,
                "CREATEROLE privilege required"
            );
            throw permission_error(
                "Actor cannot create roles"
            );
        }

        role.validate();

        if (roles.count(role.name)) {
            throw invalid_argument(
                "Role already exists: " + role.name
            );
        }

        roles.emplace(role.name, role);

        audit.add(
            "CREATE_ROLE",
            actorName,
            role.name,
            true,
            "Role created"
        );
    }

    void grantMembership(
        const string& actorName,
        const string& memberName,
        const string& groupName
    ) {
        const Role& actor = get(actorName);
        Role& member = getMutable(memberName);
        get(groupName);

        if (!actor.superuser && !actor.createrole) {
            audit.add(
                "GRANT_ROLE",
                actorName,
                memberName + "->" + groupName,
                false,
                "CREATEROLE privilege required"
            );
            throw permission_error(
                "Actor cannot grant role membership"
            );
        }

        if (memberName == groupName) {
            throw invalid_argument(
                "A role cannot be a member of itself"
            );
        }

        if (wouldCreateCycle(memberName, groupName)) {
            throw invalid_argument(
                "Role membership would create a cycle"
            );
        }

        member.memberships.insert(groupName);

        audit.add(
            "GRANT_ROLE",
            actorName,
            memberName + "->" + groupName,
            true,
            "Membership granted"
        );
    }

    const Role& get(const string& name) const {
        auto it = roles.find(name);

        if (it == roles.end()) {
            throw out_of_range("Unknown role: " + name);
        }

        return it->second;
    }

    Role& getMutable(const string& name) {
        auto it = roles.find(name);

        if (it == roles.end()) {
            throw out_of_range("Unknown role: " + name);
        }

        return it->second;
    }

    set<string> effectiveRoles(const string& roleName) const {
        const Role& root = get(roleName);
        set<string> result;
        vector<string> stack{roleName};

        while (!stack.empty()) {
            string current = stack.back();
            stack.pop_back();

            if (result.count(current)) {
                continue;
            }

            result.insert(current);

            const Role& role = get(current);

            if (role.inherit) {
                for (const auto& parent : role.memberships) {
                    stack.push_back(parent);
                }
            }
        }

        return result;
    }

    const map<string, Role>& allRoles() const {
        return roles;
    }

private:
    bool wouldCreateCycle(
        const string& member,
        const string& group
    ) const {
        vector<string> stack{group};
        set<string> visited;

        while (!stack.empty()) {
            string current = stack.back();
            stack.pop_back();

            if (current == member) {
                return true;
            }

            if (!visited.insert(current).second) {
                continue;
            }

            const Role& role = get(current);

            for (const auto& parent : role.memberships) {
                stack.push_back(parent);
            }
        }

        return false;
    }

    map<string, Role> roles;
    AuditLog& audit;
};

class PermissionStore {
public:
    void grant(
        const string& roleName,
        const DatabaseObject& object,
        initializer_list<Privilege> privileges,
        bool grantOption = false
    ) {
        Grant& grant = grants[make_pair(
            roleName,
            object.identifier()
        )];

        grant.privileges.insert(
            privileges.begin(),
            privileges.end()
        );

        grant.grantOption =
            grant.grantOption || grantOption;
    }

    void revoke(
        const string& roleName,
        const DatabaseObject& object,
        initializer_list<Privilege> privileges
    ) {
        auto key = make_pair(
            roleName,
            object.identifier()
        );

        auto it = grants.find(key);

        if (it == grants.end()) {
            return;
        }

        for (Privilege privilege : privileges) {
            it->second.privileges.erase(privilege);
        }

        if (it->second.privileges.empty()) {
            grants.erase(it);
        }
    }

    bool has(
        const string& roleName,
        const string& objectId,
        Privilege privilege
    ) const {
        auto it = grants.find(
            make_pair(roleName, objectId)
        );

        if (it == grants.end()) {
            return false;
        }

        return it->second.privileges.count(privilege) > 0;
    }

private:
    map<pair<string, string>, Grant> grants;
};

class GovernanceEngine {
public:
    GovernanceEngine(
        const RoleDirectory& roles,
        const PermissionStore& permissions
    )
        : roles(roles),
          permissions(permissions) {}

    bool allowed(
        const string& roleName,
        const DatabaseObject& object,
        Privilege privilege
    ) const {
        const Role& role = roles.get(roleName);

        if (role.superuser) {
            return true;
        }

        for (const auto& effectiveRole :
             roles.effectiveRoles(roleName)) {
            if (permissions.has(
                    effectiveRole,
                    object.identifier(),
                    privilege)) {
                return true;
            }
        }

        return false;
    }

    void require(
        const string& roleName,
        const DatabaseObject& object,
        Privilege privilege
    ) const {
        if (!allowed(roleName, object, privilege)) {
            throw permission_error(
                roleName + " lacks " +
                toString(privilege) +
                " on " +
                object.identifier()
            );
        }
    }

private:
    const RoleDirectory& roles;
    const PermissionStore& permissions;
};

class ConnectionPool {
public:
    explicit ConnectionPool(int limit)
        : limit(limit) {
        if (limit < -1) {
            throw invalid_argument(
                "Invalid connection limit"
            );
        }
    }

    void connect(const Role& role) {
        if (!role.login) {
            throw permission_error(
                role.name + " is NOLOGIN"
            );
        }

        if (limit != -1 &&
            activeConnections >= limit) {
            throw runtime_error(
                "Database connection limit reached"
            );
        }

        if (role.connectionLimit != -1) {
            auto it = perRole.find(role.name);
            int count = it == perRole.end() ? 0 : it->second;

            if (count >= role.connectionLimit) {
                throw runtime_error(
                    "Role connection limit reached"
                );
            }
        }

        ++activeConnections;
        ++perRole[role.name];
    }

    void disconnect(const Role& role) {
        auto it = perRole.find(role.name);

        if (it == perRole.end() || it->second == 0) {
            return;
        }

        --it->second;
        --activeConnections;
    }

    int active() const {
        return activeConnections;
    }

private:
    int limit;
    int activeConnections{0};
    map<string, int> perRole;
};

int main() {
    try {
        AuditLog audit;
        RoleDirectory roles(audit);

        roles.addBootstrapRole({
            "postgres",
            true,
            true,
            true,
            true,
            true,
            -1
        });

        roles.createRole(
            "postgres",
            {"app_owner"}
        );

        roles.createRole(
            "postgres",
            {"app_reader"}
        );

        roles.createRole(
            "postgres",
            {"app_writer"}
        );

        roles.createRole(
            "postgres",
            {
                "api_user",
                true,
                false,
                false,
                false,
                true,
                10
            }
        );

        roles.createRole(
            "postgres",
            {
                "report_user",
                true,
                false,
                false,
                false,
                true,
                3
            }
        );

        roles.grantMembership(
            "postgres",
            "api_user",
            "app_writer"
        );

        roles.grantMembership(
            "postgres",
            "report_user",
            "app_reader"
        );

        DatabaseObject database{
            "business_db",
            ObjectType::Database,
            ""
        };

        DatabaseObject schema{
            "app",
            ObjectType::Schema,
            ""
        };

        DatabaseObject customers{
            "customers",
            ObjectType::Table,
            "app"
        };

        DatabaseObject invoices{
            "invoices",
            ObjectType::Table,
            "app"
        };

        PermissionStore permissions;

        permissions.grant(
            "app_owner",
            database,
            {Privilege::Connect}
        );

        permissions.grant(
            "app_owner",
            schema,
            {Privilege::Usage, Privilege::Create}
        );

        permissions.grant(
            "app_reader",
            database,
            {Privilege::Connect}
        );

        permissions.grant(
            "app_reader",
            schema,
            {Privilege::Usage}
        );

        permissions.grant(
            "app_reader",
            customers,
            {Privilege::Select}
        );

        permissions.grant(
            "app_reader",
            invoices,
            {Privilege::Select}
        );

        permissions.grant(
            "app_writer",
            database,
            {Privilege::Connect}
        );

        permissions.grant(
            "app_writer",
            schema,
            {Privilege::Usage}
        );

        permissions.grant(
            "app_writer",
            customers,
            {
                Privilege::Select,
                Privilege::Insert,
                Privilege::Update
            }
        );

        permissions.grant(
            "app_writer",
            invoices,
            {
                Privilege::Select,
                Privilege::Insert,
                Privilege::Update
            }
        );

        GovernanceEngine engine(
            roles,
            permissions
        );

        cout
            << "PostgreSQL Administration Governance Engine\n"
            << "============================================\n";

        cout << "\nEffective role membership\n";
        cout << "-------------------------\n";

        for (const string& name :
             {"api_user", "report_user"}) {
            cout << name << ": ";

            auto effective = roles.effectiveRoles(name);

            bool first = true;
            for (const auto& role : effective) {
                if (!first) {
                    cout << ", ";
                }
                cout << role;
                first = false;
            }

            cout << '\n';
        }

        cout << "\nAuthorization tests\n";
        cout << "-------------------\n";

        engine.require(
            "api_user",
            customers,
            Privilege::Update
        );

        cout << "api_user UPDATE app.customers: ALLOWED\n";

        engine.require(
            "report_user",
            customers,
            Privilege::Select
        );

        cout << "report_user SELECT app.customers: ALLOWED\n";

        try {
            engine.require(
                "report_user",
                customers,
                Privilege::Delete
            );
        } catch (const exception& ex) {
            cout
                << "report_user DELETE app.customers: DENIED: "
                << ex.what()
                << '\n';
        }

        cout << "\nConnection governance\n";
        cout << "---------------------\n";

        ConnectionPool pool(2);

        pool.connect(
            roles.get("api_user")
        );

        pool.connect(
            roles.get("report_user")
        );

        cout
            << "Active connections: "
            << pool.active()
            << '\n';

        try {
            pool.connect(
                roles.get("api_user")
            );
        } catch (const exception& ex) {
            cout
                << "Expected connection failure: "
                << ex.what()
                << '\n';
        }

        pool.disconnect(
            roles.get("api_user")
        );

        cout
            << "Active after disconnect: "
            << pool.active()
            << '\n';

        cout << "\nRole-cycle validation\n";
        cout << "---------------------\n";

        try {
            roles.grantMembership(
                "postgres",
                "app_writer",
                "api_user"
            );
        } catch (const exception& ex) {
            cout
                << "Expected cycle rejection: "
                << ex.what()
                << '\n';
        }

        cout << "\nAssertions\n";
        cout << "----------\n";

        if (!roles.get("api_user").login) {
            throw logic_error(
                "api_user must have LOGIN"
            );
        }

        if (roles.get("app_writer").login) {
            throw logic_error(
                "app_writer must be NOLOGIN"
            );
        }

        if (!engine.allowed(
                "api_user",
                customers,
                Privilege::Update)) {
            throw logic_error(
                "Writer membership should allow UPDATE"
            );
        }

        if (engine.allowed(
                "report_user",
                customers,
                Privilege::Delete)) {
            throw logic_error(
                "Reader must not have DELETE"
            );
        }

        cout
            << "All governance assertions passed.\n";

        audit.print();

        /*
         * Complexity:
         * - Direct permission lookup is O(log G) using std::map.
         * - Role inheritance traversal is O(R + M), where R is the
         *   number of reachable roles and M is membership edges.
         * - Connection checks are O(log U), where U is the number
         *   of roles with active sessions.
         *
         * The implementation favors deterministic behavior and
         * explicit ownership of domain state over global variables.
         */
    } catch (const exception& ex) {
        cerr
            << "Fatal administration error: "
            << ex.what()
            << '\n';
        return 1;
    }

    return 0;
}
