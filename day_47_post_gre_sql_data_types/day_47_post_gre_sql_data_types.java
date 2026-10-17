import java.math.BigDecimal;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.UUID;
import java.util.regex.Pattern;

/**
 * PostgreSQL data types in an enterprise equipment registry.
 *
 * Compile: javac PostgresDataTypes.java
 * Run:     java PostgresDataTypes
 *
 * Java domain types are not identical to PostgreSQL types. This program
 * explicitly validates the conversion boundary between them.
 */
public class PostgresDataTypes {

    private static final Pattern SERIAL_PATTERN =
            Pattern.compile("[A-Z]{2}-\\d{4}-\\d{4}");

    record EquipmentId(UUID value) {
        EquipmentId {
            Objects.requireNonNull(value, "UUID is required");
        }

        static EquipmentId generate() {
            return new EquipmentId(UUID.randomUUID());
        }

        static EquipmentId parse(String value) {
            return new EquipmentId(UUID.fromString(value));
        }
    }

    enum CalibrationState {
        VALID,
        EXPIRED,
        UNKNOWN
    }

    record Pressure(BigDecimal value) {
        Pressure {
            Objects.requireNonNull(value, "Pressure is required");

            if (value.signum() < 0) {
                throw new IllegalArgumentException(
                        "Pressure cannot be negative"
                );
            }

            // PostgreSQL NUMERIC(10,2) permits eight integer digits
            // and two fractional digits. Reject excess scale explicitly.
            if (value.scale() > 2) {
                throw new IllegalArgumentException(
                        "Pressure exceeds the allowed decimal scale"
                );
            }

            if (value.precision() > 10) {
                throw new IllegalArgumentException(
                        "Pressure exceeds NUMERIC(10,2)"
                );
            }
        }

        String databaseValue() {
            return value.toPlainString();
        }
    }

    static final class JsonDocument {
        private final Map<String, Object> fields;

        JsonDocument(Map<String, Object> fields) {
            Objects.requireNonNull(fields, "JSON fields are required");

            Map<String, Object> copy = new LinkedHashMap<>();

            for (Map.Entry<String, Object> entry : fields.entrySet()) {
                String key = Objects.requireNonNull(entry.getKey());

                if (key.isBlank()) {
                    throw new IllegalArgumentException(
                            "JSON object keys cannot be blank"
                    );
                }

                copy.put(key, entry.getValue());
            }

            this.fields = Map.copyOf(copy);
        }

        Object get(String key) {
            return fields.get(key);
        }

        Map<String, Object> asMap() {
            return fields;
        }
    }

    record Equipment(
            EquipmentId id,
            String serialNumber,
            String manufacturer,
            Pressure maximumPressure,
            Boolean active,
            List<String> tags,
            JsonDocument metadata,
            CalibrationState calibrationState,
            OffsetDateTime createdAt
    ) {
        Equipment {
            Objects.requireNonNull(id);
            Objects.requireNonNull(maximumPressure);
            Objects.requireNonNull(metadata);
            Objects.requireNonNull(calibrationState);
            Objects.requireNonNull(createdAt);

            if (serialNumber == null ||
                    !SERIAL_PATTERN.matcher(serialNumber).matches()) {
                throw new IllegalArgumentException(
                        "Serial number must match AA-YYYY-NNNN"
                );
            }

            if (manufacturer == null || manufacturer.isBlank()) {
                throw new IllegalArgumentException(
                        "Manufacturer is required"
                );
            }

            // List.copyOf rejects null elements and prevents mutation after
            // the record has been validated.
            tags = List.copyOf(tags);

            if (tags.stream().anyMatch(String::isBlank)) {
                throw new IllegalArgumentException(
                        "Tags must not be blank"
                );
            }

            if (tags.stream().distinct().count() != tags.size()) {
                throw new IllegalArgumentException(
                        "Tags must be unique"
                );
            }

            if (!createdAt.getOffset().equals(ZoneOffset.UTC)) {
                throw new IllegalArgumentException(
                        "createdAt must use UTC"
                );
            }
        }
    }

    static class EquipmentRegistry {
        private final Map<UUID, Equipment> records = new LinkedHashMap<>();
        private final Map<String, UUID> serialIndex = new LinkedHashMap<>();

