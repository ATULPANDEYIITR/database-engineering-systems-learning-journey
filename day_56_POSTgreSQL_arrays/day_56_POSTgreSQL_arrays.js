"use strict";

/*
 * PostgreSQL-array concepts modeled with JavaScript arrays.
 * The implementation emphasizes transformations, validation,
 * asynchronous processing, and event-driven inventory updates.
 */

class ArrayOperationError extends Error {
  constructor(message) {
    super(message);
    this.name = "ArrayOperationError";
  }
}

class InventoryItem {
  constructor(id, name, tags, quantities) {
    if (!Number.isInteger(id) || id <= 0) {
      throw new ArrayOperationError("id must be a positive integer");
    }

    if (typeof name !== "string" || name.trim() === "") {
      throw new ArrayOperationError("name cannot be empty");
    }

    if (!Array.isArray(tags) || !Array.isArray(quantities)) {
      throw new ArrayOperationError("tags and quantities must be arrays");
    }

    if (quantities.some((value) => !Number.isInteger(value) || value < 0)) {
      throw new ArrayOperationError(
        "quantities must contain non-negative integers"
      );
    }

    this.id = id;
    this.name = name.trim();
    this.tags = normalize(tags);
    this.quantities = [...quantities];
  }

  get totalQuantity() {
    return this.quantities.reduce((sum, value) => sum + value, 0);
  }
}

function normalize(values) {
  const result = [];
  const seen = new Set();

  for (const value of values) {
    if (typeof value !== "string") {
      throw new ArrayOperationError("array elements must be strings");
    }

    const normalized = value.trim().toLowerCase();

    if (normalized && !seen.has(normalized)) {
      seen.add(normalized);
      result.push(normalized);
    }
  }

  return result;
}

function appendUnique(values, value) {
  const normalized = value.trim().toLowerCase();

  if (!normalized) {
    throw new ArrayOperationError("cannot append an empty value");
  }

  return values.includes(normalized)
    ? [...values]
    : [...values, normalized];
}

function arrayDifference(left, right) {
  const rightSet = new Set(right);
  return left.filter((value) => !rightSet.has(value));
}

function arrayIntersection(left, right) {
  const rightSet = new Set(right);
  return [...new Set(left.filter((value) => rightSet.has(value)))];
}

function containsAll(values, required) {
  const available = new Set(values);
  return required.every((value) => available.has(value));
}

function containsAny(values, candidates) {
  const available = new Set(values);
  return candidates.some((value) => available.has(value));
}

function unnest(values) {
  return values.map((value, index) => ({
    position: index + 1,
    value,
  }));
}

function zip(left, right) {
  if (left.length !== right.length) {
    throw new ArrayOperationError("arrays must have equal lengths");
  }

  return left.map((value, index) => ({
    value,
    quantity: right[index],
  }));
}

function flatten(matrix) {
  return matrix.flat();
}

class EventBus {
  constructor() {
    this.listeners = new Map();
  }

  on(eventName, listener) {
    if (!this.listeners.has(eventName)) {
      this.listeners.set(eventName, new Set());
    }

    this.listeners.get(eventName).add(listener);
  }

  emit(eventName, payload) {
    for (const listener of this.listeners.get(eventName) ?? []) {
      listener(payload);
    }
  }
}

async function processInventory(items) {
  /*
   * Promise.all models independent array-oriented operations.
   * A real database implementation should still enforce constraints
   * server-side instead of trusting client validation.
   */
  return Promise.all(
    items.map(async (item) => ({
      id: item.id,
      name: item.name,
      tags: item.tags,
      totalQuantity: item.totalQuantity,
      elements: unnest(item.tags),
    }))
  );
}

async function main() {
  const item = new InventoryItem(
    501,
    "Order Processing API",
    ["API", "backend", "security", "API"],
    [10, 15, 5]
  );

  console.log("Normalized:", item.tags);
  console.log(
    "Append unique:",
    appendUnique(item.tags, "postgresql")
  );
  console.log(
    "Difference:",
    arrayDifference(item.tags, ["api", "security"])
  );
  console.log(
    "Intersection:",
    arrayIntersection(item.tags, ["api", "cloud"])
  );
  console.log(
    "Contains all:",
    containsAll(item.tags, ["api", "backend"])
  );
  console.log(
    "Contains any:",
    containsAny(item.tags, ["database", "security"])
  );
  console.log("Unnested:", unnest(item.tags));
  console.log("Zipped:", zip(item.tags, [10, 15, 5]));
  console.log("Flattened:", flatten([[1, 2], [3], [4, 5]]));

  const events = new EventBus();

  events.on("array.updated", (payload) => {
    console.log("Array update event:", payload);
  });

  const updatedTags = appendUnique(item.tags, "observability");

  events.emit("array.updated", {
    itemId: item.id,
    previous: item.tags,
    current: updatedTags,
  });

  const report = await processInventory([
    item,
    new InventoryItem(
      502,
      "Audit Service",
      ["compliance", "security"],
      [30, 2]
    ),
  ]);

  console.log("Async report:", report);

  try {
    new InventoryItem(0, "Invalid", [], []);
  } catch (error) {
    console.error("Validation error:", error.message);
  }

  try {
    zip(["a"], [1, 2]);
  } catch (error) {
    console.error("Zip error:", error.message);
  }
}

main().catch((error) => {
  console.error("Fatal error:", error);
  process.exitCode = 1;
});
