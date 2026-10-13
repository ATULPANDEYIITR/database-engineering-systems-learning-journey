import java.time.Instant;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.TreeMap;
import java.util.UUID;

/*
 * Enterprise multi-tenant database placement and governance model.
 *
 * Java 17+, standard library only.
 *
 * The model separates tenant identity, infrastructure placement, authorization,
 * project lifecycle, migration history, and placement policy.
 */

public class MultiTenantDatabase {
    enum Architecture {
        SHARED_SCHEMA,
        SEPARATE_SCHEMA,
        SEPARATE_DATABASE
    }

    enum TenantStatus {
        PROVISIONING,
        ACTIVE,
        SUSPENDED,
        DEPROVISIONED
    }

    enum IsolationRequirement {
        STANDARD,
        DEDICATED_BACKUP,
        INDEPENDENT_CREDENTIALS,
        STRICT_PERFORMANCE
    }

    static final class GovernanceException extends RuntimeException {
        GovernanceException(String message) {
            super(message);
        }
    }

    record PlacementRequest(
        String tenantId,
        String slug,
        String name,
        String region,
        long expectedUsers,
        long expectedProjects,
        double monthlyBudget,
        Set<IsolationRequirement> requirements
    ) {
        PlacementRequest {
            validateIdentifier(tenantId, "tenantId");
            validateIdentifier(slug, "slug");
            if (name == null || name.isBlank()) {
                throw new IllegalArgumentException("Tenant name is required.");
            }
            if (region == null || region.isBlank()) {
                throw new IllegalArgumentException("Region is required.");
            }
            if (expectedUsers < 1 || expectedProjects < 1) {
                throw new IllegalArgumentException("Workload must be positive.");
            }
            if (monthlyBudget < 0) {
                throw new IllegalArgumentException("Budget cannot be negative.");
            }
            requirements = Set.copyOf(requirements);
        }
    }

    record PlacementDecision(
        Architecture architecture,
        double estimatedMonthlyCost,
        String rationale
    ) {}

    record Tenant(
        String id,
        String slug,
        String name,
        String region,
        Architecture architecture,
        TenantStatus status,
        int projectQuota
    ) {
        Tenant {
            validateIdentifier(id, "tenantId");
            validateIdentifier(slug, "slug");
            Objects.requireNonNull(architecture);
            Objects.requireNonNull(status);
            if (name == null || name.isBlank()) {
                throw new IllegalArgumentException("Name is required.");
            }
            if (projectQuota < 1) {
                throw new IllegalArgumentException("Quota must be positive.");
            }
        }

        Tenant withStatus(TenantStatus nextStatus) {
            return new Tenant(
                id, slug, name, region, architecture, nextStatus, projectQuota
            );
        }
    }

    record Project(
        String id,
        String tenantId,
        String name,
        Instant createdAt
    ) {}

    record Principal(String userId, Set<String> tenantMemberships) {
        Principal {
            if (userId == null || userId.isBlank()) {
                throw new IllegalArgumentException("User ID is required.");
            }
            tenantMemberships = Set.copyOf(tenantMemberships);
        }
    }

    record ResourceRoute(
        String tenantId,
        Architecture architecture,
        String schemaName,
        String databaseName
    ) {}

    static void validateIdentifier(String value, String label) {
        if (value == null ||
            !value.matches("[a-z][a-z0-9_]{2,39}")) {
            throw new IllegalArgumentException(
                label + " must be a valid lowercase identifier."
            );
        }
    }

    static final class PlacementPolicy {
        PlacementDecision evaluate(PlacementRequest request) {
            double shared = 35.0
                + request.expectedUsers() * 0.0008
                + request.expectedProjects() * 0.01;
            double schema = 65.0
                + request.expectedUsers() * 0.001
                + request.expectedProjects() * 0.012;
            double database = 180.0
                + request.expectedUsers() * 0.003
                + request.expectedProjects() * 0.02;

            boolean dedicated = request.requirements().stream().anyMatch(
                requirement -> requirement != IsolationRequirement.STANDARD
            );

            if (dedicated) {
                if (database > request.monthlyBudget()) {
                    throw new GovernanceException(
                        "Required isolation cannot fit the supplied budget."
                    );
                }
                return new PlacementDecision(
                    Architecture.SEPARATE_DATABASE,
                    database,
                    "Independent database supports dedicated credentials, "
                        + "backups, and workload controls."
                );
            }

            if (request.expectedUsers() > 10_000 ||
                request.expectedProjects() > 5_000) {
                if (database <= request.monthlyBudget()) {
                    return new PlacementDecision(
                        Architecture.SEPARATE_DATABASE,
                        database,
                        "High workload merits independent database resources."
                    );
                }
                if (schema <= request.monthlyBudget()) {
                    return new PlacementDecision(
                        Architecture.SEPARATE_SCHEMA,
                        schema,
                        "Separate schema balances workload separation and cost."
                    );
                }
            }

            if (shared <= request.monthlyBudget()) {
                return new PlacementDecision(
                    Architecture.SHARED_SCHEMA,
                    shared,
                    "Shared tables offer low operational overhead."
                );
            }
            if (schema <= request.monthlyBudget()) {
                return new PlacementDecision(
                    Architecture.SEPARATE_SCHEMA,
                    schema,
                    "Schema separation fits the available budget."
                );
            }

            throw new GovernanceException(
                "No architecture satisfies the estimated budget."
            );
        }
    }

