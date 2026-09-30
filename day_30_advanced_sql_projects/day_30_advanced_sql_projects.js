'use strict';

/*
Advanced SQL Project
Analytical SQL System Using Complex Queries

This Node.js program complements the Python implementation by treating an
analytical SQL workflow as an event-driven reporting service.

It uses only Node.js built-ins. Because database drivers are not part of the
standard Node.js runtime, the program implements a small in-memory analytical
query model in JavaScript rather than pretending to execute SQL without a
database driver.

The implementation focuses on JavaScript-specific concerns:
- immutable analytical transformations
- event-driven report execution
- asynchronous report orchestration
- validation before aggregation
- reusable metric functions
- ranking and window-style calculations
- cohort construction
- policy-driven report configuration
- failure propagation through Promises
*/

const EventEmitter = require('node:events');

const customers = Object.freeze([
  { id: 1, name: 'Aarav Industries', region: 'North', segment: 'enterprise', signup: '2024-01-05' },
  { id: 2, name: 'Bharat Retail', region: 'North', segment: 'business', signup: '2024-01-15' },
  { id: 3, name: 'Cedar Labs', region: 'West', segment: 'enterprise', signup: '2024-02-03' },
  { id: 4, name: 'Delta Studio', region: 'West', segment: 'business', signup: '2024-02-19' },
  { id: 5, name: 'Epsilon Works', region: 'South', segment: 'consumer', signup: '2024-03-01' },
  { id: 6, name: 'Falcon Systems', region: 'South', segment: 'enterprise', signup: '2024-03-12' },
  { id: 7, name: 'Ganga Foods', region: 'East', segment: 'business', signup: '2024-04-08' },
  { id: 8, name: 'Horizon Media', region: 'East', segment: 'consumer', signup: '2024-04-21' },
  { id: 9, name: 'Indus Analytics', region: 'North', segment: 'business', signup: '2024-05-04' },
  { id: 10, name: 'Jade Health', region: 'West', segment: 'enterprise', signup: '2024-05-18' },
  { id: 11, name: 'Kaveri Design', region: 'South', segment: 'consumer', signup: '2024-06-10' },
  { id: 12, name: 'Lotus Commerce', region: 'East', segment: 'business', signup: '2024-06-25' }
]);

const products = Object.freeze([
  { id: 1, name: 'Data Platform', category: 'Software', cost: 180, price: 500 },
  { id: 2, name: 'Security Suite', category: 'Security', cost: 120, price: 360 },
  { id: 3, name: 'Analytics Pro', category: 'Analytics', cost: 90, price: 280 },
  { id: 4, name: 'Cloud Storage', category: 'Infrastructure', cost: 40, price: 140 },
  { id: 5, name: 'API Gateway', category: 'Infrastructure', cost: 65, price: 190 },
  { id: 6, name: 'Support Plan', category: 'Services', cost: 35, price: 120 }
]);