        void register(Equipment equipment) {
            UUID id = equipment.id().value();

            if (records.containsKey(id)) {
                throw new IllegalStateException(
                        "Equipment UUID already exists"
                );
            }

            if (serialIndex.containsKey(equipment.serialNumber())) {
                throw new IllegalStateException(
                        "Serial number already exists"
                );
            }

            records.put(id, equipment);
            serialIndex.put(equipment.serialNumber(), id);
        }

        Equipment findBySerial(String serialNumber) {
            UUID id = serialIndex.get(serialNumber);
            return id == null ? null : records.get(id);
        }

        List<Equipment> requiringCalibrationReview() {
            List<Equipment> result = new ArrayList<>();

            for (Equipment equipment : records.values()) {
                if (equipment.calibrationState() != CalibrationState.VALID) {
                    result.add(equipment);
                }
            }

            return List.copyOf(result);
        }
    }

    private static Equipment createEquipment(
            String serial,
            String manufacturer,
            String pressure,
            Boolean active,
            List<String> tags,
            CalibrationState calibration,
            Map<String, Object> metadata
    ) {
        return new Equipment(
                EquipmentId.generate(),
                serial,
                manufacturer,
                new Pressure(new BigDecimal(pressure)),
                active,
                tags,
                new JsonDocument(metadata),
                calibration,
                OffsetDateTime.now(ZoneOffset.UTC)
        );
    }

    public static void main(String[] args) {
        EquipmentRegistry registry = new EquipmentRegistry();

        Equipment first = createEquipment(
                "PS-2026-0042",
                "Precision Instruments Ltd.",
                "7.42",
                true,
                List.of("plant-a", "critical"),
                CalibrationState.VALID,
                Map.of(
                        "protocol", "modbus",
                        "certificate_valid", true,
                        "sample_rate_hz", 10
                )
        );

        Equipment second = createEquipment(
                "PS-2026-0043",
                "Industrial Measurement Systems",
                "0.00",
                null,
                List.of("plant-b"),
                CalibrationState.UNKNOWN,
                Map.of(
                        "protocol", "mqtt",
                        "certificate_valid", false
                )
        );

        registry.register(first);
        registry.register(second);

        System.out.println("Registered equipment: " + first.id().value());
        System.out.println("Serial: " + first.serialNumber());
        System.out.println(
                "NUMERIC database representation: " +
                        first.maximumPressure().databaseValue()
        );
        System.out.println("JSONB protocol: " + first.metadata().get("protocol"));
        System.out.println("PostgreSQL text[] equivalent: " + first.tags());
        System.out.println("Second equipment active: " + second.active());

        Equipment found = registry.findBySerial("PS-2026-0042");
        System.out.println("Registry lookup: " + found.serialNumber());

        System.out.println("Calibration review required:");
        for (Equipment equipment : registry.requiringCalibrationReview()) {
            System.out.println(
                    equipment.serialNumber() + " -> " +
                            equipment.calibrationState()
            );
        }

        try {
            new Pressure(new BigDecimal("999999999.99"));
        } catch (IllegalArgumentException error) {
            System.out.println("Rejected pressure: " + error.getMessage());
        }

        try {
            registry.register(createEquipment(
                    "PS-2026-0042",
                    "Duplicate Serial Manufacturer",
                    "2.50",
                    false,
                    List.of("plant-c"),
                    CalibrationState.VALID,
                    Map.of("protocol", "modbus")
            ));
        } catch (IllegalStateException error) {
            System.out.println("Rejected duplicate: " + error.getMessage());
        }

        /*
         * Database mapping:
         * EquipmentId.value        -> UUID
         * Pressure.value           -> NUMERIC(10,2)
         * serialNumber             -> VARCHAR(13) or TEXT with a constraint
         * active                   -> BOOLEAN, nullable if unknown is allowed
         * metadata                 -> JSONB
         * tags                     -> TEXT[]
         * createdAt                -> TIMESTAMPTZ
         *
         * Application validation improves error messages; PostgreSQL
         * constraints remain necessary for multi-client data integrity.
         */
    }
}
