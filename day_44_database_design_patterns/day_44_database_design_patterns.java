import java.time.Instant;
import java.util.ArrayList;
import java.util.EnumMap;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.UUID;
import java.util.stream.Collectors;

/**
 * Enterprise database lifecycle model for an equipment-management service.
 *
 * Java 17 or later.
 *
 * The domain model separates business status from deletion state, represents
 * audit entries as immutable records, and applies version checks before
 * state changes. The in-memory service demonstrates the domain rules;
 * durable atomicity must be implemented with a transactional database.
 */
public class DatabasePatterns {

    enum EquipmentStatus {
        REQUESTED,
        APPROVED,
        IN_SERVICE,
        MAINTENANCE,
        RETIRED
    }

    enum AuditAction {
        CREATED,
        RENAMED,
        STATUS_CHANGED,
        SOFT_DELETED,
        RESTORED
    }

    static final class DomainException extends RuntimeException {
        DomainException(String message) {
            super(message);
        }
    }

    static final class ValidationException extends DomainException {
        ValidationException(String message) {
            super(message);
        }
    }

    static final class NotFoundException extends DomainException {
        NotFoundException(String message) {
            super(message);
        }
    }

    static final class InvalidTransitionException extends DomainException {
        InvalidTransitionException(String message) {
            super(message);
        }
    }

    static final class OptimisticLockException extends DomainException {
        OptimisticLockException(String message) {
            super(message);
        }
    }

    static final class IdempotencyConflictException extends DomainException {
        IdempotencyConflictException(String message) {
            super(message);
        }
    }

    record AuditEntry(
        UUID eventId,
        UUID entityId,
        AuditAction action,
        String actor,
        Instant occurredAt,
        Map<String, String> oldValues,
        Map<String, String> newValues,
        String reason,
        String correlationId
    ) {
        AuditEntry {
            Objects.requireNonNull(eventId);
            Objects.requireNonNull(entityId);
            Objects.requireNonNull(action);
            Objects.requireNonNull(actor);
            Objects.requireNonNull(occurredAt);
            oldValues = Map.copyOf(oldValues);
            newValues = Map.copyOf(newValues);
            Objects.requireNonNull(correlationId);
        }
    }

    static final class Equipment {
        private final UUID id;
        private final String assetTag;
        private String name;
        private EquipmentStatus status;
        private boolean deleted;
        private Instant deletedAt;
        private String deletedBy;
        private final Instant createdAt;
        private final String createdBy;
        private Instant updatedAt;
        private String updatedBy;
        private long version;

        Equipment(String assetTag, String name, String actor) {
            this.id = UUID.randomUUID();
            this.assetTag = requireText(assetTag, "Asset tag").toUpperCase();
            this.name = requireText(name, "Equipment name");
            this.status = EquipmentStatus.REQUESTED;
            this.deleted = false;
            this.createdAt = Instant.now();
            this.createdBy = requireText(actor, "Actor");
            this.updatedAt = createdAt;
            this.updatedBy = actor;
            this.version = 1;
            validate();
        }

        private static String requireText(String value, String field) {
            if (value == null || value.isBlank()) {
                throw new ValidationException(field + " is required.");
            }
            return value.trim();
        }

        private void validate() {
            if (deleted && (deletedAt == null || deletedBy == null
                    || deletedBy.isBlank())) {
                throw new ValidationException(
                    "Deleted records require deletion metadata."
                );
            }
            if (!deleted && (deletedAt != null || deletedBy != null)) {
                throw new ValidationException(
                    "Active records cannot retain deletion metadata."
                );
            }
            if (version < 1) {
                throw new ValidationException("Version must be positive.");
            }
        }

        UUID id() {
            return id;
        }

        String assetTag() {
            return assetTag;
        }

        String name() {
            return name;
        }

        EquipmentStatus status() {
            return status;
        }

        boolean deleted() {
            return deleted;
        }

        Instant deletedAt() {
            return deletedAt;
        }

        long version() {
            return version;
        }

        String describe() {
            return "Equipment{id=%s, tag=%s, name=%s, status=%s, deleted=%s, version=%d}"
                .formatted(id, assetTag, name, status, deleted, version);
        }
    }

    record IdempotentResult(UUID equipmentId, String actor, UUID eventId) {}

    static final class EquipmentService {
        private final Map<UUID, Equipment> equipment = new HashMap<>();
        private final Map<String, UUID> assetTagIndex = new HashMap<>();
        private final List<AuditEntry> auditEntries = new ArrayList<>();
        private final Map<String, IdempotentResult> idempotency = new HashMap<>();

        private final Map<EquipmentStatus, Set<EquipmentStatus>> transitions =
            createTransitionRules();