const orders = Object.freeze([
  { id: 101, customerId: 1, date: '2024-01-20', status: 'completed' },
  { id: 102, customerId: 1, date: '2024-02-20', status: 'completed' },
  { id: 103, customerId: 1, date: '2024-04-10', status: 'completed' },
  { id: 104, customerId: 2, date: '2024-02-02', status: 'completed' },
  { id: 105, customerId: 2, date: '2024-03-14', status: 'completed' },
  { id: 106, customerId: 2, date: '2024-05-17', status: 'completed' },
  { id: 107, customerId: 3, date: '2024-02-20', status: 'completed' },
  { id: 108, customerId: 3, date: '2024-03-22', status: 'completed' },
  { id: 109, customerId: 3, date: '2024-06-05', status: 'completed' },
  { id: 110, customerId: 4, date: '2024-03-01', status: 'completed' },
  { id: 111, customerId: 4, date: '2024-03-18', status: 'refunded' },
  { id: 112, customerId: 4, date: '2024-05-02', status: 'completed' },
  { id: 113, customerId: 5, date: '2024-03-20', status: 'completed' },
  { id: 114, customerId: 5, date: '2024-04-21', status: 'completed' },
  { id: 115, customerId: 6, date: '2024-03-25', status: 'completed' },
  { id: 116, customerId: 6, date: '2024-04-30', status: 'completed' },
  { id: 117, customerId: 6, date: '2024-06-30', status: 'completed' },
  { id: 118, customerId: 7, date: '2024-04-15', status: 'completed' },
  { id: 119, customerId: 7, date: '2024-05-20', status: 'completed' },
  { id: 120, customerId: 8, date: '2024-05-01', status: 'completed' },
  { id: 121, customerId: 9, date: '2024-05-10', status: 'completed' },
  { id: 122, customerId: 9, date: '2024-06-15', status: 'completed' },
  { id: 123, customerId: 10, date: '2024-05-28', status: 'completed' },
  { id: 124, customerId: 10, date: '2024-06-25', status: 'completed' },
  { id: 125, customerId: 11, date: '2024-06-20', status: 'completed' },
  { id: 126, customerId: 12, date: '2024-06-29', status: 'completed' },
  { id: 127, customerId: 1, date: '2024-05-15', status: 'cancelled' },
  { id: 128, customerId: 2, date: '2024-06-18', status: 'completed' },
  { id: 129, customerId: 3, date: '2024-05-15', status: 'completed' },
  { id: 130, customerId: 6, date: '2024-05-15', status: 'completed' }
]);

const itemRows = Object.freeze([
  [101, 1, 2, 480, 0.04], [101, 6, 2, 110, 0],
  [102, 3, 3, 260, 0.05],
  [103, 2, 2, 340, 0.02], [103, 4, 5, 130, 0],
  [104, 3, 2, 270, 0],
  [105, 5, 3, 180, 0.05], [105, 6, 1, 115, 0],
  [106, 1, 1, 490, 0],
  [107, 1, 4, 450, 0.10], [107, 3, 2, 270, 0],
  [108, 2, 3, 350, 0.03],
  [109, 3, 5, 250, 0.08],
  [110, 4, 4, 135, 0],
  [111, 5, 2, 185, 0],
  [112, 6, 5, 110, 0.05],
  [113, 4, 2, 140, 0],
  [114, 3, 2, 275, 0],
  [115, 1, 2, 490, 0],
  [116, 2, 2, 350, 0], [116, 6, 2, 115, 0],
  [117, 1, 1, 500, 0],
  [118, 5, 4, 180, 0.05],
  [119, 6, 3, 120, 0], [119, 4, 3, 135, 0],
  [120, 3, 2, 280, 0],
  [121, 2, 3, 355, 0.02],
  [122, 5, 2, 190, 0],
  [123, 1, 3, 470, 0.04],
  [124, 2, 2, 360, 0],
  [125, 4, 5, 125, 0],
  [126, 6, 2, 115, 0],
  [127, 1, 1, 500, 0],
  [128, 3, 4, 260, 0.07],
  [129, 2, 1, 350, 0],
  [130, 1, 1, 500, 0], [130, 5, 2, 185, 0]
]);

function normalizeItems(rows) {
  return rows.map(([orderId, productId, quantity, unitPrice, discount]) => ({
    orderId,
    productId,
    quantity,
    unitPrice,
    discount
  }));
}

const items = Object.freeze(normalizeItems(itemRows));

const byId = (records) => new Map(records.map(record => [record.id, record]));

const customerById = byId(customers);
const productById = byId(products);
const orderById = byId(orders);

function validateData() {
  const errors = [];

  for (const order of orders) {
    if (!customerById.has(order.customerId)) {
      errors.push(`Order ${order.id} references missing customer`);
    }

    if (!['completed', 'cancelled', 'refunded'].includes(order.status)) {
      errors.push(`Order ${order.id} has invalid status`);
    }
  }

  for (const item of items) {
    if (!orderById.has(item.orderId)) {
      errors.push(`Item references missing order ${item.orderId}`);
    }

    if (!productById.has(item.productId)) {
      errors.push(`Item references missing product ${item.productId}`);
    }

    if (item.quantity <= 0) {
      errors.push(`Item ${item.productId} has non-positive quantity`);
    }

    if (item.discount < 0 || item.discount > 1) {
      errors.push(`Item ${item.productId} has invalid discount`);
    }
  }

  if (errors.length > 0) {
    throw new Error(`Data validation failed:\n${errors.join('\n')}`);
  }
}

