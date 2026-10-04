#include <algorithm>
#include <exception>
#include <iomanip>
#include <iostream>
#include <map>
#include <optional>
#include <set>
#include <stdexcept>
#include <string>
#include <tuple>
#include <vector>

/*
 * Normalization II: 1NF, 2NF, and 3NF
 *
 * Case study:
 * A warehouse order system initially stores customer, order, and product
 * information in one relation. The system is redesigned using normalization.
 *
 * The C++ model focuses on data-integrity enforcement and explicit relation
 * boundaries rather than reproducing a text-oriented normalization tutorial.
 *
 * Compile:
 *   g++ -std=c++17 -Wall -Wextra -pedantic normalization_ii.cpp -o normalization_ii
 */

struct RawProduct {
    std::string productId;
    std::string productName;
    int quantity;
};

struct RawOrder {
    int orderId;
    std::string orderDate;
    std::string customerId;
    std::string customerName;
    std::string customerCity;
    std::vector<RawProduct> products;
};

struct FirstNFRow {
    int orderId;
    std::string orderDate;
    std::string customerId;
    std::string customerName;
    std::string customerCity;
    std::string productId;
    std::string productName;
    int quantity;
};

struct Order {
    int orderId;
    std::string orderDate;
    std::string customerId;
    std::string customerName;
    std::string customerCity;
};

struct Product {
    std::string productId;
    std::string productName;
};

struct OrderItem {
    int orderId;
    std::string productId;
    int quantity;
};

struct Customer {
    std::string customerId;
    std::string customerName;
    std::string customerCity;
};

void title(const std::string& text) {
    std::cout << "\n" << std::string(78, '=') << "\n";
    std::cout << text << "\n";
    std::cout << std::string(78, '=') << "\n";
}

std::vector<RawOrder> buildRawOrders() {
    return {
        {
            1001,
            "2026-10-01",
            "C001",
            "Asha Rao",
            "Lucknow",
            {
                {"P101", "Keyboard", 2},
                {"P102", "Mouse", 1}
            }
        },
        {
            1002,
            "2026-10-02",
            "C002",
            "Rohan Mehta",
            "Delhi",
            {
                {"P101", "Keyboard", 1}
            }
        }
    };
}

std::vector<FirstNFRow> flattenTo1NF(
    const std::vector<RawOrder>& rawOrders
) {
    std::vector<FirstNFRow> rows;

    for (const auto& order : rawOrders) {
        for (const auto& product : order.products) {
            if (product.quantity <= 0) {
                throw std::invalid_argument(
                    "A first-normal-form row cannot contain a non-positive quantity."
                );
            }

            rows.push_back({
                order.orderId,
                order.orderDate,
                order.customerId,
                order.customerName,
                order.customerCity,
                product.productId,
                product.productName,
                product.quantity
            });
        }
    }

    return rows;
}

using CompositeKey = std::pair<int, std::string>;

void validate1NFKey(const std::vector<FirstNFRow>& rows) {
    std::set<CompositeKey> keys;

    for (const auto& row : rows) {
        CompositeKey key{row.orderId, row.productId};

        if (!keys.insert(key).second) {
            throw std::logic_error(
                "Duplicate (orderId, productId) violates the 1NF relation key."
            );
        }
    }
}

void print1NF(const std::vector<FirstNFRow>& rows) {
    std::cout << std::left
              << std::setw(10) << "Order"
              << std::setw(12) << "Product"
              << std::setw(10) << "Qty"
              << std::setw(18) << "Customer"
              << std::setw(14) << "City"
              << "\n";

    for (const auto& row : rows) {
        std::cout << std::left
                  << std::setw(10) << row.orderId
                  << std::setw(12) << row.productId
                  << std::setw(10) << row.quantity
                  << std::setw(18) << row.customerName
                  << std::setw(14) << row.customerCity
                  << "\n";
    }
}

