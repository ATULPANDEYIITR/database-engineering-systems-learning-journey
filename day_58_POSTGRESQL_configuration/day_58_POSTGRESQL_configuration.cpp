#include <algorithm>
#include <cctype>
#include <exception>
#include <iomanip>
#include <iostream>
#include <map>
#include <optional>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

enum class Category {
    Memory,
    Connection,
    General
};

enum class ApplyMode {
    Reload,
    Restart
};

struct SettingDefinition {
    std::string name;
    std::string defaultValue;
    Category category;
    std::optional<long long> minimum;
    std::optional<long long> maximum;
    bool requiresRestart;
};

struct SettingState {
    std::string value;
    bool explicitlyConfigured{false};
    bool pendingRestart{false};
};

class ConfigurationError : public std::runtime_error {
public:
    explicit ConfigurationError(const std::string& message)
        : std::runtime_error(message) {}
};

long long parseValue(const std::string& raw) {
    std::string value;
    for (char c : raw) {
        if (!std::isspace(static_cast<unsigned char>(c))) {
            value += static_cast<char>(
                std::tolower(static_cast<unsigned char>(c))
            );
        }
    }

    std::size_t position = 0;
    while (position < value.size() &&
           std::isdigit(static_cast<unsigned char>(value[position]))) {
        ++position;
    }

    if (position == 0) {
        throw ConfigurationError("Invalid numeric value: " + raw);
    }

    long long number = std::stoll(value.substr(0, position));
    std::string unit = value.substr(position);

    if (unit.empty()) return number;
    if (unit == "kb") return number * 1024LL;
    if (unit == "mb") return number * 1024LL * 1024LL;
    if (unit == "gb") return number * 1024LL * 1024LL * 1024LL;

    throw ConfigurationError("Unsupported unit in value: " + raw);
}

class PostgreSQLGovernanceEngine {
private:
    std::map<std::string, SettingDefinition> definitions;
    std::map<std::string, SettingState> fileSettings;
    std::map<std::string, std::string> sessionOverrides;
    bool restarted{true};

    void initializeDefinitions() {
        definitions.emplace("max_connections",
            SettingDefinition{"max_connections", "100", Category::Connection,
                              10, 10000, false});

        definitions.emplace("shared_buffers",
            SettingDefinition{"shared_buffers", "128MB", Category::Memory,
                              16LL * 1024 * 1024,
                              1024LL * 1024 * 1024 * 1024, true});

        definitions.emplace("work_mem",
            SettingDefinition{"work_mem", "4MB", Category::Memory,
                              64LL * 1024,
                              1024LL * 1024 * 1024, false});

        definitions.emplace("maintenance_work_mem",
            SettingDefinition{"maintenance_work_mem", "64MB", Category::Memory,
                              1024LL * 1024,
                              2048LL * 1024 * 1024, false});

        definitions.emplace("effective_cache_size",
            SettingDefinition{"effective_cache_size", "4GB", Category::Memory,
                              128LL * 1024 * 1024,
                              4096LL * 1024 * 1024 * 1024, false});

        definitions.emplace("statement_timeout",
            SettingDefinition{"statement_timeout", "0", Category::Connection,
                              0, 24LL * 60 * 60 * 1000, false});

        definitions.emplace("idle_in_transaction_session_timeout",
            SettingDefinition{"idle_in_transaction_session_timeout", "0",
                              Category::Connection,
                              0, 24LL * 60 * 60 * 1000, false});

        definitions.emplace("listen_addresses",
            SettingDefinition{"listen_addresses", "localhost",
                              Category::Connection, std::nullopt,
                              std::nullopt, false});

        definitions.emplace("port",
            SettingDefinition{"port", "5432", Category::Connection,
                              1, 65535, true});
    }

    void validate(const SettingDefinition& definition,
                  const std::string& value) const {
        if (!definition.minimum && !definition.maximum) {
            if (value.empty()) {
                throw ConfigurationError(
                    definition.name + " cannot be empty"
                );
            }
            return;
        }

        long long parsed = parseValue(value);

        if (definition.minimum && parsed < *definition.minimum) {
            throw ConfigurationError(
                definition.name + " is below its minimum"
            );
        }

        if (definition.maximum && parsed > *definition.maximum) {
            throw ConfigurationError(
                definition.name + " exceeds its maximum"
            );
        }
    }

public:
    PostgreSQLGovernanceEngine() {
        initializeDefinitions();
    }

    ApplyMode setPersistent(const std::string& name,
                            const std::string& value) {
        auto iterator = definitions.find(name);
        if (iterator == definitions.end()) {
            throw ConfigurationError("Unknown setting: " + name);
        }

        validate(iterator->second, value);

        fileSettings[name] = SettingState{
            value,
            true,
            iterator->second.requiresRestart
        };

        restarted = false;

        return iterator->second.requiresRestart
            ? ApplyMode::Restart
            : ApplyMode::Reload;
    }

