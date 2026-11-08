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
import java.util.concurrent.atomic.AtomicLong;
import java.util.stream.Collectors;

/*
 * LSM Trees: Enterprise key-value storage model.
 *
 * Scenario: Financial transaction event storage.
 *
 * Implements:
 * - Immutable domain records
 * - Memtable buffering
 * - Sequence-numbered writes
 * - Write policies
 * - Sorted immutable runs
 * - Bloom filters
 * - Sparse indexes
 * - Tombstones
 * - Size-tiered compaction
 * - Range scans
 * - Storage validation
 * - Merge and compaction services
 *
 * Java 17, no external dependencies.
 */

public class LSMTreeDemo {

    enum Operation {
        PUT,
        DELETE
    }

    enum StorageState {
        ACTIVE,
        FLUSHING,
        COMPACTING,
        CLOSED
    }

    record Entry(
        String key,
        String value,
        long sequence,
        Operation operation,
        long timestamp
    ) {
        Entry {
            if (key == null || key.isBlank()) {
                throw new IllegalArgumentException("Invalid key");
            }

            if (sequence < 1) {
                throw new IllegalArgumentException(
                    "Sequence must be positive"
                );
            }

            Objects.requireNonNull(operation);

            if (operation == Operation.PUT && value == null) {
                throw new IllegalArgumentException(
                    "PUT requires a value"
                );
            }

            if (operation == Operation.DELETE && value != null) {
                throw new IllegalArgumentException(
                    "DELETE cannot contain a value"
                );
            }
        }
    }

    record StoragePolicy(
        int memtableCapacity,
        int runCapacity,
        int sparseIndexInterval,
        int maximumKeyLength
    ) {
        StoragePolicy {
            if (
                memtableCapacity < 1 ||
                runCapacity < 2 ||
                sparseIndexInterval < 1 ||
                maximumKeyLength < 1
            ) {
                throw new IllegalArgumentException(
                    "Invalid storage policy"
                );
            }
        }

        void validateKey(String key) {
            if (
                key == null ||
                key.isBlank() ||
                key.length() > maximumKeyLength
            ) {
                throw new IllegalArgumentException(
                    "Key violates storage policy"
                );
            }
        }

        void validateValue(String value) {
            if (value == null) {
                throw new IllegalArgumentException(
                    "Null values are not permitted"
                );
            }
        }
    }

    static final class BloomFilter {
        private final boolean[] bits;
        private final int hashCount;

        BloomFilter(int capacity) {
            if (capacity < 1) {
                throw new IllegalArgumentException(
                    "Invalid Bloom filter capacity"
                );
            }

            int bitCount = Math.max(
                8,
                (int) Math.ceil(
                    -capacity * Math.log(0.01) /
                    (Math.log(2) * Math.log(2))
                )
            );

            this.bits = new boolean[bitCount];

            this.hashCount = Math.max(
                1,
                (int) Math.round(
                    (double) bitCount / capacity *
                    Math.log(2)
                )
            );
        }

        private int[] positions(String key) {
            int first = key.hashCode();
            int second = Integer.rotateLeft(first, 13) | 1;

            int[] positions = new int[hashCount];

            for (int i = 0; i < hashCount; i++) {
                positions[i] = Math.floorMod(
                    first + i * second,
                    bits.length
                );
            }

            return positions;
        }

        void add(String key) {
            for (int position : positions(key)) {
                bits[position] = true;
            }
        }

        boolean mightContain(String key) {
            for (int position : positions(key)) {
                if (!bits[position]) {
                    return false;
                }
            }

            return true;
        }
    }

    static final class SparseIndex {
        private final List<String> keys = new ArrayList<>();
        private final List<Integer> positions = new ArrayList<>();

        SparseIndex(List<Entry> entries, int interval) {
            for (int i = 0; i < entries.size(); i += interval) {
                keys.add(entries.get(i).key());
                positions.add(i);
            }
        }

