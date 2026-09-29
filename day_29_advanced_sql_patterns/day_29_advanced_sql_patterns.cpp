/*
 * Advanced SQL Patterns: C++ Technical Case Study
 * =================================================
 *
 * Scenario:
 *   A retail analytics service receives sales transactions and customer
 *   activity events. The service must produce:
 *
 *     1. Top-N sales per region.
 *     2. Top-N results including ties.
 *     3. Consecutive activity "islands".
 *     4. Customer sessions separated by inactivity gaps.
 *     5. A deterministic deduplicated employee master.
 *     6. Pivot-style regional product analysis.
 *     7. A combined management report.
 *
 * This program models the same reasoning used by advanced SQL window
 * functions and analytical queries, but implements the algorithms with
 * C++17 standard-library data structures.
 *
 * Build:
 *   g++ -std=c++17 -O2 -Wall -Wextra -pedantic advanced_sql_patterns.cpp -o advanced_sql_patterns
 *
 * The program requires no external libraries.
 */

#include <algorithm>
#include <cassert>
#include <cmath>
#include <iomanip>
#include <iostream>
#include <map>
#include <numeric>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <tuple>
#include <unordered_map>
#include <utility>
#include <vector>

using namespace std;


// -----------------------------------------------------------------------------
// 1. Domain models
// -----------------------------------------------------------------------------

struct Sale {
    int saleId;
    int customerId;
    string salesperson;
    string region;
    string product;
    string date;
    double amount;
};

struct Event {
    int eventId;
    int customerId;
    string date;
    string type;
    double value;
};

struct EmployeeRecord {
    int recordId;
    int employeeId;
    string name;
    string email;
    string department;
    double salary;
    string updatedAt;
};

struct RankedSale {
    Sale sale;
    int rowNumber;
    int rank;
    int denseRank;
};

struct Session {
    int customerId;
    int sessionNumber;
    string startDate;
    string endDate;
    int eventCount;
    double value;
};

struct Island {
    int customerId;
    string startDate;
    string endDate;
    int eventCount;
};


// -----------------------------------------------------------------------------
// 2. Date utilities
// -----------------------------------------------------------------------------

struct SimpleDate {
    int year;
    int month;
    int day;
};

SimpleDate parseDate(const string& value) {
    if (value.size() != 10 || value[4] != '-' || value[7] != '-') {
        throw invalid_argument("Expected date in YYYY-MM-DD format: " + value);
    }

    return {
        stoi(value.substr(0, 4)),
        stoi(value.substr(5, 2)),
        stoi(value.substr(8, 2))
    };
}

bool isLeapYear(int year) {
    return (year % 400 == 0) ||
           (year % 4 == 0 && year % 100 != 0);
}

int daysInMonth(int year, int month) {
    static const int days[] = {
        31, 28, 31, 30, 31, 30,
        31, 31, 30, 31, 30, 31
    };

    if (month == 2 && isLeapYear(year)) {
        return 29;
    }

    return days[month - 1];
}

int daysBeforeYear(int year) {
    const int y = year - 1;

    return 365 * y +
           y / 4 -
           y / 100 +
           y / 400;
}

int toOrdinal(SimpleDate date) {
    int ordinal = daysBeforeYear(date.year);

    for (int month = 1; month < date.month; ++month) {
        ordinal += daysInMonth(date.year, month);
    }

    return ordinal + date.day;
}

int daysBetween(const string& first, const string& second) {
    return toOrdinal(parseDate(second)) -
           toOrdinal(parseDate(first));
}


// -----------------------------------------------------------------------------
// 3. Sample data
// -----------------------------------------------------------------------------

vector<Sale> makeSales() {
    return {
        {1, 101, "Asha", "North", "Laptop", "2026-01-03", 1200},
        {2, 101, "Asha", "North", "Phone", "2026-01-04", 800},
        {3, 101, "Asha", "North", "Laptop", "2026-01-09", 1500},
        {4, 102, "Ravi", "North", "Tablet", "2026-01-05", 600},
        {5, 102, "Ravi", "North", "Phone", "2026-01-06", 900},
        {6, 102, "Ravi", "North", "Laptop", "2026-01-10", 2100},
        {7, 103, "Meera", "South", "Laptop", "2026-01-02", 2200},
        {8, 103, "Meera", "South", "Phone", "2026-01-08", 700},
        {9, 103, "Meera", "South", "Tablet", "2026-01-11", 500},
        {10, 104, "Kabir", "South", "Laptop", "2026-01-02", 1800},
        {11, 104, "Kabir", "South", "Phone", "2026-01-07", 1100},
        {12, 104, "Kabir", "South", "Tablet", "2026-01-09", 900},
        {13, 105, "Nisha", "West", "Laptop", "2026-01-03", 1300},
        {14, 105, "Nisha", "West", "Phone", "2026-01-03", 1300},
        {15, 105, "Nisha", "West", "Tablet", "2026-01-12", 400}
    };
}

