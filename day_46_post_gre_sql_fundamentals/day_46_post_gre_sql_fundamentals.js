"use strict";

/*
 * PostgreSQL Fundamentals: interactive command-line laboratory.
 *
 * This Node.js program models database and schema discovery, interprets
 * a small set of psql-style commands, validates connection parameters,
 * and optionally queries a real PostgreSQL server through the psql executable.
 *
 * Run:
 *   node postgres_fundamentals.js
 *   node postgres_fundamentals.js --real --database postgres --user postgres
 */

const { spawn } = require("node:child_process");
const readline = require("node:readline");
const { once } = require("node:events");

class Schema {
    constructor(name) {
        this.name = name;
        this.tables = new Map();
    }

    addTable(name, columns) {
        if (this.tables.has(name)) {
            throw new Error(`Relation "${this.name}.${name}" already exists`);
        }
        this.tables.set(name, { name, columns: [...columns], rows: [] });
    }
}

class Database {
    constructor(name, owner) {
        this.name = name;
        this.owner = owner;
        this.schemas = new Map();
        this.schemas.set("public", new Schema("public"));
        this.schemas.set("operations", new Schema("operations"));
    }

    createSchema(name) {
        validateIdentifier(name);
        if (this.schemas.has(name)) {
            throw new Error(`Schema "${name}" already exists`);
        }
        this.schemas.set(name, new Schema(name));
    }

    createTable(schemaName, tableName, columns) {
        const schema = this.schemas.get(schemaName);
        if (!schema) {
            throw new Error(`Schema "${schemaName}" does not exist`);
        }
        schema.addTable(tableName, columns);
    }

    resolveRelation(name, searchPath) {
        if (name.includes(".")) {
            const [schemaName, relationName, ...extra] = name.split(".");
            if (extra.length || !schemaName || !relationName) {
                throw new Error(`Invalid qualified relation: ${name}`);
            }
            const schema = this.schemas.get(schemaName);
            const relation = schema?.tables.get(relationName);
            if (!relation) {
                throw new Error(`Relation "${name}" does not exist`);
            }
            return relation;
        }

        for (const schemaName of searchPath) {
            const relation = this.schemas.get(schemaName)?.tables.get(name);
            if (relation) return relation;
        }
        throw new Error(`Relation "${name}" was not found in search_path`);
    }
}

class Cluster {
    constructor() {
        this.roles = new Set(["postgres", "operations_owner", "report_reader"]);
        this.databases = new Map();
        this.databases.set("postgres", new Database("postgres", "postgres"));
        this.databases.set(
            "plant_operations",
            new Database("plant_operations", "operations_owner")
        );
    }

    listDatabases() {
        return [...this.databases.values()]
            .map(({ name, owner }) => ({ name, owner }))
            .sort((a, b) => a.name.localeCompare(b.name));
    }
}

function validateIdentifier(identifier) {
    // The simulation intentionally supports unquoted identifiers only.
    if (!/^[A-Za-z_][A-Za-z0-9_]*$/.test(identifier)) {
        throw new Error(`Invalid unquoted PostgreSQL identifier: ${identifier}`);
    }
}

function parseConnectionOptions(args) {
    const options = {
        host: process.env.PGHOST || "localhost",
        port: Number(process.env.PGPORT || 5432),
        database: process.env.PGDATABASE || "postgres",
        user: process.env.PGUSER || "postgres",
        real: false
    };

    for (let index = 0; index < args.length; index += 1) {
        const argument = args[index];

        if (argument === "--real") {
            options.real = true;
            continue;
        }

        const allowed = new Set(["--host", "--port", "--database", "--user"]);
        if (!allowed.has(argument)) {
            throw new Error(`Unknown option: ${argument}`);
        }

        const value = args[index + 1];
        if (!value || value.startsWith("--")) {
            throw new Error(`Missing value for ${argument}`);
        }
        index += 1;

        const key = {
            "--host": "host",
            "--port": "port",
            "--database": "database",
            "--user": "user"
        }[argument];

        options[key] = key === "port" ? Number(value) : value;
    }

    if (!Number.isInteger(options.port) ||
        options.port < 1 ||
        options.port > 65535) {
        throw new Error("Port must be an integer between 1 and 65535");
    }

    validateIdentifier(options.database);
    validateIdentifier(options.user);

    if (typeof options.host !== "string" || options.host.trim() === "") {
        throw new Error("Host must not be empty");
    }

    return options;
}

