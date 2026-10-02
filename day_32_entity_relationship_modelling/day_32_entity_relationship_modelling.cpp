#include <algorithm>
#include <iomanip>
#include <iostream>
#include <optional>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

/*
    Entity Relationship Modeling: Repository Inventory Case Study

    Scenario
    --------
    A manufacturing company maintains a repository of physical assets.
    Assets belong to locations, belong to categories, and may participate
    in maintenance work orders. A work order can involve several technicians
    and several assets.

    The program is intentionally designed as a governance-oriented modeling
    engine rather than a syntax demonstration.

    It covers:
      - entity definitions
      - simple and composite attributes
      - primary keys
      - cardinality and participation
      - one-to-many relationships
      - many-to-many relationships
      - associative entities
      - relationship attributes
      - validation
      - referential integrity
      - domain constraints
      - query-like traversals
      - schema mapping decisions
      - complexity and design trade-offs

    Build:
        g++ -std=c++17 -O2 -Wall -Wextra -pedantic er_model.cpp -o er_model
*/

namespace er {

enum class AttributeKind {
    Simple,
    Composite,
    Multivalued,
    Derived
};

enum class Cardinality {
    One,
    Many
};

struct Attribute {
    std::string name;
    std::string type;
    AttributeKind kind = AttributeKind::Simple;
    bool required = false;
    std::vector<Attribute> children;
    std::string description;

    void validate() const {
        if (name.empty()) {
            throw std::invalid_argument("Attribute name cannot be empty.");
        }

        if (kind == AttributeKind::Composite && children.empty()) {
            throw std::invalid_argument(
                "Composite attribute '" + name +
                "' requires child attributes."
            );
        }

        if (kind != AttributeKind::Composite && !children.empty()) {
            throw std::invalid_argument(
                "Only composite attributes may have children: " + name
            );
        }

        for (const auto& child : children) {
            child.validate();
        }
    }

    void flatten(std::vector<const Attribute*>& result) const {
        validate();

        if (kind != AttributeKind::Composite) {
            result.push_back(this);
            return;
        }

        for (const auto& child : children) {
            child.flatten(result);
        }
    }
};

struct Entity {
    std::string name;
    std::string description;
    std::unordered_map<std::string, Attribute> attributes;
    std::vector<std::string> primaryKey;

    void addAttribute(Attribute attribute) {
        attribute.validate();

        if (attributes.contains(attribute.name)) {
            throw std::invalid_argument(
                "Duplicate attribute '" + attribute.name +
                "' in entity '" + name + "'."
            );
        }

        attributes.emplace(attribute.name, std::move(attribute));
    }

    void setPrimaryKey(std::vector<std::string> key) {
        if (key.empty()) {
            throw std::invalid_argument(
                "Entity '" + name + "' requires a primary key."
            );
        }

        for (const auto& keyPart : key) {
            auto it = attributes.find(keyPart);

            if (it == attributes.end()) {
                throw std::invalid_argument(
                    "Primary-key attribute '" + keyPart +
                    "' does not exist in '" + name + "'."
                );
            }

            if (it->second.kind == AttributeKind::Derived) {
                throw std::invalid_argument(
                    "Derived attribute '" + keyPart +
                    "' cannot be used as a primary key."
                );
            }
        }

        primaryKey = std::move(key);
    }

    std::vector<const Attribute*> leafAttributes() const {
        std::vector<const Attribute*> result;

        for (const auto& [_, attribute] : attributes) {
            attribute.flatten(result);
        }

        return result;
    }

    bool hasAttribute(const std::string& attributeName) const {
        return attributes.contains(attributeName);
    }
};

struct Endpoint {
    std::string entity;
    int minimum = 0;
    std::optional<int> maximum;

    void validate() const {
        if (minimum != 0 && minimum != 1) {
            throw std::invalid_argument(
                "Minimum cardinality must be 0 or 1."
            );
        }

        if (maximum.has_value() && maximum.value() < 1) {
            throw std::invalid_argument(
                "Maximum cardinality must be positive."
            );
        }

        if (
            maximum.has_value() &&
            minimum > maximum.value()
        ) {
            throw std::invalid_argument(
                "Minimum cardinality cannot exceed maximum."
            );
        }
    }

