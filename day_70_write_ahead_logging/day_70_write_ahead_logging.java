import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.channels.FileChannel;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.zip.CRC32;

/*
 * Write-Ahead Logging: Enterprise Storage and Recovery Model
 *
 * Java 17 features:
 * - Records and enums
 * - Immutable WAL entries
 * - Explicit transaction states
 * - Service-oriented architecture
 * - FileChannel durability
 * - CRC32 integrity
 * - Transaction analysis
 * - REDO and UNDO
 * - Checkpoint management
 * - Recovery validation
 *
 * Compile: javac WALRecovery.java
 * Run: java WALRecovery
 */

public class WALRecovery {

    enum RecordType {
        BEGIN, UPDATE, COMMIT, ABORT, CHECKPOINT
    }

    enum TransactionState {
        ACTIVE, COMMITTED, ABORTED
    }

    static class WALError extends RuntimeException {
        WALError(String message) {
            super(message);
        }

        WALError(String message, Throwable cause) {
            super(message, cause);
        }
    }

    static class IntegrityException extends WALError {
        IntegrityException(String message) {
            super(message);
        }
    }

    record WALRecord(
        long lsn,
        int transactionId,
        RecordType type,
        String key,
        Long oldValue,
        Long newValue,
        long checksum
    ) {
        String payload() {
            return lsn + "|" +
                transactionId + "|" +
                type + "|" +
                (key == null ? "" : key) + "|" +
                (oldValue == null ? "NULL" : oldValue) + "|" +
                (newValue == null ? "NULL" : newValue);
        }

        boolean isValid() {
            return checksum == calculate(payload());
        }

        static long calculate(String payload) {
            CRC32 crc = new CRC32();
            crc.update(payload.getBytes(StandardCharsets.UTF_8));
            return crc.getValue();
        }

        static WALRecord create(
            long lsn,
            int transactionId,
            RecordType type,
            String key,
            Long oldValue,
            Long newValue
        ) {
            String payload = lsn + "|" +
                transactionId + "|" +
                type + "|" +
                (key == null ? "" : key) + "|" +
                (oldValue == null ? "NULL" : oldValue) + "|" +
                (newValue == null ? "NULL" : newValue);

            return new WALRecord(
                lsn,
                transactionId,
                type,
                key,
                oldValue,
                newValue,
                calculate(payload)
            );
        }
    }

    static final class DurableWAL implements AutoCloseable {
        private final Path path;
        private FileChannel channel;
        private final List<WALRecord> records = new ArrayList<>();
        private long nextLSN = 1;

        DurableWAL(Path path) {
            this.path = path;
            open();
        }

        private void open() {
            try {
                channel = FileChannel.open(
                    path,
                    StandardOpenOption.CREATE,
                    StandardOpenOption.READ,
                    StandardOpenOption.WRITE
                );

                load();
            } catch (IOException e) {
                throw new WALError("Unable to open WAL", e);
            }
        }

        private void load() throws IOException {
            records.clear();
            nextLSN = 1;

            channel.position(0);

            ByteBuffer buffer = ByteBuffer.allocate(8192);
            StringBuilder content = new StringBuilder();

            while (channel.read(buffer) > 0) {
                buffer.flip();

                content.append(
                    StandardCharsets.UTF_8.decode(buffer)
                );

                buffer.clear();
            }

            String text = content.toString();
            int lastNewline = text.lastIndexOf('\n');

            if (lastNewline != text.length() - 1) {
                System.out.println("Discarding incomplete WAL tail.");
                channel.truncate(
                    text.substring(0, lastNewline + 1)
                        .getBytes(StandardCharsets.UTF_8).length
                );
                channel.force(true);
                text = text.substring(0, lastNewline + 1);
            }

            for (String line : text.split("\n")) {
                if (line.isEmpty()) continue;

                WALRecord record = parse(line);

                if (record.lsn() != nextLSN ||
                    !record.isValid()) {
                    throw new IntegrityException(
                        "Invalid WAL record at LSN " + record.lsn()
                    );
                }

                records.add(record);
                nextLSN++;
            }

            channel.position(channel.size());
        }

