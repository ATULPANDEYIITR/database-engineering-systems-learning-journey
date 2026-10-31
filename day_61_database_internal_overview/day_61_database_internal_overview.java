import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import java.util.Set;
import java.util.TreeMap;
import java.util.HashSet;

/*
 * Database Internals Overview
 * Query Engine, Storage Engine, and Buffer Manager
 *
 * Java 17 enterprise-oriented model.
 *
 * The implementation separates:
 * - storage pages
 * - disk management
 * - buffer management
 * - secondary indexing
 * - query execution
 * - transaction state
 * - merge-free state transitions
 *
 * It uses records, enums, interfaces, collections, custom exceptions,
 * immutable domain values, and explicit service boundaries.
 */

public class DatabaseInternalsDemo {

    private static final int PAGE_CAPACITY = 6;
    private static final int BUFFER_POOL_CAPACITY = 3;

    enum PageType {
        HEAP,
        INDEX
    }

    enum TransactionState {
        ACTIVE,
        COMMITTED,
        ROLLED_BACK
    }

    record Row(
        int rowId,
        int customerId,
        String name,
        double balance
    ) {
        Row {
            if (rowId <= 0) {
                throw new ValidationException(
                    "rowId must be positive"
                );
            }

            if (customerId <= 0) {
                throw new ValidationException(
                    "customerId must be positive"
                );
            }

            if (name == null || name.isBlank() || name.length() > 80) {
                throw new ValidationException(
                    "name must contain 1-80 characters"
                );
            }

            if (!Double.isFinite(balance) ||
                balance < -10_000_000 ||
                balance > 10_000_000) {
                throw new ValidationException(
                    "balance is outside the supported range"
                );
            }
        }
    }

    record LogEntry(
        long lsn,
        int transactionId,
        int pageId,
        int rowId,
        double oldBalance,
        double newBalance
    ) {}

    static final class ValidationException
        extends RuntimeException {

        ValidationException(String message) {
            super(message);
        }
    }

    static final class StorageException
        extends RuntimeException {

        StorageException(String message) {
            super(message);
        }
    }

    static final class TransactionException
        extends RuntimeException {

        TransactionException(String message) {
            super(message);
        }
    }

    static final class Page {
        private final int id;
        private final PageType type;
        private final List<Row> rows = new ArrayList<>();
        private boolean dirty;
        private long lsn;

        Page(int id, PageType type) {
            this.id = id;
            this.type = Objects.requireNonNull(type);
        }

        int id() {
            return id;
        }

        PageType type() {
            return type;
        }

        boolean dirty() {
            return dirty;
        }

        void markDirty(boolean value) {
            dirty = value;
        }

        long lsn() {
            return lsn;
        }

        void setLsn(long value) {
            lsn = value;
        }

        List<Row> rows() {
            return rows;
        }

        void insert(Row row) {
            if (rows.size() >= PAGE_CAPACITY) {
                throw new StorageException(
                    "page " + id + " is full"
                );
            }

            rows.add(row);
            dirty = true;
        }

        Optional<Row> find(int rowId) {
            return rows.stream()
                .filter(row -> row.rowId() == rowId)
                .findFirst();
        }

        Row replaceBalance(int rowId, double balance) {
            if (!Double.isFinite(balance)) {
                throw new ValidationException(
                    "balance must be finite"
                );
            }

            for (int i = 0; i < rows.size(); i++) {
                Row current = rows.get(i);

                if (current.rowId() == rowId) {
                    Row replacement = new Row(
                        current.rowId(),
                        current.customerId(),
                        current.name(),
                        balance
                    );

                    rows.set(i, replacement);
                    dirty = true;

                    return current;
                }
            }

            throw new StorageException(
                "row " + rowId + " not found in page"
            );
        }
    }

    interface PageStore {
        Page read(int pageId);
        void write(Page page);
        Page allocate(PageType type);
    }

