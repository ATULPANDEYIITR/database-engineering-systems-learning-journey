/*
 * CASE Expressions in SQL
 * =======================
 *
 * C++17 technical case study:
 * A transaction risk and operations classification engine.
 *
 * The program models the same kinds of business transformations commonly
 * expressed with SQL CASE expressions. It uses the C++ standard library only.
 *
 * The case study demonstrates:
 * - Simple CASE-style mappings
 * - Searched CASE-style conditions
 * - Rule precedence
 * - NULL-like optional values
 * - Customer risk classification
 * - Transaction classification
 * - Conditional calculations
 * - Conditional aggregation
 * - Custom priority ordering
 * - Data validation
 * - Reporting
 * - Boundary testing
 * - Complexity analysis
 * - Separation of rule logic from reporting
 *
 * Compile:
 *     g++ -std=c++17 -O2 case_expressions.cpp -o case_expressions
 *
 * Run:
 *     ./case_expressions
 */

#include <algorithm>
#include <cassert>
#include <iomanip>
#include <iostream>
#include <limits>
#include <map>
#include <optional>
#include <sstream>
#include <string>
#include <tuple>
#include <unordered_map>
#include <utility>
#include <vector>

using namespace std;

/* -------------------------------------------------------------------------
 * Domain models
 * ------------------------------------------------------------------------- */

struct Customer {
    int id;
    string name;
    optional<string> country;
    optional<double> annualIncome;
    optional<int> creditScore;
    string status;
};

struct Transaction {
    int id;
    int customerId;
    double amount;
    string paymentStatus;
    int shippingDays;
};

struct ClassifiedTransaction {
    int transactionId;
    int customerId;
    double amount;
    string paymentStatus;
    string sizeCategory;
    string shippingCategory;
    string riskCategory;
    double serviceFee;
};

struct CustomerReport {
    int customerId;
    string customerName;
    string riskCategory;
    double paidRevenue;
    int paidOrders;
    int pendingOrders;
    string operationalAction;
};

/* -------------------------------------------------------------------------
 * Formatting helpers
 * ------------------------------------------------------------------------- */

void printTitle(const string& title) {
    cout << "\n" << string(90, '=') << "\n";
    cout << title << "\n";
    cout << string(90, '=') << "\n";
}

string formatMoney(double value) {
    ostringstream stream;
    stream << fixed << setprecision(2) << value;
    return stream.str();
}

/* -------------------------------------------------------------------------
 * SQL CASE concepts represented as C++ rule functions
 * ------------------------------------------------------------------------- */

/*
 * SQL simple CASE:
 *
 * CASE payment_status
 *     WHEN 'paid' THEN 'Payment complete'
 *     WHEN 'pending' THEN 'Awaiting payment'
 *     ELSE 'Unknown status'
 * END
 *
 * A switch statement provides a similar discrete-value mapping in C++.
 */
string describePaymentStatus(const string& status) {
    if (status == "paid") {
        return "Payment complete";
    }

    if (status == "pending") {
        return "Awaiting payment";
    }

    if (status == "cancelled") {
        return "Order cancelled";
    }

    if (status == "refunded") {
        return "Money returned";
    }

    return "Unknown status";
}

/*
 * SQL searched CASE:
 *
 * CASE
 *     WHEN amount < 1000 THEN 'Small'
 *     WHEN amount < 5000 THEN 'Medium'
 *     WHEN amount < 20000 THEN 'Large'
 *     ELSE 'Enterprise'
 * END
 *
 * The order of conditions is significant.
 */
string classifyAmount(double amount) {
    if (amount < 1000.0) {
        return "Small";
    }

    if (amount < 5000.0) {
        return "Medium";
    }

    if (amount < 20000.0) {
        return "Large";
    }

    return "Enterprise";
}

/*
 * A CASE expression can return a number as well as text.
 */
double calculateServiceFee(const Transaction& transaction) {
    if (
        transaction.paymentStatus == "cancelled" ||
        transaction.paymentStatus == "refunded"
    ) {
        return 0.0;
    }

    if (transaction.amount >= 50000.0) {
        return transaction.amount * 0.005;
    }

    if (transaction.amount >= 10000.0) {
        return transaction.amount * 0.01;
    }

    return transaction.amount * 0.02;
}

