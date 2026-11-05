import java.util.ArrayList;
import java.util.Comparator;
import java.util.EnumMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.UUID;
import java.util.stream.Collectors;

/*
 * Disk and SSD Behavior
 *
 * Enterprise storage performance monitoring application.
 *
 * Features:
 * - Storage device inventory
 * - Sequential and random I/O models
 * - Workload telemetry
 * - Latency percentiles
 * - Performance policies
 * - Queue-depth validation
 * - Enterprise service-level evaluation
 *
 * Java 17, standard library only.
 */

public class DiskSSDBehavior {

    enum StorageType {
        HDD,
        SATA_SSD,
        NVME_SSD
    }

    enum IOOperation {
        SEQUENTIAL_READ,
        RANDOM_READ,
        SEQUENTIAL_WRITE,
        RANDOM_WRITE
    }

    enum DeviceStatus {
        ACTIVE,
        DEGRADED,
        MAINTENANCE,
        FAILED
    }

    enum PolicyDecision {
        PASS,
        WARNING,
        CRITICAL,
        REJECTED
    }

    static class StorageException extends RuntimeException {
        StorageException(String message) {
            super(message);
        }
    }

    record StorageSpecification(
        String name,
        StorageType type,
        double sequentialReadMBps,
        double sequentialWriteMBps,
        double randomReadIOPS,
        double randomWriteIOPS,
        double accessLatencyMs,
        int maximumQueueDepth
    ) {
        StorageSpecification {
            if (name == null || name.isBlank()) {
                throw new StorageException(
                    "Storage name is required"
                );
            }

            Objects.requireNonNull(type);

            double[] values = {
                sequentialReadMBps,
                sequentialWriteMBps,
                randomReadIOPS,
                randomWriteIOPS,
                accessLatencyMs
            };

            for (double value : values) {
                if (!Double.isFinite(value) || value <= 0) {
                    throw new StorageException(
                        "Storage performance values must be positive"
                    );
                }
            }

            if (maximumQueueDepth <= 0) {
                throw new StorageException(
                    "Queue depth must be positive"
                );
            }
        }
    }

    record IORequest(
        UUID requestId,
        UUID deviceId,
        IOOperation operation,
        long blockSizeBytes,
        int queueDepth,
        String application
    ) {
        IORequest {
            Objects.requireNonNull(requestId);
            Objects.requireNonNull(deviceId);
            Objects.requireNonNull(operation);

            if (blockSizeBytes <= 0) {
                throw new StorageException(
                    "Block size must be positive"
                );
            }

            if (queueDepth <= 0) {
                throw new StorageException(
                    "Queue depth must be positive"
                );
            }

            if (application == null || application.isBlank()) {
                throw new StorageException(
                    "Application name is required"
                );
            }
        }
    }

    record IOObservation(
        UUID requestId,
        UUID deviceId,
        IOOperation operation,
        long bytes,
        double latencyMs,
        double serviceTimeMs,
        String application
    ) {}

    record PerformancePolicy(
        String policyName,
        double maximumAverageLatencyMs,
        double maximumP99LatencyMs,
        double minimumIOPS
    ) {
        PerformancePolicy {
            if (
                policyName == null ||
                policyName.isBlank() ||
                maximumAverageLatencyMs <= 0 ||
                maximumP99LatencyMs <= 0 ||
                minimumIOPS <= 0
            ) {
                throw new StorageException(
                    "Invalid performance policy"
                );
            }
        }
    }

    record PolicyResult(
        PolicyDecision decision,
        List<String> violations
    ) {
        PolicyResult {
            violations = List.copyOf(violations);
        }
    }

    static class StorageAsset {
        private final UUID id;
        private final StorageSpecification specification;
        private DeviceStatus status;

        StorageAsset(StorageSpecification specification) {
            this.id = UUID.randomUUID();
            this.specification = Objects.requireNonNull(
                specification
            );
            this.status = DeviceStatus.ACTIVE;
        }

        UUID id() {
            return id;
        }

        StorageSpecification specification() {
            return specification;
        }

        DeviceStatus status() {
            return status;
        }

