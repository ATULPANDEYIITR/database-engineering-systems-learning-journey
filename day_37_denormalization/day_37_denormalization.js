/**
 * Denormalization: why and when to denormalize.
 *
 * This Node.js-compatible program models:
 *   - normalized transactional data
 *   - a denormalized read model
 *   - event-driven materialization
 *   - stale-read detection
 *   - reconciliation
 *   - policy-based decisions about denormalization
 *
 * Run with:
 *   node denormalization.js
 */

"use strict";

const { performance } = require("node:perf_hooks");

const customers = new Map([
  [1, { customerId: 1, name: "Aarav Mehta", region: "North" }],
  [2, { customerId: 2, name: "Priya Nair", region: "South" }],
  [3, { customerId: 3, name: "Kabir Singh", region: "North" }],
  [4, { customerId: 4, name: "Meera Shah", region: "West" }]
]);

const products = new Map([
  [101, { productId: 101, name: "Mechanical Keyboard", category: "Peripherals", unitPrice: 89.99 }],
  [102, { productId: 102, name: "USB-C Dock", category: "Peripherals", unitPrice: 129.50 }],
  [103, { productId: 103, name: "27-inch Monitor", category: "Displays", unitPrice: 279.00 }],
  [104, { productId: 104, name: "Laptop Stand", category: "Accessories", unitPrice: 45.00 }],
  [105, { productId: 105, name: "Noise-Cancelling Headset", category: "Audio", unitPrice: 159.95 }]
]);

const orders = new Map([
  [5001, { orderId: 5001, customerId: 1, orderDate: "2026-09-01", status: "SHIPPED" }],
  [5002, { orderId: 5002, customerId: 2, orderDate: "2026-09-02", status: "PROCESSING" }],
  [5003, { orderId: 5003, customerId: 1, orderDate: "2026-09-03", status: "DELIVERED" }],
  [5004, { orderId: 5004, customerId: 3, orderDate: "2026-09-04", status: "SHIPPED" }],
  [5005, { orderId: 5005, customerId: 4, orderDate: "2026-09-05", status: "CANCELLED" }]
]);

const orderLines = [
  { orderId: 5001, productId: 101, quantity: 1 },
  { orderId: 5001, productId: 103, quantity: 2 },
  { orderId: 5002, productId: 102, quantity: 1 },
  { orderId: 5002, productId: 104, quantity: 2 },
  { orderId: 5003, productId: 105, quantity: 1 },
  { orderId: 5003, productId: 101, quantity: 2 },
  { orderId: 5004, productId: 103, quantity: 1 },
  { orderId: 5004, productId: 104, quantity: 1 },
  { orderId: 5005, productId: 102, quantity: 1 }
];

function roundMoney(value) {
  return Math.round((value + Number.EPSILON) * 100) / 100;
}

function linesForOrder(orderId) {
  return orderLines.filter((line) => line.orderId === orderId);
}

function calculateNormalizedSummary(orderId) {
  const order = orders.get(orderId);

  if (!order) {
    throw new Error(`Order ${orderId} does not exist.`);
  }

  const customer = customers.get(order.customerId);

  if (!customer) {
    throw new Error(`Customer ${order.customerId} does not exist.`);
  }

  let totalAmount = 0;
  let itemCount = 0;

  for (const line of linesForOrder(orderId)) {
    const product = products.get(line.productId);

    if (!product) {
      throw new Error(`Product ${line.productId} does not exist.`);
    }

    if (!Number.isInteger(line.quantity) || line.quantity <= 0) {
      throw new Error(`Invalid quantity for product ${line.productId}.`);
    }

    totalAmount += product.unitPrice * line.quantity;
    itemCount += line.quantity;
  }

  return {
    orderId,
    customerId: customer.customerId,
    customerName: customer.name,
    region: customer.region,
    orderDate: order.orderDate,
    status: order.status,
    itemCount,
    totalAmount: roundMoney(totalAmount)
  };
}

function materializeReadModel() {
  const readModel = new Map();

  for (const orderId of orders.keys()) {
    readModel.set(orderId, calculateNormalizedSummary(orderId));
  }

  return readModel;
}

function printReadModel(readModel) {
  for (const row of readModel.values()) {
    console.log(
      `Order ${row.orderId} | ${row.customerName} | ` +
      `${row.region} | ${row.status} | ${row.totalAmount.toFixed(2)}`
    );
  }
}

function createEventBus() {
  const handlers = new Map();

  return {
    on(eventName, handler) {
      if (!handlers.has(eventName)) {
        handlers.set(eventName, []);
      }
      handlers.get(eventName).push(handler);
    },

    emit(eventName, payload) {
      for (const handler of handlers.get(eventName) ?? []) {
        handler(payload);
      }
    }
  };
}

class ReadModelProjector {
  constructor(readModel) {
    this.readModel = readModel;
    this.version = 0;
    this.updatedAt = null;
  }

  refreshOrder(orderId) {
    const summary = calculateNormalizedSummary(orderId);
    this.readModel.set(orderId, summary);
    this.version += 1;
    this.updatedAt = new Date();
  }

  refreshAll() {
    for (const orderId of orders.keys()) {
      this.refreshOrder(orderId);
    }
  }
}

function reconcileRow(row) {
  const currentSource = calculateNormalizedSummary(row.orderId);

  return {
    orderId: row.orderId,
    consistent:
      row.customerId === currentSource.customerId &&
      row.customerName === currentSource.customerName &&
      row.region === currentSource.region &&
      row.status === currentSource.status &&
      row.itemCount === currentSource.itemCount &&
      row.totalAmount === currentSource.totalAmount,
    storedTotal: row.totalAmount,
    sourceTotal: currentSource.totalAmount
  };
}