std::vector<Order> decomposeOrders(
    const std::vector<FirstNFRow>& rows
) {
    std::map<int, Order> byOrder;

    for (const auto& row : rows) {
        auto [it, inserted] = byOrder.emplace(
            row.orderId,
            Order{
                row.orderId,
                row.orderDate,
                row.customerId,
                row.customerName,
                row.customerCity
            }
        );

        if (!inserted) {
            const Order& existing = it->second;

            /*
             * Projection is safe only when the determinant really determines
             * the projected attributes. Contradictory values expose a broken
             * functional dependency instead of being silently discarded.
             */
            if (existing.orderDate != row.orderDate ||
                existing.customerId != row.customerId ||
                existing.customerName != row.customerName ||
                existing.customerCity != row.customerCity) {
                throw std::logic_error(
                    "orderId does not consistently determine order attributes."
                );
            }
        }
    }

    std::vector<Order> result;
    for (const auto& [id, order] : byOrder) {
        result.push_back(order);
    }

    return result;
}

std::vector<Product> decomposeProducts(
    const std::vector<FirstNFRow>& rows
) {
    std::map<std::string, Product> byProduct;

    for (const auto& row : rows) {
        auto [it, inserted] = byProduct.emplace(
            row.productId,
            Product{row.productId, row.productName}
        );

        if (!inserted && it->second.productName != row.productName) {
            throw std::logic_error(
                "productId does not consistently determine productName."
            );
        }
    }

    std::vector<Product> result;
    for (const auto& [id, product] : byProduct) {
        result.push_back(product);
    }

    return result;
}

std::vector<OrderItem> decomposeOrderItems(
    const std::vector<FirstNFRow>& rows
) {
    std::vector<OrderItem> result;

    for (const auto& row : rows) {
        result.push_back({
            row.orderId,
            row.productId,
            row.quantity
        });
    }

    return result;
}

std::vector<Customer> decomposeCustomers(
    const std::vector<Order>& secondNFOrders
) {
    std::map<std::string, Customer> byCustomer;

    for (const auto& order : secondNFOrders) {
        auto [it, inserted] = byCustomer.emplace(
            order.customerId,
            Customer{
                order.customerId,
                order.customerName,
                order.customerCity
            }
        );

        if (!inserted) {
            const Customer& existing = it->second;

            /*
             * This is the key 3NF integrity test. If customerId identifies a
             * customer, all rows carrying that customerId must agree.
             */
            if (existing.customerName != order.customerName ||
                existing.customerCity != order.customerCity) {
                throw std::logic_error(
                    "customerId does not consistently determine customer facts."
                );
            }
        }
    }

    std::vector<Customer> result;
    for (const auto& [id, customer] : byCustomer) {
        result.push_back(customer);
    }

    return result;
}

std::vector<Order> removeCustomerAttributes(
    const std::vector<Order>& secondNFOrders
) {
    std::vector<Order> result;

    for (const auto& order : secondNFOrders) {
        /*
         * Customer attributes are intentionally cleared here because their
         * determinant is customerId rather than orderId. The final design
         * stores those facts only in Customer.
         */
        result.push_back({
            order.orderId,
            order.orderDate,
            order.customerId,
            "",
            ""
        });
    }

    return result;
}

class NormalizedRepository {
private:
    std::map<int, Order> orders;
    std::map<std::string, Customer> customers;
    std::map<std::string, Product> products;
    std::map<CompositeKey, OrderItem> orderItems;

public:
    void addCustomer(const Customer& customer) {
        if (customer.customerId.empty()) {
            throw std::invalid_argument("Customer ID cannot be empty.");
        }

        auto [it, inserted] =
            customers.emplace(customer.customerId, customer);

        if (!inserted) {
            if (it->second.customerName != customer.customerName ||
                it->second.customerCity != customer.customerCity) {
                throw std::logic_error(
                    "Customer key collision with conflicting values."
                );
            }

            throw std::logic_error("Duplicate customer ID.");
        }
    }