        void changeStatus(DeviceStatus newStatus) {
            Objects.requireNonNull(newStatus);

            if (status == DeviceStatus.FAILED &&
                newStatus == DeviceStatus.ACTIVE) {
                throw new StorageException(
                    "Failed device requires recovery approval"
                );
            }

            status = newStatus;
        }
    }

    static class StorageRegistry {
        private final Map<UUID, StorageAsset> devices =
            new java.util.HashMap<>();

        void register(StorageAsset asset) {
            Objects.requireNonNull(asset);

            if (devices.putIfAbsent(asset.id(), asset) != null) {
                throw new StorageException(
                    "Duplicate storage registration"
                );
            }
        }

        StorageAsset get(UUID id) {
            StorageAsset asset = devices.get(id);

            if (asset == null) {
                throw new StorageException(
                    "Storage device not found"
                );
            }

            return asset;
        }

        List<StorageAsset> activeDevices() {
            return devices.values()
                .stream()
                .filter(
                    asset -> asset.status() == DeviceStatus.ACTIVE
                )
                .toList();
        }
    }

    static class StorageService {

        private final StorageRegistry registry;

        StorageService(StorageRegistry registry) {
            this.registry = registry;
        }

        double calculateServiceTime(
            StorageSpecification specification,
            IOOperation operation,
            long bytes
        ) {
            if (bytes <= 0) {
                throw new StorageException(
                    "Invalid block size"
                );
            }

            double latency = specification.accessLatencyMs();

            return switch (operation) {
                case SEQUENTIAL_READ ->
                    latency + bytes /
                        (specification.sequentialReadMBps()
                            * 1024.0 * 1024.0) * 1000.0;

                case SEQUENTIAL_WRITE ->
                    latency + bytes /
                        (specification.sequentialWriteMBps()
                            * 1024.0 * 1024.0) * 1000.0;

                case RANDOM_READ ->
                    latency + 1000.0 /
                        specification.randomReadIOPS();

                case RANDOM_WRITE ->
                    latency + 1000.0 /
                        specification.randomWriteIOPS();
            };
        }

        IOObservation execute(IORequest request) {
            StorageAsset asset = registry.get(request.deviceId());

            if (asset.status() != DeviceStatus.ACTIVE) {
                throw new StorageException(
                    "Device is not available for I/O"
                );
            }

            StorageSpecification spec = asset.specification();

            double serviceTime = calculateServiceTime(
                spec,
                request.operation(),
                request.blockSizeBytes()
            );

            int excessQueue = Math.max(
                0,
                request.queueDepth() - spec.maximumQueueDepth()
            );

            double queuePenalty =
                excessQueue * serviceTime * 0.08;

            double estimatedLatency =
                serviceTime + queuePenalty;

            return new IOObservation(
                request.requestId(),
                request.deviceId(),
                request.operation(),
                request.blockSizeBytes(),
                estimatedLatency,
                serviceTime,
                request.application()
            );
        }
    }

    static class TelemetryRepository {

        private final Map<UUID, List<IOObservation>> observations =
            new java.util.HashMap<>();

        void save(IOObservation observation) {
            observations.computeIfAbsent(
                observation.deviceId(),
                key -> new ArrayList<>()
            ).add(observation);
        }

        List<IOObservation> findByDevice(UUID deviceId) {
            return List.copyOf(
                observations.getOrDefault(
                    deviceId,
                    List.of()
                )
            );
        }

        List<IOObservation> findByOperation(
            UUID deviceId,
            IOOperation operation
        ) {
            return findByDevice(deviceId)
                .stream()
                .filter(
                    observation ->
                        observation.operation() == operation
                )
                .toList();
        }
    }

    record BenchmarkMetrics(
        int requestCount,
        double averageLatencyMs,
        double p95LatencyMs,
        double p99LatencyMs,
        double throughputMBps,
        double iops
    ) {}

    static class AnalyticsService {

