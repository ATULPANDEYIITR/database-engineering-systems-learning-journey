import java.math.BigDecimal;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.TreeSet;

/*
 * Enterprise-oriented JSON document service.
 *
 * Java 17 implementation of document validation, typed path access,
 * containment, selected-field indexes, immutable document snapshots,
 * and atomic attribute updates.
 */
public class JsonDocumentGovernance {

    enum DocumentState {
        ACTIVE,
        ARCHIVED
    }

    static final class DocumentException extends RuntimeException {
        DocumentException(String message) {
            super(message);
        }
    }

    record Product(
        long id,
        String name,
        String category,
        BigDecimal price,
        Map<String, Object> attributes,
        Set<String> tags,
        DocumentState state
    ) {
        Product {
            if (id <= 0) throw new DocumentException("ID must be positive");
            if (name == null || name.isBlank() || name.length() > 120) {
                throw new DocumentException("Invalid product name");
            }
            if (category == null || !category.matches("[a-z][a-z0-9_-]{0,49}")) {
                throw new DocumentException("Invalid category");
            }
            if (price == null || price.signum() < 0 || price.scale() > 2) {
                throw new DocumentException("Invalid price");
            }
            if (state == null) throw new DocumentException("State is required");

            attributes = immutableJsonObject(attributes);
            tags = Collections.unmodifiableSet(new TreeSet<>(tags));
        }
    }

    static Map<String, Object> immutableJsonObject(Map<String, Object> source) {
        if (source == null) throw new DocumentException("Attributes are required");

        @SuppressWarnings("unchecked")
        Map<String, Object> result = (Map<String, Object>) freezeJson(source, 0);

        String serialized = canonical(result);
        if (serialized.getBytes(StandardCharsets.UTF_8).length > 16_384) {
            throw new DocumentException("Attributes exceed 16 KiB");
        }
        return result;
    }

    static Object freezeJson(Object value, int depth) {
        if (depth > 12) throw new DocumentException("Maximum nesting depth exceeded");

        if (value == null || value instanceof String || value instanceof Boolean) {
            return value;
        }

        if (value instanceof Number number) {
            BigDecimal decimal;
            try {
                decimal = new BigDecimal(number.toString());
            } catch (NumberFormatException error) {
                throw new DocumentException("Invalid JSON number");
            }
            return decimal;
        }

        if (value instanceof List<?> list) {
            List<Object> copy = new ArrayList<>();
            for (Object item : list) copy.add(freezeJson(item, depth + 1));
            return Collections.unmodifiableList(copy);
        }

        if (value instanceof Map<?, ?> map) {
            Map<String, Object> copy = new LinkedHashMap<>();
            for (Map.Entry<?, ?> entry : map.entrySet()) {
                if (!(entry.getKey() instanceof String key)) {
                    throw new DocumentException("JSON keys must be strings");
                }
                if (key.equals("__proto__") || key.equals("constructor")) {
                    throw new DocumentException("Forbidden object key");
                }
                copy.put(key, freezeJson(entry.getValue(), depth + 1));
            }
            return Collections.unmodifiableMap(copy);
        }

        throw new DocumentException("Unsupported JSON value: " + value.getClass());
    }

    static String canonical(Object value) {
        if (value == null) return "null";
        if (value instanceof String text) {
            return "\"" + text.replace("\\", "\\\\").replace("\"", "\\\"") + "\"";
        }
        if (value instanceof Boolean || value instanceof BigDecimal) {
            return value.toString();
        }
        if (value instanceof List<?> list) {
            return "[" + String.join(",", list.stream().map(JsonDocumentGovernance::canonical).toList()) + "]";
        }
        if (value instanceof Map<?, ?> map) {
            List<String> keys = map.keySet().stream().map(Object::toString).sorted().toList();
            List<String> pairs = new ArrayList<>();
            for (String key : keys) {
                pairs.add(canonical(key) + ":" + canonical(map.get(key)));
            }
            return "{" + String.join(",", pairs) + "}";
        }
        throw new DocumentException("Unsupported canonical JSON value");
    }

    static boolean contains(Object actual, Object expected) {
        if (expected instanceof Map<?, ?> expectedMap) {
            if (!(actual instanceof Map<?, ?> actualMap)) return false;
            return expectedMap.entrySet().stream().allMatch(entry ->
                actualMap.containsKey(entry.getKey()) &&
                contains(actualMap.get(entry.getKey()), entry.getValue())
            );
        }

        if (expected instanceof List<?> expectedList) {
            if (!(actual instanceof List<?> actualList)) return false;
            return expectedList.stream().allMatch(expectedItem ->
                actualList.stream().anyMatch(actualItem -> contains(actualItem, expectedItem))
            );
        }

        return Objects.equals(actual, expected);
    }

    static final class DocumentService {
        private final Map<Long, Product> products = new HashMap<>();
        private final Map<String, Set<Long>> categoryIndex = new HashMap<>();
        private final Map<String, Set<Long>> attributeIndex = new HashMap<>();
        private long nextId = 1;