        int findStart(String key) {
            int index = Collections.binarySearch(keys, key);

            if (index >= 0) {
                return positions.get(index);
            }

            index = -index - 2;

            return index < 0 ? 0 : positions.get(index);
        }
    }

    static final class SSTable {
        private final long id;
        private final int level;
        private final List<Entry> entries;
        private final BloomFilter bloom;
        private final SparseIndex sparseIndex;

        SSTable(
            long id,
            int level,
            List<Entry> input,
            int indexInterval
        ) {
            if (input.isEmpty()) {
                throw new IllegalArgumentException(
                    "Empty SSTable"
                );
            }

            this.id = id;
            this.level = level;

            List<Entry> sorted = new ArrayList<>(input);

            sorted.sort(
                Comparator.comparing(Entry::key)
            );

            for (int i = 1; i < sorted.size(); i++) {
                if (
                    sorted.get(i - 1).key().equals(
                        sorted.get(i).key()
                    )
                ) {
                    throw new IllegalArgumentException(
                        "Duplicate SSTable key"
                    );
                }
            }

            this.entries = List.copyOf(sorted);
            this.bloom = new BloomFilter(entries.size());

            entries.forEach(
                entry -> bloom.add(entry.key())
            );

            this.sparseIndex = new SparseIndex(
                entries,
                indexInterval
            );
        }

        long id() {
            return id;
        }

        int level() {
            return level;
        }

        List<Entry> entries() {
            return entries;
        }

        Optional<Entry> get(String key) {
            if (
                key.compareTo(entries.get(0).key()) < 0 ||
                key.compareTo(
                    entries.get(entries.size() - 1).key()
                ) > 0 ||
                !bloom.mightContain(key)
            ) {
                return Optional.empty();
            }

            int start = sparseIndex.findStart(key);

            int end = Math.min(
                start + 9,
                entries.size()
            );

            for (int i = start; i < end; i++) {
                Entry entry = entries.get(i);

                int comparison = entry.key().compareTo(key);

                if (comparison == 0) {
                    return Optional.of(entry);
                }

                if (comparison > 0) {
                    break;
                }
            }

            return Optional.empty();
        }
    }

    static final class MemTable {
        private final Map<String, Entry> entries =
            new HashMap<>();

        void put(Entry entry) {
            entries.put(entry.key(), entry);
        }

        Optional<Entry> get(String key) {
            return Optional.ofNullable(entries.get(key));
        }

        int size() {
            return entries.size();
        }

        boolean isEmpty() {
            return entries.isEmpty();
        }

        List<Entry> sortedEntries() {
            return entries.values()
                .stream()
                .sorted(Comparator.comparing(Entry::key))
                .toList();
        }

        void clear() {
            entries.clear();
        }
    }

    static final class StorageException extends RuntimeException {
        StorageException(String message) {
            super(message);
        }
    }

    static final class LSMStorageService {
        private final StoragePolicy policy;
        private final MemTable memtable = new MemTable();

        private final Map<Integer, List<SSTable>> levels =
            new TreeMap<>();

        private final AtomicLong sequence =
            new AtomicLong();

        private final AtomicLong tableSequence =
            new AtomicLong();

        private StorageState state = StorageState.ACTIVE;

        LSMStorageService(StoragePolicy policy) {
            this.policy = policy;
            levels.put(0, new ArrayList<>());
        }

        private void ensureActive() {
            if (state == StorageState.CLOSED) {
                throw new StorageException(
                    "Storage engine is closed"
                );
            }

            if (state != StorageState.ACTIVE) {
                throw new StorageException(
                    "Storage engine is not accepting writes"
                );
            }
        }

        public synchronized long put(
            String key,
            String value
        ) {
            ensureActive();

            policy.validateKey(key);
            policy.validateValue(value);

            long version = sequence.incrementAndGet();

            Entry entry = new Entry(
                key,
                value,
                version,
                Operation.PUT,
                System.currentTimeMillis()
            );

            memtable.put(entry);

            if (memtable.size() >= policy.memtableCapacity()) {
                flush();
            }

            return version;
        }

