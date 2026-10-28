#!/usr/bin/env node
"use strict";

/*
 * PostgreSQL configuration policy engine.
 *
 * The program models configuration-file values, session overrides,
 * reload/restart requirements, memory pressure, connection policy,
 * validation, and asynchronous configuration-change events.
 */

const fs = require("node:fs/promises");
const path = require("node:path");
const os = require("node:os");
const { EventEmitter } = require("node:events");

const SETTING_DEFINITIONS = Object.freeze({
  max_connections: {
    defaultValue: "100",
    category: "connection",
    min: 10,
    max: 10000,
    restart: false,
  },
  shared_buffers: {
    defaultValue: "128MB",
    category: "memory",
    min: 16 * 1024 ** 2,
    max: 1024 * 1024 ** 3,
    restart: true,
  },
  work_mem: {
    defaultValue: "4MB",
    category: "memory",
    min: 64 * 1024,
    max: 1024 * 1024 ** 2,
    restart: false,
  },
  maintenance_work_mem: {
    defaultValue: "64MB",
    category: "memory",
    min: 1024 ** 2,
    max: 2048 * 1024 ** 2,
    restart: false,
  },
  effective_cache_size: {
    defaultValue: "4GB",
    category: "memory",
    min: 128 * 1024 ** 2,
    max: 4096 * 1024 ** 3,
    restart: false,
  },
  statement_timeout: {
    defaultValue: "0",
    category: "connection",
    min: 0,
    max: 24 * 60 * 60 * 1000,
    restart: false,
  },
  idle_in_transaction_session_timeout: {
    defaultValue: "0",
    category: "connection",
    min: 0,
    max: 24 * 60 * 60 * 1000,
    restart: false,
  },
  listen_addresses: {
    defaultValue: "localhost",
    category: "connection",
    restart: false,
  },
  port: {
    defaultValue: "5432",
    category: "connection",
    min: 1,
    max: 65535,
    restart: true,
  },
});

function parseValue(value) {
  const match = String(value).trim().toLowerCase()
    .match(/^(\d+)\s*(kb|mb|gb)?$/);

  if (!match) {
    throw new Error(`Invalid numeric configuration value: ${value}`);
  }

  const number = Number(match[1]);
  const multipliers = {
    kb: 1024,
    mb: 1024 ** 2,
    gb: 1024 ** 3,
  };

  return number * (multipliers[match[2]] ?? 1);
}

function validateSetting(name, value) {
  const definition = SETTING_DEFINITIONS[name];
  if (!definition) {
    throw new Error(`Unknown PostgreSQL setting: ${name}`);
  }

  if (definition.min === undefined) {
    if (!String(value).trim()) {
      throw new Error(`${name} cannot be empty`);
    }
    return;
  }

  const numeric = parseValue(value);

  if (numeric < definition.min) {
    throw new Error(`${name} is below its minimum`);
  }

  if (numeric > definition.max) {
    throw new Error(`${name} exceeds its maximum`);
  }
}

class PostgreSQLConfiguration extends EventEmitter {
  constructor() {
    super();
    this.defaults = Object.fromEntries(
      Object.entries(SETTING_DEFINITIONS)
        .map(([name, definition]) => [name, definition.defaultValue])
    );
    this.fileValues = new Map();
    this.sessionValues = new Map();
    this.pendingRestart = new Set();
  }

  effective(name) {
    if (!(name in SETTING_DEFINITIONS)) {
      throw new Error(`Unknown setting: ${name}`);
    }

    return this.sessionValues.get(name)
      ?? this.fileValues.get(name)
      ?? this.defaults[name];
  }

  setFileValue(name, value) {
    validateSetting(name, value);

    const definition = SETTING_DEFINITIONS[name];
    this.fileValues.set(name, String(value));

    const mode = definition.restart ? "restart" : "reload";

    if (definition.restart) {
      this.pendingRestart.add(name);
    }

    this.emit("configurationChanged", {
      name,
      value: String(value),
      mode,
    });

    return mode;
  }

  setSessionValue(name, value) {
    validateSetting(name, value);
    this.sessionValues.set(name, String(value));

    this.emit("sessionOverride", {
      name,
      value: String(value),
    });
  }

  reload() {
    this.emit("reloadStarted");

    for (const name of [...this.pendingRestart]) {
      if (!SETTING_DEFINITIONS[name].restart) {
        this.pendingRestart.delete(name);
      }
    }

    this.emit("reloadCompleted", {
      pendingRestart: [...this.pendingRestart],
    });
  }

  restart() {
    this.pendingRestart.clear();
    this.emit("restartCompleted");
  }