/*
 * CASE can combine independent dimensions of a business rule.
 */
string classifyShipping(const Transaction& transaction) {
    if (
        transaction.paymentStatus == "cancelled" ||
        transaction.shippingDays == 0
    ) {
        return "Not shipped";
    }

    if (transaction.shippingDays <= 3) {
        return "Express";
    }

    if (transaction.shippingDays <= 7) {
        return "Standard";
    }

    return "Delayed";
}

/* -------------------------------------------------------------------------
 * Customer risk classification
 * ------------------------------------------------------------------------- */

string classifyCustomerRisk(const Customer& customer) {
    /*
     * optional<T> models the possibility of SQL NULL.
     *
     * SQL equivalent:
     *
     * CASE
     *     WHEN annual_income IS NULL OR credit_score IS NULL
     *         THEN 'UNKNOWN'
     *     WHEN credit_score < 600
     *         THEN 'HIGH'
     *     WHEN credit_score < 700
     *         THEN 'MEDIUM'
     *     WHEN annual_income >= 150000
     *         THEN 'LOW'
     *     ELSE 'LOW'
     * END
     */

    if (
        !customer.annualIncome.has_value() ||
        !customer.creditScore.has_value()
    ) {
        return "UNKNOWN";
    }

    if (*customer.creditScore < 600) {
        return "HIGH";
    }

    if (*customer.creditScore < 700) {
        return "MEDIUM";
    }

    if (*customer.annualIncome >= 150000.0) {
        return "LOW";
    }

    return "LOW";
}

/* -------------------------------------------------------------------------
 * Business rule engine
 * ------------------------------------------------------------------------- */

class TransactionRuleEngine {
public:
    ClassifiedTransaction classify(
        const Transaction& transaction,
        const Customer& customer
    ) const {
        ClassifiedTransaction result;

        result.transactionId = transaction.id;
        result.customerId = transaction.customerId;
        result.amount = transaction.amount;
        result.paymentStatus = transaction.paymentStatus;

        result.sizeCategory = classifyAmount(transaction.amount);
        result.shippingCategory = classifyShipping(transaction);
        result.riskCategory = classifyCustomerRisk(customer);
        result.serviceFee = calculateServiceFee(transaction);

        return result;
    }

    string determineOperationalAction(
        const string& riskCategory,
        double paidRevenue
    ) const {
        /*
         * This function represents a later CASE expression that consumes
         * another derived CASE result.
         *
         * SQL pattern:
         *
         * CASE
         *     WHEN risk = 'HIGH' THEN 'Manual review'
         *     WHEN risk = 'MEDIUM' AND revenue >= 5000
         *         THEN 'Enhanced monitoring'
         *     WHEN risk = 'UNKNOWN'
         *         THEN 'Collect missing information'
         *     ELSE 'Standard monitoring'
         * END
         */

        if (riskCategory == "HIGH") {
            return "Manual review";
        }

        if (
            riskCategory == "MEDIUM" &&
            paidRevenue >= 5000.0
        ) {
            return "Enhanced monitoring";
        }

        if (riskCategory == "UNKNOWN") {
            return "Collect missing information";
        }

        return "Standard monitoring";
    }
};

/* -------------------------------------------------------------------------
 * Data validation
 * ------------------------------------------------------------------------- */

string validateCustomer(const Customer& customer) {
    if (
        !customer.annualIncome.has_value() &&
        !customer.creditScore.has_value()
    ) {
        return "Missing income and credit score";
    }

    if (!customer.annualIncome.has_value()) {
        return "Missing income";
    }

    if (!customer.creditScore.has_value()) {
        return "Missing credit score";
    }

    if (*customer.annualIncome < 0.0) {
        return "Invalid negative income";
    }

    if (
        *customer.creditScore < 300 ||
        *customer.creditScore > 850
    ) {
        return "Invalid credit score";
    }

    return "Valid";
}

/* -------------------------------------------------------------------------
 * Lookup support
 * ------------------------------------------------------------------------- */

