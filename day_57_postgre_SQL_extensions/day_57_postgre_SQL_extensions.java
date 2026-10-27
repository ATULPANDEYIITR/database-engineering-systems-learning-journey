import java.util.ArrayList;
import java.util.Collections;
import java.util.EnumSet;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;

public class PostgresExtensionsPostGIS {

    enum ExtensionState {
        AVAILABLE,
        INSTALLED
    }

    enum GeometryType {
        POINT,
        LINESTRING,
        POLYGON
    }

    record Extension(
            String name,
            String version,
            String category,
            Set<String> dependencies
    ) {
        Extension {
            Objects.requireNonNull(name);
            Objects.requireNonNull(version);
            Objects.requireNonNull(category);
            dependencies = Set.copyOf(dependencies);

            if (name.isBlank() || version.isBlank()) {
                throw new IllegalArgumentException(
                        "Extension name and version are required"
                );
            }
        }
    }

    record Point(double longitude, double latitude) {
        Point {
            if (!Double.isFinite(longitude) || !Double.isFinite(latitude)) {
                throw new IllegalArgumentException(
                        "Coordinates must be finite"
                );
            }

            if (longitude < -180 || longitude > 180) {
                throw new IllegalArgumentException(
                        "Longitude outside valid range"
                );
            }

            if (latitude < -90 || latitude > 90) {
                throw new IllegalArgumentException(
                        "Latitude outside valid range"
                );
            }
        }
    }

    record SpatialFeature(
            int id,
            String name,
            GeometryType geometryType,
            List<Point> coordinates,
            Map<String, String> properties
    ) {
        SpatialFeature {
            if (id <= 0 || name == null || name.isBlank()) {
                throw new IllegalArgumentException(
                        "Invalid spatial feature identity"
                );
            }

            coordinates = List.copyOf(coordinates);
            properties = Map.copyOf(properties);

            if (coordinates.isEmpty()) {
                throw new IllegalArgumentException(
                        "Spatial feature requires coordinates"
                );
            }

            if (geometryType == GeometryType.POINT &&
                    coordinates.size() != 1) {
                throw new IllegalArgumentException(
                        "Point requires exactly one coordinate"
                );
            }

            if (geometryType == GeometryType.LINESTRING &&
                    coordinates.size() < 2) {
                throw new IllegalArgumentException(
                        "LineString requires at least two coordinates"
                );
            }

            if (geometryType == GeometryType.POLYGON) {
                if (coordinates.size() < 4) {
                    throw new IllegalArgumentException(
                            "Polygon requires at least four coordinates"
                    );
                }

                Point first = coordinates.getFirst();
                Point last = coordinates.getLast();

                if (!first.equals(last)) {
                    throw new IllegalArgumentException(
                            "Polygon ring must be closed"
                    );
                }
            }
        }
    }

    static class ExtensionRegistry {
        private final Map<String, Extension> catalog = new HashMap<>();
        private final Set<String> installed = new HashSet<>();

        void register(Extension extension) {
            if (catalog.putIfAbsent(extension.name(), extension) != null) {
                throw new IllegalArgumentException(
                        "Extension already registered: " + extension.name()
                );
            }
        }

        void install(String name) {
            Extension extension = catalog.get(name);

            if (extension == null) {
                throw new IllegalArgumentException(
                        "Unknown extension: " + name
                );
            }

            for (String dependency : extension.dependencies()) {
                if (!installed.contains(dependency)) {
                    throw new IllegalStateException(
                            "Dependency " + dependency +
                            " is required before installing " + name
                    );
                }
            }

            installed.add(name);
        }

        boolean isInstalled(String name) {
            return installed.contains(name);
        }

        List<Extension> availableExtensions() {
            return catalog.values()
                    .stream()
                    .sorted((a, b) -> a.name().compareTo(b.name()))
                    .toList();
        }
    }

    interface MergeRule {
        boolean evaluate(MergeContext context);
    }

    record MergeContext(
            boolean pullRequestOpen,
            boolean conversationsResolved,
            boolean approvalsSatisfied,
            Set<String> requiredChecks,
            Map<String, Boolean> checks,
            boolean protectedBranch,
            boolean directPush
    ) {
        MergeContext {
            requiredChecks = Set.copyOf(requiredChecks);
            checks = Map.copyOf(checks);
        }
    }

    static final class RequiredChecksRule implements MergeRule {
        @Override
        public boolean evaluate(MergeContext context) {
            return context.requiredChecks()
                    .stream()
                    .allMatch(check ->
                            Boolean.TRUE.equals(context.checks().get(check)));
        }
    }

    static final class ReviewRule implements MergeRule {
        @Override
        public boolean evaluate(MergeContext context) {
            return context.approvalsSatisfied()
                    && context.conversationsResolved();
        }
    }

    static final class ProtectedBranchRule implements MergeRule {
        @Override
        public boolean evaluate(MergeContext context) {
            return !(context.protectedBranch() && context.directPush());
        }
    }