  validate() {
    const warnings = [];

    const connections = Number(
      parseValue(this.effective("max_connections"))
    );
    const workMem = parseValue(this.effective("work_mem"));
    const sharedBuffers = parseValue(this.effective("shared_buffers"));

    const estimated = connections * workMem;

    if (estimated > sharedBuffers * 4) {
      warnings.push(
        `Potential memory pressure: ${estimated} bytes of estimated ` +
        `connection-level work memory exceeds four times shared_buffers.`
      );
    }

    if (connections > 2000) {
      warnings.push(
        "Very high max_connections detected; use connection pooling where possible."
      );
    }

    if (this.effective("listen_addresses") === "*") {
      warnings.push(
        "listen_addresses='*' exposes the server on all interfaces. " +
        "Restrict network access and pg_hba.conf rules explicitly."
      );
    }

    return warnings;
  }

  report() {
    return Object.keys(SETTING_DEFINITIONS).map(name => ({
      name,
      category: SETTING_DEFINITIONS[name].category,
      defaultValue: this.defaults[name],
      fileValue: this.fileValues.get(name) ?? null,
      sessionValue: this.sessionValues.get(name) ?? null,
      effectiveValue: this.effective(name),
      restartRequired: SETTING_DEFINITIONS[name].restart,
      pendingRestart: this.pendingRestart.has(name),
    }));
  }
}

async function writeConfigurationFile(configuration, filePath) {
  const lines = [
    "# Generated PostgreSQL-style configuration",
    "# Values were validated before writing.",
    "",
  ];

  for (const [name, value] of [...configuration.fileValues.entries()].sort()) {
    lines.push(`${name} = ${value}`);
  }

  await fs.writeFile(filePath, lines.join("\n") + "\n", "utf8");
}

async function loadConfigurationFile(filePath) {
  const content = await fs.readFile(filePath, "utf8");
  const result = new Map();

  for (const [index, rawLine] of content.split(/\r?\n/).entries()) {
    const line = rawLine.trim();

    if (!line || line.startsWith("#")) {
      continue;
    }

    const separator = line.indexOf("=");
    if (separator === -1) {
      throw new Error(`Invalid configuration at line ${index + 1}`);
    }

    const name = line.slice(0, separator).trim();
    const value = line.slice(separator + 1).trim();

    validateSetting(name, value);
    result.set(name, value);
  }

  return result;
}

async function main() {
  const configuration = new PostgreSQLConfiguration();

  configuration.on("configurationChanged", event => {
    console.log(
      `CONFIG: ${event.name}=${event.value}; apply with ${event.mode}`
    );
  });

  configuration.on("reloadCompleted", event => {
    console.log(
      `RELOAD: pending restart settings: ${event.pendingRestart.join(", ") || "none"}`
    );
  });

  configuration.on("restartCompleted", () => {
    console.log("RESTART: all pending restart settings are active.");
  });

  const productionSettings = {
    shared_buffers: "512MB",
    work_mem: "8MB",
    maintenance_work_mem: "128MB",
    effective_cache_size: "4GB",
    max_connections: "200",
    statement_timeout: "30000",
    idle_in_transaction_session_timeout: "60000",
    log_min_duration_statement: "1000",
    listen_addresses: "localhost",
    port: "5432",
  };

  for (const [name, value] of Object.entries(productionSettings)) {
    configuration.setFileValue(name, value);
  }

  configuration.setSessionValue("work_mem", "16MB");

  console.log("\nValidation:");
  const warnings = configuration.validate();
  if (warnings.length === 0) {
    console.log("No configuration warnings.");
  } else {
    for (const warning of warnings) {
      console.log(`- ${warning}`);
    }
  }

  console.log("\nEffective settings:");
  console.table(configuration.report());

  configuration.reload();

  // shared_buffers and port remain pending because they require restart.
  configuration.restart();

  const temporaryDirectory = await fs.mkdtemp(
    path.join(os.tmpdir(), "postgres-config-")
  );
  const filePath = path.join(temporaryDirectory, "postgresql.conf");

  try {
    await writeConfigurationFile(configuration, filePath);
    const loaded = await loadConfigurationFile(filePath);

    console.log("\nPersisted configuration:");
    console.log(await fs.readFile(filePath, "utf8"));

    if (loaded.get("max_connections") !== "200") {
      throw new Error("Configuration persistence verification failed");
    }

    console.log("Persistence verification passed.");
  } finally {
    await fs.rm(temporaryDirectory, { recursive: true, force: true });
  }

  // A production system should combine PostgreSQL settings with network
  // controls, authentication policy, TLS, and pg_hba.conf rules.
  if (configuration.effective("listen_addresses") === "*") {
    throw new Error("Unsafe unrestricted listener configuration");
  }

  console.log("\nFinal state:");
  console.log(JSON.stringify(configuration.report(), null, 2));
}

main().catch(error => {
  console.error(`Configuration processing failed: ${error.message}`);
  process.exitCode = 1;
});
