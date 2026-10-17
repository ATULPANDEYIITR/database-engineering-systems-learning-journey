"use strict";

/*
 * PostgreSQL data types in a Node.js telemetry ingestion service.
 *
 * Demonstrates type-aware input normalization, JSONB document validation,
 * UUID handling, PostgreSQL arrays, exact numeric transport, parameterized
 * queries, and safe handling of SQL NULL.
 *
 * Run without dependencies:
 *   node postgres_data_types.js
 *
 * Optional database execution:
 *   npm install pg
 *   Set DATABASE_URL before running the script.
 */

const { randomUUID } = require("node:crypto");

function logSection(title) {
    console.log(`\n${"=".repeat(68)}\n${title}\n${"=".repeat(68)}`);
}

function requireString(value, field, maxLength = Infinity) {
    if (typeof value !== "string" || value.trim().length === 0) {
        throw new TypeError(`${field} must be a non-empty string`);
    }

    if ([...value].length > maxLength) {
        throw new RangeError(`${field} exceeds ${maxLength} characters`);
    }

    return value;
}

function requireBooleanOrNull(value, field) {
    if (value !== null && typeof value !== "boolean") {
        throw new TypeError(`${field} must be true, false, or null`);
    }

    return value;
}

function requireUuid(value) {
    if (
        typeof value !== "string" ||
        !/^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value)
    ) {
        throw new TypeError("Invalid UUID representation");
    }

    return value.toLowerCase();
}

/*
 * PostgreSQL NUMERIC values should normally be transferred as decimal strings.
 * JavaScript Number cannot exactly represent every decimal or large integer.
 * This validator checks a NUMERIC(10,2)-style textual representation without
 * converting it to Number.
 */
function validateNumeric10_2(value) {
    if (typeof value !== "string") {
        throw new TypeError("Exact numeric input must be a decimal string");
    }

    if (!/^-?\d+(?:\.\d{1,2})?$/.test(value)) {
        throw new TypeError("Expected a decimal with at most two fractional digits");
    }

    const unsigned = value.startsWith("-") ? value.slice(1) : value;
    const [integerPart] = unsigned.split(".");
    const significantInteger = integerPart.replace(/^0+/, "") || "0";

    // NUMERIC(10,2) permits at most eight integer digits.
    if (significantInteger.length > 8) {
        throw new RangeError("Value exceeds NUMERIC(10,2)");
    }

    return value;
}

function validateTextArray(values, field) {
    if (!Array.isArray(values)) {
        throw new TypeError(`${field} must be an array`);
    }

    for (const value of values) {
        if (typeof value !== "string") {
            throw new TypeError(`${field} can contain only strings`);
        }
    }

    if (new Set(values).size !== values.length) {
        throw new RangeError(`${field} must not contain duplicates`);
    }

    return [...values];
}

function validateTelemetry(input) {
    if (input === null || Array.isArray(input) || typeof input !== "object") {
        throw new TypeError("Telemetry must be a JSON object");
    }

    const allowedKeys = new Set([
        "source",
        "pressure_bar",
        "temperature_c",
        "quality",
        "tags"
    ]);

    for (const key of Object.keys(input)) {
        if (!allowedKeys.has(key)) {
            throw new TypeError(`Unexpected telemetry field: ${key}`);
        }
    }

    const source = requireString(input.source, "source", 80);
    const pressure = input.pressure_bar;

    // JSON numbers arrive as JavaScript Number. Require a finite non-negative
    // value, but use decimal strings when exact precision is essential.
    if (
        typeof pressure !== "number" ||
        !Number.isFinite(pressure) ||
        pressure < 0
    ) {
        throw new TypeError("pressure_bar must be a finite non-negative number");
    }

    const temperature = input.temperature_c;

    if (
        temperature !== undefined &&
        (
            typeof temperature !== "number" ||
            !Number.isFinite(temperature)
        )
    ) {
        throw new TypeError("temperature_c must be finite when supplied");
    }

    const quality = input.quality;

    if (!["verified", "estimated", "rejected"].includes(quality)) {
        throw new TypeError("Unsupported quality value");
    }

    const tags = validateTextArray(input.tags ?? [], "tags");

    return {
        source,
        pressure_bar: pressure,
        ...(temperature === undefined ? {} : { temperature_c: temperature }),
        quality,
        tags
    };
}

