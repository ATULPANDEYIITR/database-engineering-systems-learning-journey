#!/usr/bin/env python3
"""
PostgreSQL Data Types: Numeric, Text, Boolean, UUID, JSON, and Arrays.

A self-contained learning implementation for PostgreSQL type selection,
validation, serialization, and realistic application data modeling.

The script uses only the Python standard library. An optional PostgreSQL
connection can be enabled by installing psycopg and setting DATABASE_URL.
"""

from __future__ import annotations

import json
import os
import re
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any


def heading(title: str) -> None:
    print(f"\n{'=' * 72}\n{title}\n{'=' * 72}")


# NUMERIC TYPES

def demonstrate_numeric_types() -> None:
    heading("Numeric types: integer ranges, exact decimals, and floating point")

    integer_examples = {
        "smallint": (-32768, 32767),
        "integer": (-2147483648, 2147483647),
        "bigint": (-9223372036854775808, 9223372036854775807),
    }

    for type_name, bounds in integer_examples.items():
        print(f"{type_name}: range {bounds[0]} through {bounds[1]}")

    # Decimal preserves base-10 precision needed for financial calculations.
    unit_price = Decimal("1499.95")
    quantity = 3
    tax_rate = Decimal("0.18")
    subtotal = unit_price * quantity
    tax = (subtotal * tax_rate).quantize(Decimal("0.01"))
    total = subtotal + tax

    print(f"Subtotal: {subtotal}")
    print(f"Tax:      {tax}")
    print(f"Total:    {total}")

    # Python float uses binary floating-point representation, as does
    # PostgreSQL double precision. It is not an exact decimal-money type.
    print(f"Float arithmetic example: {0.1 + 0.2:.17f}")

    def validate_numeric_precision(
        value: Decimal,
        precision: int,
        scale: int,
    ) -> Decimal:
        """Approximate PostgreSQL NUMERIC(p, s) value constraints."""
        if not value.is_finite():
            raise ValueError("Numeric values must be finite.")

        if precision <= 0 or scale < 0 or scale > precision:
            raise ValueError("Invalid precision or scale.")

        quantum = Decimal(1).scaleb(-scale)
        rounded = value.quantize(quantum)

        # Reject excess fractional precision rather than silently rounding.
        if rounded != value:
            raise ValueError(f"{value} exceeds scale {scale}.")

        integer_digits = max(0, len(str(abs(int(rounded)))) if rounded else 0)
        allowed_integer_digits = precision - scale

        if integer_digits > allowed_integer_digits:
            raise ValueError(f"{value} exceeds NUMERIC({precision}, {scale}).")

        return rounded

    print("NUMERIC(10,2):", validate_numeric_precision(
        Decimal("12345.67"), 10, 2
    ))

    try:
        validate_numeric_precision(Decimal("12.345"), 10, 2)
    except (ValueError, InvalidOperation) as error:
        print("Rejected numeric value:", error)

    # PostgreSQL supports numeric NaN and, in supported versions, infinities.
    # Business applications should define whether such values are acceptable.


# TEXT TYPES

def demonstrate_text_types() -> None:
    heading("Text types: character data, Unicode, and validation")

    product_name = "Industrial Pressure Sensor"
    product_code = "SENSOR-042"
    description = "Measures pressure in bar; suitable for process monitoring."

    print("Product:", product_name)
    print("Code:", product_code)
    print("Description:", description)

    # PostgreSQL text and varchar(n) store variable-length strings.
    # varchar(n) limits characters, not encoded bytes.
    def validate_varchar(value: str, maximum_length: int) -> str:
        if not isinstance(value, str):
            raise TypeError("Expected a string.")
        if len(value) > maximum_length:
            raise ValueError(
                f"Text has {len(value)} characters; maximum is {maximum_length}."
            )
        return value

    print("Validated code:", validate_varchar(product_code, 30))

    try:
        validate_varchar("PRESSURE-SENSOR-INDUSTRIAL-EXTENDED", 12)
    except ValueError as error:
        print("Rejected text:", error)

    unicode_description = "Temperature: 28°C; location: पुणे"
    print("Unicode:", unicode_description)

    # PostgreSQL character(n) pads shorter values with spaces and has
    # different comparison behavior from text and varchar.
    # Prefer text unless a specific length constraint is required.


# BOOLEAN TYPE

def demonstrate_boolean_type() -> None:
    heading("Boolean: true, false, and SQL NULL")

    equipment_status = {
        "sensor-01": True,
        "sensor-02": False,
        "sensor-03": None,
    }

    for equipment_id, is_operational in equipment_status.items():
        print(f"{equipment_id}: {is_operational!r}")

    # Python None corresponds to SQL NULL, not SQL FALSE.
    assert equipment_status["sensor-01"] is True
    assert equipment_status["sensor-02"] is False
    assert equipment_status["sensor-03"] is None

    print("Unknown operational state remains distinct from false.")

    # SQL predicates involving NULL generally produce UNKNOWN.
    # Use IS NULL and IS NOT NULL instead of comparisons with NULL.


