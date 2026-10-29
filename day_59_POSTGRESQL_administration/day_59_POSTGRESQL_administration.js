#!/usr/bin/env node
"use strict";

/*
 * PostgreSQL Administration
 * Users, roles, permissions, and database-management policy evaluation.
 *
 * This executable Node.js program models:
 * - login roles and group roles
 * - inherited memberships
 * - object privileges
 * - default privilege templates
 * - database connection limits
 * - policy evaluation
 * - administrative events
 * - asynchronous audit processing
 */

const crypto = require("node:crypto");
const { EventEmitter } = require("node:events");

const Privilege = Object.freeze({
  CONNECT: "CONNECT",
  USAGE: "USAGE",
  SELECT: "SELECT",
  INSERT: "INSERT",
  UPDATE: "UPDATE",
  DELETE: "DELETE",
  CREATE: "CREATE",
  EXECUTE: "EXECUTE",
});

const ObjectType = Object.freeze({
  DATABASE: "database",
  SCHEMA: "schema",
  TABLE: "table",
  FUNCTION: "function",
});

const RoleAttribute = Object.freeze({
  LOGIN: "LOGIN",
  SUPERUSER: "SUPERUSER",
  CREATEDB: "CREATEDB",
  CREATEROLE: "CREATEROLE",
  INHERIT: "INHERIT",
});

class ValidationError extends Error {}
class AuthorizationError extends Error {}
class ConnectionLimitError extends Error {}

class DatabaseObject {
  constructor(name, objectType, schema = null) {
    if (!name || !objectType) {
      throw new ValidationError("Object name and type are required");
    }

    this.name = name;
    this.objectType = objectType;
    this.schema = schema;
  }

  get identifier() {
    return this.schema ? `${this.schema}.${this.name}` : this.name;
  }
}

class Role {
  constructor({
    name,
    login = false,
    superuser = false,
    createdb = false,
    createrole = false,
    inherit = true,
    connectionLimit = -1,
  }) {
    if (!name) {
      throw new ValidationError("Role name is required");
    }

    if (!Number.isInteger(connectionLimit) || connectionLimit < -1) {
      throw new ValidationError(
        "connectionLimit must be -1 or a non-negative integer"
      );
    }

    this.name = name;
    this.login = login;
    this.superuser = superuser;
    this.createdb = createdb;
    this.createrole = createrole;
    this.inherit = inherit;
    this.connectionLimit = connectionLimit;
    this.memberships = new Set();
    this.passwordDigest = null;
  }

  hasAttribute(attribute) {
    const attributes = {
      [RoleAttribute.LOGIN]: this.login,
      [RoleAttribute.SUPERUSER]: this.superuser,
      [RoleAttribute.CREATEDB]: this.createdb,
      [RoleAttribute.CREATEROLE]: this.createrole,
      [RoleAttribute.INHERIT]: this.inherit,
    };

    return Boolean(attributes[attribute]);
  }
}

class AuditBus extends EventEmitter {
  async record(event) {
    await new Promise((resolve) => setImmediate(resolve));
    this.emit("audit", Object.freeze({
      timestamp: new Date().toISOString(),
      ...event,
    }));
  }
}

class RoleDirectory {
  constructor(auditBus) {
    this.roles = new Map();
    this.auditBus = auditBus;
  }

  addBootstrapRole(role) {
    if (this.roles.size !== 0) {
      throw new AuthorizationError(
        "Bootstrap role may only be installed in an empty directory"
      );
    }

    this.roles.set(role.name, role);
  }

  get(name) {
    const role = this.roles.get(name);
    if (!role) {
      throw new ValidationError(`Unknown role: ${name}`);
    }
    return role;
  }

  createRole(actorName, role) {
    const actor = this.get(actorName);

    if (!actor.superuser && !actor.createrole) {
      throw new AuthorizationError(
        `${actorName} lacks CREATEROLE authority`
      );
    }

    if (this.roles.has(role.name)) {
      throw new ValidationError(`Role already exists: ${role.name}`);
    }

    this.roles.set(role.name, role);

    return this.auditBus.record({
      action: "CREATE_ROLE",
      actor: actorName,
      target: role.name,
      success: true,
    });
  }