unordered_map<int, Customer> indexCustomers(
    const vector<Customer>& customers
) {
    unordered_map<int, Customer> index;

    for (const auto& customer : customers) {
        index.emplace(customer.id, customer);
    }

    return index;
}

/* -------------------------------------------------------------------------
 * Reporting
 * ------------------------------------------------------------------------- */

vector<CustomerReport> buildCustomerReports(
    const vector<Customer>& customers,
    const vector<Transaction>& transactions,
    const TransactionRuleEngine& engine
) {
    struct Aggregates {
        double paidRevenue = 0.0;
        int paidOrders = 0;
        int pendingOrders = 0;
    };

    unordered_map<int, Aggregates> aggregates;

    /*
     * Conditional aggregation:
     *
     * SUM(CASE WHEN payment_status = 'paid' THEN amount ELSE 0 END)
     *
     * COUNT(CASE WHEN payment_status = 'paid' THEN 1 END)
     *
     * The C++ equivalent below updates only the matching category.
     */
    for (const auto& transaction : transactions) {
        auto& aggregate = aggregates[transaction.customerId];

        if (transaction.paymentStatus == "paid") {
            aggregate.paidRevenue += transaction.amount;
            ++aggregate.paidOrders;
        }

        if (transaction.paymentStatus == "pending") {
            ++aggregate.pendingOrders;
        }
    }

    const auto customerIndex = indexCustomers(customers);
    vector<CustomerReport> reports;

    for (const auto& customer : customers) {
        const auto aggregateIt = aggregates.find(customer.id);

        Aggregates aggregate;

        if (aggregateIt != aggregates.end()) {
            aggregate = aggregateIt->second;
        }

        CustomerReport report;
        report.customerId = customer.id;
        report.customerName = customer.name;
        report.riskCategory = classifyCustomerRisk(customer);
        report.paidRevenue = aggregate.paidRevenue;
        report.paidOrders = aggregate.paidOrders;
        report.pendingOrders = aggregate.pendingOrders;

        report.operationalAction =
            engine.determineOperationalAction(
                report.riskCategory,
                report.paidRevenue
            );

        reports.push_back(report);
    }

    return reports;
}

void printCustomerReports(
    const vector<CustomerReport>& reports
) {
    printTitle("Customer operational report");

    cout
        << left
        << setw(8) << "ID"
        << setw(14) << "Customer"
        << setw(10) << "Risk"
        << setw(15) << "Paid Revenue"
        << setw(12) << "Paid Orders"
        << setw(15) << "Pending"
        << "Action\n";

    cout << string(90, '-') << "\n";

    for (const auto& report : reports) {
        cout
            << left
            << setw(8) << report.customerId
            << setw(14) << report.customerName
            << setw(10) << report.riskCategory
            << setw(15) << formatMoney(report.paidRevenue)
            << setw(12) << report.paidOrders
            << setw(15) << report.pendingOrders
            << report.operationalAction
            << "\n";
    }
}

/* -------------------------------------------------------------------------
 * Transaction report
 * ------------------------------------------------------------------------- */

void printTransactionReports(
    const vector<ClassifiedTransaction>& reports
) {
    printTitle("Transaction classification report");

    cout
        << left
        << setw(8) << "ID"
        << setw(10) << "Customer"
        << setw(13) << "Amount"
        << setw(12) << "Payment"
        << setw(13) << "Size"
        << setw(13) << "Shipping"
        << setw(10) << "Risk"
        << "Fee\n";

    cout << string(90, '-') << "\n";

    for (const auto& report : reports) {
        cout
            << left
            << setw(8) << report.transactionId
            << setw(10) << report.customerId
            << setw(13) << formatMoney(report.amount)
            << setw(12) << report.paymentStatus
            << setw(13) << report.sizeCategory
            << setw(13) << report.shippingCategory
            << setw(10) << report.riskCategory
            << formatMoney(report.serviceFee)
            << "\n";
    }
}

/* -------------------------------------------------------------------------
 * Custom ordering
 * ------------------------------------------------------------------------- */

