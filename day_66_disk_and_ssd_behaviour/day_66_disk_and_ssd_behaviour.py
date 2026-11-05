#!/usr/bin/env python3
"""
Disk and SSD Behavior
Demonstrates I/O latency, sequential versus random I/O,
HDD versus SSD characteristics, workload simulation, and
storage performance analysis.

Python 3.10+
Standard library only.
"""

from __future__ import annotations

import math
import random
import statistics
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable


class StorageType(Enum):
    HDD = "HDD"
    SATA_SSD = "SATA_SSD"
    NVME_SSD = "NVME_SSD"


class IOType(Enum):
    SEQUENTIAL_READ = "sequential_read"
    RANDOM_READ = "random_read"
    SEQUENTIAL_WRITE = "sequential_write"
    RANDOM_WRITE = "random_write"


@dataclass(frozen=True)
class StorageProfile:
    name: str
    storage_type: StorageType
    sequential_read_mbps: float
    sequential_write_mbps: float
    random_read_iops: float
    random_write_iops: float
    access_latency_ms: float
    queue_depth: int = 1

    def __post_init__(self):
        if not self.name.strip():
            raise ValueError("Storage name cannot be empty")

        values = (
            self.sequential_read_mbps,
            self.sequential_write_mbps,
            self.random_read_iops,
            self.random_write_iops,
            self.access_latency_ms,
        )

        if any(not math.isfinite(v) or v <= 0 for v in values):
            raise ValueError("Performance values must be positive and finite")

        if self.queue_depth < 1:
            raise ValueError("Queue depth must be at least one")


@dataclass
class IOResult:
    operation: IOType
    bytes_transferred: int
    latency_ms: float
    throughput_mbps: float
    completed_at: float


@dataclass
class BenchmarkReport:
    device: str
    operation: IOType
    operations: int
    total_bytes: int
    average_latency_ms: float
    median_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    throughput_mbps: float
    iops: float
    samples: list[float] = field(default_factory=list)


class StorageSimulator:
    """
    Analytical storage simulator.

    Sequential I/O is modeled using transfer bandwidth.
    Random I/O is modeled using IOPS and access latency.

    This estimates device behavior. It does not reproduce
    actual hardware, operating-system caching, or controller
    scheduling.
    """

    def __init__(
        self,
        profile: StorageProfile,
        seed: int = 42,
    ):
        self.profile = profile
        self.random = random.Random(seed)

    def estimate_latency_ms(
        self,
        operation: IOType,
        size_bytes: int,
        queue_depth: int = 1,
    ) -> float:

        if size_bytes <= 0:
            raise ValueError("I/O size must be positive")

        if queue_depth < 1:
            raise ValueError("Queue depth must be positive")

        p = self.profile

        if operation in (
            IOType.SEQUENTIAL_READ,
            IOType.SEQUENTIAL_WRITE,
        ):
            bandwidth = (
                p.sequential_read_mbps
                if operation == IOType.SEQUENTIAL_READ
                else p.sequential_write_mbps
            )

            transfer_time = (
                size_bytes / (bandwidth * 1024 * 1024)
            ) * 1000

            base_latency = p.access_latency_ms + transfer_time

        else:
            iops = (
                p.random_read_iops
                if operation == IOType.RANDOM_READ
                else p.random_write_iops
            )

            service_time = 1000 / iops
            base_latency = p.access_latency_ms + service_time

        # A simplified queue-contention penalty.
        queue_penalty = max(
            0,
            queue_depth - p.queue_depth,
        ) * base_latency * 0.08

        # Small bounded variability to model measurement noise.
        noise = self.random.uniform(-0.05, 0.05)

        return max(
            0.001,
            (base_latency + queue_penalty) * (1 + noise),
        )

    def run_benchmark(
        self,
        operation: IOType,
        block_size: int = 4096,
        operations: int = 1000,
        queue_depth: int = 1,
    ) -> BenchmarkReport:

        if operations <= 0:
            raise ValueError("Operations must be positive")

        if block_size <= 0:
            raise ValueError("Block size must be positive")

        latencies = []

        for _ in range(operations):
            latency = self.estimate_latency_ms(
                operation,
                block_size,
                queue_depth,
            )
            latencies.append(latency)

        total_bytes = operations * block_size
        total_time_ms = sum(latencies)

        throughput = (
            total_bytes / (1024 * 1024)
        ) / (total_time_ms / 1000)

        iops = operations / (total_time_ms / 1000)

        ordered = sorted(latencies)

        def percentile(values: list[float], percentile_value: float):
            index = math.ceil(
                percentile_value * len(values)
            ) - 1
            return values[max(0, index)]

        return BenchmarkReport(
            device=self.profile.name,
            operation=operation,
            operations=operations,
            total_bytes=total_bytes,
            average_latency_ms=statistics.mean(latencies),
            median_latency_ms=statistics.median(latencies),
            p95_latency_ms=percentile(ordered, 0.95),
            p99_latency_ms=percentile(ordered, 0.99),
            throughput_mbps=throughput,
            iops=iops,
            samples=latencies,
        )


def create_storage_profiles() -> list[StorageProfile]:
    return [
        StorageProfile(
            name="7200 RPM Enterprise HDD",
            storage_type=StorageType.HDD,
            sequential_read_mbps=180,
            sequential_write_mbps=160,
            random_read_iops=120,
            random_write_iops=110,
            access_latency_ms=8.0,
            queue_depth=4,
        ),
        StorageProfile(
            name="SATA SSD",
            storage_type=StorageType.SATA_SSD,
            sequential_read_mbps=550,
            sequential_write_mbps=500,
            random_read_iops=90000,
            random_write_iops=80000,
            access_latency_ms=0.08,
            queue_depth=32,
        ),
        StorageProfile(
            name="NVMe SSD",
            storage_type=StorageType.NVME_SSD,
            sequential_read_mbps=3500,
            sequential_write_mbps=3000,
            random_read_iops=600000,
            random_write_iops=500000,
            access_latency_ms=0.02,
            queue_depth=64,
        ),
    ]


