"use strict";

/*
 * PostgreSQL JSON/JSONB application model.
 * Run with Node.js 18 or later: node jsonb_workflow.js
 *
 * This file models document validation, path extraction, containment queries,
 * indexing, atomic updates, and event-driven change notifications.
 */

const { EventEmitter } = require("node:events");
const { isDeepStrictEqual } = require("node:util");

class DocumentValidationError extends Error {
  constructor(message) {
    super(message);
    this.name = "DocumentValidationError";
  }
}

function cloneJson(value) {
  let encoded;
  try {
    encoded = JSON.stringify(value);
  } catch {
    throw new DocumentValidationError("Document is not serializable as JSON");
  }

  if (encoded === undefined) {
    throw new DocumentValidationError("Top-level document must be a JSON value");
  }

  return JSON.parse(encoded);
}

function validateJson(value, depth = 0) {
  if (depth > 12) {
    throw new DocumentValidationError("Maximum nesting depth exceeded");
  }

  if (value === null || typeof value === "string" || typeof value === "boolean") {
    return;
  }

  if (typeof value === "number") {
    if (!Number.isFinite(value)) {
      throw new DocumentValidationError("Numbers must be finite");
    }
    return;
  }

  if (Array.isArray(value)) {
    for (const item of value) validateJson(item, depth + 1);
    return;
  }

  if (typeof value === "object" && Object.getPrototypeOf(value) === Object.prototype) {
    for (const [key, item] of Object.entries(value)) {
      if (key === "__proto__" || key === "constructor" || key === "prototype") {
        throw new DocumentValidationError(`Forbidden object key: ${key}`);
      }
      validateJson(item, depth + 1);
    }
    return;
  }

  throw new DocumentValidationError(`Unsupported JSON value: ${typeof value}`);
}

function canonical(value) {
  if (Array.isArray(value)) {
    return `[${value.map(canonical).join(",")}]`;
  }
  if (value && typeof value === "object") {
    const keys = Object.keys(value).sort();
    return `{${keys.map(k => `${JSON.stringify(k)}:${canonical(value[k])}`).join(",")}}`;
  }
  return JSON.stringify(value);
}

function extractPath(document, path) {
  let current = document;
  for (const segment of path) {
    if (current === null || current === undefined) return undefined;
    if (Array.isArray(current)) {
      if (!/^(0|[1-9]\d*)$/.test(String(segment))) return undefined;
      current = current[Number(segment)];
    } else if (typeof current === "object") {
      current = Object.hasOwn(current, segment) ? current[segment] : undefined;
    } else {
      return undefined;
    }
  }
  return current;
}

function containsJson(actual, expected) {
  if (expected === null || typeof expected !== "object") {
    return typeof actual === typeof expected && actual === expected;
  }

  if (Array.isArray(expected)) {
    if (!Array.isArray(actual)) return false;
    return expected.every(item => actual.some(candidate => containsJson(candidate, item)));
  }

  if (Array.isArray(actual) || actual === null || typeof actual !== "object") {
    return false;
  }

  return Object.entries(expected).every(([key, value]) =>
    Object.hasOwn(actual, key) && containsJson(actual[key], value)
  );
}

class JsonDocumentStore extends EventEmitter {
  #documents = new Map();
  #categoryIndex = new Map();
  #attributeIndex = new Map();
  #nextId = 1;

