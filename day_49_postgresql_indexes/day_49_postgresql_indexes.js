"use strict";

/*
 * PostgreSQL Index Access Methods:
 * B-tree, Hash, GIN, GiST, and BRIN
 *
 * This Node.js program complements the Python model by treating index
 * selection as an event-driven query workload. It tracks query predicates,
 * estimates which PostgreSQL access method is structurally appropriate, and
 * emits planner-oriented decisions.
 *
 * No npm packages are required.
 */

const records = [
  {
    id: 1,
    repository: 101,
    status: "open",
    labels: ["postgresql", "database"],
    createdAt: "2026-01-08T10:00:00Z",
    activeRange: ["2026-01-08T10:00:00Z", "2026-01-12T16:00:00Z"]
  },
  {
    id: 2,
    repository: 101,
    status: "merged",
    labels: ["security", "audit"],
    createdAt: "2026-01-15T10:00:00Z",
    activeRange: ["2026-01-15T10:00:00Z", "2026-01-21T14:00:00Z"]
  },
  {
    id: 3,
    repository: 102,
    status: "open",
    labels: ["postgresql", "performance", "gin"],
    createdAt: "2026-02-04T09:30:00Z",
    activeRange: ["2026-02-04T09:30:00Z", "2026-02-11T12:00:00Z"]
  },
  {
    id: 4,
    repository: 103,
    status: "merged",
    labels: ["release", "performance"],
    createdAt: "2026-02-18T11:15:00Z",
    activeRange: ["2026-02-18T11:15:00Z", "2026-02-20T13:00:00Z"]
  },
  {
    id: 5,
    repository: 102,
    status: "open",
    labels: ["security", "postgresql"],
    createdAt: "2026-03-03T08:45:00Z",
    activeRange: ["2026-03-03T08:45:00Z", "2026-03-15T17:00:00Z"]
  }
];

class QueryEventBus {
  #handlers = new Map();

  on(eventName, handler) {
    if (!this.#handlers.has(eventName)) {
      this.#handlers.set(eventName, []);
    }
    this.#handlers.get(eventName).push(handler);
  }

  emit(eventName, payload) {
    for (const handler of this.#handlers.get(eventName) ?? []) {
      handler(payload);
    }
  }
}

class IndexCatalog {
  constructor() {
    this.indexes = [
      {
        name: "idx_pr_repository_btree",
        method: "B-tree",
        column: "repository",
        predicates: ["=", "range", "ORDER BY"]
      },
      {
        name: "idx_pr_repository_hash",
        method: "Hash",
        column: "repository",
        predicates: ["="]
      },
      {
        name: "idx_pr_labels_gin",
        method: "GIN",
        column: "labels",
        predicates: ["@>", "&&"]
      },
      {
        name: "idx_pr_active_range_gist",
        method: "GiST",
        column: "activeRange",
        predicates: ["&&", "@>", "<@", "-|-"]
      },
      {
        name: "idx_pr_created_brin",
        method: "BRIN",
        column: "createdAt",
        predicates: ["range"]
      }
    ];
  }

  findCandidates(predicate) {
    return this.indexes.filter(
      index =>
        index.column === predicate.column &&
        index.predicates.includes(predicate.operator)
    );
  }
}

class QueryPlanner {
  constructor(catalog) {
    this.catalog = catalog;
  }

  choose(predicate) {
    const candidates = this.catalog.findCandidates(predicate);

    if (candidates.length === 0) {
      return {
        method: "Sequential Scan",
        reason: "No modeled index supports this predicate."
      };
    }

    /*
     * B-tree and Hash can both support equality. Prefer B-tree when the
     * workload may also require ordering or range operations because one
     * structure supports a wider family of predicates.
     */
    if (
      predicate.operator === "=" &&
      candidates.some(candidate => candidate.method === "B-tree")
    ) {
      return {
        method: "B-tree",
        reason: "Equality is supported and the B-tree remains useful for ordering and ranges."
      };
    }

    if (predicate.operator === "@>" || predicate.operator === "&&") {
      const specialized = candidates.find(
        candidate => candidate.method === "GIN" || candidate.method === "GiST"
      );

      if (specialized) {
        return {
          method: specialized.method,
          reason:
            specialized.method === "GIN"
              ? "The predicate is a containment/overlap operation over a collection."
              : "The predicate is supported by the range operator class."
        };
      }
    }

    return {
      method: candidates[0].method,
      reason: "The access method supports the requested predicate."
    };
  }
}

class QueryExecutor {
  constructor(rows) {
    this.rows = rows;
  }