    static final class InMemoryDisk
        implements PageStore {

        private final Map<Integer, Page> pages =
            new TreeMap<>();

        private int nextPageId = 1;

        @Override
        public Page allocate(PageType type) {
            Page page = new Page(nextPageId++, type);
            pages.put(page.id(), page);
            return page;
        }

        @Override
        public Page read(int pageId) {
            Page source = pages.get(pageId);

            if (source == null) {
                throw new StorageException(
                    "page " + pageId + " does not exist"
                );
            }

            return copyOf(source);
        }

        @Override
        public void write(Page page) {
            if (!pages.containsKey(page.id())) {
                throw new StorageException(
                    "cannot write unknown page"
                );
            }

            Page persisted = copyOf(page);
            persisted.markDirty(false);
            pages.put(page.id(), persisted);
        }

        List<Page> allPages() {
            return new ArrayList<>(pages.values());
        }

        private static Page copyOf(Page source) {
            Page copy = new Page(
                source.id(),
                source.type()
            );

            copy.rows().addAll(source.rows());
            copy.markDirty(source.dirty());
            copy.setLsn(source.lsn());

            return copy;
        }
    }

    static final class BufferManager {
        private final PageStore store;
        private final int capacity;

        /*
         * accessOrder=true makes LinkedHashMap behave as an LRU map.
         * The eldest entry is the next eviction candidate.
         */
        private final LinkedHashMap<Integer, Page> frames =
            new LinkedHashMap<>(16, 0.75f, true);

        private long hits;
        private long misses;
        private long evictions;
        private long diskWrites;

        BufferManager(PageStore store, int capacity) {
            if (capacity <= 0) {
                throw new ValidationException(
                    "buffer capacity must be positive"
                );
            }

            this.store = store;
            this.capacity = capacity;
        }

        Page fetch(int pageId) {
            Page cached = frames.get(pageId);

            if (cached != null) {
                hits++;
                return cached;
            }

            misses++;

            if (frames.size() >= capacity) {
                evictLeastRecentlyUsed();
            }

            Page loaded = store.read(pageId);
            frames.put(pageId, loaded);

            return loaded;
        }

        void markDirty(int pageId, long lsn) {
            Page page = fetch(pageId);
            page.markDirty(true);
            page.setLsn(lsn);
        }

        void flushAll() {
            for (Page page : frames.values()) {
                if (page.dirty()) {
                    store.write(page);
                    page.markDirty(false);
                    diskWrites++;
                }
            }
        }

        private void evictLeastRecentlyUsed() {
            Integer oldest = frames.keySet()
                .iterator()
                .next();

            Page page = frames.remove(oldest);

            if (page == null) {
                throw new StorageException(
                    "buffer metadata is inconsistent"
                );
            }

            if (page.dirty()) {
                store.write(page);
                diskWrites++;
            }

            evictions++;
        }

        double hitRate() {
            long accesses = hits + misses;
            return accesses == 0
                ? 0
                : (double) hits / accesses;
        }

        String statistics() {
            return String.format(
                "hits=%d, misses=%d, evictions=%d, "
                    + "diskWrites=%d, hitRate=%.3f",
                hits,
                misses,
                evictions,
                diskWrites,
                hitRate()
            );
        }
    }

    static final class RepositoryTable {
        private final PageStore store;
        private final BufferManager buffer;

        private final List<Integer> pageIds =
            new ArrayList<>();

        private final Map<Integer, Integer> locator =
            new HashMap<>();

        RepositoryTable(
            PageStore store,
            BufferManager buffer
        ) {
            this.store = store;
            this.buffer = buffer;
        }

        int insert(Row row) {
            if (locator.containsKey(row.rowId())) {
                throw new ValidationException(
                    "duplicate row " + row.rowId()
                );
            }

            Page target = null;

            for (int i = pageIds.size() - 1; i >= 0; i--) {
                Page page = buffer.fetch(pageIds.get(i));

                if (page.rows().size() < PAGE_CAPACITY) {
                    target = page;
                    break;
                }
            }

            if (target == null) {
                target = store.allocate(PageType.HEAP);
                pageIds.add(target.id());
                target = buffer.fetch(target.id());
            }

            target.insert(row);
            locator.put(row.rowId(), target.id());

            return target.id();
        }

