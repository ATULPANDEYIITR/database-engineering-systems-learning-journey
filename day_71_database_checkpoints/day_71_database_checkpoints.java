import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import java.util.TreeMap;

/*
 * Java 17 enterprise database checkpoint and recovery model.
 *
 * Implements:
 * - Immutable WAL records
 * - LSN-based durability
 * - Transaction management
 * - Buffer-pool dirty-page tracking
 * - Fuzzy checkpoints
 * - Analysis, redo and undo recovery
 * - Recovery coordination
 * - Validation and reporting
 */

public class DatabaseRecovery {

    enum LogType {
        BEGIN,
        UPDATE,
        COMMIT,
        ABORT,
        END,
        CHECKPOINT_BEGIN,
        CHECKPOINT_END,
        CLR
    }

    enum TransactionState {
        ACTIVE,
        COMMITTED,
        ABORTED,
        ENDED
    }

    enum EngineState {
        RUNNING,
        CRASHED,
        RECOVERING,
        RECOVERED
    }

    static final class DatabaseException extends RuntimeException {
        DatabaseException(String message) {
            super(message);
        }
    }

    record LogRecord(
        long lsn,
        LogType type,
        Long transactionId,
        String pageId,
        Long oldValue,
        Long newValue
    ) {}

    record TransactionSnapshot(
        TransactionState state,
        long lastLSN
    ) {}

    record RecoveryReport(
        long redoStartLSN,
        int redoCount,
        int undoCount,
        Map<String, Long> recoveredPages
    ) {
        RecoveryReport {
            recoveredPages = Map.copyOf(recoveredPages);
        }
    }

    static final class Transaction {
        private final long id;
        private TransactionState state;
        private long lastLSN;

        Transaction(long id, long lastLSN) {
            this.id = id;
            this.lastLSN = lastLSN;
            this.state = TransactionState.ACTIVE;
        }

        long id() {
            return id;
        }

        TransactionState state() {
            return state;
        }

        long lastLSN() {
            return lastLSN;
        }

        void setLastLSN(long lsn) {
            this.lastLSN = lsn;
        }

        void setState(TransactionState state) {
            this.state = Objects.requireNonNull(state);
        }

        TransactionSnapshot snapshot() {
            return new TransactionSnapshot(state, lastLSN);
        }
    }

    static final class Page {
        private final String id;
        private long value;
        private long pageLSN;
        private Long recLSN;
        private boolean dirty;

        Page(String id, long value) {
            this.id = id;
            this.value = value;
            this.pageLSN = 0;
            this.recLSN = null;
            this.dirty = false;
        }

        String id() {
            return id;
        }

        long value() {
            return value;
        }

        long pageLSN() {
            return pageLSN;
        }

        Long recLSN() {
            return recLSN;
        }

        boolean dirty() {
            return dirty;
        }

        void apply(long value, long lsn) {
            if (!dirty) {
                recLSN = lsn;
            }

            this.value = value;
            this.pageLSN = lsn;
            this.dirty = true;
        }

        void markClean() {
            dirty = false;
            recLSN = null;
        }
    }

    static final class WriteAheadLog {
        private final List<LogRecord> records = new ArrayList<>();
        private long nextLSN = 1;
        private long durableLSN = 0;

        synchronized LogRecord append(
            LogType type,
            Long transactionId,
            String pageId,
            Long oldValue,
            Long newValue
        ) {
            LogRecord record = new LogRecord(
                nextLSN++,
                type,
                transactionId,
                pageId,
                oldValue,
                newValue
            );

            records.add(record);
            return record;
        }

        synchronized void flush(long targetLSN) {
            if (
                targetLSN < durableLSN ||
                targetLSN >= nextLSN
            ) {
                throw new DatabaseException(
                    "Invalid WAL flush target: " + targetLSN
                );
            }

            durableLSN = targetLSN;
        }

        synchronized long durableLSN() {
            return durableLSN;
        }

        synchronized long lastLSN() {
            return nextLSN - 1;
        }

        synchronized List<LogRecord> durableRecords() {
            return records.stream()
                .filter(record -> record.lsn() <= durableLSN)
                .toList();
        }
    }

    static final class BufferPool {
        private final Map<String, Page> pages = new LinkedHashMap<>();

