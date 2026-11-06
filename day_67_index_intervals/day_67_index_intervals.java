import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.TreeMap;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;

/**
 * Enterprise-oriented B+ tree index management.
 *
 * Models:
 * - Index metadata and page structures.
 * - Internal and leaf page relationships.
 * - Database record lookup.
 * - Range retrieval.
 * - Page traversal and inspection.
 * - Index maintenance and integrity validation.
 * - Buffer-pool replacement policy.
 * - Asynchronous index query execution.
 *
 * Java version: 17
 */

public class IndexInternals {

    enum PageType {
        INTERNAL,
        LEAF
    }

    enum IndexState {
        BUILDING,
        ACTIVE,
        DEGRADED,
        DISABLED
    }

    record IndexMetadata(
        String indexName,
        String tableName,
        String columnName,
        int order,
        IndexState state
    ) {
        IndexMetadata {
            Objects.requireNonNull(indexName);
            Objects.requireNonNull(tableName);
            Objects.requireNonNull(columnName);

            if (indexName.isBlank() ||
                tableName.isBlank() ||
                columnName.isBlank()) {
                throw new IllegalArgumentException(
                    "Index metadata cannot be blank"
                );
            }

            if (order < 3) {
                throw new IllegalArgumentException(
                    "B+ tree order must be at least 3"
                );
            }
        }
    }

    record IndexRecord(int key, String value) {
        IndexRecord {
            Objects.requireNonNull(value);
        }
    }

    record PageSnapshot(
        int pageId,
        PageType type,
        List<Integer> keys,
        List<Integer> childPageIds,
        Integer nextLeafPageId
    ) {}

    record IndexStatistics(
        int recordCount,
        int height,
        int totalPages,
        int leafPages,
        int internalPages,
        long pageReads,
        long pageWrites,
        long pageSplits
    ) {}

    static class IndexException extends RuntimeException {
        IndexException(String message) {
            super(message);
        }
    }

    static class DuplicateKeyException extends IndexException {
        DuplicateKeyException(int key) {
            super("Duplicate index key: " + key);
        }
    }

    static class MissingKeyException extends IndexException {
        MissingKeyException(int key) {
            super("Index key does not exist: " + key);
        }
    }

    static class IndexPage {
        final int id;
        final PageType type;

        final List<Integer> keys = new ArrayList<>();
        final List<String> values = new ArrayList<>();
        final List<IndexPage> children = new ArrayList<>();

        IndexPage nextLeaf;
        IndexPage parent;
        long version;

        IndexPage(int id, PageType type) {
            this.id = id;
            this.type = type;
        }

        boolean isLeaf() {
            return type == PageType.LEAF;
        }
    }

    static final class BPlusIndex {
        private final IndexMetadata metadata;

        private final int order;
        private final int maxKeys;
        private final int minLeafKeys;
        private final int minInternalChildren;

        private final Map<Integer, IndexPage> pages =
            new LinkedHashMap<>();

        private int nextPageId = 1;
        private int recordCount;

        private long reads;
        private long writes;
        private long splits;

        private IndexPage root;

        BPlusIndex(IndexMetadata metadata) {
            this.metadata = metadata;
            this.order = metadata.order();
            this.maxKeys = order - 1;
            this.minLeafKeys = order / 2;
            this.minInternalChildren = (order + 1) / 2;

            this.root = createPage(PageType.LEAF);
        }

        private IndexPage createPage(PageType type) {
            IndexPage page = new IndexPage(nextPageId++, type);
            pages.put(page.id, page);
            return page;
        }

        private void read(IndexPage page) {
            reads++;
        }

        private void write(IndexPage page) {
            page.version++;
            writes++;
        }

        private int minimum(IndexPage page) {
            while (!page.isLeaf()) {
                page = page.children.get(0);
            }

            return page.keys.get(0);
        }

        private void refresh(IndexPage page) {
            if (page.isLeaf()) {
                return;
            }

            page.keys.clear();

            for (int i = 1; i < page.children.size(); i++) {
                page.keys.add(minimum(page.children.get(i)));
            }
        }

        private IndexPage locateLeaf(int key) {
            IndexPage page = root;

            while (!page.isLeaf()) {
                read(page);

                int low = 0;
                int high = page.keys.size();

                while (low < high) {
                    int middle = (low + high) >>> 1;

                    if (key >= page.keys.get(middle)) {
                        low = middle + 1;
                    } else {
                        high = middle;
                    }
                }

                page = page.children.get(low);
            }

            read(page);
            return page;
        }

