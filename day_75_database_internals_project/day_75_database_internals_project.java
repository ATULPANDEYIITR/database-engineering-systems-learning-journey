import java.util.*;
import java.util.function.Predicate;
import java.util.stream.Collectors;

/**
 * Database Internals Project
 *
 * Enterprise database behavior model:
 * storage, buffer management, WAL, transactions,
 * indexing, query execution, and cost estimation.
 *
 * Java 17, standard library only.
 */
public class DatabaseInternals {

    // ========================================================
    // 1. DOMAIN MODEL
    // ========================================================

    enum TransactionState {
        ACTIVE,
        COMMITTED,
        ABORTED
    }

    enum PageType {
        HEAP,
        INDEX
    }

    enum LogOperation {
        INSERT,
        UPDATE,
        DELETE,
        COMMIT,
        ABORT
    }

    record Employee(
        int id,
        String name,
        String department,
        double salary
    ) {
        Employee {
            if (id <= 0) {
                throw new IllegalArgumentException(
                    "Employee ID must be positive."
                );
            }

            if (name == null || name.isBlank()) {
                throw new IllegalArgumentException(
                    "Employee name is required."
                );
            }

            if (department == null || department.isBlank()) {
                throw new IllegalArgumentException(
                    "Department is required."
                );
            }

            if (!Double.isFinite(salary) || salary < 0) {
                throw new IllegalArgumentException(
                    "Salary must be finite and non-negative."
                );
            }
        }
    }

    record LogRecord(
        long lsn,
        int transactionId,
        LogOperation operation,
        int pageId,
        Employee before,
        Employee after
    ) {}

    record IndexLocation(
        int pageId,
        int slot
    ) {}

    record QueryStatistics(
        long rowsRead,
        long rowsReturned,
        long elapsedNanos
    ) {}

    record AggregateResult(
        String department,
        long count,
        double sum,
        double average,
        double minimum,
        double maximum
    ) {}

    // ========================================================
    // 2. CUSTOM EXCEPTIONS
    // ========================================================

    static class DatabaseException extends RuntimeException {
        DatabaseException(String message) {
            super(message);
        }
    }

    static class TransactionException extends DatabaseException {
        TransactionException(String message) {
            super(message);
        }
    }

    static class ConstraintException extends DatabaseException {
        ConstraintException(String message) {
            super(message);
        }
    }

    static class StorageException extends DatabaseException {
        StorageException(String message) {
            super(message);
        }
    }

    // ========================================================
    // 3. STORAGE PAGE
    // ========================================================

    static final class Page {

        private final int id;
        private final PageType type;
        private final List<Employee> records;

        private boolean dirty;
        private long pageLSN;

        Page(int id, PageType type) {
            this.id = id;
            this.type = type;
            this.records = new ArrayList<>();
            this.dirty = false;
            this.pageLSN = 0;
        }

        int id() {
            return id;
        }

        PageType type() {
            return type;
        }

        List<Employee> records() {
            return records;
        }

        boolean dirty() {
            return dirty;
        }

        void markDirty() {
            dirty = true;
        }

        void markClean() {
            dirty = false;
        }

        long pageLSN() {
            return pageLSN;
        }

        void setPageLSN(long pageLSN) {
            this.pageLSN = pageLSN;
        }

        Page copy() {
            Page copy = new Page(id, type);
            copy.records.addAll(records);
            copy.dirty = dirty;
            copy.pageLSN = pageLSN;
            return copy;
        }
    }

    // ========================================================
    // 4. WRITE-AHEAD LOG
    // ========================================================

    static final class WriteAheadLog {

        private final List<LogRecord> records =
            new ArrayList<>();

        private long nextLSN = 1;
        private long durableLSN = 0;

        synchronized long append(
            int transactionId,
            LogOperation operation,
            int pageId,
            Employee before,
            Employee after
        ) {
            LogRecord record = new LogRecord(
                nextLSN++,
                transactionId,
                operation,
                pageId,
                before,
                after
            );

            records.add(record);

            return record.lsn();
        }

