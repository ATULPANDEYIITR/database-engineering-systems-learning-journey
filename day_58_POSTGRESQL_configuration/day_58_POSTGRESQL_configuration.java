import java.util.ArrayList;
import java.util.Collections;
import java.util.EnumMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import java.util.Set;

public class PostgreSQLConfigurationManager {

    enum Category {
        MEMORY,
        CONNECTION,
        GENERAL
    }

    enum ApplyMode {
        RELOAD,
        RESTART
    }

    enum ServerState {
        RUNNING,
        RELOAD_PENDING,
        RESTART_PENDING
    }

    record SettingDefinition(
            String name,
            String defaultValue,
            Category category,
            Long minimum,
            Long maximum,
            boolean requiresRestart
    ) {
        SettingDefinition {
            Objects.requireNonNull(name);
            Objects.requireNonNull(defaultValue);
            Objects.requireNonNull(category);
        }
    }

    record ConfigurationChange(
            String setting,
            String value,
            ApplyMode applyMode
    ) {}

    static final class ConfigurationException extends Exception {
        ConfigurationException(String message) {
            super(message);
        }
    }

    interface ConfigurationPolicy {
        void validate(SettingDefinition definition, String value)
                throws ConfigurationException;
    }

    static final class DefaultConfigurationPolicy
            implements ConfigurationPolicy {

        @Override
        public void validate(
                SettingDefinition definition,
                String value
        ) throws ConfigurationException {

            if (value == null || value.isBlank()) {
                throw new ConfigurationException(
                        definition.name() + " cannot be empty"
                );
            }

            if (definition.minimum() == null &&
                    definition.maximum() == null) {
                return;
            }

            long numeric = parseValue(value);

            if (definition.minimum() != null &&
                    numeric < definition.minimum()) {
                throw new ConfigurationException(
                        definition.name() + " is below its minimum"
                );
            }

            if (definition.maximum() != null &&
                    numeric > definition.maximum()) {
                throw new ConfigurationException(
                        definition.name() + " exceeds its maximum"
                );
            }
        }
    }

    static final class ConfigurationService {
        private final Map<String, SettingDefinition> definitions =
                new LinkedHashMap<>();

        private final Map<String, String> persistentValues =
                new LinkedHashMap<>();

        private final Map<String, String> sessionOverrides =
                new LinkedHashMap<>();

        private final ConfigurationPolicy policy;

        private ServerState state = ServerState.RUNNING;

        ConfigurationService(ConfigurationPolicy policy) {
            this.policy = Objects.requireNonNull(policy);
            registerDefinitions();
        }

        private void registerDefinitions() {
            add("max_connections", "100", Category.CONNECTION,
                    10L, 10000L, false);

            add("shared_buffers", "128MB", Category.MEMORY,
                    16L * 1024 * 1024,
                    1024L * 1024 * 1024 * 1024, true);

            add("work_mem", "4MB", Category.MEMORY,
                    64L * 1024,
                    1024L * 1024 * 1024, false);

            add("maintenance_work_mem", "64MB", Category.MEMORY,
                    1024L * 1024,
                    2048L * 1024 * 1024, false);

            add("effective_cache_size", "4GB", Category.MEMORY,
                    128L * 1024 * 1024,
                    4096L * 1024 * 1024 * 1024, false);

            add("statement_timeout", "0", Category.CONNECTION,
                    0L, 24L * 60 * 60 * 1000, false);

            add("idle_in_transaction_session_timeout", "0",
                    Category.CONNECTION,
                    0L, 24L * 60 * 60 * 1000, false);

            add("listen_addresses", "localhost", Category.CONNECTION,
                    null, null, false);

            add("port", "5432", Category.CONNECTION,
                    1L, 65535L, true);
        }

        private void add(
                String name,
                String defaultValue,
                Category category,
                Long minimum,
                Long maximum,
                boolean restart
        ) {
            definitions.put(
                    name,
                    new SettingDefinition(
                            name,
                            defaultValue,
                            category,
                            minimum,
                            maximum,
                            restart
                    )
            );
        }

        ConfigurationChange setPersistent(
                String name,
                String value
        ) throws ConfigurationException {

            SettingDefinition definition = getDefinition(name);
            policy.validate(definition, value);

            persistentValues.put(name, value);

            ApplyMode mode = definition.requiresRestart()
                    ? ApplyMode.RESTART
                    : ApplyMode.RELOAD;

            state = mode == ApplyMode.RESTART
                    ? ServerState.RESTART_PENDING
                    : ServerState.RELOAD_PENDING;

            return new ConfigurationChange(name, value, mode);
        }

        void setSessionOverride(
                String name,
                String value
        ) throws ConfigurationException {

            SettingDefinition definition = getDefinition(name);
            policy.validate(definition, value);
            sessionOverrides.put(name, value);
        }

        String effectiveValue(String name)
                throws ConfigurationException {

            SettingDefinition definition = getDefinition(name);

            return sessionOverrides.getOrDefault(
                    name,
                    persistentValues.getOrDefault(
                            name,
                            definition.defaultValue()
                    )
            );
        }

        void reload() {
            state = ServerState.RUNNING;
        }