    void addProduct(const Product& product) {
        if (product.productId.empty()) {
            throw std::invalid_argument("Product ID cannot be empty.");
        }

        auto [it, inserted] =
            products.emplace(product.productId, product);

        if (!inserted) {
            throw std::logic_error("Duplicate product ID.");
        }
    }

    void addOrder(const Order& order) {
        if (orders.contains(order.orderId)) {
            throw std::logic_error("Duplicate order ID.");
        }

        if (!customers.contains(order.customerId)) {
            throw std::logic_error(
                "Foreign-key violation: customer does not exist."
            );
        }

        orders.emplace(order.orderId, order);
    }

    void addOrderItem(const OrderItem& item) {
        if (item.quantity <= 0) {
            throw std::invalid_argument(
                "Order item quantity must be greater than zero."
            );
        }

        CompositeKey key{item.orderId, item.productId};

        if (orderItems.contains(key)) {
            throw std::logic_error(
                "Duplicate order/product pair violates the OrderItems key."
            );
        }

        if (!orders.contains(item.orderId)) {
            throw std::logic_error(
                "Foreign-key violation: order does not exist."
            );
        }

        if (!products.contains(item.productId)) {
            throw std::logic_error(
                "Foreign-key violation: product does not exist."
            );
        }

        orderItems.emplace(key, item);
    }

    void printBusinessView() const {
        title("RECONSTRUCTED BUSINESS VIEW");

        std::cout << std::left
                  << std::setw(10) << "Order"
                  << std::setw(14) << "Customer"
                  << std::setw(14) << "City"
                  << std::setw(18) << "Product"
                  << std::setw(8) << "Qty"
                  << "\n";

        for (const auto& [key, item] : orderItems) {
            const auto& order = orders.at(item.orderId);
            const auto& customer = customers.at(order.customerId);
            const auto& product = products.at(item.productId);

            std::cout << std::left
                      << std::setw(10) << order.orderId
                      << std::setw(14) << customer.customerName
                      << std::setw(14) << customer.customerCity
                      << std::setw(18) << product.productName
                      << std::setw(8) << item.quantity
                      << "\n";
        }
    }

    void updateCustomerCity(
        const std::string& customerId,
        const std::string& newCity
    ) {
        auto it = customers.find(customerId);

        if (it == customers.end()) {
            throw std::out_of_range("Customer not found.");
        }

        /*
         * Only one tuple changes because customer facts have a single owner.
         * Orders refer to the customer by foreign key rather than duplicating
         * the customer's city.
         */
        it->second.customerCity = newCity;
    }

    void demonstrateCounts() const {
        std::cout << "\nRelation cardinalities after normalization:\n";
        std::cout << "Customers: " << customers.size() << "\n";
        std::cout << "Orders: " << orders.size() << "\n";
        std::cout << "Products: " << products.size() << "\n";
        std::cout << "OrderItems: " << orderItems.size() << "\n";
    }
};

void demonstrate1NF() {
    title("1NF: REMOVE REPEATING GROUPS");

    const auto raw = buildRawOrders();
    const auto rows = flattenTo1NF(raw);

    std::cout
        << "The raw order structure contains a vector of products inside one "
        << "attribute-like field.\n"
        << "Flattening produces one row for each order/product combination.\n\n";

    print1NF(rows);
    validate1NFKey(rows);

    std::cout
        << "\nThe key (orderId, productId) identifies an order line.\n"
        << "Every stored value in the resulting relation is atomic.\n";
}

void demonstrate2NF(
    const std::vector<FirstNFRow>& rows,
    std::vector<Order>& orders,
    std::vector<Product>& products,
    std::vector<OrderItem>& orderItems
) {
    title("2NF: REMOVE PARTIAL DEPENDENCIES");

    std::cout
        << "The 1NF relation has a composite key: (orderId, productId).\n"
        << "orderDate and customerId depend only on orderId.\n"
        << "productName depends only on productId.\n"
        << "quantity depends on the complete composite key.\n";

    orders = decomposeOrders(rows);
    products = decomposeProducts(rows);
    orderItems = decomposeOrderItems(rows);

    std::cout
        << "\nThe decomposition creates independent order, product, and "
        << "order-line relations.\n";
}

