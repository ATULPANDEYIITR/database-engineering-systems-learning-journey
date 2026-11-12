#include <algorithm>
#include <cmath>
#include <cstdint>
#include <iomanip>
#include <iostream>
#include <map>
#include <optional>
#include <set>
#include <stdexcept>
#include <string>
#include <vector>

using namespace std;

enum class TupleState {
    Live,
    Dead,
    Frozen,
    Removed
};

enum class VacuumMode {
    Standard,
    Full,
    Freeze
};

struct Tuple {
    uint64_t id;
    string value;
    uint64_t xmin;
    optional<uint64_t> xmax;
    TupleState state;
    size_t page;
};

struct Page {
    size_t id;
    size_t capacity;
    vector<uint64_t> tupleIds;
};

struct TableStatistics {
    size_t live;
    size_t dead;
    size_t frozen;
    size_t pages;
    double deadPercentage;
};

struct VacuumReport {
    size_t scanned;
    size_t removed;
    size_t frozen;
    size_t deadRemaining;
    size_t pagesBefore;
    size_t pagesAfter;
    size_t pagesReclaimed;
};

class TransactionRegistry {
private:
    uint64_t nextXid = 1;
    set<uint64_t> active;

public:
    uint64_t begin() {
        uint64_t xid = nextXid++;
        active.insert(xid);
        return xid;
    }

    void commit(uint64_t xid) {
        if (active.erase(xid) == 0) {
            throw invalid_argument("Transaction is not active");
        }
    }

    uint64_t oldestActive() const {
        if (active.empty()) {
            return nextXid;
        }
        return *active.begin();
    }

    uint64_t currentXid() const {
        return nextXid;
    }

    size_t activeCount() const {
        return active.size();
    }
};

class Relation {
private:
    string name;
    size_t pageCapacity;

    uint64_t nextTupleId = 1;

    vector<Page> pages;
    map<uint64_t, Tuple> tuples;

    Page& allocatePage() {
        pages.push_back({
            pages.size(),
            pageCapacity,
            {}
        });

        return pages.back();
    }

    Page& availablePage() {
        for (auto it = pages.rbegin(); it != pages.rend(); ++it) {
            size_t occupied = 0;

            for (uint64_t id : it->tupleIds) {
                auto found = tuples.find(id);

                if (found != tuples.end() &&
                    found->second.state != TupleState::Removed) {
                    occupied++;
                }
            }

            if (occupied < pageCapacity) {
                return *it;
            }
        }

        return allocatePage();
    }

    Tuple& findLive(uint64_t id) {
        auto it = tuples.find(id);

        if (it == tuples.end() ||
            (it->second.state != TupleState::Live &&
             it->second.state != TupleState::Frozen)) {
            throw invalid_argument("Live tuple does not exist");
        }

        return it->second;
    }

public:
    Relation(string relationName, size_t capacity)
        : name(move(relationName)), pageCapacity(capacity) {

        if (name.empty() || capacity == 0) {
            throw invalid_argument("Invalid relation configuration");
        }
    }

    uint64_t insert(const string& value, uint64_t xid) {
        if (value.empty() || xid == 0) {
            throw invalid_argument("Invalid tuple input");
        }

        Page& page = availablePage();

        uint64_t id = nextTupleId++;

        Tuple row{
            id,
            value,
            xid,
            nullopt,
            TupleState::Live,
            page.id
        };

        tuples.emplace(id, move(row));
        page.tupleIds.push_back(id);

        return id;
    }

    void erase(uint64_t id, uint64_t xid) {
        Tuple& row = findLive(id);

        if (xid <= row.xmin) {
            throw invalid_argument(
                "Deletion transaction must follow insertion"
            );
        }

        row.xmax = xid;
        row.state = TupleState::Dead;
    }

    uint64_t update(
        uint64_t id,
        const string& value,
        uint64_t xid
    ) {
        if (value.empty()) {
            throw invalid_argument("Updated value cannot be empty");
        }

        findLive(id);
        erase(id, xid);

        return insert(value, xid);
    }

