/*
 * SQL Foundations Project
 * ========================
 *
 * C++17 case study: a small in-memory relational database engine for an
 * educational order-management system.
 *
 * The program demonstrates how fundamental relational concepts can be modeled
 * at the systems-programming level:
 *
 *   - tables and rows
 *   - primary keys
 *   - foreign keys
 *   - indexes
 *   - constraints
 *   - joins
 *   - grouping and aggregation
 *   - transactions with rollback
 *   - query-like reporting
 *   - validation
 *   - complexity and performance trade-offs
 *
 * Compile:
 *   g++ -std=c++17 -O2 sql_foundations_case_study.cpp -o sql_case_study
 *
 * Run:
 *   ./sql_case_study
 */

#include <algorithm>
#include <chrono>
#include <iomanip>
#include <iostream>
#include <map>
#include <numeric>
#include <optional>
#include <set>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

using namespace std;

struct Customer {
    int id;
    string name;
    string email;
    string city;
    string signupDate;
    string status;
};

struct Employee {
    int id;
    string name;
    string department;
    double salary;
};

struct Category {
    int id;
    string name;
};

struct Product {
    int id;
    int categoryId;
    string name;
    double price;
    int stock;
    bool active;
};

struct Order {
    int id;
    int customerId;
    optional<int> employeeId;
    string orderDate;
    string status;
};

struct OrderItem {
    int id;
    int orderId;
    int productId;
    int quantity;
    double unitPrice;
};

struct Payment {
    int id;
    int orderId;
    double amount;
    string method;
    string paidAt;
    string status;
};

class DatabaseError : public runtime_error {
public:
    explicit DatabaseError(const string& message)
        : runtime_error(message) {}
};

class ConstraintError : public DatabaseError {
public:
    explicit ConstraintError(const string& message)
        : DatabaseError(message) {}
};

class ForeignKeyError : public ConstraintError {
public:
    explicit ForeignKeyError(const string& message)
        : ConstraintError(message) {}
};

class Database {
private:
    vector<Customer> customers;
    vector<Employee> employees;
    vector<Category> categories;
    vector<Product> products;
    vector<Order> orders;
    vector<OrderItem> orderItems;
    vector<Payment> payments;

    unordered_map<int, size_t> customerIndex;
    unordered_map<int, size_t> employeeIndex;
    unordered_map<int, size_t> categoryIndex;
    unordered_map<int, size_t> productIndex;
    unordered_map<int, size_t> orderIndex;
    unordered_map<int, size_t> orderItemIndex;
    unordered_map<int, size_t> paymentIndex;

    unordered_map<string, vector<int>> customersByCity;

    struct Snapshot {
        vector<Customer> customers;
        vector<Employee> employees;
        vector<Category> categories;
        vector<Product> products;
        vector<Order> orders;
        vector<OrderItem> orderItems;
        vector<Payment> payments;
    };

    optional<Snapshot> snapshot;

    template <typename Row>
    bool containsId(const vector<Row>& rows, int id, int Row::*member) const {
        return any_of(
            rows.begin(),
            rows.end(),
            [id, member](const Row& row) {
                return row.*member == id;
            }
        );
    }

public:
    void insertCustomer(const Customer& customer) {
        if (customerIndex.count(customer.id)) {
            throw ConstraintError("Duplicate customer primary key");
        }

        if (customer.name.empty() || customer.email.empty()) {
            throw ConstraintError("Customer name and email are required");
        }

        if (customer.email.find('@') == string::npos) {
            throw ConstraintError("Customer email is invalid");
        }

        if (
            any_of(
                customers.begin(),
                customers.end(),
                [&](const Customer& existing) {
                    return existing.email == customer.email;
                }
            )
        ) {
            throw ConstraintError("Customer email must be unique");
        }

        customerIndex[customer.id] = customers.size();
        customers.push_back(customer);
        customersByCity[customer.city].push_back(customer.id);
    }