void demonstrate3NF(
    const std::vector<Order>& secondNFOrders,
    std::vector<Customer>& customers,
    std::vector<Order>& normalizedOrders
) {
    title("3NF: REMOVE TRANSITIVE DEPENDENCIES");

    std::cout
        << "In the 2NF Orders relation:\n"
        << "  orderId -> customerId\n"
        << "  customerId -> customerName, customerCity\n"
        << "Therefore customerName and customerCity are transitively dependent "
        << "on orderId.\n";

    customers = decomposeCustomers(secondNFOrders);
    normalizedOrders = removeCustomerAttributes(secondNFOrders);

    std::cout
        << "\nCustomer facts are moved to Customer.\n"
        << "Orders retain customerId as the relationship to the customer.\n";
}

void demonstrateAnomalies() {
    title("ANOMALIES ADDRESSED BY THE DESIGN");

    std::cout
        << "Update anomaly: a customer's city is changed in one Customer row "
        << "rather than in every order.\n";

    std::cout
        << "Insertion anomaly: a Product can be created before any order "
        << "references it.\n";

    std::cout
        << "Deletion anomaly: deleting an OrderItem does not remove the "
        << "Product entity itself.\n";
}

void demonstrateFailureCases() {
    title("FAILURE CASES");

    NormalizedRepository repository;

    repository.addCustomer({"C001", "Asha Rao", "Lucknow"});
    repository.addProduct({"P101", "Keyboard"});
    repository.addOrder({1001, "2026-10-01", "C001", "", ""});
    repository.addOrderItem({1001, "P101", 2});

    try {
        repository.addOrderItem({1001, "P101", 3});
    } catch (const std::exception& ex) {
        std::cout << "Duplicate order-line rejected: "
                  << ex.what() << "\n";
    }

    try {
        repository.addOrderItem({1001, "P999", 1});
    } catch (const std::exception& ex) {
        std::cout << "Missing product rejected: "
                  << ex.what() << "\n";
    }

    try {
        repository.addOrderItem({1001, "P101", 0});
    } catch (const std::exception& ex) {
        std::cout << "Invalid quantity rejected: "
                  << ex.what() << "\n";
    }
}

int main() {
    try {
        demonstrate1NF();

        const auto raw = buildRawOrders();
        const auto firstNF = flattenTo1NF(raw);

        std::vector<Order> secondNFOrders;
        std::vector<Product> products;
        std::vector<OrderItem> orderItems;

        demonstrate2NF(
            firstNF,
            secondNFOrders,
            products,
            orderItems
        );

        std::vector<Customer> customers;
        std::vector<Order> normalizedOrders;

        demonstrate3NF(
            secondNFOrders,
            customers,
            normalizedOrders
        );

        NormalizedRepository repository;

        for (const auto& customer : customers) {
            repository.addCustomer(customer);
        }

        for (const auto& product : products) {
            repository.addProduct(product);
        }

        for (const auto& order : normalizedOrders) {
            repository.addOrder(order);
        }

        for (const auto& item : orderItems) {
            repository.addOrderItem(item);
        }

        repository.demonstrateCounts();
        repository.printBusinessView();

        title("SINGLE-OWNER UPDATE");

        repository.updateCustomerCity("C001", "Kanpur");
        std::cout
            << "Customer C001 city updated once in the Customer relation.\n";

        repository.printBusinessView();

        demonstrateAnomalies();
        demonstrateFailureCases();

        title("FINAL DESIGN");
        std::cout << "Customers(customerId, customerName, customerCity)\n";
        std::cout << "Orders(orderId, orderDate, customerId)\n";
        std::cout << "Products(productId, productName)\n";
        std::cout << "OrderItems(orderId, productId, quantity)\n";

    } catch (const std::exception& ex) {
        std::cerr << "Fatal integrity error: " << ex.what() << "\n";
        return 1;
    }

    return 0;
}#include <algorithm>
#include <exception>
#include <iomanip>
#include <iostream>
#include <map>
#include <optional>
#include <set>
#include <stdexcept>
#include <string>
#include <tuple>
#include <vector>

