"use strict";

/*
 * Surrogate and natural keys in a distributed order-ingestion service.
 * Run with Node.js 18 or later:
 *     node keys_design_lab.js
 *
 * This implementation focuses on event-driven processing, idempotent
 * ingestion, external identity mapping, asynchronous concurrency, and
 * JavaScript-specific serialization and precision constraints.
 */

const { randomUUID, createHash } = require("node:crypto");

class KeyValidationError extends Error {
  constructor(message) {
    super(message);
    this.name = "KeyValidationError";
  }
}

function normalizeExternalReference(value) {
  if (typeof value !== "string" || value.trim() === "") {
    throw new KeyValidationError("External reference must be a non-empty string.");
  }
  return value.trim().normalize("NFKC");
}

function normalizeEmail(value) {
  if (typeof value !== "string") {
    throw new KeyValidationError("Email must be a string.");
  }

  const email = value.trim().toLowerCase();
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    throw new KeyValidationError("Email format is invalid.");
  }
  return email;
}

function stableSourceKey(sourceSystem, sourceRecordId) {
  if (
    typeof sourceSystem !== "string" ||
    !sourceSystem.trim() ||
    typeof sourceRecordId !== "string" ||
    !sourceRecordId.trim()
  ) {
    throw new KeyValidationError("Source system and source record ID are required.");
  }

  // Length-prefixed fields avoid ambiguity between differently partitioned
  // strings. The digest is deterministic but should not replace a UNIQUE
  // constraint on the original source-system/source-record pair.
  const system = sourceSystem.trim().toLowerCase();
  const record = sourceRecordId.trim();
  const canonical = `${system.length}:${system}${record.length}:${record}`;

  return createHash("sha256").update(canonical, "utf8").digest("hex");
}

class OrderIngestionService {
  #ordersById = new Map();
  #orderIdBySourceKey = new Map();
  #customerIdByEmail = new Map();
  #nextCustomerNumber = 1;
  #listeners = new Map();

  on(eventName, listener) {
    if (typeof listener !== "function") {
      throw new TypeError("Listener must be a function.");
    }

    const listeners = this.#listeners.get(eventName) ?? new Set();
    listeners.add(listener);
    this.#listeners.set(eventName, listeners);

    // Returning an unsubscribe function prevents stale listeners from
    // accumulating in long-lived services.
    return () => listeners.delete(listener);
  }

  emit(eventName, event) {
    for (const listener of this.#listeners.get(eventName) ?? []) {
      listener(Object.freeze({ ...event }));
    }
  }

  registerCustomer(email, displayName) {
    const normalizedEmail = normalizeEmail(email);
    if (typeof displayName !== "string" || !displayName.trim()) {
      throw new KeyValidationError("Display name cannot be empty.");
    }

    const existing = this.#customerIdByEmail.get(normalizedEmail);
    if (existing) {
      throw new KeyValidationError(`Customer already exists: ${existing}`);
    }

    // This number is unique only inside this service instance. A database
    // sequence or distributed allocation strategy is needed across instances.
    const customerId = this.#nextCustomerNumber++;
    const customer = Object.freeze({
      customerId,
      email: normalizedEmail,
      displayName: displayName.trim(),
    });

    this.#customerIdByEmail.set(normalizedEmail, customer);
    this.emit("customer.registered", { customerId, email: normalizedEmail });
    return customer;
  }

  changeCustomerEmail(oldEmail, newEmail) {
    const oldKey = normalizeEmail(oldEmail);
    const newKey = normalizeEmail(newEmail);
    const customer = this.#customerIdByEmail.get(oldKey);

    if (!customer) {
      throw new KeyValidationError("Existing customer was not found.");
    }
    if (this.#customerIdByEmail.has(newKey)) {
      throw new KeyValidationError("New email already belongs to another customer.");
    }

    const updated = Object.freeze({
      ...customer,
      email: newKey,
    });

    this.#customerIdByEmail.delete(oldKey);
    this.#customerIdByEmail.set(newKey, updated);
    this.emit("customer.emailChanged", {
      customerId: customer.customerId,
      oldEmail: oldKey,
      newEmail: newKey,
    });

    return updated;
  }