  execute(predicate) {
    switch (predicate.column) {
      case "repository":
        return this.rows.filter(row => {
          if (predicate.operator === "=") {
            return row.repository === predicate.value;
          }

          if (predicate.operator === ">=") {
            return row.repository >= predicate.value;
          }

          return false;
        });

      case "labels":
        return this.rows.filter(row => {
          if (predicate.operator === "@>") {
            const required = new Set(predicate.value);
            return predicate.value.every(label => row.labels.includes(label))
              && required.size === predicate.value.length;
          }

          if (predicate.operator === "&&") {
            return predicate.value.some(label => row.labels.includes(label));
          }

          return false;
        });

      case "activeRange": {
        const queryStart = new Date(predicate.value[0]);
        const queryEnd = new Date(predicate.value[1]);

        return this.rows.filter(row => {
          const rowStart = new Date(row.activeRange[0]);
          const rowEnd = new Date(row.activeRange[1]);

          return rowStart <= queryEnd && rowEnd >= queryStart;
        });
      }

      case "createdAt": {
        const lower = new Date(predicate.value[0]);
        const upper = new Date(predicate.value[1]);

        return this.rows.filter(row => {
          const value = new Date(row.createdAt);
          return value >= lower && value <= upper;
        });
      }

      default:
        throw new Error(`Unsupported query column: ${predicate.column}`);
    }
  }
}

function validatePredicate(predicate) {
  const supportedOperators = new Set([
    "=",
    ">=",
    "@>",
    "&&",
    "range"
  ]);

  if (!predicate || typeof predicate !== "object") {
    throw new TypeError("Predicate must be an object.");
  }

  if (!predicate.column || !predicate.operator) {
    throw new Error("Predicate requires column and operator.");
  }

  if (!supportedOperators.has(predicate.operator)) {
    throw new Error(`Unsupported operator: ${predicate.operator}`);
  }
}

async function runQuery(eventBus, planner, executor, predicate) {
  validatePredicate(predicate);

  const plan = planner.choose(predicate);
  const started = performance.now();

  const result = executor.execute(predicate);

  const elapsed = performance.now() - started;

  eventBus.emit("query:planned", {
    predicate,
    plan,
    rowCount: result.length,
    elapsed
  });

  return result;
}

async function main() {
  const bus = new QueryEventBus();
  const catalog = new IndexCatalog();
  const planner = new QueryPlanner(catalog);
  const executor = new QueryExecutor(records);

  bus.on("query:planned", event => {
    console.log(
      `\n${event.predicate.column} ${event.predicate.operator}`,
      `=> ${event.plan.method}`,
      `| ${event.plan.reason}`,
      `| rows=${event.rowCount}`,
      `| ${event.elapsed.toFixed(3)} ms`
    );
  });

  const workload = [
    {
      column: "repository",
      operator: "=",
      value: 102
    },
    {
      column: "labels",
      operator: "@>",
      value: ["postgresql", "performance"]
    },
    {
      column: "labels",
      operator: "&&",
      value: ["security", "audit"]
    },
    {
      column: "activeRange",
      operator: "&&",
      value: ["2026-02-07T00:00:00Z", "2026-02-13T00:00:00Z"]
    },
    {
      column: "createdAt",
      operator: "range",
      value: ["2026-03-01T00:00:00Z", "2026-03-31T23:59:59Z"]
    }
  ];

  console.log("PostgreSQL Index Workload Simulator");

  for (const predicate of workload) {
    const result = await runQuery(bus, planner, executor, predicate);

    console.log(
      "Matching IDs:",
      result.map(row => row.id).join(", ") || "(none)"
    );
  }

  console.log("\nAccess-method distinctions");

  const distinctions = new Map([
    ["B-tree", "General-purpose equality, ordering, and range access."],
    ["Hash", "Equality-focused lookup without ordering semantics."],
    ["GIN", "Inverted indexing for collection/document containment."],
    ["GiST", "Extensible search framework supporting operator classes such as ranges."],
    ["BRIN", "Small summaries of physical block ranges; strongest with correlation."]
  ]);

  for (const [method, description] of distinctions) {
    console.log(`${method}: ${description}`);
  }

  console.log("\nPlanner warning");
  console.log(
    "An index being structurally applicable does not guarantee that PostgreSQL will use it."
  );
  console.log(
    "The real planner compares estimated selectivity, table size, statistics, cache state, and scan costs."
  );

  try {
    await runQuery(bus, planner, executor, {
      column: "labels",
      operator: "=",
      value: ["security"]
    });
  } catch (error) {
    console.log(`\nValidation failure: ${error.message}`);
  }
}

main().catch(error => {
  console.error("Fatal error:", error.message);
  process.exitCode = 1;
});