        private static Map<EquipmentStatus, Set<EquipmentStatus>>
        createTransitionRules() {
            Map<EquipmentStatus, Set<EquipmentStatus>> rules =
                new EnumMap<>(EquipmentStatus.class);

            rules.put(EquipmentStatus.REQUESTED,
                Set.of(EquipmentStatus.APPROVED));
            rules.put(EquipmentStatus.APPROVED,
                Set.of(EquipmentStatus.IN_SERVICE, EquipmentStatus.RETIRED));
            rules.put(EquipmentStatus.IN_SERVICE,
                Set.of(EquipmentStatus.MAINTENANCE, EquipmentStatus.RETIRED));
            rules.put(EquipmentStatus.MAINTENANCE,
                Set.of(EquipmentStatus.IN_SERVICE, EquipmentStatus.RETIRED));
            rules.put(EquipmentStatus.RETIRED, Set.of());

            return Map.copyOf(rules);
        }

        private static String requireText(String value, String field) {
            if (value == null || value.isBlank()) {
                throw new ValidationException(field + " is required.");
            }
            return value.trim();
        }

        private Equipment requireEquipment(UUID id, boolean includeDeleted) {
            Equipment item = equipment.get(id);
            if (item == null || (item.deleted && !includeDeleted)) {
                throw new NotFoundException("Equipment was not found.");
            }
            return item;
        }

        private void verifyVersion(Equipment item, long expectedVersion) {
            if (item.version != expectedVersion) {
                throw new OptimisticLockException(
                    "Expected version %d but found %d."
                        .formatted(expectedVersion, item.version)
                );
            }
        }

        private AuditEntry appendEvent(
            Equipment item,
            AuditAction action,
            String actor,
            Map<String, String> oldValues,
            Map<String, String> newValues,
            String reason,
            String correlationId
        ) {
            AuditEntry entry = new AuditEntry(
                UUID.randomUUID(),
                item.id,
                action,
                actor,
                Instant.now(),
                oldValues,
                newValues,
                reason,
                correlationId
            );
            auditEntries.add(entry);
            return entry;
        }

        Equipment create(String assetTag, String name, String actor) {
            actor = requireText(actor, "Actor");
            Equipment item = new Equipment(assetTag, name, actor);

            if (assetTagIndex.containsKey(item.assetTag)) {
                throw new ValidationException(
                    "Asset tag already exists: " + item.assetTag
                );
            }

            equipment.put(item.id, item);
            assetTagIndex.put(item.assetTag, item.id);

            appendEvent(
                item,
                AuditAction.CREATED,
                actor,
                Map.of(),
                Map.of(
                    "assetTag", item.assetTag,
                    "name", item.name,
                    "status", item.status.name(),
                    "version", Long.toString(item.version)
                ),
                "Initial registration",
                "create-" + item.id
            );
            return item;
        }

        AuditEntry changeStatus(
            UUID id,
            EquipmentStatus target,
            long expectedVersion,
            String actor,
            String reason
        ) {
            actor = requireText(actor, "Actor");
            reason = requireText(reason, "Reason");
            Objects.requireNonNull(target, "Target status");

            Equipment item = requireEquipment(id, false);
            verifyVersion(item, expectedVersion);

            if (!transitions.get(item.status).contains(target)) {
                throw new InvalidTransitionException(
                    "Transition %s -> %s is prohibited."
                        .formatted(item.status, target)
                );
            }

            String oldStatus = item.status.name();
            item.status = target;
            item.version++;
            item.updatedAt = Instant.now();
            item.updatedBy = actor;
            item.validate();

            return appendEvent(
                item,
                AuditAction.STATUS_CHANGED,
                actor,
                Map.of("status", oldStatus),
                Map.of(
                    "status", item.status.name(),
                    "version", Long.toString(item.version)
                ),
                reason,
                "status-" + id + "-" + item.version
            );
        }

        AuditEntry rename(
            UUID id,
            String newName,
            long expectedVersion,
            String actor,
            String reason
        ) {
            actor = requireText(actor, "Actor");
            newName = requireText(newName, "Equipment name");
            reason = requireText(reason, "Reason");

            Equipment item = requireEquipment(id, false);
            verifyVersion(item, expectedVersion);

            if (item.name.equals(newName)) {
                throw new ValidationException(
                    "New name must differ from current name."
                );
            }

            String oldName = item.name;
            item.name = newName;
            item.version++;
            item.updatedAt = Instant.now();
            item.updatedBy = actor;
            item.validate();

            return appendEvent(
                item,
                AuditAction.RENAMED,
                actor,
                Map.of("name", oldName),
                Map.of(
                    "name", item.name,
                    "version", Long.toString(item.version)
                ),
                reason,
                "rename-" + id + "-" + item.version
            );
        }

        AuditEntry softDelete(
            UUID id,
            long expectedVersion,
            String actor,
            String reason,
            String operationKey
        ) {
            actor = requireText(actor, "Actor");
            reason = requireText(reason, "Reason");
            operationKey = requireText(operationKey, "Operation key");

            IdempotentResult previous = idempotency.get(operationKey);
            if (previous != null) {
                if (!previous.equipmentId().equals(id)
                    || !previous.actor().equals(actor)) {
                    throw new IdempotencyConflictException(
                        "Idempotency key belongs to another operation."
                    );
                }

                return auditEntries.stream()
                    .filter(entry -> entry.eventId().equals(previous.eventId()))
                    .findFirst()
                    .orElseThrow(() -> new DomainException(
                        "Idempotency event is missing."
                    ));
            }

            Equipment item = requireEquipment(id, false);
            verifyVersion(item, expectedVersion);

            item.deleted = true;
            item.deletedAt = Instant.now();
            item.deletedBy = actor;
            item.version++;
            item.updatedAt = Instant.now();
            item.updatedBy = actor;
            item.validate();

            AuditEntry entry = appendEvent(
                item,
                AuditAction.SOFT_DELETED,
                actor,
                Map.of("deleted", "false"),
                Map.of(
                    "deleted", "true",
                    "deletedAt", item.deletedAt.toString(),
                    "deletedBy", actor,
                    "version", Long.toString(item.version)
                ),
                reason,
                operationKey
            );

            idempotency.put(
                operationKey, new IdempotentResult(id, actor, entry.eventId())
            );
            return entry;
        }

