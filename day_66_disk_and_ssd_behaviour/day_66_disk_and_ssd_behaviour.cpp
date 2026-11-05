#include <algorithm>
#include <cmath>
#include <iomanip>
#include <iostream>
#include <map>
#include <numeric>
#include <stdexcept>
#include <string>
#include <vector>

/*
 * Disk and SSD Behavior
 *
 * C++17 storage performance and workload analysis engine.
 *
 * Models:
 * - HDD, SATA SSD, NVMe SSD
 * - Sequential and random operations
 * - IOPS and throughput
 * - Request queueing
 * - Latency distributions
 * - Performance classification
 */

enum class StorageType {
    HDD,
    SATA_SSD,
    NVME_SSD
};

enum class IOOperation {
    SEQUENTIAL_READ,
    RANDOM_READ,
    SEQUENTIAL_WRITE,
    RANDOM_WRITE
};

std::string toString(StorageType type) {
    switch (type) {
        case StorageType::HDD:
            return "HDD";
        case StorageType::SATA_SSD:
            return "SATA SSD";
        case StorageType::NVME_SSD:
            return "NVMe SSD";
    }

    throw std::invalid_argument("Unknown storage type");
}

std::string toString(IOOperation operation) {
    switch (operation) {
        case IOOperation::SEQUENTIAL_READ:
            return "Sequential Read";
        case IOOperation::RANDOM_READ:
            return "Random Read";
        case IOOperation::SEQUENTIAL_WRITE:
            return "Sequential Write";
        case IOOperation::RANDOM_WRITE:
            return "Random Write";
    }

    throw std::invalid_argument("Unknown I/O operation");
}

struct StorageDevice {
    std::string name;
    StorageType type;

    double sequentialReadMBps;
    double sequentialWriteMBps;

    double randomReadIOPS;
    double randomWriteIOPS;

    double accessLatencyMs;

    int maximumQueueDepth;

    void validate() const {
        if (name.empty()) {
            throw std::invalid_argument(
                "Device name cannot be empty"
            );
        }

        if (
            sequentialReadMBps <= 0 ||
            sequentialWriteMBps <= 0 ||
            randomReadIOPS <= 0 ||
            randomWriteIOPS <= 0 ||
            accessLatencyMs <= 0 ||
            maximumQueueDepth <= 0
        ) {
            throw std::invalid_argument(
                "Performance values must be positive"
            );
        }

        if (
            !std::isfinite(sequentialReadMBps) ||
            !std::isfinite(sequentialWriteMBps) ||
            !std::isfinite(randomReadIOPS) ||
            !std::isfinite(randomWriteIOPS) ||
            !std::isfinite(accessLatencyMs)
        ) {
            throw std::invalid_argument(
                "Performance values must be finite"
            );
        }
    }
};

struct IORequest {
    std::size_t requestId;
    IOOperation operation;
    std::size_t blockSizeBytes;
    int queueDepth;
};

struct IOResult {
    std::size_t requestId;
    double latencyMs;
    double serviceTimeMs;
    std::size_t bytesTransferred;
};

struct BenchmarkReport {
    std::string device;
    IOOperation operation;

    std::size_t requestCount;
    std::size_t totalBytes;

    double averageLatencyMs;
    double p95LatencyMs;
    double p99LatencyMs;

    double throughputMBps;
    double iops;
};

class StorageEngine {
private:
    StorageDevice device;

    double transferTime(
        std::size_t bytes,
        double bandwidthMBps
    ) const {
        return (
            static_cast<double>(bytes) /
            (bandwidthMBps * 1024.0 * 1024.0)
        ) * 1000.0;
    }

public:
    explicit StorageEngine(StorageDevice storage)
        : device(std::move(storage)) {
        device.validate();
    }

    const StorageDevice& getDevice() const {
        return device;
    }