vector<Event> makeEvents() {
    return {
        {1, 101, "2026-01-01", "login", 0},
        {2, 101, "2026-01-02", "purchase", 120},
        {3, 101, "2026-01-03", "login", 0},
        {4, 101, "2026-01-04", "purchase", 90},
        {5, 101, "2026-01-10", "login", 0},
        {6, 101, "2026-01-11", "purchase", 150},
        {7, 102, "2026-01-02", "login", 0},
        {8, 102, "2026-01-03", "purchase", 80},
        {9, 102, "2026-01-08", "login", 0},
        {10, 102, "2026-01-09", "purchase", 100},
        {11, 102, "2026-01-10", "purchase", 60},
        {12, 103, "2026-01-01", "login", 0},
        {13, 103, "2026-01-15", "purchase", 300}
    };
}

vector<EmployeeRecord> makeEmployees() {
    return {
        {1, 501, "Arjun", "arjun@example.com", "Engineering", 90000, "2026-01-01T09:00:00"},
        {2, 501, "Arjun Kumar", "arjun@example.com", "Engineering", 95000, "2026-02-01T09:00:00"},
        {3, 502, "Bhavna", "bhavna@example.com", "Finance", 85000, "2026-01-15T09:00:00"},
        {4, 502, "Bhavna", "bhavna@example.com", "Finance", 88000, "2026-02-15T09:00:00"},
        {5, 503, "Chirag", "chirag@example.com", "Engineering", 78000, "2026-01-10T09:00:00"},
        {6, 504, "Divya", "divya@example.com", "HR", 70000, "2026-01-05T09:00:00"},
        {7, 504, "Divya", "divya@example.com", "HR", 72000, "2026-03-05T09:00:00"}
    };
}


// -----------------------------------------------------------------------------
// 4. Formatting utilities
// -----------------------------------------------------------------------------

void heading(const string& title) {
    cout << "\n" << string(88, '=') << "\n";
    cout << title << "\n";
    cout << string(88, '=') << "\n";
}

void printMoney(double value) {
    cout << fixed << setprecision(2) << value;
}


// -----------------------------------------------------------------------------
// 5. Top-N ranking
// -----------------------------------------------------------------------------

vector<RankedSale> rankSalesByRegion(
    const vector<Sale>& sales
) {
    /*
     * This is the in-memory equivalent of:
     *
     * ROW_NUMBER() OVER (
     *     PARTITION BY region
     *     ORDER BY amount DESC, sale_id
     * )
     *
     * A std::map creates the logical partitions.
     */
    map<string, vector<Sale>> partitions;

    for (const Sale& sale : sales) {
        partitions[sale.region].push_back(sale);
    }

    vector<RankedSale> result;

    for (auto& [region, group] : partitions) {
        sort(
            group.begin(),
            group.end(),
            [](const Sale& left, const Sale& right) {
                if (left.amount != right.amount) {
                    return left.amount > right.amount;
                }

                return left.saleId < right.saleId;
            }
        );

        double previousAmount = numeric_limits<double>::quiet_NaN();
        int rank = 0;
        int denseRank = 0;

        for (size_t index = 0; index < group.size(); ++index) {
            const Sale& sale = group[index];

            if (index == 0 ||
                sale.amount != previousAmount) {
                rank = static_cast<int>(index) + 1;
                ++denseRank;
            }

            result.push_back({
                sale,
                static_cast<int>(index) + 1,
                rank,
                denseRank
            });

            previousAmount = sale.amount;
        }
    }

    return result;
}

vector<RankedSale> topNPerRegion(
    const vector<Sale>& sales,
    int n
) {
    if (n <= 0) {
        throw invalid_argument("Top-N requires a positive N.");
    }

    vector<RankedSale> ranked = rankSalesByRegion(sales);

    ranked.erase(
        remove_if(
            ranked.begin(),
            ranked.end(),
            [n](const RankedSale& row) {
                return row.rowNumber > n;
            }
        ),
        ranked.end()
    );

    return ranked;
}