  grantMembership(actorName, memberName, groupName) {
    const actor = this.get(actorName);
    const member = this.get(memberName);
    const group = this.get(groupName);

    if (!actor.superuser && !actor.createrole) {
      throw new AuthorizationError(
        `${actorName} cannot modify role membership`
      );
    }

    if (memberName === groupName) {
      throw new ValidationError("A role cannot be a member of itself");
    }

    if (this.wouldCycle(memberName, groupName)) {
      throw new ValidationError("Role membership would create a cycle");
    }

    member.memberships.add(groupName);

    return this.auditBus.record({
      action: "GRANT_ROLE",
      actor: actorName,
      target: `${memberName} -> ${groupName}`,
      success: true,
    });
  }

  wouldCycle(memberName, groupName) {
    const stack = [groupName];
    const visited = new Set();

    while (stack.length > 0) {
      const current = stack.pop();

      if (current === memberName) {
        return true;
      }

      if (visited.has(current)) {
        continue;
      }

      visited.add(current);
      const role = this.get(current);

      for (const parent of role.memberships) {
        stack.push(parent);
      }
    }

    return false;
  }

  effectiveRoles(roleName) {
    const root = this.get(roleName);
    const result = new Set([roleName]);

    if (!root.inherit) {
      return result;
    }

    const stack = [...root.memberships];

    while (stack.length > 0) {
      const current = stack.pop();

      if (result.has(current)) {
        continue;
      }

      result.add(current);

      const role = this.get(current);
      if (role.inherit) {
        stack.push(...role.memberships);
      }
    }

    return result;
  }

  setPassword(actorName, targetName, password) {
    const actor = this.get(actorName);
    const target = this.get(targetName);

    if (password.length < 12) {
      throw new ValidationError(
        "Password must contain at least 12 characters"
      );
    }

    if (!/[A-Z]/.test(password) ||
        !/[a-z]/.test(password) ||
        !/[0-9]/.test(password)) {
      throw new ValidationError(
        "Password requires uppercase, lowercase, and numeric characters"
      );
    }

    if (actorName !== targetName && !actor.superuser) {
      throw new AuthorizationError(
        "Only a superuser may change another role's password"
      );
    }

    target.passwordDigest = crypto
      .createHash("sha256")
      .update(password)
      .digest("hex");

    return this.auditBus.record({
      action: "ALTER_ROLE",
      actor: actorName,
      target: targetName,
      success: true,
    });
  }
}

class PermissionStore {
  constructor() {
    this.grants = new Map();
    this.defaultPrivileges = new Map();
  }

  key(roleName, objectId) {
    return `${roleName}|${objectId}`;
  }

  grant(roleName, object, privileges, grantOption = false) {
    const privilegeSet = new Set(privileges);

    if (privilegeSet.size === 0) {
      throw new ValidationError("At least one privilege is required");
    }

    const key = this.key(roleName, object.identifier);
    const existing = this.grants.get(key);

    if (existing) {
      for (const privilege of privilegeSet) {
        existing.privileges.add(privilege);
      }
      existing.grantOption ||= grantOption;
      return;
    }

    this.grants.set(key, {
      roleName,
      objectId: object.identifier,
      privileges: privilegeSet,
      grantOption,
    });
  }

  revoke(roleName, object, privileges) {
    const key = this.key(roleName, object.identifier);
    const grant = this.grants.get(key);

    if (!grant) {
      return;
    }

    for (const privilege of privileges) {
      grant.privileges.delete(privilege);
    }

    if (grant.privileges.size === 0) {
      this.grants.delete(key);
    }
  }

  setDefaultPrivileges(roleName, objectType, privileges) {
    this.defaultPrivileges.set(
      `${roleName}|${objectType}`,
      new Set(privileges)
    );
  }

  getPrivileges(roleName, objectId) {
    const grant = this.grants.get(this.key(roleName, objectId));
    return grant ? new Set(grant.privileges) : new Set();
  }

  getDefaultPrivileges(roleName, objectType) {
    return new Set(
      this.defaultPrivileges.get(`${roleName}|${objectType}`) || []
    );
  }
}

