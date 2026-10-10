#include <algorithm>
#include <cstdint>
#include <functional>
#include <iomanip>
#include <iostream>
#include <map>
#include <optional>
#include <set>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

using namespace std;

class EvolutionError : public runtime_error {
public:
    using runtime_error::runtime_error;
};

struct CustomerV1 {
    int64_t id;
    string name;
};

struct CustomerV2 {
    int64_t id;
    string name;
    optional<string> email;
};

struct CustomerV3 {
    int64_t id;
    string displayName;
    string email;
    bool active;
    string region;
};

void validate(const CustomerV1& customer) {
    if (customer.id <= 0 || customer.name.empty()) {
        throw EvolutionError("Invalid V1 customer");
    }
}

void validate(const CustomerV2& customer) {
    if (customer.id <= 0 || customer.name.empty()) {
        throw EvolutionError("Invalid V2 identity");
    }
    if (customer.email && customer.email->find('@') == string::npos) {
        throw EvolutionError("V2 email must contain @");
    }
}

void validate(const CustomerV3& customer) {
    if (customer.id <= 0 || customer.displayName.empty()) {
        throw EvolutionError("V3 identity is invalid");
    }
    if (customer.email.find('@') == string::npos) {
        throw EvolutionError("V3 requires a valid email");
    }
    if (customer.region.size() != 2) {
        throw EvolutionError("Region must be a two-character code");
    }
}

CustomerV2 migrate(const CustomerV1& oldRecord) {
    validate(oldRecord);

    // Expansion introduces a nullable email field without pretending that
    // historical records already contain verified contact information.
    CustomerV2 result{oldRecord.id, oldRecord.name, nullopt};
    validate(result);
    return result;
}

CustomerV3 migrate(const CustomerV2& oldRecord) {
    validate(oldRecord);

    if (!oldRecord.email || oldRecord.email->empty()) {
        throw EvolutionError(
            "Cannot enforce required email until the record is backfilled"
        );
    }

    CustomerV3 result{
        oldRecord.id,
        oldRecord.name,
        *oldRecord.email,
        true,
        "IN"
    };
    validate(result);
    return result;
}

enum class MigrationPhase {
    Expand,
    Backfill,
    Enforce,
    Contract
};

string phaseName(MigrationPhase phase) {
    switch (phase) {
        case MigrationPhase::Expand: return "expand";
        case MigrationPhase::Backfill: return "backfill";
        case MigrationPhase::Enforce: return "enforce";
        case MigrationPhase::Contract: return "contract";
    }
    throw EvolutionError("Unknown migration phase");
}

struct Deployment {
    MigrationPhase phase;
    bool oldReadersRunning;
    bool oldWritersRunning;
    bool backfillComplete;
    bool compatibilityTestPassed;
};

bool canAdvance(const Deployment& deployment, MigrationPhase next) {
    if (static_cast<int>(next) != static_cast<int>(deployment.phase) + 1) {
        return false;
    }

    switch (next) {
        case MigrationPhase::Expand:
            return deployment.compatibilityTestPassed;
        case MigrationPhase::Backfill:
            return true;
        case MigrationPhase::Enforce:
            return deployment.backfillComplete;
        case MigrationPhase::Contract:
            return !deployment.oldReadersRunning &&
                   !deployment.oldWritersRunning &&
                   deployment.backfillComplete;
    }
    return false;
}

class CustomerRepository {
private:
    map<int64_t, CustomerV1> rows;
    uint64_t revision = 0;

public:
    void insert(CustomerV1 customer) {
        validate(customer);
        if (rows.count(customer.id)) {
            throw EvolutionError("Duplicate customer identifier");
        }
        rows.emplace(customer.id, move(customer));
        ++revision;
    }

    vector<CustomerV1> snapshot() const {
        vector<CustomerV1> result;
        for (const auto& [id, customer] : rows) {
            result.push_back(customer);
        }
        return result;
    }

    uint64_t getRevision() const {
        return revision;
    }

    // Build a replacement dataset before swapping it into service. If any
    // transformation fails, the original collection remains unchanged.
    vector<CustomerV2> prepareExpansion() const {
        vector<CustomerV2> result;
        result.reserve(rows.size());

        for (const auto& [id, customer] : rows) {
            result.push_back(migrate(customer));
        }

        return result;
    }
};