    void insertEmployee(const Employee& employee) {
        if (employeeIndex.count(employee.id)) {
            throw ConstraintError("Duplicate employee primary key");
        }

        if (employee.salary < 0) {
            throw ConstraintError("Salary cannot be negative");
        }

        employeeIndex[employee.id] = employees.size();
        employees.push_back(employee);
    }

    void insertCategory(const Category& category) {
        if (categoryIndex.count(category.id)) {
            throw ConstraintError("Duplicate category primary key");
        }

        if (category.name.empty()) {
            throw ConstraintError("Category name is required");
        }

        categoryIndex[category.id] = categories.size();
        categories.push_back(category);
    }

    void insertProduct(const Product& product) {
        if (productIndex.count(product.id)) {
            throw ConstraintError("Duplicate product primary key");
        }

        if (!categoryIndex.count(product.categoryId)) {
            throw ForeignKeyError(
                "Product references an unknown category"
            );
        }

        if (product.price < 0 || product.stock < 0) {
            throw ConstraintError(
                "Product price and stock must be non-negative"
            );
        }

        productIndex[product.id] = products.size();
        products.push_back(product);
    }

    void insertOrder(const Order& order) {
        if (orderIndex.count(order.id)) {
            throw ConstraintError("Duplicate order primary key");
        }

        if (!customerIndex.count(order.customerId)) {
            throw ForeignKeyError(
                "Order references an unknown customer"
            );
        }

        if (
            order.employeeId.has_value() &&
            !employeeIndex.count(*order.employeeId)
        ) {
            throw ForeignKeyError(
                "Order references an unknown employee"
            );
        }

        const set<string> validStatuses = {
            "pending",
            "paid",
            "shipped",
            "cancelled"
        };

        if (!validStatuses.count(order.status)) {
            throw ConstraintError("Invalid order status");
        }

        orderIndex[order.id] = orders.size();
        orders.push_back(order);
    }

    void insertOrderItem(const OrderItem& item) {
        if (orderItemIndex.count(item.id)) {
            throw ConstraintError(
                "Duplicate order-item primary key"
            );
        }

        if (!orderIndex.count(item.orderId)) {
            throw ForeignKeyError(
                "Order item references an unknown order"
            );
        }

        if (!productIndex.count(item.productId)) {
            throw ForeignKeyError(
                "Order item references an unknown product"
            );
        }

        if (item.quantity <= 0 || item.unitPrice < 0) {
            throw ConstraintError(
                "Order item quantity and price are invalid"
            );
        }

        orderItemIndex[item.id] = orderItems.size();
        orderItems.push_back(item);
    }

    void insertPayment(const Payment& payment) {
        if (paymentIndex.count(payment.id)) {
            throw ConstraintError("Duplicate payment primary key");
        }

        if (!orderIndex.count(payment.orderId)) {
            throw ForeignKeyError(
                "Payment references an unknown order"
            );
        }

        if (payment.amount < 0) {
            throw ConstraintError(
                "Payment amount cannot be negative"
            );
        }

        if (
            any_of(
                payments.begin(),
                payments.end(),
                [&](const Payment& existing) {
                    return existing.orderId == payment.orderId;
                }
            )
        ) {
            throw ConstraintError(
                "Only one payment is permitted per order"
            );
        }

        paymentIndex[payment.id] = payments.size();
        payments.push_back(payment);
    }

    Customer& getCustomer(int id) {
        auto it = customerIndex.find(id);

        if (it == customerIndex.end()) {
            throw ForeignKeyError("Customer does not exist");
        }

        return customers[it->second];
    }

    Product& getProduct(int id) {
        auto it = productIndex.find(id);

        if (it == productIndex.end()) {
            throw ForeignKeyError("Product does not exist");
        }

        return products[it->second];
    }

