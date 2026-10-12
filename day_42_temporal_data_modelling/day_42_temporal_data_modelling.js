"use strict";

/*
 * Temporal data modeling in Node.js.
 * Demonstrates effective-dated state, event-time windows, late arrivals,
 * deterministic replay, and event-driven corrections without dependencies.
 */

const assert = require("node:assert/strict");

function parseInstant(value) {
  if (typeof value !== "string" || !/(Z|[+-]\d{2}:\d{2})$/i.test(value)) {
    throw new TypeError("Timestamp must be an ISO 8601 string with a timezone.");
  }
  const milliseconds = Date.parse(value);
  if (!Number.isFinite(milliseconds)) {
    throw new RangeError(`Invalid timestamp: ${value}`);
  }
  return milliseconds;
}

function iso(milliseconds) {
  return new Date(milliseconds).toISOString();
}

function deepFreeze(value) {
  if (value && typeof value === "object" && !Object.isFrozen(value)) {
    Object.freeze(value);
    for (const child of Object.values(value)) deepFreeze(child);
  }
  return value;
}

class EffectiveDatedRegistry {
  #records = new Map();

  add(entityId, value, validFrom, validTo = null, recordedAt = Date.now()) {
    if (typeof entityId !== "string" || entityId.trim() === "") {
      throw new TypeError("entityId is required.");
    }
    if (value === undefined || value === null) {
      throw new TypeError("A temporal record must contain a value.");
    }
    if (!Number.isFinite(validFrom) || !Number.isFinite(recordedAt)) {
      throw new TypeError("validFrom and recordedAt must be timestamps.");
    }
    if (validTo !== null && (!Number.isFinite(validTo) || validTo <= validFrom)) {
      throw new RangeError("validTo must be later than validFrom.");
    }

    const records = this.#records.get(entityId) ?? [];
    const end = validTo ?? Infinity;

    // Reject overlapping valid-time intervals rather than silently choosing
    // whichever version happened to be inserted last.
    for (const old of records) {
      const oldEnd = old.validTo ?? Infinity;
      if (validFrom < oldEnd && old.validFrom < end) {
        throw new Error(`Overlapping effective periods for ${entityId}.`);
      }
    }

    const record = deepFreeze({
      id: `${entityId}:${validFrom}:${recordedAt}`,
      entityId,
      value,
      validFrom,
      validTo,
      recordedAt,
    });

    records.push(record);
    records.sort((a, b) => a.validFrom - b.validFrom);
    this.#records.set(entityId, records);
    return record;
  }

  at(entityId, instant) {
    const matches = (this.#records.get(entityId) ?? []).filter(
      record =>
        record.validFrom <= instant &&
        (record.validTo === null || instant < record.validTo)
    );
    if (matches.length > 1) throw new Error("Temporal integrity violation.");
    return matches[0] ?? null;
  }

  asKnownAt(entityId, businessTime, knowledgeTime) {
    const matches = (this.#records.get(entityId) ?? []).filter(
      record =>
        record.validFrom <= businessTime &&
        (record.validTo === null || businessTime < record.validTo) &&
        record.recordedAt <= knowledgeTime
    );
    return matches.sort((a, b) => b.recordedAt - a.recordedAt)[0] ?? null;
  }