vector<RankedSale> topNRanksIncludingTies(
    const vector<Sale>& sales,
    int n
) {
    if (n <= 0) {
        throw invalid_argument("Top-N requires a positive N.");
    }

    vector<RankedSale> ranked = rankSalesByRegion(sales);

    ranked.erase(
        remove_if(
            ranked.begin(),
            ranked.end(),
            [n](const RankedSale& row) {
                return row.rank > n;
            }
        ),
        ranked.end()
    );

    return ranked;
}

void printRankedSales(const vector<RankedSale>& rows) {
    cout << left
         << setw(8) << "Region"
         << setw(10) << "Sale"
         << setw(14) << "Person"
         << setw(12) << "Amount"
         << setw(8) << "ROW_NUM"
         << setw(8) << "RANK"
         << setw(8) << "DENSE"
         << "\n";

    for (const RankedSale& row : rows) {
        cout << left
             << setw(8) << row.sale.region
             << setw(10) << row.sale.saleId
             << setw(14) << row.sale.salesperson;

        cout << setw(12);
        printMoney(row.sale.amount);

        cout << setw(8) << row.rowNumber
             << setw(8) << row.rank
             << setw(8) << row.denseRank
             << "\n";
    }
}


// -----------------------------------------------------------------------------
// 6. Gaps-and-islands
// -----------------------------------------------------------------------------

vector<Island> consecutiveActivityIslands(
    const vector<Event>& events
) {
    /*
     * A new island starts when there is a calendar gap.
     *
     * SQL often implements this with:
     *
     *   event_date - ROW_NUMBER()
     *
     * or with LAG followed by a cumulative SUM of a new-island flag.
     *
     * The explicit state machine below makes the same boundary condition
     * visible at the application level.
     */
    map<int, vector<Event>> partitions;

    for (const Event& event : events) {
        partitions[event.customerId].push_back(event);
    }

    vector<Island> islands;

    for (auto& [customerId, group] : partitions) {
        sort(
            group.begin(),
            group.end(),
            [](const Event& left, const Event& right) {
                if (left.date != right.date) {
                    return left.date < right.date;
                }

                return left.eventId < right.eventId;
            }
        );

        if (group.empty()) {
            continue;
        }

        Island current{
            customerId,
            group.front().date,
            group.front().date,
            1
        };

        for (size_t i = 1; i < group.size(); ++i) {
            const Event& event = group[i];

            if (daysBetween(current.endDate, event.date) > 1) {
                islands.push_back(current);

                current = {
                    customerId,
                    event.date,
                    event.date,
                    1
                };
            } else {
                current.endDate = event.date;
                ++current.eventCount;
            }
        }

        islands.push_back(current);
    }

    return islands;
}

void printIslands(const vector<Island>& islands) {
    cout << left
         << setw(12) << "Customer"
         << setw(15) << "Start"
         << setw(15) << "End"
         << setw(10) << "Events"
         << "\n";

    for (const Island& island : islands) {
        cout << left
             << setw(12) << island.customerId
             << setw(15) << island.startDate
             << setw(15) << island.endDate
             << setw(10) << island.eventCount
             << "\n";
    }
}


// -----------------------------------------------------------------------------
// 7. Sessionization
// -----------------------------------------------------------------------------

vector<Session> sessionize(
    const vector<Event>& events,
    int maximumGapDays
) {
    if (maximumGapDays < 0) {
        throw invalid_argument(
            "The session gap cannot be negative."
        );
    }

    map<int, vector<Event>> partitions;

    for (const Event& event : events) {
        partitions[event.customerId].push_back(event);
    }

    vector<Session> sessions;

    for (auto& [customerId, group] : partitions) {
        sort(
            group.begin(),
            group.end(),
            [](const Event& left, const Event& right) {
                if (left.date != right.date) {
                    return left.date < right.date;
                }

                return left.eventId < right.eventId;
            }
        );

        int sessionNumber = 0;
        Session current{};

        for (const Event& event : group) {
            const bool newSession =
                sessionNumber == 0 ||
                daysBetween(current.endDate, event.date)
                    > maximumGapDays;

            if (newSession) {
                ++sessionNumber;

                current = {
                    customerId,
                    sessionNumber,
                    event.date,
                    event.date,
                    1,
                    event.value
                };

                sessions.push_back(current);
            } else {
                current.endDate = event.date;
                ++current.eventCount;
                current.value += event.value;

                sessions.back() = current;
            }
        }
    }

    return sessions;
}

