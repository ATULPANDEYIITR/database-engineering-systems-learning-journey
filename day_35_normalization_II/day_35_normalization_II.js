"use strict";

/*
 * Normalization II: 1NF, 2NF, and 3NF
 *
 * This Node.js program models an order-management dataset and progressively
 * transforms it from a repeating-group representation into a 3NF design.
 *
 * Run:
 *   node normalization_ii.js
 */

const deepClone = (value) => JSON.parse(JSON.stringify(value));

function printTitle(title) {
  console.log(`\n${"=".repeat(78)}\n${title}\n${"=".repeat(78)}`);
}

function printTable(rows, columns) {
  if (rows.length === 0) {
    console.log("(no rows)");
    return;
  }

  const widths = Object.fromEntries(
    columns.map((column) => [
      column,
      Math.max(
        column.length,
        ...rows.map((row) => String(row[column] ?? "").length)
      ),
    ])
  );

  console.log(
    columns.map((column) => column.padEnd(widths[column])).join(" | ")
  );
  console.log(columns.map((column) => "-".repeat(widths[column])).join("-+-"));

  for (const row of rows) {
    console.log(
      columns
        .map((column) => String(row[column] ?? "").padEnd(widths[column]))
        .join(" | ")
    );
  }
}

function assertUnique(rows, keyColumns) {
  const seen = new Set();

  for (const row of rows) {
    const key = keyColumns.map((column) => row[column]).join("\u0001");

    if (seen.has(key)) {
      throw new Error(
        `Duplicate key (${keyColumns.join(", ")}) for values ${key}`
      );
    }

    seen.add(key);
  }
}

function containsNestedValue(value) {
  return (
    Array.isArray(value) ||
    (value !== null && typeof value === "object")
  );
}

function findNonAtomicValues(rows) {
  const violations = [];

  rows.forEach((row, rowIndex) => {
    for (const [column, value] of Object.entries(row)) {
      if (containsNestedValue(value)) {
        violations.push({
          row: rowIndex + 1,
          column,
          value,
        });
      }
    }
  });

  return violations;
}

function createNon1NFOrders() {
  return [
    {
      orderId: 1001,
      orderDate: "2026-10-01",
      customerId: "C001",
      customerName: "Asha Rao",
      customerCity: "Lucknow",
      products: [
        { productId: "P101", productName: "Keyboard", quantity: 2 },
        { productId: "P102", productName: "Mouse", quantity: 1 },
      ],
    },
    {
      orderId: 1002,
      orderDate: "2026-10-02",
      customerId: "C002",
      customerName: "Rohan Mehta",
      customerCity: "Delhi",
      products: [
        { productId: "P101", productName: "Keyboard", quantity: 1 },
      ],
    },
  ];
}

function convertTo1NF(non1NFRows) {
  const result = [];

  for (const order of non1NFRows) {
    for (const product of order.products) {
      result.push({
        orderId: order.orderId,
        orderDate: order.orderDate,
        customerId: order.customerId,
        customerName: order.customerName,
        customerCity: order.customerCity,
        productId: product.productId,
        productName: product.productName,
        quantity: product.quantity,
      });
    }
  }

  return result;
}

function dependencyHolds(rows, determinant, dependent) {
  const observed = new Map();

  for (const row of rows) {
    const determinantKey = determinant.map((column) => row[column]).join("\u0001");
    const dependentValue = row[dependent];

    if (observed.has(determinantKey)) {
      if (observed.get(determinantKey) !== dependentValue) {
        return false;
      }
    } else {
      observed.set(determinantKey, dependentValue);
    }
  }

  return true;
}

function projectDistinct(rows, columns, keyColumns) {
  const result = [];
  const byKey = new Map();

  for (const row of rows) {
    const projected = Object.fromEntries(
      columns.map((column) => [column, row[column]])
    );

    const key = keyColumns.map((column) => projected[column]).join("\u0001");

    if (byKey.has(key)) {
      const existing = byKey.get(key);
      if (JSON.stringify(existing) !== JSON.stringify(projected)) {
        throw new Error(
          `Projection exposes a functional-dependency violation for ${key}`
        );
      }
      continue;
    }

    byKey.set(key, projected);
    result.push(projected);
  }

  return result;
}

function demonstrate1NF(rows) {
  printTitle("FIRST NORMAL FORM: ATOMIC VALUES");

  const source = createNon1NFOrders();
  const violations = findNonAtomicValues(source);

  console.log("Repeating-group violations:");
  for (const violation of violations) {
    console.log(
      `  row ${violation.row}, column ${violation.column}:`,
      JSON.stringify(violation.value)
    );
  }

  console.log("\nFlattened 1NF relation:");
  printTable(rows, [
    "orderId",
    "productId",
    "quantity",
    "productName",
    "customerId",
  ]);

  const remainingViolations = findNonAtomicValues(rows);
  console.log(
    `\nAtomic-value validation: ${
      remainingViolations.length === 0 ? "PASS" : "FAIL"
    }`
  );

  assertUnique(rows, ["orderId", "productId"]);
  console.log("Composite candidate key: (orderId, productId).");
}

