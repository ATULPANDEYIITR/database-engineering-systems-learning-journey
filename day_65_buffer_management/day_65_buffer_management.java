import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.concurrent.atomic.AtomicLong;

public class BufferManagement {

    enum PageState {
        CLEAN,
        DIRTY
    }

    enum EvictionPolicy {
        LRU,
        LFU
    }

    static class BufferException extends RuntimeException {
        BufferException(String message) {
            super(message);
        }
    }

    static class BufferFullException extends BufferException {
        BufferFullException(String message) {
            super(message);
        }
    }

    static class StorageException extends BufferException {
        StorageException(String message) {
            super(message);
        }
    }

    record BufferConfiguration(
        int capacity,
        int pageSize,
        EvictionPolicy evictionPolicy,
        boolean writeThrough
    ) {
        BufferConfiguration {
            if (capacity <= 0 || pageSize <= 0) {
                throw new IllegalArgumentException(
                    "Capacity and page size must be positive."
                );
            }

            if (evictionPolicy == null) {
                throw new IllegalArgumentException(
                    "An eviction policy is required."
                );
            }
        }
    }

    static final class PageFrame {
        private final long pageId;
        private byte[] data;
        private int pinCount;
        private long accessCount;
        private long lastAccess;
        private PageState state;

        PageFrame(long pageId, byte[] data) {
            this.pageId = pageId;
            this.data = data.clone();
            this.pinCount = 0;
            this.accessCount = 1;
            this.lastAccess = System.nanoTime();
            this.state = PageState.CLEAN;
        }

        long pageId() {
            return pageId;
        }

        int pinCount() {
            return pinCount;
        }

        PageState state() {
            return state;
        }

        long accessCount() {
            return accessCount;
        }

        void touch() {
            accessCount++;
            lastAccess = System.nanoTime();
        }

        void pin() {
            pinCount++;
        }

        void unpin() {
            if (pinCount == 0) {
                throw new BufferException("Page is not pinned.");
            }
            pinCount--;
        }

        byte[] read() {
            return data.clone();
        }

        void modify(int offset, byte[] value) {
            if (offset < 0 || offset > data.length ||
                value.length > data.length - offset) {
                throw new IllegalArgumentException(
                    "Write exceeds page boundaries."
                );
            }

            System.arraycopy(
                value, 0, data, offset, value.length
            );

            state = PageState.DIRTY;
        }

        void markClean() {
            state = PageState.CLEAN;
        }

        byte[] snapshot() {
            return data.clone();
        }
    }

    interface PageStorage {
        byte[] read(long pageId);

        void write(long pageId, byte[] data);
    }

    static final class InMemoryStorage implements PageStorage {
        private final Map<Long, byte[]> disk = new HashMap<>();
        private final int pageSize;
        private boolean writesEnabled = true;

        InMemoryStorage(int pageSize) {
            this.pageSize = pageSize;
        }

        @Override
        public synchronized byte[] read(long pageId) {
            if (pageId < 0) {
                throw new StorageException("Invalid page identifier.");
            }

            return disk.computeIfAbsent(pageId, id -> {
                byte[] page = new byte[pageSize];
                byte[] initial = ("DATABASE_PAGE_" + id)
                    .getBytes(java.nio.charset.StandardCharsets.UTF_8);

                System.arraycopy(
                    initial,
                    0,
                    page,
                    0,
                    Math.min(initial.length, page.length)
                );

                return page;
            }).clone();
        }

        @Override
        public synchronized void write(long pageId, byte[] data) {
            if (!writesEnabled) {
                throw new StorageException("Storage writes are disabled.");
            }

            if (data.length != pageSize) {
                throw new StorageException("Invalid page size.");
            }

            disk.put(pageId, data.clone());
        }

        synchronized void setWritesEnabled(boolean enabled) {
            writesEnabled = enabled;
        }

        synchronized boolean contains(long pageId) {
            return disk.containsKey(pageId);
        }
    }

    static final class BufferStatistics {
        long requests;
        long hits;
        long misses;
        long evictions;
        long writes;
        long failedEvictions;

        double hitRatio() {
            return requests == 0
                ? 0.0
                : (double) hits / requests;
        }