        private WALRecord parse(String line) {
            try {
                String[] fields = line.split("\\|", -1);

                if (fields.length != 7) {
                    throw new IllegalArgumentException(
                        "Incorrect field count"
                    );
                }

                return new WALRecord(
                    Long.parseLong(fields[0]),
                    Integer.parseInt(fields[1]),
                    RecordType.valueOf(fields[2]),
                    fields[3].isEmpty() ? null : fields[3],
                    fields[4].equals("NULL")
                        ? null : Long.parseLong(fields[4]),
                    fields[5].equals("NULL")
                        ? null : Long.parseLong(fields[5]),
                    Long.parseLong(fields[6])
                );
            } catch (RuntimeException e) {
                throw new IntegrityException(
                    "Malformed WAL record: " + e.getMessage()
                );
            }
        }

        synchronized WALRecord append(
            int transactionId,
            RecordType type,
            String key,
            Long oldValue,
            Long newValue
        ) {
            WALRecord record = WALRecord.create(
                nextLSN,
                transactionId,
                type,
                key,
                oldValue,
                newValue
            );

            String serialized = record.payload()
                + "|" + record.checksum() + "\n";

            ByteBuffer buffer = ByteBuffer.wrap(
                serialized.getBytes(StandardCharsets.UTF_8)
            );

            try {
                while (buffer.hasRemaining()) {
                    channel.write(buffer);
                }

                // force(true) requests persistence of file data and metadata.
                channel.force(true);
            } catch (IOException e) {
                throw new WALError("WAL durability failure", e);
            }

            records.add(record);
            nextLSN++;

            return record;
        }

        List<WALRecord> records() {
            return List.copyOf(records);
        }

        @Override
        public void close() {
            try {
                if (channel != null && channel.isOpen()) {
                    channel.force(true);
                    channel.close();
                }
            } catch (IOException e) {
                throw new WALError("Unable to close WAL", e);
            }
        }
    }

    record Transaction(int id, TransactionState state) {}

    static final class TransactionService {
        private final DurableWAL wal;
        private final Map<String, Long> pages = new HashMap<>();
        private final Map<Integer, Transaction> transactions =
            new HashMap<>();
        private final Set<String> dirtyPages = new HashSet<>();

        private int nextTransactionId = 1;

        TransactionService(DurableWAL wal) {
            this.wal = wal;
        }

        Transaction begin() {
            int id = nextTransactionId++;

            wal.append(id, RecordType.BEGIN, null, null, null);

            Transaction tx = new Transaction(
                id, TransactionState.ACTIVE
            );

            transactions.put(id, tx);
            return tx;
        }

        private void requireActive(Transaction tx) {
            Transaction current = transactions.get(tx.id());

            if (current == null ||
                current.state() != TransactionState.ACTIVE ||
                tx.state() != TransactionState.ACTIVE) {
                throw new WALError("Transaction is not active");
            }
        }

        void update(
            Transaction tx,
            String key,
            long newValue
        ) {
            requireActive(tx);

            if (key == null || key.isBlank() ||
                key.length() > 128) {
                throw new IllegalArgumentException(
                    "Invalid database key"
                );
            }

            Long oldValue = pages.get(key);

            // The update is logged and persisted before page modification.
            wal.append(
                tx.id(),
                RecordType.UPDATE,
                key,
                oldValue,
                newValue
            );

            pages.put(key, newValue);
            dirtyPages.add(key);
        }

        void commit(Transaction tx) {
            requireActive(tx);

            wal.append(
                tx.id(), RecordType.COMMIT, null, null, null
            );

            transactions.put(
                tx.id(),
                new Transaction(
                    tx.id(), TransactionState.COMMITTED
                )
            );
        }

        void abort(Transaction tx) {
            requireActive(tx);

            List<WALRecord> records = wal.records();

            for (int i = records.size() - 1; i >= 0; i--) {
                WALRecord record = records.get(i);

                if (record.transactionId() != tx.id() ||
                    record.type() != RecordType.UPDATE) {
                    continue;
                }

                restore(record);
            }

            wal.append(
                tx.id(), RecordType.ABORT, null, null, null
            );

            transactions.put(
                tx.id(),
                new Transaction(
                    tx.id(), TransactionState.ABORTED
                )
            );
        }