    double orderTotal(int orderId) const {
        double total = 0.0;

        for (const auto& item : orderItems) {
            if (item.orderId == orderId) {
                total += item.quantity * item.unitPrice;
            }
        }

        return total;
    }

    void updateStock(int productId, int quantity) {
        Product& product = getProduct(productId);

        if (quantity < 0) {
            throw ConstraintError(
                "Stock deduction cannot be negative"
            );
        }

        if (product.stock < quantity) {
            throw ConstraintError(
                "Insufficient stock"
            );
        }

        product.stock -= quantity;
    }

    vector<int> customersInCity(const string& city) const {
        auto it = customersByCity.find(city);

        if (it == customersByCity.end()) {
            return {};
        }

        return it->second;
    }

    void rebuildIndexes() {
        customerIndex.clear();
        employeeIndex.clear();
        categoryIndex.clear();
        productIndex.clear();
        orderIndex.clear();
        orderItemIndex.clear();
        paymentIndex.clear();
        customersByCity.clear();

        for (size_t i = 0; i < customers.size(); ++i) {
            customerIndex[customers[i].id] = i;
            customersByCity[customers[i].city].push_back(
                customers[i].id
            );
        }

        for (size_t i = 0; i < employees.size(); ++i) {
            employeeIndex[employees[i].id] = i;
        }

        for (size_t i = 0; i < categories.size(); ++i) {
            categoryIndex[categories[i].id] = i;
        }

        for (size_t i = 0; i < products.size(); ++i) {
            productIndex[products[i].id] = i;
        }

        for (size_t i = 0; i < orders.size(); ++i) {
            orderIndex[orders[i].id] = i;
        }

        for (size_t i = 0; i < orderItems.size(); ++i) {
            orderItemIndex[orderItems[i].id] = i;
        }

        for (size_t i = 0; i < payments.size(); ++i) {
            paymentIndex[payments[i].id] = i;
        }
    }

    void beginTransaction() {
        if (snapshot.has_value()) {
            throw DatabaseError(
                "Nested transactions are not supported"
            );
        }

        snapshot = Snapshot{
            customers,
            employees,
            categories,
            products,
            orders,
            orderItems,
            payments
        };
    }

    void commit() {
        if (!snapshot.has_value()) {
            throw DatabaseError("No active transaction");
        }

        snapshot.reset();
        rebuildIndexes();
    }

    void rollback() {
        if (!snapshot.has_value()) {
            throw DatabaseError("No active transaction");
        }

        customers = snapshot->customers;
        employees = snapshot->employees;
        categories = snapshot->categories;
        products = snapshot->products;
        orders = snapshot->orders;
        orderItems = snapshot->orderItems;
        payments = snapshot->payments;

        snapshot.reset();
        rebuildIndexes();
    }

    template <typename Function>
    void transaction(Function operation) {
        beginTransaction();

        try {
            operation();
            commit();
        } catch (...) {
            rollback();
            throw;
        }
    }

    const vector<Customer>& getCustomers() const {
        return customers;
    }

    const vector<Employee>& getEmployees() const {
        return employees;
    }

    const vector<Category>& getCategories() const {
        return categories;
    }

    const vector<Product>& getProducts() const {
        return products;
    }

    const vector<Order>& getOrders() const {
        return orders;
    }

    const vector<OrderItem>& getOrderItems() const {
        return orderItems;
    }

    const vector<Payment>& getPayments() const {
        return payments;
    }
};

void printHeader(const string& title) {
    cout << "\n" << string(88, '=') << "\n";
    cout << title << "\n";
    cout << string(88, '=') << "\n";
}

void printCustomerReport(const Database& db) {
    printHeader("1. CUSTOMER TABLE AND PRIMARY KEYS");

    cout << left
         << setw(5) << "ID"
         << setw(22) << "Name"
         << setw(26) << "Email"
         << setw(15) << "City"
         << "Status\n";

    cout << string(80, '-') << "\n";

    for (const auto& customer : db.getCustomers()) {
        cout << left
             << setw(5) << customer.id
             << setw(22) << customer.name
             << setw(26) << customer.email
             << setw(15) << customer.city
             << customer.status
             << "\n";
    }
}

