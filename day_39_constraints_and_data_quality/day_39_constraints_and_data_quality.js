"use strict";

/*
 * Constraints and Data Quality
 *
 * A Node.js implementation centered on event-driven validation, staged
 * imports, uniqueness indexes, and policy evaluation.
 *
 * Run with:
 *   node constraints_data_quality.js
 *
 * No external packages are required.
 */

const { EventEmitter } = require("node:events");
const { randomUUID } = require("node:crypto");

class DataQualityError extends Error {
  constructor(rule, message, field = null) {
    super(message);
    this.name = "DataQualityError";
    this.rule = rule;
    this.field = field;
  }
}

function normalizeText(value, field, maximumLength) {
  if (typeof value !== "string") {
    throw new DataQualityError(
      "TYPE",
      `${field} must be a string.`,
      field
    );
  }

  const normalized = value.trim();

  if (normalized.length === 0 || normalized.length > maximumLength) {
    throw new DataQualityError(
      "TEXT_LENGTH",
      `${field} must contain between 1 and ${maximumLength} characters.`,
      field
    );
  }

  return normalized;
}

function normalizeEmail(value) {
  const email = normalizeText(value, "email", 254).toLowerCase();

  // This is a deliberately conservative business-level check, not a complete
  // implementation of every valid Internet email-address syntax.
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    throw new DataQualityError(
      "EMAIL_FORMAT",
      "Email must have a basic local-part and domain structure.",
      "email"
    );
  }

  return email;
}

function normalizeMoney(value) {
  if (
    typeof value !== "number" &&
    !(typeof value === "string" && value.trim() !== "")
  ) {
    throw new DataQualityError(
      "MONEY_TYPE",
      "Salary must be a number or a numeric string.",
      "salary"
    );
  }

  const salary = Number(value);

  if (!Number.isFinite(salary) || salary < 0) {
    throw new DataQualityError(
      "SALARY_RANGE",
      "Salary must be finite and nonnegative.",
      "salary"
    );
  }

  // Monetary values are represented in integer cents after validation.
  const cents = Math.round(salary * 100);

  if (Math.abs(salary * 100 - cents) > 1e-7) {
    throw new DataQualityError(
      "SALARY_PRECISION",
      "Salary cannot contain fractions of a cent.",
      "salary"
    );
  }

  return cents;
}

function validateEmployee(input) {
  if (input === null || typeof input !== "object" || Array.isArray(input)) {
    throw new DataQualityError(
      "RECORD_TYPE",
      "Employee input must be an object."
    );
  }

  const employeeCode = normalizeText(
    input.employeeCode,
    "employeeCode",
    20
  ).toUpperCase();

  const fullName = normalizeText(input.fullName, "fullName", 100);
  const department = normalizeText(input.department, "department", 50);
  const email = normalizeEmail(input.email);
  const salaryCents = normalizeMoney(input.salary);

  if (!Number.isInteger(input.age) || input.age < 18 || input.age > 100) {
    throw new DataQualityError(
      "AGE_RANGE",
      "Age must be an integer from 18 through 100.",
      "age"
    );
  }

  if (typeof input.active !== "boolean") {
    throw new DataQualityError(
      "ACTIVE_TYPE",
      "Active status must be a Boolean.",
      "active"
    );
  }

  return Object.freeze({
    id: randomUUID(),
    employeeCode,
    email,
    fullName,
    age: input.age,
    salaryCents,
    department,
    active: input.active
  });
}

class QualityEventBus extends EventEmitter {
  publishQualityFailure(error, context) {
    this.emit("qualityFailure", {
      eventId: randomUUID(),
      timestamp: new Date().toISOString(),
      rule: error.rule ?? "UNEXPECTED",
      field: error.field,
      message: error.message,
      context
    });
  }
}

class EmployeeRegistry {
  #byCode = new Map();
  #byEmail = new Map();
  #byId = new Map();
  #events;

  constructor(events) {
    this.#events = events;
  }

  get size() {
    return this.#byId.size;
  }

  add(input) {
    let employee;

    try {
      employee = validateEmployee(input);

      // Normalized values are indexed so case and whitespace differences do
      // not create duplicate logical identifiers.
      if (this.#byCode.has(employee.employeeCode)) {
        throw new DataQualityError(
          "UNIQUE_EMPLOYEE_CODE",
          `Employee code ${employee.employeeCode} already exists.`,
          "employeeCode"
        );
      }

      if (this.#byEmail.has(employee.email)) {
        throw new DataQualityError(
          "UNIQUE_EMAIL",
          `Email ${employee.email} already exists.`,
          "email"
        );
      }

      if (!this.#departmentExists(employee.department)) {
        throw new DataQualityError(
          "FOREIGN_KEY_DEPARTMENT",
          `Department ${employee.department} does not exist.`,
          "department"
        );
      }

      // All checks complete before any index is mutated. This prevents a
      // failed insert from leaving partially updated uniqueness indexes.
      this.#byId.set(employee.id, employee);
      this.#byCode.set(employee.employeeCode, employee.id);
      this.#byEmail.set(employee.email, employee.id);

      return employee;
    } catch (error) {
      if (error instanceof DataQualityError) {
        this.#events.publishQualityFailure(error, {
          employeeCode: input?.employeeCode ?? null
        });
      }

