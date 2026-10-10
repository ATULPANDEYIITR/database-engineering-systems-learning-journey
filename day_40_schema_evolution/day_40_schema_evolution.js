"use strict";

/*
 * Schema evolution as an event-driven service contract.
 * Run with Node.js 18 or later: node schema-evolution.js
 */

const { createHash } = require("node:crypto");
const { EventEmitter } = require("node:events");

class ContractError extends Error {}
class MigrationError extends Error {}

const schemas = new Map([
  [1, {
    required: ["id", "customerName"],
    optional: ["email"],
    validate(record) {
      if (!Number.isSafeInteger(record.id) || record.id <= 0) {
        throw new ContractError("id must be a positive safe integer");
      }
      if (typeof record.customerName !== "string" ||
          record.customerName.trim() === "") {
        throw new ContractError("customerName must be a non-empty string");
      }
      if (record.email !== undefined && typeof record.email !== "string") {
        throw new ContractError("email must be a string when supplied");
      }
    }
  }],
  [2, {
    required: ["id", "customerName", "email"],
    optional: ["marketingConsent"],
    validate(record) {
      if (!Number.isSafeInteger(record.id) || record.id <= 0) {
        throw new ContractError("id must be a positive safe integer");
      }
      if (typeof record.customerName !== "string" ||
          record.customerName.trim() === "") {
        throw new ContractError("customerName is required");
      }
      if (typeof record.email !== "string" ||
          !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(record.email)) {
        throw new ContractError("email must be a valid email address");
      }
      if (record.marketingConsent !== undefined &&
          typeof record.marketingConsent !== "boolean") {
        throw new ContractError("marketingConsent must be boolean");
      }
    }
  }],
  [3, {
    required: ["id", "displayName", "email", "marketingConsent"],
    optional: ["locale"],
    validate(record) {
      if (!Number.isSafeInteger(record.id) || record.id <= 0) {
        throw new ContractError("id must be a positive safe integer");
      }
      if (typeof record.displayName !== "string" ||
          record.displayName.trim() === "") {
        throw new ContractError("displayName is required");
      }
      if (typeof record.email !== "string" ||
          !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(record.email)) {
        throw new ContractError("email must be valid");
      }
      if (typeof record.marketingConsent !== "boolean") {
        throw new ContractError("marketingConsent must be explicit");
      }
      if (record.locale !== undefined &&
          !/^[a-z]{2}(?:-[A-Z]{2})?$/.test(record.locale)) {
        throw new ContractError("locale must resemble en or en-US");
      }
    }
  }]
]);

const migrations = new Map([
  ["1:2", record => ({
    id: record.id,
    customerName: record.customerName.trim(),
    email: record.email ?? `customer-${record.id}@migration.invalid`,
    marketingConsent: false
  })],
  ["2:3", record => ({
    id: record.id,
    displayName: record.customerName,
    email: record.email,
    marketingConsent: record.marketingConsent,
    locale: "en"
  })]
]);

function clone(value) {
  return structuredClone(value);
}

function validate(version, record) {
  const schema = schemas.get(version);
  if (!schema) throw new ContractError(`Unknown schema version ${version}`);
  if (record === null || typeof record !== "object" || Array.isArray(record)) {
    throw new ContractError("Record must be a plain object");
  }

  const allowed = new Set([...schema.required, ...schema.optional]);
  const unknown = Object.keys(record).filter(key => !allowed.has(key));
  if (unknown.length) {
    throw new ContractError(`Unknown fields: ${unknown.join(", ")}`);
  }

  for (const field of schema.required) {
    if (!Object.hasOwn(record, field) || record[field] === null) {
      throw new ContractError(`Missing required field: ${field}`);
    }
  }

  schema.validate(record);
  return clone(record);
}

function evolve(record, fromVersion, toVersion) {
  if (!Number.isInteger(fromVersion) || !Number.isInteger(toVersion)) {
    throw new MigrationError("Schema versions must be integers");
  }
  if (toVersion < fromVersion) {
    throw new MigrationError("Downgrades need explicit reverse migrations");
  }

  let current = validate(fromVersion, record);

  for (let version = fromVersion; version < toVersion; version++) {
    const migrate = migrations.get(`${version}:${version + 1}`);
    if (!migrate) {
      throw new MigrationError(`Missing migration ${version} -> ${version + 1}`);
    }

    try {
      const transformed = migrate(clone(current));
      current = validate(version + 1, transformed);
    } catch (error) {
      throw new MigrationError(
        `Migration ${version} -> ${version + 1} failed: ${error.message}`,
        { cause: error }
      );
    }
  }

  return current;
}