        private double percentile(
            List<Double> values,
            double p
        ) {
            if (values.isEmpty()) {
                throw new StorageException(
                    "No observations available"
                );
            }

            List<Double> sorted = values.stream()
                .sorted()
                .toList();

            int index = Math.max(
                0,
                (int) Math.ceil(p * sorted.size()) - 1
            );

            return sorted.get(index);
        }

        BenchmarkMetrics calculate(
            List<IOObservation> observations
        ) {
            if (observations.isEmpty()) {
                throw new StorageException(
                    "Cannot analyze an empty workload"
                );
            }

            List<Double> latencies = observations.stream()
                .map(IOObservation::latencyMs)
                .toList();

            double totalLatency = latencies.stream()
                .mapToDouble(Double::doubleValue)
                .sum();

            long totalBytes = observations.stream()
                .mapToLong(IOObservation::bytes)
                .sum();

            double average = totalLatency / observations.size();

            double throughput = (
                totalBytes / (1024.0 * 1024.0)
            ) / (totalLatency / 1000.0);

            double iops =
                observations.size() / (totalLatency / 1000.0);

            return new BenchmarkMetrics(
                observations.size(),
                average,
                percentile(latencies, 0.95),
                percentile(latencies, 0.99),
                throughput,
                iops
            );
        }
    }

    static class PolicyEngine {

        PolicyResult evaluate(
            BenchmarkMetrics metrics,
            PerformancePolicy policy
        ) {
            List<String> violations = new ArrayList<>();

            if (
                metrics.averageLatencyMs() >
                policy.maximumAverageLatencyMs()
            ) {
                violations.add(
                    "Average latency exceeds the configured limit"
                );
            }

            if (
                metrics.p99LatencyMs() >
                policy.maximumP99LatencyMs()
            ) {
                violations.add(
                    "P99 latency exceeds the configured limit"
                );
            }

            if (metrics.iops() < policy.minimumIOPS()) {
                violations.add(
                    "IOPS is below the configured minimum"
                );
            }

            PolicyDecision decision;

            if (violations.isEmpty()) {
                decision = PolicyDecision.PASS;
            } else if (
                metrics.p99LatencyMs() >
                policy.maximumP99LatencyMs() * 2
            ) {
                decision = PolicyDecision.CRITICAL;
            } else {
                decision = PolicyDecision.WARNING;
            }

            return new PolicyResult(decision, violations);
        }
    }

    static class WorkloadService {

        private final StorageService storageService;
        private final TelemetryRepository repository;

        WorkloadService(
            StorageService storageService,
            TelemetryRepository repository
        ) {
            this.storageService = storageService;
            this.repository = repository;
        }

        List<IOObservation> executeWorkload(
            UUID deviceId,
            String application,
            IOOperation operation,
            long blockSize,
            int requestCount,
            int queueDepth
        ) {
            if (requestCount <= 0) {
                throw new StorageException(
                    "Request count must be positive"
                );
            }

            List<IOObservation> results = new ArrayList<>();

            for (int i = 0; i < requestCount; i++) {
                IORequest request = new IORequest(
                    UUID.randomUUID(),
                    deviceId,
                    operation,
                    blockSize,
                    queueDepth,
                    application
                );

                IOObservation observation =
                    storageService.execute(request);

                repository.save(observation);
                results.add(observation);
            }

            return List.copyOf(results);
        }
    }

    static void printMetrics(
        String device,
        IOOperation operation,
        BenchmarkMetrics metrics,
        PolicyResult result
    ) {
        System.out.println("\nDevice: " + device);
        System.out.println("Operation: " + operation);
        System.out.println("Requests: " + metrics.requestCount());

        System.out.printf(
            "Average latency: %.4f ms%n",
            metrics.averageLatencyMs()
        );

        System.out.printf(
            "P95 latency: %.4f ms%n",
            metrics.p95LatencyMs()
        );

        System.out.printf(
            "P99 latency: %.4f ms%n",
            metrics.p99LatencyMs()
        );

        System.out.printf(
            "Throughput: %.2f MB/s%n",
            metrics.throughputMBps()
        );

        System.out.printf(
            "IOPS: %.2f%n",
            metrics.iops()
        );

        System.out.println(
            "Policy decision: " + result.decision()
        );

        result.violations().forEach(
            violation -> System.out.println(
                "Violation: " + violation
            )
        );
    }