/*
 * Normalization II: 1NF, 2NF, and 3NF
 *
 * Case study:
 * A warehouse order system initially stores customer, order, and product
 * information in one relation. The system is redesigned using normalization.
 *
 * The C++ model focuses on data-integrity enforcement and explicit relation
 * boundaries rather than reproducing a text-oriented normalization tutorial.
 *
 * Compile:
 *   g++ -std=c++17 -Wall -Wextra -pedantic normalization_ii.cpp -o normalization_ii
 */

struct RawProduct {
    std::string productId;
    std::string productName;
    int quantity;
};

struct RawOrder {
    int orderId;
    std::string orderDate;
    std::string customerId;
    std::string customerName;
    std::string customerCity;
    std::vector<RawProduct> products;
};

struct FirstNFRow {
    int orderId;
    std::string orderDate;
    std::string customerId;
    std::string customerName;
    std::string customerCity;
    std::string productId;
    std::string productName;
    int quantity;
};

struct Order {
    int orderId;
    std::string orderDate;
    std::string customerId;
    std::string customerName;
    std::string customerCity;
};

struct Product {
    std::string productId;
    std::string productName;
};

struct OrderItem {
    int orderId;
    std::string productId;
    int quantity;
};

struct Customer {
    std::string customerId;
    std::string customerName;
    std::string customerCity;
};

void title(const std::string& text) {
    std::cout << "\n" << std::string(78, '=') << "\n";
    std::cout << text << "\n";
    std::cout << std::string(78, '=') << "\n";
}

std::vector<RawOrder> buildRawOrders() {
    return {
        {
            1001,
            "2026-10-01",
            "C001",
            "Asha Rao",
            "Lucknow",
            {
                {"P101", "Keyboard", 2},
                {"P102", "Mouse", 1}
            }
        },
        {
            1002,
            "2026-10-02",
            "C002",
            "Rohan Mehta",
            "Delhi",
            {
                {"P101", "Keyboard", 1}
            }
        }
    };
}

std::vector<FirstNFRow> flattenTo1NF(
    const std::vector<RawOrder>& rawOrders
) {
    std::vector<FirstNFRow> rows;

    for (const auto& order : rawOrders) {
        for (const auto& product : order.products) {
            if (product.quantity <= 0) {
                throw std::invalid_argument(
                    "A first-normal-form row cannot contain a non-positive quantity."
                );
            }

            rows.push_back({
                order.orderId,
                order.orderDate,
                order.customerId,
                order.customerName,
                order.customerCity,
                product.productId,
                product.productName,
                product.quantity
            });
        }
    }

    return rows;
}

using CompositeKey = std::pair<int, std::string>;

void validate1NFKey(const std::vector<FirstNFRow>& rows) {
    std::set<CompositeKey> keys;

    for (const auto& row : rows) {
        CompositeKey key{row.orderId, row.productId};

        if (!keys.insert(key).second) {
            throw std::logic_error(
                "Duplicate (orderId, productId) violates the 1NF relation key."
            );
        }
    }
}

void print1NF(const std::vector<FirstNFRow>& rows) {
    std::cout << std::left
              << std::setw(10) << "Order"
              << std::setw(12) << "Product"
              << std::setw(10) << "Qty"
              << std::setw(18) << "Customer"
              << std::setw(14) << "City"
              << "\n";

    for (const auto& row : rows) {
        std::cout << std::left
                  << std::setw(10) << row.orderId
                  << std::setw(12) << row.productId
                  << std::setw(10) << row.quantity
                  << std::setw(18) << row.customerName
                  << std::setw(14) << row.customerCity
                  << "\n";
    }
}

