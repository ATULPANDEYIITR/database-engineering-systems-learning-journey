#include <algorithm>
#include <iomanip>
#include <iostream>
#include <optional>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <vector>

enum class DeleteAction {
    Restrict,
    Cascade,
    SetNull
};

std::string actionName(DeleteAction action) {
    switch (action) {
        case DeleteAction::Restrict:
            return "RESTRICT";
        case DeleteAction::Cascade:
            return "CASCADE";
        case DeleteAction::SetNull:
            return "SET NULL";
    }
    return "UNKNOWN";
}

struct Customer {
    int id;
    std::string name;
};

struct Order {
    int id;
    int customerId;
    double amount;
};

struct OrderItem {
    int id;
    int orderId;
    std::string product;
    int quantity;
};

class IntegrityException : public std::runtime_error {
public:
    explicit IntegrityException(const std::string& message)
        : std::runtime_error(message) {}
};

class RepositoryGovernanceEngine {
private:
    std::unordered_map<int, Customer> customers_;
    std::unordered_map<int, Order> orders_;
    std::unordered_map<int, OrderItem> items_;

    DeleteAction customerOrderDeleteAction_ = DeleteAction::Restrict;
    DeleteAction orderItemDeleteAction_ = DeleteAction::Cascade;

    static void requirePositive(int value, const std::string& field) {
        if (value <= 0) {
            throw std::invalid_argument(field + " must be positive.");
        }
    }

public:
    void setCustomerOrderDeleteAction(DeleteAction action) {
        customerOrderDeleteAction_ = action;
    }

    void setOrderItemDeleteAction(DeleteAction action) {
        orderItemDeleteAction_ = action;
    }

    void addCustomer(int id, const std::string& name) {
        requirePositive(id, "Customer ID");

        if (customers_.contains(id)) {
            throw IntegrityException(
                "Duplicate customer key: " + std::to_string(id)
            );
        }

        if (name.empty()) {
            throw std::invalid_argument("Customer name cannot be empty.");
        }

        customers_.emplace(id, Customer{id, name});
    }

    void addOrder(int id, int customerId, double amount) {
        requirePositive(id, "Order ID");

        if (orders_.contains(id)) {
            throw IntegrityException(
                "Duplicate order key: " + std::to_string(id)
            );
        }

        if (!customers_.contains(customerId)) {
            throw IntegrityException(
                "Foreign-key violation: customer " +
                std::to_string(customerId) +
                " does not exist."
            );
        }

        if (amount < 0.0) {
            throw std::invalid_argument("Order amount cannot be negative.");
        }

        orders_.emplace(id, Order{id, customerId, amount});
    }

    void addItem(
        int id,
        int orderId,
        const std::string& product,
        int quantity
    ) {
        requirePositive(id, "Item ID");

        if (items_.contains(id)) {
            throw IntegrityException(
                "Duplicate item key: " + std::to_string(id)
            );
        }

        if (!orders_.contains(orderId)) {
            throw IntegrityException(
                "Foreign-key violation: order " +
                std::to_string(orderId) +
                " does not exist."
            );
        }

        if (product.empty()) {
            throw std::invalid_argument("Product cannot be empty.");
        }

        if (quantity <= 0) {
            throw std::invalid_argument("Quantity must be positive.");
        }

        items_.emplace(
            id,
            OrderItem{id, orderId, product, quantity}
        );
    }

    std::vector<int> ordersForCustomer(int customerId) const {
        std::vector<int> result;

        for (const auto& [id, order] : orders_) {
            if (order.customerId == customerId) {
                result.push_back(id);
            }
        }

        return result;
    }

    std::vector<int> itemsForOrder(int orderId) const {
        std::vector<int> result;

        for (const auto& [id, item] : items_) {
            if (item.orderId == orderId) {
                result.push_back(id);
            }
        }

        return result;
    }