void printSessions(const vector<Session>& sessions) {
    cout << left
         << setw(12) << "Customer"
         << setw(10) << "Session"
         << setw(15) << "Start"
         << setw(15) << "End"
         << setw(10) << "Events"
         << setw(12) << "Value"
         << "\n";

    for (const Session& session : sessions) {
        cout << left
             << setw(12) << session.customerId
             << setw(10) << session.sessionNumber
             << setw(15) << session.startDate
             << setw(15) << session.endDate
             << setw(10) << session.eventCount
             << setw(12);

        printMoney(session.value);
        cout << "\n";
    }
}


// -----------------------------------------------------------------------------
// 8. Deterministic deduplication
// -----------------------------------------------------------------------------

vector<EmployeeRecord> deduplicateEmployees(
    const vector<EmployeeRecord>& records
) {
    /*
     * SQL equivalent:
     *
     *   ROW_NUMBER() OVER (
     *       PARTITION BY email
     *       ORDER BY updated_at DESC, record_id DESC
     *   )
     *
     * Keep rn = 1.
     *
     * The second ordering criterion is important because timestamps can tie.
     * Without a deterministic tie-breaker, repeated executions may not make
     * the same retention decision.
     */
    map<string, vector<EmployeeRecord>> partitions;

    for (const EmployeeRecord& record : records) {
        partitions[record.email].push_back(record);
    }

    vector<EmployeeRecord> result;

    for (auto& [email, group] : partitions) {
        sort(
            group.begin(),
            group.end(),
            [](const EmployeeRecord& left, const EmployeeRecord& right) {
                if (left.updatedAt != right.updatedAt) {
                    return left.updatedAt > right.updatedAt;
                }

                return left.recordId > right.recordId;
            }
        );

        result.push_back(group.front());
    }

    sort(
        result.begin(),
        result.end(),
        [](const EmployeeRecord& left, const EmployeeRecord& right) {
            return left.recordId < right.recordId;
        }
    );

    return result;
}

void printEmployees(const vector<EmployeeRecord>& records) {
    cout << left
         << setw(10) << "Record"
         << setw(12) << "Employee"
         << setw(20) << "Name"
         << setw(28) << "Email"
         << setw(16) << "Department"
         << setw(12) << "Salary"
         << "\n";

    for (const auto& record : records) {
        cout << left
             << setw(10) << record.recordId
             << setw(12) << record.employeeId
             << setw(20) << record.name
             << setw(28) << record.email
             << setw(16) << record.department
             << setw(12);

        printMoney(record.salary);
        cout << "\n";
    }
}


// -----------------------------------------------------------------------------
// 9. Pivot-style aggregation
// -----------------------------------------------------------------------------

struct PivotRow {
    string region;
    double laptop = 0;
    double phone = 0;
    double tablet = 0;
    double total = 0;
};

vector<PivotRow> pivotSales(const vector<Sale>& sales) {
    /*
     * SQL:
     *
     *   SUM(CASE WHEN product = 'Laptop' THEN amount ELSE 0 END)
     *
     * is conditional aggregation. It is portable and works even in database
     * systems that do not provide a dedicated PIVOT operator.
     */
    map<string, PivotRow> rows;

    for (const Sale& sale : sales) {
        PivotRow& row = rows[sale.region];
        row.region = sale.region;
        row.total += sale.amount;

        if (sale.product == "Laptop") {
            row.laptop += sale.amount;
        } else if (sale.product == "Phone") {
            row.phone += sale.amount;
        } else if (sale.product == "Tablet") {
            row.tablet += sale.amount;
        }
    }

    vector<PivotRow> result;

    for (const auto& [region, row] : rows) {
        result.push_back(row);
    }

    return result;
}

void printPivot(const vector<PivotRow>& rows) {
    cout << left
         << setw(10) << "Region"
         << setw(14) << "Laptop"
         << setw(14) << "Phone"
         << setw(14) << "Tablet"
         << setw(14) << "Total"
         << "\n";

    for (const PivotRow& row : rows) {
        cout << left
             << setw(10) << row.region
             << setw(14);

        printMoney(row.laptop);

        cout << setw(14);
        printMoney(row.phone);

        cout << setw(14);
        printMoney(row.tablet);

        cout << setw(14);
        printMoney(row.total);

        cout << "\n";
    }
}