    bool isMany() const {
        return !maximum.has_value();
    }

    bool isMandatory() const {
        return minimum == 1;
    }

    std::string notation() const {
        std::ostringstream out;
        out << "(" << minimum << ",";
        if (maximum.has_value()) {
            out << maximum.value();
        } else {
            out << "N";
        }
        out << ")";
        return out.str();
    }
};

struct Relationship {
    std::string name;
    Endpoint left;
    Endpoint right;
    std::string description;
    std::vector<Attribute> attributes;

    std::string type() const {
        if (left.isMany() && right.isMany()) {
            return "many-to-many";
        }

        if (left.isMany() || right.isMany()) {
            return "one-to-many";
        }

        return "one-to-one";
    }
};

struct Model {
    std::string name;
    std::unordered_map<std::string, Entity> entities;
    std::vector<Relationship> relationships;

    void addEntity(Entity entity) {
        if (entities.contains(entity.name)) {
            throw std::invalid_argument(
                "Duplicate entity '" + entity.name + "'."
            );
        }

        entities.emplace(entity.name, std::move(entity));
    }

    void addRelationship(Relationship relationship) {
        relationship.left.validate();
        relationship.right.validate();

        if (!entities.contains(relationship.left.entity)) {
            throw std::invalid_argument(
                "Unknown left endpoint entity: " +
                relationship.left.entity
            );
        }

        if (!entities.contains(relationship.right.entity)) {
            throw std::invalid_argument(
                "Unknown right endpoint entity: " +
                relationship.right.entity
            );
        }

        if (relationship.name.empty()) {
            throw std::invalid_argument(
                "Relationship name cannot be empty."
            );
        }

        for (const auto& attribute : relationship.attributes) {
            attribute.validate();
        }

        relationships.push_back(std::move(relationship));
    }

    void validate() const {
        for (const auto& [name, entity] : entities) {
            if (entity.primaryKey.empty()) {
                throw std::invalid_argument(
                    "Entity '" + name + "' has no primary key."
                );
            }

            for (const auto& [_, attribute] : entity.attributes) {
                attribute.validate();
            }
        }

        for (const auto& relationship : relationships) {
            if (!entities.contains(relationship.left.entity)) {
                throw std::invalid_argument(
                    "Dangling left relationship endpoint."
                );
            }

            if (!entities.contains(relationship.right.entity)) {
                throw std::invalid_argument(
                    "Dangling right relationship endpoint."
                );
            }
        }
    }
};

}  // namespace er

// ---------------------------------------------------------------------------
// Domain records
// ---------------------------------------------------------------------------

struct Asset {
    std::string assetId;
    std::string serialNumber;
    std::string categoryId;
    std::string locationId;
    std::string status;
};

struct Location {
    std::string locationId;
    std::string name;
};

struct Technician {
    std::string technicianId;
    std::string name;
    std::string skill;
};

struct WorkOrder {
    std::string workOrderId;
    std::string description;
    std::string status;
};

struct WorkOrderAsset {
    std::string workOrderId;
    std::string assetId;
    std::string role;
};

struct WorkOrderTechnician {
    std::string workOrderId;
    std::string technicianId;
    double hoursWorked = 0.0;
};

// ---------------------------------------------------------------------------
// Case-study repository
// ---------------------------------------------------------------------------

class AssetRepository {
private:
    std::unordered_map<std::string, Asset> assets;
    std::unordered_map<std::string, Location> locations;
    std::unordered_map<std::string, Technician> technicians;
    std::unordered_map<std::string, WorkOrder> workOrders;

    // Associative entities are represented explicitly because a work order
    // can involve many assets and an asset can appear in many work orders.
    std::vector<WorkOrderAsset> workOrderAssets;
    std::vector<WorkOrderTechnician> workOrderTechnicians;

    static void requireNonEmpty(
        const std::string& value,
        const std::string& field
    ) {
        if (value.empty()) {
            throw std::invalid_argument(field + " cannot be empty.");
        }
    }

