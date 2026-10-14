#include <algorithm>
#include <chrono>
#include <cstdint>
#include <iomanip>
#include <iostream>
#include <map>
#include <optional>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

/*
 * Repository governance case study expressed as database lifecycle patterns:
 * an industrial equipment registry with audit history, logical deletion,
 * explicit state transitions, and optimistic concurrency control.
 *
 * This C++17 program models transaction boundaries in memory. A production
 * database must persist entity changes and audit events in one transaction.
 */

using Clock = std::chrono::system_clock;

std::string timestampNow() {
    const auto now = Clock::now();
    const auto time = Clock::to_time_t(now);
    std::tm utc{};
#ifdef _WIN32
    gmtime_s(&utc, &time);
#else
    gmtime_r(&time, &utc);
#endif
    std::ostringstream out;
    out << std::put_time(&utc, "%Y-%m-%dT%H:%M:%SZ");
    return out.str();
}

enum class Status {
    Requested,
    Approved,
    InService,
    Maintenance,
    Retired
};

std::string toString(Status status) {
    switch (status) {
        case Status::Requested: return "requested";
        case Status::Approved: return "approved";
        case Status::InService: return "in_service";
        case Status::Maintenance: return "maintenance";
        case Status::Retired: return "retired";
    }
    throw std::logic_error("Unknown status value.");
}

const std::map<Status, std::set<Status>> transitions{
    {Status::Requested, {Status::Approved}},
    {Status::Approved, {Status::InService, Status::Retired}},
    {Status::InService, {Status::Maintenance, Status::Retired}},
    {Status::Maintenance, {Status::InService, Status::Retired}},
    {Status::Retired, {}}
};

class DomainError : public std::runtime_error {
public:
    using std::runtime_error::runtime_error;
};

class ValidationError : public DomainError {
public:
    using DomainError::DomainError;
};

class NotFoundError : public DomainError {
public:
    using DomainError::DomainError;
};

class InvalidTransitionError : public DomainError {
public:
    using DomainError::DomainError;
};

class ConcurrencyError : public DomainError {
public:
    using DomainError::DomainError;
};

struct Equipment {
    std::string id;
    std::string assetTag;
    std::string name;
    Status status{Status::Requested};
    bool deleted{false};
    std::optional<std::string> deletedAt;
    std::optional<std::string> deletedBy;
    std::string createdAt;
    std::string createdBy;
    std::string updatedAt;
    std::string updatedBy;
    std::uint64_t version{1};
};

struct AuditEvent {
    std::uint64_t sequence;
    std::string entityId;
    std::string action;
    std::string actor;
    std::string occurredAt;
    std::string oldValue;
    std::string newValue;
    std::string reason;
    std::string correlationId;
};

struct MutationResult {
    Equipment equipment;
    std::uint64_t auditSequence;
};

class EquipmentRegistry {
private:
    std::map<std::string, Equipment> records;
    std::map<std::string, std::string> tagIndex;
    std::vector<AuditEvent> audit;
    std::uint64_t nextAuditSequence{1};

    static void requireText(const std::string& value, const std::string& field) {
        if (value.find_first_not_of(" \t\r\n") == std::string::npos) {
            throw ValidationError(field + " cannot be empty.");
        }
    }

    Equipment& requireRecord(const std::string& id, bool includeDeleted) {
        auto it = records.find(id);
        if (it == records.end() || (it->second.deleted && !includeDeleted)) {
            throw NotFoundError("Equipment is not visible.");
        }
        return it->second;
    }

    static void requireVersion(const Equipment& item,
                               std::uint64_t expectedVersion) {
        if (item.version != expectedVersion) {
            throw ConcurrencyError(
                "Expected version " + std::to_string(expectedVersion) +
                ", current version " + std::to_string(item.version)
            );
        }
    }

    std::uint64_t appendEvent(const Equipment& item,
                              const std::string& action,
                              const std::string& actor,
                              const std::string& oldValue,
                              const std::string& newValue,
                              const std::string& reason,
                              const std::string& correlationId) {
        const auto sequence = nextAuditSequence++;
        audit.push_back({
            sequence, item.id, action, actor, timestampNow(),
            oldValue, newValue, reason, correlationId
        });
        return sequence;
    }

    MutationResult finishMutation(Equipment& item,
                                  const std::string& actor,
                                  const std::string& action,
                                  const std::string& oldValue,
                                  const std::string& reason,
                                  const std::string& correlationId) {
        ++item.version;
        item.updatedAt = timestampNow();
        item.updatedBy = actor;

        const auto sequence = appendEvent(
            item, action, actor, oldValue, toString(item.status),
            reason, correlationId
        );
        return {item, sequence};
    }

public:
    MutationResult create(const std::string& id,
                          const std::string& assetTag,
                          const std::string& name,
                          const std::string& actor) {
        requireText(id, "Identifier");
        requireText(assetTag, "Asset tag");
        requireText(name, "Name");
        requireText(actor, "Actor");

        if (records.count(id)) {
            throw ValidationError("Equipment identifier already exists.");
        }
        if (tagIndex.count(assetTag)) {
            throw ValidationError("Asset tag already exists.");
        }

        const auto now = timestampNow();
        Equipment item{
            id, assetTag, name, Status::Requested, false,
            std::nullopt, std::nullopt,
            now, actor, now, actor, 1
        };

        // In-memory insertion is followed by an audit event. A durable
        // implementation should wrap both writes in a database transaction.
        records.emplace(id, item);
        tagIndex.emplace(assetTag, id);

        const auto sequence = appendEvent(
            item, "created", actor, "", toString(item.status),
            "Initial equipment registration", "create-" + id
        );
        return {item, sequence};
    }

