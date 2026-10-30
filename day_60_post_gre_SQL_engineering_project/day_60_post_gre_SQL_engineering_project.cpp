#include <algorithm>
#include <cmath>
#include <iomanip>
#include <iostream>
#include <numeric>
#include <set>
#include <stdexcept>
#include <string>
#include <vector>

/*
 * PostgreSQL connection-capacity planner.
 *
 * The planner estimates connection demand during normal operation and
 * rolling deployments. It does not connect to PostgreSQL. Its purpose is
 * to validate pool configuration before deployment and reserve capacity
 * for administration, monitoring, and emergency access.
 *
 * Build:
 *   g++ -std=c++17 -O2 -Wall -Wextra -pedantic postgres_capacity.cpp -o postgres_capacity
 *
 * Run:
 *   ./postgres_capacity
 *   ./postgres_capacity --max-connections 100
 *   ./postgres_capacity --max-connections 100 --strict
 */

struct ServerLimits {
    int maxConnections{};
    int superuserReserve{};
    int maintenanceReserve{};
};

struct Workload {
    std::string name;
    int instances{};
    int poolSizePerInstance{};
};

struct WorkloadForecast {
    std::string name;
    int configuredInstances{};
    int peakInstances{};
    int poolSizePerInstance{};
    int normalConnections{};
    int peakConnections{};
};

struct CapacityPlan {
    int protectedConnections{};
    int applicationCapacity{};
    int normalDemand{};
    int peakDemand{};
    int peakHeadroom{};
    double peakUtilization{};
    bool safe{};
    std::vector<WorkloadForecast> forecasts;
};

class CapacityPlanner {
public:
    CapacityPlanner(
        ServerLimits limits,
        double rolloutSurgeFactor,
        std::vector<Workload> workloads
    )
        : limits_(limits),
          rolloutSurgeFactor_(rolloutSurgeFactor),
          workloads_(std::move(workloads)) {
        validate();
    }

    CapacityPlan evaluate() const {
        CapacityPlan plan;

        plan.protectedConnections =
            limits_.superuserReserve + limits_.maintenanceReserve;

        plan.applicationCapacity =
            limits_.maxConnections - plan.protectedConnections;

        for (const auto& workload : workloads_) {
            const int peakInstances = static_cast<int>(
                std::ceil(workload.instances * rolloutSurgeFactor_)
            );

            const int normalConnections =
                workload.instances * workload.poolSizePerInstance;

            const int peakConnections =
                peakInstances * workload.poolSizePerInstance;

            plan.normalDemand += normalConnections;
            plan.peakDemand += peakConnections;

            plan.forecasts.push_back({
                workload.name,
                workload.instances,
                peakInstances,
                workload.poolSizePerInstance,
                normalConnections,
                peakConnections
            });
        }

        plan.peakHeadroom =
            plan.applicationCapacity - plan.peakDemand;

        plan.peakUtilization =
            static_cast<double>(plan.peakDemand) /
            static_cast<double>(limits_.maxConnections);

        plan.safe =
            plan.applicationCapacity >= 0 &&
            plan.peakDemand <= plan.applicationCapacity;

        std::sort(
            plan.forecasts.begin(),
            plan.forecasts.end(),
            [](const WorkloadForecast& left,
               const WorkloadForecast& right) {
                return left.peakConnections > right.peakConnections;
            }
        );

        return plan;
    }

private:
    ServerLimits limits_;
    double rolloutSurgeFactor_;
    std::vector<Workload> workloads_;

    void validate() const {
        if (limits_.maxConnections <= 0) {
            throw std::invalid_argument(
                "max_connections must be greater than zero"
            );
        }

        if (limits_.superuserReserve < 0 ||
            limits_.maintenanceReserve < 0) {
            throw std::invalid_argument(
                "Connection reserves cannot be negative"
            );
        }

        if (limits_.superuserReserve +
                limits_.maintenanceReserve >=
            limits_.maxConnections) {
            throw std::invalid_argument(
                "Protected connection reserves leave no application capacity"
            );
        }

        if (!std::isfinite(rolloutSurgeFactor_) ||
            rolloutSurgeFactor_ < 1.0 ||
            rolloutSurgeFactor_ > 3.0) {
            throw std::invalid_argument(
                "Rollout surge factor must be between 1.0 and 3.0"
            );
        }

        if (workloads_.empty()) {
            throw std::invalid_argument(
                "At least one workload must be configured"
            );
        }

        std::set<std::string> names;

        for (const auto& workload : workloads_) {
            if (workload.name.empty()) {
                throw std::invalid_argument(
                    "Workload names cannot be empty"
                );
            }

            if (!names.insert(workload.name).second) {
                throw std::invalid_argument(
                    "Duplicate workload name: " + workload.name
                );
            }

            if (workload.instances < 1 ||
                workload.poolSizePerInstance < 1) {
                throw std::invalid_argument(
                    "Workload instances and pool size must be positive"
                );
            }

            if (workload.instances > 100000 ||
                workload.poolSizePerInstance > 100000) {
                throw std::invalid_argument(
                    "Workload configuration exceeds safe planning limits"
                );
            }
        }
    }
};

struct Arguments {
    int maxConnections = 180;
    int superuserReserve = 3;
    int maintenanceReserve = 20;
    double surgeFactor = 1.5;
    bool strict = false;
};