    void deleteOrder(int orderId) {
        auto orderIterator = orders_.find(orderId);

        if (orderIterator == orders_.end()) {
            throw IntegrityException(
                "Order " + std::to_string(orderId) + " does not exist."
            );
        }

        const std::vector<int> childItems = itemsForOrder(orderId);

        if (orderItemDeleteAction_ == DeleteAction::Restrict &&
            !childItems.empty()) {
            throw IntegrityException(
                "RESTRICT blocked order deletion because dependent "
                "order items exist."
            );
        }

        if (orderItemDeleteAction_ == DeleteAction::Cascade) {
            for (int itemId : childItems) {
                items_.erase(itemId);
            }
        }

        if (orderItemDeleteAction_ == DeleteAction::SetNull) {
            /*
             * SET NULL requires the child foreign-key column to be nullable.
             * The model therefore uses std::optional<int> only conceptually;
             * this domain keeps the relationship mandatory, so this action
             * cannot be represented without changing OrderItem's invariant.
             */
            throw IntegrityException(
                "SET NULL is incompatible with the mandatory order_id "
                "in this domain model."
            );
        }

        orders_.erase(orderIterator);
    }

    void deleteCustomer(int customerId) {
        auto customerIterator = customers_.find(customerId);

        if (customerIterator == customers_.end()) {
            throw IntegrityException(
                "Customer " + std::to_string(customerId) + " does not exist."
            );
        }

        const std::vector<int> dependentOrders =
            ordersForCustomer(customerId);

        if (customerOrderDeleteAction_ == DeleteAction::Restrict &&
            !dependentOrders.empty()) {
            throw IntegrityException(
                "RESTRICT blocked customer deletion because dependent "
                "orders exist."
            );
        }

        if (customerOrderDeleteAction_ == DeleteAction::Cascade) {
            for (int orderId : dependentOrders) {
                deleteOrder(orderId);
            }
        }

        if (customerOrderDeleteAction_ == DeleteAction::SetNull) {
            throw IntegrityException(
                "SET NULL requires customer_id in Order to be nullable."
            );
        }

        customers_.erase(customerIterator);
    }

    void reassignOrder(int orderId, int newCustomerId) {
        auto orderIterator = orders_.find(orderId);

        if (orderIterator == orders_.end()) {
            throw IntegrityException(
                "Order " + std::to_string(orderId) + " does not exist."
            );
        }

        if (!customers_.contains(newCustomerId)) {
            throw IntegrityException(
                "Cannot assign order to missing customer " +
                std::to_string(newCustomerId)
            );
        }

        orderIterator->second.customerId = newCustomerId;
    }

    std::vector<std::string> validateIntegrity() const {
        std::vector<std::string> errors;

        for (const auto& [id, order] : orders_) {
            if (!customers_.contains(order.customerId)) {
                errors.push_back(
                    "Order " + std::to_string(id) +
                    " references missing customer " +
                    std::to_string(order.customerId)
                );
            }
        }

        for (const auto& [id, item] : items_) {
            if (!orders_.contains(item.orderId)) {
                errors.push_back(
                    "Item " + std::to_string(id) +
                    " references missing order " +
                    std::to_string(item.orderId)
                );
            }
        }

        return errors;
    }

    void printState(const std::string& title) const {
        std::cout << "\n" << title << "\n";
        std::cout << "Customers: " << customers_.size() << "\n";
        std::cout << "Orders:    " << orders_.size() << "\n";
        std::cout << "Items:     " << items_.size() << "\n";
    }
};

void demonstrateForeignKeyInsertion() {
    std::cout << "\n=== Foreign-key insertion rules ===\n";

    RepositoryGovernanceEngine engine;
    engine.addCustomer(1, "Industrial Systems Ltd");
    engine.addOrder(101, 1, 45000.00);
    engine.addItem(1001, 101, "Pressure Sensor", 8);

    try {
        engine.addOrder(102, 999, 500.00);
    } catch (const std::exception& error) {
        std::cout << "Rejected orphan order: "
                  << error.what() << "\n";
    }

    try {
        engine.addItem(1002, 888, "Gateway", 2);
    } catch (const std::exception& error) {
        std::cout << "Rejected orphan item: "
                  << error.what() << "\n";
    }

    engine.printState("Valid state");
}