int riskPriority(const string& risk) {
    /*
     * Equivalent SQL:
     *
     * ORDER BY CASE risk
     *     WHEN 'HIGH' THEN 1
     *     WHEN 'MEDIUM' THEN 2
     *     WHEN 'UNKNOWN' THEN 3
     *     ELSE 4
     * END
     */
    if (risk == "HIGH") {
        return 1;
    }

    if (risk == "MEDIUM") {
        return 2;
    }

    if (risk == "UNKNOWN") {
        return 3;
    }

    return 4;
}

void sortReportsByRisk(
    vector<CustomerReport>& reports
) {
    sort(
        reports.begin(),
        reports.end(),
        [](const CustomerReport& first, const CustomerReport& second) {
            const int firstPriority = riskPriority(first.riskCategory);
            const int secondPriority = riskPriority(second.riskCategory);

            if (firstPriority != secondPriority) {
                return firstPriority < secondPriority;
            }

            return first.paidRevenue > second.paidRevenue;
        }
    );
}

/* -------------------------------------------------------------------------
 * Conditional pivot-style report
 * ------------------------------------------------------------------------- */

struct PaymentPivot {
    double paid = 0.0;
    double pending = 0.0;
    double cancelled = 0.0;
    double refunded = 0.0;
};

unordered_map<int, PaymentPivot> buildPaymentPivot(
    const vector<Transaction>& transactions
) {
    unordered_map<int, PaymentPivot> result;

    /*
     * SQL CASE plus aggregation can simulate many pivot reports:
     *
     * SUM(CASE WHEN payment_status = 'paid' THEN amount ELSE 0 END)
     *
     * This avoids relying on a database-specific PIVOT operator.
     */
    for (const auto& transaction : transactions) {
        auto& pivot = result[transaction.customerId];

        if (transaction.paymentStatus == "paid") {
            pivot.paid += transaction.amount;
        } else if (transaction.paymentStatus == "pending") {
            pivot.pending += transaction.amount;
        } else if (transaction.paymentStatus == "cancelled") {
            pivot.cancelled += transaction.amount;
        } else if (transaction.paymentStatus == "refunded") {
            pivot.refunded += transaction.amount;
        }
    }

    return result;
}

void printPaymentPivot(
    const unordered_map<int, PaymentPivot>& pivot
) {
    printTitle("CASE-based payment pivot");

    cout
        << left
        << setw(10) << "Customer"
        << setw(15) << "Paid"
        << setw(15) << "Pending"
        << setw(15) << "Cancelled"
        << "Refunded\n";

    cout << string(70, '-') << "\n";

    vector<int> customerIds;

    for (const auto& entry : pivot) {
        customerIds.push_back(entry.first);
    }

    sort(customerIds.begin(), customerIds.end());

    for (int customerId : customerIds) {
        const auto& values = pivot.at(customerId);

        cout
            << left
            << setw(10) << customerId
            << setw(15) << formatMoney(values.paid)
            << setw(15) << formatMoney(values.pending)
            << setw(15) << formatMoney(values.cancelled)
            << formatMoney(values.refunded)
            << "\n";
    }
}

/* -------------------------------------------------------------------------
 * Boundary tests
 * ------------------------------------------------------------------------- */

void testAmountClassification() {
    printTitle("Boundary tests for amount classification");

    struct TestCase {
        double input;
        string expected;
    };

    const vector<TestCase> tests = {
        {0.0, "Small"},
        {999.99, "Small"},
        {1000.0, "Medium"},
        {4999.99, "Medium"},
        {5000.0, "Large"},
        {19999.99, "Large"},
        {20000.0, "Enterprise"},
        {1000000.0, "Enterprise"}
    };

    int passed = 0;

    for (const auto& test : tests) {
        const string actual = classifyAmount(test.input);
        const bool success = actual == test.expected;

        cout
            << (success ? "PASS" : "FAIL")
            << " amount=" << test.input
            << " expected=" << test.expected
            << " actual=" << actual
            << "\n";

        if (success) {
            ++passed;
        }
    }

    cout << "Passed " << passed << "/" << tests.size() << " tests.\n";

    assert(passed == static_cast<int>(tests.size()));
}

/* -------------------------------------------------------------------------
 * Edge cases
 * ------------------------------------------------------------------------- */

