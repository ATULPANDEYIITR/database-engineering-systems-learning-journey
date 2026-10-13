"use strict";

/*
 * Event-driven multi-tenant architecture simulator.
 *
 * Node.js 18+; no third-party dependencies.
 *
 * The event stream models provisioning, tenant-scoped writes, schema/database
 * routing, suspension, migration outcomes, and architecture-specific policies.
 * A tenant context is validated on every command rather than trusted because
 * it was previously resolved.
 */

const { EventEmitter } = require("node:events");
const { randomUUID } = require("node:crypto");

const Architecture = Object.freeze({
  SHARED_SCHEMA: "shared_schema",
  SEPARATE_SCHEMA: "separate_schema",
  SEPARATE_DATABASE: "separate_database",
});

const TenantStatus = Object.freeze({
  PROVISIONING: "provisioning",
  ACTIVE: "active",
  SUSPENDED: "suspended",
  DEPROVISIONED: "deprovisioned",
});

class DomainError extends Error {
  constructor(message, code) {
    super(message);
    this.name = "DomainError";
    this.code = code;
  }
}

function validateIdentifier(value, label = "identifier") {
  if (
    typeof value !== "string" ||
    !/^[a-z][a-z0-9_]{2,39}$/.test(value)
  ) {
    throw new DomainError(
      `${label} must be a 3-40 character lowercase identifier.`,
      "INVALID_IDENTIFIER"
    );
  }
  return value;
}

class Tenant {
  constructor({
    id,
    slug,
    name,
    architecture,
    region = "ap-south-1",
    maxProjects = 100,
  }) {
    this.id = validateIdentifier(id, "tenant id");
    this.slug = validateIdentifier(slug, "tenant slug");

    if (!name?.trim()) {
      throw new DomainError("Tenant name is required.", "INVALID_NAME");
    }
    if (!Object.values(Architecture).includes(architecture)) {
      throw new DomainError(
        "Unsupported database architecture.",
        "INVALID_ARCHITECTURE"
      );
    }
    if (!Number.isSafeInteger(maxProjects) || maxProjects < 1) {
      throw new DomainError("Invalid project quota.", "INVALID_QUOTA");
    }

    this.name = name.trim();
    this.architecture = architecture;
    this.region = region;
    this.maxProjects = maxProjects;
    this.status = TenantStatus.PROVISIONING;
    this.createdAt = new Date().toISOString();
  }
}

class TenantDirectory {
  #tenants = new Map();
  #slugs = new Map();

  register(tenant) {
    if (this.#tenants.has(tenant.id) || this.#slugs.has(tenant.slug)) {
      throw new DomainError(
        "Tenant ID and slug must be globally unique.",
        "DUPLICATE_TENANT"
      );
    }
    this.#tenants.set(tenant.id, tenant);
    this.#slugs.set(tenant.slug, tenant.id);
  }

  get(tenantId) {
    const tenant = this.#tenants.get(tenantId);
    if (!tenant) {
      throw new DomainError(`Unknown tenant: ${tenantId}`, "NOT_FOUND");
    }
    return tenant;
  }

  activeTenants() {
    return [...this.#tenants.values()].filter(
      (tenant) => tenant.status === TenantStatus.ACTIVE
    );
  }
}

class ResourceRouter {
  #routes = new Map();

  provision(tenant) {
    if (this.#routes.has(tenant.id)) {
      throw new DomainError("Route already exists.", "ROUTE_EXISTS");
    }

    const route = {
      architecture: tenant.architecture,
      schema: null,
      database: null,
      projects: new Map(),
      appliedMigrations: new Set(),
    };

    if (tenant.architecture === Architecture.SHARED_SCHEMA) {
      route.schema = "public";
      // Shared tables need tenant_id in every tenant-owned row and query.
    } else if (tenant.architecture === Architecture.SEPARATE_SCHEMA) {
      route.schema = `tenant_${tenant.id}`;
    } else {
      route.database = `db_${tenant.id}`;
    }

    this.#routes.set(tenant.id, route);
    return route;
  }