        synchronized void flush() {
            if (!records.isEmpty()) {
                durableLSN = records.get(
                    records.size() - 1
                ).lsn();
            }
        }

        synchronized long durableLSN() {
            return durableLSN;
        }

        synchronized List<LogRecord> records() {
            return List.copyOf(records);
        }

        synchronized List<LogRecord> recordsFor(
            int transactionId
        ) {
            return records.stream()
                .filter(record ->
                    record.transactionId() == transactionId
                )
                .toList();
        }
    }

    // ========================================================
    // 5. DISK STORAGE
    // ========================================================

    static final class DiskManager {

        private final Map<Integer, Page> storage =
            new HashMap<>();

        private int nextPageId = 1;

        private long reads = 0;
        private long writes = 0;

        synchronized Page allocate(PageType type) {
            Page page = new Page(nextPageId++, type);
            storage.put(page.id(), page.copy());
            return page;
        }

        synchronized Page read(int pageId) {
            Page page = storage.get(pageId);

            if (page == null) {
                throw new StorageException(
                    "Page does not exist: " + pageId
                );
            }

            reads++;
            return page.copy();
        }

        synchronized void write(
            Page page,
            long durableLSN
        ) {
            if (page.pageLSN() > durableLSN) {
                throw new StorageException(
                    "WAL durability requirement violated."
                );
            }

            storage.put(page.id(), page.copy());
            writes++;
        }

        long reads() {
            return reads;
        }

        long writes() {
            return writes;
        }

        int pageCount() {
            return storage.size();
        }
    }

    // ========================================================
    // 6. BUFFER POOL WITH LRU REPLACEMENT
    // ========================================================

    static final class BufferPool {

        private static final class Frame {
            final Page page;

            Frame(Page page) {
                this.page = page;
            }
        }

        private final int capacity;
        private final DiskManager disk;
        private final WriteAheadLog wal;

        private final LinkedHashMap<Integer, Frame> frames =
            new LinkedHashMap<>(16, 0.75f, true);

        private long hits = 0;
        private long misses = 0;
        private long evictions = 0;

        BufferPool(
            int capacity,
            DiskManager disk,
            WriteAheadLog wal
        ) {
            if (capacity < 1) {
                throw new IllegalArgumentException(
                    "Buffer capacity must be positive."
                );
            }

            this.capacity = capacity;
            this.disk = disk;
            this.wal = wal;
        }

        synchronized Page fetch(int pageId) {
            Frame existing = frames.get(pageId);

            if (existing != null) {
                hits++;
                return existing.page;
            }

            misses++;

            if (frames.size() >= capacity) {
                evict();
            }

            Page page = disk.read(pageId);
            frames.put(pageId, new Frame(page));

            return page;
        }

        synchronized void register(Page page) {
            if (frames.size() >= capacity) {
                evict();
            }

            frames.put(page.id(), new Frame(page));
        }

        private void evict() {
            Iterator<Map.Entry<Integer, Frame>> iterator =
                frames.entrySet().iterator();

            if (!iterator.hasNext()) return;

            Map.Entry<Integer, Frame> victim =
                iterator.next();

            Page page = victim.getValue().page;

            if (page.dirty()) {
                wal.flush();
                disk.write(page, wal.durableLSN());
            }

            iterator.remove();
            evictions++;
        }

        synchronized void flushAll() {
            wal.flush();

            for (Frame frame : frames.values()) {
                Page page = frame.page;

                if (page.dirty()) {
                    disk.write(page, wal.durableLSN());
                    page.markClean();
                }
            }
        }

        double hitRatio() {
            long total = hits + misses;

            return total == 0
                ? 0.0
                : (double) hits / total;
        }

        void printStatistics() {
            System.out.println("Hits: " + hits);
            System.out.println("Misses: " + misses);
            System.out.println("Evictions: " + evictions);
            System.out.printf(
                "Hit ratio: %.2f%%%n",
                hitRatio() * 100
            );
        }
    }

