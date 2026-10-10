import java.time.Instant;
import java.util.ArrayList;
import java.util.Collections;
import java.util.EnumSet;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.function.UnaryOperator;

public class SchemaEvolution {
    enum MigrationStage {
        EXPAND,
        BACKFILL,
        ENFORCE,
        CONTRACT
    }

    enum ChangeRisk {
        ADD_OPTIONAL_FIELD,
        ADD_REQUIRED_FIELD,
        RENAME_FIELD,
        CHANGE_TYPE,
        REMOVE_FIELD
    }

    record CustomerV1(long id, String fullName) {
        CustomerV1 {
            if (id <= 0) {
                throw new IllegalArgumentException("Customer ID must be positive");
            }
            if (fullName == null || fullName.isBlank()) {
                throw new IllegalArgumentException("Full name is required");
            }
        }
    }

    record CustomerV2(long id, String fullName, String email) {
        CustomerV2 {
            if (id <= 0 || fullName == null || fullName.isBlank()) {
                throw new IllegalArgumentException("Invalid customer identity");
            }
        }
    }

    record CustomerV3(
        long id,
        String displayName,
        String email,
        boolean active,
        String locale
    ) {
        CustomerV3 {
            if (id <= 0) {
                throw new IllegalArgumentException("Customer ID must be positive");
            }
            if (displayName == null || displayName.isBlank()) {
                throw new IllegalArgumentException("Display name is required");
            }
            if (email == null || !email.matches("^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$")) {
                throw new IllegalArgumentException("Valid email is required");
            }
            if (locale == null || !locale.matches("[a-z]{2}(-[A-Z]{2})?")) {
                throw new IllegalArgumentException("Invalid locale");
            }
        }
    }

    record MigrationRecord(
        int fromVersion,
        int toVersion,
        String description,
        Instant appliedAt
    ) {}

    record ReviewResult(boolean compatible, String explanation) {}

    static final class MigrationPlan {
        private final int fromVersion;
        private final int toVersion;
        private final UnaryOperator<CustomerV1> normalization;

        MigrationPlan(
            int fromVersion,
            int toVersion,
            UnaryOperator<CustomerV1> normalization
        ) {
            if (toVersion != fromVersion + 1) {
                throw new IllegalArgumentException(
                    "Migration plans must advance one version at a time"
                );
            }
            this.fromVersion = fromVersion;
            this.toVersion = toVersion;
            this.normalization = Objects.requireNonNull(normalization);
        }

        CustomerV1 normalize(CustomerV1 customer) {
            return normalization.apply(customer);
        }

        int fromVersion() {
            return fromVersion;
        }

        int toVersion() {
            return toVersion;
        }
    }

    static final class CompatibilityPolicy {
        private final Map<ChangeRisk, String> rules = Map.of(
            ChangeRisk.ADD_OPTIONAL_FIELD,
            "Usually backward-compatible when old readers ignore unknown fields.",
            ChangeRisk.ADD_REQUIRED_FIELD,
            "Requires a default or staged producer and consumer rollout.",
            ChangeRisk.RENAME_FIELD,
            "Treat as add, dual-read or dual-write, backfill, then remove.",
            ChangeRisk.CHANGE_TYPE,
            "Use a compatible representation or a validated staged conversion.",
            ChangeRisk.REMOVE_FIELD,
            "Remove only after consumers no longer depend on the field."
        );

        ReviewResult evaluate(
            ChangeRisk risk,
            boolean defaultAvailable,
            boolean oldConsumersRemain
        ) {
            String explanation = rules.get(risk);

            boolean compatible = switch (risk) {
                case ADD_OPTIONAL_FIELD -> true;
                case ADD_REQUIRED_FIELD -> defaultAvailable;
                case RENAME_FIELD, CHANGE_TYPE, REMOVE_FIELD -> !oldConsumersRemain;
            };

            return new ReviewResult(compatible, explanation);
        }
    }

    static final class MigrationService {
        private final List<MigrationRecord> history = new ArrayList<>();
        private MigrationStage stage = MigrationStage.EXPAND;
        private boolean oldReadersRunning = true;
        private boolean oldWritersRunning = true;
        private boolean backfillComplete;

        void advance(MigrationStage next) {
            if (next.ordinal() != stage.ordinal() + 1) {
                throw new IllegalStateException(
                    "Invalid migration transition: " + stage + " -> " + next
                );
            }

            switch (next) {
                case BACKFILL -> {
                    // The new representation exists, but historical data
                    // must be repaired before it becomes mandatory.
                }
                case ENFORCE -> {
                    if (!backfillComplete) {
                        throw new IllegalStateException(
                            "Cannot enforce constraints before backfill"
                        );
                    }
                }
                case CONTRACT -> {
                    if (oldReadersRunning || oldWritersRunning) {
                        throw new IllegalStateException(
                            "Cannot remove old fields while old applications run"
                        );
                    }
                }
                case EXPAND -> throw new IllegalStateException(
                    "Expansion is the initial stage"
                );
            }

            stage = next;
        }

        void markBackfillComplete() {
            if (stage != MigrationStage.BACKFILL) {
                throw new IllegalStateException(
                    "Backfill completion is only valid during BACKFILL"
                );
            }
            backfillComplete = true;
        }

