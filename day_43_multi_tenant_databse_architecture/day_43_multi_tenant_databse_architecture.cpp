#include <algorithm>
#include <cctype>
#include <iostream>
#include <map>
#include <optional>
#include <set>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <utility>
#include <vector>

/*
 * Repository-independent database tenancy governance engine.
 *
 * Case study: a SaaS platform must place new enterprise customers into one of
 * three database architectures while enforcing tenant isolation and operational
 * limits. The engine evaluates placement and simulates scoped data access.
 *
 * Compile:
 *   g++ -std=c++17 -Wall -Wextra -pedantic multi_tenant.cpp -o multi_tenant
 */

enum class Architecture {
    SharedSchema,
    SeparateSchema,
    SeparateDatabase
};

enum class Status {
    Provisioning,
    Active,
    Suspended,
    Deprovisioned
};

std::string toString(Architecture architecture) {
    switch (architecture) {
        case Architecture::SharedSchema: return "shared schema";
        case Architecture::SeparateSchema: return "separate schema";
        case Architecture::SeparateDatabase: return "separate database";
    }
    throw std::logic_error("Unknown architecture.");
}

std::string toString(Status status) {
    switch (status) {
        case Status::Provisioning: return "provisioning";
        case Status::Active: return "active";
        case Status::Suspended: return "suspended";
        case Status::Deprovisioned: return "deprovisioned";
    }
    throw std::logic_error("Unknown tenant status.");
}

bool validIdentifier(const std::string& value) {
    if (value.size() < 3 || value.size() > 40 ||
        !std::islower(static_cast<unsigned char>(value[0]))) {
        return false;
    }

    return std::all_of(value.begin(), value.end(), [](unsigned char c) {
        return std::islower(c) || std::isdigit(c) || c == '_';
    });
}

struct PlacementRequest {
    std::string tenantId;
    std::string slug;
    std::string name;
    std::string region;
    std::size_t expectedUsers;
    std::size_t expectedProjects;
    bool requiresDedicatedBackup;
    bool requiresIndependentCredentials;
    bool strictPerformanceIsolation;
    double monthlyBudget;
};

struct PlacementDecision {
    Architecture architecture;
    std::string explanation;
    double estimatedMonthlyCost;
};

class PlacementPolicy {
public:
    PlacementDecision evaluate(const PlacementRequest& request) const {
        if (!validIdentifier(request.tenantId) ||
            !validIdentifier(request.slug)) {
            throw std::invalid_argument("Invalid tenant identifier or slug.");
        }
        if (request.name.empty() || request.region.empty()) {
            throw std::invalid_argument("Tenant name and region are required.");
        }
        if (request.expectedUsers == 0 || request.expectedProjects == 0) {
            throw std::invalid_argument("Expected workloads must be positive.");
        }
        if (request.monthlyBudget < 0.0) {
            throw std::invalid_argument("Budget cannot be negative.");
        }

        // These illustrative costs represent relative planning estimates,
        // not actual cloud-provider quotations.
        const double sharedCost =
            35.0 + 0.0008 * request.expectedUsers
                 + 0.01 * request.expectedProjects;
        const double schemaCost =
            65.0 + 0.0010 * request.expectedUsers
                 + 0.012 * request.expectedProjects;
        const double databaseCost =
            180.0 + 0.0030 * request.expectedUsers
                  + 0.02 * request.expectedProjects;

        if (request.requiresDedicatedBackup ||
            request.requiresIndependentCredentials ||
            request.strictPerformanceIsolation) {
            if (databaseCost > request.monthlyBudget) {
                throw std::runtime_error(
                    "Isolation requirements exceed the supplied budget."
                );
            }
            return {
                Architecture::SeparateDatabase,
                "Dedicated database supports independent credentials, "
                "backup policy, and resource management.",
                databaseCost
            };
        }

        if (request.expectedUsers > 10000 ||
            request.expectedProjects > 5000) {
            if (databaseCost <= request.monthlyBudget) {
                return {
                    Architecture::SeparateDatabase,
                    "Large workload justifies a separately managed database.",
                    databaseCost
                };
            }
            if (schemaCost <= request.monthlyBudget) {
                return {
                    Architecture::SeparateSchema,
                    "Separate schema is the affordable intermediate option.",
                    schemaCost
                };
            }
        }

        if (sharedCost <= request.monthlyBudget) {
            return {
                Architecture::SharedSchema,
                "Shared tables minimize operational overhead for this workload.",
                sharedCost
            };
        }

        if (schemaCost <= request.monthlyBudget) {
            return {
                Architecture::SeparateSchema,
                "Shared placement exceeds budget; schema isolation is viable.",
                schemaCost
            };
        }

        throw std::runtime_error("No placement satisfies the budget.");
    }
};