    static void runTests() {
        StorageSpecification spec = new StorageSpecification(
            "Test SSD",
            StorageType.SATA_SSD,
            550,
            500,
            90000,
            80000,
            0.08,
            32
        );

        StorageAsset asset = new StorageAsset(spec);

        StorageRegistry registry = new StorageRegistry();
        registry.register(asset);

        StorageService service = new StorageService(registry);

        IORequest request = new IORequest(
            UUID.randomUUID(),
            asset.id(),
            IOOperation.RANDOM_READ,
            4096,
            4,
            "TestApplication"
        );

        IOObservation observation = service.execute(request);

        if (observation.latencyMs() <= 0) {
            throw new StorageException(
                "Latency validation failed"
            );
        }

        boolean rejected = false;

        try {
            new IORequest(
                UUID.randomUUID(),
                asset.id(),
                IOOperation.RANDOM_READ,
                0,
                4,
                "TestApplication"
            );
        } catch (StorageException exception) {
            rejected = true;
        }

        if (!rejected) {
            throw new StorageException(
                "Invalid request was accepted"
            );
        }

        asset.changeStatus(DeviceStatus.FAILED);

        rejected = false;

        try {
            asset.changeStatus(DeviceStatus.ACTIVE);
        } catch (StorageException exception) {
            rejected = true;
        }

        if (!rejected) {
            throw new StorageException(
                "Invalid device recovery was accepted"
            );
        }

        System.out.println("All enterprise validation tests passed.");
    }

    public static void main(String[] args) {

        try {
            runTests();

            StorageRegistry registry = new StorageRegistry();

            StorageAsset hdd = new StorageAsset(
                new StorageSpecification(
                    "Enterprise HDD",
                    StorageType.HDD,
                    180,
                    160,
                    120,
                    110,
                    8.0,
                    4
                )
            );

            StorageAsset sata = new StorageAsset(
                new StorageSpecification(
                    "SATA SSD",
                    StorageType.SATA_SSD,
                    550,
                    500,
                    90000,
                    80000,
                    0.08,
                    32
                )
            );

            StorageAsset nvme = new StorageAsset(
                new StorageSpecification(
                    "NVMe SSD",
                    StorageType.NVME_SSD,
                    3500,
                    3000,
                    600000,
                    500000,
                    0.02,
                    64
                )
            );

            registry.register(hdd);
            registry.register(sata);
            registry.register(nvme);

            StorageService storageService =
                new StorageService(registry);

            TelemetryRepository repository =
                new TelemetryRepository();

            WorkloadService workloadService =
                new WorkloadService(
                    storageService,
                    repository
                );

            AnalyticsService analytics =
                new AnalyticsService();

            PolicyEngine policyEngine = new PolicyEngine();

            PerformancePolicy policy = new PerformancePolicy(
                "Enterprise Storage SLA",
                20.0,
                100.0,
                100.0
            );

            List<StorageAsset> devices =
                registry.activeDevices();

            for (StorageAsset device : devices) {
                for (IOOperation operation : IOOperation.values()) {

                    long blockSize =
                        operation == IOOperation.SEQUENTIAL_READ ||
                        operation == IOOperation.SEQUENTIAL_WRITE
                        ? 1024 * 1024
                        : 4096;

                    List<IOObservation> workload =
                        workloadService.executeWorkload(
                            device.id(),
                            "DatabaseService",
                            operation,
                            blockSize,
                            1000,
                            8
                        );

                    BenchmarkMetrics metrics =
                        analytics.calculate(workload);

                    PolicyResult decision =
                        policyEngine.evaluate(metrics, policy);

                    printMetrics(
                        device.specification().name(),
                        operation,
                        metrics,
                        decision
                    );
                }
            }

            System.out.println(
                "\nEnterprise storage evaluation completed."
            );

        } catch (StorageException exception) {
            System.err.println(
                "Storage workflow rejected: " +
                exception.getMessage()
            );

            System.exitCode = 1;
        }
    }
}