    void requireLocation(const std::string& locationId) const {
        if (!locations.contains(locationId)) {
            throw std::invalid_argument(
                "Location does not exist: " + locationId
            );
        }
    }

    void requireAsset(const std::string& assetId) const {
        if (!assets.contains(assetId)) {
            throw std::invalid_argument(
                "Asset does not exist: " + assetId
            );
        }
    }

    void requireTechnician(const std::string& technicianId) const {
        if (!technicians.contains(technicianId)) {
            throw std::invalid_argument(
                "Technician does not exist: " + technicianId
            );
        }
    }

    void requireWorkOrder(const std::string& workOrderId) const {
        if (!workOrders.contains(workOrderId)) {
            throw std::invalid_argument(
                "Work order does not exist: " + workOrderId
            );
        }
    }

public:
    void addLocation(Location location) {
        requireNonEmpty(location.locationId, "Location ID");
        requireNonEmpty(location.name, "Location name");

        if (locations.contains(location.locationId)) {
            throw std::invalid_argument(
                "Duplicate location ID: " + location.locationId
            );
        }

        locations.emplace(location.locationId, std::move(location));
    }

    void addAsset(Asset asset) {
        requireNonEmpty(asset.assetId, "Asset ID");
        requireNonEmpty(asset.serialNumber, "Serial number");
        requireLocation(asset.locationId);

        if (assets.contains(asset.assetId)) {
            throw std::invalid_argument(
                "Duplicate asset ID: " + asset.assetId
            );
        }

        const bool duplicateSerial = std::any_of(
            assets.begin(),
            assets.end(),
            [&](const auto& pair) {
                return pair.second.serialNumber == asset.serialNumber;
            }
        );

        if (duplicateSerial) {
            throw std::invalid_argument(
                "Serial number must identify only one asset: " +
                asset.serialNumber
            );
        }

        assets.emplace(asset.assetId, std::move(asset));
    }

    void addTechnician(Technician technician) {
        requireNonEmpty(technician.technicianId, "Technician ID");
        requireNonEmpty(technician.name, "Technician name");

        if (technicians.contains(technician.technicianId)) {
            throw std::invalid_argument(
                "Duplicate technician ID: " +
                technician.technicianId
            );
        }

        technicians.emplace(
            technician.technicianId,
            std::move(technician)
        );
    }

    void addWorkOrder(WorkOrder workOrder) {
        requireNonEmpty(workOrder.workOrderId, "Work order ID");
        requireNonEmpty(workOrder.description, "Work order description");

        if (workOrders.contains(workOrder.workOrderId)) {
            throw std::invalid_argument(
                "Duplicate work order ID: " +
                workOrder.workOrderId
            );
        }

        if (
            workOrder.status != "OPEN" &&
            workOrder.status != "CLOSED"
        ) {
            throw std::invalid_argument(
                "Work order status must be OPEN or CLOSED."
            );
        }

        workOrders.emplace(
            workOrder.workOrderId,
            std::move(workOrder)
        );
    }

    void assignAsset(
        const std::string& workOrderId,
        const std::string& assetId,
        const std::string& role
    ) {
        requireWorkOrder(workOrderId);
        requireAsset(assetId);
        requireNonEmpty(role, "Asset role");

        const bool duplicate = std::any_of(
            workOrderAssets.begin(),
            workOrderAssets.end(),
            [&](const WorkOrderAsset& assignment) {
                return assignment.workOrderId == workOrderId &&
                       assignment.assetId == assetId;
            }
        );

        if (duplicate) {
            throw std::invalid_argument(
                "Asset is already assigned to this work order."
            );
        }

        workOrderAssets.push_back(
            {workOrderId, assetId, role}
        );
    }