void printProductReport(const Database& db) {
    printHeader("2. PRODUCTS AND FOREIGN-KEY RELATIONSHIPS");

    unordered_map<int, string> categoryNames;

    for (const auto& category : db.getCategories()) {
        categoryNames[category.id] = category.name;
    }

    cout << left
         << setw(5) << "ID"
         << setw(24) << "Product"
         << setw(18) << "Category"
         << setw(12) << "Price"
         << setw(8) << "Stock"
         << "Active\n";

    cout << string(80, '-') << "\n";

    for (const auto& product : db.getProducts()) {
        cout << left
             << setw(5) << product.id
             << setw(24) << product.name
             << setw(18) << categoryNames[product.categoryId]
             << setw(12) << fixed << setprecision(2) << product.price
             << setw(8) << product.stock
             << (product.active ? "yes" : "no")
             << "\n";
    }
}

void printOrderJoin(const Database& db) {
    printHeader("3. INNER JOIN: ORDERS + CUSTOMERS");

    unordered_map<int, string> customerNames;

    for (const auto& customer : db.getCustomers()) {
        customerNames[customer.id] = customer.name;
    }

    cout << left
         << setw(8) << "Order"
         << setw(24) << "Customer"
         << setw(22) << "Date"
         << "Status\n";

    cout << string(75, '-') << "\n";

    for (const auto& order : db.getOrders()) {
        cout << left
             << setw(8) << order.id
             << setw(24) << customerNames[order.customerId]
             << setw(22) << order.orderDate
             << order.status
             << "\n";
    }
}

void printDetailedOrderLines(const Database& db) {
    printHeader("4. MULTI-TABLE JOIN AND COMPUTED LINE TOTALS");

    unordered_map<int, string> customerNames;
    unordered_map<int, string> productNames;

    for (const auto& customer : db.getCustomers()) {
        customerNames[customer.id] = customer.name;
    }

    for (const auto& product : db.getProducts()) {
        productNames[product.id] = product.name;
    }

    cout << left
         << setw(8) << "Order"
         << setw(22) << "Customer"
         << setw(24) << "Product"
         << setw(10) << "Qty"
         << setw(12) << "Unit"
         << "Total\n";

    cout << string(90, '-') << "\n";

    for (const auto& item : db.getOrderItems()) {
        auto orderIt = find_if(
            db.getOrders().begin(),
            db.getOrders().end(),
            [&](const Order& order) {
                return order.id == item.orderId;
            }
        );

        if (orderIt == db.getOrders().end()) {
            continue;
        }

        cout << left
             << setw(8) << item.orderId
             << setw(22) << customerNames[orderIt->customerId]
             << setw(24) << productNames[item.productId]
             << setw(10) << item.quantity
             << setw(12) << fixed << setprecision(2)
             << item.unitPrice
             << fixed << setprecision(2)
             << item.quantity * item.unitPrice
             << "\n";
    }
}

void printRevenueByCustomer(const Database& db) {
    printHeader("5. GROUP BY CUSTOMER AND AGGREGATION");

    unordered_map<int, double> revenue;
    unordered_map<int, int> orderCount;

    for (const auto& order : db.getOrders()) {
        if (order.status == "cancelled") {
            continue;
        }

        revenue[order.customerId] += db.orderTotal(order.id);
        orderCount[order.customerId]++;
    }

    struct Row {
        int customerId;
        double revenue;
        int orders;
    };

    vector<Row> rows;

    for (const auto& customer : db.getCustomers()) {
        rows.push_back({
            customer.id,
            revenue[customer.id],
            orderCount[customer.id]
        });
    }

    sort(
        rows.begin(),
        rows.end(),
        [](const Row& a, const Row& b) {
            return a.revenue > b.revenue;
        }
    );

    unordered_map<int, string> names;

    for (const auto& customer : db.getCustomers()) {
        names[customer.id] = customer.name;
    }

    cout << left
         << setw(24) << "Customer"
         << setw(12) << "Orders"
         << "Revenue\n";

    cout << string(55, '-') << "\n";

    for (const auto& row : rows) {
        cout << left
             << setw(24) << names[row.customerId]
             << setw(12) << row.orders
             << fixed << setprecision(2)
             << row.revenue
             << "\n";
    }
}