// -----------------------------------------------------------------------------
// 10. Combined management report
// -----------------------------------------------------------------------------

struct RegionalReportRow {
    Sale sale;
    int rank;
    double regionTotal;
    double percentageOfRegion;
    double runningTotal;
};

vector<RegionalReportRow> buildRegionalReport(
    const vector<Sale>& sales
) {
    map<string, vector<Sale>> partitions;
    map<string, double> totals;

    for (const Sale& sale : sales) {
        partitions[sale.region].push_back(sale);
        totals[sale.region] += sale.amount;
    }

    vector<RegionalReportRow> result;

    for (auto& [region, group] : partitions) {
        sort(
            group.begin(),
            group.end(),
            [](const Sale& left, const Sale& right) {
                if (left.amount != right.amount) {
                    return left.amount > right.amount;
                }

                return left.saleId < right.saleId;
            }
        );

        map<int, double> runningTotals;

        vector<Sale> chronological = group;

        sort(
            chronological.begin(),
            chronological.end(),
            [](const Sale& left, const Sale& right) {
                if (left.date != right.date) {
                    return left.date < right.date;
                }

                return left.saleId < right.saleId;
            }
        );

        double running = 0;

        for (const Sale& sale : chronological) {
            running += sale.amount;
            runningTotals[sale.saleId] = running;
        }

        for (size_t index = 0; index < group.size(); ++index) {
            const Sale& sale = group[index];
            const double regionTotal = totals[region];

            result.push_back({
                sale,
                static_cast<int>(index) + 1,
                regionTotal,
                (sale.amount / regionTotal) * 100.0,
                runningTotals[sale.saleId]
            });
        }
    }

    return result;
}

void printRegionalReport(
    const vector<RegionalReportRow>& rows
) {
    cout << left
         << setw(9) << "Region"
         << setw(8) << "Sale"
         << setw(14) << "Person"
         << setw(12) << "Amount"
         << setw(9) << "Rank"
         << setw(12) << "%Region"
         << setw(15) << "Running"
         << "\n";

    for (const auto& row : rows) {
        cout << left
             << setw(9) << row.sale.region
             << setw(8) << row.sale.saleId
             << setw(14) << row.sale.salesperson
             << setw(12);

        printMoney(row.sale.amount);

        cout << setw(9) << row.rank
             << setw(12);

        printMoney(row.percentageOfRegion);

        cout << setw(15);
        printMoney(row.runningTotal);

        cout << "\n";
    }
}


// -----------------------------------------------------------------------------
// 11. SQL generation with safe identifier validation
// -----------------------------------------------------------------------------

bool isSafeIdentifier(const string& value) {
    if (value.empty()) {
        return false;
    }

    if (!(isalpha(static_cast<unsigned char>(value.front())) ||
          value.front() == '_')) {
        return false;
    }

    for (char character : value) {
        if (!(isalnum(static_cast<unsigned char>(character)) ||
              character == '_')) {
            return false;
        }
    }

    return true;
}

string quoteSqlLiteral(const string& value) {
    string escaped;

    for (char character : value) {
        if (character == '\'') {
            escaped += "''";
        } else {
            escaped += character;
        }
    }

    return "'" + escaped + "'";
}

string quoteIdentifier(const string& identifier) {
    if (!isSafeIdentifier(identifier)) {
        throw invalid_argument(
            "Unsafe SQL identifier: " + identifier
        );
    }

    return "\"" + identifier + "\"";
}

string buildPivotSQL(const vector<string>& products) {
    if (products.empty()) {
        throw invalid_argument(
            "At least one pivot product is required."
        );
    }

    ostringstream sql;

    sql << "SELECT\n";
    sql << "    region,\n";

    for (size_t index = 0; index < products.size(); ++index) {
        const string& product = products[index];

        /*
         * Product values are literals, while generated aliases are SQL
         * identifiers. These two forms of SQL data require different safety
         * handling.
         */
        const string literal = quoteSqlLiteral(product);
        const string alias =
            quoteIdentifier(product + "_sales");

        sql << "    SUM(CASE WHEN product = "
            << literal
            << " THEN amount ELSE 0 END) AS "
            << alias;

        if (index + 1 < products.size()) {
            sql << ",";
        }

        sql << "\n";
    }

    sql << "FROM sales\n";
    sql << "GROUP BY region\n";
    sql << "ORDER BY region;";

    return sql.str();
}


