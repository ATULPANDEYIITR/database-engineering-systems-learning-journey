-- PostgreSQL 15+
-- Multi-tenant database design: shared schema, separate schema,
-- and separate database placement.
--
-- This script creates a shared control-plane catalog and a shared-schema
-- application example. Separate-schema and separate-database placements are
-- represented in the registry and are intended to be provisioned by a trusted
-- deployment service with appropriately restricted database credentials.
--
-- Run with:
--   psql -v ON_ERROR_STOP=1 -f multi_tenant_database.sql
--
-- IMPORTANT:
-- PostgreSQL RLS is enabled below. In a production application, the connection
-- role must not own protected tables or have BYPASSRLS. Use a trusted method to
-- set app.tenant_id for each transaction. A user who can execute arbitrary SQL
-- as the application role may be able to change a custom setting, so stronger
-- threat models require trusted connection mediation or per-tenant database
-- roles and credentials.

BEGIN;

CREATE SCHEMA IF NOT EXISTS control_plane;
CREATE SCHEMA IF NOT EXISTS shared_app;

CREATE TABLE control_plane.tenants (
    tenant_id       text PRIMARY KEY,
    slug            text NOT NULL UNIQUE,
    display_name    text NOT NULL CHECK (length(trim(display_name)) > 0),
    architecture    text NOT NULL CHECK (
        architecture IN (
            'shared_schema',
            'separate_schema',
            'separate_database'
        )
    ),
    region          text NOT NULL CHECK (length(trim(region)) > 0),
    status          text NOT NULL DEFAULT 'provisioning' CHECK (
        status IN (
            'provisioning',
            'active',
            'suspended',
            'deprovisioned'
        )
    ),
    schema_name     text,
    database_name   text,
    connection_key  text,
    max_projects    integer NOT NULL DEFAULT 100 CHECK (max_projects > 0),
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now(),

    CHECK (
        (architecture = 'shared_schema'
            AND schema_name IS NULL
            AND database_name IS NULL
            AND connection_key IS NULL)
        OR
        (architecture = 'separate_schema'
            AND schema_name IS NOT NULL
            AND database_name IS NULL
            AND connection_key IS NULL)
        OR
        (architecture = 'separate_database'
            AND schema_name IS NULL
            AND database_name IS NOT NULL
            AND connection_key IS NOT NULL)
    )
);

CREATE UNIQUE INDEX uq_tenant_schema_name
    ON control_plane.tenants (schema_name)
    WHERE schema_name IS NOT NULL;

CREATE UNIQUE INDEX uq_tenant_database_name
    ON control_plane.tenants (database_name)
    WHERE database_name IS NOT NULL;

CREATE TABLE control_plane.tenant_memberships (
    tenant_id       text NOT NULL
                    REFERENCES control_plane.tenants(tenant_id),
    user_id         text NOT NULL,
    member_role     text NOT NULL CHECK (
        member_role IN ('owner', 'admin', 'editor', 'viewer')
    ),
    active          boolean NOT NULL DEFAULT true,
    created_at      timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, user_id)
);

CREATE INDEX idx_memberships_user_active
    ON control_plane.tenant_memberships (user_id, tenant_id)
    WHERE active;

CREATE TABLE shared_app.projects (
    project_id      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       text NOT NULL
                    REFERENCES control_plane.tenants(tenant_id),
    project_name    text NOT NULL CHECK (length(trim(project_name)) > 0),
    status          text NOT NULL DEFAULT 'active' CHECK (
        status IN ('active', 'archived')
    ),
    created_by      text NOT NULL,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, project_name),
    UNIQUE (tenant_id, project_id)
);

CREATE INDEX idx_projects_tenant_recent
    ON shared_app.projects (tenant_id, created_at DESC);

CREATE TABLE shared_app.project_members (
    tenant_id       text NOT NULL,
    project_id      uuid NOT NULL,
    user_id         text NOT NULL,
    member_role     text NOT NULL CHECK (
        member_role IN ('admin', 'editor', 'viewer')
    ),
    PRIMARY KEY (tenant_id, project_id, user_id),
    FOREIGN KEY (tenant_id, project_id)
        REFERENCES shared_app.projects (tenant_id, project_id)
        ON DELETE CASCADE
);

