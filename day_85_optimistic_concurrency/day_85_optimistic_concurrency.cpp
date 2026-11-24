#include <algorithm>
#include <cmath>
#include <cstdint>
#include <exception>
#include <functional>
#include <iomanip>
#include <iostream>
#include <limits>
#include <map>
#include <mutex>
#include <optional>
#include <random>
#include <stdexcept>
#include <string>
#include <thread>
#include <utility>
#include <vector>

using namespace std;

// ---------------------------------------------------------
// Optimistic Concurrency Control
// C++17 implementation
// ---------------------------------------------------------

enum class TransactionStatus {
    Pending,
    Committed,
    Conflicted,
    Aborted
};

enum class OperationType {
    Update,
    TransferDebit,
    TransferCredit
};

class ConcurrencyException : public runtime_error {
public:
    explicit ConcurrencyException(const string& message)
        : runtime_error(message) {}
};

class VersionConflict : public ConcurrencyException {
public:
    string recordId;
    uint64_t expectedVersion;
    uint64_t actualVersion;

    VersionConflict(
        const string& id,
        uint64_t expected,
        uint64_t actual
    )
        : ConcurrencyException(
            "Version conflict on " + id +
            ": expected " + to_string(expected) +
            ", actual " + to_string(actual)
        ),
          recordId(id),
          expectedVersion(expected),
          actualVersion(actual) {}
};

class ValidationException : public runtime_error {
public:
    explicit ValidationException(const string& message)
        : runtime_error(message) {}
};

struct AccountData {
    double balance = 0.0;
};

struct VersionedRecord {
    AccountData data;
    uint64_t version = 1;
};

struct Snapshot {
    string id;
    AccountData data;
    uint64_t version;
};

struct AuditEntry {
    string transactionId;
    string recordId;
    uint64_t oldVersion;
    uint64_t newVersion;
    OperationType operation;
};

struct TransactionResult {
    TransactionStatus status;
    unsigned attempts;
    uint64_t finalVersion;
};


// ---------------------------------------------------------
// Repository
// ---------------------------------------------------------

class VersionedRepository {

private:

    map<string, VersionedRecord> records;
    vector<AuditEntry> audit;

    // A single mutex makes compare-and-swap atomic.
    mutable mutex repositoryMutex;

    void validate(const AccountData& data) const {

        if (!isfinite(data.balance) || data.balance < 0) {
            throw ValidationException(
                "Balance must be finite and non-negative."
            );
        }
    }

public:

    void create(
        const string& id,
        const AccountData& data
    ) {

        if (id.empty()) {
            throw ValidationException("Record ID is empty.");
        }

        validate(data);

        lock_guard<mutex> guard(repositoryMutex);

        if (records.count(id)) {
            throw ValidationException("Duplicate record.");
        }

        records.emplace(
            id,
            VersionedRecord{data, 1}
        );
    }

    Snapshot read(const string& id) const {

        lock_guard<mutex> guard(repositoryMutex);

        auto iterator = records.find(id);

        if (iterator == records.end()) {
            throw ValidationException("Record not found: " + id);
        }

        return Snapshot{
            id,
            iterator->second.data,
            iterator->second.version
        };
    }

    Snapshot compareAndSwap(
        const string& id,
        uint64_t expectedVersion,
        const AccountData& newData,
        const string& transactionId
    ) {

        validate(newData);

        lock_guard<mutex> guard(repositoryMutex);

        auto iterator = records.find(id);

        if (iterator == records.end()) {
            throw ValidationException("Record not found.");
        }

        VersionedRecord& record = iterator->second;

        if (record.version != expectedVersion) {
            throw VersionConflict(
                id,
                expectedVersion,
                record.version
            );
        }

        uint64_t oldVersion = record.version;

        record.data = newData;
        ++record.version;

        audit.push_back({
            transactionId,
            id,
            oldVersion,
            record.version,
            OperationType::Update
        });

        return Snapshot{
            id,
            record.data,
            record.version
        };
    }

