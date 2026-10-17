#include <algorithm>
#include <cmath>
#include <iomanip>
#include <iostream>
#include <optional>
#include <regex>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

/*
 * C++17 case study: an industrial telemetry gateway preparing typed records
 * for PostgreSQL storage.
 *
 * This program models typed scalar values, exact-decimal input validation,
 * UUID representation, JSON document validation, and text-array constraints.
 * It intentionally does not pretend to implement a PostgreSQL wire protocol.
 */

class ValidationError : public std::runtime_error {
public:
    using std::runtime_error::runtime_error;
};

struct NumericDecimal {
    std::string value;

    static NumericDecimal parse(const std::string& input,
                                int precision,
                                int scale) {
        if (precision <= 0 || scale < 0 || scale > precision) {
            throw ValidationError("Invalid NUMERIC precision or scale");
        }

        static const std::regex decimalPattern(R"(^-?\d+(\.\d+)?$)");

        if (!std::regex_match(input, decimalPattern)) {
            throw ValidationError("Invalid decimal representation");
        }

        std::string unsignedValue =
            (!input.empty() && input.front() == '-') ? input.substr(1) : input;

        const auto dot = unsignedValue.find('.');
        std::string integerPart = unsignedValue.substr(0, dot);
        std::string fraction =
            dot == std::string::npos ? "" : unsignedValue.substr(dot + 1);

        while (integerPart.size() > 1 && integerPart.front() == '0') {
            integerPart.erase(integerPart.begin());
        }

        if (static_cast<int>(fraction.size()) > scale) {
            throw ValidationError("Too many fractional digits");
        }

        if (static_cast<int>(integerPart.size()) > precision - scale) {
            throw ValidationError("Integer part exceeds NUMERIC precision");
        }

        return {input};
    }
};

struct Uuid {
    std::string value;

    static Uuid parse(const std::string& input) {
        static const std::regex pattern(
            R"(^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89aAbB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$)"
        );

        if (!std::regex_match(input, pattern)) {
            throw ValidationError("Invalid UUID");
        }

        std::string normalized = input;
        std::transform(normalized.begin(), normalized.end(),
                       normalized.begin(),
                       [](unsigned char c) {
                           return static_cast<char>(std::tolower(c));
                       });

        return {normalized};
    }
};

struct TelemetryReading {
    Uuid equipmentId;
    std::string serialNumber;
    NumericDecimal pressureBar;
    std::optional<bool> operational;
    std::vector<std::string> tags;
    std::string jsonMetadata;

    void validate() const {
        if (serialNumber.empty() || serialNumber.size() > 40) {
            throw ValidationError("Serial number must contain 1 to 40 bytes");
        }

        if (pressureBar.value.empty()) {
            throw ValidationError("Pressure is required");
        }

        std::set<std::string> uniqueTags(tags.begin(), tags.end());

        if (uniqueTags.size() != tags.size()) {
            throw ValidationError("Duplicate tags are not allowed");
        }

        for (const auto& tag : tags) {
            if (tag.empty()) {
                throw ValidationError("Empty tags are not allowed");
            }
        }

        /*
         * This is a structural safeguard, not a complete JSON parser.
         * Production ingestion should use a real JSON parser or let PostgreSQL
         * validate a bound value cast to jsonb.
         */
        if (jsonMetadata.empty() ||
            jsonMetadata.front() != '{' ||
            jsonMetadata.back() != '}') {
            throw ValidationError("Metadata must resemble a JSON object");
        }
    }
};

class TelemetryGateway {
private:
    std::vector<TelemetryReading> accepted_;
    std::vector<std::string> rejected_;

public:
    void ingest(TelemetryReading reading) {
        try {
            reading.validate();
            accepted_.push_back(std::move(reading));
        } catch (const std::exception& error) {
            rejected_.push_back(error.what());
        }
    }

    void printBatch() const {
        std::cout << "\nAccepted telemetry records: "
                  << accepted_.size() << '\n';

        for (const auto& reading : accepted_) {
            std::cout << "Equipment UUID: " << reading.equipmentId.value
                      << "\nSerial: " << reading.serialNumber
                      << "\nPressure NUMERIC: " << reading.pressureBar.value
                      << "\nOperational: ";

            if (reading.operational.has_value()) {
                std::cout << (reading.operational.value() ? "true" : "false");
            } else {
                std::cout << "NULL";
            }

            std::cout << "\nText array: {";

            for (std::size_t i = 0; i < reading.tags.size(); ++i) {
                if (i != 0) {
                    std::cout << ", ";
                }
                std::cout << reading.tags[i];
            }

            std::cout << "}\nJSONB candidate: "
                      << reading.jsonMetadata << "\n\n";
        }

        std::cout << "Rejected records: " << rejected_.size() << '\n';

        for (const auto& reason : rejected_) {
            std::cout << "Rejected: " << reason << '\n';
        }
    }
};

int main() {
    try {
        TelemetryGateway gateway;

        const Uuid equipmentId = Uuid::parse(
            "550e8400-e29b-41d4-a716-446655440000"
        );

        gateway.ingest({
            equipmentId,
            "PS-2026-0042",
            NumericDecimal::parse("7.42", 10, 2),
            true,
            {"plant-a", "critical"},
            R"({"protocol":"modbus","calibration_valid":true})"
        });

        // A missing status is different from an explicitly false status.
        gateway.ingest({
            equipmentId,
            "PS-2026-0043",
            NumericDecimal::parse("0.00", 10, 2),
            std::nullopt,
            {"plant-b"},
            R"({"protocol":"mqtt","calibration_valid":false})"
        });

        try {
            gateway.ingest({
                equipmentId,
                "PS-2026-0044",
                NumericDecimal::parse("123456789.00", 10, 2),
                false,
                {"plant-c"},
                R"({"protocol":"modbus"})"
            });
        } catch (const ValidationError&) {
            // Invalid numeric input is caught below by the gateway only when
            // construction succeeds. This exception demonstrates input failure.
            throw;
        }
    } catch (const ValidationError& error) {
        std::cout << "Input construction failed: " << error.what() << '\n';
    }

    TelemetryGateway gateway;

    gateway.ingest({
        Uuid::parse("550e8400-e29b-41d4-a716-446655440000"),
        "PS-2026-0042",
        NumericDecimal::parse("7.42", 10, 2),
        true,
        {"plant-a", "critical"},
        R"({"protocol":"modbus","calibration_valid":true})"
    });

    gateway.ingest({
        Uuid::parse("550e8400-e29b-41d4-a716-446655440000"),
        "PS-2026-0043",
        NumericDecimal::parse("0.00", 10, 2),
        std::nullopt,
        {"plant-b"},
        R"({"protocol":"mqtt"})"
    });

    gateway.ingest({
        Uuid::parse("550e8400-e29b-41d4-a716-446655440000"),
        "PS-2026-0045",
        NumericDecimal::parse("3.15", 10, 2),
        false,
        {"plant-a", "plant-a"},
        R"({"protocol":"modbus"})"
    });

    gateway.printBatch();

    /*
     * A production gateway should bind typed values through libpq or another
     * PostgreSQL client library, rather than building SQL strings.
     *
     * Decimal strings preserve exact numeric input. std::optional<bool>
     * represents the three application states true, false, and absent.
     * PostgreSQL remains responsible for final type and constraint checks.
     */
    return 0;
}