function revenueForItem(item) {
  return item.quantity * item.unitPrice * (1 - item.discount);
}

function marginForItem(item) {
  const product = productById.get(item.productId);
  return item.quantity * (
    item.unitPrice * (1 - item.discount) - product.cost
  );
}

function completedItems() {
  return items.filter(item => orderById.get(item.orderId).status === 'completed');
}

function groupBy(records, keyFunction) {
  const groups = new Map();

  for (const record of records) {
    const key = keyFunction(record);
    if (!groups.has(key)) {
      groups.set(key, []);
    }
    groups.get(key).push(record);
  }

  return groups;
}

function monthOf(isoDate) {
  return isoDate.slice(0, 7);
}

function aggregateRevenueByMonth() {
  const totals = new Map();

  for (const item of completedItems()) {
    const order = orderById.get(item.orderId);
    const month = monthOf(order.date);
    totals.set(month, (totals.get(month) ?? 0) + revenueForItem(item));
  }

  return [...totals.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([month, revenue]) => ({
      month,
      revenue: Number(revenue.toFixed(2))
    }));
}

function calculateMonthlyWindows(monthlyRows) {
  let cumulative = 0;

  return monthlyRows.map((row, index) => {
    cumulative += row.revenue;

    const previous = monthlyRows[index - 1]?.revenue ?? null;
    const growth = previous === null
      ? null
      : Number(((row.revenue - previous) / previous * 100).toFixed(2));

    const window = monthlyRows
      .slice(Math.max(0, index - 2), index + 1)
      .map(entry => entry.revenue);

    const rollingAverage =
      window.reduce((sum, value) => sum + value, 0) / window.length;

    return {
      ...row,
      previousRevenue: previous,
      growthPercent: growth,
      rollingThreeMonthAverage: Number(rollingAverage.toFixed(2)),
      cumulativeRevenue: Number(cumulative.toFixed(2))
    };
  });
}

function customerRevenue() {
  const totals = new Map();

  for (const item of completedItems()) {
    const order = orderById.get(item.orderId);
    const current = totals.get(order.customerId) ?? {
      customerId: order.customerId,
      revenue: 0,
      margin: 0,
      orders: new Set(),
      lastOrder: null
    };

    current.revenue += revenueForItem(item);
    current.margin += marginForItem(item);
    current.orders.add(order.id);

    if (current.lastOrder === null || order.date > current.lastOrder) {
      current.lastOrder = order.date;
    }

    totals.set(order.customerId, current);
  }

  return [...totals.values()]
    .map(value => ({
      customerId: value.customerId,
      customerName: customerById.get(value.customerId).name,
      segment: customerById.get(value.customerId).segment,
      region: customerById.get(value.customerId).region,
      revenue: Number(value.revenue.toFixed(2)),
      margin: Number(value.margin.toFixed(2)),
      orders: value.orders.size,
      lastOrder: value.lastOrder
    }))
    .sort((a, b) => b.revenue - a.revenue);
}

function rankCustomers(rows) {
  let previousRevenue = null;
  let rank = 0;

  return rows.map((row, index) => {
    if (row.revenue !== previousRevenue) {
      rank = index + 1;
      previousRevenue = row.revenue;
    }

    return {
      ...row,
      rank,
      revenueSharePercent: Number(
        (row.revenue / rows.reduce((sum, value) => sum + value.revenue, 0) * 100)
          .toFixed(2)
      )
    };
  });
}

