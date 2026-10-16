#include <algorithm>
#include <cctype>
#include <cstdlib>
#include <iomanip>
#include <iostream>
#include <map>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

/*
 * PostgreSQL Fundamentals: a server administration case study.
 *
 * Scenario:
 * A manufacturing organization operates one PostgreSQL cluster containing
 * plant_operations and compliance_reporting. Cluster-wide roles, database
 * ownership, schema organization, relation lookup, and connection limits are
 * represented explicitly.
 *
 * Build:
 *   g++ -std=c++17 -Wall -Wextra -pedantic postgres_fundamentals.cpp -o postgres_lab
 *
 * This is a deterministic architecture model, not a PostgreSQL server emulator.
 */

namespace pgfundamentals {

struct Relation {
    std::string name;
    std::vector<std::string> columns;
    std::size_t estimatedRows{0};
};

struct Schema {
    std::string name;
    std::map<std::string, Relation> relations;

    void createRelation(Relation relation) {
        if (!validIdentifier(relation.name)) {
            throw std::invalid_argument("Invalid relation identifier");
        }
        const auto [iterator, inserted] =
            relations.emplace(relation.name, std::move(relation));
        if (!inserted) {
            throw std::runtime_error(
                "Relation already exists: " + iterator->first
            );
        }
    }

    static bool validIdentifier(const std::string& value) {
        if (value.empty()) return false;
        const auto first = static_cast<unsigned char>(value.front());
        if (!(std::isalpha(first) || value.front() == '_')) return false;

        return std::all_of(value.begin() + 1, value.end(), [](char character) {
            const auto converted = static_cast<unsigned char>(character);
            return std::isalnum(converted) || character == '_';
        });
    }
};

struct Database {
    std::string name;
    std::string owner;
    std::map<std::string, Schema> schemas;
    unsigned connectionLimit{30};
    unsigned activeConnections{0};

    Database(std::string databaseName, std::string databaseOwner)
        : name(std::move(databaseName)), owner(std::move(databaseOwner)) {
        schemas.emplace("public", Schema{"public", {}});
    }

    void createSchema(const std::string& schemaName) {
        if (!Schema::validIdentifier(schemaName)) {
            throw std::invalid_argument("Invalid schema identifier");
        }

        const auto [iterator, inserted] =
            schemas.emplace(schemaName, Schema{schemaName, {}});
        if (!inserted) {
            throw std::runtime_error("Schema already exists: " + iterator->first);
        }
    }

    const Relation& resolve(
        const std::string& relationName,
        const std::vector<std::string>& searchPath
    ) const {
        for (const auto& schemaName : searchPath) {
            const auto schema = schemas.find(schemaName);
            if (schema == schemas.end()) continue;

            const auto relation = schema->second.relations.find(relationName);
            if (relation != schema->second.relations.end()) {
                return relation->second;
            }
        }

        throw std::runtime_error(
            "Relation not found in search_path: " + relationName
        );
    }

    void connect() {
        if (activeConnections >= connectionLimit) {
            throw std::runtime_error(
                "Connection limit reached for database " + name
            );
        }
        ++activeConnections;
    }

    void disconnect() {
        if (activeConnections == 0) {
            throw std::runtime_error("No active connection to release");
        }
        --activeConnections;
    }
};

struct Role {
    std::string name;
    bool canLogin{false};
    bool superuser{false};
};

class Cluster {
private:
    std::map<std::string, Role> roles_;
    std::map<std::string, Database> databases_;

public:
    void createRole(Role role) {
        if (!Schema::validIdentifier(role.name)) {
            throw std::invalid_argument("Invalid role name");
        }

        const auto [iterator, inserted] =
            roles_.emplace(role.name, std::move(role));
        if (!inserted) {
            throw std::runtime_error("Role already exists: " + iterator->first);
        }
    }

    void createDatabase(const std::string& name, const std::string& owner) {
        if (databases_.count(name)) {
            throw std::runtime_error("Database already exists: " + name);
        }
        if (!roles_.count(owner)) {
            throw std::runtime_error("Database owner role does not exist: " + owner);
        }
        databases_.emplace(name, Database{name, owner});
    }

    Database& database(const std::string& name) {
        auto iterator = databases_.find(name);
        if (iterator == databases_.end()) {
            throw std::runtime_error("Database not found: " + name);
        }
        return iterator->second;
    }