    void assignTechnician(
        const std::string& workOrderId,
        const std::string& technicianId,
        double hoursWorked
    ) {
        requireWorkOrder(workOrderId);
        requireTechnician(technicianId);

        if (hoursWorked < 0.0 || hoursWorked > 24.0) {
            throw std::invalid_argument(
                "Hours worked must be between 0 and 24."
            );
        }

        const bool duplicate = std::any_of(
            workOrderTechnicians.begin(),
            workOrderTechnicians.end(),
            [&](const WorkOrderTechnician& assignment) {
                return assignment.workOrderId == workOrderId &&
                       assignment.technicianId == technicianId;
            }
        );

        if (duplicate) {
            throw std::invalid_argument(
                "Technician is already assigned to this work order."
            );
        }

        workOrderTechnicians.push_back(
            {workOrderId, technicianId, hoursWorked}
        );
    }

    std::vector<Asset> assetsAtLocation(
        const std::string& locationId
    ) const {
        requireLocation(locationId);

        std::vector<Asset> result;

        for (const auto& [_, asset] : assets) {
            if (asset.locationId == locationId) {
                result.push_back(asset);
            }
        }

        return result;
    }

    std::vector<Asset> assetsForWorkOrder(
        const std::string& workOrderId
    ) const {
        requireWorkOrder(workOrderId);

        std::vector<Asset> result;

        for (const auto& assignment : workOrderAssets) {
            if (assignment.workOrderId == workOrderId) {
                result.push_back(assets.at(assignment.assetId));
            }
        }

        return result;
    }

    std::vector<Technician> techniciansForWorkOrder(
        const std::string& workOrderId
    ) const {
        requireWorkOrder(workOrderId);

        std::vector<Technician> result;

        for (const auto& assignment : workOrderTechnicians) {
            if (assignment.workOrderId == workOrderId) {
                result.push_back(
                    technicians.at(assignment.technicianId)
                );
            }
        }

        return result;
    }

    double technicianHoursForWorkOrder(
        const std::string& workOrderId
    ) const {
        requireWorkOrder(workOrderId);

        double total = 0.0;

        for (const auto& assignment : workOrderTechnicians) {
            if (assignment.workOrderId == workOrderId) {
                total += assignment.hoursWorked;
            }
        }

        return total;
    }

    void printWorkOrderGraph(
        const std::string& workOrderId
    ) const {
        const auto& workOrder = workOrders.at(workOrderId);

        std::cout << "\nWORK ORDER GRAPH\n";
        std::cout << workOrder.workOrderId
                  << " -> " << workOrder.description << '\n';

        std::cout << "  Assets:\n";
        for (const auto& asset : assetsForWorkOrder(workOrderId)) {
            std::cout << "    " << asset.assetId
                      << " [" << asset.serialNumber << "]\n";
        }

        std::cout << "  Technicians:\n";
        for (const auto& technician :
             techniciansForWorkOrder(workOrderId)) {
            std::cout << "    " << technician.technicianId
                      << " [" << technician.name << "]\n";
        }

        std::cout << "  Total technician hours: "
                  << std::fixed << std::setprecision(1)
                  << technicianHoursForWorkOrder(workOrderId)
                  << '\n';
    }
};

// ---------------------------------------------------------------------------
// ER model construction for the case study
// ---------------------------------------------------------------------------

