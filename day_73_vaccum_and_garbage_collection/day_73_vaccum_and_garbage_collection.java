import java.util.*;
import java.util.concurrent.atomic.AtomicLong;

/*
 * VACUUM AND GARBAGE COLLECTION
 *
 * Enterprise-oriented PostgreSQL storage maintenance model.
 *
 * Java 17 features:
 * records, enums, immutable policy objects, collections,
 * service classes, interfaces, validation and exceptions.
 */

public class VacuumGarbageCollection {

    enum TupleState {
        LIVE,
        DEAD,
        FROZEN,
        REMOVED
    }

    enum VacuumMode {
        STANDARD,
        FULL,
        FREEZE
    }

    enum TransactionStatus {
        ACTIVE,
        COMMITTED
    }

    static class StorageException extends RuntimeException {
        StorageException(String message) {
            super(message);
        }
    }

    static class TransactionException extends RuntimeException {
        TransactionException(String message) {
            super(message);
        }
    }

    record Tuple(
        long id,
        String value,
        long xmin,
        Long xmax,
        TupleState state,
        int pageId
    ) {
        Tuple {
            if (id < 1 || xmin < 1 || value == null ||
                value.isBlank() || pageId < 0) {
                throw new IllegalArgumentException(
                    "Invalid tuple"
                );
            }

            Objects.requireNonNull(state);
        }

        Tuple markDead(long xid) {
            if (state != TupleState.LIVE &&
                state != TupleState.FROZEN) {
                throw new StorageException(
                    "Only live tuples can be deleted"
                );
            }

            if (xid <= xmin) {
                throw new StorageException(
                    "Deletion transaction must follow insertion"
                );
            }

            return new Tuple(
                id,
                value,
                xmin,
                xid,
                TupleState.DEAD,
                pageId
            );
        }

        Tuple freeze() {
            if (state != TupleState.LIVE) {
                throw new StorageException(
                    "Only live tuples can be frozen"
                );
            }

            return new Tuple(
                id,
                value,
                xmin,
                xmax,
                TupleState.FROZEN,
                pageId
            );
        }

        Tuple relocate(int newPageId) {
            return new Tuple(
                id,
                value,
                xmin,
                xmax,
                state,
                newPageId
            );
        }

        boolean isLive() {
            return state == TupleState.LIVE ||
                state == TupleState.FROZEN;
        }
    }

    record TableStatistics(
        long live,
        long dead,
        long frozen,
        int pages,
        double deadPercentage
    ) {}

    record VacuumReport(
        int scanned,
        int removed,
        int frozen,
        long deadRemaining,
        int pagesBefore,
        int pagesAfter,
        int pagesReclaimed,
        VacuumMode mode
    ) {}

    record AutovacuumPolicy(
        long threshold,
        double scaleFactor,
        double maxDeadRatio
    ) {
        AutovacuumPolicy {
            if (threshold < 0 ||
                scaleFactor < 0 ||
                scaleFactor > 1 ||
                maxDeadRatio < 0 ||
                maxDeadRatio > 1) {
                throw new IllegalArgumentException(
                    "Invalid autovacuum policy"
                );
            }
        }

        boolean required(TableStatistics stats) {
            double effectiveThreshold =
                threshold + scaleFactor * stats.live();

            return stats.dead() > effectiveThreshold ||
                stats.deadPercentage() / 100.0 > maxDeadRatio;
        }
    }

    record Transaction(
        long xid,
        String owner,
        TransactionStatus status
    ) {}

    interface MaintenanceService {
        VacuumReport vacuum(
            VacuumMode mode,
            long oldestActiveXid,
            long currentXid
        );
    }

    static class TransactionService {

        private final AtomicLong sequence = new AtomicLong(1);

        private final Map<Long, Transaction> transactions =
            new TreeMap<>();

        long begin(String owner) {
            if (owner == null || owner.isBlank()) {
                throw new IllegalArgumentException(
                    "Transaction owner is required"
                );
            }

            long xid = sequence.getAndIncrement();

            transactions.put(
                xid,
                new Transaction(
                    xid,
                    owner,
                    TransactionStatus.ACTIVE
                )
            );

            return xid;
        }

        void commit(long xid) {
            Transaction transaction = transactions.get(xid);

            if (transaction == null ||
                transaction.status() != TransactionStatus.ACTIVE) {
                throw new TransactionException(
                    "Transaction is not active: " + xid
                );
            }

            transactions.put(
                xid,
                new Transaction(
                    xid,
                    transaction.owner(),
                    TransactionStatus.COMMITTED
                )
            );
        }

        long oldestActiveXid() {
            return transactions.values()
                .stream()
                .filter(t ->
                    t.status() == TransactionStatus.ACTIVE
                )
                .mapToLong(Transaction::xid)
                .min()
                .orElse(sequence.get());
        }

        long currentXid() {
            return sequence.get();
        }

        long activeCount() {
            return transactions.values()
                .stream()
                .filter(t ->
                    t.status() == TransactionStatus.ACTIVE
                )
                .count();
        }
    }

    static class Page {

        private final int id;
        private final int capacity;
        private final List<Long> tupleIds = new ArrayList<>();