        private int lowerBound(List<Integer> keys, int key) {
            int low = 0;
            int high = keys.size();

            while (low < high) {
                int middle = (low + high) >>> 1;

                if (keys.get(middle) < key) {
                    low = middle + 1;
                } else {
                    high = middle;
                }
            }

            return low;
        }

        private void insertParent(
            IndexPage left,
            IndexPage right
        ) {
            IndexPage parent = left.parent;

            if (parent == null) {
                parent = createPage(PageType.INTERNAL);

                parent.children.add(left);
                parent.children.add(right);

                left.parent = parent;
                right.parent = parent;

                refresh(parent);
                root = parent;
                write(parent);
                return;
            }

            int index = parent.children.indexOf(left);

            if (index < 0) {
                throw new IndexException(
                    "Parent-child relationship is invalid"
                );
            }

            parent.children.add(index + 1, right);
            right.parent = parent;

            refresh(parent);
            write(parent);

            if (parent.children.size() > order) {
                splitInternal(parent);
            }
        }

        private void splitLeaf(IndexPage leaf) {
            int middle = leaf.keys.size() / 2;
            IndexPage right = createPage(PageType.LEAF);

            right.keys.addAll(
                leaf.keys.subList(middle, leaf.keys.size())
            );

            right.values.addAll(
                leaf.values.subList(middle, leaf.values.size())
            );

            leaf.keys.subList(middle, leaf.keys.size()).clear();
            leaf.values.subList(middle, leaf.values.size()).clear();

            right.nextLeaf = leaf.nextLeaf;
            leaf.nextLeaf = right;

            splits++;
            write(leaf);
            write(right);

            insertParent(leaf, right);
        }

        private void splitInternal(IndexPage page) {
            int middle = page.children.size() / 2;
            IndexPage right = createPage(PageType.INTERNAL);

            right.children.addAll(
                page.children.subList(middle, page.children.size())
            );

            page.children.subList(
                middle,
                page.children.size()
            ).clear();

            for (IndexPage child : right.children) {
                child.parent = right;
            }

            refresh(page);
            refresh(right);

            splits++;
            write(page);
            write(right);

            insertParent(page, right);
        }

        private void repairAncestors(IndexPage page) {
            while (page != null) {
                refresh(page);
                write(page);
                page = page.parent;
            }
        }

        public synchronized void insert(IndexRecord record) {
            Objects.requireNonNull(record);

            if (metadata.state() != IndexState.ACTIVE &&
                metadata.state() != IndexState.BUILDING) {
                throw new IndexException(
                    "Index does not accept writes in current state"
                );
            }

            IndexPage leaf = locateLeaf(record.key());
            int index = lowerBound(leaf.keys, record.key());

            if (index < leaf.keys.size() &&
                leaf.keys.get(index) == record.key()) {
                throw new DuplicateKeyException(record.key());
            }

            leaf.keys.add(index, record.key());
            leaf.values.add(index, record.value());

            recordCount++;
            write(leaf);

            if (leaf.keys.size() > maxKeys) {
                splitLeaf(leaf);
            }

            repairAncestors(leaf.parent);
        }

        public synchronized String search(int key) {
            if (metadata.state() != IndexState.ACTIVE) {
                throw new IndexException(
                    "Index is not available for queries"
                );
            }

            IndexPage leaf = locateLeaf(key);
            int index = lowerBound(leaf.keys, key);

            if (index < leaf.keys.size() &&
                leaf.keys.get(index) == key) {
                return leaf.values.get(index);
            }

            return null;
        }

        public synchronized List<IndexRecord> rangeScan(
            int start,
            int end
        ) {
            if (start > end) {
                return List.of();
            }

            IndexPage leaf = locateLeaf(start);
            List<IndexRecord> results = new ArrayList<>();

            while (leaf != null) {
                read(leaf);

                for (int i = 0; i < leaf.keys.size(); i++) {
                    int key = leaf.keys.get(i);

                    if (key > end) {
                        return List.copyOf(results);
                    }

                    if (key >= start) {
                        results.add(
                            new IndexRecord(
                                key,
                                leaf.values.get(i)
                            )
                        );
                    }
                }

                leaf = leaf.nextLeaf;
            }

            return List.copyOf(results);
        }