        public synchronized long delete(String key) {
            ensureActive();

            policy.validateKey(key);

            long version = sequence.incrementAndGet();

            Entry entry = new Entry(
                key,
                null,
                version,
                Operation.DELETE,
                System.currentTimeMillis()
            );

            memtable.put(entry);

            if (memtable.size() >= policy.memtableCapacity()) {
                flush();
            }

            return version;
        }

        public synchronized Optional<String> get(String key) {
            policy.validateKey(key);

            Entry latest = memtable.get(key).orElse(null);

            // Runs are checked by sequence rather than assumed recency.
            for (List<SSTable> tables : levels.values()) {
                for (SSTable table : tables) {
                    Entry candidate = table.get(key).orElse(null);

                    if (
                        candidate != null &&
                        (
                            latest == null ||
                            candidate.sequence() > latest.sequence()
                        )
                    ) {
                        latest = candidate;
                    }
                }
            }

            if (
                latest == null ||
                latest.operation() == Operation.DELETE
            ) {
                return Optional.empty();
            }

            return Optional.of(latest.value());
        }

        public synchronized void flush() {
            if (memtable.isEmpty()) {
                return;
            }

            state = StorageState.FLUSHING;

            try {
                List<Entry> snapshot = memtable.sortedEntries();

                SSTable output = new SSTable(
                    tableSequence.incrementAndGet(),
                    0,
                    snapshot,
                    policy.sparseIndexInterval()
                );

                levels.computeIfAbsent(
                    0,
                    ignored -> new ArrayList<>()
                ).add(output);

                memtable.clear();

                state = StorageState.ACTIVE;

                if (
                    levels.get(0).size() >=
                    policy.runCapacity()
                ) {
                    compact(0);
                }

            } catch (RuntimeException error) {
                state = StorageState.ACTIVE;

                throw new StorageException(
                    "Flush failed: " + error.getMessage()
                );
            }
        }

        public synchronized void compact(int level) {
            List<SSTable> inputs = levels.computeIfAbsent(
                level,
                ignored -> new ArrayList<>()
            );

            if (inputs.size() < 2) {
                return;
            }

            state = StorageState.COMPACTING;

            try {
                Map<String, Entry> newest = new TreeMap<>();

                for (SSTable table : inputs) {
                    for (Entry entry : table.entries()) {
                        newest.merge(
                            entry.key(),
                            entry,
                            (first, second) ->
                                first.sequence() > second.sequence()
                                    ? first
                                    : second
                        );
                    }
                }

                List<Entry> outputEntries =
                    new ArrayList<>(newest.values());

                SSTable output = new SSTable(
                    tableSequence.incrementAndGet(),
                    level + 1,
                    outputEntries,
                    policy.sparseIndexInterval()
                );

                // Preserve tombstones until lower-level overlap,
                // snapshots, and replication are accounted for.
                inputs.clear();

                levels.computeIfAbsent(
                    level + 1,
                    ignored -> new ArrayList<>()
                ).add(output);

                state = StorageState.ACTIVE;

                List<SSTable> nextLevel = levels.get(level + 1);

                if (nextLevel.size() >= policy.runCapacity()) {
                    compact(level + 1);
                }

            } catch (RuntimeException error) {
                state = StorageState.ACTIVE;

                throw new StorageException(
                    "Compaction failed: " + error.getMessage()
                );
            }
        }