function printTable(headers, rows) {
    const widths = headers.map((header, index) =>
        Math.max(
            header.length,
            ...rows.map(row => String(row[index] ?? "").length)
        )
    );

    const format = row => row
        .map((cell, index) => String(cell ?? "").padEnd(widths[index]))
        .join(" | ");

    console.log(format(headers));
    console.log(widths.map(width => "-".repeat(width)).join("-+-"));
    rows.forEach(row => console.log(format(row)));
}

function runLaboratory() {
    const cluster = new Cluster();
    const database = cluster.databases.get("plant_operations");

    database.createTable("operations", "assets", [
        "asset_id", "asset_name", "site_code"
    ]);
    database.createTable("operations", "inspection_log", [
        "inspection_id", "asset_id", "inspected_at", "result"
    ]);

    const assets = database.schemas.get("operations").tables.get("assets");
    assets.rows.push(
        [501, "Cooling Pump", "PLANT-N"],
        [502, "Power Transformer", "PLANT-S"]
    );

    console.log("\nPostgreSQL cluster: database inventory");
    printTable(
        ["Database", "Owner"],
        cluster.listDatabases().map(row => [row.name, row.owner])
    );

    console.log("\nSchemas and relations in plant_operations");
    for (const [schemaName, schema] of database.schemas) {
        for (const relation of schema.tables.values()) {
            console.log(
                `${database.name}.${schemaName}.${relation.name}` +
                ` (${relation.columns.join(", ")})`
            );
        }
    }

    const searchPath = ["operations", "public"];
    console.log(`\nEffective demonstration search_path: ${searchPath.join(", ")}`);
    const resolved = database.resolveRelation("assets", searchPath);
    console.log(`assets resolves to operations.${resolved.name}`);

    console.log("\nEquivalent psql commands:");
    console.log("\\conninfo");
    console.log("\\l");
    console.log("\\c plant_operations");
    console.log("\\dn");
    console.log("\\dt operations.*");
    console.log("\\d operations.assets");
    console.log("SHOW search_path;");
    console.log("SELECT current_database(), current_user;");

    console.log("\nPostgreSQL architecture notes:");
    console.log("- The postmaster coordinates server processes and connections.");
    console.log("- A backend process executes work for a client connection.");
    console.log("- Shared buffers cache database pages in shared memory.");
    console.log("- WAL records support crash recovery and durability.");
    console.log("- Databases have separate object namespaces; roles are cluster-wide.");
    console.log("- Schemas organize objects within a database.");
    console.log("- The psql client is separate from the database server.");
}

async function runRealQuery(options) {
    const args = [
        "-X",
        "-v", "ON_ERROR_STOP=1",
        "-h", options.host,
        "-p", String(options.port),
        "-U", options.user,
        "-d", options.database,
        "-c",
        "SELECT current_database(), current_user, version();"
    ];

    console.log(`\nConnecting to ${options.host}:${options.port}/${options.database}`);
    console.log("Authentication is delegated to PostgreSQL's configured mechanisms.");

    // spawn avoids shell interpolation. Passwords are not included in arguments.
    const child = spawn("psql", args, {
        stdio: ["ignore", "inherit", "inherit"],
        shell: false,
        env: process.env
    });

    child.on("error", error => {
        console.error(`Could not start psql: ${error.message}`);
    });

    const [code, signal] = await once(child, "exit");
    if (code !== 0) {
        console.error(`psql failed: exit=${code}, signal=${signal || "none"}`);
    }
    return code ?? 1;
}

async function main() {
    try {
        const options = parseConnectionOptions(process.argv.slice(2));
        runLaboratory();

        if (options.real) {
            return await runRealQuery(options);
        }

        console.log("\nLaboratory completed without a server connection.");
        console.log("Pass --real to query an existing PostgreSQL installation.");
        return 0;
    } catch (error) {
        console.error(`Error: ${error.message}`);
        return 1;
    }
}

main().then(code => {
    process.exitCode = code;
});