function decomposeTo2NF(rows) {
  printTitle("SECOND NORMAL FORM: REMOVE PARTIAL DEPENDENCIES");

  console.log("The 1NF key is (orderId, productId).");
  console.log("Partial dependency: orderId -> orderDate.");
  console.log("Partial dependency: orderId -> customerId.");
  console.log("Partial dependency: productId -> productName.");
  console.log(
    "The quantity depends on the complete order/product combination."
  );

  const orders = projectDistinct(
    rows,
    ["orderId", "orderDate", "customerId", "customerName", "customerCity"],
    ["orderId"]
  );

  const products = projectDistinct(
    rows,
    ["productId", "productName"],
    ["productId"]
  );

  const orderItems = rows.map((row) => ({
    orderId: row.orderId,
    productId: row.productId,
    quantity: row.quantity,
  }));

  assertUnique(orderItems, ["orderId", "productId"]);

  console.log("\nOrders:");
  printTable(orders, [
    "orderId",
    "orderDate",
    "customerId",
    "customerName",
    "customerCity",
  ]);

  console.log("\nProducts:");
  printTable(products, ["productId", "productName"]);

  console.log("\nOrderItems:");
  printTable(orderItems, ["orderId", "productId", "quantity"]);

  return { orders, products, orderItems };
}

function decomposeTo3NF(orders) {
  printTitle("THIRD NORMAL FORM: REMOVE TRANSITIVE DEPENDENCIES");

  console.log("In Orders, orderId -> customerId.");
  console.log("In customer data, customerId -> customerName, customerCity.");
  console.log(
    "Therefore customerName and customerCity are transitively dependent "
    + "on orderId."
  );

  const customers = projectDistinct(
    orders,
    ["customerId", "customerName", "customerCity"],
    ["customerId"]
  );

  const normalizedOrders = orders.map((order) => ({
    orderId: order.orderId,
    orderDate: order.orderDate,
    customerId: order.customerId,
  }));

  assertUnique(customers, ["customerId"]);
  assertUnique(normalizedOrders, ["orderId"]);

  console.log("\nCustomers:");
  printTable(customers, ["customerId", "customerName", "customerCity"]);

  console.log("\nOrders:");
  printTable(normalizedOrders, ["orderId", "orderDate", "customerId"]);

  return { customers, orders: normalizedOrders };
}

class RepositoryStyleRelation {
  constructor(name, rows, keyColumns) {
    this.name = name;
    this.rows = rows;
    this.keyColumns = keyColumns;
  }

  validate() {
    assertUnique(this.rows, this.keyColumns);
    return true;
  }

  findByKey(values) {
    return this.rows.find((row) =>
      this.keyColumns.every(
        (column, index) => row[column] === values[index]
      )
    );
  }
}

function createRepository() {
  const source = createNon1NFOrders();
  const oneNF = convertTo1NF(source);
  const secondNF = decomposeTo2NF(oneNF);
  const thirdNF = decomposeTo3NF(secondNF.orders);

  return {
    customers: new RepositoryStyleRelation(
      "Customers",
      thirdNF.customers,
      ["customerId"]
    ),
    orders: new RepositoryStyleRelation(
      "Orders",
      thirdNF.orders,
      ["orderId"]
    ),
    products: new RepositoryStyleRelation(
      "Products",
      secondNF.products,
      ["productId"]
    ),
    orderItems: new RepositoryStyleRelation(
      "OrderItems",
      secondNF.orderItems,
      ["orderId", "productId"]
    ),
  };
}

function enforceForeignKeys(repository) {
  const customerIds = new Set(
    repository.customers.rows.map((row) => row.customerId)
  );
  const orderIds = new Set(
    repository.orders.rows.map((row) => row.orderId)
  );
  const productIds = new Set(
    repository.products.rows.map((row) => row.productId)
  );

  for (const order of repository.orders.rows) {
    if (!customerIds.has(order.customerId)) {
      throw new Error(
        `Order ${order.orderId} references missing customer ${order.customerId}`
      );
    }
  }

  for (const item of repository.orderItems.rows) {
    if (!orderIds.has(item.orderId)) {
      throw new Error(`OrderItem references missing order ${item.orderId}`);
    }
    if (!productIds.has(item.productId)) {
      throw new Error(`OrderItem references missing product ${item.productId}`);
    }
    if (!Number.isInteger(item.quantity) || item.quantity <= 0) {
      throw new Error("OrderItem quantity must be a positive integer.");
    }
  }
}