int parseInteger(const std::string& value, const std::string& option) {
    std::size_t consumed = 0;
    int parsed = 0;

    try {
        parsed = std::stoi(value, &consumed);
    } catch (const std::exception&) {
        throw std::invalid_argument(
            "Invalid integer for " + option + ": " + value
        );
    }

    if (consumed != value.size()) {
        throw std::invalid_argument(
            "Invalid integer for " + option + ": " + value
        );
    }

    return parsed;
}

double parseDouble(const std::string& value, const std::string& option) {
    std::size_t consumed = 0;
    double parsed = 0.0;

    try {
        parsed = std::stod(value, &consumed);
    } catch (const std::exception&) {
        throw std::invalid_argument(
            "Invalid number for " + option + ": " + value
        );
    }

    if (consumed != value.size() || !std::isfinite(parsed)) {
        throw std::invalid_argument(
            "Invalid number for " + option + ": " + value
        );
    }

    return parsed;
}

Arguments parseArguments(int argc, char* argv[]) {
    Arguments arguments;

    for (int index = 1; index < argc; ++index) {
        const std::string option = argv[index];

        if (option == "--strict") {
            arguments.strict = true;
            continue;
        }

        if (index + 1 >= argc) {
            throw std::invalid_argument(
                "Missing value for option " + option
            );
        }

        const std::string value = argv[++index];

        if (option == "--max-connections") {
            arguments.maxConnections =
                parseInteger(value, option);
        } else if (option == "--superuser-reserve") {
            arguments.superuserReserve =
                parseInteger(value, option);
        } else if (option == "--maintenance-reserve") {
            arguments.maintenanceReserve =
                parseInteger(value, option);
        } else if (option == "--surge-factor") {
            arguments.surgeFactor =
                parseDouble(value, option);
        } else {
            throw std::invalid_argument(
                "Unknown option: " + option
            );
        }
    }

    return arguments;
}

std::vector<Workload> defaultWorkloads() {
    return {
        {"api", 5, 12},
        {"background-workers", 2, 6},
        {"reporting", 2, 4}
    };
}

void printPlan(
    const ServerLimits& limits,
    double surgeFactor,
    const CapacityPlan& plan
) {
    std::cout << "\nPOSTGRESQL CONNECTION CAPACITY PLAN\n";
    std::cout << "-----------------------------------\n";

    std::cout << "Server max_connections:       "
              << limits.maxConnections << '\n';
    std::cout << "Superuser reserve:             "
              << limits.superuserReserve << '\n';
    std::cout << "Maintenance reserve:           "
              << limits.maintenanceReserve << '\n';
    std::cout << "Protected capacity:            "
              << plan.protectedConnections << '\n';
    std::cout << "Application capacity:          "
              << plan.applicationCapacity << '\n';
    std::cout << "Deployment surge factor:       "
              << std::fixed << std::setprecision(2)
              << surgeFactor << '\n';

    std::cout << "\nWORKLOAD FORECAST\n";
    std::cout << std::left
              << std::setw(25) << "Workload"
              << std::right
              << std::setw(12) << "Instances"
              << std::setw(12) << "Peak"
              << std::setw(12) << "Pool"
              << std::setw(14) << "Normal"
              << std::setw(14) << "Peak"
              << '\n';

    for (const auto& item : plan.forecasts) {
        std::cout << std::left
                  << std::setw(25) << item.name
                  << std::right
                  << std::setw(12) << item.configuredInstances
                  << std::setw(12) << item.peakInstances
                  << std::setw(12) << item.poolSizePerInstance
                  << std::setw(14) << item.normalConnections
                  << std::setw(14) << item.peakConnections
                  << '\n';
    }

    std::cout << "\nNormal application demand:     "
              << plan.normalDemand << '\n';
    std::cout << "Peak application demand:       "
              << plan.peakDemand << '\n';
    std::cout << "Peak headroom:                 "
              << plan.peakHeadroom << '\n';
    std::cout << "Peak utilization of server:    "
              << std::fixed << std::setprecision(1)
              << plan.peakUtilization * 100.0 << "%\n";

    std::cout << "Capacity decision:             "
              << (plan.safe ? "SAFE" : "UNSAFE") << '\n';

    if (!plan.safe) {
        std::cout
            << "\nThe configured pools exceed the capacity available "
               "after protected reservations.\n";
    }

    std::cout
        << "\nPlanning note: pool capacity is an upper-bound estimate. "
           "Compare it with pg_stat_activity, application pool metrics, "
           "and workload peaks before changing max_connections.\n";
}

int main(int argc, char* argv[]) {
    try {
        const Arguments arguments = parseArguments(argc, argv);

        const ServerLimits limits{
            arguments.maxConnections,
            arguments.superuserReserve,
            arguments.maintenanceReserve
        };

        CapacityPlanner planner(
            limits,
            arguments.surgeFactor,
            defaultWorkloads()
        );

        const CapacityPlan plan = planner.evaluate();

        printPlan(limits, arguments.surgeFactor, plan);

        if (!plan.safe && arguments.strict) {
            return 2;
        }

        return 0;
    } catch (const std::exception& error) {
        std::cerr << "ERROR: " << error.what() << '\n';
        std::cerr
            << "Usage: postgres_capacity "
               "[--max-connections N] "
               "[--superuser-reserve N] "
               "[--maintenance-reserve N] "
               "[--surge-factor X] [--strict]\n";
        return 1;
    }
}