    TableStatistics statistics() const {
        size_t live = 0;
        size_t dead = 0;
        size_t frozen = 0;

        for (const auto& [id, row] : tuples) {
            switch (row.state) {
                case TupleState::Live:
                    live++;
                    break;
                case TupleState::Dead:
                    dead++;
                    break;
                case TupleState::Frozen:
                    live++;
                    frozen++;
                    break;
                case TupleState::Removed:
                    break;
            }
        }

        double percentage = 100.0 * dead /
            max<size_t>(live + dead, 1);

        return {
            live,
            dead,
            frozen,
            pages.size(),
            percentage
        };
    }

    VacuumReport vacuum(
        VacuumMode mode,
        uint64_t oldestActiveXid,
        uint64_t currentXid
    ) {
        if (oldestActiveXid == 0 ||
            currentXid < oldestActiveXid) {
            throw invalid_argument("Invalid visibility horizon");
        }

        TableStatistics before = statistics();

        size_t removed = 0;
        size_t frozen = 0;

        for (auto& [id, row] : tuples) {
            if (row.state == TupleState::Dead &&
                row.xmax.has_value() &&
                *row.xmax < oldestActiveXid) {

                row.state = TupleState::Removed;
                removed++;
            }

            if (mode == VacuumMode::Freeze &&
                row.state == TupleState::Live &&
                currentXid - row.xmin >= 100) {

                row.state = TupleState::Frozen;
                frozen++;
            }
        }

        if (mode == VacuumMode::Full) {
            // A full rewrite compacts live tuples into new pages.
            pages.clear();

            for (auto& [id, row] : tuples) {
                if (row.state != TupleState::Live &&
                    row.state != TupleState::Frozen) {
                    continue;
                }

                if (pages.empty() ||
                    pages.back().tupleIds.size() >= pageCapacity) {
                    allocatePage();
                }

                Page& page = pages.back();
                row.page = page.id;
                page.tupleIds.push_back(id);
            }
        }

        TableStatistics after = statistics();

        return {
            tuples.size(),
            removed,
            frozen,
            after.dead,
            before.pages,
            after.pages,
            before.pages > after.pages
                ? before.pages - after.pages
                : 0
        };
    }

    const string& getName() const {
        return name;
    }
};

struct AutovacuumPolicy {
    size_t threshold = 50;
    double scaleFactor = 0.20;
    double maxDeadRatio = 0.25;

    void validate() const {
        if (scaleFactor < 0 || scaleFactor > 1 ||
            maxDeadRatio < 0 || maxDeadRatio > 1) {
            throw invalid_argument("Invalid autovacuum policy");
        }
    }

    bool required(const TableStatistics& stats) const {
        validate();

        double thresholdValue =
            threshold + scaleFactor * stats.live;

        return stats.dead > thresholdValue ||
            stats.deadPercentage / 100.0 > maxDeadRatio;
    }
};

class GovernanceEngine {
private:
    Relation& relation;
    TransactionRegistry& transactions;
    AutovacuumPolicy policy;

public:
    GovernanceEngine(
        Relation& r,
        TransactionRegistry& t,
        AutovacuumPolicy p
    ) : relation(r), transactions(t), policy(p) {
        policy.validate();
    }

    optional<VacuumReport> evaluate() {
        TableStatistics stats = relation.statistics();

        if (!policy.required(stats)) {
            return nullopt;
        }

        return relation.vacuum(
            VacuumMode::Standard,
            transactions.oldestActive(),
            transactions.currentXid()
        );
    }
};

void printStatistics(const TableStatistics& stats) {
    cout << "Live tuples: " << stats.live << '\n';
    cout << "Dead tuples: " << stats.dead << '\n';
    cout << "Frozen tuples: " << stats.frozen << '\n';
    cout << "Physical pages: " << stats.pages << '\n';
    cout << "Dead percentage: "
         << fixed << setprecision(2)
         << stats.deadPercentage << "%\n";
}