function demonstrateScalarTypes() {
    logSection("Scalar type handling");

    const equipment = {
        id: randomUUID(),
        serialNumber: requireString("PS-2026-0042", "serialNumber", 40),
        nominalPressure: validateNumeric10_2("1250.75"),
        active: requireBooleanOrNull(true, "active"),
        inspectionStatus: null
    };

    console.log("UUID:", equipment.id);
    console.log("Text:", equipment.serialNumber);
    console.log("Exact NUMERIC transport:", equipment.nominalPressure);
    console.log("Boolean:", equipment.active);
    console.log("Unknown inspection status:", equipment.inspectionStatus);

    // null represents SQL NULL only when the driver and query context bind it
    // as a database value. JavaScript undefined should not be used as a
    // substitute for a deliberate SQL NULL.
}

function demonstrateJsonbAndArrays() {
    logSection("JSONB payloads and PostgreSQL arrays");

    const payload = validateTelemetry({
        source: "PS-2026-0042",
        pressure_bar: 7.42,
        temperature_c: 28.6,
        quality: "verified",
        tags: ["plant-a", "critical"]
    });

    const jsonDocument = JSON.stringify(payload);
    console.log("JSON payload:", jsonDocument);
    console.log("Tags:", payload.tags);

    const badPayload = {
        source: "sensor-7",
        pressure_bar: -4,
        quality: "verified",
        tags: []
    };

    try {
        validateTelemetry(badPayload);
    } catch (error) {
        console.log("Rejected payload:", error.message);
    }

    try {
        validateTextArray(["plant-a", 42], "tags");
    } catch (error) {
        console.log("Rejected array:", error.message);
    }

    // JSONB is appropriate for variable telemetry attributes. Frequently
    // filtered business properties are often better stored in typed columns.
}

function demonstrateNumericBoundary() {
    logSection("Numeric boundary cases");

    for (const value of ["0", "99999999.99", "-12.50", "100000000.00"]) {
        try {
            console.log(value, "=>", validateNumeric10_2(value));
        } catch (error) {
            console.log(value, "rejected:", error.message);
        }
    }

    console.log("Binary floating point:", 0.1 + 0.2);
    console.log("Exact decimal transport:", "0.1", "+", "0.2");
}

async function optionallyQueryPostgres() {
    if (!process.env.DATABASE_URL) {
        console.log("\nDATABASE_URL absent; PostgreSQL query skipped.");
        return;
    }

    let pg;

    try {
        pg = require("pg");
    } catch {
        console.log("Install the pg package to enable database queries.");
        return;
    }

    const client = new pg.Client({
        connectionString: process.env.DATABASE_URL
    });

    try {
        await client.connect();

        /*
         * $1 through $6 are bound parameters. Values remain separate from
         * executable SQL, preventing input from changing query structure.
         */
        const result = await client.query(
            `SELECT
                $1::uuid AS equipment_id,
                $2::numeric(10,2) AS nominal_pressure,
                $3::text AS serial_number,
                $4::boolean AS active,
                $5::jsonb AS telemetry,
                $6::text[] AS tags`,
            [
                randomUUID(),
                "1250.75",
                "PS-2026-0042",
                true,
                JSON.stringify({
                    protocol: "modbus",
                    calibration: { valid: true }
                }),
                ["plant-a", "critical"]
            ]
        );

        console.log("PostgreSQL typed row:", result.rows[0]);

        // node-postgres commonly returns NUMERIC as a string to preserve
        // precision. UUID and JSONB have their own driver conversion behavior.
        const nullResult = await client.query(
            "SELECT $1::boolean AS active",
            [null]
        );

        console.log("SQL NULL:", nullResult.rows[0].active);
    } finally {
        await client.end();
    }
}

async function main() {
    demonstrateScalarTypes();
    demonstrateJsonbAndArrays();
    demonstrateNumericBoundary();
    await optionallyQueryPostgres();
}

main().catch((error) => {
    console.error("Execution failed:", error.message);
    process.exitCode = 1;
});
