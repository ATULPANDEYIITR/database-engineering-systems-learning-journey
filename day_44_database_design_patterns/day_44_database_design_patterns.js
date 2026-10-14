"use strict";

/**
 * Database Design Patterns: Audit Tables, Soft Deletes, and Status Models.
 *
 * Event-driven repository lifecycle model for Node.js 18+.
 * Demonstrates:
 * - Explicit status transition rules.
 * - Soft deletion independent of business status.
 * - Append-only audit events.
 * - Optimistic version checks.
 * - Idempotent commands.
 * - Event subscriptions and asynchronous persistence boundaries.
 * - Safe query filtering and reproducible tests.
 *
 * Run:
 *   node database-patterns.js
 */

const assert = require("node:assert/strict");
const { randomUUID } = require("node:crypto");
const { EventEmitter } = require("node:events");

const Status = Object.freeze({
  REQUESTED: "requested",
  APPROVED: "approved",
  IN_SERVICE: "in_service",
  MAINTENANCE: "maintenance",
  RETIRED: "retired",
});

const TRANSITIONS = new Map([
  [Status.REQUESTED, new Set([Status.APPROVED])],
  [Status.APPROVED, new Set([Status.IN_SERVICE, Status.RETIRED])],
  [Status.IN_SERVICE, new Set([Status.MAINTENANCE, Status.RETIRED])],
  [Status.MAINTENANCE, new Set([Status.IN_SERVICE, Status.RETIRED])],
  [Status.RETIRED, new Set()],
]);

class DomainError extends Error {}
class ValidationError extends DomainError {}
class NotFoundError extends DomainError {}
class InvalidTransitionError extends DomainError {}
class ConcurrencyError extends DomainError {}
class IdempotencyConflictError extends DomainError {}

function requireActor(actor) {
  if (typeof actor !== "string" || actor.trim() === "") {
    throw new ValidationError("A non-empty actor is required.");
  }
  return actor.trim();
}

function requireReason(reason) {
  if (typeof reason !== "string" || reason.trim() === "") {
    throw new ValidationError("A reason is required.");
  }
  return reason.trim();
}

function clone(value) {
  // Copy domain data at event boundaries so subscribers cannot mutate
  // the repository's internal state through a shared object reference.
  return structuredClone(value);
}

class EquipmentService extends EventEmitter {
  #records = new Map();
  #assetTags = new Map();
  #auditEvents = [];
  #idempotency = new Map();

  constructor(clock = () => new Date()) {
    super();
    this.clock = clock;
  }