        void retireLegacyApplications() {
            oldReadersRunning = false;
            oldWritersRunning = false;
        }

        void recordMigration(int from, int to, String description) {
            if (to != from + 1) {
                throw new IllegalArgumentException("Non-adjacent migration");
            }
            history.add(new MigrationRecord(
                from, to, description, Instant.now()
            ));
        }

        MigrationStage stage() {
            return stage;
        }

        List<MigrationRecord> history() {
            return Collections.unmodifiableList(history);
        }
    }

    static final class CustomerService {
        private final Map<Long, CustomerV3> customers = new HashMap<>();
        private long revision;

        synchronized void replaceAll(
            List<CustomerV3> replacement,
            long expectedRevision
        ) {
            if (expectedRevision != revision) {
                throw new IllegalStateException(
                    "Concurrent update: refresh before replacing records"
                );
            }

            Map<Long, CustomerV3> candidate = new HashMap<>();
            for (CustomerV3 customer : replacement) {
                Objects.requireNonNull(customer);
                if (candidate.putIfAbsent(customer.id(), customer) != null) {
                    throw new IllegalArgumentException(
                        "Duplicate customer ID " + customer.id()
                    );
                }
            }

            // Publish only after every record validates. No partial batch is
            // visible when validation fails.
            customers.clear();
            customers.putAll(candidate);
            revision++;
        }

        synchronized List<CustomerV3> findAll() {
            return customers.values().stream()
                .sorted((left, right) -> Long.compare(left.id(), right.id()))
                .toList();
        }

        synchronized long revision() {
            return revision;
        }
    }

    static CustomerV2 toV2(CustomerV1 oldCustomer) {
        return new CustomerV2(
            oldCustomer.id(),
            oldCustomer.fullName().trim(),
            null
        );
    }

    static CustomerV3 toV3(CustomerV2 customer) {
        if (customer.email() == null || customer.email().isBlank()) {
            throw new IllegalStateException(
                "Backfill email before enforcing the V3 contract"
            );
        }

        return new CustomerV3(
            customer.id(),
            customer.fullName(),
            customer.email(),
            true,
            "en-IN"
        );
    }

    public static void main(String[] args) {
        CompatibilityPolicy policy = new CompatibilityPolicy();

        for (ChangeRisk risk : ChangeRisk.values()) {
            ReviewResult result = policy.evaluate(
                risk,
                false,
                true
            );
            System.out.printf(
                "%s: compatible=%s; %s%n",
                risk, result.compatible(), result.explanation()
            );
        }

        List<CustomerV1> legacyCustomers = List.of(
            new CustomerV1(501, "Meera Iyer"),
            new CustomerV1(502, "Arjun Sinha")
        );

        List<CustomerV2> expanded = legacyCustomers.stream()
            .map(SchemaEvolution::toV2)
            .toList();

        MigrationService migrations = new MigrationService();
        CustomerService service = new CustomerService();

        migrations.recordMigration(1, 2, "Introduce nullable email");
        migrations.advance(MigrationStage.BACKFILL);

        List<CustomerV2> backfilled = expanded.stream()
            .map(customer -> new CustomerV2(
                customer.id(),
                customer.fullName(),
                "customer" + customer.id() + "@example.com"
            ))
            .toList();

        migrations.markBackfillComplete();
        migrations.advance(MigrationStage.ENFORCE);

        List<CustomerV3> current = backfilled.stream()
            .map(SchemaEvolution::toV3)
            .toList();

        service.replaceAll(current, service.revision());
        System.out.println("\nCurrent customer contract:");
        service.findAll().forEach(System.out::println);

        try {
            toV3(new CustomerV2(503, "Unbackfilled Customer", null));
        } catch (IllegalStateException exception) {
            System.out.println("Expected enforcement failure: " + exception.getMessage());
        }

        try {
            service.replaceAll(current, 0);
        } catch (IllegalStateException exception) {
            System.out.println("Expected optimistic-lock failure: " + exception.getMessage());
        }

        try {
            service.replaceAll(
                List.of(current.get(0), current.get(0)),
                service.revision()
            );
        } catch (IllegalArgumentException exception) {
            System.out.println("Expected duplicate failure: " + exception.getMessage());
        }

        // Removing the legacy representation is safe only after every old
        // application instance has stopped reading and writing it.
        migrations.retireLegacyApplications();
        migrations.advance(MigrationStage.CONTRACT);
        migrations.recordMigration(2, 3, "Enforce email and rename display field");

        System.out.println("\nFinal stage: " + migrations.stage());
        migrations.history().forEach(System.out::println);
        System.out.println("Active customer revision: " + service.revision());

        // EnumSet represents explicitly allowed review risks without relying
        // on undocumented string values from a deployment configuration.
        Set<ChangeRisk> reviewedRisks = EnumSet.of(
            ChangeRisk.ADD_OPTIONAL_FIELD,
            ChangeRisk.ADD_REQUIRED_FIELD
        );
        System.out.println("Reviewed changes: " + new HashSet<>(reviewedRisks));
    }
}