er::Model buildAssetModel() {
    er::Model model{
        "Asset Maintenance ER Model"
    };

    er::Entity location{
        "Location",
        "Physical facility or operational area."
    };

    location.addAttribute({
        "locationId",
        "string",
        er::AttributeKind::Simple,
        true,
        {},
        "Stable location identifier"
    });

    location.addAttribute({
        "name",
        "string",
        er::AttributeKind::Simple,
        true,
        {},
        "Human-readable location"
    });

    location.setPrimaryKey({"locationId"});
    model.addEntity(std::move(location));

    er::Entity asset{
        "Asset",
        "Physical item tracked by the organization."
    };

    asset.addAttribute({
        "assetId",
        "string",
        er::AttributeKind::Simple,
        true,
        {},
        "Internal asset identifier"
    });

    asset.addAttribute({
        "serialNumber",
        "string",
        er::AttributeKind::Simple,
        true,
        {},
        "Manufacturer serial number"
    });

    asset.addAttribute({
        "status",
        "string",
        er::AttributeKind::Simple,
        true,
        {},
        "Operational state"
    });

    asset.addAttribute({
        "locationId",
        "string",
        er::AttributeKind::Simple,
        true,
        {},
        "Foreign key to Location"
    });

    asset.addAttribute({
        "physicalAddress",
        "composite",
        er::AttributeKind::Composite,
        false,
        {
            {
                "building",
                "string",
                er::AttributeKind::Simple,
                false,
                {},
                "Building"
            },
            {
                "floor",
                "integer",
                er::AttributeKind::Simple,
                false,
                {},
                "Floor"
            }
        },
        "Decomposable physical location"
    });

    asset.setPrimaryKey({"assetId"});
    model.addEntity(std::move(asset));

    er::Entity technician{
        "Technician",
        "Employee qualified to perform maintenance."
    };

    technician.addAttribute({
        "technicianId",
        "string",
        er::AttributeKind::Simple,
        true,
        {},
        "Technician identifier"
    });

    technician.addAttribute({
        "name",
        "string",
        er::AttributeKind::Simple,
        true,
        {},
        "Technician name"
    });

    technician.addAttribute({
        "skill",
        "string",
        er::AttributeKind::Simple,
        true,
        {},
        "Primary technical skill"
    });

    technician.setPrimaryKey({"technicianId"});
    model.addEntity(std::move(technician));

    er::Entity workOrder{
        "WorkOrder",
        "Maintenance request or scheduled maintenance activity."
    };

    workOrder.addAttribute({
        "workOrderId",
        "string",
        er::AttributeKind::Simple,
        true,
        {},
        "Work order identifier"
    });

    workOrder.addAttribute({
        "description",
        "string",
        er::AttributeKind::Simple,
        true,
        {},
        "Maintenance description"
    });

    workOrder.addAttribute({
        "status",
        "string",
        er::AttributeKind::Simple,
        true,
        {},
        "OPEN or CLOSED"
    });

    workOrder.setPrimaryKey({"workOrderId"});
    model.addEntity(std::move(workOrder));

    er::Entity workOrderAsset{
        "WorkOrderAsset",
        "Associative entity resolving WorkOrder to Asset."
    };

    workOrderAsset.addAttribute({
        "workOrderId",
        "string",
        er::AttributeKind::Simple,
        true,
        {},
        "Work order foreign key"
    });

    workOrderAsset.addAttribute({
        "assetId",
        "string",
        er::AttributeKind::Simple,
        true,
        {},
        "Asset foreign key"
    });

    workOrderAsset.addAttribute({
        "role",
        "string",
        er::AttributeKind::Simple,
        true,
        {},
        "Affected asset role in the work order"
    });

    // Composite identity demonstrates an identifying association: the
    // association row is uniquely identified by its two parent references.
    workOrderAsset.setPrimaryKey({"workOrderId", "assetId"});
    model.addEntity(std::move(workOrderAsset));

    er::Entity workOrderTechnician{
        "WorkOrderTechnician",
        "Associative entity resolving WorkOrder to Technician."
    };

    workOrderTechnician.addAttribute({
        "workOrderId",
        "string",
        er::AttributeKind::Simple,
        true,
        {},
        "Work order foreign key"
    });

    workOrderTechnician.addAttribute({
        "technicianId",
        "string",
        er::AttributeKind::Simple,
        true,
        {},
        "Technician foreign key"
    });

    workOrderTechnician.addAttribute({
        "hoursWorked",
        "decimal",
        er::AttributeKind::Simple,
        true,
        {},
        "Relationship-specific effort"
    });

    workOrderTechnician.setPrimaryKey({
        "workOrderId",
        "technicianId"
    });
    model.addEntity(std::move(workOrderTechnician));

    model.addRelationship({
        "LOCATED_AT",
        {"Location", 0, std::nullopt},
        {"Asset", 1, 1},
        "Each asset is located at one location; a location can contain many assets.",
        {}
    });

    model.addRelationship({
        "HAS_ASSET_LINK",
        {"WorkOrder", 0, std::nullopt},
        {"WorkOrderAsset", 1, 1},
        "A work order may reference multiple asset-association rows.",
        {}
    });

    model.addRelationship({
        "ASSET_LINK_TARGET",
        {"Asset", 0, std::nullopt},
        {"WorkOrderAsset", 1, 1},
        "An asset can occur in multiple work-order associations.",
        {}
    });

    model.addRelationship({
        "HAS_TECHNICIAN_LINK",
        {"WorkOrder", 0, std::nullopt},
        {"WorkOrderTechnician", 1, 1},
        "A work order can involve multiple technicians.",
        {}
    });

    model.addRelationship({
        "TECHNICIAN_LINK_TARGET",
        {"Technician", 0, std::nullopt},
        {"WorkOrderTechnician", 1, 1},
        "A technician can work on many work orders.",
        {}
    });

    return model;
}