# UUID TYPE

def demonstrate_uuid_type() -> None:
    heading("UUID: stable identifiers")

    record_id = uuid.uuid4()
    print("Generated UUID:", record_id)
    print("Canonical text:", str(record_id))
    print("Parsed UUID:", uuid.UUID(str(record_id)))

    deterministic_id = uuid.uuid5(
        uuid.NAMESPACE_URL,
        "https://example.org/equipment/sensor-042",
    )
    print("Deterministic UUID:", deterministic_id)

    # UUID v4 is random; UUID v5 is deterministic for a namespace and name.
    # UUIDs reduce dependence on centrally allocated numeric identifiers,
    # but they do not replace authorization or access-control checks.

    try:
        uuid.UUID("not-a-valid-uuid")
    except ValueError as error:
        print("Invalid UUID rejected:", error)


# JSON AND JSONB TYPES

def demonstrate_json_types() -> None:
    heading("JSON: structured attributes and validation")

    telemetry = {
        "source": "sensor-042",
        "measurement": {
            "pressure_bar": 7.42,
            "temperature_c": 28.6,
        },
        "quality": "verified",
        "tags": ["plant-a", "pressure-line"],
    }

    serialized = json.dumps(telemetry, ensure_ascii=False)
    restored = json.loads(serialized)

    print("Serialized JSON:", serialized)
    print("Pressure:", restored["measurement"]["pressure_bar"])

    def validate_telemetry(document: Any) -> dict[str, Any]:
        if not isinstance(document, dict):
            raise ValueError("Telemetry must be a JSON object.")

        allowed = {"source", "measurement", "quality", "tags"}
        if set(document) - allowed:
            raise ValueError("Unexpected telemetry fields.")

        source = document.get("source")
        measurement = document.get("measurement")
        quality = document.get("quality")
        tags = document.get("tags")

        if not isinstance(source, str) or not source.strip():
            raise ValueError("source must be a non-empty string.")

        if not isinstance(measurement, dict):
            raise ValueError("measurement must be an object.")

        pressure = measurement.get("pressure_bar")
        if (
            isinstance(pressure, bool)
            or not isinstance(pressure, (int, float))
            or pressure < 0
        ):
            raise ValueError("pressure_bar must be a non-negative number.")

        if quality not in {"verified", "estimated", "rejected"}:
            raise ValueError("Unsupported quality state.")

        if not isinstance(tags, list) or not all(
            isinstance(tag, str) for tag in tags
        ):
            raise ValueError("tags must be a list of strings.")

        return document

    print("Validated telemetry:", validate_telemetry(telemetry))

    invalid_telemetry = {
        "source": "sensor-042",
        "measurement": {"pressure_bar": -1},
        "quality": "verified",
        "tags": [],
    }

    try:
        validate_telemetry(invalid_telemetry)
    except ValueError as error:
        print("Invalid telemetry rejected:", error)

    # PostgreSQL JSON preserves input text representation more closely,
    # while JSONB stores a decomposed representation suited to querying
    # and indexing. JSONB does not preserve whitespace or object key order.
    # Application validation remains important for both types.


# ARRAY TYPES

def demonstrate_array_types() -> None:
    heading("Arrays: ordered collections with a single PostgreSQL element type")

    supported_regions = ["north", "south", "west"]
    maintenance_days = [1, 15, 28]
    nullable_measurements = [7.1, None, 7.4]

    print("Regions:", supported_regions)
    print("Maintenance days:", maintenance_days)
    print("Measurements:", nullable_measurements)

    def validate_text_array(values: Any) -> list[str]:
        if not isinstance(values, list):
            raise TypeError("Expected a list.")
        if not all(isinstance(value, str) for value in values):
            raise ValueError("Every element must be text.")
        if len(values) != len(set(values)):
            raise ValueError("Duplicate entries are not permitted.")
        return values

    print("Validated regions:", validate_text_array(supported_regions))

    try:
        validate_text_array(["north", 42])
    except ValueError as error:
        print("Invalid array rejected:", error)

    # PostgreSQL arrays can contain NULL elements and may be multidimensional.
    # Arrays are useful for compact attributes, but frequent membership
    # queries or independently managed elements may warrant a child table.


# APPLICATION DATA MODEL

