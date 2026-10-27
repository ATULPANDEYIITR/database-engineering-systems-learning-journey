#include <algorithm>
#include <cmath>
#include <iomanip>
#include <iostream>
#include <map>
#include <optional>
#include <set>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

enum class ExtensionState {
    Available,
    Installed
};

struct Extension {
    std::string name;
    std::string version;
    std::string category;
    std::vector<std::string> dependencies;
    ExtensionState state{ExtensionState::Available};
};

class ExtensionCatalog {
private:
    std::map<std::string, Extension> extensions_;

public:
    void registerExtension(Extension extension) {
        if (extension.name.empty() || extension.version.empty()) {
            throw std::invalid_argument("Extension name and version are required");
        }

        if (extensions_.contains(extension.name)) {
            throw std::invalid_argument("Extension already exists: " + extension.name);
        }

        extensions_.emplace(extension.name, std::move(extension));
    }

    void install(const std::string& name) {
        auto it = extensions_.find(name);
        if (it == extensions_.end()) {
            throw std::out_of_range("Unknown extension: " + name);
        }

        for (const auto& dependency : it->second.dependencies) {
            auto dependencyIt = extensions_.find(dependency);

            if (dependencyIt == extensions_.end() ||
                dependencyIt->second.state != ExtensionState::Installed) {
                throw std::runtime_error(
                    "Missing dependency " + dependency + " for " + name
                );
            }
        }

        it->second.state = ExtensionState::Installed;
    }

    const std::map<std::string, Extension>& all() const {
        return extensions_;
    }
};

struct Point {
    double longitude{};
    double latitude{};

    void validate() const {
        if (!std::isfinite(longitude) || !std::isfinite(latitude)) {
            throw std::invalid_argument("Coordinates must be finite");
        }

        if (longitude < -180.0 || longitude > 180.0) {
            throw std::invalid_argument("Longitude outside valid range");
        }

        if (latitude < -90.0 || latitude > 90.0) {
            throw std::invalid_argument("Latitude outside valid range");
        }
    }
};

enum class GeometryType {
    Point,
    LineString,
    Polygon
};

struct SpatialFeature {
    int id;
    std::string name;
    GeometryType type;
    std::vector<Point> coordinates;

    void validate() const {
        if (id <= 0 || name.empty()) {
            throw std::invalid_argument("Invalid spatial feature identity");
        }

        if (coordinates.empty()) {
            throw std::invalid_argument("Spatial feature has no coordinates");
        }

        for (const auto& point : coordinates) {
            point.validate();
        }

        if (type == GeometryType::Point && coordinates.size() != 1) {
            throw std::invalid_argument("Point must have one coordinate");
        }

        if (type == GeometryType::LineString && coordinates.size() < 2) {
            throw std::invalid_argument("LineString needs two coordinates");
        }

        if (type == GeometryType::Polygon) {
            if (coordinates.size() < 4) {
                throw std::invalid_argument("Polygon needs at least four coordinates");
            }

            const auto& first = coordinates.front();
            const auto& last = coordinates.back();

            if (first.longitude != last.longitude ||
                first.latitude != last.latitude) {
                throw std::invalid_argument("Polygon ring is not closed");
            }
        }
    }
};

double haversineKm(const Point& a, const Point& b) {
    a.validate();
    b.validate();

    constexpr double earthRadiusKm = 6371.0088;
    constexpr double pi = 3.14159265358979323846;

    const double lat1 = a.latitude * pi / 180.0;
    const double lat2 = b.latitude * pi / 180.0;
    const double dLat = lat2 - lat1;
    const double dLon = (b.longitude - a.longitude) * pi / 180.0;

    double h =
        std::sin(dLat / 2.0) * std::sin(dLat / 2.0) +
        std::cos(lat1) * std::cos(lat2) *
        std::sin(dLon / 2.0) * std::sin(dLon / 2.0);

    h = std::clamp(h, 0.0, 1.0);

    return 2.0 * earthRadiusKm *
           std::atan2(std::sqrt(h), std::sqrt(1.0 - h));
}

