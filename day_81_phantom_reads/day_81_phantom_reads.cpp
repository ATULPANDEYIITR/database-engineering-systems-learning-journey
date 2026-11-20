#include <algorithm>
#include <cassert>
#include <cmath>
#include <iostream>
#include <map>
#include <optional>
#include <stdexcept>
#include <string>
#include <vector>

/*
 * Phantom Reads: Range Queries and Transaction Isolation
 *
 * C++17 repository-independent transactional storage simulator.
 *
 * Models:
 * - Read Committed
 * - Repeatable Read
 * - Serializable
 * - Snapshot visibility
 * - Predicate-range reads
 * - Write-write conflicts
 * - Transaction states
 * - Atomic commit validation
 */

enum class IsolationLevel {
    READ_COMMITTED,
    REPEATABLE_READ,
    SERIALIZABLE
};

enum class TransactionState {
    ACTIVE,
    COMMITTED,
    ABORTED
};

std::string toString(IsolationLevel level) {
    switch (level) {
        case IsolationLevel::READ_COMMITTED:
            return "READ COMMITTED";
        case IsolationLevel::REPEATABLE_READ:
            return "REPEATABLE READ";
        case IsolationLevel::SERIALIZABLE:
            return "SERIALIZABLE";
    }
    throw std::logic_error("Unknown isolation level");
}

struct Product {
    int id;
    std::string name;
    double price;
    std::string category;

    void validate() const {
        if (id <= 0) {
            throw std::invalid_argument("Product ID must be positive");
        }

        if (name.empty()) {
            throw std::invalid_argument("Product name is required");
        }

        if (!std::isfinite(price) || price < 0) {
            throw std::invalid_argument("Invalid product price");
        }

        if (category.empty()) {
            throw std::invalid_argument("Category is required");
        }
    }
};

struct VersionedProduct {
    Product product;
    unsigned long long version;
};

struct RangePredicate {
    double minimum;
    double maximum;
    bool includeMinimum = true;
    bool includeMaximum = false;

    RangePredicate(
        double min,
        double max,
        bool includeMin = true,
        bool includeMax = false
    ) : minimum(min),
        maximum(max),
        includeMinimum(includeMin),
        includeMaximum(includeMax) {

        if (!std::isfinite(min) || !std::isfinite(max) || min > max) {
            throw std::invalid_argument("Invalid range");
        }
    }

    bool contains(double value) const {
        bool lower = includeMinimum
            ? value >= minimum
            : value > minimum;

        bool upper = includeMaximum
            ? value <= maximum
            : value < maximum;

        return lower && upper;
    }
};

struct Change {
    unsigned long long version;
    double price;
    int productId;
};

class TransactionError : public std::runtime_error {
public:
    using std::runtime_error::runtime_error;
};

class SerializationFailure : public TransactionError {
public:
    using TransactionError::TransactionError;
};

class WriteConflict : public TransactionError {
public:
    using TransactionError::TransactionError;
};

struct Transaction {
    int id;
    IsolationLevel isolation;
    TransactionState state = TransactionState::ACTIVE;

    unsigned long long startVersion;

    std::map<int, VersionedProduct> snapshot;

    // nullopt means a deletion.
    std::map<int, std::optional<Product>> writes;

    std::vector<RangePredicate> readRanges;

    void ensureActive() const {
        if (state != TransactionState::ACTIVE) {
            throw TransactionError("Transaction is not active");
        }
    }
};

class Database {
private:
    std::map<int, VersionedProduct> rows;
    std::vector<Change> history;

    unsigned long long version = 0;
    int nextTransactionId = 1;

    std::map<int, Product> visibleRows(
        const Transaction& transaction
    ) const {
        transaction.ensureActive();

        const auto& source =
            transaction.isolation == IsolationLevel::READ_COMMITTED
            ? rows
            : transaction.snapshot;

        std::map<int, Product> result;

        for (const auto& [id, entry] : source) {
            result.emplace(id, entry.product);
        }

        for (const auto& [id, product] : transaction.writes) {
            if (product.has_value()) {
                result[id] = *product;
            } else {
                result.erase(id);
            }
        }

        return result;
    }