  async ingestOrder(sourceSystem, sourceRecordId, customer, amountMinorUnits) {
    // Yielding to the event loop models asynchronous ingestion. The critical
    // section below contains no await, so Map checks and updates remain
    // atomic relative to other JavaScript callbacks in this isolate.
    await Promise.resolve();

    if (!customer || !Number.isSafeInteger(customer.customerId)) {
      throw new KeyValidationError("A valid registered customer is required.");
    }
    if (!Number.isSafeInteger(amountMinorUnits) || amountMinorUnits < 0) {
      throw new KeyValidationError(
        "Amount must be a non-negative safe integer in minor currency units."
      );
    }

    const sourceKey = stableSourceKey(sourceSystem, sourceRecordId);
    const existingOrderId = this.#orderIdBySourceKey.get(sourceKey);

    if (existingOrderId) {
      const existing = this.#ordersById.get(existingOrderId);

      // Idempotency means retrying the same source event does not create
      // another order. Conflicting payloads must not be silently accepted.
      if (
        existing.customerId !== customer.customerId ||
        existing.amountMinorUnits !== amountMinorUnits
      ) {
        throw new KeyValidationError(
          "The source record already exists with a different payload."
        );
      }

      return { order: existing, duplicate: true };
    }

    const order = Object.freeze({
      orderId: randomUUID(),
      customerId: customer.customerId,
      sourceSystem: sourceSystem.trim().toLowerCase(),
      sourceRecordId: normalizeExternalReference(sourceRecordId),
      amountMinorUnits,
      createdAt: new Date().toISOString(),
    });

    this.#ordersById.set(order.orderId, order);
    this.#orderIdBySourceKey.set(sourceKey, order.orderId);
    this.emit("order.created", {
      orderId: order.orderId,
      customerId: order.customerId,
      sourceSystem: order.sourceSystem,
    });

    return { order, duplicate: false };
  }

  getOrder(orderId) {
    return this.#ordersById.get(orderId) ?? null;
  }

  getOrdersForCustomer(customerId) {
    return [...this.#ordersById.values()].filter(
      (order) => order.customerId === customerId
    );
  }
}

async function main() {
  console.log("=== Event-driven key design ===");

  const service = new OrderIngestionService();

  service.on("order.created", (event) => {
    console.log("Order event:", event);
  });

  service.on("customer.emailChanged", (event) => {
    console.log("Customer identity retained:", event.customerId);
  });

  const customer = service.registerCustomer(
    "operations@example.com",
    "Operations Team"
  );

  const firstResult = await service.ingestOrder(
    "warehouse-erp",
    "INV-2026-0038",
    customer,
    259900
  );

  const retryResult = await service.ingestOrder(
    "warehouse-erp",
    "INV-2026-0038",
    customer,
    259900
  );

  console.log("Created order:", firstResult.order.orderId);
  console.log("Retry was deduplicated:", retryResult.duplicate);
  console.log(
    "Both attempts reference the same ID:",
    firstResult.order.orderId === retryResult.order.orderId
  );

  try {
    await service.ingestOrder(
      "warehouse-erp",
      "INV-2026-0038",
      customer,
      100
    );
  } catch (error) {
    console.log("Conflicting retry rejected:", error.message);
  }

  service.changeCustomerEmail(
    "operations@example.com",
    "operations-team@example.com"
  );

  console.log(
    "Orders still reference the same customer:",
    service.getOrdersForCustomer(customer.customerId).length
  );

  console.log("\n=== Key serialization and numeric precision ===");

  // JavaScript Number cannot represent every integer above 2^53 - 1 exactly.
  const unsafeInteger = 9007199254740993;
  console.log("Unsafe Number:", unsafeInteger);
  console.log("Precision-safe check:", Number.isSafeInteger(unsafeInteger));

  // Keep large external numeric identifiers as strings or BigInt.
  // JSON.stringify does not serialize BigInt without explicit conversion.
  const largeIdentifier = 9007199254740993n;
  const serializedIdentifier = JSON.stringify(largeIdentifier.toString());
  console.log("Serialized large identifier:", serializedIdentifier);

  const digestA = stableSourceKey("ERP", "INV-77");
  const digestB = stableSourceKey("erp", "INV-77");
  console.log("Normalized source systems match:", digestA === digestB);
  console.log("Digest length:", digestA.length);

  console.log("\n=== Identity design observations ===");
  console.log("Internal UUID: independent order identity.");
  console.log("Source pair: idempotency and external reconciliation.");
  console.log("Customer email: mutable business attribute with uniqueness policy.");
  console.log(
    "Production requirement: persist these mappings under database constraints."
  );
}

main().catch((error) => {
  console.error("Ingestion failed:", error.message);
  process.exitCode = 1;
});