// ---------------------------------------------------------------------------
// Schema interpretation
// ---------------------------------------------------------------------------

void printRelationalMapping(const er::Model& model) {
    std::cout << "\nRELATIONAL MAPPING\n";

    for (const auto& [entityName, entity] : model.entities) {
        std::cout << "TABLE " << entityName << '\n';

        for (const auto& attribute : entity.leafAttributes()) {
            const bool isPrimaryKey = std::find(
                entity.primaryKey.begin(),
                entity.primaryKey.end(),
                attribute->name
            ) != entity.primaryKey.end();

            std::cout << "  "
                      << attribute->name
                      << " : "
                      << attribute->type;

            if (isPrimaryKey) {
                std::cout << " [PK]";
            }

            if (attribute->required) {
                std::cout << " [NOT NULL]";
            }

            std::cout << '\n';
        }

        std::cout << "  Primary key: (";

        for (std::size_t i = 0; i < entity.primaryKey.size(); ++i) {
            if (i > 0) {
                std::cout << ", ";
            }
            std::cout << entity.primaryKey[i];
        }

        std::cout << ")\n";
    }
}

void printRelationshipSemantics(const er::Model& model) {
    std::cout << "\nRELATIONSHIP SEMANTICS\n";

    for (const auto& relationship : model.relationships) {
        std::cout
            << relationship.left.entity
            << " "
            << relationship.left.notation()
            << " -- "
            << relationship.name
            << " -- "
            << relationship.right.notation()
            << " "
            << relationship.right.entity
            << " : "
            << relationship.type()
            << '\n';
    }
}

// ---------------------------------------------------------------------------
// Main case study
// ---------------------------------------------------------------------------