class AccessPolicy {
  constructor(roleDirectory, permissionStore) {
    this.roles = roleDirectory;
    this.permissions = permissionStore;
  }

  can(roleName, object, privilege) {
    const role = this.roles.get(roleName);

    if (role.superuser) {
      return true;
    }

    for (const effectiveRole of this.roles.effectiveRoles(roleName)) {
      if (
        this.permissions
          .getPrivileges(effectiveRole, object.identifier)
          .has(privilege)
      ) {
        return true;
      }
    }

    return false;
  }

  require(roleName, object, privilege) {
    if (!this.can(roleName, object, privilege)) {
      throw new AuthorizationError(
        `${roleName} lacks ${privilege} on ${object.identifier}`
      );
    }
  }
}

class DatabaseSessionManager {
  constructor(name, connectionLimit = -1) {
    if (connectionLimit < -1) {
      throw new ValidationError("Invalid database connection limit");
    }

    this.name = name;
    this.connectionLimit = connectionLimit;
    this.active = new Map();
    this.acceptingConnections = true;
  }

  connect(role) {
    if (!this.acceptingConnections) {
      throw new ConnectionLimitError(
        `Database ${this.name} is not accepting connections`
      );
    }

    if (!role.login) {
      throw new AuthorizationError(`${role.name} is NOLOGIN`);
    }

    if (
      this.connectionLimit !== -1 &&
      this.active.size >= this.connectionLimit
    ) {
      throw new ConnectionLimitError(
        `Database ${this.name} reached its connection limit`
      );
    }

    const roleConnections = this.active.get(role.name) || 0;

    if (
      role.connectionLimit !== -1 &&
      roleConnections >= role.connectionLimit
    ) {
      throw new ConnectionLimitError(
        `Role ${role.name} reached its connection limit`
      );
    }

    this.active.set(role.name, roleConnections + 1);

    return `${role.name}-${Date.now()}-${crypto.randomUUID()}`;
  }

  disconnect(sessionId) {
    const separator = sessionId.indexOf("-");
    const roleName = sessionId.slice(0, separator);

    const count = this.active.get(roleName);

    if (!count) {
      return false;
    }

    if (count === 1) {
      this.active.delete(roleName);
    } else {
      this.active.set(roleName, count - 1);
    }

    return true;
  }

  activeConnectionCount() {
    let count = 0;

    for (const value of this.active.values()) {
      count += value;
    }

    return count;
  }
}

