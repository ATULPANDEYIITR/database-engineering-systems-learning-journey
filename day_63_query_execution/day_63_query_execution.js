#!/usr/bin/env node
"use strict";

/*
 * Query Execution: operators, plans, and result generation.
 *
 * This implementation models execution as an event-driven pipeline.
 * Operators emit rows through asynchronous generators, allowing the same
 * design to support streaming sources and asynchronous operators.
 */

const crypto = require("node:crypto");
const { performance } = require("node:perf_hooks");

class QueryError extends Error {}
class ValidationError extends QueryError {}
class ExecutionError extends QueryError {}

class Table {
  constructor(name, columns, rows) {
    if (!name || !columns.length) {
      throw new ValidationError("A table requires a name and columns.");
    }

    this.name = name;
    this.columns = Object.freeze([...columns]);
    this.rows = rows.map(row => ({ ...row }));
    this.indexes = new Map();
    this.validate();
  }

  validate() {
    const expected = new Set(this.columns);

    if (expected.size !== this.columns.length) {
      throw new ValidationError(`Duplicate columns in ${this.name}.`);
    }

    for (const row of this.rows) {
      const actual = new Set(Object.keys(row));
      if (actual.size !== expected.size ||
          [...expected].some(column => !actual.has(column))) {
        throw new ValidationError(`Invalid row in ${this.name}.`);
      }
    }
  }

  buildIndex(column) {
    if (!this.columns.includes(column)) {
      throw new ValidationError(`Unknown column ${column}.`);
    }

    const index = new Map();

    this.rows.forEach((row, position) => {
      const value = row[column];
      if (!index.has(value)) index.set(value, []);
      index.get(value).push(position);
    });

    this.indexes.set(column, index);
  }
}

class Operator {
  constructor() {
    this.rowsIn = 0;
    this.rowsOut = 0;
  }

  async *execute() {
    throw new ExecutionError("Operator has no execution implementation.");
  }

  async collect() {
    const output = [];
    for await (const row of this.execute()) {
      output.push(row);
    }
    this.rowsOut = output.length;
    return output;
  }

  explain(indent = 0) {
    throw new ExecutionError("Operator has no plan representation.");
  }
}

class SeqScan extends Operator {
  constructor(table, alias = table.name) {
    super();
    this.table = table;
    this.alias = alias;
  }

  async *execute() {
    for (const sourceRow of this.table.rows) {
      this.rowsIn++;
      const row = {};
      for (const column of this.table.columns) {
        row[`${this.alias}.${column}`] = sourceRow[column];
      }
      yield row;
    }
  }

  explain(indent = 0) {
    return `${" ".repeat(indent)}Seq Scan on ${this.table.name}`;
  }
}

class IndexScan extends Operator {
  constructor(table, column, value, alias = table.name) {
    super();

    if (!table.indexes.has(column)) {
      throw new ValidationError(
        `No index exists for ${table.name}.${column}`
      );
    }

    this.table = table;
    this.column = column;
    this.value = value;
    this.alias = alias;
  }

  async *execute() {
    const index = this.table.indexes.get(this.column);
    const positions = index.get(this.value) || [];

    for (const position of positions) {
      this.rowsIn++;
      const sourceRow = this.table.rows[position];
      const row = {};
      for (const column of this.table.columns) {
        row[`${this.alias}.${column}`] = sourceRow[column];
      }
      yield row;
    }
  }

  explain(indent = 0) {
    return `${" ".repeat(indent)}Index Scan on ${this.table.name} ` +
      `using ${this.column} = ${JSON.stringify(this.value)}`;
  }
}

class Filter extends Operator {
  constructor(child, predicate, description) {
    super();
    this.child = child;
    this.predicate = predicate;
    this.description = description;
  }

  async *execute() {
    for await (const row of this.child.execute()) {
      this.rowsIn++;
      if (this.predicate(row)) yield row;
    }
  }

  explain(indent = 0) {
    return `${" ".repeat(indent)}Filter: ${this.description}\n` +
      this.child.explain(indent + 2);
  }
}

class Project extends Operator {
  constructor(child, expressions) {
    super();
    this.child = child;
    this.expressions = expressions;
  }

  async *execute() {
    for await (const row of this.child.execute()) {
      this.rowsIn++;
      const result = {};

      for (const [name, expression] of Object.entries(this.expressions)) {
        try {
          result[name] = expression(row);
        } catch (error) {
          throw new ExecutionError(
            `Projection failed for ${name}: ${error.message}`
          );
        }
      }

      yield result;
    }
  }

  explain(indent = 0) {
    return `${" ".repeat(indent)}Project: ` +
      `${Object.keys(this.expressions).join(", ")}\n` +
      this.child.explain(indent + 2);
  }
}

class HashJoin extends Operator {
  constructor(left, right, leftKey, rightKey) {
    super();
    this.left = left;
    this.right = right;
    this.leftKey = leftKey;
    this.rightKey = rightKey;
  }

  async *execute() {
    const hash = new Map();

    for await (const row of this.right.execute()) {
      this.rowsIn++;
      const key = row[this.rightKey];
      if (!hash.has(key)) hash.set(key, []);
      hash.get(key).push(row);
    }

    for await (const leftRow of this.left.execute()) {
      this.rowsIn++;
      const matches = hash.get(leftRow[this.leftKey]) || [];

      for (const rightRow of matches) {
        const overlap = Object.keys(leftRow)
          .some(key => Object.hasOwn(rightRow, key));

        if (overlap) {
          throw new ExecutionError("Ambiguous join output column.");
        }

        yield { ...leftRow, ...rightRow };
      }
    }
  }