        Page(int id, int capacity) {
            this.id = id;
            this.capacity = capacity;
        }

        boolean hasSpace(Map<Long, Tuple> tuples) {
            long occupied = tupleIds.stream()
                .map(tuples::get)
                .filter(Objects::nonNull)
                .filter(t -> t.state() != TupleState.REMOVED)
                .count();

            return occupied < capacity;
        }

        int id() {
            return id;
        }

        void add(long tupleId) {
            tupleIds.add(tupleId);
        }
    }

    static class Relation implements MaintenanceService {

        private final String name;
        private final int pageCapacity;

        private long nextTupleId = 1;

        private final Map<Long, Tuple> tuples =
            new LinkedHashMap<>();

        private final List<Page> pages =
            new ArrayList<>();

        Relation(String name, int pageCapacity) {
            if (name == null || name.isBlank() ||
                pageCapacity < 1) {
                throw new IllegalArgumentException(
                    "Invalid relation configuration"
                );
            }

            this.name = name;
            this.pageCapacity = pageCapacity;
        }

        private Page availablePage() {
            for (int i = pages.size() - 1; i >= 0; i--) {
                Page page = pages.get(i);

                if (page.hasSpace(tuples)) {
                    return page;
                }
            }

            Page page = new Page(
                pages.size(),
                pageCapacity
            );

            pages.add(page);
            return page;
        }

        long insert(String value, long xid) {
            if (value == null || value.isBlank() || xid < 1) {
                throw new StorageException(
                    "Invalid insertion request"
                );
            }

            Page page = availablePage();

            long id = nextTupleId++;

            Tuple tuple = new Tuple(
                id,
                value,
                xid,
                null,
                TupleState.LIVE,
                page.id()
            );

            tuples.put(id, tuple);
            page.add(id);

            return id;
        }

        private Tuple findLive(long id) {
            Tuple tuple = tuples.get(id);

            if (tuple == null || !tuple.isLive()) {
                throw new StorageException(
                    "Live tuple not found: " + id
                );
            }

            return tuple;
        }

        void delete(long id, long xid) {
            Tuple tuple = findLive(id);

            tuples.put(id, tuple.markDead(xid));
        }

        long update(long id, String value, long xid) {
            findLive(id);

            delete(id, xid);

            return insert(value, xid);
        }

        TableStatistics statistics() {
            long live = 0;
            long dead = 0;
            long frozen = 0;

            for (Tuple tuple : tuples.values()) {
                switch (tuple.state()) {
                    case LIVE -> live++;
                    case FROZEN -> {
                        live++;
                        frozen++;
                    }
                    case DEAD -> dead++;
                    case REMOVED -> {
                    }
                }
            }

            double percentage = 100.0 * dead /
                Math.max(live + dead, 1);

            return new TableStatistics(
                live,
                dead,
                frozen,
                pages.size(),
                percentage
            );
        }

        @Override
        public VacuumReport vacuum(
            VacuumMode mode,
            long oldestActiveXid,
            long currentXid
        ) {
            Objects.requireNonNull(mode);

            if (oldestActiveXid < 1 ||
                currentXid < oldestActiveXid) {
                throw new StorageException(
                    "Invalid transaction visibility horizon"
                );
            }

            TableStatistics before = statistics();

            int removed = 0;
            int frozen = 0;

            for (Map.Entry<Long, Tuple> entry :
                tuples.entrySet()) {

                Tuple tuple = entry.getValue();

                if (tuple.state() == TupleState.DEAD &&
                    tuple.xmax() != null &&
                    tuple.xmax() < oldestActiveXid) {

                    entry.setValue(
                        new Tuple(
                            tuple.id(),
                            tuple.value(),
                            tuple.xmin(),
                            tuple.xmax(),
                            TupleState.REMOVED,
                            tuple.pageId()
                        )
                    );

                    removed++;
                }

                if (mode == VacuumMode.FREEZE &&
                    tuple.state() == TupleState.LIVE &&
                    currentXid - tuple.xmin() >= 100) {

                    entry.setValue(tuple.freeze());
                    frozen++;
                }
            }

            if (mode == VacuumMode.FULL) {
                compact();
            }

            TableStatistics after = statistics();

            return new VacuumReport(
                tuples.size(),
                removed,
                frozen,
                after.dead(),
                before.pages(),
                after.pages(),
                Math.max(0, before.pages() - after.pages()),
                mode
            );
        }

        private void compact() {
            // Rebuild page placement without dead row versions.
            pages.clear();

            for (Map.Entry<Long, Tuple> entry :
                tuples.entrySet()) {

                Tuple tuple = entry.getValue();

                if (!tuple.isLive()) {
                    continue;
                }

                Page page;

                if (pages.isEmpty() ||
                    pages.get(pages.size() - 1).tupleIds.size()
                        >= pageCapacity) {

                    page = new Page(
                        pages.size(),
                        pageCapacity
                    );

                    pages.add(page);
                } else {
                    page = pages.get(pages.size() - 1);
                }

                entry.setValue(tuple.relocate(page.id()));
                page.add(tuple.id());
            }
        }