async function main() {
  const auditBus = new AuditBus();

  auditBus.on("audit", (event) => {
    const state = event.success ? "SUCCESS" : "DENIED";
    console.log(
      `[AUDIT] ${state} ${event.action} actor=${event.actor} target=${event.target}`
    );
  });

  const roles = new RoleDirectory(auditBus);

  roles.addBootstrapRole(
    new Role({
      name: "postgres",
      login: true,
      superuser: true,
      createdb: true,
      createrole: true,
    })
  );

  await roles.createRole(
    "postgres",
    new Role({ name: "application_owner" })
  );

  await roles.createRole(
    "postgres",
    new Role({ name: "application_reader" })
  );

  await roles.createRole(
    "postgres",
    new Role({ name: "application_writer" })
  );

  await roles.createRole(
    "postgres",
    new Role({
      name: "api_user",
      login: true,
      connectionLimit: 10,
    })
  );

  await roles.createRole(
    "postgres",
    new Role({
      name: "report_user",
      login: true,
      connectionLimit: 3,
    })
  );

  await roles.grantMembership(
    "postgres",
    "api_user",
    "application_writer"
  );

  await roles.grantMembership(
    "postgres",
    "report_user",
    "application_reader"
  );

  await roles.setPassword(
    "postgres",
    "api_user",
    "StrongPassword7"
  );

  const permissions = new PermissionStore();

  const businessDatabase = new DatabaseObject(
    "business_db",
    ObjectType.DATABASE
  );

  const appSchema = new DatabaseObject(
    "app",
    ObjectType.SCHEMA
  );

  const customerTable = new DatabaseObject(
    "customers",
    ObjectType.TABLE,
    "app"
  );

  const invoiceTable = new DatabaseObject(
    "invoices",
    ObjectType.TABLE,
    "app"
  );

  permissions.grant(
    "application_owner",
    businessDatabase,
    [Privilege.CONNECT]
  );

  permissions.grant(
    "application_owner",
    appSchema,
    [Privilege.USAGE, Privilege.CREATE]
  );

  permissions.grant(
    "application_reader",
    businessDatabase,
    [Privilege.CONNECT]
  );

  permissions.grant(
    "application_reader",
    appSchema,
    [Privilege.USAGE]
  );

  permissions.grant(
    "application_reader",
    customerTable,
    [Privilege.SELECT]
  );

  permissions.grant(
    "application_reader",
    invoiceTable,
    [Privilege.SELECT]
  );

  permissions.grant(
    "application_writer",
    businessDatabase,
    [Privilege.CONNECT]
  );

  permissions.grant(
    "application_writer",
    appSchema,
    [Privilege.USAGE]
  );

  permissions.grant(
    "application_writer",
    customerTable,
    [Privilege.SELECT, Privilege.INSERT, Privilege.UPDATE]
  );

  permissions.grant(
    "application_writer",
    invoiceTable,
    [Privilege.SELECT, Privilege.INSERT, Privilege.UPDATE]
  );

  permissions.setDefaultPrivileges(
    "application_owner",
    ObjectType.TABLE,
    [Privilege.SELECT]
  );

  const policy = new AccessPolicy(roles, permissions);

  console.log("\nEffective role membership");
  console.log("-------------------------");

  for (const roleName of ["api_user", "report_user"]) {
    console.log(
      `${roleName}: ${[
        ...roles.effectiveRoles(roleName),
      ].sort().join(", ")}`
    );
  }

  console.log("\nAuthorization evaluation");
  console.log("------------------------");

  policy.require(
    "api_user",
    customerTable,
    Privilege.UPDATE
  );
  console.log("api_user UPDATE app.customers: ALLOWED");

  policy.require(
    "report_user",
    customerTable,
    Privilege.SELECT
  );
  console.log("report_user SELECT app.customers: ALLOWED");

  try {
    policy.require(
      "report_user",
      customerTable,
      Privilege.DELETE
    );
  } catch (error) {
    console.log(`report_user DELETE app.customers: DENIED (${error.message})`);
  }

  console.log("\nDefault privileges");
  console.log("------------------");

  console.log(
    `application_owner default TABLE privileges: ${
      [...permissions.getDefaultPrivileges(
        "application_owner",
        ObjectType.TABLE
      )].join(", ")
    }`
  );

  console.log("\nConnection management");
  console.log("---------------------");

  const database = new DatabaseSessionManager("business_db", 2);

  const session1 = database.connect(roles.get("api_user"));
  const session2 = database.connect(roles.get("report_user"));

  console.log(`Active sessions: ${database.activeConnectionCount()}`);

  try {
    database.connect(roles.get("api_user"));
  } catch (error) {
    console.log(`Expected connection rejection: ${error.message}`);
  }

  database.disconnect(session1);
  console.log(
    `Active sessions after disconnect: ${database.activeConnectionCount()}`
  );

  database.disconnect(session2);

  console.log("\nMembership cycle protection");
  console.log("---------------------------");

  try {
    await roles.grantMembership(
      "postgres",
      "application_writer",
      "api_user"
    );
  } catch (error) {
    console.log(`Expected cycle rejection: ${error.message}`);
  }

  console.log("\nAssertions");
  console.log("----------");

  console.assert(
    roles.get("api_user").login,
    "api_user must be a login role"
  );

  console.assert(
    !roles.get("application_writer").login,
    "application_writer must be NOLOGIN"
  );

  console.assert(
    policy.can(
      "api_user",
      customerTable,
      Privilege.UPDATE
    ),
    "writer membership must provide UPDATE"
  );

  console.assert(
    !policy.can(
      "report_user",
      customerTable,
      Privilege.DELETE
    ),
    "reader must not receive DELETE"
  );

  console.assert(
    database.activeConnectionCount() === 0,
    "All sessions should be closed"
  );

  console.log("All administration-policy assertions passed.");
}

main().catch((error) => {
  console.error(`Fatal administration error: ${error.message}`);
  process.exitCode = 1;
});