function productPareto() {
  const totals = new Map();

  for (const item of completedItems()) {
    const product = productById.get(item.productId);
    const current = totals.get(product.id) ?? {
      productId: product.id,
      productName: product.name,
      category: product.category,
      revenue: 0
    };

    current.revenue += revenueForItem(item);
    totals.set(product.id, current);
  }

  const rows = [...totals.values()]
    .sort((a, b) => b.revenue - a.revenue);

  const totalRevenue = rows.reduce((sum, row) => sum + row.revenue, 0);
  let cumulative = 0;

  return rows.map(row => {
    cumulative += row.revenue;

    return {
      ...row,
      revenue: Number(row.revenue.toFixed(2)),
      revenueSharePercent: Number(
        (row.revenue / totalRevenue * 100).toFixed(2)
      ),
      cumulativeSharePercent: Number(
        (cumulative / totalRevenue * 100).toFixed(2)
      )
    };
  });
}

function cohortRetention() {
  const firstPurchase = new Map();

  for (const order of orders.filter(order => order.status === 'completed')) {
    const current = firstPurchase.get(order.customerId);

    if (!current || order.date < current) {
      firstPurchase.set(order.customerId, order.date);
    }
  }

  const activity = new Map();

  for (const order of orders.filter(order => order.status === 'completed')) {
    if (!activity.has(order.customerId)) {
      activity.set(order.customerId, new Set());
    }

    activity.get(order.customerId).add(monthOf(order.date));
  }

  const cohortGroups = new Map();

  for (const [customerId, firstDate] of firstPurchase) {
    const cohort = monthOf(firstDate);

    if (!cohortGroups.has(cohort)) {
      cohortGroups.set(cohort, []);
    }

    cohortGroups.get(cohort).push(customerId);
  }

  const output = [];

  for (const [cohort, cohortCustomers] of cohortGroups) {
    const cohortSize = cohortCustomers.length;
    const activeCounts = new Map();

    for (const customerId of cohortCustomers) {
      for (const month of activity.get(customerId) ?? []) {
        activeCounts.set(month, (activeCounts.get(month) ?? 0) + 1);
      }
    }

    for (const [month, activeCustomers] of activeCounts) {
      output.push({
        cohortMonth: cohort,
        activityMonth: month,
        activeCustomers,
        cohortSize,
        retentionPercent: Number(
          (activeCustomers / cohortSize * 100).toFixed(2)
        )
      });
    }
  }

  return output.sort((a, b) =>
    a.cohortMonth.localeCompare(b.cohortMonth) ||
    a.activityMonth.localeCompare(b.activityMonth)
  );
}

function rfmSegmentation() {
  const rows = customerRevenue();

  if (rows.length === 0) {
    return [];
  }

  const scoreAscending = (records, selector) => {
    const sorted = [...records].sort(
      (a, b) => selector(a) - selector(b)
    );

    const scores = new Map();
    const bucketSize = Math.max(1, Math.ceil(sorted.length / 4));

    sorted.forEach((record, index) => {
      scores.set(record.customerId, Math.min(
        4,
        Math.floor(index / bucketSize) + 1
      ));
    });

    return scores;
  };

  const recencyScores = scoreAscending(
    rows,
    row => Date.parse(row.lastOrder)
  );

  const frequencyScores = scoreAscending(
    rows,
    row => row.orders
  );

  const monetaryScores = scoreAscending(
    rows,
    row => row.revenue
  );

  return rows.map(row => {
    const recency = recencyScores.get(row.customerId);
    const frequency = frequencyScores.get(row.customerId);
    const monetary = monetaryScores.get(row.customerId);
    const score = recency + frequency + monetary;

    let segment = 'standard';

    if (recency >= 3 && frequency >= 3 && monetary >= 3) {
      segment = 'high-value-active';
    } else if (recency >= 3 && frequency >= 2) {
      segment = 'active-growth';
    } else if (recency <= 2 && monetary >= 3) {
      segment = 'valuable-at-risk';
    }

    return {
      customerName: row.customerName,
      recencyScore: recency,
      frequencyScore: frequency,
      monetaryScore: monetary,
      rfmScore: score,
      segment
    };
  }).sort((a, b) => b.rfmScore - a.rfmScore);
}

class AnalyticalReportService extends EventEmitter {
  constructor() {
    super();

    this.reports = new Map([
      ['monthly-revenue', aggregateRevenueByMonth],
      ['customer-ranking', () => rankCustomers(customerRevenue())],
      ['product-pareto', productPareto],
      ['cohort-retention', cohortRetention],
      ['rfm-segmentation', rfmSegmentation]
    ]);
  }

