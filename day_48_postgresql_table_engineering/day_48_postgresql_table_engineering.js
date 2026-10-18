"use strict";

/*
 * PostgreSQL Table Engineering: JavaScript schema deployment utility.
 *
 * Runtime: Node.js 18+
 * Optional dependency: pg
 *
 * Install pg using npm install pg.
 * Configure DATABASE_URL before running against a PostgreSQL database.
 *
 * This implementation focuses on schema deployment ordering, migration
 * tracking, catalog inspection, and safe handling of failed migrations.
 */

const { createHash } = require("node:crypto");

const migrations = [
  {
    version: "001",
    name: "create_inventory_schema",
    statements: [
      `
      CREATE SCHEMA IF NOT EXISTS inventory
      `,
      `
      CREATE TABLE IF NOT EXISTS inventory.categories (
        category_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        category_name TEXT NOT NULL UNIQUE,
        CONSTRAINT ck_categories_name
          CHECK (length(btrim(category_name)) > 0)
      )
      `,
      `
      CREATE TABLE IF NOT EXISTS inventory.products (
        product_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        sku TEXT NOT NULL UNIQUE,
        product_name TEXT NOT NULL,
        category_id BIGINT,
        unit_price NUMERIC(12,2) NOT NULL DEFAULT 0.00,
        stock_quantity INTEGER NOT NULL DEFAULT 0,
        active BOOLEAN NOT NULL DEFAULT TRUE,
        created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
        CONSTRAINT ck_products_sku
          CHECK (length(btrim(sku)) > 0),
        CONSTRAINT ck_products_name
          CHECK (length(btrim(product_name)) > 0),
        CONSTRAINT ck_products_price
          CHECK (unit_price >= 0),
        CONSTRAINT ck_products_stock
          CHECK (stock_quantity >= 0),
        CONSTRAINT fk_products_category
          FOREIGN KEY (category_id)
          REFERENCES inventory.categories(category_id)
          ON DELETE SET NULL
      )
      `,
      `
      CREATE INDEX IF NOT EXISTS ix_products_category_active
        ON inventory.products(category_id, active)
      `,
    ],
  },
  {
    version: "002",
    name: "add_product_description_and_audit_time",
    statements: [
      `
      ALTER TABLE inventory.products
        ADD COLUMN IF NOT EXISTS description TEXT NOT NULL DEFAULT ''
      `,
      `
      ALTER TABLE inventory.products
        ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ
          NOT NULL DEFAULT CURRENT_TIMESTAMP
      `,
    ],
  },
];

function validateMigration(migration) {
  if (!/^[0-9]{3}$/.test(migration.version)) {
    throw new Error(`Invalid migration version: ${migration.version}`);
  }

  if (!/^[a-z][a-z0-9_]*$/.test(migration.name)) {
    throw new Error(`Invalid migration name: ${migration.name}`);
  }

  if (!Array.isArray(migration.statements) || migration.statements.length === 0) {
    throw new Error(`Migration ${migration.version} has no SQL statements`);
  }

  for (const statement of migration.statements) {
    if (typeof statement !== "string" || statement.trim() === "") {
      throw new Error(`Migration ${migration.version} contains empty SQL`);
    }
  }
}

function checksumMigration(migration) {
  // A checksum detects accidental edits to a migration already deployed.
  return createHash("sha256")
    .update(migration.statements.map((sql) => sql.trim()).join("\n"))
    .digest("hex");
}

function inspectMigrationPlan(plan) {
  console.log("\n=== Migration plan ===");

  const seenVersions = new Set();

  for (const migration of plan) {
    validateMigration(migration);

    if (seenVersions.has(migration.version)) {
      throw new Error(`Duplicate migration version: ${migration.version}`);
    }

    seenVersions.add(migration.version);

    console.log({
      version: migration.version,
      name: migration.name,
      statementCount: migration.statements.length,
      checksum: checksumMigration(migration),
    });
  }

  const sorted = [...plan].sort((a, b) =>
    a.version.localeCompare(b.version)
  );

  if (sorted.some((migration, index) => migration !== plan[index])) {
    throw new Error("Migrations must be supplied in version order");
  }

  return sorted;
}