std::vector<Order> decomposeOrders(
    const std::vector<FirstNFRow>& rows
) {
    std::map<int, Order> byOrder;

    for (const auto& row : rows) {
        auto [it, inserted] = byOrder.emplace(
            row.orderId,
            Order{
                row.orderId,
                row.orderDate,
                row.customerId,
                row.customerName,
                row.customerCity
            }
        );

        if (!inserted) {
            const Order& existing = it->second;

            /*
             * Projection is safe only when the determinant really determines
             * the projected attributes. Contradictory values expose a broken
             * functional dependency instead of being silently discarded.
             */
            if (existing.orderDate != row.orderDate ||
                existing.customerId != row.customerId ||
                existing.customerName != row.customerName ||
                existing.customerCity != row.customerCity) {
                throw std::logic_error(
                    "orderId does not consistently determine order attributes."
                );
            }
        }
    }

    std::vector<Order> result;
    for (const auto& [id, order] : byOrder) {
        result.push_back(order);
    }

    return result;
}

std::vector<Product> decomposeProducts(
    const std::vector<FirstNFRow>& rows
) {
    std::map<std::string, Product> byProduct;

    for (const auto& row : rows) {
        auto [it, inserted] = byProduct.emplace(
            row.productId,
            Product{row.productId, row.productName}
        );

        if (!inserted && it->second.productName != row.productName) {
            throw std::logic_error(
                "productId does not consistently determine productName."
            );
        }
    }

    std::vector<Product> result;
    for (const auto& [id, product] : byProduct) {
        result.push_back(product);
    }

    return result;
}

std::vector<OrderItem> decomposeOrderItems(
    const std::vector<FirstNFRow>& rows
) {
    std::vector<OrderItem> result;

    for (const auto& row : rows) {
        result.push_back({
            row.orderId,
            row.productId,
            row.quantity
        });
    }

    return result;
}

std::vector<Customer> decomposeCustomers(
    const std::vector<Order>& secondNFOrders
) {
    std::map<std::string, Customer> byCustomer;

    for (const auto& order : secondNFOrders) {
        auto [it, inserted] = byCustomer.emplace(
            order.customerId,
            Customer{
                order.customerId,
                order.customerName,
                order.customerCity
            }
        );

        if (!inserted) {
            const Customer& existing = it->second;

            /*
             * This is the key 3NF integrity test. If customerId identifies a
             * customer, all rows carrying that customerId must agree.
             */
            if (existing.customerName != order.customerName ||
                existing.customerCity != order.customerCity) {
                throw std::logic_error(
                    "customerId does not consistently determine customer facts."
                );
            }
        }
    }

    std::vector<Customer> result;
    for (const auto& [id, customer] : byCustomer) {
        result.push_back(customer);
    }

    return result;
}

std::vector<Order> removeCustomerAttributes(
    const std::vector<Order>& secondNFOrders
) {
    std::vector<Order> result;

    for (const auto& order : secondNFOrders) {
        /*
         * Customer attributes are intentionally cleared here because their
         * determinant is customerId rather than orderId. The final design
         * stores those facts only in Customer.
         */
        result.push_back({
            order.orderId,
            order.orderDate,
            order.customerId,
            "",
            ""
        });
    }

    return result;
}

class NormalizedRepository {
private:
    std::map<int, Order> orders;
    std::map<std::string, Customer> customers;
    std::map<std::string, Product> products;
    std::map<CompositeKey, OrderItem> orderItems;

public:
    void addCustomer(const Customer& customer) {
        if (customer.customerId.empty()) {
            throw std::invalid_argument("Customer ID cannot be empty.");
        }

        auto [it, inserted] =
            customers.emplace(customer.customerId, customer);

        if (!inserted) {
            if (it->second.customerName != customer.customerName ||
                it->second.customerCity != customer.customerCity) {
                throw std::logic_error(
                    "Customer key collision with conflicting values."
                );
            }

            throw std::logic_error("Duplicate customer ID.");
        }
    }