std::pair<const SpatialFeature*, double>
nearestPoint(const Point& origin,
             const std::vector<SpatialFeature>& features) {
    origin.validate();

    const SpatialFeature* nearest = nullptr;
    double nearestDistance = std::numeric_limits<double>::infinity();

    for (const auto& feature : features) {
        feature.validate();

        if (feature.type != GeometryType::Point) {
            continue;
        }

        const double distance =
            haversineKm(origin, feature.coordinates.front());

        if (distance < nearestDistance) {
            nearestDistance = distance;
            nearest = &feature;
        }
    }

    if (nearest == nullptr) {
        throw std::runtime_error("No point features available");
    }

    return {nearest, nearestDistance};
}

class MergeEligibilityPolicy {
private:
    std::set<std::string> requiredChecks_;

public:
    explicit MergeEligibilityPolicy(std::set<std::string> requiredChecks)
        : requiredChecks_(std::move(requiredChecks)) {}

    bool eligible(
        bool openPullRequest,
        bool conversationsResolved,
        bool requiredReviewApproved,
        const std::map<std::string, bool>& checks,
        bool branchProtected,
        bool directPushAttempt
    ) const {
        if (!openPullRequest) {
            return false;
        }

        if (!conversationsResolved || !requiredReviewApproved) {
            return false;
        }

        if (branchProtected && directPushAttempt) {
            return false;
        }

        for (const auto& check : requiredChecks_) {
            auto it = checks.find(check);

            if (it == checks.end() || !it->second) {
                return false;
            }
        }

        return true;
    }
};

int main() {
    try {
        ExtensionCatalog catalog;

        catalog.registerExtension({
            "pgcrypto",
            "1.3",
            "security",
            {}
        });

        catalog.registerExtension({
            "postgis",
            "3.x",
            "spatial",
            {}
        });

        catalog.registerExtension({
            "postgis_raster",
            "3.x",
            "spatial",
            {"postgis"}
        });

        catalog.registerExtension({
            "postgis_topology",
            "3.x",
            "spatial",
            {"postgis"}
        });

        catalog.install("pgcrypto");
        catalog.install("postgis");
        catalog.install("postgis_raster");
        catalog.install("postgis_topology");

        std::cout << "=== PostgreSQL Extension Catalog ===\n";
        for (const auto& [name, extension] : catalog.all()) {
            std::cout
                << std::left
                << std::setw(22) << name
                << std::setw(8) << extension.version
                << std::setw(12) << extension.category
                << (extension.state == ExtensionState::Installed
                    ? "installed"
                    : "available")
                << '\n';
        }

        std::vector<SpatialFeature> facilities{
            {
                1,
                "Lucknow Office",
                GeometryType::Point,
                {{80.9462, 26.8467}}
            },
            {
                2,
                "Kanpur Depot",
                GeometryType::Point,
                {{80.3319, 26.4499}}
            },
            {
                3,
                "Prayagraj Depot",
                GeometryType::Point,
                {{81.8463, 25.4358}}
            }
        };

        const Point origin{80.9462, 26.8467};

        const auto [nearest, distance] =
            nearestPoint(origin, facilities);

        std::cout << "\n=== Spatial Query ===\n";
        std::cout << "Origin: Lucknow Office\n";
        std::cout << "Nearest feature: " << nearest->name << '\n';
        std::cout << "Distance: "
                  << std::fixed << std::setprecision(2)
                  << distance << " km\n";

        MergeEligibilityPolicy mergePolicy({
            "unit-tests",
            "security-scan",
            "schema-validation"
        });

        const bool eligible = mergePolicy.eligible(
            true,
            true,
            true,
            {
                {"unit-tests", true},
                {"security-scan", true},
                {"schema-validation", true}
            },
            true,
            false
        );

        std::cout << "\n=== Spatial Platform Governance Example ===\n";
        std::cout << "Database change eligible for protected-branch merge: "
                  << (eligible ? "yes" : "no") << '\n';

        std::cout << "\nDesign note:\n";
        std::cout
            << "Application-side distance calculations are useful for the case study, "
            << "but production spatial filtering should normally be delegated to "
            << "PostGIS so GiST/SP-GiST indexes and spatial predicates can reduce "
            << "the amount of data processed by the application.\n";

    } catch (const std::exception& error) {
        std::cerr << "Failure: " << error.what() << '\n';
        return 1;
    }

    return 0;
}