void printTopProducts(const Database& db) {
    printHeader("6. PRODUCT AGGREGATION AND RANKING");

    unordered_map<int, int> unitsSold;
    unordered_map<int, double> revenue;

    for (const auto& item : db.getOrderItems()) {
        auto orderIt = find_if(
            db.getOrders().begin(),
            db.getOrders().end(),
            [&](const Order& order) {
                return order.id == item.orderId;
            }
        );

        if (
            orderIt == db.getOrders().end() ||
            orderIt->status == "cancelled"
        ) {
            continue;
        }

        unitsSold[item.productId] += item.quantity;
        revenue[item.productId] +=
            item.quantity * item.unitPrice;
    }

    struct ProductStats {
        int id;
        string name;
        int units;
        double revenue;
    };

    vector<ProductStats> stats;

    for (const auto& product : db.getProducts()) {
        stats.push_back({
            product.id,
            product.name,
            unitsSold[product.id],
            revenue[product.id]
        });
    }

    sort(
        stats.begin(),
        stats.end(),
        [](const ProductStats& a, const ProductStats& b) {
            return a.revenue > b.revenue;
        }
    );

    cout << left
         << setw(30) << "Product"
         << setw(12) << "Units"
         << "Revenue\n";

    cout << string(60, '-') << "\n";

    for (const auto& row : stats) {
        cout << left
             << setw(30) << row.name
             << setw(12) << row.units
             << fixed << setprecision(2)
             << row.revenue
             << "\n";
    }
}

void demonstrateConstraints(Database& db) {
    printHeader("7. CONSTRAINT VALIDATION");

    try {
        db.insertProduct({
            100,
            999,
            "Invalid Product",
            1000,
            10,
            true
        });
    } catch (const DatabaseError& error) {
        cout << "Expected failure: "
             << error.what() << "\n";
    }

    try {
        db.insertCustomer({
            1,
            "Duplicate",
            "duplicate@example.com",
            "Delhi",
            "2025-08-01",
            "active"
        });
    } catch (const DatabaseError& error) {
        cout << "Expected failure: "
             << error.what() << "\n";
    }

    try {
        db.insertCustomer({
            99,
            "Bad Email",
            "not-an-email",
            "Delhi",
            "2025-08-01",
            "active"
        });
    } catch (const DatabaseError& error) {
        cout << "Expected failure: "
             << error.what() << "\n";
    }
}

void demonstrateTransactions(Database& db) {
    printHeader("8. ATOMIC ORDER TRANSACTION");

    const int productId = 3;
    const int quantity = 2;

    const int before =
        db.getProduct(productId).stock;

    db.transaction([&]() {
        Product& product =
            db.getProduct(productId);

        if (product.stock < quantity) {
            throw ConstraintError(
                "Insufficient stock"
            );
        }

        db.updateStock(productId, quantity);
    });

    const int after =
        db.getProduct(productId).stock;

    cout << "Stock before commit: " << before << "\n";
    cout << "Stock after commit : " << after << "\n";

    const int rollbackBefore =
        db.getProduct(1).stock;

    try {
        db.transaction([&]() {
            db.updateStock(1, 1);

            throw DatabaseError(
                "Payment service failed"
            );
        });
    } catch (const DatabaseError& error) {
        cout << "Transaction failed: "
             << error.what() << "\n";
    }

    const int rollbackAfter =
        db.getProduct(1).stock;

    cout << "Stock before failed transaction: "
         << rollbackBefore << "\n";

    cout << "Stock after rollback: "
         << rollbackAfter << "\n";

    cout << "Rollback preserved state: "
         << boolalpha
         << (rollbackBefore == rollbackAfter)
         << "\n";
}