    void validateWriteConflicts(
        const Transaction& transaction
    ) const {
        for (const auto& [id, product] : transaction.writes) {
            auto current = rows.find(id);
            auto original = transaction.snapshot.find(id);

            bool existsNow = current != rows.end();
            bool existedInitially =
                original != transaction.snapshot.end();

            if (transaction.isolation != IsolationLevel::READ_COMMITTED) {
                if (existsNow != existedInitially) {
                    throw WriteConflict(
                        "Concurrent insert or delete detected"
                    );
                }

                if (
                    existsNow &&
                    current->second.version != original->second.version
                ) {
                    throw WriteConflict(
                        "Concurrent update detected"
                    );
                }
            } else if (!existedInitially && existsNow) {
                throw WriteConflict(
                    "Concurrent insertion detected"
                );
            }
        }
    }

    void validateSerializable(
        const Transaction& transaction
    ) const {
        for (const auto& change : history) {
            if (change.version <= transaction.startVersion) {
                continue;
            }

            for (const auto& predicate : transaction.readRanges) {
                if (predicate.contains(change.price)) {
                    throw SerializationFailure(
                        "Concurrent change overlaps a read predicate"
                    );
                }
            }
        }
    }

public:
    void seed(const std::vector<Product>& products) {
        for (const auto& product : products) {
            product.validate();

            if (rows.count(product.id)) {
                throw WriteConflict("Duplicate product ID");
            }

            rows.emplace(
                product.id,
                VersionedProduct{product, ++version}
            );
        }
    }

    Transaction begin(IsolationLevel isolation) {
        Transaction transaction;

        transaction.id = nextTransactionId++;
        transaction.isolation = isolation;
        transaction.startVersion = version;
        transaction.snapshot = rows;

        std::cout
            << "\nTransaction " << transaction.id
            << " started: " << toString(isolation)
            << '\n';

        return transaction;
    }

    std::vector<Product> queryRange(
        Transaction& transaction,
        const RangePredicate& predicate
    ) {
        transaction.ensureActive();

        if (transaction.isolation == IsolationLevel::SERIALIZABLE) {
            transaction.readRanges.push_back(predicate);
        }

        auto visible = visibleRows(transaction);
        std::vector<Product> result;

        for (const auto& [id, product] : visible) {
            if (predicate.contains(product.price)) {
                result.push_back(product);
            }
        }

        return result;
    }

    void insert(
        Transaction& transaction,
        const Product& product
    ) {
        transaction.ensureActive();
        product.validate();

        if (visibleRows(transaction).count(product.id)) {
            throw WriteConflict("Product already exists");
        }

        transaction.writes[product.id] = product;
    }

    void update(
        Transaction& transaction,
        const Product& product
    ) {
        transaction.ensureActive();
        product.validate();

        if (!visibleRows(transaction).count(product.id)) {
            throw TransactionError("Product does not exist");
        }

        transaction.writes[product.id] = product;
    }

    void remove(
        Transaction& transaction,
        int id
    ) {
        transaction.ensureActive();

        if (!visibleRows(transaction).count(id)) {
            throw TransactionError("Product does not exist");
        }

        transaction.writes[id] = std::nullopt;
    }

    void commit(Transaction& transaction) {
        transaction.ensureActive();

        try {
            validateWriteConflicts(transaction);

            if (transaction.isolation == IsolationLevel::SERIALIZABLE) {
                validateSerializable(transaction);
            }

            for (const auto& [id, product] : transaction.writes) {
                if (product.has_value()) {
                    product->validate();
                }
            }

            // All checks occur before the shared database is modified.
            for (const auto& [id, product] : transaction.writes) {
                ++version;

                if (!product.has_value()) {
                    rows.erase(id);
                } else {
                    rows[id] = VersionedProduct{
                        *product,
                        version
                    };

                    history.push_back(
                        Change{version, product->price, id}
                    );
                }
            }

            transaction.state = TransactionState::COMMITTED;

            std::cout
                << "Transaction " << transaction.id
                << " committed.\n";

        } catch (const TransactionError&) {
            transaction.state = TransactionState::ABORTED;
            std::cout
                << "Transaction " << transaction.id
                << " aborted.\n";
            throw;
        }
    }

    void rollback(Transaction& transaction) {
        transaction.ensureActive();
        transaction.writes.clear();
        transaction.state = TransactionState::ABORTED;

        std::cout << "Transaction rolled back.\n";
    }

    void display(
        const std::string& title,
        const std::vector<Product>& products
    ) const {
        std::cout << "\n" << title << '\n';
        std::cout << "-------------------------------------------\n";

        for (const auto& product : products) {
            std::cout
                << product.id << " | "
                << product.name << " | "
                << product.price << '\n';
        }

        std::cout << "Rows: " << products.size() << '\n';
    }