class ContractCatalog extends EventEmitter {
  constructor() {
    super();
    this.activeVersion = 1;
    this.records = new Map();
    this.events = [];
  }

  appendEvent(type, payload) {
    const event = Object.freeze({
      sequence: this.events.length + 1,
      type,
      occurredAt: new Date().toISOString(),
      payload: clone(payload)
    });
    this.events.push(event);
    this.emit(type, event);
    return event;
  }

  save(record, version) {
    const normalized = validate(version, record);
    const existing = this.records.get(normalized.id);

    // A versioned write avoids silently replacing a record modified by
    // another request since it was read.
    if (existing && existing.revision !== record.expectedRevision) {
      throw new ContractError(
        `Revision conflict for customer ${normalized.id}`
      );
    }

    const revision = existing ? existing.revision + 1 : 1;
    const stored = {
      schemaVersion: version,
      revision,
      data: normalized
    };

    this.records.set(normalized.id, stored);
    this.appendEvent("record.saved", {
      id: normalized.id,
      schemaVersion: version,
      revision
    });
    return clone(stored);
  }

  evolveAll(targetVersion) {
    const replacements = new Map();

    // Prepare every replacement before publishing any. A failed record
    // leaves the catalog untouched instead of partially migrating the set.
    for (const [id, stored] of this.records) {
      const nextData = evolve(
        stored.data,
        stored.schemaVersion,
        targetVersion
      );
      replacements.set(id, {
        schemaVersion: targetVersion,
        revision: stored.revision + 1,
        data: nextData
      });
    }

    for (const [id, replacement] of replacements) {
      this.records.set(id, replacement);
    }

    const previousVersion = this.activeVersion;
    this.activeVersion = targetVersion;
    this.appendEvent("schema.activated", {
      from: previousVersion,
      to: targetVersion,
      recordCount: replacements.size
    });
  }

  get(id) {
    const stored = this.records.get(id);
    if (!stored) return null;
    return clone(stored);
  }
}

function fingerprint(schema) {
  // A stable representation supports contract-change detection in CI.
  const canonical = JSON.stringify({
    version: schema.version,
    required: [...schema.required].sort(),
    optional: [...schema.optional].sort()
  });
  return createHash("sha256").update(canonical).digest("hex");
}

function main() {
  const catalog = new ContractCatalog();
  catalog.on("schema.activated", event => {
    console.log("Schema activation event:", event.payload);
  });

  const original = {
    id: 101,
    customerName: "  Kavita Rao  ",
    email: "kavita@example.com"
  };

  catalog.save(original, 1);
  console.log("Before migration:", catalog.get(101));

  catalog.evolveAll(3);
  console.log("After migration:", catalog.get(101));

  try {
    validate(3, {
      id: 102,
      displayName: "Invalid Consent",
      email: "invalid@example.com",
      marketingConsent: "yes"
    });
  } catch (error) {
    console.log("Rejected incompatible record:", error.message);
  }

  // Demonstrate optimistic concurrency with an expected revision.
  const current = catalog.get(101);
  const update = {
    ...current.data,
    expectedRevision: current.revision
  };
  console.log("Current revision:", current.revision);
  console.log("Schema v3 fingerprint:", fingerprint({
    version: 3,
    required: schemas.get(3).required,
    optional: schemas.get(3).optional
  }));

  console.log("Event count:", catalog.events.length);
  console.log("Audit trail:", catalog.events.map(event => ({
    sequence: event.sequence,
    type: event.type
  })));

  // Compatibility rule: do not switch required fields on all writers until
  // old readers and old application instances have been retired.
  console.log(
    "Rollout policy: add optional fields, deploy compatible consumers, " +
    "backfill, migrate writers, enforce the new contract."
  );
}

if (require.main === module) {
  try {
    main();
  } catch (error) {
    console.error(error.stack || error.message);
    process.exitCode = 1;
  }
}

module.exports = { ContractCatalog, ContractError, evolve, validate };