struct Tenant {
    std::string id;
    std::string slug;
    std::string name;
    std::string region;
    Architecture architecture;
    Status status;
    std::size_t projectQuota;
};

struct Project {
    std::string id;
    std::string tenantId;
    std::string name;
};

struct Principal {
    std::string userId;
    std::unordered_set<std::string> tenantMemberships;
};

class TenantPlatform {
private:
    std::unordered_map<std::string, Tenant> tenants_;
    std::unordered_map<std::string, std::string> slugs_;
    std::unordered_map<std::string, std::vector<Project>> projects_;
    std::set<std::string> schemaNames_;
    std::set<std::string> databaseNames_;
    std::unordered_map<std::string, std::set<int>> migrationVersions_;
    std::size_t nextProjectId_ = 1;

    static std::string normalizeName(std::string value) {
        std::transform(value.begin(), value.end(), value.begin(),
            [](unsigned char c) {
                return static_cast<char>(std::tolower(c));
            });
        return value;
    }

public:
    void provision(const Tenant& tenant) {
        if (!validIdentifier(tenant.id) || !validIdentifier(tenant.slug)) {
            throw std::invalid_argument("Invalid tenant identifiers.");
        }
        if (tenants_.count(tenant.id) || slugs_.count(tenant.slug)) {
            throw std::runtime_error("Tenant ID or slug already exists.");
        }

        if (tenant.architecture == Architecture::SeparateSchema) {
            const std::string schema = "tenant_" + tenant.id;
            if (!validIdentifier(schema) || schemaNames_.count(schema)) {
                throw std::runtime_error("Schema name collision.");
            }
            schemaNames_.insert(schema);
        }

        if (tenant.architecture == Architecture::SeparateDatabase) {
            const std::string database = "db_" + tenant.id;
            if (!validIdentifier(database) || databaseNames_.count(database)) {
                throw std::runtime_error("Database name collision.");
            }
            databaseNames_.insert(database);
        }

        Tenant active = tenant;
        active.status = Status::Active;
        tenants_.emplace(active.id, active);
        slugs_.emplace(active.slug, active.id);
        projects_.emplace(active.id, std::vector<Project>{});
        migrationVersions_.emplace(active.id, std::set<int>{});
    }

    const Tenant& authorize(
        const Principal& principal,
        const std::string& tenantId
    ) const {
        const auto tenantIt = tenants_.find(tenantId);
        if (tenantIt == tenants_.end()) {
            throw std::runtime_error("Tenant does not exist.");
        }

        if (!principal.tenantMemberships.count(tenantId)) {
            throw std::runtime_error("Tenant membership is required.");
        }

        if (tenantIt->second.status != Status::Active) {
            throw std::runtime_error("Tenant is not active.");
        }

        return tenantIt->second;
    }

    Project createProject(
        const Principal& principal,
        const std::string& tenantId,
        std::string name
    ) {
        const Tenant& tenant = authorize(principal, tenantId);
        if (name.empty()) {
            throw std::invalid_argument("Project name cannot be empty.");
        }

        auto& tenantProjects = projects_.at(tenantId);
        if (tenantProjects.size() >= tenant.projectQuota) {
            throw std::runtime_error("Tenant project quota exceeded.");
        }

        const std::string normalized = normalizeName(name);
        for (const Project& existing : tenantProjects) {
            if (normalizeName(existing.name) == normalized) {
                throw std::runtime_error(
                    "Project name already exists for this tenant."
                );
            }
        }

        Project project{
            "project_" + std::to_string(nextProjectId_++),
            tenantId,
            std::move(name)
        };
        tenantProjects.push_back(project);
        return project;
    }

    std::vector<Project> listProjects(
        const Principal& principal,
        const std::string& tenantId
    ) const {
        authorize(principal, tenantId);
        // Even if the storage layer is shared, the result is scoped to the
        // authorized tenant. A real database query must enforce this scope.
        return projects_.at(tenantId);
    }

    void setStatus(const std::string& tenantId, Status nextStatus) {
        auto it = tenants_.find(tenantId);
        if (it == tenants_.end()) {
            throw std::runtime_error("Tenant does not exist.");
        }

        const Status current = it->second.status;
        bool permitted = false;

        if (current == Status::Active) {
            permitted = nextStatus == Status::Suspended ||
                        nextStatus == Status::Deprovisioned;
        } else if (current == Status::Suspended) {
            permitted = nextStatus == Status::Active ||
                        nextStatus == Status::Deprovisioned;
        }

        if (!permitted) {
            throw std::runtime_error("Invalid tenant status transition.");
        }
        it->second.status = nextStatus;
    }