@dataclass(frozen=True)
class EquipmentRecord:
    equipment_id: uuid.UUID
    serial_number: str
    manufacturer: str
    is_active: bool | None
    pressure_bar: Decimal
    labels: tuple[str, ...]
    metadata: dict[str, Any]
    created_at: datetime

    def validate(self) -> None:
        if not self.serial_number.strip():
            raise ValueError("Serial number cannot be empty.")

        if len(self.serial_number) > 40:
            raise ValueError("Serial number exceeds 40 characters.")

        if not self.manufacturer.strip():
            raise ValueError("Manufacturer cannot be empty.")

        if not self.pressure_bar.is_finite() or self.pressure_bar < 0:
            raise ValueError("Pressure must be finite and non-negative.")

        if len(set(self.labels)) != len(self.labels):
            raise ValueError("Labels must be unique.")

        if not all(isinstance(label, str) for label in self.labels):
            raise ValueError("Every label must be text.")

        if not isinstance(self.metadata, dict):
            raise ValueError("Metadata must be a dictionary.")

        if self.created_at.tzinfo is None:
            raise ValueError("created_at must include a timezone.")


def demonstrate_application_model() -> None:
    heading("Integrated equipment record")

    record = EquipmentRecord(
        equipment_id=uuid.uuid4(),
        serial_number="PS-2026-0042",
        manufacturer="Precision Instruments Ltd.",
        is_active=True,
        pressure_bar=Decimal("7.42"),
        labels=("plant-a", "critical"),
        metadata={
            "calibration": {
                "last_calibrated": "2026-09-15",
                "certificate_valid": True,
            },
            "protocol": "modbus",
        },
        created_at=datetime.now(timezone.utc),
    )

    record.validate()

    document = {
        "equipment_id": str(record.equipment_id),
        "serial_number": record.serial_number,
        "manufacturer": record.manufacturer,
        "is_active": record.is_active,
        "pressure_bar": str(record.pressure_bar),
        "labels": list(record.labels),
        "metadata": record.metadata,
        "created_at": record.created_at.isoformat(),
    }

    print(json.dumps(document, indent=2, ensure_ascii=False))

    # Decimal is serialized as text to avoid losing exact decimal semantics.
    # The database column should remain NUMERIC, not JSON text.


def demonstrate_json_query_semantics() -> None:
    heading("JSON path access and application-level filtering")

    records = [
        {"id": "sensor-01", "metadata": {"protocol": "modbus"}},
        {"id": "sensor-02", "metadata": {"protocol": "mqtt"}},
        {"id": "sensor-03", "metadata": {"protocol": "modbus"}},
    ]

    matching = [
        record["id"]
        for record in records
        if record.get("metadata", {}).get("protocol") == "modbus"
    ]

    print("Devices using Modbus:", matching)

    # PostgreSQL equivalent:
    # SELECT serial_number
    # FROM equipment
    # WHERE metadata ->> 'protocol' = 'modbus';


def demonstrate_safe_sql_parameters() -> None:
    heading("Parameterized SQL: keep values separate from SQL syntax")

    serial_number = "PS-2026-0042' OR TRUE --"

    query = """
        SELECT equipment_id, serial_number
        FROM equipment
        WHERE serial_number = %s
    """

    print("SQL template:", query.strip())
    print("Bound parameter:", serial_number)

    # The query is illustrative until connected to PostgreSQL.
    # With psycopg, pass query and values separately:
    # cursor.execute(query, (serial_number,))
    # Never interpolate untrusted values into SQL strings.


def demonstrate_optional_postgresql_connection() -> None:
    database_url = os.environ.get("DATABASE_URL")

    if not database_url:
        print("\nDATABASE_URL not configured; database execution skipped.")
        return

    try:
        import psycopg
    except ImportError:
        print("Install psycopg to enable database execution.")
        return

    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT version()")
            version = cursor.fetchone()[0]
            print("\nConnected PostgreSQL version:", version)

            cursor.execute("""
                SELECT
                    42::integer,
                    1499.95::numeric(10, 2),
                    'Industrial sensor'::text,
                    TRUE::boolean,
                    gen_random_uuid()::text,
                    '{"protocol":"modbus"}'::jsonb,
                    ARRAY['plant-a', 'critical']::text[]
            """)

            row = cursor.fetchone()
            print("PostgreSQL type demonstration:", row)


def main() -> None:
    demonstrate_numeric_types()
    demonstrate_text_types()
    demonstrate_boolean_type()
    demonstrate_uuid_type()
    demonstrate_json_types()
    demonstrate_array_types()
    demonstrate_application_model()
    demonstrate_json_query_semantics()
    demonstrate_safe_sql_parameters()
    demonstrate_optional_postgresql_connection()


if __name__ == "__main__":
    main()