void demonstrateRestrict() {
    std::cout << "\n=== Parent deletion with RESTRICT ===\n";

    RepositoryGovernanceEngine engine;
    engine.addCustomer(10, "Restricted Customer");
    engine.addOrder(501, 10, 1200.00);

    try {
        engine.deleteCustomer(10);
    } catch (const IntegrityException& error) {
        std::cout << error.what() << "\n";
    }

    engine.deleteOrder(501);
    engine.deleteCustomer(10);

    engine.printState("After dependent order is removed");
}

void demonstrateCascade() {
    std::cout << "\n=== Cascading deletion ===\n";

    RepositoryGovernanceEngine engine;

    engine.addCustomer(20, "Cascade Customer");
    engine.addOrder(601, 20, 1000.00);
    engine.addOrder(602, 20, 2000.00);

    engine.addItem(6001, 601, "Component A", 2);
    engine.addItem(6002, 601, "Component B", 3);
    engine.addItem(6003, 602, "Component C", 4);

    engine.setCustomerOrderDeleteAction(DeleteAction::Cascade);

    engine.printState("Before transitive cascade");
    engine.deleteCustomer(20);
    engine.printState("After customer -> orders -> items cascade");
}

void demonstrateRelationshipReassignment() {
    std::cout << "\n=== Foreign-key reassignment ===\n";

    RepositoryGovernanceEngine engine;

    engine.addCustomer(30, "Customer A");
    engine.addCustomer(31, "Customer B");
    engine.addOrder(701, 30, 5000.00);

    engine.reassignOrder(701, 31);

    std::cout << "Order 701 was reassigned from customer 30 to 31.\n";

    const auto errors = engine.validateIntegrity();

    if (errors.empty()) {
        std::cout << "No referential-integrity violations detected.\n";
    }
}

void demonstrateInvalidSetNullDesign() {
    std::cout << "\n=== SET NULL domain constraint ===\n";

    RepositoryGovernanceEngine engine;

    engine.addCustomer(40, "Nullable Policy Test");
    engine.addOrder(801, 40, 800.00);
    engine.addItem(8001, 801, "Device", 1);

    engine.setOrderItemDeleteAction(DeleteAction::SetNull);

    try {
        engine.deleteOrder(801);
    } catch (const IntegrityException& error) {
        std::cout << "Policy rejected: " << error.what() << "\n";
    }
}

void demonstrateComplexity() {
    std::cout << "\n=== Performance characteristics ===\n";
    std::cout
        << "This educational engine scans child collections to discover "
           "dependents.\n"
        << "With n orders, finding all orders for a customer is O(n), and "
           "finding all items for an order is O(m).\n"
        << "A database normally uses indexes on foreign-key columns to "
           "avoid repeatedly scanning large child tables.\n"
        << "For example, an index on order.customer_id accelerates parent "
           "deletion checks, joins, and customer-specific order lookups.\n";
}

void demonstrateSecurityAndIntegrityBoundary() {
    std::cout << "\n=== Integrity and security boundary ===\n";
    std::cout
        << "Application validation improves error messages, but it cannot "
           "replace database foreign keys.\n"
        << "A second application, migration script, administrative SQL "
           "session, or concurrent transaction can modify the same data.\n"
        << "The database must therefore enforce the invariant at the "
           "storage boundary.\n";
}

int main() {
    std::cout
        << "REFERENTIAL INTEGRITY: FOREIGN KEYS AND CASCADING ACTIONS\n";

    demonstrateForeignKeyInsertion();
    demonstrateRestrict();
    demonstrateCascade();
    demonstrateRelationshipReassignment();
    demonstrateInvalidSetNullDesign();
    demonstrateComplexity();
    demonstrateSecurityAndIntegrityBoundary();

    std::cout << "\n=== Case-study rule ===\n";
    std::cout
        << "A child row is valid only when its non-null foreign-key value "
           "matches a permitted parent key.\n"
        << "RESTRICT preserves dependent rows by blocking parent deletion; "
           "CASCADE propagates deletion; SET NULL preserves the child while "
           "removing its parent reference when the relationship permits it.\n";

    return 0;
}