        public synchronized Map<String, String> rangeScan(
            String start,
            String end
        ) {
            if (
                start == null ||
                end == null ||
                start.compareTo(end) > 0
            ) {
                throw new IllegalArgumentException(
                    "Invalid range"
                );
            }

            Map<String, Entry> newest = new TreeMap<>();

            java.util.function.Consumer<Entry> process = entry -> {
                if (
                    entry.key().compareTo(start) < 0 ||
                    entry.key().compareTo(end) > 0
                ) {
                    return;
                }

                newest.merge(
                    entry.key(),
                    entry,
                    (first, second) ->
                        first.sequence() > second.sequence()
                            ? first
                            : second
                );
            };

            memtable.sortedEntries().forEach(process);

            levels.values().stream()
                .flatMap(List::stream)
                .flatMap(table -> table.entries().stream())
                .forEach(process);

            return newest.values().stream()
                .filter(
                    entry -> entry.operation() == Operation.PUT
                )
                .collect(
                    Collectors.toMap(
                        Entry::key,
                        Entry::value,
                        (first, second) -> second,
                        LinkedHashMap::new
                    )
                );
        }

        public synchronized boolean validate() {
            Map<Long, Boolean> identifiers = new HashMap<>();

            for (var levelEntry : levels.entrySet()) {
                int level = levelEntry.getKey();

                for (SSTable table : levelEntry.getValue()) {
                    if (table.level() != level) {
                        return false;
                    }

                    if (
                        identifiers.put(table.id(), true) != null
                    ) {
                        return false;
                    }

                    List<Entry> entries = table.entries();

                    for (int i = 1; i < entries.size(); i++) {
                        if (
                            entries.get(i - 1).key().compareTo(
                                entries.get(i).key()
                            ) >= 0
                        ) {
                            return false;
                        }
                    }
                }
            }

            return true;
        }

        public synchronized void printStatistics() {
            System.out.println("\nSTORAGE METRICS");
            System.out.println("Sequence: " + sequence.get());
            System.out.println(
                "Memtable entries: " + memtable.size()
            );
            System.out.println("State: " + state);

            for (var level : levels.entrySet()) {
                int count = level.getValue().stream()
                    .mapToInt(table -> table.entries().size())
                    .sum();

                System.out.printf(
                    "Level %d | Runs: %d | Entries: %d%n",
                    level.getKey(),
                    level.getValue().size(),
                    count
                );
            }
        }

        public synchronized void close() {
            if (state == StorageState.CLOSED) {
                return;
            }

            flush();
            state = StorageState.CLOSED;
        }
    }

    public static void main(String[] args) {
        StoragePolicy policy = new StoragePolicy(
            3,
            2,
            4,
            128
        );

        LSMStorageService storage =
            new LSMStorageService(policy);

        try {
            System.out.println(
                "ENTERPRISE FINANCIAL EVENT STORAGE"
            );

            storage.put("transaction:1001", "INITIATED");
            storage.put("transaction:1002", "AUTHORIZED");
            storage.put("transaction:1003", "PENDING");

            storage.put("transaction:1002", "SETTLED");
            storage.delete("transaction:1003");
            storage.put("transaction:1004", "AUTHORIZED");

            System.out.println("\nPOINT QUERIES");

            for (String key : List.of(
                "transaction:1001",
                "transaction:1002",
                "transaction:1003",
                "transaction:1004"
            )) {
                System.out.println(
                    key + " = " +
                    storage.get(key).orElse("NOT FOUND")
                );
            }

            System.out.println("\nRANGE QUERY");

            storage.rangeScan(
                "transaction:1001",
                "transaction:1004"
            ).forEach(
                (key, value) ->
                    System.out.println(key + " -> " + value)
            );

            storage.flush();

            System.out.println("\nVALIDATION");

            if (!storage.validate()) {
                throw new StorageException(
                    "Storage invariant validation failed"
                );
            }

            if (!storage.get("transaction:1002")
                .orElse("")
                .equals("SETTLED")) {
                throw new StorageException(
                    "Latest version resolution failed"
                );
            }

            if (storage.get("transaction:1003").isPresent()) {
                throw new StorageException(
                    "Deletion resolution failed"
                );
            }

            storage.printStatistics();

            System.out.println("\nALL VALIDATIONS PASSED");

        } catch (RuntimeException error) {
            System.err.println(
                "Storage failure: " + error.getMessage()
            );

            System.exitCode = 1;

        } finally {
            storage.close();
        }
    }
}