function demonstrateStaleness() {
  const readModel = materializeReadModel();

  console.log("\n=== STALE DENORMALIZED VALUE ===");
  console.log(`Before source update: ${readModel.get(5001).customerName}`);

  customers.set(1, {
    customerId: 1,
    name: "Aarav Mehta Kumar",
    region: "North"
  });

  console.log(`Source value: ${customers.get(1).name}`);
  console.log(`Read-model value: ${readModel.get(5001).customerName}`);

  const projector = new ReadModelProjector(readModel);
  projector.refreshOrder(5001);

  console.log(`After refresh: ${readModel.get(5001).customerName}`);
}

function demonstrateEventDrivenProjection() {
  console.log("\n=== EVENT-DRIVEN MATERIALIZATION ===");

  const readModel = materializeReadModel();
  const projector = new ReadModelProjector(readModel);
  const bus = createEventBus();

  bus.on("customer.updated", ({ customerId }) => {
    for (const order of orders.values()) {
      if (order.customerId === customerId) {
        projector.refreshOrder(order.orderId);
      }
    }
  });

  customers.set(2, {
    customerId: 2,
    name: "Priya Nair",
    region: "South"
  });

  bus.emit("customer.updated", { customerId: 2 });

  console.log(
    `Projection version: ${projector.version}, ` +
    `updated: ${projector.updatedAt.toISOString()}`
  );
}

function buildDashboard(readModel) {
  const dashboard = new Map();

  for (const row of readModel.values()) {
    if (row.status === "CANCELLED") {
      continue;
    }

    if (!dashboard.has(row.region)) {
      dashboard.set(row.region, {
        orders: 0,
        units: 0,
        revenue: 0
      });
    }

    const region = dashboard.get(row.region);
    region.orders += 1;
    region.units += row.itemCount;
    region.revenue = roundMoney(region.revenue + row.totalAmount);
  }

  return dashboard;
}

function demonstrateReadHeavyQuery() {
  const readModel = materializeReadModel();

  console.log("\n=== READ-OPTIMIZED DASHBOARD ===");

  for (const [region, values] of buildDashboard(readModel)) {
    console.log(
      `${region}: orders=${values.orders}, ` +
      `units=${values.units}, revenue=${values.revenue.toFixed(2)}`
    );
  }
}

function demonstrateCorruptionDetection() {
  const readModel = materializeReadModel();
  const row = readModel.get(5003);

  row.totalAmount = roundMoney(row.totalAmount + 100);

  console.log("\n=== RECONCILIATION ===");
  console.log(reconcileRow(row));
}

function benchmark(iterations = 10000) {
  const readModel = materializeReadModel();

  const normalizedStart = performance.now();

  for (let i = 0; i < iterations; i += 1) {
    for (const orderId of orders.keys()) {
      calculateNormalizedSummary(orderId);
    }
  }

  const normalizedDuration = performance.now() - normalizedStart;

  const denormalizedStart = performance.now();

  for (let i = 0; i < iterations; i += 1) {
    for (const orderId of orders.keys()) {
      readModel.get(orderId).totalAmount;
    }
  }

  const denormalizedDuration = performance.now() - denormalizedStart;

  console.log("\n=== LOCAL LOOKUP EXPERIMENT ===");
  console.log(`Normalized reconstruction: ${normalizedDuration.toFixed(2)} ms`);
  console.log(`Denormalized lookup:       ${denormalizedDuration.toFixed(2)} ms`);
  console.log(
    "This measures application-level object access, not database performance. " +
    "A real database benchmark must include query planning, indexes, I/O, " +
    "network latency, concurrency, and realistic data volume."
  );
}

function evaluateScenario(scenario) {
  const {
    readFrequency,
    writeFrequency,
    joinCost,
    consistencyTolerance,
    historicalSnapshot
  } = scenario;

  if (readFrequency < 0 || writeFrequency < 0 || joinCost < 0) {
    throw new RangeError("Frequency and cost values cannot be negative.");
  }

  if (consistencyTolerance < 0 || consistencyTolerance > 1) {
    throw new RangeError("Consistency tolerance must be between 0 and 1.");
  }

  if (historicalSnapshot) {
    return "Denormalization can preserve an intentional historical snapshot.";
  }

  if (
    readFrequency > writeFrequency * 5 &&
    joinCost >= 3 &&
    consistencyTolerance >= 0.5
  ) {
    return "Denormalization is a strong candidate after benchmarking.";
  }

  return "Keep the normalized model until measurements justify duplication.";
}

function demonstrateDecisionMatrix() {
  console.log("\n=== DENORMALIZATION DECISION MODEL ===");

  const scenarios = [
    {
      name: "Operational dashboard",
      readFrequency: 100,
      writeFrequency: 10,
      joinCost: 5,
      consistencyTolerance: 0.8,
      historicalSnapshot: false
    },
    {
      name: "Customer profile",
      readFrequency: 10,
      writeFrequency: 20,
      joinCost: 1,
      consistencyTolerance: 0,
      historicalSnapshot: false
    },
    {
      name: "Invoice history",
      readFrequency: 40,
      writeFrequency: 2,
      joinCost: 4,
      consistencyTolerance: 0.9,
      historicalSnapshot: true
    }
  ];

  for (const scenario of scenarios) {
    console.log(`${scenario.name}: ${evaluateScenario(scenario)}`);
  }
}

function main() {
  console.log("=== NORMALIZED QUERY ===");
  console.log(calculateNormalizedSummary(5001));

  console.log("\n=== DENORMALIZED READ MODEL ===");
  printReadModel(materializeReadModel());

  demonstrateStaleness();
  demonstrateEventDrivenProjection();
  demonstrateReadHeavyQuery();
  demonstrateCorruptionDetection();
  demonstrateDecisionMatrix();
  benchmark();
}

main();