        double missRatio() {
            return requests == 0
                ? 0.0
                : (double) misses / requests;
        }
    }

    static final class BufferPool {
        private final BufferConfiguration configuration;
        private final PageStorage storage;

        // Access-order LinkedHashMap provides O(1) LRU lookup and ordering.
        private final LinkedHashMap<Long, PageFrame> frames =
            new LinkedHashMap<>(16, 0.75f, true);

        private final BufferStatistics statistics =
            new BufferStatistics();

        private boolean closed;

        BufferPool(
            BufferConfiguration configuration,
            PageStorage storage
        ) {
            this.configuration = configuration;
            this.storage = storage;
        }

        private void ensureOpen() {
            if (closed) {
                throw new BufferException("Buffer pool is closed.");
            }
        }

        private void validatePageId(long pageId) {
            if (pageId < 0) {
                throw new IllegalArgumentException(
                    "Page ID cannot be negative."
                );
            }
        }

        private void persist(PageFrame frame) {
            if (frame.state() != PageState.DIRTY) {
                return;
            }

            storage.write(frame.pageId(), frame.snapshot());
            frame.markClean();
            statistics.writes++;
        }

        private PageFrame findVictim() {
            List<PageFrame> candidates = new ArrayList<>(frames.values());

            Optional<PageFrame> candidate;

            if (configuration.evictionPolicy() == EvictionPolicy.LRU) {
                candidate = candidates.stream()
                    .filter(frame -> frame.pinCount() == 0)
                    .findFirst();
            } else {
                candidate = candidates.stream()
                    .filter(frame -> frame.pinCount() == 0)
                    .min(
                        Comparator.comparingLong(PageFrame::accessCount)
                            .thenComparingLong(PageFrame::pageId)
                    );
            }

            if (candidate.isEmpty()) {
                statistics.failedEvictions++;
                throw new BufferFullException(
                    "Every buffer frame is pinned."
                );
            }

            return candidate.get();
        }

        private void evictIfRequired() {
            if (frames.size() < configuration.capacity()) {
                return;
            }

            PageFrame victim = findVictim();

            // Remove a frame only after its dirty data is persisted.
            persist(victim);
            frames.remove(victim.pageId());
            statistics.evictions++;
        }

        public synchronized PageFrame fetch(long pageId) {
            ensureOpen();
            validatePageId(pageId);

            statistics.requests++;

            PageFrame existing = frames.get(pageId);

            if (existing != null) {
                statistics.hits++;
                existing.touch();
                return existing;
            }

            statistics.misses++;

            // Storage failure must not evict an existing frame.
            byte[] data = storage.read(pageId);

            if (data.length != configuration.pageSize()) {
                throw new StorageException(
                    "Storage returned an invalid page size."
                );
            }

            evictIfRequired();

            PageFrame frame = new PageFrame(pageId, data);
            frames.put(pageId, frame);

            return frame;
        }

        public synchronized PageFrame pin(long pageId) {
            PageFrame frame = fetch(pageId);
            frame.pin();
            return frame;
        }

        public synchronized void unpin(long pageId, boolean dirty) {
            ensureOpen();

            PageFrame frame = frames.get(pageId);

            if (frame == null) {
                throw new BufferException("Page is not cached.");
            }

            frame.unpin();

            if (dirty) {
                frame.modify(
                    0,
                    new byte[0]
                );
                frame.state = PageState.DIRTY;
            }
        }

        public synchronized byte[] read(long pageId) {
            return fetch(pageId).read();
        }

        public synchronized void write(
            long pageId,
            int offset,
            byte[] value
        ) {
            PageFrame frame = pin(pageId);

            try {
                frame.modify(offset, value);

                if (configuration.writeThrough()) {
                    persist(frame);
                }
            } finally {
                frame.unpin();
            }
        }

        public synchronized void flushPage(long pageId) {
            ensureOpen();

            PageFrame frame = frames.get(pageId);

            if (frame == null) {
                throw new BufferException("Page is not cached.");
            }

            if (frame.pinCount() > 0) {
                throw new BufferException(
                    "Cannot flush a pinned page."
                );
            }

            persist(frame);
        }