    void addProduct(const Product& product) {
        if (product.productId.empty()) {
            throw std::invalid_argument("Product ID cannot be empty.");
        }

        auto [it, inserted] =
            products.emplace(product.productId, product);

        if (!inserted) {
            throw std::logic_error("Duplicate product ID.");
        }
    }

    void addOrder(const Order& order) {
        if (orders.contains(order.orderId)) {
            throw std::logic_error("Duplicate order ID.");
        }

        if (!customers.contains(order.customerId)) {
            throw std::logic_error(
                "Foreign-key violation: customer does not exist."
            );
        }

        orders.emplace(order.orderId, order);
    }

    void addOrderItem(const OrderItem& item) {
        if (item.quantity <= 0) {
            throw std::invalid_argument(
                "Order item quantity must be greater than zero."
            );
        }

        CompositeKey key{item.orderId, item.productId};

        if (orderItems.contains(key)) {
            throw std::logic_error(
                "Duplicate order/product pair violates the OrderItems key."
            );
        }

        if (!orders.contains(item.orderId)) {
            throw std::logic_error(
                "Foreign-key violation: order does not exist."
            );
        }

        if (!products.contains(item.productId)) {
            throw std::logic_error(
                "Foreign-key violation: product does not exist."
            );
        }

        orderItems.emplace(key, item);
    }

    void printBusinessView() const {
        title("RECONSTRUCTED BUSINESS VIEW");

        std::cout << std::left
                  << std::setw(10) << "Order"
                  << std::setw(14) << "Customer"
                  << std::setw(14) << "City"
                  << std::setw(18) << "Product"
                  << std::setw(8) << "Qty"
                  << "\n";

        for (const auto& [key, item] : orderItems) {
            const auto& order = orders.at(item.orderId);
            const auto& customer = customers.at(order.customerId);
            const auto& product = products.at(item.productId);

            std::cout << std::left
                      << std::setw(10) << order.orderId
                      << std::setw(14) << customer.customerName
                      << std::setw(14) << customer.customerCity
                      << std::setw(18) << product.productName
                      << std::setw(8) << item.quantity
                      << "\n";
        }
    }

    void updateCustomerCity(
        const std::string& customerId,
        const std::string& newCity
    ) {
        auto it = customers.find(customerId);

        if (it == customers.end()) {
            throw std::out_of_range("Customer not found.");
        }

        /*
         * Only one tuple changes because customer facts have a single owner.
         * Orders refer to the customer by foreign key rather than duplicating
         * the customer's city.
         */
        it->second.customerCity = newCity;
    }

    void demonstrateCounts() const {
        std::cout << "\nRelation cardinalities after normalization:\n";
        std::cout << "Customers: " << customers.size() << "\n";
        std::cout << "Orders: " << orders.size() << "\n";
        std::cout << "Products: " << products.size() << "\n";
        std::cout << "OrderItems: " << orderItems.size() << "\n";
    }
};

void demonstrate1NF() {
    title("1NF: REMOVE REPEATING GROUPS");

    const auto raw = buildRawOrders();
    const auto rows = flattenTo1NF(raw);

    std::cout
        << "The raw order structure contains a vector of products inside one "
        << "attribute-like field.\n"
        << "Flattening produces one row for each order/product combination.\n\n";

    print1NF(rows);
    validate1NFKey(rows);

    std::cout
        << "\nThe key (orderId, productId) identifies an order line.\n"
        << "Every stored value in the resulting relation is atomic.\n";
}

void demonstrate2NF(
    const std::vector<FirstNFRow>& rows,
    std::vector<Order>& orders,
    std::vector<Product>& products,
    std::vector<OrderItem>& orderItems
) {
    title("2NF: REMOVE PARTIAL DEPENDENCIES");

    std::cout
        << "The 1NF relation has a composite key: (orderId, productId).\n"
        << "orderDate and customerId depend only on orderId.\n"
        << "productName depends only on productId.\n"
        << "quantity depends on the complete composite key.\n";

    orders = decomposeOrders(rows);
    products = decomposeProducts(rows);
    orderItems = decomposeOrderItems(rows);

    std::cout
        << "\nThe decomposition creates independent order, product, and "
        << "order-line relations.\n";
}