  getRoute(tenantId) {
    const route = this.#routes.get(tenantId);
    if (!route) {
      throw new DomainError("Tenant resources are missing.", "NO_ROUTE");
    }
    return route;
  }

  describe(tenantId) {
    const route = this.getRoute(tenantId);
    return Object.freeze({
      tenantId,
      architecture: route.architecture,
      schema: route.schema,
      database: route.database,
      projectCount: route.projects.size,
    });
  }
}

class GovernanceEngine extends EventEmitter {
  constructor() {
    super();
    this.directory = new TenantDirectory();
    this.router = new ResourceRouter();
    this.eventHistory = [];
    this.on("audit", (event) => {
      this.eventHistory.push(Object.freeze({ ...event }));
    });
  }

  #audit(type, tenantId, details = {}) {
    this.emit("audit", {
      eventId: randomUUID(),
      type,
      tenantId,
      at: new Date().toISOString(),
      details,
    });
  }

  provision(input) {
    const tenant = new Tenant(input);
    this.directory.register(tenant);

    try {
      this.router.provision(tenant);
      tenant.status = TenantStatus.ACTIVE;
      this.#audit("tenant.provisioned", tenant.id, {
        architecture: tenant.architecture,
        region: tenant.region,
      });
      return tenant;
    } catch (error) {
      tenant.status = TenantStatus.SUSPENDED;
      this.#audit("tenant.provisioning_failed", tenant.id, {
        reason: error.message,
      });
      throw error;
    }
  }

  resolveAuthorizedTenant(principal, requestedTenantId) {
    const tenant = this.directory.get(requestedTenantId);

    // Membership is evaluated for each operation. A cached route is not proof
    // that the current caller has permission to use it.
    if (!principal?.tenantIds?.has(requestedTenantId)) {
      throw new DomainError("Tenant membership required.", "FORBIDDEN");
    }
    if (tenant.status !== TenantStatus.ACTIVE) {
      throw new DomainError("Tenant is not active.", "TENANT_INACTIVE");
    }
    return tenant;
  }

  createProject(principal, tenantId, name) {
    const tenant = this.resolveAuthorizedTenant(principal, tenantId);
    if (typeof name !== "string" || !name.trim()) {
      throw new DomainError("Project name is required.", "INVALID_PROJECT");
    }

    const route = this.router.getRoute(tenantId);
    if (route.projects.size >= tenant.maxProjects) {
      throw new DomainError("Project quota exceeded.", "QUOTA_EXCEEDED");
    }

    const normalizedName = name.trim();
    for (const project of route.projects.values()) {
      if (project.name.toLocaleLowerCase("en-US") ===
          normalizedName.toLocaleLowerCase("en-US")) {
        throw new DomainError(
          "Project name already exists for this tenant.",
          "DUPLICATE_PROJECT"
        );
      }
    }

    const project = Object.freeze({
      id: randomUUID(),
      tenantId,
      name: normalizedName,
      createdAt: new Date().toISOString(),
    });

    route.projects.set(project.id, project);
    this.#audit("project.created", tenantId, {
      projectId: project.id,
      architecture: tenant.architecture,
    });
    return project;
  }

  listProjects(principal, tenantId) {
    this.resolveAuthorizedTenant(principal, tenantId);
    return [...this.router.getRoute(tenantId).projects.values()];
  }

  transitionTenant(tenantId, nextStatus) {
    const tenant = this.directory.get(tenantId);
    const permitted = {
      [TenantStatus.ACTIVE]: [
        TenantStatus.SUSPENDED,
        TenantStatus.DEPROVISIONED,
      ],
      [TenantStatus.SUSPENDED]: [
        TenantStatus.ACTIVE,
        TenantStatus.DEPROVISIONED,
      ],
      [TenantStatus.PROVISIONING]: [
        TenantStatus.ACTIVE,
        TenantStatus.SUSPENDED,
      ],
      [TenantStatus.DEPROVISIONED]: [],
    };

    if (!permitted[tenant.status]?.includes(nextStatus)) {
      throw new DomainError(
        `Invalid status transition: ${tenant.status} -> ${nextStatus}`,
        "INVALID_TRANSITION"
      );
    }

    tenant.status = nextStatus;
    this.#audit("tenant.status_changed", tenantId, { nextStatus });
  }

  applyMigration(version, migration, tenantIds) {
    if (!Number.isSafeInteger(version) || version < 1) {
      throw new DomainError("Invalid migration version.", "INVALID_VERSION");
    }

    const ids = tenantIds ?? this.directory.activeTenants().map((t) => t.id);
    const results = [];

    for (const tenantId of ids) {
      const tenant = this.directory.get(tenantId);
      const route = this.router.getRoute(tenantId);

      if (tenant.status !== TenantStatus.ACTIVE) {
        results.push({ tenantId, result: "skipped_inactive" });
        continue;
      }
      if (route.appliedMigrations.has(version)) {
        results.push({ tenantId, result: "already_applied" });
        continue;
      }

      try {
        // The callback receives the intended tenant and route, not a raw
        // user-supplied schema or database name.
        migration(tenant, this.router.describe(tenantId));
        route.appliedMigrations.add(version);
        this.#audit("migration.applied", tenantId, { version });
        results.push({ tenantId, result: "applied" });
      } catch (error) {
        this.#audit("migration.failed", tenantId, {
          version,
          reason: error.message,
        });
        results.push({
          tenantId,
          result: "failed",
          reason: error.message,
        });
      }
    }

    return results;
  }
}