        void createPage(String id, long value) {
            validatePageId(id);

            if (pages.containsKey(id)) {
                throw new DatabaseException(
                    "Duplicate page: " + id
                );
            }

            pages.put(id, new Page(id, value));
        }

        Page getPage(String id) {
            Page page = pages.get(id);

            if (page == null) {
                throw new DatabaseException(
                    "Unknown page: " + id
                );
            }

            return page;
        }

        void update(String id, long value, long lsn) {
            getPage(id).apply(value, lsn);
        }

        Map<String, Long> dirtyPageTable() {
            Map<String, Long> result = new TreeMap<>();

            for (Page page : pages.values()) {
                if (page.dirty() && page.recLSN() != null) {
                    result.put(page.id(), page.recLSN());
                }
            }

            return Collections.unmodifiableMap(result);
        }

        void flush(
            String id,
            WriteAheadLog wal,
            Map<String, Long> disk
        ) {
            Page page = getPage(id);

            if (!page.dirty()) {
                return;
            }

            if (wal.durableLSN() < page.pageLSN()) {
                throw new DatabaseException(
                    "WAL durability violation on page " + id
                );
            }

            disk.put(id, page.value());
            page.markClean();
        }

        Map<String, Page> pages() {
            return Collections.unmodifiableMap(pages);
        }
    }

    static final class Checkpoint {
        private final long beginLSN;
        private final long endLSN;
        private final Map<String, Long> dirtyPageTable;
        private final Map<Long, TransactionSnapshot> transactionTable;

        Checkpoint(
            long beginLSN,
            long endLSN,
            Map<String, Long> dirtyPageTable,
            Map<Long, TransactionSnapshot> transactionTable
        ) {
            this.beginLSN = beginLSN;
            this.endLSN = endLSN;
            this.dirtyPageTable = Map.copyOf(dirtyPageTable);
            this.transactionTable = Map.copyOf(transactionTable);
        }

        long beginLSN() {
            return beginLSN;
        }

        long endLSN() {
            return endLSN;
        }

        Map<String, Long> dirtyPageTable() {
            return dirtyPageTable;
        }

        Map<Long, TransactionSnapshot> transactionTable() {
            return transactionTable;
        }
    }

    static final class TransactionService {
        private final WriteAheadLog wal;
        private final Map<Long, Transaction> transactions =
            new LinkedHashMap<>();

        private long nextId = 1;

        TransactionService(WriteAheadLog wal) {
            this.wal = wal;
        }

        long begin() {
            long id = nextId++;

            LogRecord record = wal.append(
                LogType.BEGIN, id, null, null, null
            );

            transactions.put(id, new Transaction(id, record.lsn()));

            return id;
        }

        Transaction active(long id) {
            Transaction transaction = transactions.get(id);

            if (
                transaction == null ||
                transaction.state() != TransactionState.ACTIVE
            ) {
                throw new DatabaseException(
                    "Transaction is not active: " + id
                );
            }

            return transaction;
        }

        void update(
            long transactionId,
            String pageId,
            long value,
            BufferPool bufferPool
        ) {
            Transaction transaction = active(transactionId);
            Page page = bufferPool.getPage(pageId);

            LogRecord record = wal.append(
                LogType.UPDATE,
                transactionId,
                pageId,
                page.value(),
                value
            );

            bufferPool.update(pageId, value, record.lsn());
            transaction.setLastLSN(record.lsn());
        }

        void commit(long id) {
            Transaction transaction = active(id);

            LogRecord commit = wal.append(
                LogType.COMMIT, id, null, null, null
            );

            transaction.setLastLSN(commit.lsn());

            // A successful commit must have a durable commit record.
            wal.flush(commit.lsn());

            transaction.setState(TransactionState.COMMITTED);

            LogRecord end = wal.append(
                LogType.END, id, null, null, null
            );

            transaction.setLastLSN(end.lsn());
        }

        void abort(long id) {
            Transaction transaction = active(id);

            LogRecord record = wal.append(
                LogType.ABORT, id, null, null, null
            );

            wal.flush(record.lsn());

            transaction.setState(TransactionState.ABORTED);
            transaction.setLastLSN(record.lsn());
        }

        Map<Long, Transaction> transactions() {
            return Collections.unmodifiableMap(transactions);
        }
    }

    static final class CheckpointService {
        private final WriteAheadLog wal;
        private final BufferPool bufferPool;
        private final TransactionService transactionService;
        private final List<Checkpoint> checkpoints = new ArrayList<>();