        Optional<Row> find(int rowId) {
            Integer pageId = locator.get(rowId);

            if (pageId == null) {
                return Optional.empty();
            }

            return buffer.fetch(pageId).find(rowId);
        }

        Row updateBalance(
            int rowId,
            double newBalance
        ) {
            Integer pageId = locator.get(rowId);

            if (pageId == null) {
                throw new StorageException(
                    "row " + rowId + " does not exist"
                );
            }

            return buffer
                .fetch(pageId)
                .replaceBalance(rowId, newBalance);
        }

        List<Row> scan() {
            List<Row> result = new ArrayList<>();

            for (int pageId : pageIds) {
                result.addAll(
                    buffer.fetch(pageId).rows()
                );
            }

            return result;
        }

        int pageOf(int rowId) {
            Integer pageId = locator.get(rowId);

            if (pageId == null) {
                throw new StorageException(
                    "row locator missing"
                );
            }

            return pageId;
        }

        int pageCount() {
            return pageIds.size();
        }
    }

    static final class CustomerIndex {
        private final Map<Integer, Set<Integer>> entries =
            new TreeMap<>();

        void rebuild(RepositoryTable table) {
            entries.clear();

            for (Row row : table.scan()) {
                entries
                    .computeIfAbsent(
                        row.customerId(),
                        ignored -> new HashSet<>()
                    )
                    .add(table.pageOf(row.rowId()));
            }
        }

        Set<Integer> pagesFor(int customerId) {
            return entries.getOrDefault(
                customerId,
                Set.of()
            );
        }
    }

    interface QueryPlan {
        List<Row> execute();
    }

    static final class SequentialScanPlan
        implements QueryPlan {

        private final RepositoryTable table;
        private final int customerId;

        SequentialScanPlan(
            RepositoryTable table,
            int customerId
        ) {
            this.table = table;
            this.customerId = customerId;
        }

        @Override
        public List<Row> execute() {
            return table.scan()
                .stream()
                .filter(row ->
                    row.customerId() == customerId
                )
                .toList();
        }
    }

    static final class IndexedLookupPlan
        implements QueryPlan {

        private final RepositoryTable table;
        private final CustomerIndex index;
        private final BufferManager buffer;
        private final int customerId;

        IndexedLookupPlan(
            RepositoryTable table,
            CustomerIndex index,
            BufferManager buffer,
            int customerId
        ) {
            this.table = table;
            this.index = index;
            this.buffer = buffer;
            this.customerId = customerId;
        }

        @Override
        public List<Row> execute() {
            List<Row> result = new ArrayList<>();

            for (int pageId : index.pagesFor(customerId)) {
                result.addAll(
                    buffer.fetch(pageId)
                        .rows()
                        .stream()
                        .filter(row ->
                            row.customerId() == customerId
                        )
                        .toList()
                );
            }

            return result;
        }
    }

    static final class TransactionService {
        private final RepositoryTable table;
        private final BufferManager buffer;

        private TransactionState state =
            TransactionState.ACTIVE;

        private long nextLsn = 1;

        private final List<LogEntry> log =
            new ArrayList<>();

        TransactionService(
            RepositoryTable table,
            BufferManager buffer
        ) {
            this.table = table;
            this.buffer = buffer;
        }

        void update(
            int transactionId,
            int rowId,
            double newBalance
        ) {
            requireActive();

            int pageId = table.pageOf(rowId);
            Row oldRow = table.find(rowId)
                .orElseThrow(() ->
                    new StorageException(
                        "row not found"
                    ));

            table.updateBalance(
                rowId,
                newBalance
            );

            LogEntry entry = new LogEntry(
                nextLsn++,
                transactionId,
                pageId,
                rowId,
                oldRow.balance(),
                newBalance
            );

            log.add(entry);
            buffer.markDirty(pageId, entry.lsn());
        }

        void commit() {
            requireActive();
            buffer.flushAll();
            state = TransactionState.COMMITTED;
        }