void demonstrateIndex(Database& db) {
    printHeader("9. INDEX LOOKUP");

    vector<int> customerIds =
        db.customersInCity("Lucknow");

    cout << "Customers found through city index:\n";

    for (int id : customerIds) {
        const Customer& customer =
            db.getCustomer(id);

        cout << "  "
             << customer.id
             << " - "
             << customer.name
             << "\n";
    }

    cout << "\nA hash-based index provides expected O(1) key lookup, "
            "while building or maintaining the index has a cost.\n";
}

void demonstrateComplexity(Database& db) {
    printHeader("10. QUERY COMPLEXITY CASE STUDY");

    vector<Customer> syntheticCustomers;

    const int recordCount = 100000;

    syntheticCustomers.reserve(recordCount);

    for (int i = 0; i < recordCount; ++i) {
        syntheticCustomers.push_back({
            i,
            "Customer " + to_string(i),
            "customer" + to_string(i) + "@example.com",
            i % 2 == 0 ? "Lucknow" : "Delhi",
            "2025-01-01",
            "active"
        });
    }

    const string targetCity = "Lucknow";

    auto startLinear =
        chrono::high_resolution_clock::now();

    size_t linearMatches = count_if(
        syntheticCustomers.begin(),
        syntheticCustomers.end(),
        [&](const Customer& customer) {
            return customer.city == targetCity;
        }
    );

    auto endLinear =
        chrono::high_resolution_clock::now();

    auto linearDuration =
        chrono::duration_cast<
            chrono::microseconds
        >(endLinear - startLinear);

    unordered_map<string, vector<int>> cityIndex;

    auto startIndex =
        chrono::high_resolution_clock::now();

    for (const auto& customer : syntheticCustomers) {
        cityIndex[customer.city].push_back(
            customer.id
        );
    }

    auto endIndex =
        chrono::high_resolution_clock::now();

    auto indexBuildDuration =
        chrono::duration_cast<
            chrono::microseconds
        >(endIndex - startIndex);

    auto startIndexed =
        chrono::high_resolution_clock::now();

    size_t indexedMatches =
        cityIndex[targetCity].size();

    auto endIndexed =
        chrono::high_resolution_clock::now();

    auto indexedDuration =
        chrono::duration_cast<
            chrono::microseconds
        >(endIndexed - startIndexed);

    cout << "Records: " << recordCount << "\n";
    cout << "Linear matches: "
         << linearMatches << "\n";
    cout << "Indexed matches: "
         << indexedMatches << "\n";
    cout << "Linear scan time: "
         << linearDuration.count()
         << " microseconds\n";
    cout << "Index build time: "
         << indexBuildDuration.count()
         << " microseconds\n";
    cout << "Indexed lookup time: "
         << indexedDuration.count()
         << " microseconds\n";

    cout << "\nComplexity model:\n";
    cout << "  Linear scan: O(n)\n";
    cout << "  Hash index lookup: expected O(1)\n";
    cout << "  Index construction: O(n)\n";
    cout << "  Index storage: O(n)\n";
}