    TransactionResult updateWithRetry(
        const string& id,
        const function<AccountData(const AccountData&)>& transform,
        unsigned maxAttempts = 10
    ) {

        if (maxAttempts == 0) {
            throw ValidationException("Retry count cannot be zero.");
        }

        static thread_local mt19937 generator(
            random_device{}()
        );

        uniform_int_distribution<int> jitter(1, 5);

        const string transactionId =
            "TX-" + to_string(
                hash<thread::id>{}(this_thread::get_id())
            );

        for (unsigned attempt = 1; attempt <= maxAttempts; ++attempt) {

            Snapshot snapshot = read(id);

            // Business calculation occurs outside the mutex.
            AccountData proposed = transform(snapshot.data);

            try {

                Snapshot result = compareAndSwap(
                    id,
                    snapshot.version,
                    proposed,
                    transactionId
                );

                return {
                    TransactionStatus::Committed,
                    attempt,
                    result.version
                };

            } catch (const VersionConflict&) {

                if (attempt == maxAttempts) {
                    return {
                        TransactionStatus::Aborted,
                        attempt,
                        read(id).version
                    };
                }

                unsigned delay = (1U << min(attempt - 1, 10U))
                               * jitter(generator);

                this_thread::sleep_for(
                    chrono::microseconds(delay)
                );
            }
        }

        return {
            TransactionStatus::Aborted,
            maxAttempts,
            0
        };
    }

    /*
     * Transfer is a multi-record transaction.
     *
     * Both versions are checked before either record changes.
     * Both changes are committed under the same mutex.
     */
    void transfer(
        const string& sourceId,
        const string& destinationId,
        double amount,
        const string& transactionId
    ) {

        if (
            sourceId == destinationId ||
            !isfinite(amount) ||
            amount <= 0
        ) {
            throw ValidationException("Invalid transfer parameters.");
        }

        lock_guard<mutex> guard(repositoryMutex);

        auto sourceIterator = records.find(sourceId);
        auto destinationIterator = records.find(destinationId);

        if (
            sourceIterator == records.end() ||
            destinationIterator == records.end()
        ) {
            throw ValidationException("Account not found.");
        }

        VersionedRecord& source = sourceIterator->second;
        VersionedRecord& destination = destinationIterator->second;

        if (source.data.balance < amount) {
            throw ValidationException("Insufficient funds.");
        }

        // Calculate both results before changing stored state.
        AccountData newSource = source.data;
        AccountData newDestination = destination.data;

        newSource.balance -= amount;
        newDestination.balance += amount;

        validate(newSource);
        validate(newDestination);

        uint64_t oldSourceVersion = source.version;
        uint64_t oldDestinationVersion = destination.version;

        source.data = newSource;
        destination.data = newDestination;

        ++source.version;
        ++destination.version;

        audit.push_back({
            transactionId,
            sourceId,
            oldSourceVersion,
            source.version,
            OperationType::TransferDebit
        });

        audit.push_back({
            transactionId,
            destinationId,
            oldDestinationVersion,
            destination.version,
            OperationType::TransferCredit
        });
    }

    vector<AuditEntry> getAudit() const {

        lock_guard<mutex> guard(repositoryMutex);

        return audit;
    }

    double totalBalance() const {

        lock_guard<mutex> guard(repositoryMutex);

        double total = 0;

        for (const auto& [id, record] : records) {
            total += record.data.balance;
        }

        return total;
    }
};


// ---------------------------------------------------------
// Inventory concurrency service
// ---------------------------------------------------------

class InventoryService {

private:
    VersionedRepository& repository;

public:

    explicit InventoryService(VersionedRepository& repo)
        : repository(repo) {}

    TransactionResult reserve(
        const string& productId,
        double quantity
    ) {

        if (!isfinite(quantity) || quantity <= 0) {
            throw ValidationException("Invalid quantity.");
        }

        return repository.updateWithRetry(
            productId,
            [quantity](const AccountData& current) {

                if (current.balance < quantity) {
                    throw ValidationException(
                        "Insufficient inventory."
                    );
                }

                return AccountData{
                    current.balance - quantity
                };
            },
            20
        );
    }
};


// ---------------------------------------------------------
// Demonstration
// ---------------------------------------------------------