// -----------------------------------------------------------------------------
// 12. Performance notes
// -----------------------------------------------------------------------------

void printPerformanceNotes() {
    heading("Performance and design considerations");

    cout
        << "Top-N per group:\n"
        << "  Window ranking generally requires partition ordering.\n"
        << "  Indexes aligned with PARTITION BY and ORDER BY can reduce work.\n\n"

        << "Gaps-and-islands:\n"
        << "  Correct ordering is essential.\n"
        << "  A missing or duplicated timestamp can change island boundaries.\n\n"

        << "Deduplication:\n"
        << "  A deterministic business key and retention rule are required.\n"
        << "  Large tables benefit from indexes on the duplicate key and ordering columns.\n\n"

        << "Pivot-style aggregation:\n"
        << "  Conditional aggregation is portable but becomes wide as category count grows.\n"
        << "  Dynamic SQL requires strict identifier validation.\n\n"

        << "Memory model:\n"
        << "  This program loads all rows into memory.\n"
        << "  A production database can process larger datasets with indexes,\n"
        << "  query planning, partition pruning, and disk-backed execution.\n";
}


// -----------------------------------------------------------------------------
// 13. Tests
// -----------------------------------------------------------------------------

void runTests(
    const vector<Sale>& sales,
    const vector<EmployeeRecord>& employees,
    const vector<PivotRow>& pivotRows
) {
    heading("Validation tests");

    const auto topTwo = topNPerRegion(sales, 2);

    map<string, int> counts;

    for (const auto& row : topTwo) {
        ++counts[row.sale.region];
    }

    assert(counts["North"] == 2);
    assert(counts["South"] == 2);
    assert(counts["West"] == 2);

    const auto deduplicated =
        deduplicateEmployees(employees);

    set<string> emails;

    for (const auto& employee : deduplicated) {
        const bool inserted =
            emails.insert(employee.email).second;

        assert(inserted);
    }

    const auto arjun = find_if(
        deduplicated.begin(),
        deduplicated.end(),
        [](const EmployeeRecord& employee) {
            return employee.email == "arjun@example.com";
        }
    );

    assert(arjun != deduplicated.end());
    assert(arjun->salary == 95000);

    const auto north = find_if(
        pivotRows.begin(),
        pivotRows.end(),
        [](const PivotRow& row) {
            return row.region == "North";
        }
    );

    assert(north != pivotRows.end());
    assert(north->laptop == 3600);
    assert(north->phone == 1700);
    assert(north->tablet == 600);

    cout << "All tests passed.\n";
}


// -----------------------------------------------------------------------------
// 14. Main
// -----------------------------------------------------------------------------

int main() {
    try {
        const vector<Sale> sales = makeSales();
        const vector<Event> events = makeEvents();
        const vector<EmployeeRecord> employees = makeEmployees();

        heading(
            "ADVANCED SQL PATTERNS - C++ CASE STUDY"
        );

        heading("1. Top 2 sales per region");

        const auto topTwo = topNPerRegion(sales, 2);
        printRankedSales(topTwo);

        heading("2. Top 2 ranks per region, including ties");

        const auto tiedTopTwo =
            topNRanksIncludingTies(sales, 2);

        printRankedSales(tiedTopTwo);

        heading("3. Consecutive activity islands");

        const auto islands =
            consecutiveActivityIslands(events);

        printIslands(islands);

        heading("4. Customer sessionization");

        const auto sessions =
            sessionize(events, 1);

        printSessions(sessions);

        heading("5. Deterministic employee deduplication");

        const auto deduplicated =
            deduplicateEmployees(employees);

        printEmployees(deduplicated);

        heading("6. Pivot-style regional product analysis");

        const auto pivotRows =
            pivotSales(sales);

        printPivot(pivotRows);

        heading("7. Combined regional analytical report");

        const auto regionalReport =
            buildRegionalReport(sales);

        printRegionalReport(regionalReport);

        heading("8. Generated pivot-style SQL");

        cout << buildPivotSQL({
            "Laptop",
            "Phone",
            "Tablet"
        }) << "\n";

        printPerformanceNotes();

        runTests(
            sales,
            employees,
            pivotRows
        );

        heading("Case study completed successfully");

        cout
            << "The implementation demonstrates the application-level logic\n"
            << "behind advanced SQL analytical patterns.\n";

        return 0;
    }
    catch (const exception& error) {
        cerr << "Fatal error: " << error.what() << "\n";
        return 1;
    }
}