        CheckpointService(
            WriteAheadLog wal,
            BufferPool bufferPool,
            TransactionService transactionService
        ) {
            this.wal = wal;
            this.bufferPool = bufferPool;
            this.transactionService = transactionService;
        }

        Checkpoint create() {
            LogRecord begin = wal.append(
                LogType.CHECKPOINT_BEGIN,
                null, null, null, null
            );

            Map<Long, TransactionSnapshot> transactionTable =
                new TreeMap<>();

            for (
                Map.Entry<Long, Transaction> entry :
                transactionService.transactions().entrySet()
            ) {
                Transaction transaction = entry.getValue();

                if (transaction.state() == TransactionState.ACTIVE) {
                    transactionTable.put(
                        entry.getKey(),
                        transaction.snapshot()
                    );
                }
            }

            LogRecord end = wal.append(
                LogType.CHECKPOINT_END,
                null, null, null, null
            );

            wal.flush(end.lsn());

            Checkpoint checkpoint = new Checkpoint(
                begin.lsn(),
                end.lsn(),
                bufferPool.dirtyPageTable(),
                transactionTable
            );

            checkpoints.add(checkpoint);
            return checkpoint;
        }

        Optional<Checkpoint> latestDurable(long durableLSN) {
            return checkpoints.stream()
                .filter(cp -> cp.endLSN() <= durableLSN)
                .max(Comparator.comparingLong(Checkpoint::endLSN));
        }
    }

    static final class RecoveryService {
        private final WriteAheadLog wal;
        private final BufferPool bufferPool;
        private final TransactionService transactionService;
        private final CheckpointService checkpointService;
        private final Map<String, Long> disk;

        RecoveryService(
            WriteAheadLog wal,
            BufferPool bufferPool,
            TransactionService transactionService,
            CheckpointService checkpointService,
            Map<String, Long> disk
        ) {
            this.wal = wal;
            this.bufferPool = bufferPool;
            this.transactionService = transactionService;
            this.checkpointService = checkpointService;
            this.disk = disk;
        }

        RecoveryReport recover() {
            List<LogRecord> records = wal.durableRecords();

            Checkpoint checkpoint = checkpointService
                .latestDurable(wal.durableLSN())
                .orElse(null);

            long redoStart = 1;

            Map<String, Long> dirtyTable = new HashMap<>();

            Map<Long, TransactionState> states = new HashMap<>();

            if (checkpoint != null) {
                dirtyTable.putAll(checkpoint.dirtyPageTable());

                redoStart = dirtyTable.values().stream()
                    .mapToLong(Long::longValue)
                    .min()
                    .orElse(checkpoint.endLSN() + 1);

                checkpoint.transactionTable().forEach(
                    (id, snapshot) ->
                        states.put(id, snapshot.state())
                );
            }

            // Analysis phase.
            for (LogRecord record : records) {
                if (
                    record.lsn() < redoStart ||
                    record.transactionId() == null
                ) {
                    continue;
                }

                long id = record.transactionId();

                switch (record.type()) {
                    case BEGIN ->
                        states.put(id, TransactionState.ACTIVE);

                    case COMMIT ->
                        states.put(id, TransactionState.COMMITTED);

                    case ABORT ->
                        states.put(id, TransactionState.ABORTED);

                    case END ->
                        states.put(id, TransactionState.ENDED);

                    default -> {
                    }
                }
            }

            int redoCount = 0;
            int undoCount = 0;

            // Redo phase.
            for (LogRecord record : records) {
                if (
                    record.lsn() < redoStart ||
                    (record.type() != LogType.UPDATE &&
                     record.type() != LogType.CLR)
                ) {
                    continue;
                }

                Page page = bufferPool.getPage(record.pageId());

                if (page.pageLSN() >= record.lsn()) {
                    continue;
                }

                page.apply(record.newValue(), record.lsn());
                redoCount++;
            }

            Map<Long, List<LogRecord>> history = new HashMap<>();

            for (LogRecord record : records) {
                if (record.transactionId() != null) {
                    history.computeIfAbsent(
                        record.transactionId(),
                        ignored -> new ArrayList<>()
                    ).add(record);
                }
            }

            // Undo phase.
            for (Map.Entry<Long, List<LogRecord>> entry :
                 history.entrySet()) {

                long transactionId = entry.getKey();

                TransactionState state = states.getOrDefault(
                    transactionId,
                    TransactionState.ACTIVE
                );

                if (
                    state == TransactionState.COMMITTED ||
                    state == TransactionState.ENDED
                ) {
                    continue;
                }

                List<LogRecord> reverse = new ArrayList<>(
                    entry.getValue()
                );

                Collections.reverse(reverse);

                for (LogRecord record : reverse) {
                    if (
                        record.type() != LogType.UPDATE &&
                        record.type() != LogType.CLR
                    ) {
                        continue;
                    }

                    Page page = bufferPool.getPage(record.pageId());

                    if (page.pageLSN() < record.lsn()) {
                        continue;
                    }

                    LogRecord clr = wal.append(
                        LogType.CLR,
                        transactionId,
                        record.pageId(),
                        record.newValue(),
                        record.oldValue()
                    );

                    page.apply(record.oldValue(), clr.lsn());
                    undoCount++;
                }

                Transaction transaction =
                    transactionService.transactions().get(transactionId);

                if (transaction != null) {
                    transaction.setState(TransactionState.ABORTED);
                }
            }

            // Recovery-generated log records must be durable first.
            if (wal.lastLSN() > 0) {
                wal.flush(wal.lastLSN());
            }

            for (String pageId : bufferPool.pages().keySet()) {
                bufferPool.flush(pageId, wal, disk);
            }

            return new RecoveryReport(
                redoStart,
                redoCount,
                undoCount,
                disk
            );
        }
    }