        String getName() {
            return name;
        }
    }

    static class AutovacuumService {

        private final AutovacuumPolicy policy;
        private final TransactionService transactions;

        AutovacuumService(
            AutovacuumPolicy policy,
            TransactionService transactions
        ) {
            this.policy = Objects.requireNonNull(policy);
            this.transactions = Objects.requireNonNull(
                transactions
            );
        }

        Optional<VacuumReport> evaluate(Relation relation) {
            TableStatistics stats = relation.statistics();

            if (!policy.required(stats)) {
                return Optional.empty();
            }

            return Optional.of(
                relation.vacuum(
                    VacuumMode.STANDARD,
                    transactions.oldestActiveXid(),
                    transactions.currentXid()
                )
            );
        }
    }

    static void printStatistics(TableStatistics stats) {
        System.out.println("Live tuples: " + stats.live());
        System.out.println("Dead tuples: " + stats.dead());
        System.out.println("Frozen tuples: " + stats.frozen());
        System.out.println("Physical pages: " + stats.pages());

        System.out.printf(
            Locale.ROOT,
            "Dead percentage: %.2f%%%n",
            stats.deadPercentage()
        );
    }

    static void printReport(VacuumReport report) {
        System.out.println("Mode: " + report.mode());
        System.out.println("Scanned: " + report.scanned());
        System.out.println("Removed: " + report.removed());
        System.out.println("Frozen: " + report.frozen());
        System.out.println(
            "Remaining dead: " + report.deadRemaining()
        );
        System.out.println(
            "Pages reclaimed: " + report.pagesReclaimed()
        );
    }

    public static void main(String[] args) {

        System.out.println(
            "POSTGRESQL VACUUM AND GARBAGE COLLECTION"
        );

        TransactionService transactions =
            new TransactionService();

        Relation orders = new Relation("orders", 10);

        System.out.println("\n1. INITIAL INSERTION");

        long insertXid = transactions.begin("order-service");

        List<Long> identifiers = new ArrayList<>();

        for (int i = 0; i < 35; i++) {
            identifiers.add(
                orders.insert("Order-" + i, insertXid)
            );
        }

        transactions.commit(insertXid);

        printStatistics(orders.statistics());

        System.out.println("\n2. DELETE OPERATIONS");

        long oldXid = transactions.begin("reporting-service");
        long deleteXid = transactions.begin("cleanup-service");

        for (long id : identifiers.subList(0, 15)) {
            orders.delete(id, deleteXid);
        }

        transactions.commit(deleteXid);

        printStatistics(orders.statistics());

        System.out.println("\n3. STANDARD VACUUM");

        printReport(
            orders.vacuum(
                VacuumMode.STANDARD,
                transactions.oldestActiveXid(),
                transactions.currentXid()
            )
        );

        System.out.println("\n4. RELEASE OLD SNAPSHOT");

        transactions.commit(oldXid);

        printReport(
            orders.vacuum(
                VacuumMode.STANDARD,
                transactions.oldestActiveXid(),
                transactions.currentXid()
            )
        );

        System.out.println("\n5. UPDATE OPERATIONS");

        for (long id : identifiers.subList(15, 25)) {
            long xid = transactions.begin("order-update");

            orders.update(
                id,
                "Revised-" + id,
                xid
            );

            transactions.commit(xid);
        }

        printStatistics(orders.statistics());

        System.out.println("\n6. AUTOVACUUM POLICY");

        AutovacuumPolicy policy = new AutovacuumPolicy(
            3,
            0.10,
            0.10
        );

        AutovacuumService autovacuum =
            new AutovacuumService(policy, transactions);

        Optional<VacuumReport> automatic =
            autovacuum.evaluate(orders);

        automatic.ifPresentOrElse(
            VacuumGarbageCollection::printReport,
            () -> System.out.println(
                "Autovacuum threshold not reached"
            )
        );

        System.out.println("\n7. FREEZE");

        printReport(
            orders.vacuum(
                VacuumMode.FREEZE,
                transactions.oldestActiveXid(),
                transactions.currentXid() + 200
            )
        );

        System.out.println("\n8. VACUUM FULL");

        printReport(
            orders.vacuum(
                VacuumMode.FULL,
                transactions.oldestActiveXid(),
                transactions.currentXid() + 200
            )
        );

        System.out.println("\n9. FINAL STATISTICS");

        printStatistics(orders.statistics());

        System.out.println("\n10. FAILURE HANDLING");

        try {
            orders.delete(99999, transactions.currentXid());
        } catch (StorageException exception) {
            System.out.println(
                "Expected failure: " + exception.getMessage()
            );
        }

        try {
            new AutovacuumPolicy(10, 2.0, 0.20);
        } catch (IllegalArgumentException exception) {
            System.out.println(
                "Expected policy failure: " +
                exception.getMessage()
            );
        }

        if (transactions.activeCount() != 0) {
            throw new TransactionException(
                "Unexpected active transactions"
            );
        }

        if (orders.statistics().dead() < 0) {
            throw new StorageException(
                "Invalid dead tuple statistics"
            );
        }

        System.out.println("\nAll validation checks passed.");
    }
}