void demonstrateDataQuality(const Database& db) {
    printHeader("11. DATA QUALITY TESTS");

    for (const auto& customer : db.getCustomers()) {
        if (customer.name.empty()) {
            throw DatabaseError(
                "Customer name must not be empty"
            );
        }

        if (
            customer.email.find('@') ==
            string::npos
        ) {
            throw DatabaseError(
                "Customer email validation failed"
            );
        }
    }

    for (const auto& product : db.getProducts()) {
        if (product.price < 0 || product.stock < 0) {
            throw DatabaseError(
                "Product validation failed"
            );
        }
    }

    for (const auto& order : db.getOrders()) {
        bool customerExists =
            any_of(
                db.getCustomers().begin(),
                db.getCustomers().end(),
                [&](const Customer& customer) {
                    return customer.id ==
                           order.customerId;
                }
            );

        if (!customerExists) {
            throw DatabaseError(
                "Orphaned order detected"
            );
        }
    }

    cout << "PASS: customer validation\n";
    cout << "PASS: product validation\n";
    cout << "PASS: foreign-key validation\n";
}

void demonstrateRealisticWorkflow(Database& db) {
    printHeader("12. REALISTIC ORDER PROCESSING WORKFLOW");

    const int customerId = 1;
    const int productId = 3;
    const int quantity = 2;

    const double price =
        db.getProduct(productId).price;

    const double expectedTotal =
        price * quantity;

    cout << "Customer ID: " << customerId << "\n";
    cout << "Product ID : " << productId << "\n";
    cout << "Quantity   : " << quantity << "\n";
    cout << "Total      : "
         << fixed << setprecision(2)
         << expectedTotal
         << "\n";

    try {
        db.transaction([&]() {
            Product& product =
                db.getProduct(productId);

            if (!product.active) {
                throw ConstraintError(
                    "Product is inactive"
                );
            }

            db.updateStock(productId, quantity);

            const int newOrderId = 50;

            db.insertOrder({
                newOrderId,
                customerId,
                1,
                "2025-08-10T10:00:00",
                "paid"
            });

            db.insertOrderItem({
                50,
                50,
                productId,
                quantity,
                price
            });

            db.insertPayment({
                50,
                50,
                expectedTotal,
                "upi",
                "2025-08-10T10:01:00",
                "completed"
            });
        });

        cout << "Order, stock update and payment committed.\n";
    } catch (const DatabaseError& error) {
        cout << "Workflow failed: "
             << error.what() << "\n";
    }
}

void printFinalCounts(const Database& db) {
    printHeader("13. FINAL DATABASE STATE");

    cout << "Customers   : "
         << db.getCustomers().size() << "\n";

    cout << "Employees   : "
         << db.getEmployees().size() << "\n";

    cout << "Categories  : "
         << db.getCategories().size() << "\n";

    cout << "Products    : "
         << db.getProducts().size() << "\n";

    cout << "Orders      : "
         << db.getOrders().size() << "\n";

    cout << "Order items : "
         << db.getOrderItems().size() << "\n";

    cout << "Payments    : "
         << db.getPayments().size() << "\n";
}