    // ========================================================
    // 7. TRANSACTION AND UNDO MODEL
    // ========================================================

    static final class UndoEntry {
        final int pageId;
        final Employee employee;

        UndoEntry(int pageId, Employee employee) {
            this.pageId = pageId;
            this.employee = employee;
        }
    }

    static final class Transaction {

        private final int id;
        private final Database database;

        private TransactionState state =
            TransactionState.ACTIVE;

        private final List<UndoEntry> undoLog =
            new ArrayList<>();

        Transaction(int id, Database database) {
            this.id = id;
            this.database = database;
        }

        int id() {
            return id;
        }

        TransactionState state() {
            return state;
        }

        void ensureActive() {
            if (state != TransactionState.ACTIVE) {
                throw new TransactionException(
                    "Transaction is not active."
                );
            }
        }

        void insert(String table, Employee employee) {
            ensureActive();
            database.insert(this, table, employee);
        }

        void commit() {
            ensureActive();
            database.commit(this);
        }

        void rollback() {
            ensureActive();
            database.rollback(this);
        }
    }

    // ========================================================
    // 8. DATABASE SERVICE
    // ========================================================

    static final class Database {

        private final DiskManager disk =
            new DiskManager();

        private final WriteAheadLog wal =
            new WriteAheadLog();

        private final BufferPool buffer;

        private final Map<String, List<Integer>> tables =
            new HashMap<>();

        private final Map<Integer, IndexLocation> primaryIndex =
            new HashMap<>();

        private int nextTransactionId = 1;

        Database(int bufferCapacity) {
            buffer = new BufferPool(
                bufferCapacity,
                disk,
                wal
            );
        }

        synchronized Transaction begin() {
            return new Transaction(
                nextTransactionId++,
                this
            );
        }

        synchronized void insert(
            Transaction transaction,
            String table,
            Employee employee
        ) {
            transaction.ensureActive();

            if (table == null ||
                !table.matches("[A-Za-z_][A-Za-z0-9_]*")) {
                throw new ConstraintException(
                    "Invalid table identifier."
                );
            }

            if (primaryIndex.containsKey(employee.id())) {
                throw new ConstraintException(
                    "Duplicate primary key: " + employee.id()
                );
            }

            List<Integer> pageIds = tables.computeIfAbsent(
                table,
                ignored -> new ArrayList<>()
            );

            Page target = null;

            for (int pageId : pageIds) {
                Page page = buffer.fetch(pageId);

                if (page.records().size() < 3) {
                    target = page;
                    break;
                }
            }

            if (target == null) {
                target = disk.allocate(PageType.HEAP);
                pageIds.add(target.id());
                buffer.register(target);
            }

            int slot = target.records().size();

            long lsn = wal.append(
                transaction.id(),
                LogOperation.INSERT,
                target.id(),
                null,
                employee
            );

            target.records().add(employee);
            target.setPageLSN(lsn);
            target.markDirty();

            primaryIndex.put(
                employee.id(),
                new IndexLocation(target.id(), slot)
            );

            transaction.undoLog.add(
                new UndoEntry(target.id(), employee)
            );
        }

        synchronized Optional<Employee> findById(int id) {
            IndexLocation location = primaryIndex.get(id);

            if (location == null) {
                return Optional.empty();
            }

            Page page = buffer.fetch(location.pageId());

            if (location.slot() >= page.records().size()) {
                throw new StorageException(
                    "Index points to an invalid slot."
                );
            }

            return Optional.of(
                page.records().get(location.slot())
            );
        }

        synchronized List<Employee> scan(String table) {
            List<Employee> result = new ArrayList<>();

            for (int pageId : tables.getOrDefault(
                table,
                List.of()
            )) {
                result.addAll(
                    buffer.fetch(pageId).records()
                );
            }

            return result;
        }