CREATE INDEX idx_project_members_user
    ON shared_app.project_members (user_id, tenant_id);

CREATE TABLE control_plane.schema_migrations (
    tenant_id       text NOT NULL
                    REFERENCES control_plane.tenants(tenant_id),
    version         integer NOT NULL CHECK (version > 0),
    checksum        text NOT NULL,
    status          text NOT NULL CHECK (
        status IN ('running', 'applied', 'failed')
    ),
    started_at      timestamptz NOT NULL DEFAULT now(),
    finished_at     timestamptz,
    error_message   text,
    PRIMARY KEY (tenant_id, version),
    CHECK (
        (status = 'applied' AND finished_at IS NOT NULL)
        OR status <> 'applied'
    )
);

CREATE INDEX idx_migrations_failed
    ON control_plane.schema_migrations (tenant_id, version)
    WHERE status = 'failed';

CREATE TABLE control_plane.audit_events (
    event_id        bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    tenant_id       text REFERENCES control_plane.tenants(tenant_id),
    actor_id        text NOT NULL,
    event_type      text NOT NULL,
    details         jsonb NOT NULL DEFAULT '{}'::jsonb,
    occurred_at     timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_audit_tenant_time
    ON control_plane.audit_events (tenant_id, occurred_at DESC);

-- The tenant setting is expected to be installed by trusted application
-- middleware inside the same transaction as the tenant's data operations.
CREATE OR REPLACE FUNCTION shared_app.current_tenant_id()
RETURNS text
LANGUAGE sql
STABLE
AS $function$
    SELECT NULLIF(current_setting('app.tenant_id', true), '')
$function$;

ALTER TABLE shared_app.projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE shared_app.projects FORCE ROW LEVEL SECURITY;

CREATE POLICY projects_tenant_isolation
    ON shared_app.projects
    USING (tenant_id = shared_app.current_tenant_id())
    WITH CHECK (tenant_id = shared_app.current_tenant_id());

ALTER TABLE shared_app.project_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE shared_app.project_members FORCE ROW LEVEL SECURITY;

CREATE POLICY project_members_tenant_isolation
    ON shared_app.project_members
    USING (tenant_id = shared_app.current_tenant_id())
    WITH CHECK (tenant_id = shared_app.current_tenant_id());

-- This trigger enforces active status and quota for shared-schema writes.
-- It does not replace authorization or RLS. The tenant row is locked so
-- concurrent project creation for one tenant cannot both exceed the quota.
CREATE OR REPLACE FUNCTION shared_app.validate_project_insert()
RETURNS trigger
LANGUAGE plpgsql
AS $function$
DECLARE
    tenant_status text;
    project_limit integer;
    current_count bigint;
BEGIN
    IF NEW.tenant_id IS DISTINCT FROM shared_app.current_tenant_id() THEN
        RAISE EXCEPTION 'Tenant context does not match project tenant'
            USING ERRCODE = '42501';
    END IF;

    SELECT status, max_projects
      INTO tenant_status, project_limit
      FROM control_plane.tenants
     WHERE tenant_id = NEW.tenant_id
     FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Unknown tenant: %', NEW.tenant_id
            USING ERRCODE = '23503';
    END IF;

    IF tenant_status <> 'active' THEN
        RAISE EXCEPTION 'Tenant % is not active', NEW.tenant_id
            USING ERRCODE = '55000';
    END IF;

    SELECT count(*)
      INTO current_count
      FROM shared_app.projects
     WHERE tenant_id = NEW.tenant_id;

    IF current_count >= project_limit THEN
        RAISE EXCEPTION 'Project quota exceeded for tenant %', NEW.tenant_id
            USING ERRCODE = '23514';
    END IF;

    NEW.project_name := trim(NEW.project_name);
    RETURN NEW;
END;
$function$;

CREATE TRIGGER trg_validate_project_insert
BEFORE INSERT ON shared_app.projects
FOR EACH ROW
EXECUTE FUNCTION shared_app.validate_project_insert();

-- Shared-schema example tenants.
INSERT INTO control_plane.tenants (
    tenant_id, slug, display_name, architecture, region,
    status, max_projects
)
VALUES
    ('tenant_alpha', 'alpha', 'Alpha Analytics',
     'shared_schema', 'ap-south-1', 'active', 2),
    ('tenant_beta', 'beta', 'Beta Logistics',
     'shared_schema', 'ap-south-1', 'active', 10),
    ('tenant_gamma', 'gamma', 'Gamma Research',
     'separate_database', 'eu-west-1', 'active', 500)
ON CONFLICT (tenant_id) DO NOTHING;

INSERT INTO control_plane.tenants (
    tenant_id, slug, display_name, architecture, region,
    status, database_name, connection_key, max_projects
)
VALUES (
    'tenant_gamma', 'gamma', 'Gamma Research',
    'separate_database', 'eu-west-1', 'active',
    'db_tenant_gamma', 'conn_tenant_gamma', 500
)
ON CONFLICT (tenant_id) DO NOTHING;

INSERT INTO control_plane.tenant_memberships (
    tenant_id, user_id, member_role
)
VALUES
    ('tenant_alpha', 'alice', 'owner'),
    ('tenant_beta', 'bob', 'admin'),
    ('tenant_gamma', 'carol', 'owner')
ON CONFLICT DO NOTHING;

-- Illustrative data for the shared-schema tenants. Each SET LOCAL value lasts
-- only for the current transaction and is reset automatically at transaction
-- end, reducing the risk of context leaking through a pooled connection.
SET LOCAL app.tenant_id = 'tenant_alpha';

INSERT INTO shared_app.projects (tenant_id, project_name, created_by)
VALUES
    ('tenant_alpha', 'Fraud Analytics', 'alice'),
    ('tenant_alpha', 'Risk Dashboard', 'alice');

SET LOCAL app.tenant_id = 'tenant_beta';

INSERT INTO shared_app.projects (tenant_id, project_name, created_by)
VALUES
    ('tenant_beta', 'Fleet Operations', 'bob'),
    ('tenant_beta', 'Delivery Intelligence', 'bob');

COMMIT;

-- Run tenant-scoped reports in explicit transactions.
BEGIN;
SET LOCAL app.tenant_id = 'tenant_alpha';

SELECT project_id, project_name, status, created_at
FROM shared_app.projects
ORDER BY created_at DESC;

SELECT tenant_id, count(*) AS project_count
FROM shared_app.projects
GROUP BY tenant_id;

COMMIT;

-- Architecture inventory: the control plane routes each tenant to its
-- shared tables, dedicated schema, or separate database connection.
SELECT
    tenant_id,
    display_name,
    architecture,
    region,
    status,
    schema_name,
    database_name,
    connection_key,
    max_projects
FROM control_plane.tenants
ORDER BY tenant_id;

-- Detect failed migrations that need operational intervention.
SELECT tenant_id, version, checksum, error_message, started_at
FROM control_plane.schema_migrations
WHERE status = 'failed'
ORDER BY started_at DESC;

-- Migration status per tenant. Separate-database migrations need to be run
-- against each target database, not merely recorded in this central catalog.
SELECT
    t.tenant_id,
    t.architecture,
    m.version,
    m.status,
    m.finished_at
FROM control_plane.tenants AS t
LEFT JOIN control_plane.schema_migrations AS m
    ON m.tenant_id = t.tenant_id
ORDER BY t.tenant_id, m.version;

-- Production deployment notes:
-- 1. Create tenant schemas and databases using a privileged provisioning
--    service, not dynamic SQL assembled from an untrusted tenant identifier.
-- 2. Grant each application role only the required schema or database access.
-- 3. Keep database credentials in a secret manager and rotate them independently.
-- 4. Use transaction-scoped tenant context and test RLS under the real runtime role.
-- 5. Use advisory locks or a migration orchestrator to coordinate schema changes.
-- 6. Treat deprovisioning as a controlled process with retention, backup,
--    export, legal hold, and deletion verification.
-- 7. A central catalog cannot create a PostgreSQL database inside the current
--    transaction. Database provisioning must be a separate administrative step.