  #timestamp() {
    const value = this.clock();
    if (!(value instanceof Date) || Number.isNaN(value.getTime())) {
      throw new ValidationError("Clock returned an invalid date.");
    }
    return value.toISOString();
  }

  #snapshot(record) {
    return clone(record);
  }

  #appendAudit(record, action, actor, oldValues, newValues, reason, key) {
    const event = Object.freeze({
      eventId: randomUUID(),
      entityType: "equipment",
      entityId: record.id,
      action,
      actor,
      occurredAt: this.#timestamp(),
      oldValues: clone(oldValues),
      newValues: clone(newValues),
      reason: reason ?? null,
      correlationId: key ?? randomUUID(),
    });

    this.#auditEvents.push(event);
    // Events are emitted after state and audit data have been updated.
    // Listeners should not be trusted to provide durable transactionality.
    this.emit("audit", clone(event));
    return event;
  }

  create({ assetTag, name, actor, requestKey = randomUUID() }) {
    actor = requireActor(actor);

    if (typeof assetTag !== "string" || !assetTag.trim()) {
      throw new ValidationError("Asset tag is required.");
    }
    if (typeof name !== "string" || !name.trim()) {
      throw new ValidationError("Equipment name is required.");
    }

    const normalizedTag = assetTag.trim().toUpperCase();
    if (this.#assetTags.has(normalizedTag)) {
      throw new ValidationError(`Asset tag ${normalizedTag} already exists.`);
    }

    const record = {
      id: randomUUID(),
      assetTag: normalizedTag,
      name: name.trim(),
      status: Status.REQUESTED,
      isDeleted: false,
      deletedAt: null,
      deletedBy: null,
      createdAt: this.#timestamp(),
      createdBy: actor,
      updatedAt: this.#timestamp(),
      updatedBy: actor,
      version: 1,
    };

    this.#records.set(record.id, record);
    this.#assetTags.set(normalizedTag, record.id);

    const event = this.#appendAudit(
      record, "created", actor, {}, this.#snapshot(record), null, requestKey
    );

    return { record: this.#snapshot(record), eventId: event.eventId };
  }

  get(id, { includeDeleted = false } = {}) {
    const record = this.#records.get(id);
    if (!record || (record.isDeleted && !includeDeleted)) {
      throw new NotFoundError("Equipment was not found.");
    }
    return this.#snapshot(record);
  }

  list({ includeDeleted = false, status = null } = {}) {
    return [...this.#records.values()]
      .filter(record => includeDeleted || !record.isDeleted)
      .filter(record => status === null || record.status === status)
      .sort((left, right) => left.assetTag.localeCompare(right.assetTag))
      .map(record => this.#snapshot(record));
  }

  #checkVersion(record, expectedVersion) {
    if (!Number.isInteger(expectedVersion) || expectedVersion < 1) {
      throw new ValidationError("Expected version must be a positive integer.");
    }
    if (record.version !== expectedVersion) {
      throw new ConcurrencyError(
        `Expected version ${expectedVersion}; found ${record.version}.`
      );
    }
  }

  #requireRecord(id, includeDeleted = false) {
    const record = this.#records.get(id);
    if (!record || (record.isDeleted && !includeDeleted)) {
      throw new NotFoundError("Equipment was not found.");
    }
    return record;
  }

  #commit(record, action, actor, oldValues, reason, requestKey) {
    record.version += 1;
    record.updatedAt = this.#timestamp();
    record.updatedBy = actor;

    const event = this.#appendAudit(
      record, action, actor, oldValues, this.#snapshot(record),
      reason, requestKey
    );

    return { record: this.#snapshot(record), eventId: event.eventId };
  }

  transition({
    id,
    targetStatus,
    expectedVersion,
    actor,
    reason,
    requestKey = randomUUID(),
  }) {
    actor = requireActor(actor);
    reason = requireReason(reason);

    const record = this.#requireRecord(id);
    this.#checkVersion(record, expectedVersion);

    if (!Object.values(Status).includes(targetStatus)) {
      throw new ValidationError(`Unknown status: ${targetStatus}`);
    }
    if (!TRANSITIONS.get(record.status).has(targetStatus)) {
      throw new InvalidTransitionError(
        `Transition ${record.status} -> ${targetStatus} is not permitted.`
      );
    }

    const oldValues = { status: record.status };
    record.status = targetStatus;

    return this.#commit(
      record, "status_changed", actor, oldValues, reason, requestKey
    );
  }

  softDelete({
    id,
    expectedVersion,
    actor,
    reason,
    operationKey,
  }) {
    actor = requireActor(actor);
    reason = requireReason(reason);

    if (typeof operationKey !== "string" || !operationKey.trim()) {
      throw new ValidationError("An idempotency key is required.");
    }

    const key = operationKey.trim();
    const existing = this.#idempotency.get(key);

    if (existing) {
      if (existing.id !== id || existing.actor !== actor) {
        throw new IdempotencyConflictError(
          "The key belongs to a different operation."
        );
      }
      return clone(existing.result);
    }

    const record = this.#requireRecord(id);
    this.#checkVersion(record, expectedVersion);

    const oldValues = {
      isDeleted: false,
      deletedAt: null,
      deletedBy: null,
    };

    record.isDeleted = true;
    record.deletedAt = this.#timestamp();
    record.deletedBy = actor;

    const result = this.#commit(
      record, "soft_deleted", actor, oldValues, reason, key
    );

    this.#idempotency.set(key, {
      id,
      actor,
      result: clone(result),
    });

    return result;
  }

  restore({ id, expectedVersion, actor, reason, requestKey = randomUUID() }) {
    actor = requireActor(actor);
    reason = requireReason(reason);

    const record = this.#requireRecord(id, true);
    this.#checkVersion(record, expectedVersion);

    if (!record.isDeleted) {
      throw new InvalidTransitionError("Equipment is already active.");
    }

    const oldValues = {
      isDeleted: true,
      deletedAt: record.deletedAt,
      deletedBy: record.deletedBy,
    };

    record.isDeleted = false;
    record.deletedAt = null;
    record.deletedBy = null;

    return this.#commit(
      record, "restored", actor, oldValues, reason, requestKey
    );
  }

  history(id) {
    if (!this.#records.has(id)) {
      throw new NotFoundError("Equipment was not found.");
    }
    return this.#auditEvents
      .filter(event => event.entityId === id)
      .map(event => clone(event));
  }

  auditReport() {
    const issues = [];
    for (const record of this.#records.values()) {
      const history = this.#auditEvents.filter(
        event => event.entityId === record.id
      );
      if (history.length === 0 || history[0].action !== "created") {
        issues.push(`${record.id}: missing creation event`);
      }
    }
    return {
      entityCount: this.#records.size,
      eventCount: this.#auditEvents.length,
      issues,
    };
  }
}