    void setSession(const std::string& name, const std::string& value) {
        auto iterator = definitions.find(name);
        if (iterator == definitions.end()) {
            throw ConfigurationError("Unknown setting: " + name);
        }

        validate(iterator->second, value);
        sessionOverrides[name] = value;
    }

    std::string effective(const std::string& name) const {
        auto definition = definitions.find(name);
        if (definition == definitions.end()) {
            throw ConfigurationError("Unknown setting: " + name);
        }

        auto session = sessionOverrides.find(name);
        if (session != sessionOverrides.end()) {
            return session->second;
        }

        auto file = fileSettings.find(name);
        if (file != fileSettings.end()) {
            return file->second.value;
        }

        return definition->second.defaultValue;
    }

    void reload() {
        // Reloadable values become effective immediately. Restart-required
        // values remain pending until restart.
        std::cout << "Configuration reload completed.\n";
    }

    void restart() {
        for (auto& [name, state] : fileSettings) {
            state.pendingRestart = false;
        }

        restarted = true;
        std::cout << "Server restart completed.\n";
    }

    std::vector<std::string> validateRuntime() const {
        std::vector<std::string> warnings;

        const long long maxConnections =
            parseValue(effective("max_connections"));

        const long long workMem =
            parseValue(effective("work_mem"));

        const long long sharedBuffers =
            parseValue(effective("shared_buffers"));

        // work_mem is not a global allocation. Multiple query nodes and
        // sessions can consume it, so this is an intentionally conservative
        // risk indicator rather than an exact memory calculation.
        const long long estimated =
            maxConnections * workMem;

        if (estimated > sharedBuffers * 4) {
            warnings.push_back(
                "Potential memory pressure from max_connections and work_mem."
            );
        }

        if (maxConnections > 2000) {
            warnings.push_back(
                "Very high connection count; use connection pooling."
            );
        }

        if (effective("listen_addresses") == "*") {
            warnings.push_back(
                "Server listens on all interfaces; network and pg_hba.conf "
                "controls must be tightly restricted."
            );
        }

        return warnings;
    }

    void printReport() const {
        std::cout << "\nConfiguration report\n";
        std::cout << std::left
                  << std::setw(40) << "Setting"
                  << std::setw(18) << "Effective"
                  << std::setw(12) << "Restart"
                  << "State\n";
        std::cout << std::string(85, '-') << '\n';

        for (const auto& [name, definition] : definitions) {
            std::string state = "default";

            auto file = fileSettings.find(name);
            if (file != fileSettings.end()) {
                state = file->second.pendingRestart
                    ? "pending restart"
                    : "configured";
            }

            if (sessionOverrides.find(name) != sessionOverrides.end()) {
                state = "session override";
            }

            std::cout << std::left
                      << std::setw(40) << name
                      << std::setw(18) << effective(name)
                      << std::setw(12)
                      << (definition.requiresRestart ? "yes" : "no")
                      << state << '\n';
        }
    }
};

int main() {
    try {
        PostgreSQLGovernanceEngine engine;

        const std::vector<std::pair<std::string, std::string>> settings = {
            {"shared_buffers", "512MB"},
            {"work_mem", "8MB"},
            {"maintenance_work_mem", "128MB"},
            {"effective_cache_size", "4GB"},
            {"max_connections", "200"},
            {"statement_timeout", "30000"},
            {"idle_in_transaction_session_timeout", "60000"},
            {"listen_addresses", "localhost"},
            {"port", "5432"}
        };

        for (const auto& [name, value] : settings) {
            ApplyMode mode = engine.setPersistent(name, value);

            std::cout << name << "=" << value
                      << " -> "
                      << (mode == ApplyMode::Restart
                          ? "restart required"
                          : "reload sufficient")
                      << '\n';
        }

        engine.setSession("work_mem", "16MB");

        auto warnings = engine.validateRuntime();

        std::cout << "\nRuntime validation\n";
        if (warnings.empty()) {
            std::cout << "No configuration warnings.\n";
        } else {
            for (const auto& warning : warnings) {
                std::cout << "- " << warning << '\n';
            }
        }

        engine.printReport();

        engine.reload();
        engine.restart();

        std::cout << "\nAfter restart:\n";
        engine.printReport();

        // Explicitly test a failure condition rather than silently accepting
        // an invalid production setting.
        try {
            engine.setPersistent("max_connections", "2");
        } catch (const ConfigurationError& error) {
            std::cout << "\nExpected validation failure: "
                      << error.what() << '\n';
        }

        try {
            engine.setPersistent("unknown_setting", "10");
        } catch (const ConfigurationError& error) {
            std::cout << "Expected unknown-setting failure: "
                      << error.what() << '\n';
        }

        return 0;
    } catch (const std::exception& error) {
        std::cerr << "Fatal configuration error: "
                  << error.what() << '\n';
        return 1;
    }
}