  history(entityId) {
    return [...(this.#records.get(entityId) ?? [])];
  }
}

class TemporalEventStream {
  #events = new Map();
  #maximumEventTime = -Infinity;
  #listeners = new Map();

  constructor({ allowedLatenessMs = 5 * 60 * 1000 } = {}) {
    if (!Number.isFinite(allowedLatenessMs) || allowedLatenessMs < 0) {
      throw new RangeError("allowedLatenessMs must be a non-negative number.");
    }
    this.allowedLatenessMs = allowedLatenessMs;
  }

  on(eventName, listener) {
    if (typeof listener !== "function") throw new TypeError("Listener must be a function.");
    const listeners = this.#listeners.get(eventName) ?? new Set();
    listeners.add(listener);
    this.#listeners.set(eventName, listeners);
    return () => listeners.delete(listener);
  }

  #emit(eventName, value) {
    for (const listener of this.#listeners.get(eventName) ?? []) {
      listener(value);
    }
  }

  ingest(input) {
    if (!input || typeof input !== "object") throw new TypeError("Event must be an object.");
    if (typeof input.id !== "string" || input.id.trim() === "") {
      throw new TypeError("Event id is required.");
    }
    if (this.#events.has(input.id)) return "duplicate";
    if (typeof input.type !== "string" || !input.type.trim()) {
      throw new TypeError("Event type is required.");
    }
    if (!Number.isFinite(input.eventTime) || !Number.isFinite(input.receivedAt)) {
      throw new TypeError("Event and ingestion times must be numeric timestamps.");
    }

    const late = input.eventTime < this.#maximumEventTime - this.allowedLatenessMs;
    const event = deepFreeze({ ...input, payload: { ...(input.payload ?? {}) } });

    this.#events.set(event.id, event);
    this.#maximumEventTime = Math.max(this.#maximumEventTime, event.eventTime);
    this.#emit(late ? "late" : "accepted", event);
    this.#emit("ingested", event);
    return late ? "late" : "accepted";
  }

  window(start, end) {
    if (!Number.isFinite(start) || !Number.isFinite(end) || end <= start) {
      throw new RangeError("Window must be a valid half-open interval.");
    }
    return [...this.#events.values()]
      .filter(event => event.eventTime >= start && event.eventTime < end)
      .sort((a, b) => a.eventTime - b.eventTime || a.id.localeCompare(b.id));
  }

  countByType(start, end) {
    const counts = new Map();
    for (const event of this.window(start, end)) {
      counts.set(event.type, (counts.get(event.type) ?? 0) + 1);
    }
    return Object.fromEntries(counts);
  }
}

async function replayEvents(events, handler) {
  // A stable sort gives reproducible replay even when events arrived out of order.
  const ordered = [...events].sort(
    (a, b) => a.eventTime - b.eventTime || a.id.localeCompare(b.id)
  );
  for (const event of ordered) await handler(event);
}

async function main() {
  console.log("=== Effective-dated configuration ===");

  const registry = new EffectiveDatedRegistry();
  const jan = parseInstant("2026-01-01T00:00:00Z");
  const apr = parseInstant("2026-04-01T00:00:00Z");
  const jul = parseInstant("2026-07-01T00:00:00Z");
  const aug = parseInstant("2026-08-10T09:00:00Z");

  registry.add("warehouse-west", { capacity: 1200 }, jan, apr, jan);
  registry.add("warehouse-west", { capacity: 1500 }, apr, jul, apr);
  registry.add("warehouse-west", { capacity: 1800 }, jul, null, aug);

  console.log("Capacity on May 15:", registry.at(
    "warehouse-west", parseInstant("2026-05-15T00:00:00Z")
  ).value.capacity);
  console.log("Capacity on August 1:", registry.at(
    "warehouse-west", parseInstant("2026-08-01T00:00:00Z")
  ).value.capacity);

  try {
    registry.add("warehouse-west", { capacity: 1600 }, jul - 1000, null, aug);
  } catch (error) {
    console.log("Invalid overlapping version rejected:", error.message);
  }

  console.log("\n=== Event-driven temporal processing ===");

  const stream = new TemporalEventStream({ allowedLatenessMs: 2 * 60 * 1000 });
  const accepted = [];
  const late = [];

  stream.on("accepted", event => accepted.push(event.id));
  stream.on("late", event => late.push(event.id));

  const incoming = [
    {
      id: "shipment-301",
      type: "shipment.departed",
      eventTime: parseInstant("2026-10-12T10:10:00Z"),
      receivedAt: parseInstant("2026-10-12T10:11:00Z"),
      payload: { route: "LKO-DEL", kilometres: 490 },
    },
    {
      id: "shipment-302",
      type: "shipment.delayed",
      eventTime: parseInstant("2026-10-12T10:12:00Z"),
      receivedAt: parseInstant("2026-10-12T10:12:05Z"),
      payload: { delayMinutes: 35 },
    },
    {
      id: "shipment-303",
      type: "shipment.departed",
      eventTime: parseInstant("2026-10-12T10:01:00Z"),
      receivedAt: parseInstant("2026-10-12T10:13:00Z"),
      payload: { route: "LKO-KNP", kilometres: 90 },
    },
  ];

  for (const event of incoming) console.log(event.id, stream.ingest(event));
  console.log("Accepted event IDs:", accepted);
  console.log("Late event IDs:", late);

  const start = parseInstant("2026-10-12T10:00:00Z");
  const end = parseInstant("2026-10-12T10:15:00Z");
  console.log("Counts by event time:", stream.countByType(start, end));

  const replayed = [];
  await replayEvents(stream.window(start, end), async event => {
    replayed.push({ id: event.id, eventTime: iso(event.eventTime) });
  });
  console.log("Deterministic replay:", replayed);

  // Tests cover temporal boundaries, invalid dates, deduplication, and lateness.
  assert.equal(registry.at("warehouse-west", apr).value.capacity, 1500);
  assert.equal(registry.at("warehouse-west", jul).value.capacity, 1800);
  assert.equal(registry.at("warehouse-west", jan - 1), null);
  assert.equal(stream.ingest(incoming[0]), "duplicate");
  assert.throws(() => parseInstant("2026-10-12T10:00:00"), /timezone/);
  assert.equal(stream.window(start, end).length, 3);
  assert.throws(() => stream.window(end, start), /half-open/);

  const historical = registry.asKnownAt(
    "warehouse-west",
    parseInstant("2026-08-01T00:00:00Z"),
    parseInstant("2026-08-01T00:00:00Z")
  );
  assert.equal(historical, null);

  console.log("All temporal-model assertions passed.");
}

main().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