    static final class MergeEligibilityService {
        private final List<MergeRule> rules;

        MergeEligibilityService(List<MergeRule> rules) {
            this.rules = List.copyOf(rules);
        }

        boolean eligible(MergeContext context) {
            return context.pullRequestOpen()
                    && rules.stream().allMatch(rule -> rule.evaluate(context));
        }
    }

    static double haversineKm(Point first, Point second) {
        double earthRadiusKm = 6371.0088;

        double latitude1 = Math.toRadians(first.latitude());
        double latitude2 = Math.toRadians(second.latitude());
        double deltaLatitude =
                latitude2 - latitude1;
        double deltaLongitude =
                Math.toRadians(second.longitude() - first.longitude());

        double h =
                Math.pow(Math.sin(deltaLatitude / 2), 2)
                + Math.cos(latitude1)
                * Math.cos(latitude2)
                * Math.pow(Math.sin(deltaLongitude / 2), 2);

        h = Math.max(0, Math.min(1, h));

        return 2 * earthRadiusKm *
                Math.atan2(Math.sqrt(h), Math.sqrt(1 - h));
    }

    static SpatialFeature nearest(
            Point origin,
            List<SpatialFeature> features
    ) {
        return features.stream()
                .filter(feature ->
                        feature.geometryType() == GeometryType.POINT)
                .min((a, b) ->
                        Double.compare(
                                haversineKm(
                                        origin,
                                        a.coordinates().getFirst()
                                ),
                                haversineKm(
                                        origin,
                                        b.coordinates().getFirst()
                                )
                        ))
                .orElseThrow(() ->
                        new IllegalStateException(
                                "No Point features available"
                        ));
    }

    public static void main(String[] args) {
        ExtensionRegistry registry = new ExtensionRegistry();

        registry.register(new Extension(
                "pgcrypto",
                "1.3",
                "security",
                Set.of()
        ));

        registry.register(new Extension(
                "postgis",
                "3.x",
                "spatial",
                Set.of()
        ));

        registry.register(new Extension(
                "postgis_raster",
                "3.x",
                "spatial",
                Set.of("postgis")
        ));

        registry.register(new Extension(
                "postgis_topology",
                "3.x",
                "spatial",
                Set.of("postgis")
        ));

        registry.install("pgcrypto");
        registry.install("postgis");
        registry.install("postgis_raster");
        registry.install("postgis_topology");

        System.out.println("=== Extension Registry ===");
        for (Extension extension : registry.availableExtensions()) {
            String state = registry.isInstalled(extension.name())
                    ? "installed"
                    : "available";

            System.out.printf(
                    "%-22s %-8s %-12s %s%n",
                    extension.name(),
                    extension.version(),
                    extension.category(),
                    state
            );
        }

        List<SpatialFeature> facilities = List.of(
                new SpatialFeature(
                        1,
                        "Lucknow Office",
                        GeometryType.POINT,
                        List.of(new Point(80.9462, 26.8467)),
                        Map.of("type", "office")
                ),
                new SpatialFeature(
                        2,
                        "Kanpur Depot",
                        GeometryType.POINT,
                        List.of(new Point(80.3319, 26.4499)),
                        Map.of("type", "depot")
                ),
                new SpatialFeature(
                        3,
                        "Prayagraj Depot",
                        GeometryType.POINT,
                        List.of(new Point(81.8463, 25.4358)),
                        Map.of("type", "depot")
                )
        );

        Point origin = facilities.getFirst().coordinates().getFirst();
        SpatialFeature nearest = nearest(origin, facilities.subList(1, facilities.size()));

        System.out.printf(
                "%nNearest depot to %s: %s (%.2f km)%n",
                facilities.getFirst().name(),
                nearest.name(),
                haversineKm(origin, nearest.coordinates().getFirst())
        );

        MergeContext mergeContext = new MergeContext(
                true,
                true,
                true,
                Set.of("unit-tests", "schema-validation", "security-scan"),
                Map.of(
                        "unit-tests", true,
                        "schema-validation", true,
                        "security-scan", true
                ),
                true,
                false
        );

        MergeEligibilityService service =
                new MergeEligibilityService(List.of(
                        new ReviewRule(),
                        new RequiredChecksRule(),
                        new ProtectedBranchRule()
                ));

        System.out.println(
                "Protected-branch change eligible: "
                        + service.eligible(mergeContext)
        );

        MergeContext failedContext = new MergeContext(
                true,
                true,
                false,
                Set.of("unit-tests"),
                Map.of("unit-tests", true),
                true,
                false
        );

        System.out.println(
                "Change with missing approval eligible: "
                        + service.eligible(failedContext)
        );

        System.out.println(
                "Spatial design decision: production spatial filtering "
                        + "should use database-side PostGIS predicates and "
                        + "spatial indexes instead of transferring every "
                        + "geometry to the application."
        );
    }
}