  #indexKey(key, value) {
    return `${key}\u0000${canonical(value)}`;
  }

  #addToIndex(index, key, id) {
    if (!index.has(key)) index.set(key, new Set());
    index.get(key).add(id);
  }

  #removeFromIndex(index, key, id) {
    const ids = index.get(key);
    if (!ids) return;
    ids.delete(id);
    if (ids.size === 0) index.delete(key);
  }

  #indexDocument(document) {
    this.#addToIndex(this.#categoryIndex, document.category, document.id);

    for (const [key, value] of Object.entries(document.attributes)) {
      if (value === null || ["string", "boolean", "number"].includes(typeof value)) {
        this.#addToIndex(
          this.#attributeIndex,
          this.#indexKey(key, value),
          document.id
        );
      }
    }
  }

  #unindexDocument(document) {
    this.#removeFromIndex(this.#categoryIndex, document.category, document.id);

    for (const [key, value] of Object.entries(document.attributes)) {
      if (value === null || ["string", "boolean", "number"].includes(typeof value)) {
        this.#removeFromIndex(
          this.#attributeIndex,
          this.#indexKey(key, value),
          document.id
        );
      }
    }
  }

  create({ name, category, price, attributes, tags = [] }) {
    if (typeof name !== "string" || !name.trim() || name.trim().length > 120) {
      throw new DocumentValidationError("Invalid product name");
    }
    if (typeof category !== "string" || !/^[a-z][a-z0-9_-]{0,49}$/.test(category)) {
      throw new DocumentValidationError("Invalid category");
    }
    if (!Number.isSafeInteger(price) || price < 0) {
      throw new DocumentValidationError("price must be a non-negative integer in cents");
    }
    if (!Array.isArray(tags) || !tags.every(tag => typeof tag === "string")) {
      throw new DocumentValidationError("tags must be strings");
    }
    if (attributes === null || Array.isArray(attributes) ||
        typeof attributes !== "object") {
      throw new DocumentValidationError("attributes must be an object");
    }

    validateJson(attributes);
    const safeAttributes = cloneJson(attributes);

    if (Buffer.byteLength(JSON.stringify(safeAttributes), "utf8") > 16384) {
      throw new DocumentValidationError("Attributes exceed 16 KiB");
    }

    const document = Object.freeze({
      id: this.#nextId++,
      name: name.trim(),
      category,
      price,
      attributes: safeAttributes,
      tags: [...new Set(tags.map(tag => tag.trim().toLowerCase()).filter(Boolean))].sort()
    });

    this.#documents.set(document.id, document);
    this.#indexDocument(document);
    this.emit("created", { id: document.id, category: document.category });
    return document;
  }

  get(id) {
    const document = this.#documents.get(id);
    return document ? cloneJson(document) : null;
  }

  byCategory(category) {
    const ids = this.#categoryIndex.get(category) || new Set();
    return [...ids].sort((a, b) => a - b).map(id => this.get(id));
  }

  byAttribute(key, value) {
    const ids = this.#attributeIndex.get(this.#indexKey(key, value)) || new Set();
    return [...ids].sort((a, b) => a - b).map(id => this.get(id));
  }

  findContaining(required) {
    validateJson(required);
    return [...this.#documents.values()]
      .filter(document => containsJson(document.attributes, required))
      .map(document => this.get(document.id));
  }

  updateAttributes(id, patch) {
    const current = this.#documents.get(id);
    if (!current) throw new DocumentValidationError("Document not found");

    if (patch === null || Array.isArray(patch) || typeof patch !== "object") {
      throw new DocumentValidationError("Patch must be an object");
    }

    validateJson(patch);

    // Build and validate a replacement before changing the stored state.
    const attributes = { ...current.attributes, ...cloneJson(patch) };
    validateJson(attributes);

    if (Buffer.byteLength(JSON.stringify(attributes), "utf8") > 16384) {
      throw new DocumentValidationError("Attributes exceed 16 KiB");
    }

    const replacement = Object.freeze({ ...current, attributes });

    this.#unindexDocument(current);
    this.#documents.set(id, replacement);
    this.#indexDocument(replacement);
    this.emit("updated", { id, changedKeys: Object.keys(patch) });

    return this.get(id);
  }

  path(id, ...segments) {
    const document = this.#documents.get(id);
    return document ? extractPath(document.attributes, segments) : undefined;
  }

  explainIndexUsage() {
    return {
      categoryIndexEntries: this.#categoryIndex.size,
      attributeIndexEntries: this.#attributeIndex.size,
      note: "A real PostgreSQL planner chooses indexes using statistics and query costs."
    };
  }
}

async function main() {
  const store = new JsonDocumentStore();

  store.on("created", event => {
    console.log("Document created:", event);
  });

  store.on("updated", event => {
    console.log("Document updated:", event);
  });

  const laptop = store.create({
    name: "Engineering Laptop",
    category: "electronics",
    price: 129999,
    attributes: {
      brand: "Northstar",
      specs: { ram_gb: 32, storage_gb: 1024 },
      wireless: true,
      ports: ["USB-C", "HDMI"]
    },
    tags: ["developer", "portable", "developer"]
  });

  store.create({
    name: "Operations Monitor",
    category: "electronics",
    price: 34950,
    attributes: {
      brand: "Northstar",
      specs: { ram_gb: 0, storage_gb: 0 },
      wireless: false,
      ports: ["HDMI", "DisplayPort"]
    },
    tags: ["office"]
  });

  console.log("RAM:", store.path(laptop.id, "specs", "ram_gb"));
  console.log("Wireless products:", store.byAttribute("wireless", true).map(p => p.name));
  console.log(
    "32 GB products:",
    store.findContaining({ specs: { ram_gb: 32 } }).map(p => p.name)
  );

  await Promise.resolve();
  store.updateAttributes(2, { wireless: true, warranty_years: 3 });

  console.log("Updated wireless products:", store.byAttribute("wireless", true).map(p => p.name));
  console.log("Index model:", store.explainIndexUsage());

  try {
    store.create({
      name: "Invalid",
      category: "electronics",
      price: -1,
      attributes: {}
    });
  } catch (error) {
    console.log("Rejected invalid document:", error.message);
  }

  if (!isDeepStrictEqual(store.path(laptop.id, "specs"), {
    ram_gb: 32,
    storage_gb: 1024
  })) {
    throw new Error("Path extraction test failed");
  }

  console.log("All assertions passed.");
}

main().catch(error => {
  console.error("Fatal error:", error.message);
  process.exitCode = 1;
});