    static final class TenantDirectory {
        private final Map<String, Tenant> tenants = new HashMap<>();
        private final Map<String, String> tenantBySlug = new HashMap<>();

        void register(Tenant tenant) {
            if (tenants.containsKey(tenant.id()) ||
                tenantBySlug.containsKey(tenant.slug())) {
                throw new GovernanceException(
                    "Tenant ID and slug must be unique."
                );
            }
            tenants.put(tenant.id(), tenant);
            tenantBySlug.put(tenant.slug(), tenant.id());
        }

        Tenant get(String tenantId) {
            Tenant tenant = tenants.get(tenantId);
            if (tenant == null) {
                throw new GovernanceException("Unknown tenant: " + tenantId);
            }
            return tenant;
        }

        void update(Tenant tenant) {
            if (!tenants.containsKey(tenant.id())) {
                throw new GovernanceException("Cannot update unknown tenant.");
            }
            tenants.put(tenant.id(), tenant);
        }

        List<Tenant> activeTenants() {
            return tenants.values().stream()
                .filter(t -> t.status() == TenantStatus.ACTIVE)
                .sorted(Comparator.comparing(Tenant::id))
                .toList();
        }
    }

    static final class TenantResources {
        private final ResourceRoute route;
        private final Map<String, Project> projects = new HashMap<>();
        private final Set<String> normalizedNames = new HashSet<>();
        private final Set<Integer> migrationVersions = new HashSet<>();

        TenantResources(ResourceRoute route) {
            this.route = route;
        }
    }

    static final class MigrationService {
        private final TenantDirectory directory;
        private final Map<String, TenantResources> resources;

        MigrationService(
            TenantDirectory directory,
            Map<String, TenantResources> resources
        ) {
            this.directory = directory;
            this.resources = resources;
        }

        Map<String, String> apply(int version) {
            if (version < 1) {
                throw new IllegalArgumentException(
                    "Migration version must be positive."
                );
            }

            Map<String, String> outcomes = new TreeMap<>();
            for (Tenant tenant : directory.activeTenants()) {
                TenantResources tenantResources = resources.get(tenant.id());
                if (tenantResources.migrationVersions.contains(version)) {
                    outcomes.put(tenant.id(), "already applied");
                    continue;
                }

                try {
                    // In production, the migration executor uses the route to
                    // choose the target connection or schema and persists its
                    // result in a durable migration-history table.
                    if (tenantResources.route.architecture()
                        == Architecture.SEPARATE_DATABASE
                        && tenantResources.route.databaseName() == null) {
                        throw new GovernanceException(
                            "Database route is missing."
                        );
                    }
                    tenantResources.migrationVersions.add(version);
                    outcomes.put(tenant.id(), "applied");
                } catch (RuntimeException exception) {
                    outcomes.put(
                        tenant.id(), "failed: " + exception.getMessage()
                    );
                }
            }
            return outcomes;
        }
    }

    static final class TenantService {
        private final TenantDirectory directory = new TenantDirectory();
        private final Map<String, TenantResources> resources = new HashMap<>();

        Tenant provision(PlacementRequest request, PlacementPolicy policy) {
            PlacementDecision decision = policy.evaluate(request);

            Tenant tenant = new Tenant(
                request.tenantId(),
                request.slug(),
                request.name(),
                request.region(),
                decision.architecture(),
                TenantStatus.PROVISIONING,
                100
            );

            directory.register(tenant);
            ResourceRoute route;

            switch (decision.architecture()) {
                case SHARED_SCHEMA -> route = new ResourceRoute(
                    tenant.id(), decision.architecture(), "public", null
                );
                case SEPARATE_SCHEMA -> route = new ResourceRoute(
                    tenant.id(),
                    decision.architecture(),
                    "tenant_" + tenant.id(),
                    null
                );
                case SEPARATE_DATABASE -> route = new ResourceRoute(
                    tenant.id(),
                    decision.architecture(),
                    null,
                    "db_" + tenant.id()
                );
                default -> throw new IllegalStateException(
                    "Unsupported architecture."
                );
            }

            validateRoute(route);
            resources.put(tenant.id(), new TenantResources(route));
            Tenant active = tenant.withStatus(TenantStatus.ACTIVE);
            directory.update(active);
            return active;
        }

        private void validateRoute(ResourceRoute route) {
            if (route.architecture() == Architecture.SEPARATE_SCHEMA) {
                validateIdentifier(route.schemaName(), "schemaName");
            }
            if (route.architecture() == Architecture.SEPARATE_DATABASE) {
                validateIdentifier(route.databaseName(), "databaseName");
            }
        }

        private Tenant authorize(Principal principal, String tenantId) {
            Tenant tenant = directory.get(tenantId);
            if (!principal.tenantMemberships().contains(tenantId)) {
                throw new GovernanceException("Tenant access denied.");
            }
            if (tenant.status() != TenantStatus.ACTIVE) {
                throw new GovernanceException("Tenant is not active.");
            }
            return tenant;
        }