        void restart() {
            state = ServerState.RUNNING;
        }

        ServerState state() {
            return state;
        }

        List<String> validateRuntime()
                throws ConfigurationException {

            List<String> warnings = new ArrayList<>();

            long maxConnections =
                    parseValue(effectiveValue("max_connections"));

            long workMem =
                    parseValue(effectiveValue("work_mem"));

            long sharedBuffers =
                    parseValue(effectiveValue("shared_buffers"));

            long estimatedWorkMemory =
                    maxConnections * workMem;

            if (estimatedWorkMemory > sharedBuffers * 4) {
                warnings.add(
                        "Potential memory pressure from max_connections "
                                + "and work_mem."
                );
            }

            if (maxConnections > 2000) {
                warnings.add(
                        "Very high connection count; connection pooling "
                                + "should be considered."
                );
            }

            if ("*".equals(effectiveValue("listen_addresses"))) {
                warnings.add(
                        "Unrestricted network listener requires strict "
                                + "network and authentication controls."
                );
            }

            return warnings;
        }

        Map<String, String> effectiveSnapshot()
                throws ConfigurationException {

            Map<String, String> snapshot = new LinkedHashMap<>();

            for (String name : definitions.keySet()) {
                snapshot.put(name, effectiveValue(name));
            }

            return Collections.unmodifiableMap(snapshot);
        }

        private SettingDefinition getDefinition(String name)
                throws ConfigurationException {

            SettingDefinition definition = definitions.get(name);

            if (definition == null) {
                throw new ConfigurationException(
                        "Unknown PostgreSQL setting: " + name
                );
            }

            return definition;
        }
    }

    static long parseValue(String raw)
            throws ConfigurationException {

        String value = raw.trim().toLowerCase();

        int position = 0;

        while (position < value.length() &&
                Character.isDigit(value.charAt(position))) {
            position++;
        }

        if (position == 0) {
            throw new ConfigurationException(
                    "Invalid numeric value: " + raw
            );
        }

        long number;

        try {
            number = Long.parseLong(value.substring(0, position));
        } catch (NumberFormatException exception) {
            throw new ConfigurationException(
                    "Numeric value is outside supported range: " + raw
            );
        }

        String unit = value.substring(position);

        return switch (unit) {
            case "" -> number;
            case "kb" -> Math.multiplyExact(number, 1024L);
            case "mb" -> Math.multiplyExact(
                    number, 1024L * 1024L
            );
            case "gb" -> Math.multiplyExact(
                    number, 1024L * 1024L * 1024L
            );
            default -> throw new ConfigurationException(
                    "Unsupported unit: " + unit
            );
        };
    }

    public static void main(String[] args) {
        ConfigurationService service =
                new ConfigurationService(
                        new DefaultConfigurationPolicy()
                );

        try {
            List<ConfigurationChange> changes = List.of(
                    service.setPersistent(
                            "shared_buffers", "512MB"
                    ),
                    service.setPersistent(
                            "work_mem", "8MB"
                    ),
                    service.setPersistent(
                            "maintenance_work_mem", "128MB"
                    ),
                    service.setPersistent(
                            "effective_cache_size", "4GB"
                    ),
                    service.setPersistent(
                            "max_connections", "200"
                    ),
                    service.setPersistent(
                            "statement_timeout", "30000"
                    ),
                    service.setPersistent(
                            "idle_in_transaction_session_timeout",
                            "60000"
                    ),
                    service.setPersistent(
                            "listen_addresses", "localhost"
                    ),
                    service.setPersistent(
                            "port", "5432"
                    )
            );

            for (ConfigurationChange change : changes) {
                System.out.printf(
                        "%s=%s -> %s%n",
                        change.setting(),
                        change.value(),
                        change.applyMode()
                );
            }

            service.setSessionOverride("work_mem", "16MB");

            System.out.println("\nRuntime validation:");

            List<String> warnings = service.validateRuntime();

            if (warnings.isEmpty()) {
                System.out.println("No warnings.");
            } else {
                warnings.forEach(warning ->
                        System.out.println("- " + warning)
                );
            }

            System.out.println("\nEffective configuration:");

            service.effectiveSnapshot().forEach(
                    (name, value) ->
                            System.out.printf(
                                    "%-45s %s%n",
                                    name,
                                    value
                            )
            );

            System.out.println(
                    "\nState before reload: " + service.state()
            );

            service.reload();

            System.out.println(
                    "State after reload: " + service.state()
            );

            service.restart();

            System.out.println(
                    "State after restart: " + service.state()
            );

            try {
                service.setPersistent(
                        "max_connections",
                        "5"
                );
            } catch (ConfigurationException expected) {
                System.out.println(
                        "\nExpected validation failure: "
                                + expected.getMessage()
                );
            }

            try {
                service.setPersistent(
                        "not_a_postgresql_setting",
                        "10"
                );
            } catch (ConfigurationException expected) {
                System.out.println(
                        "Expected unknown-setting failure: "
                                + expected.getMessage()
                );
            }

        } catch (ConfigurationException exception) {
            System.err.println(
                    "Configuration failure: "
                            + exception.getMessage()
            );
            System.exit(1);
        }
    }
}