  explain(indent = 0) {
    return `${" ".repeat(indent)}Hash Join ` +
      `${this.leftKey} = ${this.rightKey}\n` +
      this.left.explain(indent + 2) + "\n" +
      this.right.explain(indent + 2);
  }
}

class Sort extends Operator {
  constructor(child, key, descending = false) {
    super();
    this.child = child;
    this.key = key;
    this.descending = descending;
  }

  async *execute() {
    const rows = [];

    for await (const row of this.child.execute()) {
      this.rowsIn++;
      if (!Object.hasOwn(row, this.key)) {
        throw new ExecutionError(`Unknown sort key ${this.key}.`);
      }
      rows.push(row);
    }

    rows.sort((a, b) => {
      const result = a[this.key] < b[this.key] ? -1 :
        a[this.key] > b[this.key] ? 1 : 0;
      return this.descending ? -result : result;
    });

    yield* rows;
  }

  explain(indent = 0) {
    const direction = this.descending ? "DESC" : "ASC";
    return `${" ".repeat(indent)}Sort: ${this.key} ${direction}\n` +
      this.child.explain(indent + 2);
  }
}

class Limit extends Operator {
  constructor(child, count) {
    super();

    if (!Number.isInteger(count) || count < 0) {
      throw new ValidationError("LIMIT must be a non-negative integer.");
    }

    this.child = child;
    this.count = count;
  }

  async *execute() {
    let emitted = 0;

    for await (const row of this.child.execute()) {
      this.rowsIn++;

      if (emitted >= this.count) break;

      emitted++;
      yield row;
    }
  }

  explain(indent = 0) {
    return `${" ".repeat(indent)}Limit: ${this.count}\n` +
      this.child.explain(indent + 2);
  }
}

function validateQuery(query) {
  if (!["active", "inactive"].includes(query.status)) {
    throw new ValidationError("Unsupported customer status.");
  }

  if (!Number.isFinite(query.minimumTotal) || query.minimumTotal < 0) {
    throw new ValidationError("Minimum total must be non-negative.");
  }

  if (!Number.isInteger(query.limit) || query.limit <= 0) {
    throw new ValidationError("LIMIT must be positive.");
  }
}

function buildPlan(customers, orders, query) {
  validateQuery(query);

  const customerScan = new IndexScan(
    customers,
    "status",
    query.status,
    "c"
  );

  const orderScan = new SeqScan(orders, "o");

  const join = new HashJoin(
    customerScan,
    orderScan,
    "c.id",
    "o.customer_id"
  );

  const filter = new Filter(
    join,
    row => row["o.total"] >= query.minimumTotal,
    `o.total >= ${query.minimumTotal}`
  );

  const project = new Project(filter, {
    customerId: row => row["c.id"],
    customerName: row => row["c.name"],
    orderId: row => row["o.id"],
    orderTotal: row => row["o.total"]
  });

  return new Limit(
    new Sort(project, "orderTotal", true),
    query.limit
  );
}

function queryId(query) {
  return crypto
    .createHash("sha256")
    .update(JSON.stringify(query))
    .digest("hex")
    .slice(0, 12);
}

async function main() {
  const customers = new Table(
    "customers",
    ["id", "name", "status"],
    [
      { id: 1, name: "Asha", status: "active" },
      { id: 2, name: "Bharat", status: "active" },
      { id: 3, name: "Chen", status: "inactive" },
      { id: 4, name: "Divya", status: "active" }
    ]
  );

  const orders = new Table(
    "orders",
    ["id", "customer_id", "total"],
    [
      { id: 101, customer_id: 1, total: 450 },
      { id: 102, customer_id: 1, total: 1200 },
      { id: 103, customer_id: 2, total: 900 },
      { id: 104, customer_id: 3, total: 2500 },
      { id: 105, customer_id: 4, total: 1750 }
    ]
  );

  customers.buildIndex("status");
  orders.buildIndex("customer_id");

  const query = {
    status: "active",
    minimumTotal: 800,
    limit: 3
  };

  const plan = buildPlan(customers, orders, query);

  console.log(`Query ID: ${queryId(query)}`);
  console.log("\nEXECUTION PLAN");
  console.log(plan.explain());

  const started = performance.now();
  const result = await plan.collect();
  const elapsed = performance.now() - started;

  console.log("\nRESULT SET");
  console.table(result);
  console.log(`Rows returned: ${result.length}`);
  console.log(`Execution time: ${elapsed.toFixed(3)} ms`);

  if (
    result.length > query.limit ||
    result.some(row => row.orderTotal < query.minimumTotal)
  ) {
    throw new ExecutionError("Result invariant failed.");
  }

  try {
    buildPlan(customers, orders, {
      status: "unknown",
      minimumTotal: 0,
      limit: 5
    });
  } catch (error) {
    if (!(error instanceof ValidationError)) throw error;
    console.log(`Validation failure handled: ${error.message}`);
  }
}

main().catch(error => {
  console.error(`Query execution failed: ${error.message}`);
  process.exitCode = 1;
});