def compare_storage_devices():
    profiles = create_storage_profiles()

    operations = [
        IOType.SEQUENTIAL_READ,
        IOType.RANDOM_READ,
        IOType.SEQUENTIAL_WRITE,
        IOType.RANDOM_WRITE,
    ]

    reports = []

    for profile in profiles:
        simulator = StorageSimulator(profile)

        for operation in operations:
            report = simulator.run_benchmark(
                operation=operation,
                block_size=4096,
                operations=2000,
                queue_depth=8,
            )
            reports.append(report)

    return reports


def print_report(reports: Iterable[BenchmarkReport]):
    print("\nDISK AND SSD PERFORMANCE REPORT")
    print("=" * 110)

    print(
        f"{'Device':30} "
        f"{'Workload':20} "
        f"{'Avg ms':>10} "
        f"{'P95 ms':>10} "
        f"{'P99 ms':>10} "
        f"{'MB/s':>12} "
        f"{'IOPS':>12}"
    )

    print("-" * 110)

    for report in reports:
        print(
            f"{report.device[:30]:30} "
            f"{report.operation.value:20} "
            f"{report.average_latency_ms:10.4f} "
            f"{report.p95_latency_ms:10.4f} "
            f"{report.p99_latency_ms:10.4f} "
            f"{report.throughput_mbps:12.2f} "
            f"{report.iops:12.2f}"
        )


def demonstrate_io_calculations():
    print("\nBASIC I/O CALCULATIONS")
    print("=" * 60)

    file_size_mb = 1024
    transfer_speed_mbps = 500

    transfer_time = file_size_mb / transfer_speed_mbps

    print(f"File size: {file_size_mb} MB")
    print(f"Transfer speed: {transfer_speed_mbps} MB/s")
    print(f"Estimated transfer time: {transfer_time:.2f} seconds")

    iops = 100000
    block_size = 4096

    throughput = (
        iops * block_size
    ) / (1024 * 1024)

    print(f"\nRandom IOPS: {iops}")
    print(f"Block size: {block_size} bytes")
    print(f"Estimated throughput: {throughput:.2f} MB/s")


def analyze_workload(
    report: BenchmarkReport,
    latency_threshold_ms: float = 10.0,
) -> str:

    if latency_threshold_ms <= 0:
        raise ValueError("Threshold must be positive")

    if report.p95_latency_ms > latency_threshold_ms:
        return "HIGH LATENCY: Investigate storage performance"

    if report.iops < 100:
        return "LOW IOPS: Random I/O performance is limited"

    return "WITHIN CONFIGURED PERFORMANCE THRESHOLD"


def demonstrate_real_file_io():
    """
    Measures actual buffered file operations.

    This is an educational microbenchmark, not a device-level
    benchmark. Results can be affected by page cache, filesystem,
    background activity, and hardware write caching.
    """

    import os
    import tempfile

    print("\nREAL FILE I/O MICROBENCHMARK")
    print("=" * 60)

    block_size = 1024 * 1024
    blocks = 16

    data = os.urandom(block_size)

    with tempfile.TemporaryDirectory() as directory:
        path = os.path.join(directory, "io_test.bin")

        start = time.perf_counter()

        with open(path, "wb", buffering=0) as file:
            for _ in range(blocks):
                file.write(data)

        write_time = time.perf_counter() - start

        start = time.perf_counter()

        with open(path, "rb", buffering=0) as file:
            while file.read(block_size):
                pass

        read_time = time.perf_counter() - start

        total_mb = blocks * block_size / (1024 * 1024)

        print(f"Transferred: {total_mb:.2f} MB")
        print(
            f"Write throughput: "
            f"{total_mb / max(write_time, 1e-9):.2f} MB/s"
        )
        print(
            f"Read throughput: "
            f"{total_mb / max(read_time, 1e-9):.2f} MB/s"
        )


def run_tests():
    profile = StorageProfile(
        name="Test SSD",
        storage_type=StorageType.SATA_SSD,
        sequential_read_mbps=550,
        sequential_write_mbps=500,
        random_read_iops=90000,
        random_write_iops=80000,
        access_latency_ms=0.08,
    )

    simulator = StorageSimulator(profile)

    assert simulator.estimate_latency_ms(
        IOType.SEQUENTIAL_READ,
        4096,
    ) > 0

    assert simulator.estimate_latency_ms(
        IOType.RANDOM_READ,
        4096,
    ) > 0

    report = simulator.run_benchmark(
        IOType.RANDOM_READ,
        operations=100,
    )

    assert report.operations == 100
    assert report.total_bytes == 409600
    assert report.iops > 0
    assert report.p99_latency_ms >= report.p95_latency_ms

    try:
        simulator.run_benchmark(
            IOType.RANDOM_READ,
            operations=0,
        )
        raise AssertionError("Invalid operation count was accepted")
    except ValueError:
        pass

    print("\nAll validation tests passed.")


def main():
    run_tests()
    demonstrate_io_calculations()

    reports = compare_storage_devices()
    print_report(reports)

    print("\nPERFORMANCE INTERPRETATION")
    print("=" * 60)

    for report in reports:
        print(
            f"{report.device} | "
            f"{report.operation.value}: "
            f"{analyze_workload(report)}"
        )

    demonstrate_real_file_io()


if __name__ == "__main__":
    main()
