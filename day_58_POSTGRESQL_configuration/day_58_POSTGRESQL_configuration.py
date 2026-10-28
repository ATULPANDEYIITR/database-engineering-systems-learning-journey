#!/usr/bin/env python3
"""
PostgreSQL configuration simulator.

Models configuration files, memory settings, connection settings, validation,
reload/restart requirements, effective settings, and safe configuration changes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, Iterable, Optional
import argparse
import json
import re
import tempfile


class ApplyMode(Enum):
    RELOAD = "reload"
    RESTART = "restart"


class SettingScope(Enum):
    MEMORY = "memory"
    CONNECTION = "connection"
    GENERAL = "general"


@dataclass(frozen=True)
class SettingDefinition:
    name: str
    default: str
    scope: SettingScope
    minimum: Optional[int] = None
    maximum: Optional[int] = None
    requires_restart: bool = False
    description: str = ""

    def validate(self, value: str) -> None:
        if self.minimum is None and self.maximum is None:
            if not value.strip():
                raise ValueError(f"{self.name}: value cannot be empty")
            return

        number = parse_size_or_integer(value)
        if self.minimum is not None and number < self.minimum:
            raise ValueError(
                f"{self.name}: {number} is below minimum {self.minimum}"
            )
        if self.maximum is not None and number > self.maximum:
            raise ValueError(
                f"{self.name}: {number} exceeds maximum {self.maximum}"
            )


def parse_size_or_integer(value: str) -> int:
    value = value.strip().lower()
    match = re.fullmatch(r"(\d+)\s*(kb|mb|gb)?", value)
    if not match:
        raise ValueError(f"Invalid numeric setting: {value}")

    number = int(match.group(1))
    unit = match.group(2)
    multiplier = {"kb": 1024, "mb": 1024**2, "gb": 1024**3}
    return number * multiplier.get(unit, 1)


SETTING_DEFINITIONS: Dict[str, SettingDefinition] = {
    "max_connections": SettingDefinition(
        "max_connections", "100", SettingScope.CONNECTION,
        minimum=10, maximum=10000,
        description="Maximum concurrent client connections."
    ),
    "shared_buffers": SettingDefinition(
        "shared_buffers", "128MB", SettingScope.MEMORY,
        minimum=16 * 1024**2, maximum=1024 * 1024**3,
        requires_restart=True,
        description="Shared memory allocated to PostgreSQL buffers."
    ),
    "work_mem": SettingDefinition(
        "work_mem", "4MB", SettingScope.MEMORY,
        minimum=64 * 1024, maximum=1024 * 1024**2,
        description="Memory available for an individual query operation."
    ),
    "maintenance_work_mem": SettingDefinition(
        "maintenance_work_mem", "64MB", SettingScope.MEMORY,
        minimum=1024**2, maximum=2048 * 1024**2,
        description="Memory used by maintenance operations."
    ),
    "effective_cache_size": SettingDefinition(
        "effective_cache_size", "4GB", SettingScope.MEMORY,
        minimum=128 * 1024**2, maximum=4096 * 1024**3,
        description="Planner estimate of available filesystem cache."
    ),
    "statement_timeout": SettingDefinition(
        "statement_timeout", "0", SettingScope.CONNECTION,
        minimum=0, maximum=24 * 60 * 60 * 1000,
        description="Maximum statement execution time in milliseconds."
    ),
    "idle_in_transaction_session_timeout": SettingDefinition(
        "idle_in_transaction_session_timeout", "0", SettingScope.CONNECTION,
        minimum=0, maximum=24 * 60 * 60 * 1000,
        description="Maximum idle time inside an open transaction."
    ),
    "log_min_duration_statement": SettingDefinition(
        "log_min_duration_statement", "-1", SettingScope.GENERAL,
        minimum=-1, maximum=24 * 60 * 60 * 1000,
        description="Log statements exceeding the configured duration."
    ),
    "listen_addresses": SettingDefinition(
        "listen_addresses", "localhost", SettingScope.CONNECTION,
        description="Network addresses on which the server listens."
    ),
    "port": SettingDefinition(
        "port", "5432", SettingScope.CONNECTION,
        minimum=1, maximum=65535,
        requires_restart=True,
        description="TCP listening port."
    ),
}


@dataclass
class ConfigFile:
    path: Path
    values: Dict[str, str] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> "ConfigFile":
        values: Dict[str, str] = {}
        if not path.exists():
            return cls(path, values)

        for line_number, raw in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                raise ValueError(f"Invalid configuration at line {line_number}")
            name, value = line.split("=", 1)
            name = name.strip()
            value = value.strip()
            if name not in SETTING_DEFINITIONS:
                raise ValueError(
                    f"Unsupported setting {name!r} at line {line_number}"
                )
            SETTING_DEFINITIONS[name].validate(value)
            values[name] = value

        return cls(path, values)

    def save(self) -> None:
        lines = [
            "# PostgreSQL configuration generated by the configuration simulator",
            "# Values are validated before writing.",
            "",
        ]
        for name in sorted(self.values):
            lines.append(f"{name} = {self.values[name]}")
        self.path.write_text("\n".join(lines) + "\n", encoding="utf-8")


@dataclass
class PostgreSQLConfig:
    defaults: Dict[str, str]
    file_values: Dict[str, str] = field(default_factory=dict)
    session_values: Dict[str, str] = field(default_factory=dict)
    pending_restart: set[str] = field(default_factory=set)

    @classmethod
    def create_default(cls) -> "PostgreSQLConfig":
        defaults = {
            name: definition.default
            for name, definition in SETTING_DEFINITIONS.items()
        }
        return cls(defaults)

    def effective(self, name: str) -> str:
        if name not in SETTING_DEFINITIONS:
            raise KeyError(f"Unknown PostgreSQL setting: {name}")
        return self.session_values.get(
            name,
            self.file_values.get(name, self.defaults[name])
        )

    def set_file_value(self, name: str, value: str) -> ApplyMode:
        definition = SETTING_DEFINITIONS.get(name)
        if definition is None:
            raise KeyError(f"Unknown PostgreSQL setting: {name}")

        definition.validate(value)
        self.file_values[name] = value

        if definition.requires_restart:
            self.pending_restart.add(name)
            return ApplyMode.RESTART

        return ApplyMode.RELOAD

    def set_session_value(self, name: str, value: str) -> None:
        definition = SETTING_DEFINITIONS.get(name)
        if definition is None:
            raise KeyError(f"Unknown PostgreSQL setting: {name}")
        definition.validate(value)
        self.session_values[name] = value

    def reload(self) -> None:
        self.pending_restart = {
            name for name in self.pending_restart
            if SETTING_DEFINITIONS[name].requires_restart
        }

    def restart(self) -> None:
        self.pending_restart.clear()

    def report(self) -> list[dict]:
        report = []
        for name, definition in SETTING_DEFINITIONS.items():
            report.append({
                "name": name,
                "scope": definition.scope.value,
                "default": definition.default,
                "file_value": self.file_values.get(name),
                "session_value": self.session_values.get(name),
                "effective": self.effective(name),
                "restart_required": definition.requires_restart,
                "pending_restart": name in self.pending_restart,
            })
        return report


def validate_configuration(config: PostgreSQLConfig) -> list[str]:
    errors: list[str] = []

    try:
        max_connections = int(
            parse_size_or_integer(config.effective("max_connections"))
        )
        shared_buffers = parse_size_or_integer(
            config.effective("shared_buffers")
        )
        work_mem = parse_size_or_integer(config.effective("work_mem"))

        # This is deliberately a conservative safety check. work_mem is per
        # operation and can be consumed by multiple operations per session.
        estimated_memory = max_connections * work_mem
        if estimated_memory > shared_buffers * 4:
            errors.append(
                "Potential memory pressure: "
                f"max_connections * work_mem = {estimated_memory:,} bytes "
                f"while shared_buffers * 4 = {shared_buffers * 4:,} bytes."
            )

        if max_connections > 2000:
            errors.append(
                "Very high max_connections detected; consider connection "
                "pooling instead of creating thousands of server backends."
            )
    except ValueError as exc:
        errors.append(str(exc))

    return errors


def demonstrate() -> None:
    config = PostgreSQLConfig.create_default()

    print("Initial effective settings")
    print(json.dumps(config.report(), indent=2))

    print("\nApplying production-oriented settings")
    changes = {
        "shared_buffers": "512MB",
        "work_mem": "8MB",
        "maintenance_work_mem": "128MB",
        "effective_cache_size": "4GB",
        "max_connections": "200",
        "statement_timeout": "30000",
        "idle_in_transaction_session_timeout": "60000",
        "log_min_duration_statement": "1000",
    }

    for name, value in changes.items():
        mode = config.set_file_value(name, value)
        print(f"{name}={value}: requires {mode.value}")

    errors = validate_configuration(config)
    if errors:
        print("\nConfiguration warnings/errors:")
        for error in errors:
            print(f"- {error}")
    else:
        print("\nConfiguration validation passed.")

    print("\nPending restart settings:")
    print(sorted(config.pending_restart))

    config.reload()
    print("Reload completed.")
    print("Still pending restart:", sorted(config.pending_restart))

    config.restart()
    print("Restart completed.")
    print("Still pending restart:", sorted(config.pending_restart))

    # Session settings override file settings for that session.
    config.set_session_value("work_mem", "16MB")
    print("\nSession-specific work_mem:", config.effective("work_mem"))
    print("Persistent file work_mem:", config.file_values["work_mem"])

    # Demonstrate configuration-file persistence without modifying a real
    # PostgreSQL installation.
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "postgresql.conf"
        file_config = ConfigFile(path, {
            "max_connections": "200",
            "shared_buffers": "512MB",
            "work_mem": "8MB",
            "statement_timeout": "30000",
        })
        file_config.save()

        loaded = ConfigFile.load(path)
        print("\nGenerated configuration file:")
        print(path.read_text(encoding="utf-8"))
        assert loaded.values == file_config.values

    # Security-focused validation.
    config.set_file_value("listen_addresses", "localhost")
    if config.effective("listen_addresses") == "*":
        raise RuntimeError(
            "Refusing an unrestricted listener without an explicit network policy."
        )

    print("Security validation passed: listener is restricted.")


def inspect_file(path: Path) -> None:
    config_file = ConfigFile.load(path)
    print(json.dumps(config_file.values, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="PostgreSQL configuration and memory/connection simulator"
    )
    parser.add_argument(
        "--inspect",
        type=Path,
        help="Validate and inspect a PostgreSQL-style configuration file"
    )
    args = parser.parse_args()

    if args.inspect:
        inspect_file(args.inspect)
    else:
        demonstrate()


if __name__ == "__main__":
    main()