    double estimateServiceTime(
        IOOperation operation,
        std::size_t bytes
    ) const {
        if (bytes == 0) {
            throw std::invalid_argument(
                "Block size must be positive"
            );
        }

        double serviceTime = device.accessLatencyMs;

        switch (operation) {
            case IOOperation::SEQUENTIAL_READ:
                serviceTime += transferTime(
                    bytes,
                    device.sequentialReadMBps
                );
                break;

            case IOOperation::SEQUENTIAL_WRITE:
                serviceTime += transferTime(
                    bytes,
                    device.sequentialWriteMBps
                );
                break;

            case IOOperation::RANDOM_READ:
                serviceTime += 1000.0 / device.randomReadIOPS;
                break;

            case IOOperation::RANDOM_WRITE:
                serviceTime += 1000.0 / device.randomWriteIOPS;
                break;
        }

        return serviceTime;
    }

    IOResult process(const IORequest& request) const {
        if (request.queueDepth <= 0) {
            throw std::invalid_argument(
                "Queue depth must be positive"
            );
        }

        double serviceTime = estimateServiceTime(
            request.operation,
            request.blockSizeBytes
        );

        /*
         * This is a simplified queue-contention model.
         * It is not a physical NVMe or HDD scheduler.
         */
        double queuePenalty = std::max(
            0,
            request.queueDepth - device.maximumQueueDepth
        ) * serviceTime * 0.08;

        return {
            request.requestId,
            serviceTime + queuePenalty,
            serviceTime,
            request.blockSizeBytes
        };
    }

    static double percentile(
        std::vector<double> values,
        double p
    ) {
        if (values.empty()) {
            throw std::invalid_argument(
                "Cannot calculate percentile of empty data"
            );
        }

        if (p < 0 || p > 1) {
            throw std::invalid_argument(
                "Percentile must be between zero and one"
            );
        }

        std::sort(values.begin(), values.end());

        std::size_t index = static_cast<std::size_t>(
            std::ceil(p * values.size())
        );

        index = std::max(
            static_cast<std::size_t>(1),
            index
        );

        return values[index - 1];
    }

    BenchmarkReport benchmark(
        IOOperation operation,
        std::size_t blockSize,
        std::size_t requestCount,
        int queueDepth
    ) const {
        if (requestCount == 0) {
            throw std::invalid_argument(
                "Request count must be positive"
            );
        }

        if (blockSize == 0 || queueDepth <= 0) {
            throw std::invalid_argument(
                "Invalid benchmark parameters"
            );
        }

        std::vector<double> latencies;

        double totalBytes = 0;
        double totalTimeMs = 0;

        for (
            std::size_t i = 0;
            i < requestCount;
            ++i
        ) {
            IORequest request {
                i + 1,
                operation,
                blockSize,
                queueDepth
            };

            IOResult result = process(request);

            latencies.push_back(result.latencyMs);
            totalBytes += result.bytesTransferred;
            totalTimeMs += result.latencyMs;
        }

        double throughput = (
            totalBytes / (1024.0 * 1024.0)
        ) / (totalTimeMs / 1000.0);

        double iops = requestCount / (totalTimeMs / 1000.0);

        double average = std::accumulate(
            latencies.begin(),
            latencies.end(),
            0.0
        ) / latencies.size();

        return {
            device.name,
            operation,
            requestCount,
            static_cast<std::size_t>(totalBytes),
            average,
            percentile(latencies, 0.95),
            percentile(latencies, 0.99),
            throughput,
            iops
        };
    }
};

class StorageFleet {
private:
    std::vector<StorageEngine> engines;

public:
    void addDevice(const StorageDevice& device) {
        engines.emplace_back(device);
    }

    const std::vector<StorageEngine>& getEngines() const {
        return engines;
    }

    std::vector<BenchmarkReport> evaluate() const {
        const std::vector<IOOperation> operations = {
            IOOperation::SEQUENTIAL_READ,
            IOOperation::RANDOM_READ,
            IOOperation::SEQUENTIAL_WRITE,
            IOOperation::RANDOM_WRITE
        };

        std::vector<BenchmarkReport> reports;

        for (const auto& engine : engines) {
            for (IOOperation operation : operations) {
                std::size_t blockSize =
                    operation == IOOperation::SEQUENTIAL_READ ||
                    operation == IOOperation::SEQUENTIAL_WRITE
                    ? 1024 * 1024
                    : 4096;

                reports.push_back(
                    engine.benchmark(
                        operation,
                        blockSize,
                        1000,
                        8
                    )
                );
            }
        }

        return reports;
    }
};