    std::map<std::string, std::string> applyMigration(
        int version,
        const std::vector<std::string>& tenantIds
    ) {
        if (version < 1) {
            throw std::invalid_argument("Migration version must be positive.");
        }

        std::map<std::string, std::string> outcomes;

        for (const auto& tenantId : tenantIds) {
            auto tenantIt = tenants_.find(tenantId);
            if (tenantIt == tenants_.end()) {
                outcomes[tenantId] = "failed: unknown tenant";
                continue;
            }

            if (tenantIt->second.status != Status::Active) {
                outcomes[tenantId] = "skipped: inactive";
                continue;
            }

            auto& applied = migrationVersions_.at(tenantId);
            if (applied.count(version)) {
                outcomes[tenantId] = "skipped: already applied";
                continue;
            }

            // Each tenant records migration progress independently. Production
            // deployments need durable history, locking, and retry semantics.
            applied.insert(version);
            outcomes[tenantId] = "applied";
        }

        return outcomes;
    }

    void printArchitectureReport() const {
        std::vector<std::string> ids;
        ids.reserve(tenants_.size());
        for (const auto& entry : tenants_) {
            ids.push_back(entry.first);
        }
        std::sort(ids.begin(), ids.end());

        for (const auto& id : ids) {
            const Tenant& tenant = tenants_.at(id);
            std::cout << tenant.id
                      << " | " << toString(tenant.architecture)
                      << " | " << toString(tenant.status)
                      << " | projects=" << projects_.at(id).size()
                      << '\n';
        }
    }
};

int main() {
    try {
        PlacementPolicy policy;
        TenantPlatform platform;

        const std::vector<PlacementRequest> requests{
            {
                "tenant_alpha", "alpha", "Alpha Analytics", "ap-south-1",
                80, 12, false, false, false, 100.0
            },
            {
                "tenant_beta", "beta", "Beta Logistics", "ap-south-1",
                900, 300, false, false, false, 1000.0
            },
            {
                "tenant_gamma", "gamma", "Gamma Research", "eu-west-1",
                2000, 120, true, true, true, 500.0
            }
        };

        std::cout << "Placement decisions\n";
        for (const auto& request : requests) {
            const PlacementDecision decision = policy.evaluate(request);
            std::cout << request.tenantId << ": "
                      << toString(decision.architecture)
                      << ", estimated cost="
                      << decision.estimatedMonthlyCost
                      << ", reason=" << decision.explanation << '\n';

            platform.provision(Tenant{
                request.tenantId,
                request.slug,
                request.name,
                request.region,
                decision.architecture,
                Status::Provisioning,
                3
            });
        }

        Principal alphaUser{
            "alice",
            {"tenant_alpha"}
        };
        Principal betaUser{
            "bob",
            {"tenant_beta"}
        };

        platform.createProject(
            alphaUser, "tenant_alpha", "Fraud Analytics"
        );
        platform.createProject(
            alphaUser, "tenant_alpha", "Risk Dashboard"
        );
        platform.createProject(
            betaUser, "tenant_beta", "Fleet Operations"
        );

        std::cout << "\nTenant resources\n";
        platform.printArchitectureReport();

        std::cout << "\nCross-tenant access test\n";
        try {
            platform.listProjects(alphaUser, "tenant_beta");
            std::cerr << "ERROR: unauthorized access was allowed.\n";
            return 2;
        } catch (const std::exception& error) {
            std::cout << "Denied: " << error.what() << '\n';
        }

        std::cout << "\nMigration version 5\n";
        const auto first = platform.applyMigration(
            5, {"tenant_alpha", "tenant_beta", "tenant_gamma"}
        );
        for (const auto& result : first) {
            std::cout << result.first << ": " << result.second << '\n';
        }

        std::cout << "\nRepeated migration version 5\n";
        const auto second = platform.applyMigration(
            5, {"tenant_alpha", "tenant_beta", "tenant_gamma"}
        );
        for (const auto& result : second) {
            std::cout << result.first << ": " << result.second << '\n';
        }

        std::cout << "\nSuspending tenant_beta\n";
        platform.setStatus("tenant_beta", Status::Suspended);
        try {
            platform.listProjects(betaUser, "tenant_beta");
        } catch (const std::exception& error) {
            std::cout << "Denied: " << error.what() << '\n';
        }

    } catch (const std::exception& error) {
        std::cerr << "Fatal error: " << error.what() << '\n';
        return 1;
    }

    return 0;
}