        public synchronized void delete(int key) {
            IndexPage leaf = locateLeaf(key);
            int index = lowerBound(leaf.keys, key);

            if (index >= leaf.keys.size() ||
                leaf.keys.get(index) != key) {
                throw new MissingKeyException(key);
            }

            leaf.keys.remove(index);
            leaf.values.remove(index);
            recordCount--;

            write(leaf);

            if (leaf == root) {
                return;
            }

            if (leaf.keys.size() < minLeafKeys) {
                rebalanceLeaf(leaf);
            }

            repairAncestors(leaf.parent);
        }

        private void rebalanceLeaf(IndexPage leaf) {
            IndexPage parent = leaf.parent;
            int index = parent.children.indexOf(leaf);

            IndexPage left = index > 0
                ? parent.children.get(index - 1)
                : null;

            IndexPage right = index + 1 < parent.children.size()
                ? parent.children.get(index + 1)
                : null;

            if (left != null && left.keys.size() > minLeafKeys) {
                int last = left.keys.size() - 1;

                leaf.keys.add(0, left.keys.remove(last));
                leaf.values.add(0, left.values.remove(last));

                write(left);
                write(leaf);

            } else if (right != null &&
                       right.keys.size() > minLeafKeys) {
                leaf.keys.add(right.keys.remove(0));
                leaf.values.add(right.values.remove(0));

                write(right);
                write(leaf);

            } else if (left != null) {
                left.keys.addAll(leaf.keys);
                left.values.addAll(leaf.values);
                left.nextLeaf = leaf.nextLeaf;

                parent.children.remove(index);

                write(left);
                repairInternal(parent);

            } else if (right != null) {
                leaf.keys.addAll(right.keys);
                leaf.values.addAll(right.values);
                leaf.nextLeaf = right.nextLeaf;

                parent.children.remove(index + 1);

                write(leaf);
                repairInternal(parent);
            }
        }

        private void repairInternal(IndexPage page) {
            if (page == root) {
                if (page.children.size() == 1) {
                    root = page.children.get(0);
                    root.parent = null;
                } else {
                    refresh(page);
                }

                return;
            }

            refresh(page);

            if (page.children.size() >= minInternalChildren) {
                repairAncestors(page.parent);
                return;
            }

            IndexPage parent = page.parent;
            int index = parent.children.indexOf(page);

            IndexPage left = index > 0
                ? parent.children.get(index - 1)
                : null;

            IndexPage right = index + 1 < parent.children.size()
                ? parent.children.get(index + 1)
                : null;

            if (left != null &&
                left.children.size() > minInternalChildren) {

                IndexPage child = left.children.remove(
                    left.children.size() - 1
                );

                page.children.add(0, child);
                child.parent = page;

                refresh(left);
                refresh(page);

            } else if (right != null &&
                       right.children.size() > minInternalChildren) {

                IndexPage child = right.children.remove(0);

                page.children.add(child);
                child.parent = page;

                refresh(right);
                refresh(page);

            } else if (left != null) {
                left.children.addAll(page.children);

                for (IndexPage child : page.children) {
                    child.parent = left;
                }

                parent.children.remove(index);
                refresh(left);

            } else if (right != null) {
                page.children.addAll(right.children);

                for (IndexPage child : right.children) {
                    child.parent = page;
                }

                parent.children.remove(index + 1);
            }

            refresh(parent);
            write(parent);
            repairInternal(parent);
        }

        public synchronized List<Integer> traversal() {
            IndexPage page = root;

            while (!page.isLeaf()) {
                page = page.children.get(0);
            }

            List<Integer> result = new ArrayList<>();

            while (page != null) {
                read(page);
                result.addAll(page.keys);
                page = page.nextLeaf;
            }

            return List.copyOf(result);
        }

        public synchronized List<PageSnapshot> pageSnapshots() {
            List<PageSnapshot> snapshots = new ArrayList<>();
            List<IndexPage> queue = new ArrayList<>();
            queue.add(root);

            for (int i = 0; i < queue.size(); i++) {
                IndexPage page = queue.get(i);

                List<Integer> childIds = page.children.stream()
                    .map(child -> child.id)
                    .toList();

                snapshots.add(
                    new PageSnapshot(
                        page.id,
                        page.type,
                        List.copyOf(page.keys),
                        childIds,
                        page.nextLeaf == null
                            ? null
                            : page.nextLeaf.id
                    )
                );

                queue.addAll(page.children);
            }

            return List.copyOf(snapshots);
        }