function validateProduct(input) {
  const errors = [];

  if (typeof input.sku !== "string" || input.sku.trim() === "") {
    errors.push("SKU is required");
  }

  if (
    typeof input.productName !== "string" ||
    input.productName.trim() === ""
  ) {
    errors.push("Product name is required");
  }

  // Numeric database values should not be silently rounded in JavaScript.
  // Accept decimal strings for NUMERIC columns to preserve exact values.
  const price = input.unitPrice;
  if (
    typeof price !== "string" ||
    !/^\d{1,10}(\.\d{1,2})?$/.test(price)
  ) {
    errors.push("Unit price must be a non-negative decimal string");
  }

  if (!Number.isSafeInteger(input.stockQuantity) || input.stockQuantity < 0) {
    errors.push("Stock quantity must be a non-negative safe integer");
  }

  return errors;
}

async function deploySchema(databaseUrl) {
  let pg;

  try {
    pg = require("pg");
  } catch {
    throw new Error("Missing pg package. Install it with npm install pg.");
  }

  const { Pool } = pg;
  const pool = new Pool({
    connectionString: databaseUrl,
    max: 3,
    connectionTimeoutMillis: 5000,
    application_name: "table-engineering-demo",
  });

  const client = await pool.connect();

  try {
    // A dedicated migration table records applied versions and checksums.
    await client.query("BEGIN");

    await client.query(`
      CREATE SCHEMA IF NOT EXISTS inventory
    `);

    await client.query(`
      CREATE TABLE IF NOT EXISTS inventory.schema_migrations (
        version TEXT PRIMARY KEY,
        migration_name TEXT NOT NULL,
        checksum TEXT NOT NULL,
        applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
      )
    `);

    await client.query("COMMIT");

    // Serialize migration runners. The lock is scoped to this database
    // session and is released automatically when the client disconnects.
    await client.query("SELECT pg_advisory_lock($1, $2)", [73121, 1]);

    const plan = inspectMigrationPlan(migrations);

    for (const migration of plan) {
      const checksum = checksumMigration(migration);

      const existing = await client.query(
        `
        SELECT migration_name, checksum
        FROM inventory.schema_migrations
        WHERE version = $1
        `,
        [migration.version]
      );

      if (existing.rowCount > 0) {
        const row = existing.rows[0];

        if (
          row.migration_name !== migration.name ||
          row.checksum !== checksum
        ) {
          throw new Error(
            `Migration ${migration.version} differs from its applied record`
          );
        }

        console.log(`Already applied: ${migration.version}`);
        continue;
      }

      // PostgreSQL supports transactional DDL for these operations.
      // If any statement fails, the entire migration is rolled back.
      await client.query("BEGIN");

      try {
        for (const statement of migration.statements) {
          await client.query(statement);
        }

        await client.query(
          `
          INSERT INTO inventory.schema_migrations
            (version, migration_name, checksum)
          VALUES ($1, $2, $3)
          `,
          [migration.version, migration.name, checksum]
        );

        await client.query("COMMIT");
        console.log(`Applied: ${migration.version} ${migration.name}`);
      } catch (error) {
        await client.query("ROLLBACK");
        throw error;
      }
    }

    const columns = await client.query(
      `
      SELECT column_name, data_type, is_nullable, column_default
      FROM information_schema.columns
      WHERE table_schema = $1 AND table_name = $2
      ORDER BY ordinal_position
      `,
      ["inventory", "products"]
    );

    console.log("\n=== Product table ===");
    console.table(columns.rows);
  } finally {
    try {
      await client.query("SELECT pg_advisory_unlock($1, $2)", [73121, 1]);
    } catch {
      // A broken connection may prevent explicit unlock. PostgreSQL releases
      // session advisory locks when that connection closes.
    }

    client.release();
    await pool.end();
  }
}

async function main() {
  console.log("=== Product validation ===");

  const examples = [
    {
      sku: "KB-100",
      productName: "Mechanical Keyboard",
      unitPrice: "3499.00",
      stockQuantity: 20,
    },
    {
      sku: "BAD-PRICE",
      productName: "Invalid Price Example",
      unitPrice: "-20.00",
      stockQuantity: 2,
    },
    {
      sku: "BAD-STOCK",
      productName: "Invalid Stock Example",
      unitPrice: "250.00",
      stockQuantity: -1,
    },
  ];

  for (const product of examples) {
    const errors = validateProduct(product);
    console.log(
      product.sku,
      errors.length === 0 ? "VALID" : `INVALID: ${errors.join("; ")}`
    );
  }

  inspectMigrationPlan(migrations);

  const databaseUrl = process.env.DATABASE_URL;

  if (!databaseUrl) {
    console.log(
      "\nDATABASE_URL is not set. Offline validation and migration planning completed."
    );
    return;
  }

  await deploySchema(databaseUrl);
}

main().catch((error) => {
  console.error("Schema deployment failed:", error.message);
  process.exitCode = 1;
});