        Project createProject(
            Principal principal,
            String tenantId,
            String projectName
        ) {
            Tenant tenant = authorize(principal, tenantId);
            if (projectName == null || projectName.isBlank()) {
                throw new IllegalArgumentException(
                    "Project name is required."
                );
            }

            TenantResources tenantResources = resources.get(tenantId);
            if (tenantResources.projects.size() >= tenant.projectQuota()) {
                throw new GovernanceException("Project quota exceeded.");
            }

            String normalized = projectName.strip().toLowerCase();
            if (!tenantResources.normalizedNames.add(normalized)) {
                throw new GovernanceException(
                    "Project name already exists in this tenant."
                );
            }

            Project project = new Project(
                UUID.randomUUID().toString(),
                tenantId,
                projectName.strip(),
                Instant.now()
            );
            tenantResources.projects.put(project.id(), project);
            return project;
        }

        List<Project> listProjects(Principal principal, String tenantId) {
            authorize(principal, tenantId);
            return resources.get(tenantId).projects.values().stream()
                .sorted(Comparator.comparing(Project::createdAt))
                .toList();
        }

        void transition(String tenantId, TenantStatus next) {
            Tenant current = directory.get(tenantId);
            boolean permitted = switch (current.status()) {
                case ACTIVE -> next == TenantStatus.SUSPENDED
                    || next == TenantStatus.DEPROVISIONED;
                case SUSPENDED -> next == TenantStatus.ACTIVE
                    || next == TenantStatus.DEPROVISIONED;
                case PROVISIONING -> next == TenantStatus.ACTIVE
                    || next == TenantStatus.SUSPENDED;
                case DEPROVISIONED -> false;
            };

            if (!permitted) {
                throw new GovernanceException(
                    "Invalid tenant status transition."
                );
            }
            directory.update(current.withStatus(next));
        }

        void printReport() {
            for (Tenant tenant : directory.activeTenants()) {
                TenantResources resource = resources.get(tenant.id());
                System.out.printf(
                    "%s | %s | schema=%s | database=%s | projects=%d%n",
                    tenant.id(),
                    tenant.architecture(),
                    resource.route.schemaName(),
                    resource.route.databaseName(),
                    resource.projects.size()
                );
            }
        }

        TenantDirectory directory() {
            return directory;
        }

        Map<String, TenantResources> resources() {
            return resources;
        }
    }

    public static void main(String[] args) {
        PlacementPolicy policy = new PlacementPolicy();
        TenantService service = new TenantService();

        List<PlacementRequest> requests = List.of(
            new PlacementRequest(
                "tenant_alpha", "alpha", "Alpha Analytics", "ap-south-1",
                80, 12, 100,
                Set.of(IsolationRequirement.STANDARD)
            ),
            new PlacementRequest(
                "tenant_beta", "beta", "Beta Logistics", "ap-south-1",
                900, 300, 1000,
                Set.of(IsolationRequirement.STANDARD)
            ),
            new PlacementRequest(
                "tenant_gamma", "gamma", "Gamma Research", "eu-west-1",
                2000, 120, 500,
                Set.of(
                    IsolationRequirement.DEDICATED_BACKUP,
                    IsolationRequirement.INDEPENDENT_CREDENTIALS
                )
            )
        );

        for (PlacementRequest request : requests) {
            PlacementDecision decision = policy.evaluate(request);
            System.out.printf(
                "%s -> %s; estimated monthly cost %.2f%n",
                request.tenantId(),
                decision.architecture(),
                decision.estimatedMonthlyCost()
            );
            service.provision(request, policy);
        }

        Principal alphaUser = new Principal(
            "alice", Set.of("tenant_alpha")
        );
        Principal betaUser = new Principal(
            "bob", Set.of("tenant_beta")
        );

        service.createProject(
            alphaUser, "tenant_alpha", "Fraud Analytics"
        );
        service.createProject(
            alphaUser, "tenant_alpha", "Risk Dashboard"
        );
        service.createProject(
            betaUser, "tenant_beta", "Fleet Operations"
        );

        System.out.println("\nActive tenant resource routes:");
        service.printReport();

        System.out.println("\nCross-tenant access test:");
        try {
            service.listProjects(alphaUser, "tenant_beta");
            throw new AssertionError("Cross-tenant access should be denied.");
        } catch (GovernanceException expected) {
            System.out.println("Denied: " + expected.getMessage());
        }

        MigrationService migrations = new MigrationService(
            service.directory(), service.resources()
        );
        System.out.println("\nMigration version 7:");
        System.out.println(migrations.apply(7));
        System.out.println("Retrying migration version 7:");
        System.out.println(migrations.apply(7));

        service.transition("tenant_beta", TenantStatus.SUSPENDED);
        try {
            service.listProjects(betaUser, "tenant_beta");
        } catch (GovernanceException expected) {
            System.out.println("Suspended tenant blocked: "
                + expected.getMessage());
        }
    }
}
