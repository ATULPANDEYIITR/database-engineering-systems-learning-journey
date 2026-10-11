#include <algorithm>
#include <cstdint>
#include <iomanip>
#include <iostream>
#include <limits>
#include <map>
#include <optional>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

/*
 * Repository-independent case study: a logistics company must reconcile
 * customer identifiers arriving from multiple acquired business systems.
 *
 * The same design principles apply to surrogate and natural keys:
 * internal identity remains stable while external business identifiers
 * are validated and mapped to the internal entity.
 *
 * Compile:
 *   g++ -std=c++17 -Wall -Wextra -pedantic keys_design_lab.cpp -o keys_lab
 */

class DomainError : public std::runtime_error {
public:
    explicit DomainError(const std::string& message)
        : std::runtime_error(message) {}
};

struct SourceIdentity {
    std::string system;
    std::string record;

    bool operator==(const SourceIdentity& other) const {
        return system == other.system && record == other.record;
    }

    bool operator<(const SourceIdentity& other) const {
        return std::tie(system, record) <
               std::tie(other.system, other.record);
    }
};

struct Customer {
    std::uint64_t id;
    std::string legal_name;
    std::string country_code;
    std::string tax_identifier;
};

struct Shipment {
    std::uint64_t id;
    std::uint64_t customer_id;
    SourceIdentity source;
    std::int64_t declared_value_minor_units;
};

static std::string trim(const std::string& value) {
    const auto first = value.find_first_not_of(" \t\r\n");
    if (first == std::string::npos) {
        return "";
    }
    const auto last = value.find_last_not_of(" \t\r\n");
    return value.substr(first, last - first + 1);
}

static std::string normalize_country(const std::string& country) {
    std::string result = trim(country);
    if (result.size() != 2) {
        throw DomainError("Country code must contain two characters.");
    }
    for (char& ch : result) {
        if (ch >= 'a' && ch <= 'z') {
            ch = static_cast<char>(ch - 'a' + 'A');
        }
        if (ch < 'A' || ch > 'Z') {
            throw DomainError("Country code must contain ASCII letters.");
        }
    }
    return result;
}

static std::string normalize_tax_id(const std::string& identifier) {
    const std::string result = trim(identifier);
    if (result.empty()) {
        throw DomainError("Tax identifier cannot be empty.");
    }
    return result;
}

static SourceIdentity normalize_source(SourceIdentity source) {
    source.system = trim(source.system);
    source.record = trim(source.record);
    if (source.system.empty() || source.record.empty()) {
        throw DomainError("Source system and record ID are required.");
    }

    // System identifiers are case-insensitive by this application's contract.
    // Record IDs remain case-sensitive because some upstream systems require it.
    std::transform(
        source.system.begin(),
        source.system.end(),
        source.system.begin(),
        [](unsigned char ch) {
            return static_cast<char>(
                ch >= 'A' && ch <= 'Z' ? ch - 'A' + 'a' : ch
            );
        }
    );
    return source;
}

class CustomerMasterData {
private:
    std::uint64_t next_customer_id_ = 1;
    std::uint64_t next_shipment_id_ = 1;

    std::unordered_map<std::uint64_t, Customer> customers_;
    std::map<std::pair<std::string, std::string>, std::uint64_t> tax_index_;
    std::map<SourceIdentity, std::uint64_t> source_index_;
    std::unordered_map<std::uint64_t, Shipment> shipments_;

public:
    std::uint64_t register_customer(
        const std::string& legal_name,
        const std::string& country,
        const std::string& tax_identifier
    ) {
        const std::string name = trim(legal_name);
        const std::string normalized_country = normalize_country(country);
        const std::string normalized_tax = normalize_tax_id(tax_identifier);

        if (name.empty()) {
            throw DomainError("Legal name cannot be empty.");
        }

        const auto natural_key =
            std::make_pair(normalized_country, normalized_tax);

        if (tax_index_.find(natural_key) != tax_index_.end()) {
            throw DomainError(
                "A customer with this country and tax identifier already exists."
            );
        }

        const std::uint64_t id = next_customer_id_++;
        Customer customer{id, name, normalized_country, normalized_tax};

        customers_.emplace(id, customer);
        tax_index_.emplace(natural_key, id);
        return id;
    }

    std::uint64_t find_by_tax_identity(
        const std::string& country,
        const std::string& tax_identifier
    ) const {
        const auto key = std::make_pair(
            normalize_country(country),
            normalize_tax_id(tax_identifier)
        );

        const auto found = tax_index_.find(key);
        if (found == tax_index_.end()) {
            throw DomainError("Customer natural key was not found.");
        }
        return found->second;
    }

    void correct_tax_identity(
        std::uint64_t customer_id,
        const std::string& new_country,
        const std::string& new_tax_identifier
    ) {
        auto customer_it = customers_.find(customer_id);
        if (customer_it == customers_.end()) {
            throw DomainError("Cannot correct an unknown customer.");
        }

        const std::string country = normalize_country(new_country);
        const std::string tax = normalize_tax_id(new_tax_identifier);
        const auto new_key = std::make_pair(country, tax);
        const auto owner = tax_index_.find(new_key);

        if (owner != tax_index_.end() && owner->second != customer_id) {
            throw DomainError("The replacement natural key is already assigned.");
        }

        // Validate before modifying either index so a rejected correction
        // cannot leave the registry half-updated.
        const auto old_key = std::make_pair(
            customer_it->second.country_code,
            customer_it->second.tax_identifier
        );

        tax_index_.erase(old_key);
        customer_it->second.country_code = country;
        customer_it->second.tax_identifier = tax;
        tax_index_[new_key] = customer_id;
    }