function runDemo() {
  const service = new EquipmentService();
  const receivedActions = [];

  service.on("audit", event => {
    receivedActions.push(event.action);
  });

  const created = service.create({
    assetTag: "motor-701",
    name: "Conveyor drive motor",
    actor: "asset-clerk",
  });

  const approved = service.transition({
    id: created.record.id,
    targetStatus: Status.APPROVED,
    expectedVersion: 1,
    actor: "maintenance-manager",
    reason: "Maintenance specifications verified.",
  });

  const deleted = service.softDelete({
    id: created.record.id,
    expectedVersion: approved.record.version,
    actor: "records-officer",
    reason: "Duplicate department assignment.",
    operationKey: "delete-motor-701",
  });

  const repeatedDelete = service.softDelete({
    id: created.record.id,
    expectedVersion: approved.record.version,
    actor: "records-officer",
    reason: "Duplicate department assignment.",
    operationKey: "delete-motor-701",
  });

  assert.equal(deleted.eventId, repeatedDelete.eventId);
  assert.equal(service.list().length, 0);
  assert.equal(service.get(created.record.id, { includeDeleted: true }).isDeleted, true);

  const restored = service.restore({
    id: created.record.id,
    expectedVersion: deleted.record.version,
    actor: "records-officer",
    reason: "The asset assignment was verified.",
  });

  assert.equal(restored.record.isDeleted, false);
  assert.equal(service.history(created.record.id).length, 4);
  assert.deepEqual(service.auditReport().issues, []);

  assert.throws(
    () => service.transition({
      id: created.record.id,
      targetStatus: Status.RETIRED,
      expectedVersion: restored.record.version,
      actor: "maintenance-manager",
      reason: "Invalid direct transition from approved.",
    }),
    InvalidTransitionError
  );

  assert.throws(
    () => service.transition({
      id: created.record.id,
      targetStatus: Status.IN_SERVICE,
      expectedVersion: 1,
      actor: "maintenance-manager",
      reason: "Stale update test.",
    }),
    ConcurrencyError
  );

  console.log("Active equipment:", service.list());
  console.log("Audit actions:", receivedActions);
  console.log("Audit report:", service.auditReport());
  console.log("Lifecycle tests passed.");
}

if (require.main === module) {
  runDemo();
}

module.exports = {
  EquipmentService,
  Status,
  DomainError,
  ValidationError,
  NotFoundError,
  InvalidTransitionError,
  ConcurrencyError,
  IdempotencyConflictError,
};