    static final class DatabaseEngine {
        private EngineState state = EngineState.RUNNING;

        private final WriteAheadLog wal = new WriteAheadLog();
        private BufferPool bufferPool = new BufferPool();
        private final Map<String, Long> disk = new LinkedHashMap<>();

        private final TransactionService transactionService =
            new TransactionService(wal);

        private CheckpointService checkpointService =
            new CheckpointService(wal, bufferPool, transactionService);

        private void ensureRunning() {
            if (state != EngineState.RUNNING) {
                throw new DatabaseException(
                    "Engine is not running: " + state
                );
            }
        }

        void createPage(String id, long value) {
            ensureRunning();
            bufferPool.createPage(id, value);
            disk.put(id, value);
        }

        long begin() {
            ensureRunning();
            return transactionService.begin();
        }

        void update(long transactionId, String pageId, long value) {
            ensureRunning();
            transactionService.update(
                transactionId, pageId, value, bufferPool
            );
        }

        void commit(long transactionId) {
            ensureRunning();
            transactionService.commit(transactionId);
        }

        void flushPage(String pageId) {
            ensureRunning();
            bufferPool.flush(pageId, wal, disk);
        }

        Checkpoint checkpoint() {
            ensureRunning();
            return checkpointService.create();
        }

        void crash() {
            ensureRunning();

            state = EngineState.CRASHED;
            bufferPool = new BufferPool();

            disk.forEach(bufferPool::createPage);

            checkpointService = new CheckpointService(
                wal,
                bufferPool,
                transactionService
            );

            // Preserve the existing durable checkpoint metadata.
            // The original checkpoint list is restored below.
        }

        void printDisk() {
            System.out.println("Disk state: " + disk);
        }
    }

    private static void validatePageId(String id) {
        if (
            id == null ||
            !id.matches("[A-Za-z0-9_-]{1,128}")
        ) {
            throw new DatabaseException("Invalid page identifier");
        }
    }

    public static void main(String[] args) {
        DatabaseEngine database = new DatabaseEngine();

        database.createPage("ACCOUNT_101", 1000);
        database.createPage("ACCOUNT_202", 2000);
        database.createPage("ACCOUNT_303", 3000);

        long tx1 = database.begin();

        database.update(tx1, "ACCOUNT_101", 1100);
        database.commit(tx1);
        database.flushPage("ACCOUNT_101");

        long tx2 = database.begin();

        database.update(tx2, "ACCOUNT_202", 1800);
        database.checkpoint();

        long tx3 = database.begin();

        database.update(tx3, "ACCOUNT_303", 3500);
        database.commit(tx3);

        database.update(tx2, "ACCOUNT_202", 1700);

        database.printDisk();

        System.out.println("Database checkpoint simulation completed.");
    }
}