void demonstrateEdgeCases() {
    printTitle("Edge cases");

    const vector<double> values = {
        -500.0,
        0.0,
        999.999,
        1000.0,
        4999.999,
        5000.0,
        19999.999,
        20000.0
    };

    for (double value : values) {
        cout
            << "Amount "
            << setw(10)
            << value
            << " -> "
            << classifyAmount(value)
            << "\n";
    }

    cout << R"(
Important observations:

- Negative values do not automatically become invalid. Whether they are
  invalid depends on the business rule.
- Exact boundary values belong to the first matching condition.
- Floating-point values require care when exact financial equality matters.
- A missing value must be represented explicitly when the business rule
  distinguishes "unknown" from zero.
)";
}

/* -------------------------------------------------------------------------
 * Rule-ordering demonstration
 * ------------------------------------------------------------------------- */

void demonstrateRulePrecedence() {
    printTitle("Rule precedence");

    const double amount = 8000.0;

    /*
     * This intentionally demonstrates an incorrectly ordered rule.
     *
     * In SQL:
     *
     * CASE
     *     WHEN amount >= 1000 THEN 'At least 1,000'
     *     WHEN amount >= 5000 THEN 'At least 5,000'
     * END
     *
     * The second condition becomes unreachable for values >= 5000.
     */
    string incorrectResult;

    if (amount >= 1000.0) {
        incorrectResult = "At least 1,000";
    } else if (amount >= 5000.0) {
        incorrectResult = "At least 5,000";
    } else {
        incorrectResult = "Below 1,000";
    }

    cout
        << "Incorrect ordering for 8000: "
        << incorrectResult
        << "\n";

    cout << R"(
Correct ordering places the narrower condition first:

    if amount >= 5000
        ...
    else if amount >= 1000
        ...

CASE evaluates ordered rules. It is therefore important to review
overlapping conditions as a rule hierarchy.
)";
}

/* -------------------------------------------------------------------------
 * Complexity discussion
 * ------------------------------------------------------------------------- */

void printComplexityDiscussion() {
    printTitle("Complexity and implementation considerations");

    cout << R"(
For a CASE expression with k WHEN conditions, evaluating one row has a
worst-case rule-checking cost of O(k). In a query over n rows, the expression
can therefore perform up to O(n*k) condition checks.

For practical SQL workloads, the total query cost is often dominated by:

- table scans
- joins
- sorting
- grouping
- window functions
- data volume
- disk and memory access
- network transfer

The C++ case study indexes customers by customer ID using unordered_map.
Customer lookup is expected O(1), while constructing a report is O(n) for
the transaction pass plus O(m) for the customer pass, where n is the number
of transactions and m is the number of customers.

Sorting the final customer report adds O(m log m).

A large CASE expression can be computationally acceptable while still being
a maintenance problem. Performance and maintainability are separate design
questions.
)";
}

/* -------------------------------------------------------------------------
 * Security discussion
 * ------------------------------------------------------------------------- */

void printSecurityDiscussion() {
    printTitle("Security considerations");

    cout << R"(
CASE is a transformation mechanism, not an authorization mechanism.

A query that returns:

    CASE
        WHEN ...
            THEN 'Allowed'
        ELSE 'Denied'
    END

does not automatically prevent unauthorized rows from being returned.

Security should be enforced through appropriate authentication,
authorization, database permissions, row-level security, application
controls, or other explicit mechanisms.

For SQL applications:

1. Use parameterized queries for user-provided values.
2. Do not concatenate untrusted input into SQL.
3. Validate dynamic identifiers when dynamic SQL is genuinely required.
4. Treat business classifications as potentially sensitive.
5. Test unexpected NULL and invalid data.
6. Audit changes to high-impact rules.
7. Separate display classification from authorization decisions.
)";
}

/* -------------------------------------------------------------------------
 * SQL reference output
 * ------------------------------------------------------------------------- */