function buildBusinessView(repository) {
  const customers = new Map(
    repository.customers.rows.map((customer) => [
      customer.customerId,
      customer,
    ])
  );
  const orders = new Map(
    repository.orders.rows.map((order) => [order.orderId, order])
  );
  const products = new Map(
    repository.products.rows.map((product) => [
      product.productId,
      product,
    ])
  );

  return repository.orderItems.rows.map((item) => {
    const order = orders.get(item.orderId);
    const customer = customers.get(order.customerId);
    const product = products.get(item.productId);

    return {
      orderId: order.orderId,
      orderDate: order.orderDate,
      customer: customer.customerName,
      city: customer.customerCity,
      product: product.productName,
      quantity: item.quantity,
    };
  });
}

function demonstrateAnomalies() {
  printTitle("ANOMALIES ADDRESSED BY NORMALIZATION");

  console.log(
    "Update anomaly: duplicated customer facts require multiple updates "
    + "when the customer record changes."
  );
  console.log(
    "Insertion anomaly: a product should be insertable without fabricating "
    + "an order just to hold its description."
  );
  console.log(
    "Deletion anomaly: removing the final order for a product should not "
    + "delete the only stored product description."
  );
}

function demonstrateFailureCases(repository) {
  printTitle("VALIDATION AND FAILURE CASES");

  try {
    assertUnique(
      [
        { orderId: 1001, productId: "P101" },
        { orderId: 1001, productId: "P101" },
      ],
      ["orderId", "productId"]
    );
  } catch (error) {
    console.log("Duplicate composite key rejected:", error.message);
  }

  const inconsistentCustomerRows = [
    {
      customerId: "C001",
      customerName: "Asha Rao",
      customerCity: "Lucknow",
    },
    {
      customerId: "C001",
      customerName: "Asha Rao",
      customerCity: "Kanpur",
    },
  ];

  try {
    projectDistinct(
      inconsistentCustomerRows,
      ["customerId", "customerName", "customerCity"],
      ["customerId"]
    );
  } catch (error) {
    console.log(
      "Functional-dependency violation rejected:",
      error.message
    );
  }

  const invalidRepository = deepClone(repository);
  invalidRepository.orderItems.rows.push({
    orderId: 9999,
    productId: "P101",
    quantity: 1,
  });

  try {
    enforceForeignKeys(invalidRepository);
  } catch (error) {
    console.log("Foreign-key failure detected:", error.message);
  }
}

function explainNormalForms() {
  printTitle("NORMAL-FORM BOUNDARIES");

  console.log(
    "1NF: eliminate repeating groups and make every stored attribute atomic."
  );
  console.log(
    "2NF: after 1NF, eliminate dependencies on only part of a composite "
    + "candidate key."
  );
  console.log(
    "3NF: after 2NF, eliminate dependencies in which a non-key attribute "
    + "determines another non-key attribute."
  );
}

function main() {
  printTitle("NORMALIZATION II: 1NF, 2NF, AND 3NF");
  console.log(
    "Scenario: order management with customers, products, orders, and "
    + "order-line quantities."
  );

  explainNormalForms();

  const non1NF = createNon1NFOrders();
  const oneNF = convertTo1NF(non1NF);

  demonstrate1NF(oneNF);

  const secondNF = decomposeTo2NF(oneNF);
  const repository = {
    customers: new RepositoryStyleRelation(
      "Customers",
      [],
      ["customerId"]
    ),
    orders: new RepositoryStyleRelation(
      "Orders",
      secondNF.orders,
      ["orderId"]
    ),
    products: new RepositoryStyleRelation(
      "Products",
      secondNF.products,
      ["productId"]
    ),
    orderItems: new RepositoryStyleRelation(
      "OrderItems",
      secondNF.orderItems,
      ["orderId", "productId"]
    ),
  };

  const thirdNF = decomposeTo3NF(secondNF.orders);
  repository.customers = new RepositoryStyleRelation(
    "Customers",
    thirdNF.customers,
    ["customerId"]
  );
  repository.orders = new RepositoryStyleRelation(
    "Orders",
    thirdNF.orders,
    ["orderId"]
  );

  for (const relation of Object.values(repository)) {
    relation.validate();
  }

  enforceForeignKeys(repository);

  console.log("\nNormalized business view:");
  printTable(buildBusinessView(repository), [
    "orderId",
    "orderDate",
    "customer",
    "city",
    "product",
    "quantity",
  ]);

  demonstrateAnomalies();
  demonstrateFailureCases(repository);

  printTitle("FINAL 3NF RELATIONS");
  console.log("Customers(customerId, customerName, customerCity)");
  console.log("Orders(orderId, orderDate, customerId)");
  console.log("Products(productId, productName)");
  console.log("OrderItems(orderId, productId, quantity)");
}

main();