      throw error;
    }
  }

  #departmentExists(department) {
    return this.departments.has(department);
  }

  departments = new Set(["Engineering", "Finance", "Operations"]);

  getByCode(code) {
    const id = this.#byCode.get(String(code).trim().toUpperCase());
    return id ? this.#byId.get(id) : null;
  }

  updateSalary(code, value) {
    const employee = this.getByCode(code);

    if (!employee) {
      throw new DataQualityError(
        "EMPLOYEE_NOT_FOUND",
        `Employee ${code} does not exist.`
      );
    }

    const salaryCents = normalizeMoney(value);
    const updated = Object.freeze({ ...employee, salaryCents });

    // Replacing an immutable record avoids exposing mutable internal state.
    this.#byId.set(employee.id, updated);
    return updated;
  }

  all() {
    return [...this.#byId.values()];
  }

  findByDepartment(department, activeOnly = false) {
    return this.all().filter(
      (employee) =>
        employee.department === department &&
        (!activeOnly || employee.active)
    );
  }

  inspect() {
    const failures = [];
    const codes = new Set();
    const emails = new Set();

    for (const employee of this.#byId.values()) {
      if (codes.has(employee.employeeCode)) {
        failures.push({
          rule: "UNIQUE_EMPLOYEE_CODE",
          employeeCode: employee.employeeCode
        });
      }

      if (emails.has(employee.email)) {
        failures.push({
          rule: "UNIQUE_EMAIL",
          email: employee.email
        });
      }

      codes.add(employee.employeeCode);
      emails.add(employee.email);

      if (employee.salaryCents < 0) {
        failures.push({
          rule: "SALARY_RANGE",
          employeeCode: employee.employeeCode
        });
      }
    }

    return failures;
  }
}

class ImportService {
  constructor(registry, events) {
    this.registry = registry;
    this.events = events;
  }

  /*
   * Each record is processed independently. The report distinguishes valid
   * inserts from rejected records, which is useful for large file imports.
   * A whole-file atomic import would instead require a staging table or
   * a transaction in a persistent database.
   */
  importRecords(records) {
    if (!Array.isArray(records)) {
      throw new TypeError("Import data must be an array.");
    }

    const report = {
      accepted: [],
      rejected: [],
      received: records.length
    };

    for (const [index, record] of records.entries()) {
      try {
        report.accepted.push(this.registry.add(record));
      } catch (error) {
        report.rejected.push({
          index,
          employeeCode: record?.employeeCode ?? null,
          rule: error.rule ?? "UNEXPECTED",
          message: error.message
        });
      }
    }

    return report;
  }
}

function printReport(title, report) {
  console.log(`\n${title}`);
  console.log(`Received: ${report.received}`);
  console.log(`Accepted: ${report.accepted.length}`);
  console.log(`Rejected: ${report.rejected.length}`);

  for (const rejected of report.rejected) {
    console.log(
      `Rejected record ${rejected.index}: ${rejected.rule}: ${rejected.message}`
    );
  }
}

function main() {
  const events = new QualityEventBus();
  const registry = new EmployeeRegistry(events);
  const importService = new ImportService(registry, events);
  const qualityEvents = [];

  events.on("qualityFailure", (event) => {
    qualityEvents.push(event);
    console.log(
      `Quality event ${event.rule}: ${event.message}`
    );
  });

  const inputRecords = [
    {
      employeeCode: "E-201",
      email: "ALICE@example.com",
      fullName: "Alice Sharma",
      age: 32,
      salary: "65000.00",
      department: "Engineering",
      active: true
    },
    {
      employeeCode: "E-202",
      email: "rahul@example.com",
      fullName: "Rahul Verma",
      age: 41,
      salary: 82000,
      department: "Finance",
      active: true
    },
    {
      employeeCode: "E-203",
      email: "meera@example.com",
      fullName: "Meera Singh",
      age: 27,
      salary: 54000,
      department: "Operations",
      active: false
    },
    {
      employeeCode: "E-201",
      email: "second@example.com",
      fullName: "Duplicate Employee Code",
      age: 30,
      salary: 50000,
      department: "Finance",
      active: true
    },
    {
      employeeCode: "E-204",
      email: "alice@EXAMPLE.com",
      fullName: "Duplicate Email",
      age: 30,
      salary: 50000,
      department: "Engineering",
      active: true
    },
    {
      employeeCode: "E-205",
      email: "bad@example.com",
      fullName: "Invalid Age",
      age: 17,
      salary: 45000,
      department: "Finance",
      active: true
    },
    {
      employeeCode: "E-206",
      email: "unknown@example.com",
      fullName: "Unknown Department",
      age: 29,
      salary: 47000,
      department: "Legal",
      active: true
    },
    {
      employeeCode: "E-207",
      email: "negative@example.com",
      fullName: "Negative Salary",
      age: 34,
      salary: -100,
      department: "Finance",
      active: true
    }
  ];

  const report = importService.importRecords(inputRecords);
  printReport("Staged employee import", report);

  console.log("\nEngineering employees");
  for (const employee of registry.findByDepartment("Engineering", true)) {
    console.log({
      employeeCode: employee.employeeCode,
      fullName: employee.fullName,
      salary: (employee.salaryCents / 100).toFixed(2)
    });
  }

  console.log("\nSalary change");
  const updated = registry.updateSalary("E-201", "68000.00");
  console.log(
    `${updated.employeeCode}: ${(updated.salaryCents / 100).toFixed(2)}`
  );

  try {
    registry.updateSalary("E-201", "-1.00");
  } catch (error) {
    console.log(`Salary change rejected: ${error.message}`);
  }

  console.log("\nQuality inspection");
  console.log(`Registry records: ${registry.size}`);
  console.log(`Detected integrity problems: ${registry.inspect().length}`);
  console.log(`Emitted quality events: ${qualityEvents.length}`);

  // Events are useful for monitoring but do not replace durable audit storage.
  // Production systems should persist failures and enforce critical rules
  // again in the database to handle concurrent writers.
}

main();