int main() {
    try {
        std::cout << std::string(78, '=') << '\n';
        std::cout << "ENTITY RELATIONSHIP MODELING CASE STUDY\n";
        std::cout << std::string(78, '=') << '\n';

        const er::Model model = buildAssetModel();

        // Validation occurs before operational records are processed. This
        // keeps conceptual-model errors separate from application data errors.
        model.validate();

        std::cout << "\nMODEL: " << model.name << '\n';
        std::cout << "Entities: " << model.entities.size() << '\n';
        std::cout << "Relationships: " << model.relationships.size() << '\n';

        printRelationshipSemantics(model);
        printRelationalMapping(model);

        std::cout << "\nCASE STUDY DATA\n";

        AssetRepository repository;

        repository.addLocation({
            "LOC-01",
            "Lucknow Assembly Facility"
        });

        repository.addLocation({
            "LOC-02",
            "Kanpur Service Center"
        });

        repository.addAsset({
            "AST-100",
            "SN-AX91",
            "COMPRESSOR",
            "LOC-01",
            "ACTIVE"
        });

        repository.addAsset({
            "AST-200",
            "SN-BX17",
            "PUMP",
            "LOC-01",
            "ACTIVE"
        });

        repository.addAsset({
            "AST-300",
            "SN-CZ42",
            "GENERATOR",
            "LOC-02",
            "ACTIVE"
        });

        repository.addTechnician({
            "TECH-01",
            "Priya",
            "Electrical"
        });

        repository.addTechnician({
            "TECH-02",
            "Ravi",
            "Mechanical"
        });

        repository.addWorkOrder({
            "WO-5001",
            "Inspect compressor vibration and replace worn coupling.",
            "OPEN"
        });

        repository.addWorkOrder({
            "WO-5002",
            "Inspect pump seal and verify pressure.",
            "OPEN"
        });

        repository.assignAsset(
            "WO-5001",
            "AST-100",
            "Primary affected asset"
        );

        repository.assignAsset(
            "WO-5001",
            "AST-200",
            "Related pump"
        );

        repository.assignAsset(
            "WO-5002",
            "AST-200",
            "Primary affected asset"
        );

        repository.assignTechnician(
            "WO-5001",
            "TECH-01",
            2.5
        );

        repository.assignTechnician(
            "WO-5001",
            "TECH-02",
            3.0
        );

        repository.assignTechnician(
            "WO-5002",
            "TECH-02",
            1.5
        );

        repository.printWorkOrderGraph("WO-5001");

        std::cout << "\nLOCATION TRAVERSAL\n";

        const auto locationAssets =
            repository.assetsAtLocation("LOC-01");

        for (const auto& asset : locationAssets) {
            std::cout
                << asset.assetId
                << " -> "
                << asset.serialNumber
                << " -> "
                << asset.status
                << '\n';
        }

        std::cout << "\nRELATIONSHIP-SPECIFIC ATTRIBUTE\n";
        std::cout
            << "WorkOrderTechnician.hoursWorked belongs to the association "
               "between a work order and technician, not to either entity.\n";

        std::cout << "\nIDENTIFYING ASSOCIATION\n";
        std::cout
            << "WorkOrderAsset uses (workOrderId, assetId) as its composite "
               "primary key. The association is uniquely identified by the "
               "two parent references.\n";

        std::cout << "\nEDGE CASE: DUPLICATE ASSOCIATION\n";

        try {
            repository.assignAsset(
                "WO-5001",
                "AST-100",
                "Duplicate reference"
            );
        } catch (const std::exception& error) {
            std::cout
                << "Rejected as expected: "
                << error.what()
                << '\n';
        }

        std::cout << "\nEDGE CASE: REFERENTIAL INTEGRITY\n";

        try {
            repository.assignAsset(
                "WO-5001",
                "AST-999",
                "Unknown asset"
            );
        } catch (const std::exception& error) {
            std::cout
                << "Rejected as expected: "
                << error.what()
                << '\n';
        }

        std::cout << "\nEDGE CASE: INVALID CARDINALITY\n";

        try {
            er::Endpoint invalidEndpoint{
                "Asset",
                2,
                1
            };

            invalidEndpoint.validate();
        } catch (const std::exception& error) {
            std::cout
                << "Rejected as expected: "
                << error.what()
                << '\n';
        }

        std::cout << "\nPERFORMANCE CHARACTERISTICS\n";
        std::cout
            << "Entity lookup uses unordered_map and is expected O(1) average.\n"
            << "Associative-record traversal is O(E) for E association rows "
               "because this case study stores links in vectors.\n"
            << "A production relational database would index foreign keys "
               "such as workOrderId and assetId to avoid repeatedly scanning "
               "large association tables.\n";

        std::cout << "\nDESIGN TRADE-OFFS\n";
        std::cout
            << "The conceptual model keeps WorkOrder, Asset, and Technician "
               "independent. Many-to-many relationships are resolved through "
               "associative entities so relationship-specific data such as "
               "role and hoursWorked has a precise owner.\n";

        std::cout
            << "A single comma-separated asset list inside WorkOrder would "
               "destroy atomicity and make referential integrity difficult. "
               "The associative entity preserves individual relationships.\n";

        std::cout
            << "The model distinguishes structural ER constraints from "
               "business rules. Capacity limits, valid status values, and "
               "hoursWorked ranges are application/domain constraints rather "
               "than cardinality alone.\n";

        std::cout << "\nCASE STUDY COMPLETE\n";
        return 0;
    }
    catch (const std::exception& error) {
        std::cerr
            << "Model execution failed: "
            << error.what()
            << '\n';

        return 1;
    }
}