        public synchronized void flushAll() {
            ensureOpen();

            if (frames.values().stream()
                .anyMatch(frame -> frame.pinCount() > 0)) {
                throw new BufferException(
                    "Cannot flush while frames are pinned."
                );
            }

            // If a write fails, the affected page remains dirty.
            for (PageFrame frame : frames.values()) {
                persist(frame);
            }
        }

        public synchronized void invalidate(
            long pageId,
            boolean discardDirty
        ) {
            ensureOpen();

            PageFrame frame = frames.get(pageId);

            if (frame == null) {
                return;
            }

            if (frame.pinCount() > 0) {
                throw new BufferException(
                    "Cannot invalidate a pinned page."
                );
            }

            if (!discardDirty) {
                persist(frame);
            }

            frames.remove(pageId);
        }

        public synchronized void close() {
            flushAll();
            closed = true;
        }

        public synchronized void printReport() {
            System.out.println("\nBUFFER POOL REPORT");
            System.out.println("Capacity: " + configuration.capacity());
            System.out.println("Occupied frames: " + frames.size());

            System.out.println("\nPage ID | State | Pins | Accesses");

            frames.values().forEach(frame ->
                System.out.printf(
                    "%d | %s | %d | %d%n",
                    frame.pageId(),
                    frame.state(),
                    frame.pinCount(),
                    frame.accessCount()
                )
            );

            System.out.println("\nSTATISTICS");
            System.out.println("Requests: " + statistics.requests);
            System.out.println("Hits: " + statistics.hits);
            System.out.println("Misses: " + statistics.misses);
            System.out.println("Evictions: " + statistics.evictions);
            System.out.println("Writes: " + statistics.writes);
            System.out.println(
                "Failed evictions: " + statistics.failedEvictions
            );

            System.out.printf(
                "Hit ratio: %.2f%%%n",
                statistics.hitRatio() * 100
            );

            System.out.printf(
                "Miss ratio: %.2f%%%n",
                statistics.missRatio() * 100
            );
        }
    }

    public static void main(String[] args) {
        int pageSize = 128;

        InMemoryStorage storage = new InMemoryStorage(pageSize);

        BufferConfiguration configuration =
            new BufferConfiguration(
                3,
                pageSize,
                EvictionPolicy.LRU,
                false
            );

        BufferPool pool = new BufferPool(configuration, storage);

        try {
            System.out.println("ENTERPRISE DATABASE BUFFER MANAGEMENT");

            System.out.println("\n1. Load pages");

            pool.fetch(101);
            pool.fetch(102);
            pool.fetch(103);

            System.out.println("\n2. Generate cache hits");

            pool.fetch(101);
            pool.fetch(102);

            System.out.println("\n3. Modify a page");

            pool.write(
                102,
                0,
                "UPDATED_CUSTOMER_RECORD"
                    .getBytes(java.nio.charset.StandardCharsets.UTF_8)
            );

            System.out.println("\n4. Trigger LRU eviction");

            pool.fetch(104);

            System.out.println("\n5. Demonstrate pin protection");

            pool.pin(102);
            pool.pin(103);
            pool.pin(104);

            try {
                pool.fetch(105);
            } catch (BufferFullException error) {
                System.out.println("Expected failure: " + error.getMessage());
            }

            pool.unpin(102, false);
            pool.unpin(103, false);
            pool.unpin(104, false);

            System.out.println("\n6. Flush modified pages");

            pool.flushAll();

            System.out.println("\n7. Storage failure handling");

            pool.write(
                104,
                0,
                "ANOTHER_UPDATE"
                    .getBytes(java.nio.charset.StandardCharsets.UTF_8)
            );

            storage.setWritesEnabled(false);

            try {
                pool.flushPage(104);
            } catch (StorageException error) {
                System.out.println("Expected storage failure: " + error.getMessage());
            }

            storage.setWritesEnabled(true);
            pool.flushPage(104);

            System.out.println("\n8. Verify persisted records");

            if (!storage.contains(102) || !storage.contains(104)) {
                throw new IllegalStateException("Persistence validation failed.");
            }

            pool.printReport();

            pool.close();

            System.out.println("\nAll enterprise buffer tests passed.");

        } catch (RuntimeException error) {
            System.err.println("Buffer management failure: " + error.getMessage());
            System.exitCode = 1;
        }
    }
}