  availableReports() {
    return [...this.reports.keys()];
  }

  async run(name) {
    if (!this.reports.has(name)) {
      throw new Error(`Unknown analytical report: ${name}`);
    }

    this.emit('reportStarted', name);

    try {
      // Promise.resolve creates an asynchronous boundary without requiring
      // an unnecessary external package or fake network dependency.
      const result = await Promise.resolve().then(() => this.reports.get(name)());

      this.emit('reportCompleted', {
        name,
        rowCount: result.length
      });

      return result;
    } catch (error) {
      this.emit('reportFailed', {
        name,
        message: error.message
      });

      throw error;
    }
  }

  async runMany(names) {
    const unknown = names.filter(name => !this.reports.has(name));

    if (unknown.length > 0) {
      throw new Error(`Unknown reports: ${unknown.join(', ')}`);
    }

    // Promise.all preserves input order while allowing independent analytical
    // reports to execute concurrently when the backing database supports it.
    return Promise.all(names.map(name => this.run(name)));
  }
}

function printTable(title, rows, limit = 12) {
  console.log(`\n=== ${title} ===`);

  if (rows.length === 0) {
    console.log('(no rows)');
    return;
  }

  const visible = rows.slice(0, limit);
  const columns = Object.keys(visible[0]);

  console.table(visible.map(row => {
    const copy = {};

    for (const column of columns) {
      copy[column] = row[column];
    }

    return copy;
  }));

  if (rows.length > limit) {
    console.log(`... ${rows.length - limit} additional rows omitted`);
  }
}

function printCategoryMarginAnalysis() {
  const categoryTotals = new Map();

  for (const item of completedItems()) {
    const product = productById.get(item.productId);

    const current = categoryTotals.get(product.category) ?? {
      category: product.category,
      revenue: 0,
      margin: 0
    };

    current.revenue += revenueForItem(item);
    current.margin += marginForItem(item);
    categoryTotals.set(product.category, current);
  }

  const rows = [...categoryTotals.values()]
    .map(row => ({
      category: row.category,
      revenue: Number(row.revenue.toFixed(2)),
      grossMargin: Number(row.margin.toFixed(2)),
      marginPercent: Number(
        (row.margin / row.revenue * 100).toFixed(2)
      )
    }))
    .sort((a, b) => b.revenue - a.revenue);

  printTable('Category revenue and margin', rows);
}

async function main() {
  validateData();

  const service = new AnalyticalReportService();

  service.on('reportStarted', name => {
    console.log(`Running report: ${name}`);
  });

  service.on('reportCompleted', event => {
    console.log(
      `Completed ${event.name}: ${event.rowCount} analytical rows`
    );
  });

  service.on('reportFailed', event => {
    console.error(
      `Failed ${event.name}: ${event.message}`
    );
  });

  const [monthly, customersRanked, pareto, cohorts, rfm] =
    await service.runMany([
      'monthly-revenue',
      'customer-ranking',
      'product-pareto',
      'cohort-retention',
      'rfm-segmentation'
    ]);

  printTable(
    'Monthly revenue with window-style metrics',
    calculateMonthlyWindows(monthly)
  );

  printTable(
    'Customer revenue ranking',
    customersRanked
  );

  printTable(
    'Product Pareto analysis',
    pareto
  );

  printTable(
    'Cohort retention',
    cohorts,
    30
  );

  printTable(
    'RFM segmentation',
    rfm
  );

  printCategoryMarginAnalysis();

  const northCustomers = customersRanked.filter(
    row => row.region === 'North'
  );

  printTable(
    'Reusable filtered analytical view: North region',
    northCustomers
  );

  try {
    await service.run('missing-report');
  } catch (error) {
    console.log(`Expected report validation error: ${error.message}`);
  }
}

main().catch(error => {
  console.error(`Fatal analytical pipeline error: ${error.message}`);
  process.exitCode = 1;
});
