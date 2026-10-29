-- PostgreSQL Administration
-- Users, roles, permissions, and database management
--
-- Execute this script while connected to a PostgreSQL database with
-- sufficient privileges to create roles, schemas, functions, triggers,
-- and grants. The administrative objects are isolated in pg_admin_lab.
--
-- The script intentionally uses NOLOGIN group roles for permission
-- aggregation and separate LOGIN roles for human/application sessions.

BEGIN;

CREATE SCHEMA IF NOT EXISTS pg_admin_lab;

COMMENT ON SCHEMA pg_admin_lab IS
'Demonstration model for PostgreSQL users, roles, privileges, and administration.';

CREATE TABLE IF NOT EXISTS pg_admin_lab.admin_roles (
    role_id              BIGSERIAL PRIMARY KEY,
    role_name            TEXT NOT NULL UNIQUE,
    role_kind            TEXT NOT NULL CHECK (
        role_kind IN ('LOGIN', 'GROUP')
    ),
    is_superuser         BOOLEAN NOT NULL DEFAULT FALSE,
    can_create_database  BOOLEAN NOT NULL DEFAULT FALSE,
    can_create_role      BOOLEAN NOT NULL DEFAULT FALSE,
    inherit_privileges   BOOLEAN NOT NULL DEFAULT TRUE,
    connection_limit     INTEGER NOT NULL DEFAULT -1 CHECK (
        connection_limit = -1 OR connection_limit >= 0
    ),
    enabled              BOOLEAN NOT NULL DEFAULT TRUE,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE IF NOT EXISTS pg_admin_lab.role_memberships (
    member_role_id BIGINT NOT NULL
        REFERENCES pg_admin_lab.admin_roles(role_id)
        ON DELETE CASCADE,
    group_role_id BIGINT NOT NULL
        REFERENCES pg_admin_lab.admin_roles(role_id)
        ON DELETE CASCADE,
    granted_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (member_role_id, group_role_id),
    CHECK (member_role_id <> group_role_id)
);

CREATE TABLE IF NOT EXISTS pg_admin_lab.databases (
    database_id BIGSERIAL PRIMARY KEY,
    database_name TEXT NOT NULL UNIQUE,
    owner_role_id BIGINT NOT NULL
        REFERENCES pg_admin_lab.admin_roles(role_id),
    allow_connections BOOLEAN NOT NULL DEFAULT TRUE,
    connection_limit INTEGER NOT NULL DEFAULT -1 CHECK (
        connection_limit = -1 OR connection_limit >= 0
    ),
    environment TEXT NOT NULL CHECK (
        environment IN ('development', 'staging', 'production')
    ),
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE IF NOT EXISTS pg_admin_lab.schemas (
    schema_id BIGSERIAL PRIMARY KEY,
    database_id BIGINT NOT NULL
        REFERENCES pg_admin_lab.databases(database_id)
        ON DELETE CASCADE,
    schema_name TEXT NOT NULL,
    owner_role_id BIGINT NOT NULL
        REFERENCES pg_admin_lab.admin_roles(role_id),
    UNIQUE (database_id, schema_name)
);

CREATE TABLE IF NOT EXISTS pg_admin_lab.objects (
    object_id BIGSERIAL PRIMARY KEY,
    schema_id BIGINT NOT NULL
        REFERENCES pg_admin_lab.schemas(schema_id)
        ON DELETE CASCADE,
    object_name TEXT NOT NULL,
    object_type TEXT NOT NULL CHECK (
        object_type IN ('TABLE', 'SEQUENCE', 'FUNCTION', 'VIEW')
    ),
    owner_role_id BIGINT NOT NULL
        REFERENCES pg_admin_lab.admin_roles(role_id),
    UNIQUE (schema_id, object_name, object_type)
);

CREATE TABLE IF NOT EXISTS pg_admin_lab.object_privileges (
    privilege_id BIGSERIAL PRIMARY KEY,
    role_id BIGINT NOT NULL
        REFERENCES pg_admin_lab.admin_roles(role_id)
        ON DELETE CASCADE,
    object_id BIGINT NOT NULL
        REFERENCES pg_admin_lab.objects(object_id)
        ON DELETE CASCADE,
    privilege_name TEXT NOT NULL CHECK (
        privilege_name IN (
            'SELECT',
            'INSERT',
            'UPDATE',
            'DELETE',
            'REFERENCES',
            'TRIGGER',
            'USAGE',
            'CREATE',
            'EXECUTE'
        )
    ),
    grant_option BOOLEAN NOT NULL DEFAULT FALSE,
    granted_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (role_id, object_id, privilege_name)
);

CREATE TABLE IF NOT EXISTS pg_admin_lab.database_privileges (
    database_privilege_id BIGSERIAL PRIMARY KEY,
    role_id BIGINT NOT NULL
        REFERENCES pg_admin_lab.admin_roles(role_id)
        ON DELETE CASCADE,
    database_id BIGINT NOT NULL
        REFERENCES pg_admin_lab.databases(database_id)
        ON DELETE CASCADE,
    privilege_name TEXT NOT NULL CHECK (
        privilege_name IN ('CONNECT', 'CREATE', 'TEMPORARY')
    ),
    grant_option BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE (role_id, database_id, privilege_name)
);

CREATE TABLE IF NOT EXISTS pg_admin_lab.approval_policies (
    policy_id BIGSERIAL PRIMARY KEY,
    policy_name TEXT NOT NULL UNIQUE,
    required_reader_count INTEGER NOT NULL DEFAULT 0 CHECK (
        required_reader_count >= 0
    ),
    allow_writer_access BOOLEAN NOT NULL DEFAULT FALSE,
    production_only BOOLEAN NOT NULL DEFAULT FALSE,
    active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS pg_admin_lab.role_policy_assignments (
    role_id BIGINT NOT NULL
        REFERENCES pg_admin_lab.admin_roles(role_id)
        ON DELETE CASCADE,
    policy_id BIGINT NOT NULL
        REFERENCES pg_admin_lab.approval_policies(policy_id)
        ON DELETE CASCADE,
    assigned_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (role_id, policy_id)
);

CREATE TABLE IF NOT EXISTS pg_admin_lab.admin_audit (
    audit_id BIGSERIAL PRIMARY KEY,
    event_time TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    actor_role_id BIGINT
        REFERENCES pg_admin_lab.admin_roles(role_id)
        ON DELETE SET NULL,
    action_name TEXT NOT NULL,
    target_type TEXT,
    target_name TEXT,
    success BOOLEAN NOT NULL,
    detail TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_role_memberships_group
    ON pg_admin_lab.role_memberships(group_role_id);

CREATE INDEX IF NOT EXISTS idx_object_privileges_role
    ON pg_admin_lab.object_privileges(role_id);

CREATE INDEX IF NOT EXISTS idx_database_privileges_role
    ON pg_admin_lab.database_privileges(role_id);

CREATE INDEX IF NOT EXISTS idx_admin_audit_event_time
    ON pg_admin_lab.admin_audit(event_time DESC);

COMMENT ON TABLE pg_admin_lab.role_memberships IS
'Represents group-role membership separately from object privileges.';

COMMENT ON TABLE pg_admin_lab.object_privileges IS
'Models object-level GRANT decisions independently from role membership.';

COMMENT ON TABLE pg_admin_lab.admin_audit IS
'Administrative audit trail for permission and role-management events.';

CREATE OR REPLACE FUNCTION pg_admin_lab.prevent_membership_cycle()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.member_role_id = NEW.group_role_id THEN
        RAISE EXCEPTION 'A role cannot be granted to itself';
    END IF;

    IF EXISTS (
        WITH RECURSIVE reachable(role_id) AS (
            SELECT NEW.group_role_id

            UNION

            SELECT rm.group_role_id
            FROM pg_admin_lab.role_memberships rm
            JOIN reachable r
              ON r.role_id = rm.member_role_id
        )
        SELECT 1
        FROM reachable
        WHERE role_id = NEW.member_role_id
    ) THEN
        RAISE EXCEPTION
            'Role membership would create a circular inheritance path';
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_prevent_membership_cycle
ON pg_admin_lab.role_memberships;

CREATE TRIGGER trg_prevent_membership_cycle
BEFORE INSERT OR UPDATE
ON pg_admin_lab.role_memberships
FOR EACH ROW
EXECUTE FUNCTION pg_admin_lab.prevent_membership_cycle();

CREATE OR REPLACE FUNCTION pg_admin_lab.audit_role_change()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO pg_admin_lab.admin_audit (
        actor_role_id,
        action_name,
        target_type,
        target_name,
        success,
        detail
    )
    VALUES (
        NULL,
        TG_OP,
        'ROLE',
        NEW.role_name,
        TRUE,
        format(
            'Role record changed: %s',
            TG_OP
        )
    );

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_audit_role_change
ON pg_admin_lab.admin_roles;

CREATE TRIGGER trg_audit_role_change
AFTER INSERT OR UPDATE
ON pg_admin_lab.admin_roles
FOR EACH ROW
EXECUTE FUNCTION pg_admin_lab.audit_role_change();

CREATE OR REPLACE FUNCTION pg_admin_lab.effective_role_ids(
    p_role_id BIGINT
)
RETURNS TABLE(role_id BIGINT)
LANGUAGE sql
STABLE
AS $$
    WITH RECURSIVE inherited(role_id) AS (
        SELECT p_role_id

        UNION

        SELECT rm.group_role_id
        FROM pg_admin_lab.role_memberships rm
        JOIN inherited i
          ON i.role_id = rm.member_role_id
        JOIN pg_admin_lab.admin_roles r
          ON r.role_id = rm.member_role_id
        WHERE r.inherit_privileges = TRUE
    )
    SELECT role_id
    FROM inherited;
$$;

CREATE OR REPLACE FUNCTION pg_admin_lab.has_object_privilege(
    p_role_id BIGINT,
    p_object_id BIGINT,
    p_privilege TEXT
)
RETURNS BOOLEAN
LANGUAGE sql
STABLE
AS $$
    SELECT EXISTS (
        SELECT 1
        FROM pg_admin_lab.object_privileges op
        JOIN pg_admin_lab.effective_role_ids(p_role_id) er
          ON er.role_id = op.role_id
        WHERE op.object_id = p_object_id
          AND op.privilege_name = upper(p_privilege)
    );
$$;

CREATE OR REPLACE FUNCTION pg_admin_lab.has_database_privilege(
    p_role_id BIGINT,
    p_database_id BIGINT,
    p_privilege TEXT
)
RETURNS BOOLEAN
LANGUAGE sql
STABLE
AS $$
    SELECT
        r.is_superuser
        OR EXISTS (
            SELECT 1
            FROM pg_admin_lab.database_privileges dp
            JOIN pg_admin_lab.effective_role_ids(p_role_id) er
              ON er.role_id = dp.role_id
            WHERE dp.database_id = p_database_id
              AND dp.privilege_name = upper(p_privilege)
        )
    FROM pg_admin_lab.admin_roles r
    WHERE r.role_id = p_role_id;
$$;

INSERT INTO pg_admin_lab.admin_roles (
    role_name,
    role_kind,
    is_superuser,
    can_create_database,
    can_create_role,
    inherit_privileges,
    connection_limit
)
VALUES
    ('platform_admin', 'LOGIN', TRUE, TRUE, TRUE, TRUE, -1),
    ('app_owner', 'GROUP', FALSE, FALSE, FALSE, TRUE, -1),
    ('app_readonly', 'GROUP', FALSE, FALSE, FALSE, TRUE, -1),
    ('app_writer', 'GROUP', FALSE, FALSE, FALSE, TRUE, -1),
    ('api_service', 'LOGIN', FALSE, FALSE, FALSE, TRUE, 20),
    ('report_service', 'LOGIN', FALSE, FALSE, FALSE, TRUE, 5)
ON CONFLICT (role_name) DO NOTHING;

INSERT INTO pg_admin_lab.role_memberships (
    member_role_id,
    group_role_id
)
SELECT member.role_id, group_role.role_id
FROM (
    VALUES
        ('api_service', 'app_writer'),
        ('report_service', 'app_readonly')
) AS memberships(member_name, group_name)
JOIN pg_admin_lab.admin_roles member
  ON member.role_name = memberships.member_name
JOIN pg_admin_lab.admin_roles group_role
  ON group_role.role_name = memberships.group_name
ON CONFLICT DO NOTHING;

INSERT INTO pg_admin_lab.databases (
    database_name,
    owner_role_id,
    allow_connections,
    connection_limit,
    environment
)
SELECT
    'business_db',
    role_id,
    TRUE,
    100,
    'production'
FROM pg_admin_lab.admin_roles
WHERE role_name = 'app_owner'
ON CONFLICT (database_name) DO NOTHING;

INSERT INTO pg_admin_lab.schemas (
    database_id,
    schema_name,
    owner_role_id
)
SELECT
    d.database_id,
    'application',
    r.role_id
FROM pg_admin_lab.databases d
JOIN pg_admin_lab.admin_roles r
  ON r.role_name = 'app_owner'
WHERE d.database_name = 'business_db'
ON CONFLICT (database_id, schema_name) DO NOTHING;

INSERT INTO pg_admin_lab.objects (
    schema_id,
    object_name,
    object_type,
    owner_role_id
)
SELECT
    s.schema_id,
    object_name,
    object_type,
    owner.role_id
FROM pg_admin_lab.schemas s
JOIN pg_admin_lab.admin_roles owner
  ON owner.role_name = 'app_owner'
CROSS JOIN (
    VALUES
        ('customers', 'TABLE'),
        ('orders', 'TABLE'),
        ('customer_summary', 'VIEW')
) AS object_list(object_name, object_type)
WHERE s.schema_name = 'application'
ON CONFLICT (schema_id, object_name, object_type) DO NOTHING;

INSERT INTO pg_admin_lab.database_privileges (
    role_id,
    database_id,
    privilege_name
)
SELECT
    r.role_id,
    d.database_id,
    'CONNECT'
FROM pg_admin_lab.admin_roles r
CROSS JOIN pg_admin_lab.databases d
WHERE r.role_name IN (
    'app_owner',
    'app_readonly',
    'app_writer'
)
AND d.database_name = 'business_db'
ON CONFLICT DO NOTHING;

INSERT INTO pg_admin_lab.object_privileges (
    role_id,
    object_id,
    privilege_name
)
SELECT
    r.role_id,
    o.object_id,
    p.privilege_name
FROM pg_admin_lab.admin_roles r
JOIN pg_admin_lab.objects o
  ON o.object_type = 'TABLE'
CROSS JOIN (
    VALUES
        ('SELECT')
) AS p(privilege_name)
WHERE r.role_name = 'app_readonly'
ON CONFLICT DO NOTHING;

INSERT INTO pg_admin_lab.object_privileges (
    role_id,
    object_id,
    privilege_name
)
SELECT
    r.role_id,
    o.object_id,
    p.privilege_name
FROM pg_admin_lab.admin_roles r
JOIN pg_admin_lab.objects o
  ON o.object_type = 'TABLE'
CROSS JOIN (
    VALUES
        ('SELECT'),
        ('INSERT'),
        ('UPDATE')
) AS p(privilege_name)
WHERE r.role_name = 'app_writer'
AND o.object_name IN ('customers', 'orders')
ON CONFLICT DO NOTHING;

INSERT INTO pg_admin_lab.object_privileges (
    role_id,
    object_id,
    privilege_name
)
SELECT
    r.role_id,
    o.object_id,
    'SELECT'
FROM pg_admin_lab.admin_roles r
JOIN pg_admin_lab.objects o
  ON o.object_type = 'VIEW'
WHERE r.role_name = 'app_readonly'
ON CONFLICT DO NOTHING;

INSERT INTO pg_admin_lab.approval_policies (
    policy_name,
    required_reader_count,
    allow_writer_access,
    production_only
)
VALUES
    ('Production read policy', 1, FALSE, TRUE),
    ('Service write policy', 0, TRUE, FALSE)
ON CONFLICT (policy_name) DO NOTHING;

INSERT INTO pg_admin_lab.role_policy_assignments (
    role_id,
    policy_id
)
SELECT
    r.role_id,
    p.policy_id
FROM pg_admin_lab.admin_roles r
JOIN pg_admin_lab.approval_policies p
  ON p.policy_name = 'Production read policy'
WHERE r.role_name = 'app_readonly'
ON CONFLICT DO NOTHING;

-- PostgreSQL-specific administration:
-- group roles are preferable for permission aggregation because
-- privileges can be changed centrally without editing every login role.

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_roles
        WHERE rolname = 'pg_admin_lab_owner'
    ) THEN
        CREATE ROLE pg_admin_lab_owner NOLOGIN;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_roles
        WHERE rolname = 'pg_admin_lab_readonly'
    ) THEN
        CREATE ROLE pg_admin_lab_readonly NOLOGIN;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_roles
        WHERE rolname = 'pg_admin_lab_writer'
    ) THEN
        CREATE ROLE pg_admin_lab_writer NOLOGIN;
    END IF;
END;
$$;

GRANT USAGE ON SCHEMA pg_admin_lab
TO pg_admin_lab_owner, pg_admin_lab_readonly, pg_admin_lab_writer;

GRANT SELECT ON ALL TABLES IN SCHEMA pg_admin_lab
TO pg_admin_lab_readonly;

GRANT SELECT, INSERT, UPDATE, DELETE
ON pg_admin_lab.admin_audit
TO pg_admin_lab_writer;

ALTER DEFAULT PRIVILEGES IN SCHEMA pg_admin_lab
GRANT SELECT ON TABLES
TO pg_admin_lab_readonly;

ALTER DEFAULT PRIVILEGES IN SCHEMA pg_admin_lab
GRANT SELECT, INSERT, UPDATE, DELETE
ON TABLES
TO pg_admin_lab_writer;

-- A transaction demonstrates atomic privilege changes.
SAVEPOINT privilege_change;

INSERT INTO pg_admin_lab.object_privileges (
    role_id,
    object_id,
    privilege_name
)
SELECT
    r.role_id,
    o.object_id,
    'REFERENCES'
FROM pg_admin_lab.admin_roles r
JOIN pg_admin_lab.objects o
  ON o.object_name = 'orders'
 AND o.object_type = 'TABLE'
WHERE r.role_name = 'app_writer'
ON CONFLICT DO NOTHING;

RELEASE SAVEPOINT privilege_change;

COMMIT;

-- Reporting: role hierarchy.
SELECT
    member.role_name AS member_role,
    group_role.role_name AS inherited_group,
    member.inherit_privileges
FROM pg_admin_lab.role_memberships rm
JOIN pg_admin_lab.admin_roles member
  ON member.role_id = rm.member_role_id
JOIN pg_admin_lab.admin_roles group_role
  ON group_role.role_id = rm.group_role_id
ORDER BY member.role_name, group_role.role_name;

-- Reporting: object privileges.
SELECT
    r.role_name,
    o.object_type,
    s.schema_name,
    o.object_name,
    op.privilege_name,
    op.grant_option
FROM pg_admin_lab.object_privileges op
JOIN pg_admin_lab.admin_roles r
  ON r.role_id = op.role_id
JOIN pg_admin_lab.objects o
  ON o.object_id = op.object_id
JOIN pg_admin_lab.schemas s
  ON s.schema_id = o.schema_id
ORDER BY
    r.role_name,
    s.schema_name,
    o.object_name,
    op.privilege_name;

-- Reporting: effective roles for api_service.
SELECT
    r.role_name AS effective_role
FROM pg_admin_lab.effective_role_ids(
    (
        SELECT role_id
        FROM pg_admin_lab.admin_roles
        WHERE role_name = 'api_service'
    )
) effective
JOIN pg_admin_lab.admin_roles r
  ON r.role_id = effective.role_id
ORDER BY r.role_name;

-- Evaluation: api_service should inherit writer privileges.
SELECT
    pg_admin_lab.has_object_privilege(
        (
            SELECT role_id
            FROM pg_admin_lab.admin_roles
            WHERE role_name = 'api_service'
        ),
        (
            SELECT o.object_id
            FROM pg_admin_lab.objects o
            JOIN pg_admin_lab.schemas s
              ON s.schema_id = o.schema_id
            WHERE s.schema_name = 'application'
              AND o.object_name = 'orders'
              AND o.object_type = 'TABLE'
        ),
        'UPDATE'
    ) AS api_service_can_update_orders;

-- Evaluation: report_service should be able to read
-- but should not be able to delete.
SELECT
    pg_admin_lab.has_object_privilege(
        (
            SELECT role_id
            FROM pg_admin_lab.admin_roles
            WHERE role_name = 'report_service'
        ),
        (
            SELECT o.object_id
            FROM pg_admin_lab.objects o
            JOIN pg_admin_lab.schemas s
              ON s.schema_id = o.schema_id
            WHERE s.schema_name = 'application'
              AND o.object_name = 'customers'
              AND o.object_type = 'TABLE'
        ),
        'SELECT'
    ) AS report_service_can_select,
    pg_admin_lab.has_object_privilege(
        (
            SELECT role_id
            FROM pg_admin_lab.admin_roles
            WHERE role_name = 'report_service'
        ),
        (
            SELECT o.object_id
            FROM pg_admin_lab.objects o
            JOIN pg_admin_lab.schemas s
              ON s.schema_id = o.schema_id
            WHERE s.schema_name = 'application'
              AND o.object_name = 'customers'
              AND o.object_type = 'TABLE'
        ),
        'DELETE'
    ) AS report_service_can_delete;

-- Database-management reporting.
SELECT
    d.database_name,
    owner.role_name AS owner_role,
    d.environment,
    d.allow_connections,
    d.connection_limit
FROM pg_admin_lab.databases d
JOIN pg_admin_lab.admin_roles owner
  ON owner.role_id = d.owner_role_id
ORDER BY d.database_name;

-- Policy reporting.
SELECT
    r.role_name,
    p.policy_name,
    p.required_reader_count,
    p.allow_writer_access,
    p.production_only,
    p.active
FROM pg_admin_lab.role_policy_assignments rpa
JOIN pg_admin_lab.admin_roles r
  ON r.role_id = rpa.role_id
JOIN pg_admin_lab.approval_policies p
  ON p.policy_id = rpa.policy_id
ORDER BY r.role_name, p.policy_name;

-- PostgreSQL catalog inspection. These queries show the distinction
-- between the teaching model above and actual server-side roles.
SELECT
    rolname,
    rolsuper,
    rolcreatedb,
    rolcreaterole,
    rolinherit,
    rolcanlogin,
    rolconnlimit
FROM pg_roles
WHERE rolname IN (
    'pg_admin_lab_owner',
    'pg_admin_lab_readonly',
    'pg_admin_lab_writer'
)
ORDER BY rolname;