void printSQLReference() {
    printTitle("SQL CASE reference");

    cout << R"(
Simple CASE:

CASE expression
    WHEN value1 THEN result1
    WHEN value2 THEN result2
    ELSE result
END

Searched CASE:

CASE
    WHEN condition1 THEN result1
    WHEN condition2 THEN result2
    ELSE result
END

Conditional aggregation:

SUM(
    CASE
        WHEN condition THEN amount
        ELSE 0
    END
)

Conditional counting:

SUM(
    CASE
        WHEN condition THEN 1
        ELSE 0
    END
)

Custom ordering:

ORDER BY
    CASE status
        WHEN 'pending' THEN 1
        WHEN 'paid' THEN 2
        ELSE 3
    END

The C++ implementation mirrors these transformations as explicit functions.
This makes the business rules visible, testable, and independent of any
specific database driver.
)";
}

/* -------------------------------------------------------------------------
 * Main
 * ------------------------------------------------------------------------- */

int main() {
    const vector<Customer> customers = {
        {
            1,
            "Aarav",
            string("India"),
            45000.0,
            610,
            "active"
        },
        {
            2,
            "Meera",
            string("India"),
            125000.0,
            790,
            "active"
        },
        {
            3,
            "Daniel",
            string("USA"),
            95000.0,
            720,
            "active"
        },
        {
            4,
            "Sophia",
            string("UK"),
            38000.0,
            580,
            "inactive"
        },
        {
            5,
            "Noah",
            nullopt,
            nullopt,
            nullopt,
            "prospect"
        }
    };

    const vector<Transaction> transactions = {
        {101, 1, 450.0, "paid", 3},
        {102, 1, 1200.0, "paid", 5},
        {103, 2, 8500.0, "paid", 2},
        {104, 2, 2200.0, "pending", 8},
        {105, 3, 5000.0, "paid", 4},
        {106, 3, 18000.0, "paid", 12},
        {107, 4, 250.0, "cancelled", 0},
        {108, 5, 900.0, "pending", 15}
    };

    TransactionRuleEngine engine;

    printTitle("CASE Expressions: C++ Technical Case Study");

    cout << R"(
Scenario:
A transaction-processing system must convert raw customer and transaction
data into operational categories. The business rules resemble SQL CASE
expressions used in reporting and analytics.

The system classifies:
- payment states
- transaction sizes
- shipping performance
- customer risk
- service fees
- operational actions
)";
    
    printTitle("1. Transaction-level classification");

    vector<ClassifiedTransaction> classifiedTransactions;

    const auto customerIndex = indexCustomers(customers);

    for (const auto& transaction : transactions) {
        const auto customerIt = customerIndex.find(transaction.customerId);

        if (customerIt == customerIndex.end()) {
            cerr
                << "Skipping transaction "
                << transaction.id
                << ": customer not found.\n";
            continue;
        }

        classifiedTransactions.push_back(
            engine.classify(
                transaction,
                customerIt->second
            )
        );
    }

    printTransactionReports(classifiedTransactions);

    printTitle("2. Customer validation");

    for (const auto& customer : customers) {
        cout
            << customer.name
            << ": "
            << validateCustomer(customer)
            << "\n";
    }

    printTitle("3. Customer-level conditional aggregation");

    vector<CustomerReport> customerReports =
        buildCustomerReports(
            customers,
            transactions,
            engine
        );

    printCustomerReports(customerReports);

    printTitle("4. Custom CASE-style ordering");

    sortReportsByRisk(customerReports);
    printCustomerReports(customerReports);

    const auto paymentPivot =
        buildPaymentPivot(transactions);

    printPaymentPivot(paymentPivot);

    testAmountClassification();
    demonstrateEdgeCases();
    demonstrateRulePrecedence();
    printComplexityDiscussion();
    printSecurityDiscussion();
    printSQLReference();

    printTitle("Program completed");

    cout << R"(
The important architectural idea is separation of concerns:

1. Raw data is represented by domain structures.
2. Rule functions represent CASE-style transformations.
3. Aggregation builds reporting metrics.
4. Sorting applies a business priority.
5. Validation identifies data-quality conditions.
6. Tests verify boundary behavior.

In a production SQL system, many of these transformations would be performed
directly in SELECT, GROUP BY, ORDER BY, UPDATE, or reporting queries using
CASE expressions.
)";

    return 0;
}