class PerformancePolicy {
public:
    static std::string classify(
        const BenchmarkReport& report
    ) {
        if (report.p99LatencyMs > 100) {
            return "CRITICAL LATENCY";
        }

        if (report.averageLatencyMs > 20) {
            return "HIGH LATENCY";
        }

        if (report.iops < 100) {
            return "LOW IOPS";
        }

        return "ACCEPTABLE";
    }
};

void printReports(
    const std::vector<BenchmarkReport>& reports
) {
    std::cout << "\nSTORAGE PERFORMANCE ANALYSIS\n";
    std::cout << std::string(112, '=') << "\n";

    std::cout
        << std::left
        << std::setw(23) << "Device"
        << std::setw(21) << "Operation"
        << std::right
        << std::setw(12) << "Avg ms"
        << std::setw(12) << "P95 ms"
        << std::setw(12) << "P99 ms"
        << std::setw(14) << "MB/s"
        << std::setw(14) << "IOPS"
        << "\n";

    std::cout << std::string(112, '-') << "\n";

    for (const auto& report : reports) {
        std::cout
            << std::left
            << std::setw(23) << report.device
            << std::setw(21) << toString(report.operation)
            << std::right
            << std::fixed
            << std::setprecision(3)
            << std::setw(12) << report.averageLatencyMs
            << std::setw(12) << report.p95LatencyMs
            << std::setw(12) << report.p99LatencyMs
            << std::setw(14) << report.throughputMBps
            << std::setw(14) << report.iops
            << "\n";
    }
}

void runTests() {
    StorageDevice testDevice {
        "Test SSD",
        StorageType::SATA_SSD,
        550,
        500,
        90000,
        80000,
        0.08,
        32
    };

    StorageEngine engine(testDevice);

    if (
        engine.estimateServiceTime(
            IOOperation::RANDOM_READ,
            4096
        ) <= 0
    ) {
        throw std::runtime_error(
            "Random I/O calculation failed"
        );
    }

    if (
        engine.estimateServiceTime(
            IOOperation::SEQUENTIAL_READ,
            4096
        ) <= 0
    ) {
        throw std::runtime_error(
            "Sequential I/O calculation failed"
        );
    }

    bool invalidInputRejected = false;

    try {
        engine.estimateServiceTime(
            IOOperation::RANDOM_READ,
            0
        );
    } catch (const std::invalid_argument&) {
        invalidInputRejected = true;
    }

    if (!invalidInputRejected) {
        throw std::runtime_error(
            "Zero-byte request was not rejected"
        );
    }

    std::cout << "All validation tests passed.\n";
}

int main() {
    try {
        runTests();

        StorageFleet fleet;

        fleet.addDevice({
            "Enterprise HDD",
            StorageType::HDD,
            180,
            160,
            120,
            110,
            8.0,
            4
        });

        fleet.addDevice({
            "SATA SSD",
            StorageType::SATA_SSD,
            550,
            500,
            90000,
            80000,
            0.08,
            32
        });

        fleet.addDevice({
            "NVMe SSD",
            StorageType::NVME_SSD,
            3500,
            3000,
            600000,
            500000,
            0.02,
            64
        });

        const auto reports = fleet.evaluate();

        printReports(reports);

        std::cout << "\nPERFORMANCE POLICY EVALUATION\n";
        std::cout << std::string(60, '-') << "\n";

        for (const auto& report : reports) {
            std::cout
                << report.device
                << " | "
                << toString(report.operation)
                << " | "
                << PerformancePolicy::classify(report)
                << "\n";
        }

        std::cout << "\nStorage analysis completed.\n";

    } catch (const std::exception& error) {
        std::cerr
            << "Storage engine error: "
            << error.what()
            << "\n";

        return 1;
    }

    return 0;
}