    std::uint64_t ingest_shipment(
        std::uint64_t customer_id,
        SourceIdentity source,
        std::int64_t declared_value_minor_units
    ) {
        if (customers_.find(customer_id) == customers_.end()) {
            throw DomainError("Shipment references an unknown customer.");
        }
        if (declared_value_minor_units < 0) {
            throw DomainError("Declared value cannot be negative.");
        }

        source = normalize_source(std::move(source));
        const auto existing = source_index_.find(source);

        if (existing != source_index_.end()) {
            const Shipment& shipment = shipments_.at(existing->second);
            if (shipment.customer_id != customer_id ||
                shipment.declared_value_minor_units != declared_value_minor_units) {
                throw DomainError(
                    "Source record was previously ingested with conflicting data."
                );
            }
            return shipment.id;
        }

        const std::uint64_t shipment_id = next_shipment_id_++;
        Shipment shipment{
            shipment_id,
            customer_id,
            source,
            declared_value_minor_units
        };

        shipments_.emplace(shipment_id, shipment);
        source_index_.emplace(source, shipment_id);
        return shipment_id;
    }

    const Customer& customer(std::uint64_t id) const {
        const auto found = customers_.find(id);
        if (found == customers_.end()) {
            throw DomainError("Customer does not exist.");
        }
        return found->second;
    }

    std::vector<Shipment> shipments_for(std::uint64_t customer_id) const {
        std::vector<Shipment> result;
        for (const auto& [id, shipment] : shipments_) {
            (void)id;
            if (shipment.customer_id == customer_id) {
                result.push_back(shipment);
            }
        }
        return result;
    }

    std::size_t customer_count() const {
        return customers_.size();
    }

    std::size_t shipment_count() const {
        return shipments_.size();
    }
};

static std::string format_minor_units(std::int64_t amount) {
    std::ostringstream output;
    output << amount / 100 << '.'
           << std::setw(2) << std::setfill('0') << amount % 100;
    return output.str();
}

int main() {
    try {
        std::cout << "=== Logistics customer identity registry ===\n";

        CustomerMasterData registry;

        const auto india_id = registry.register_customer(
            "Eastern Freight Pvt Ltd",
            "in",
            "GST-29-EXAMPLE-001"
        );

        const auto us_id = registry.register_customer(
            "Eastern Freight LLC",
            "US",
            "EIN-12-3456789"
        );

        std::cout << "Indian customer surrogate ID: " << india_id << '\n';
        std::cout << "US customer surrogate ID: " << us_id << '\n';

        const auto shipment_id = registry.ingest_shipment(
            india_id,
            {"ERP-A", "MANIFEST-8821"},
            1542500
        );

        const auto retry_id = registry.ingest_shipment(
            india_id,
            {"erp-a", "MANIFEST-8821"},
            1542500
        );

        std::cout << "Shipment ID: " << shipment_id << '\n';
        std::cout << "Idempotent retry reused ID: "
                  << std::boolalpha << (shipment_id == retry_id) << '\n';

        try {
            registry.register_customer(
                "Duplicate Legal Entity",
                "IN",
                "GST-29-EXAMPLE-001"
            );
        } catch (const DomainError& error) {
            std::cout << "Natural-key collision rejected: "
                      << error.what() << '\n';
        }

        try {
            registry.ingest_shipment(
                india_id,
                {"ERP-A", "MANIFEST-8821"},
                100
            );
        } catch (const DomainError& error) {
            std::cout << "Conflicting source event rejected: "
                      << error.what() << '\n';
        }

        registry.correct_tax_identity(
            india_id,
            "IN",
            "GST-29-EXAMPLE-009"
        );

        const auto resolved_id = registry.find_by_tax_identity(
            "IN",
            "GST-29-EXAMPLE-009"
        );

        std::cout << "Corrected tax identifier still maps to surrogate ID: "
                  << (resolved_id == india_id) << '\n';

        for (const Shipment& shipment : registry.shipments_for(india_id)) {
            std::cout << "Shipment " << shipment.id
                      << " belongs to customer " << shipment.customer_id
                      << ", source " << shipment.source.system << ':'
                      << shipment.source.record
                      << ", value " << format_minor_units(
                             shipment.declared_value_minor_units
                         )
                      << '\n';
        }

        try {
            registry.ingest_shipment(
                std::numeric_limits<std::uint64_t>::max(),
                {"ERP-B", "MANIFEST-9999"},
                2500
            );
        } catch (const DomainError& error) {
            std::cout << "Invalid foreign reference rejected: "
                      << error.what() << '\n';
        }

        std::cout << "Customers: " << registry.customer_count()
                  << ", shipments: " << registry.shipment_count() << '\n';

        std::cout << "\nComplexity considerations:\n"
                  << "- Customer lookup by surrogate ID: expected O(1).\n"
                  << "- Natural-key lookup: O(log n) using ordered map.\n"
                  << "- Shipment lookup by customer: O(m) in this case study; "
                     "a production secondary index reduces scanning.\n"
                  << "- Hash collisions and natural-key uniqueness still require "
                     "explicit validation and authoritative constraints.\n";
    } catch (const std::exception& error) {
        std::cerr << "Fatal error: " << error.what() << '\n';
        return 1;
    }

    return 0;
}