function runScenario() {
  const platform = new GovernanceEngine();

  platform.on("audit", (event) => {
    if (event.type === "tenant.provisioned") {
      console.log(
        `[AUDIT] ${event.tenantId}: ${event.details.architecture}`
      );
    }
  });

  const configurations = [
    {
      id: "tenant_alpha",
      slug: "alpha",
      name: "Alpha Analytics",
      architecture: Architecture.SHARED_SCHEMA,
      maxProjects: 2,
    },
    {
      id: "tenant_beta",
      slug: "beta",
      name: "Beta Logistics",
      architecture: Architecture.SEPARATE_SCHEMA,
    },
    {
      id: "tenant_gamma",
      slug: "gamma",
      name: "Gamma Research",
      architecture: Architecture.SEPARATE_DATABASE,
    },
  ];

  for (const configuration of configurations) {
    platform.provision(configuration);
  }

  const alpha = { userId: "alice", tenantIds: new Set(["tenant_alpha"]) };
  const beta = { userId: "bob", tenantIds: new Set(["tenant_beta"]) };

  platform.createProject(alpha, "tenant_alpha", "Fraud Analytics");
  platform.createProject(alpha, "tenant_alpha", "Risk Dashboard");
  platform.createProject(beta, "tenant_beta", "Fleet Operations");

  console.log("\nResource routing:");
  for (const configuration of configurations) {
    console.log(platform.router.describe(configuration.id));
  }

  console.log("\nCross-tenant access attempt:");
  try {
    platform.listProjects(alpha, "tenant_beta");
  } catch (error) {
    console.log(`${error.code}: ${error.message}`);
  }

  console.log("\nMigration outcomes:");
  const migration = (tenant, route) => {
    if (tenant.id === "tenant_beta") {
      throw new Error("Simulated schema permission failure");
    }
    console.log(`Preparing version 4 for ${route.tenantId}`);
  };

  console.log(platform.applyMigration(4, migration));
  console.log(platform.applyMigration(4, migration));

  console.log("\nSuspension behavior:");
  platform.transitionTenant("tenant_beta", TenantStatus.SUSPENDED);
  try {
    platform.listProjects(beta, "tenant_beta");
  } catch (error) {
    console.log(`${error.code}: ${error.message}`);
  }

  console.log(`\nAudit events recorded: ${platform.eventHistory.length}`);
}

if (require.main === module) {
  runScenario();
}

module.exports = {
  Architecture,
  TenantStatus,
  Tenant,
  TenantDirectory,
  ResourceRouter,
  GovernanceEngine,
};