        private int inspect(
            IndexPage page,
            boolean isRoot,
            Set<Integer> visited,
            List<IndexPage> leaves
        ) {
            if (!visited.add(page.id)) {
                throw new IndexException("Page cycle detected");
            }

            if (page.isLeaf()) {
                if (page.keys.size() != page.values.size()) {
                    throw new IndexException("Leaf value mismatch");
                }

                if (page.keys.size() > maxKeys) {
                    throw new IndexException("Leaf overflow");
                }

                if (!isRoot && page.keys.size() < minLeafKeys) {
                    throw new IndexException("Leaf underflow");
                }

                for (int i = 1; i < page.keys.size(); i++) {
                    if (page.keys.get(i - 1) >= page.keys.get(i)) {
                        throw new IndexException(
                            "Leaf keys are not strictly ordered"
                        );
                    }
                }

                leaves.add(page);
                return page.keys.isEmpty()
                    ? Integer.MAX_VALUE
                    : page.keys.get(0);
            }

            if (page.children.size() != page.keys.size() + 1) {
                throw new IndexException(
                    "Internal pointer count mismatch"
                );
            }

            if (page.children.size() > order) {
                throw new IndexException("Internal overflow");
            }

            if (isRoot && page.children.size() < 2) {
                throw new IndexException("Invalid root");
            }

            if (!isRoot &&
                page.children.size() < minInternalChildren) {
                throw new IndexException("Internal underflow");
            }

            List<Integer> minima = new ArrayList<>();
            List<Integer> maxima = new ArrayList<>();

            for (IndexPage child : page.children) {
                if (child.parent != page) {
                    throw new IndexException("Invalid parent pointer");
                }

                int min = inspect(child, false, visited, leaves);
                minima.add(min);
            }

            for (int i = 1; i < minima.size(); i++) {
                if (page.keys.get(i - 1) != minima.get(i)) {
                    throw new IndexException("Separator mismatch");
                }
            }

            for (int i = 0; i < page.children.size() - 1; i++) {
                if (maximum(page.children.get(i)) >=
                    minimum(page.children.get(i + 1))) {
                    throw new IndexException("Overlapping key ranges");
                }
            }

            return minima.get(0);
        }

        private int maximum(IndexPage page) {
            while (!page.isLeaf()) {
                page = page.children.get(page.children.size() - 1);
            }

            return page.keys.get(page.keys.size() - 1);
        }

        public synchronized void validate() {
            Set<Integer> visited = new HashSet<>();
            List<IndexPage> leaves = new ArrayList<>();

            inspect(root, true, visited, leaves);

            int total = 0;

            for (int i = 0; i < leaves.size(); i++) {
                IndexPage expected = i + 1 < leaves.size()
                    ? leaves.get(i + 1)
                    : null;

                if (leaves.get(i).nextLeaf != expected) {
                    throw new IndexException("Invalid leaf chain");
                }

                total += leaves.get(i).keys.size();
            }

            if (total != recordCount) {
                throw new IndexException("Record count mismatch");
            }

            if (visited.size() != pages.size()) {
                throw new IndexException("Unreachable index pages");
            }
        }

        public synchronized IndexStatistics statistics() {
            List<PageSnapshot> snapshots = pageSnapshots();

            int leafCount = 0;
            int internalCount = 0;

            for (PageSnapshot snapshot : snapshots) {
                if (snapshot.type() == PageType.LEAF) {
                    leafCount++;
                } else {
                    internalCount++;
                }
            }

            int height = 0;
            IndexPage page = root;

            while (page != null) {
                height++;
                page = page.isLeaf()
                    ? null
                    : page.children.get(0);
            }

            return new IndexStatistics(
                recordCount,
                height,
                snapshots.size(),
                leafCount,
                internalCount,
                reads,
                writes,
                splits
            );
        }

        public IndexMetadata metadata() {
            return metadata;
        }
    }

    static final class BufferPool {
        private final int capacity;

        private final LinkedHashMap<Integer, Boolean> cache =
            new LinkedHashMap<>(16, 0.75f, true);

        private long hits;
        private long misses;
        private long evictions;

        BufferPool(int capacity) {
            if (capacity < 1) {
                throw new IllegalArgumentException(
                    "Buffer capacity must be positive"
                );
            }

            this.capacity = capacity;
        }