class VersionedStore {
private:
    map<int64_t, CustomerV3> currentRows;
    uint64_t revision = 0;

public:
    void replaceAll(vector<CustomerV3> replacement,
                    uint64_t expectedRevision) {
        if (revision != expectedRevision) {
            throw EvolutionError("Concurrent modification detected");
        }

        map<int64_t, CustomerV3> candidate;
        for (const auto& customer : replacement) {
            validate(customer);
            if (!candidate.emplace(customer.id, customer).second) {
                throw EvolutionError("Duplicate identifier in migration batch");
            }
        }

        currentRows.swap(candidate);
        ++revision;
    }

    void print() const {
        for (const auto& [id, customer] : currentRows) {
            cout << "id=" << id
                 << ", displayName=" << customer.displayName
                 << ", email=" << customer.email
                 << ", active=" << boolalpha << customer.active
                 << ", region=" << customer.region << '\n';
        }
    }
};

int main() {
    try {
        cout << "Customer data schema evolution case study\n";

        CustomerRepository repository;
        repository.insert({1001, "Nisha Kapoor"});
        repository.insert({1002, "Dev Malhotra"});

        const uint64_t originalRevision = repository.getRevision();
        cout << "Initial dataset revision: " << originalRevision << '\n';

        auto expanded = repository.prepareExpansion();
        cout << "Expanded records: " << expanded.size()
             << "; email remains nullable during expansion\n";

        // A legacy row without email is intentionally rejected at enforcement
        // time. A data owner must supply verified information first.
        try {
            migrate(expanded.front());
        } catch (const EvolutionError& error) {
            cout << "Expected enforcement block: " << error.what() << '\n';
        }

        vector<CustomerV3> backfilled;
        backfilled.reserve(expanded.size());

        for (const auto& customer : expanded) {
            CustomerV2 enriched = customer;
            enriched.email = "customer" + to_string(customer.id) +
                             "@example.com";
            backfilled.push_back(migrate(enriched));
        }

        VersionedStore store;
        store.replaceAll(backfilled, 0);

        cout << "Enforced V3 dataset:\n";
        store.print();

        Deployment deployment{
            MigrationPhase::Expand, true, true, false, true
        };

        deployment.phase = MigrationPhase::Expand;
        cout << "Phase: " << phaseName(deployment.phase) << '\n';

        if (canAdvance(deployment, MigrationPhase::Backfill)) {
            deployment.phase = MigrationPhase::Backfill;
            deployment.backfillComplete = true;
            cout << "Phase: " << phaseName(deployment.phase) << '\n';
        }

        if (canAdvance(deployment, MigrationPhase::Enforce)) {
            deployment.phase = MigrationPhase::Enforce;
            cout << "Phase: " << phaseName(deployment.phase) << '\n';
        }

        // Contracting removes compatibility for old software, so it cannot
        // proceed while either old readers or old writers remain active.
        if (!canAdvance(deployment, MigrationPhase::Contract)) {
            cout << "Contract blocked: old application instances remain\n";
        }

        deployment.oldReadersRunning = false;
        deployment.oldWritersRunning = false;

        if (canAdvance(deployment, MigrationPhase::Contract)) {
            deployment.phase = MigrationPhase::Contract;
            cout << "Phase: " << phaseName(deployment.phase) << '\n';
        }

        // Deterministic ordered maps make duplicate detection and output
        // predictable. Migration processing is O(n log n) for map insertion.
        // For large online datasets, use bounded batches and resumable cursors.
        cout << "Repository revision before migration: "
             << originalRevision << '\n';

        try {
            vector<CustomerV3> invalidBatch = backfilled;
            invalidBatch.push_back(backfilled.front());
            store.replaceAll(invalidBatch, 1);
        } catch (const EvolutionError& error) {
            cout << "Expected batch rejection: " << error.what() << '\n';
        }

        store.print();
    } catch (const exception& error) {
        cerr << "Schema evolution failed: " << error.what() << '\n';
        return 1;
    }

    return 0;
}