Database seedDatabase() {
    Database db;

    vector<Customer> customers = {
        {1, "Aarav Sharma", "aarav@example.com", "Lucknow", "2025-01-12", "active"},
        {2, "Priya Singh", "priya@example.com", "Delhi", "2025-02-20", "active"},
        {3, "Rohan Verma", "rohan@example.com", "Mumbai", "2025-03-05", "active"},
        {4, "Ananya Gupta", "ananya@example.com", "Lucknow", "2025-03-18", "active"},
        {5, "Kabir Khan", "kabir@example.com", "Bengaluru", "2025-04-02", "inactive"},
        {6, "Meera Joshi", "meera@example.com", "Pune", "2025-04-15", "active"},
        {7, "Vikram Rao", "vikram@example.com", "Hyderabad", "2025-05-11", "blocked"},
        {8, "Ishita Patel", "ishita@example.com", "Ahmedabad", "2025-06-21", "active"}
    };

    for (const auto& customer : customers) {
        db.insertCustomer(customer);
    }

    vector<Employee> employees = {
        {1, "Neha Kapoor", "Sales", 65000},
        {2, "Arjun Mehta", "Operations", 72000},
        {3, "Sana Ali", "Support", 58000}
    };

    for (const auto& employee : employees) {
        db.insertEmployee(employee);
    }

    vector<Category> categories = {
        {1, "Programming"},
        {2, "Data"},
        {3, "Business"},
        {4, "Cloud"}
    };

    for (const auto& category : categories) {
        db.insertCategory(category);
    }

    vector<Product> products = {
        {1, 1, "Python Foundations", 4999, 50, true},
        {2, 1, "Advanced Python", 6999, 40, true},
        {3, 2, "SQL Foundations", 3999, 100, true},
        {4, 2, "Data Analytics", 5999, 60, true},
        {5, 3, "Product Management", 5499, 30, true},
        {6, 3, "Business Metrics", 4499, 25, true},
        {7, 4, "Cloud Fundamentals", 7999, 20, true},
        {8, 4, "DevOps Foundations", 8999, 15, false}
    };

    for (const auto& product : products) {
        db.insertProduct(product);
    }

    vector<Order> orders = {
        {1, 1, 1, "2025-07-01T10:30:00", "paid"},
        {2, 2, 1, "2025-07-02T11:10:00", "shipped"},
        {3, 1, 2, "2025-07-04T09:15:00", "paid"},
        {4, 3, 2, "2025-07-06T15:20:00", "cancelled"},
        {5, 4, 1, "2025-07-10T16:45:00", "shipped"},
        {6, 6, 3, "2025-07-12T13:00:00", "paid"},
        {7, 2, 2, "2025-07-15T12:00:00", "pending"},
        {8, 8, 1, "2025-07-20T17:30:00", "paid"}
    };

    for (const auto& order : orders) {
        db.insertOrder(order);
    }

    vector<OrderItem> items = {
        {1, 1, 3, 1, 3999},
        {2, 1, 1, 1, 4999},
        {3, 2, 4, 1, 5999},
        {4, 2, 6, 2, 4499},
        {5, 3, 2, 1, 6999},
        {6, 3, 3, 2, 3999},
        {7, 4, 7, 1, 7999},
        {8, 5, 5, 1, 5499},
        {9, 5, 3, 1, 3999},
        {10, 6, 1, 1, 4999},
        {11, 6, 4, 1, 5999},
        {12, 7, 7, 1, 7999},
        {13, 8, 2, 1, 6999},
        {14, 8, 5, 1, 5499}
    };

    for (const auto& item : items) {
        db.insertOrderItem(item);
    }

    vector<Payment> payments = {
        {1, 1, 8998, "upi", "2025-07-01T10:31:00", "completed"},
        {2, 2, 14997, "card", "2025-07-02T11:11:00", "completed"},
        {3, 3, 14997, "upi", "2025-07-04T09:16:00", "completed"},
        {4, 4, 7999, "card", "2025-07-06T15:21:00", "refunded"},
        {5, 5, 9498, "upi", "2025-07-10T16:46:00", "completed"},
        {6, 6, 10998, "bank_transfer", "2025-07-12T13:01:00", "completed"},
        {7, 7, 7999, "upi", "", "pending"},
        {8, 8, 12498, "card", "2025-07-20T17:31:00", "completed"}
    };

    for (const auto& payment : payments) {
        db.insertPayment(payment);
    }

    return db;
}

int main() {
    try {
        Database db = seedDatabase();

        printCustomerReport(db);
        printProductReport(db);
        printOrderJoin(db);
        printDetailedOrderLines(db);
        printRevenueByCustomer(db);
        printTopProducts(db);
        demonstrateConstraints(db);
        demonstrateTransactions(db);
        demonstrateIndex(db);
        demonstrateComplexity(db);
        demonstrateDataQuality(db);
        demonstrateRealisticWorkflow(db);
        printFinalCounts(db);

        cout << "\nCase study completed successfully.\n";
        return 0;
    } catch (const exception& error) {
        cerr << "Fatal error: "
             << error.what()
             << "\n";
        return 1;
    }
}