        private void restore(WALRecord record) {
            if (record.oldValue() == null) {
                pages.remove(record.key());
            } else {
                pages.put(record.key(), record.oldValue());
            }
        }

        void checkpoint() {
            wal.append(
                0, RecordType.CHECKPOINT, null, null, null
            );

            dirtyPages.clear();
        }

        Map<String, Long> recover() {
            List<WALRecord> records = wal.records();

            Set<Integer> active = new HashSet<>();
            Set<Integer> committed = new HashSet<>();

            // ANALYSIS: classify transactions.
            for (WALRecord record : records) {
                switch (record.type()) {
                    case BEGIN ->
                        active.add(record.transactionId());

                    case COMMIT -> {
                        active.remove(record.transactionId());
                        committed.add(record.transactionId());
                    }

                    case ABORT ->
                        active.remove(record.transactionId());

                    default -> {
                    }
                }
            }

            System.out.println("Committed transactions: " + committed);
            System.out.println("Incomplete transactions: " + active);

            // REDO: replay committed and incomplete transactions.
            for (WALRecord record : records) {
                if (record.type() != RecordType.UPDATE) continue;

                if (committed.contains(record.transactionId()) ||
                    active.contains(record.transactionId())) {
                    pages.put(record.key(), record.newValue());
                }
            }

            // UNDO: process loser transactions backward.
            List<WALRecord> reversed = new ArrayList<>(records);

            reversed.sort(
                Comparator.comparingLong(WALRecord::lsn).reversed()
            );

            for (WALRecord record : reversed) {
                if (record.type() == RecordType.UPDATE &&
                    active.contains(record.transactionId())) {
                    restore(record);
                }
            }

            // Record completed rollback to make repeated recovery safe.
            for (int id : active.stream().sorted().toList()) {
                wal.append(
                    id, RecordType.ABORT, null, null, null
                );
            }

            return Map.copyOf(pages);
        }

        Map<String, Long> snapshot() {
            return Map.copyOf(pages);
        }

        void simulateCrash() {
            pages.clear();
            transactions.clear();
            dirtyPages.clear();
        }
    }

    public static void main(String[] args) {
        Path walPath = Path.of("enterprise_wal.log");

        try {
            java.nio.file.Files.deleteIfExists(walPath);

            try (DurableWAL wal = new DurableWAL(walPath)) {
                TransactionService service =
                    new TransactionService(wal);

                System.out.println("--- NORMAL OPERATIONS ---");

                Transaction first = service.begin();
                service.update(first, "account_A", 1000);
                service.update(first, "account_B", 500);
                service.commit(first);

                Transaction second = service.begin();
                service.update(second, "account_A", 800);
                service.update(second, "account_B", 700);

                System.out.println(
                    "Volatile state: " + service.snapshot()
                );

                service.simulateCrash();
            }

            System.out.println("\n--- CRASH RECOVERY ---");

            try (DurableWAL recoveryWAL =
                     new DurableWAL(walPath)) {

                TransactionService recovery =
                    new TransactionService(recoveryWAL);

                Map<String, Long> recovered = recovery.recover();

                System.out.println("Recovered pages: " + recovered);

                if (!Long.valueOf(1000).equals(
                        recovered.get("account_A")) ||
                    !Long.valueOf(500).equals(
                        recovered.get("account_B"))) {
                    throw new AssertionError(
                        "Recovery produced incorrect values"
                    );
                }

                recovery.simulateCrash();

                Map<String, Long> repeated = recovery.recover();

                if (!recovered.equals(repeated)) {
                    throw new AssertionError(
                        "Recovery is not idempotent"
                    );
                }

                System.out.println("All validations passed.");
            }

        } catch (IOException | RuntimeException error) {
            System.err.println(
                "Storage failure: " + error.getMessage()
            );
            System.exit(1);
        }
    }
}