    MutationResult changeStatus(const std::string& id,
                                Status target,
                                std::uint64_t expectedVersion,
                                const std::string& actor,
                                const std::string& reason) {
        requireText(actor, "Actor");
        requireText(reason, "Reason");
        Equipment& item = requireRecord(id, false);
        requireVersion(item, expectedVersion);

        const auto& allowed = transitions.at(item.status);
        if (!allowed.count(target)) {
            throw InvalidTransitionError(
                "Transition " + toString(item.status) + " -> " +
                toString(target) + " is not permitted."
            );
        }

        const auto oldStatus = toString(item.status);
        item.status = target;
        return finishMutation(
            item, actor, "status_changed", oldStatus, reason,
            "status-" + id + "-" + std::to_string(item.version)
        );
    }

    MutationResult softDelete(const std::string& id,
                              std::uint64_t expectedVersion,
                              const std::string& actor,
                              const std::string& reason) {
        requireText(actor, "Actor");
        requireText(reason, "Reason");
        Equipment& item = requireRecord(id, false);
        requireVersion(item, expectedVersion);

        item.deleted = true;
        item.deletedAt = timestampNow();
        item.deletedBy = actor;
        return finishMutation(
            item, actor, "soft_deleted", "active", "deleted: " + reason,
            "delete-" + id + "-" + std::to_string(item.version)
        );
    }

    MutationResult restore(const std::string& id,
                           std::uint64_t expectedVersion,
                           const std::string& actor,
                           const std::string& reason) {
        requireText(actor, "Actor");
        requireText(reason, "Reason");
        Equipment& item = requireRecord(id, true);
        requireVersion(item, expectedVersion);

        if (!item.deleted) {
            throw InvalidTransitionError("Equipment is already active.");
        }

        item.deleted = false;
        item.deletedAt.reset();
        item.deletedBy.reset();
        return finishMutation(
            item, actor, "restored", "deleted", "active: " + reason,
            "restore-" + id + "-" + std::to_string(item.version)
        );
    }

    std::vector<Equipment> activeEquipment() const {
        std::vector<Equipment> result;
        for (const auto& [id, item] : records) {
            if (!item.deleted) {
                result.push_back(item);
            }
        }
        return result;
    }

    std::vector<AuditEvent> history(const std::string& id) const {
        if (!records.count(id)) {
            throw NotFoundError("Equipment is not known.");
        }
        std::vector<AuditEvent> result;
        for (const auto& event : audit) {
            if (event.entityId == id) {
                result.push_back(event);
            }
        }
        return result;
    }

    bool auditCoverageValid() const {
        for (const auto& [id, item] : records) {
            const auto events = history(id);
            if (events.empty() || events.front().action != "created") {
                return false;
            }
            for (std::size_t index = 1; index < events.size(); ++index) {
                if (events[index].sequence <= events[index - 1].sequence) {
                    return false;
                }
            }
        }
        return true;
    }

    void printHistory(const std::string& id) const {
        for (const auto& event : history(id)) {
            std::cout << "#" << event.sequence << " "
                      << event.action << " actor=" << event.actor
                      << " at=" << event.occurredAt
                      << " reason=" << event.reason << '\n';
        }
    }
};

int main() {
    try {
        EquipmentRegistry registry;

        auto created = registry.create(
            "EQ-900", "PUMP-900", "Cooling water pump", "asset-clerk"
        );
        std::cout << "Created: " << created.equipment.assetTag
                  << " version=" << created.equipment.version << '\n';

        auto approved = registry.changeStatus(
            "EQ-900", Status::Approved, 1,
            "maintenance-manager", "Technical documentation verified."
        );

        auto operational = registry.changeStatus(
            "EQ-900", Status::InService, approved.equipment.version,
            "plant-supervisor", "Installation and safety checks passed."
        );

        auto deleted = registry.softDelete(
            "EQ-900", operational.equipment.version,
            "records-officer", "Duplicate departmental assignment."
        );

        std::cout << "Active equipment after deletion: "
                  << registry.activeEquipment().size() << '\n';

        auto restored = registry.restore(
            "EQ-900", deleted.equipment.version,
            "records-officer", "Original departmental ownership confirmed."
        );

        std::cout << "Restored version: "
                  << restored.equipment.version << '\n';

        try {
            registry.changeStatus(
                "EQ-900", Status::Requested, restored.equipment.version,
                "plant-supervisor", "Attempt to reverse the lifecycle."
            );
        } catch (const InvalidTransitionError& error) {
            std::cout << "Rejected status change: " << error.what() << '\n';
        }

        try {
            registry.softDelete(
                "EQ-900", 1, "records-officer", "Stale version test."
            );
        } catch (const ConcurrencyError& error) {
            std::cout << "Rejected stale write: " << error.what() << '\n';
        }

        std::cout << "\nAudit history for EQ-900\n";
        registry.printHistory("EQ-900");
        std::cout << "Audit coverage valid: "
                  << std::boolalpha << registry.auditCoverageValid() << '\n';

        return 0;
    } catch (const std::exception& error) {
        std::cerr << "Fatal error: " << error.what() << '\n';
        return 1;
    }
}