    std::vector<Product> allProducts() const {
        std::vector<Product> result;

        for (const auto& [id, entry] : rows) {
            result.push_back(entry.product);
        }

        return result;
    }
};

Database createDatabase() {
    Database database;

    database.seed({
        {1, "Keyboard", 1200, "Electronics"},
        {2, "Mouse", 800, "Electronics"},
        {3, "Monitor", 8500, "Electronics"},
        {4, "Desk", 6000, "Furniture"},
        {5, "Notebook", 150, "Stationery"}
    });

    return database;
}

void demonstrateReadCommitted() {
    std::cout << "\n=== READ COMMITTED ===\n";

    Database database = createDatabase();

    auto reader = database.begin(IsolationLevel::READ_COMMITTED);
    RangePredicate range(500, 5000);

    auto first = database.queryRange(reader, range);

    auto writer = database.begin(IsolationLevel::READ_COMMITTED);

    database.insert(
        writer,
        {6, "Webcam", 2500, "Electronics"}
    );

    database.commit(writer);

    auto second = database.queryRange(reader, range);

    database.display("First query", first);
    database.display("Second query", second);

    assert(first.size() == 3);
    assert(second.size() == 4);

    database.commit(reader);
}

void demonstrateRepeatableRead() {
    std::cout << "\n=== REPEATABLE READ ===\n";

    Database database = createDatabase();

    auto reader = database.begin(IsolationLevel::REPEATABLE_READ);
    RangePredicate range(500, 5000);

    auto first = database.queryRange(reader, range);

    auto writer = database.begin(IsolationLevel::READ_COMMITTED);

    database.insert(
        writer,
        {6, "Webcam", 2500, "Electronics"}
    );

    database.commit(writer);

    auto second = database.queryRange(reader, range);

    database.display("First query", first);
    database.display("Second query", second);

    assert(first.size() == second.size());

    database.commit(reader);

    auto later = database.begin(IsolationLevel::REPEATABLE_READ);
    auto current = database.queryRange(later, range);

    assert(current.size() == 4);

    database.display("New transaction", current);

    database.commit(later);
}

void demonstrateSerializable() {
    std::cout << "\n=== SERIALIZABLE ===\n";

    Database database = createDatabase();

    auto reader = database.begin(IsolationLevel::SERIALIZABLE);
    RangePredicate range(500, 5000);

    auto first = database.queryRange(reader, range);

    auto writer = database.begin(IsolationLevel::READ_COMMITTED);

    database.insert(
        writer,
        {6, "Webcam", 2500, "Electronics"}
    );

    database.commit(writer);

    database.display("Initial range", first);

    try {
        database.commit(reader);
        assert(false);
    } catch (const SerializationFailure& error) {
        std::cout
            << "Expected serialization failure: "
            << error.what() << '\n';
    }

    assert(reader.state == TransactionState::ABORTED);
}

void demonstrateRangeBoundaries() {
    std::cout << "\n=== RANGE BOUNDARIES ===\n";

    Database database = createDatabase();

    auto transaction = database.begin(
        IsolationLevel::REPEATABLE_READ
    );

    RangePredicate range(800, 6000, true, false);

    auto results = database.queryRange(transaction, range);

    database.display("Range [800, 6000)", results);

    for (const auto& product : results) {
        assert(product.price >= 800);
        assert(product.price < 6000);
    }

    database.commit(transaction);
}

void demonstrateRollback() {
    std::cout << "\n=== ROLLBACK ===\n";

    Database database = createDatabase();

    auto transaction = database.begin(
        IsolationLevel::READ_COMMITTED
    );

    database.insert(
        transaction,
        {99, "Temporary", 900, "Testing"}
    );

    database.rollback(transaction);

    auto products = database.allProducts();

    assert(std::none_of(
        products.begin(),
        products.end(),
        [](const Product& product) {
            return product.id == 99;
        }
    ));

    std::cout << "Uncommitted insertion discarded.\n";
}

int main() {
    try {
        demonstrateReadCommitted();
        demonstrateRepeatableRead();
        demonstrateSerializable();
        demonstrateRangeBoundaries();
        demonstrateRollback();

        std::cout << "\nAll transaction tests passed.\n";

    } catch (const std::exception& error) {
        std::cerr << "Execution error: " << error.what() << '\n';
        return 1;
    }

    return 0;
}