void printReport(const VacuumReport& report) {
    cout << "Scanned tuples: " << report.scanned << '\n';
    cout << "Removed tuples: " << report.removed << '\n';
    cout << "Frozen tuples: " << report.frozen << '\n';
    cout << "Remaining dead tuples: "
         << report.deadRemaining << '\n';
    cout << "Pages before: " << report.pagesBefore << '\n';
    cout << "Pages after: " << report.pagesAfter << '\n';
    cout << "Pages reclaimed: "
         << report.pagesReclaimed << '\n';
}

int main() {
    try {
        cout << "POSTGRESQL VACUUM AND GARBAGE COLLECTION\n";
        cout << "========================================\n\n";

        TransactionRegistry transactions;
        Relation orders("orders", 10);

        cout << "1. INITIAL INSERTION\n";

        uint64_t insertXid = transactions.begin();

        vector<uint64_t> identifiers;

        for (int i = 0; i < 35; i++) {
            identifiers.push_back(
                orders.insert(
                    "Order-" + to_string(i),
                    insertXid
                )
            );
        }

        transactions.commit(insertXid);
        printStatistics(orders.statistics());

        cout << "\n2. DELETE WITH LONG-RUNNING SNAPSHOT\n";

        uint64_t oldXid = transactions.begin();
        uint64_t deleteXid = transactions.begin();

        for (int i = 0; i < 15; i++) {
            orders.erase(identifiers[i], deleteXid);
        }

        transactions.commit(deleteXid);

        printStatistics(orders.statistics());

        cout << "\n3. STANDARD VACUUM\n";

        VacuumReport first = orders.vacuum(
            VacuumMode::Standard,
            transactions.oldestActive(),
            transactions.currentXid()
        );

        printReport(first);

        cout << "\n4. RELEASE OLD SNAPSHOT\n";

        transactions.commit(oldXid);

        VacuumReport second = orders.vacuum(
            VacuumMode::Standard,
            transactions.oldestActive(),
            transactions.currentXid()
        );

        printReport(second);

        cout << "\n5. UPDATE WORKLOAD\n";

        for (int i = 15; i < 25; i++) {
            uint64_t xid = transactions.begin();

            orders.update(
                identifiers[i],
                "Updated-" + to_string(i),
                xid
            );

            transactions.commit(xid);
        }

        printStatistics(orders.statistics());

        cout << "\n6. AUTOVACUUM POLICY\n";

        AutovacuumPolicy policy{
            3,
            0.10,
            0.10
        };

        GovernanceEngine engine(
            orders,
            transactions,
            policy
        );

        auto automaticReport = engine.evaluate();

        if (automaticReport.has_value()) {
            printReport(*automaticReport);
        } else {
            cout << "Autovacuum threshold not reached.\n";
        }

        cout << "\n7. FREEZE\n";

        VacuumReport freezeReport = orders.vacuum(
            VacuumMode::Freeze,
            transactions.oldestActive(),
            transactions.currentXid() + 200
        );

        printReport(freezeReport);

        cout << "\n8. VACUUM FULL\n";

        VacuumReport fullReport = orders.vacuum(
            VacuumMode::Full,
            transactions.oldestActive(),
            transactions.currentXid() + 200
        );

        printReport(fullReport);

        cout << "\n9. FINAL TABLE STATISTICS\n";

        printStatistics(orders.statistics());

        cout << "\n10. FAILURE HANDLING\n";

        try {
            orders.erase(99999, transactions.currentXid());
        } catch (const invalid_argument& error) {
            cout << "Expected failure: "
                 << error.what() << '\n';
        }

        try {
            AutovacuumPolicy invalidPolicy{
                10,
                1.5,
                0.20
            };

            invalidPolicy.validate();
        } catch (const invalid_argument& error) {
            cout << "Expected policy failure: "
                 << error.what() << '\n';
        }

        if (transactions.activeCount() != 0) {
            throw runtime_error(
                "Active transactions remain after simulation"
            );
        }

        TableStatistics finalStats = orders.statistics();

        if (finalStats.dead < 0 || finalStats.pages < 0) {
            throw runtime_error("Invalid storage statistics");
        }

        cout << "\nAll validation checks passed.\n";

    } catch (const exception& error) {
        cerr << "Execution failed: "
             << error.what() << '\n';

        return 1;
    }

    return 0;
}