        AuditEntry restore(
            UUID id,
            long expectedVersion,
            String actor,
            String reason
        ) {
            actor = requireText(actor, "Actor");
            reason = requireText(reason, "Reason");

            Equipment item = requireEquipment(id, true);
            verifyVersion(item, expectedVersion);

            if (!item.deleted) {
                throw new InvalidTransitionException(
                    "Equipment is already active."
                );
            }

            String previousDeletedAt = item.deletedAt.toString();
            item.deleted = false;
            item.deletedAt = null;
            item.deletedBy = null;
            item.version++;
            item.updatedAt = Instant.now();
            item.updatedBy = actor;
            item.validate();

            return appendEvent(
                item,
                AuditAction.RESTORED,
                actor,
                Map.of(
                    "deleted", "true",
                    "deletedAt", previousDeletedAt
                ),
                Map.of(
                    "deleted", "false",
                    "version", Long.toString(item.version)
                ),
                reason,
                "restore-" + id + "-" + item.version
            );
        }

        List<Equipment> listActive() {
            return equipment.values().stream()
                .filter(item -> !item.deleted)
                .sorted((left, right) ->
                    left.assetTag.compareTo(right.assetTag))
                .toList();
        }

        List<AuditEntry> history(UUID id) {
            if (!equipment.containsKey(id)) {
                throw new NotFoundException("Equipment was not found.");
            }
            return auditEntries.stream()
                .filter(entry -> entry.entityId().equals(id))
                .toList();
        }

        List<AuditEntry> eventsByAction(AuditAction action) {
            return auditEntries.stream()
                .filter(entry -> entry.action() == action)
                .toList();
        }

        List<String> integrityIssues() {
            List<String> issues = new ArrayList<>();
            for (Equipment item : equipment.values()) {
                List<AuditEntry> history = history(item.id);
                if (history.isEmpty()
                    || history.get(0).action() != AuditAction.CREATED) {
                    issues.add(item.id + ": missing creation event");
                }
            }
            return issues;
        }
    }

    public static void main(String[] args) {
        EquipmentService service = new EquipmentService();

        Equipment pump = service.create(
            "pump-310",
            "Emergency cooling pump",
            "asset-clerk"
        );
        System.out.println(pump.describe());

        AuditEntry approval = service.changeStatus(
            pump.id(),
            EquipmentStatus.APPROVED,
            pump.version(),
            "maintenance-manager",
            "Engineering specification approved."
        );

        AuditEntry deployment = service.changeStatus(
            pump.id(),
            EquipmentStatus.IN_SERVICE,
            pump.version(),
            "plant-supervisor",
            "Installation checks completed."
        );

        AuditEntry deletion = service.softDelete(
            pump.id(),
            pump.version(),
            "records-officer",
            "Incorrect department assignment.",
            "delete-pump-310"
        );

        System.out.println("Active count after deletion: "
            + service.listActive().size());

        AuditEntry repeatedDeletion = service.softDelete(
            pump.id(),
            pump.version() - 1,
            "records-officer",
            "Incorrect department assignment.",
            "delete-pump-310"
        );
        if (!deletion.eventId().equals(repeatedDeletion.eventId())) {
            throw new AssertionError("Idempotent operation changed its event.");
        }

        AuditEntry restoration = service.restore(
            pump.id(),
            pump.version(),
            "records-officer",
            "Department ownership verified."
        );

        try {
            service.changeStatus(
                pump.id(),
                EquipmentStatus.REQUESTED,
                pump.version(),
                "plant-supervisor",
                "Invalid backward transition."
            );
        } catch (InvalidTransitionException exception) {
            System.out.println("Rejected transition: " + exception.getMessage());
        }

        try {
            service.rename(
                pump.id(),
                "Cooling pump revised",
                1,
                "asset-clerk",
                "Stale write test."
            );
        } catch (OptimisticLockException exception) {
            System.out.println("Rejected stale write: " + exception.getMessage());
        }

        System.out.println("Audit history:");
        service.history(pump.id()).forEach(System.out::println);

        System.out.println("Status changes: "
            + service.eventsByAction(AuditAction.STATUS_CHANGED).size());
        System.out.println("Integrity issues: " + service.integrityIssues());

        if (approval == null || deployment == null || restoration == null) {
            throw new AssertionError("Expected lifecycle events were not created.");
        }
    }
}