        private String attributeKey(String key, Object value) {
            return key + "\u0000" + canonical(value);
        }

        private void addIndex(Map<String, Set<Long>> index, String key, long id) {
            index.computeIfAbsent(key, ignored -> new HashSet<>()).add(id);
        }

        private void removeIndex(Map<String, Set<Long>> index, String key, long id) {
            Set<Long> ids = index.get(key);
            if (ids != null) {
                ids.remove(id);
                if (ids.isEmpty()) index.remove(key);
            }
        }

        private void index(Product product) {
            addIndex(categoryIndex, product.category(), product.id());
            product.attributes().forEach((key, value) ->
                addIndex(attributeIndex, attributeKey(key, value), product.id())
            );
        }

        private void unindex(Product product) {
            removeIndex(categoryIndex, product.category(), product.id());
            product.attributes().forEach((key, value) ->
                removeIndex(attributeIndex, attributeKey(key, value), product.id())
            );
        }

        public synchronized Product create(
            String name,
            String category,
            BigDecimal price,
            Map<String, Object> attributes,
            Set<String> tags
        ) {
            Product product = new Product(
                nextId++, name.trim(), category, price,
                attributes, tags, DocumentState.ACTIVE
            );
            products.put(product.id(), product);
            index(product);
            return product;
        }

        public synchronized List<Product> byCategory(String category) {
            return ids(categoryIndex.get(category));
        }

        public synchronized List<Product> byAttribute(String key, Object value) {
            return ids(attributeIndex.get(attributeKey(key, value)));
        }

        private List<Product> ids(Set<Long> ids) {
            if (ids == null) return List.of();
            return ids.stream().sorted().map(products::get).toList();
        }

        public synchronized List<Product> containing(Map<String, Object> required) {
            Map<String, Object> safe = immutableJsonObject(required);
            return products.values().stream()
                .filter(product -> contains(product.attributes(), safe))
                .sorted((a, b) -> Long.compare(a.id(), b.id()))
                .toList();
        }

        public synchronized Object path(long id, String... path) {
            Product product = products.get(id);
            if (product == null) return null;

            Object current = product.attributes();
            for (String segment : path) {
                if (current instanceof Map<?, ?> map) {
                    if (!map.containsKey(segment)) return null;
                    current = map.get(segment);
                } else if (current instanceof List<?> list) {
                    try {
                        int index = Integer.parseInt(segment);
                        if (index < 0 || index >= list.size()) return null;
                        current = list.get(index);
                    } catch (NumberFormatException error) {
                        return null;
                    }
                } else {
                    return null;
                }
            }
            return current;
        }

        public synchronized Product updateAttributes(long id, Map<String, Object> patch) {
            Product current = products.get(id);
            if (current == null) throw new DocumentException("Product does not exist");

            Map<String, Object> merged = new LinkedHashMap<>(current.attributes());
            merged.putAll(patch);

            Product replacement = new Product(
                current.id(), current.name(), current.category(), current.price(),
                merged, current.tags(), current.state()
            );

            unindex(current);
            products.put(id, replacement);
            index(replacement);
            return replacement;
        }
    }

    public static void main(String[] args) {
        DocumentService service = new DocumentService();

        Product laptop = service.create(
            "Engineering Laptop",
            "electronics",
            new BigDecimal("1299.99"),
            Map.of(
                "brand", "Northstar",
                "wireless", true,
                "specs", Map.of("ram_gb", 32, "storage_gb", 1024),
                "ports", List.of("USB-C", "HDMI")
            ),
            Set.of("developer", "portable")
        );

        service.create(
            "Operations Monitor",
            "electronics",
            new BigDecimal("349.50"),
            Map.of(
                "brand", "Northstar",
                "wireless", false,
                "specs", Map.of("ram_gb", 0, "storage_gb", 0),
                "ports", List.of("HDMI", "DisplayPort")
            ),
            Set.of("office")
        );

        System.out.println("Electronics: " + service.byCategory("electronics").size());
        System.out.println("Wireless: " + service.byAttribute("wireless", true).size());
        System.out.println("RAM: " + service.path(laptop.id(), "specs", "ram_gb"));

        System.out.println(
            "32 GB RAM matches: " +
            service.containing(Map.of("specs", Map.of("ram_gb", 32))).size()
        );

        service.updateAttributes(
            2,
            Map.of("wireless", true, "warranty_years", 3)
        );

        System.out.println("Wireless after update: " + service.byAttribute("wireless", true).size());

        try {
            service.create(
                "Invalid",
                "electronics",
                new BigDecimal("-1.00"),
                Map.of(),
                Set.of()
            );
            throw new AssertionError("Negative price was accepted");
        } catch (DocumentException expected) {
            System.out.println("Rejected invalid product: " + expected.getMessage());
        }

        if (service.path(laptop.id(), "missing") != null) {
            throw new AssertionError("Missing path should return null");
        }

        System.out.println("All assertions passed.");
    }
}