void demonstrate3NF(
    const std::vector<Order>& secondNFOrders,
    std::vector<Customer>& customers,
    std::vector<Order>& normalizedOrders
) {
    title("3NF: REMOVE TRANSITIVE DEPENDENCIES");

    std::cout
        << "In the 2NF Orders relation:\n"
        << "  orderId -> customerId\n"
        << "  customerId -> customerName, customerCity\n"
        << "Therefore customerName and customerCity are transitively dependent "
        << "on orderId.\n";

    customers = decomposeCustomers(secondNFOrders);
    normalizedOrders = removeCustomerAttributes(secondNFOrders);

    std::cout
        << "\nCustomer facts are moved to Customer.\n"
        << "Orders retain customerId as the relationship to the customer.\n";
}

void demonstrateAnomalies() {
    title("ANOMALIES ADDRESSED BY THE DESIGN");

    std::cout
        << "Update anomaly: a customer's city is changed in one Customer row "
        << "rather than in every order.\n";

    std::cout
        << "Insertion anomaly: a Product can be created before any order "
        << "references it.\n";

    std::cout
        << "Deletion anomaly: deleting an OrderItem does not remove the "
        << "Product entity itself.\n";
}

void demonstrateFailureCases() {
    title("FAILURE CASES");

    NormalizedRepository repository;

    repository.addCustomer({"C001", "Asha Rao", "Lucknow"});
    repository.addProduct({"P101", "Keyboard"});
    repository.addOrder({1001, "2026-10-01", "C001", "", ""});
    repository.addOrderItem({1001, "P101", 2});

    try {
        repository.addOrderItem({1001, "P101", 3});
    } catch (const std::exception& ex) {
        std::cout << "Duplicate order-line rejected: "
                  << ex.what() << "\n";
    }

    try {
        repository.addOrderItem({1001, "P999", 1});
    } catch (const std::exception& ex) {
        std::cout << "Missing product rejected: "
                  << ex.what() << "\n";
    }

    try {
        repository.addOrderItem({1001, "P101", 0});
    } catch (const std::exception& ex) {
        std::cout << "Invalid quantity rejected: "
                  << ex.what() << "\n";
    }
}

int main() {
    try {
        demonstrate1NF();

        const auto raw = buildRawOrders();
        const auto firstNF = flattenTo1NF(raw);

        std::vector<Order> secondNFOrders;
        std::vector<Product> products;
        std::vector<OrderItem> orderItems;

        demonstrate2NF(
            firstNF,
            secondNFOrders,
            products,
            orderItems
        );

        std::vector<Customer> customers;
        std::vector<Order> normalizedOrders;

        demonstrate3NF(
            secondNFOrders,
            customers,
            normalizedOrders
        );

        NormalizedRepository repository;

        for (const auto& customer : customers) {
            repository.addCustomer(customer);
        }

        for (const auto& product : products) {
            repository.addProduct(product);
        }

        for (const auto& order : normalizedOrders) {
            repository.addOrder(order);
        }

        for (const auto& item : orderItems) {
            repository.addOrderItem(item);
        }

        repository.demonstrateCounts();
        repository.printBusinessView();

        title("SINGLE-OWNER UPDATE");

        repository.updateCustomerCity("C001", "Kanpur");
        std::cout
            << "Customer C001 city updated once in the Customer relation.\n";

        repository.printBusinessView();

        demonstrateAnomalies();
        demonstrateFailureCases();

        title("FINAL DESIGN");
        std::cout << "Customers(customerId, customerName, customerCity)\n";
        std::cout << "Orders(orderId, orderDate, customerId)\n";
        std::cout << "Products(productId, productName)\n";
        std::cout << "OrderItems(orderId, productId, quantity)\n";

    } catch (const std::exception& ex) {
        std::cerr << "Fatal integrity error: " << ex.what() << "\n";
        return 1;
    }

    return 0;
}