        synchronized void commit(Transaction transaction) {
            transaction.ensureActive();

            wal.append(
                transaction.id(),
                LogOperation.COMMIT,
                0,
                null,
                null
            );

            wal.flush();
            buffer.flushAll();

            transaction.undoLog.clear();
            transaction.state = TransactionState.COMMITTED;
        }

        synchronized void rollback(Transaction transaction) {
            transaction.ensureActive();

            List<UndoEntry> entries =
                transaction.undoLog;

            for (int i = entries.size() - 1; i >= 0; i--) {
                UndoEntry entry = entries.get(i);

                Page page = buffer.fetch(entry.pageId);

                boolean removed = page.records().remove(
                    entry.employee
                );

                if (!removed) {
                    throw new StorageException(
                        "Undo record was not found."
                    );
                }

                page.markDirty();

                primaryIndex.remove(entry.employee.id());

                // Rebuild locations because removing an array-list
                // element shifts the subsequent slot positions.
                for (int slot = 0;
                     slot < page.records().size();
                     slot++) {
                    Employee remaining = page.records().get(slot);

                    primaryIndex.put(
                        remaining.id(),
                        new IndexLocation(page.id(), slot)
                    );
                }
            }

            wal.append(
                transaction.id(),
                LogOperation.ABORT,
                0,
                null,
                null
            );

            wal.flush();
            buffer.flushAll();

            transaction.undoLog.clear();
            transaction.state = TransactionState.ABORTED;
        }

        void flush() {
            buffer.flushAll();
        }

        void printStatistics() {
            System.out.println(
                "Allocated pages: " + disk.pageCount()
            );

            System.out.println(
                "WAL records: " + wal.records().size()
            );

            System.out.println(
                "Disk reads: " + disk.reads()
            );

            System.out.println(
                "Disk writes: " + disk.writes()
            );

            buffer.printStatistics();
        }
    }

    // ========================================================
    // 9. QUERY EXECUTION INTERFACE
    // ========================================================

    interface QueryOperator<T> {
        List<T> execute();
    }

    static final class TableScan
        implements QueryOperator<Employee> {

        private final Database database;
        private final String table;

        TableScan(Database database, String table) {
            this.database = database;
            this.table = table;
        }

        @Override
        public List<Employee> execute() {
            return database.scan(table);
        }
    }

    static final class Filter
        implements QueryOperator<Employee> {

        private final QueryOperator<Employee> child;
        private final Predicate<Employee> predicate;

        Filter(
            QueryOperator<Employee> child,
            Predicate<Employee> predicate
        ) {
            this.child = child;
            this.predicate = predicate;
        }

        @Override
        public List<Employee> execute() {
            return child.execute()
                .stream()
                .filter(predicate)
                .toList();
        }
    }

    static final class Sort
        implements QueryOperator<Employee> {

        private final QueryOperator<Employee> child;

        Sort(QueryOperator<Employee> child) {
            this.child = child;
        }

        @Override
        public List<Employee> execute() {
            return child.execute()
                .stream()
                .sorted(
                    Comparator.comparingDouble(
                        Employee::salary
                    ).reversed()
                )
                .toList();
        }
    }

    // ========================================================
    // 10. GROUP AGGREGATION
    // ========================================================

    static List<AggregateResult> aggregate(
        List<Employee> employees
    ) {
        Map<String, List<Double>> groups =
            employees.stream().collect(
                Collectors.groupingBy(
                    Employee::department,
                    Collectors.mapping(
                        Employee::salary,
                        Collectors.toList()
                    )
                )
            );

        return groups.entrySet()
            .stream()
            .map(entry -> {
                List<Double> salaries = entry.getValue();

                double sum = salaries.stream()
                    .mapToDouble(Double::doubleValue)
                    .sum();

                double minimum = salaries.stream()
                    .mapToDouble(Double::doubleValue)
                    .min()
                    .orElseThrow();

                double maximum = salaries.stream()
                    .mapToDouble(Double::doubleValue)
                    .max()
                    .orElseThrow();

                return new AggregateResult(
                    entry.getKey(),
                    salaries.size(),
                    sum,
                    sum / salaries.size(),
                    minimum,
                    maximum
                );
            })
            .toList();
    }