        void rollback() {
            requireActive();

            List<LogEntry> reverse =
                new ArrayList<>(log);

            java.util.Collections.reverse(reverse);

            for (LogEntry entry : reverse) {
                Page page = buffer.fetch(entry.pageId());

                page.replaceBalance(
                    entry.rowId(),
                    entry.oldBalance()
                );
            }

            buffer.flushAll();
            state = TransactionState.ROLLED_BACK;
        }

        TransactionState state() {
            return state;
        }

        List<LogEntry> log() {
            return List.copyOf(log);
        }

        private void requireActive() {
            if (state != TransactionState.ACTIVE) {
                throw new TransactionException(
                    "transaction is not active"
                );
            }
        }
    }

    static void verifySameRows(
        List<Row> left,
        List<Row> right
    ) {
        Set<Integer> leftIds = left.stream()
            .map(Row::rowId)
            .collect(java.util.stream.Collectors.toSet());

        Set<Integer> rightIds = right.stream()
            .map(Row::rowId)
            .collect(java.util.stream.Collectors.toSet());

        if (!leftIds.equals(rightIds)) {
            throw new IllegalStateException(
                "query plans returned different rows"
            );
        }
    }

    public static void main(String[] args) {
        try {
            InMemoryDisk disk = new InMemoryDisk();

            BufferManager buffer = new BufferManager(
                disk,
                BUFFER_POOL_CAPACITY
            );

            RepositoryTable table =
                new RepositoryTable(disk, buffer);

            List<Row> rows = List.of(
                new Row(1, 101, "Asha", 1250),
                new Row(2, 102, "Ravi", 840),
                new Row(3, 101, "Meera", 2190),
                new Row(4, 103, "Kabir", 450),
                new Row(5, 104, "Nisha", 3300),
                new Row(6, 102, "Arjun", 910),
                new Row(7, 105, "Isha", 720),
                new Row(8, 101, "Dev", 1500)
            );

            rows.forEach(table::insert);

            CustomerIndex index = new CustomerIndex();
            index.rebuild(table);

            QueryPlan sequential =
                new SequentialScanPlan(table, 101);

            QueryPlan indexed =
                new IndexedLookupPlan(
                    table,
                    index,
                    buffer,
                    101
                );

            List<Row> sequentialRows =
                sequential.execute();

            List<Row> indexedRows =
                indexed.execute();

            verifySameRows(
                sequentialRows,
                indexedRows
            );

            TransactionService committed =
                new TransactionService(
                    table,
                    buffer
                );

            committed.update(8001, 1, 1750);
            committed.update(8001, 3, 2490);
            committed.commit();

            if (table.find(1).orElseThrow().balance() != 1750) {
                throw new IllegalStateException(
                    "commit failed"
                );
            }

            TransactionService rolledBack =
                new TransactionService(
                    table,
                    buffer
                );

            rolledBack.update(8002, 1, 9999);
            rolledBack.rollback();

            if (table.find(1).orElseThrow().balance() != 1750) {
                throw new IllegalStateException(
                    "rollback failed"
                );
            }

            System.out.println(
                "Database Internals Demonstration"
            );
            System.out.println(
                "--------------------------------"
            );
            System.out.println(
                "Heap pages: " + table.pageCount()
            );
            System.out.println(
                "Customer 101 rows: "
                    + indexedRows.size()
            );
            System.out.println(
                "Committed state: "
                    + committed.state()
            );
            System.out.println(
                "Rollback state: "
                    + rolledBack.state()
            );
            System.out.println(
                "WAL-style entries: "
                    + committed.log().size()
            );
            System.out.println(
                "Buffer statistics: "
                    + buffer.statistics()
            );

            try {
                table.insert(
                    new Row(
                        1,
                        999,
                        "Duplicate",
                        1
                    )
                );
            } catch (ValidationException error) {
                System.out.println(
                    "Validation failure handled: "
                        + error.getMessage()
                );
            }

        } catch (RuntimeException error) {
            System.err.println(
                "Fatal database-engine error: "
                    + error.getMessage()
            );
            System.exit(1);
        }
    }
}