        synchronized void access(int pageId) {
            if (cache.containsKey(pageId)) {
                hits++;
                cache.get(pageId);
                return;
            }

            misses++;

            if (cache.size() == capacity) {
                Integer victim = cache.keySet().iterator().next();
                cache.remove(victim);
                evictions++;
            }

            cache.put(pageId, true);
        }

        synchronized Map<String, Double> statistics() {
            long total = hits + misses;

            Map<String, Double> result = new LinkedHashMap<>();

            result.put("hits", (double) hits);
            result.put("misses", (double) misses);
            result.put("evictions", (double) evictions);
            result.put(
                "hitRatio",
                total == 0 ? 0.0 : (double) hits / total
            );

            return result;
        }
    }

    static final class IndexQueryService
        implements AutoCloseable {

        private final BPlusIndex index;
        private final ExecutorService executor;

        IndexQueryService(BPlusIndex index, int workers) {
            this.index = Objects.requireNonNull(index);

            if (workers < 1) {
                throw new IllegalArgumentException(
                    "Worker count must be positive"
                );
            }

            this.executor = Executors.newFixedThreadPool(workers);
        }

        CompletableFuture<String> searchAsync(int key) {
            return CompletableFuture.supplyAsync(
                () -> index.search(key),
                executor
            );
        }

        @Override
        public void close() {
            executor.shutdown();

            try {
                if (!executor.awaitTermination(5, TimeUnit.SECONDS)) {
                    executor.shutdownNow();
                }
            } catch (InterruptedException error) {
                executor.shutdownNow();
                Thread.currentThread().interrupt();
            }
        }
    }

    public static void main(String[] args) {
        IndexMetadata metadata = new IndexMetadata(
            "idx_customer_id",
            "customers",
            "customer_id",
            5,
            IndexState.ACTIVE
        );

        BPlusIndex index = new BPlusIndex(metadata);

        int[] keys = {
            42, 12, 89, 23, 56, 78, 34,
            67, 91, 10, 50, 72, 15, 28
        };

        for (int key : keys) {
            index.insert(
                new IndexRecord(key, "Customer-" + key)
            );
        }

        System.out.println("B+ TREE INDEX INTERNALS");
        System.out.println("Metadata: " + index.metadata());

        System.out.println("\nSearch 56: " + index.search(56));
        System.out.println("Search 999: " + index.search(999));

        System.out.println("\nSorted traversal:");
        System.out.println(index.traversal());

        System.out.println("\nRange scan 20-70:");
        System.out.println(index.rangeScan(20, 70));

        System.out.println("\nIndex page snapshots:");

        for (PageSnapshot page : index.pageSnapshots()) {
            System.out.println(page);
        }

        System.out.println("\nIndex statistics:");
        System.out.println(index.statistics());

        System.out.println("\nAsynchronous enterprise queries:");

        try (IndexQueryService service =
                 new IndexQueryService(index, 3)) {

            List<CompletableFuture<String>> futures = List.of(
                service.searchAsync(12),
                service.searchAsync(56),
                service.searchAsync(91)
            );

            CompletableFuture.allOf(
                futures.toArray(CompletableFuture[]::new)
            ).join();

            futures.forEach(future ->
                System.out.println(future.join())
            );
        }

        System.out.println("\nBuffer pool simulation:");

        BufferPool pool = new BufferPool(4);

        for (PageSnapshot page : index.pageSnapshots()) {
            pool.access(page.pageId());
        }

        for (PageSnapshot page : index.pageSnapshots()) {
            pool.access(page.pageId());
        }

        System.out.println(pool.statistics());

        System.out.println("\nDeletion and maintenance:");

        for (int key : new int[]{10, 12, 15, 23, 28}) {
            index.delete(key);
            index.validate();
        }

        System.out.println("Remaining: " + index.traversal());
        System.out.println("Validated: true");

        System.out.println("\nDuplicate-key validation:");

        try {
            index.insert(new IndexRecord(42, "Duplicate"));
        } catch (DuplicateKeyException error) {
            System.out.println(error.getMessage());
        }

        System.out.println("\nMissing-key validation:");

        try {
            index.delete(999);
        } catch (MissingKeyException error) {
            System.out.println(error.getMessage());
        }

        index.validate();
        System.out.println("\nFinal index statistics:");
        System.out.println(index.statistics());
    }
}