    // ========================================================
    // 11. COST-BASED QUERY PLANNER
    // ========================================================

    static final class QueryPlanner {

        record Plan(
            String accessPath,
            double scanCost,
            double indexCost
        ) {}

        Plan choose(
            long rowCount,
            long distinctValues,
            int rowsPerPage
        ) {
            if (rowCount < 0 ||
                distinctValues < 0 ||
                rowsPerPage <= 0) {
                throw new IllegalArgumentException(
                    "Invalid statistics."
                );
            }

            double scanCost = Math.ceil(
                (double) rowCount / rowsPerPage
            );

            double indexCost;

            if (rowCount == 0 || distinctValues == 0) {
                indexCost = Double.POSITIVE_INFINITY;
            } else {
                indexCost = Math.log(
                    Math.max(2, rowCount)
                ) / Math.log(2)
                    + (double) rowCount / distinctValues;
            }

            return new Plan(
                indexCost < scanCost
                    ? "INDEX_SCAN"
                    : "TABLE_SCAN",
                scanCost,
                indexCost
            );
        }
    }

    // ========================================================
    // 12. EXECUTION AND VALIDATION
    // ========================================================

    public static void main(String[] args) {

        Database database = new Database(2);

        Transaction transaction = database.begin();

        try {
            transaction.insert(
                "employees",
                new Employee(
                    101,
                    "Asha",
                    "Engineering",
                    90000
                )
            );

            transaction.insert(
                "employees",
                new Employee(
                    102,
                    "Ravi",
                    "Engineering",
                    85000
                )
            );

            transaction.insert(
                "employees",
                new Employee(
                    103,
                    "Meera",
                    "Research",
                    110000
                )
            );

            transaction.insert(
                "employees",
                new Employee(
                    104,
                    "Kabir",
                    "Research",
                    95000
                )
            );

            transaction.commit();

        } catch (RuntimeException exception) {
            if (transaction.state() ==
                TransactionState.ACTIVE) {
                transaction.rollback();
            }

            throw exception;
        }

        System.out.println("\nPRIMARY INDEX LOOKUP");

        Optional<Employee> employee =
            database.findById(103);

        employee.ifPresent(System.out::println);

        System.out.println("\nQUERY EXECUTION");

        long start = System.nanoTime();

        QueryOperator<Employee> query =
            new Sort(
                new Filter(
                    new TableScan(
                        database,
                        "employees"
                    ),
                    employeeRecord ->
                        employeeRecord.salary() >= 90000
                )
            );

        List<Employee> results = query.execute();

        long elapsed = System.nanoTime() - start;

        results.forEach(System.out::println);

        QueryStatistics statistics =
            new QueryStatistics(
                database.scan("employees").size(),
                results.size(),
                elapsed
            );

        System.out.println("\nQUERY METRICS");
        System.out.println(statistics);

        System.out.println("\nGROUP AGGREGATION");

        aggregate(
            database.scan("employees")
        ).forEach(System.out::println);

        System.out.println("\nQUERY PLAN");

        QueryPlanner planner = new QueryPlanner();

        QueryPlanner.Plan plan = planner.choose(
            100000,
            100000,
            64
        );

        System.out.println(plan);

        System.out.println("\nROLLBACK TEST");

        Transaction rollbackTransaction =
            database.begin();

        rollbackTransaction.insert(
            "employees",
            new Employee(
                105,
                "Temporary",
                "Testing",
                50000
            )
        );

        rollbackTransaction.rollback();

        if (database.findById(105).isEmpty()) {
            System.out.println(
                "Rollback verification: PASSED"
            );
        } else {
            throw new DatabaseException(
                "Rollback verification failed."
            );
        }

        System.out.println("\nDATABASE STATISTICS");
        database.printStatistics();

        System.out.println("\nALL TESTS PASSED");
    }
}