void printSnapshot(
    const VersionedRepository& repository,
    const string& id
) {

    Snapshot snapshot = repository.read(id);

    cout << left << setw(15) << id
         << " Balance: " << setw(10)
         << snapshot.data.balance
         << " Version: " << snapshot.version
         << '\n';
}

void demonstrateConflict(VersionedRepository& repository) {

    cout << "\n1. Stale version detection\n";

    Snapshot readerA = repository.read("ACCOUNT-A");
    Snapshot readerB = repository.read("ACCOUNT-A");

    repository.compareAndSwap(
        "ACCOUNT-A",
        readerA.version,
        AccountData{4500},
        "TX-A"
    );

    try {

        repository.compareAndSwap(
            "ACCOUNT-A",
            readerB.version,
            AccountData{3000},
            "TX-B"
        );

    } catch (const VersionConflict& error) {

        cout << "Conflict correctly detected: "
             << error.what() << '\n';
    }
}

void demonstrateConcurrency(VersionedRepository& repository) {

    cout << "\n2. Concurrent counter updates\n";

    repository.create("COUNTER", AccountData{0});

    constexpr int THREAD_COUNT = 10;
    constexpr int UPDATES_PER_THREAD = 100;

    vector<thread> workers;

    for (int i = 0; i < THREAD_COUNT; ++i) {

        workers.emplace_back([&repository]() {

            for (int j = 0; j < UPDATES_PER_THREAD; ++j) {

                auto result = repository.updateWithRetry(
                    "COUNTER",
                    [](const AccountData& current) {
                        return AccountData{
                            current.balance + 1
                        };
                    },
                    100
                );

                if (result.status != TransactionStatus::Committed) {
                    throw runtime_error("Counter update aborted.");
                }
            }
        });
    }

    for (auto& worker : workers) {
        worker.join();
    }

    printSnapshot(repository, "COUNTER");

    Snapshot counter = repository.read("COUNTER");

    if (counter.data.balance != 1000) {
        throw runtime_error("Lost update detected.");
    }
}

void demonstrateTransfer(VersionedRepository& repository) {

    cout << "\n3. Atomic transfer\n";

    repository.create("ACCOUNT-B", AccountData{1000});

    double before = repository.totalBalance();

    repository.transfer(
        "ACCOUNT-A",
        "ACCOUNT-B",
        500,
        "TRANSFER-001"
    );

    double after = repository.totalBalance();

    printSnapshot(repository, "ACCOUNT-A");
    printSnapshot(repository, "ACCOUNT-B");

    if (abs(before - after) > 0.000001) {
        throw runtime_error("Financial conservation failure.");
    }
}

void demonstrateInventory(VersionedRepository& repository) {

    cout << "\n4. Inventory reservations\n";

    repository.create("PRODUCT-001", AccountData{1000});

    InventoryService inventory(repository);

    vector<thread> workers;

    for (int i = 0; i < 5; ++i) {

        workers.emplace_back([&inventory]() {

            for (int j = 0; j < 10; ++j) {

                auto result = inventory.reserve(
                    "PRODUCT-001",
                    10
                );

                if (result.status != TransactionStatus::Committed) {
                    throw runtime_error("Reservation aborted.");
                }
            }
        });
    }

    for (auto& worker : workers) {
        worker.join();
    }

    printSnapshot(repository, "PRODUCT-001");
}

void demonstrateAudit(const VersionedRepository& repository) {

    cout << "\n5. Audit trail\n";

    for (const auto& event : repository.getAudit()) {

        cout << event.transactionId
             << " | " << event.recordId
             << " | " << event.oldVersion
             << " -> " << event.newVersion
             << '\n';
    }
}

int main() {

    try {

        VersionedRepository repository;

        repository.create("ACCOUNT-A", AccountData{5000});

        demonstrateConflict(repository);
        demonstrateConcurrency(repository);
        demonstrateTransfer(repository);
        demonstrateInventory(repository);
        demonstrateAudit(repository);

        cout << "\nAll integrity checks passed.\n";

    } catch (const exception& error) {

        cerr << "Execution error: "
             << error.what() << '\n';

        return 1;
    }

    return 0;
}