    const std::map<std::string, Role>& roles() const {
        return roles_;
    }

    const std::map<std::string, Database>& databases() const {
        return databases_;
    }
};

void printArchitecture(const Cluster& cluster) {
    std::cout << "\nCluster-wide roles\n";
    for (const auto& [name, role] : cluster.roles()) {
        std::cout << "  " << std::left << std::setw(22) << name
                  << " LOGIN=" << std::boolalpha << role.canLogin
                  << " SUPERUSER=" << role.superuser << '\n';
    }

    std::cout << "\nDatabases and schemas\n";
    for (const auto& [databaseName, database] : cluster.databases()) {
        std::cout << databaseName << " owner=" << database.owner << '\n';
        for (const auto& [schemaName, schema] : database.schemas) {
            std::cout << "  schema " << schemaName << '\n';
            for (const auto& [relationName, relation] : schema.relations) {
                std::cout << "    " << relationName
                          << " estimated_rows=" << relation.estimatedRows << '\n';
            }
        }
    }
}

void explainOperationalMechanisms() {
    std::cout << "\nServer architecture and operational interpretation\n";
    std::cout << "  postmaster: accepts connections and supervises server processes\n";
    std::cout << "  backend: executes SQL for an individual connection\n";
    std::cout << "  shared_buffers: PostgreSQL's shared page cache\n";
    std::cout << "  WAL: write-ahead log used for recovery and durability\n";
    std::cout << "  system catalogs: metadata about roles, databases, and relations\n";
    std::cout << "  psql: interactive client, not the database server\n";
    std::cout << "  search_path: ordered schema lookup for unqualified names\n";
}

}  // namespace pgfundamentals

int main() {
    using namespace pgfundamentals;

    try {
        Cluster cluster;

        cluster.createRole(Role{"postgres", true, true});
        cluster.createRole(Role{"plant_owner", true, false});
        cluster.createRole(Role{"reporting_reader", true, false});
        cluster.createRole(Role{"migration_service", true, false});

        cluster.createDatabase("plant_operations", "plant_owner");
        cluster.createDatabase("compliance_reporting", "postgres");

        auto& plant = cluster.database("plant_operations");
        plant.createSchema("operations");
        plant.createSchema("maintenance");

        plant.schemas.at("operations").createRelation(
            Relation{"assets", {"asset_id", "asset_code", "site_id"}, 12500}
        );
        plant.schemas.at("operations").createRelation(
            Relation{
                "inspection_results",
                {"inspection_id", "asset_id", "result", "recorded_at"},
                870000
            }
        );
        plant.schemas.at("maintenance").createRelation(
            Relation{
                "work_orders",
                {"work_order_id", "asset_id", "priority", "status"},
                42000
            }
        );

        auto& reporting = cluster.database("compliance_reporting");
        reporting.createSchema("compliance");
        reporting.schemas.at("compliance").createRelation(
            Relation{
                "monthly_compliance",
                {"month_start", "site_id", "compliant_count", "total_count"},
                1800
            }
        );

        printArchitecture(cluster);
        explainOperationalMechanisms();

        std::cout << "\nRelation resolution\n";
        const std::vector<std::string> searchPath{
            "maintenance", "operations", "public"
        };
        const auto& assets = plant.resolve("assets", searchPath);
        std::cout << "assets resolves to operations." << assets.name << '\n';

        std::cout << "\nConnection limit demonstration\n";
        plant.connectionLimit = 2;
        plant.connect();
        plant.connect();
        try {
            plant.connect();
        } catch (const std::runtime_error& error) {
            std::cout << "Expected failure: " << error.what() << '\n';
        }
        plant.disconnect();
        plant.disconnect();

        std::cout << "\nInstallation verification commands\n";
        std::cout << "  psql --version\n";
        std::cout << "  pg_isready -h localhost -p 5432\n";
        std::cout << "  psql -h localhost -p 5432 -U plant_owner -d plant_operations\n";
        std::cout << "  SELECT current_database(), current_user;\n";
        std::cout << "  SELECT datname FROM pg_database ORDER BY datname;\n";
        std::cout << "  SELECT schema_name FROM information_schema.schemata;\n";

        std::cout << "\nOperational case study completed.\n";
    } catch (const std::exception& error) {
        std::cerr << "Fatal demonstration error: " << error.what() << '\n';
        return EXIT_FAILURE;
    }

    return EXIT_SUCCESS;
}
