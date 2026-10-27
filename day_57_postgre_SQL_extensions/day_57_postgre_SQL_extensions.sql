-- PostgreSQL Extensions and PostGIS Ecosystem
-- Requires a PostgreSQL installation with PostGIS packages available.
-- The extension names and supported versions depend on the installed
-- PostgreSQL/PostGIS distribution.

DROP SCHEMA IF EXISTS spatial_extension_lab CASCADE;
CREATE SCHEMA spatial_extension_lab;
SET search_path = spatial_extension_lab, public;

-- PostGIS adds geometry/geography types, spatial predicates, functions,
-- coordinate-reference-system support, and spatial index operator classes.
CREATE EXTENSION IF NOT EXISTS postgis;

-- Useful supporting extension for UUID identifiers.
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE extension_catalog (
    extension_name text PRIMARY KEY,
    category text NOT NULL,
    description text NOT NULL,
    operational_status text NOT NULL
        CHECK (operational_status IN ('available', 'installed', 'disabled'))
);

INSERT INTO extension_catalog (
    extension_name,
    category,
    description,
    operational_status
)
VALUES
    (
        'postgis',
        'spatial',
        'Geometry, geography, spatial functions, predicates and indexes',
        'installed'
    ),
    (
        'pgcrypto',
        'security',
        'Cryptographic functions and UUID generation',
        'installed'
    ),
    (
        'postgis_raster',
        'spatial',
        'Raster processing support associated with PostGIS',
        'available'
    ),
    (
        'postgis_topology',
        'spatial',
        'Topology-aware spatial data model',
        'available'
    );

CREATE TABLE repository (
    repository_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    repository_name text NOT NULL UNIQUE,
    owner_name text NOT NULL
);

CREATE TABLE branch (
    branch_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    repository_id uuid NOT NULL
        REFERENCES repository(repository_id)
        ON DELETE CASCADE,
    branch_name text NOT NULL,
    is_default boolean NOT NULL DEFAULT false,
    is_protected boolean NOT NULL DEFAULT false,
    allow_direct_push boolean NOT NULL DEFAULT false,
    allow_force_push boolean NOT NULL DEFAULT false,
    allow_deletion boolean NOT NULL DEFAULT false,
    UNIQUE (repository_id, branch_name)
);

CREATE TABLE commit_record (
    commit_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    repository_id uuid NOT NULL
        REFERENCES repository(repository_id)
        ON DELETE CASCADE,
    commit_hash text NOT NULL,
    author_name text NOT NULL,
    committed_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (repository_id, commit_hash)
);

CREATE TABLE pull_request (
    pull_request_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    repository_id uuid NOT NULL
        REFERENCES repository(repository_id)
        ON DELETE CASCADE,
    source_branch_id bigint NOT NULL
        REFERENCES branch(branch_id),
    target_branch_id bigint NOT NULL
        REFERENCES branch(branch_id),
    title text NOT NULL,
    state text NOT NULL
        CHECK (state IN ('draft', 'open', 'closed', 'merged')),
    head_commit_id bigint NOT NULL
        REFERENCES commit_record(commit_id),
    base_commit_id bigint NOT NULL
        REFERENCES commit_record(commit_id),
    created_at timestamptz NOT NULL DEFAULT now(),
    closed_at timestamptz,
    merged_at timestamptz,
    CHECK (source_branch_id <> target_branch_id),
    CHECK (
        (state = 'merged' AND merged_at IS NOT NULL)
        OR state <> 'merged'
    )
);

CREATE TABLE reviewer (
    reviewer_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    login_name text NOT NULL UNIQUE,
    active boolean NOT NULL DEFAULT true
);

CREATE TABLE review (
    review_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    pull_request_id bigint NOT NULL
        REFERENCES pull_request(pull_request_id)
        ON DELETE CASCADE,
    reviewer_id bigint NOT NULL
        REFERENCES reviewer(reviewer_id),
    review_state text NOT NULL
        CHECK (review_state IN (
            'commented',
            'approved',
            'changes_requested',
            'dismissed'
        )),
    submitted_at timestamptz NOT NULL DEFAULT now(),
    commit_id bigint NOT NULL
        REFERENCES commit_record(commit_id)
);

CREATE TABLE review_comment (
    comment_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    review_id bigint NOT NULL
        REFERENCES review(review_id)
        ON DELETE CASCADE,
    file_path text NOT NULL,
    line_number integer CHECK (line_number > 0),
    comment_text text NOT NULL,
    resolved boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE conversation (
    conversation_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    pull_request_id bigint NOT NULL
        REFERENCES pull_request(pull_request_id)
        ON DELETE CASCADE,
    topic text NOT NULL,
    resolved boolean NOT NULL DEFAULT false
);

CREATE TABLE status_check (
    status_check_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    pull_request_id bigint NOT NULL
        REFERENCES pull_request(pull_request_id)
        ON DELETE CASCADE,
    check_name text NOT NULL,
    status text NOT NULL
        CHECK (status IN ('pending', 'passed', 'failed', 'cancelled')),
    commit_id bigint NOT NULL
        REFERENCES commit_record(commit_id),
    completed_at timestamptz,
    UNIQUE (pull_request_id, check_name, commit_id)
);

CREATE TABLE branch_protection_policy (
    policy_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    branch_id bigint NOT NULL UNIQUE
        REFERENCES branch(branch_id)
        ON DELETE CASCADE,
    required_reviews integer NOT NULL DEFAULT 0
        CHECK (required_reviews >= 0),
    require_conversation_resolution boolean NOT NULL DEFAULT false,
    require_status_checks boolean NOT NULL DEFAULT true,
    require_linear_history boolean NOT NULL DEFAULT false,
    prohibit_force_push boolean NOT NULL DEFAULT true,
    prohibit_deletion boolean NOT NULL DEFAULT true,
    prohibit_direct_push boolean NOT NULL DEFAULT true,
    administrator_bypass boolean NOT NULL DEFAULT false
);

CREATE TABLE approval_requirement (
    requirement_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    policy_id bigint NOT NULL
        REFERENCES branch_protection_policy(policy_id)
        ON DELETE CASCADE,
    required_reviewer_group text NOT NULL,
    required_count integer NOT NULL
        CHECK (required_count > 0),
    UNIQUE (policy_id, required_reviewer_group)
);

CREATE TABLE reviewer_group_member (
    reviewer_id bigint NOT NULL
        REFERENCES reviewer(reviewer_id)
        ON DELETE CASCADE,
    reviewer_group text NOT NULL,
    PRIMARY KEY (reviewer_id, reviewer_group)
);

CREATE TABLE spatial_facility (
    facility_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    facility_name text NOT NULL UNIQUE,
    facility_type text NOT NULL
        CHECK (facility_type IN ('office', 'depot', 'warehouse', 'sensor')),
    location geography(Point, 4326) NOT NULL,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE spatial_zone (
    zone_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    zone_name text NOT NULL UNIQUE,
    boundary geography(Polygon, 4326) NOT NULL
);

-- GiST indexes are the central performance mechanism for common
-- PostGIS proximity, containment, intersection, and bounding-box queries.
CREATE INDEX spatial_facility_location_gist
    ON spatial_facility
    USING gist (location);

CREATE INDEX spatial_zone_boundary_gist
    ON spatial_zone
    USING gist (boundary);

CREATE INDEX status_check_pr_status_idx
    ON status_check (pull_request_id, status);

CREATE INDEX review_pr_state_idx
    ON review (pull_request_id, review_state);

CREATE INDEX conversation_pr_resolution_idx
    ON conversation (pull_request_id, resolved);

INSERT INTO repository (repository_name, owner_name)
VALUES ('geo-platform', 'platform-engineering');

INSERT INTO branch (
    repository_id,
    branch_name,
    is_default,
    is_protected,
    allow_direct_push,
    allow_force_push,
    allow_deletion
)
SELECT
    repository_id,
    'main',
    true,
    true,
    false,
    false,
    false
FROM repository
WHERE repository_name = 'geo-platform';

INSERT INTO branch (
    repository_id,
    branch_name,
    is_default,
    is_protected,
    allow_direct_push,
    allow_force_push,
    allow_deletion
)
SELECT
    repository_id,
    'feature/spatial-index',
    false,
    false,
    true,
    true,
    true
FROM repository
WHERE repository_name = 'geo-platform';

INSERT INTO commit_record (
    repository_id,
    commit_hash,
    author_name
)
SELECT repository_id, 'a1b2c3d4', 'developer_one'
FROM repository
WHERE repository_name = 'geo-platform';

INSERT INTO commit_record (
    repository_id,
    commit_hash,
    author_name
)
SELECT repository_id, 'e5f6g7h8', 'developer_one'
FROM repository
WHERE repository_name = 'geo-platform';

INSERT INTO pull_request (
    repository_id,
    source_branch_id,
    target_branch_id,
    title,
    state,
    head_commit_id,
    base_commit_id
)
SELECT
    r.repository_id,
    source.branch_id,
    target.branch_id,
    'Add spatial facility index',
    'open',
    head.commit_id,
    base.commit_id
FROM repository r
JOIN branch source
    ON source.repository_id = r.repository_id
   AND source.branch_name = 'feature/spatial-index'
JOIN branch target
    ON target.repository_id = r.repository_id
   AND target.branch_name = 'main'
JOIN commit_record head
    ON head.repository_id = r.repository_id
   AND head.commit_hash = 'e5f6g7h8'
JOIN commit_record base
    ON base.repository_id = r.repository_id
   AND base.commit_hash = 'a1b2c3d4'
WHERE r.repository_name = 'geo-platform';

INSERT INTO reviewer (login_name)
VALUES
    ('spatial-reviewer'),
    ('security-reviewer'),
    ('inactive-reviewer');

UPDATE reviewer
SET active = false
WHERE login_name = 'inactive-reviewer';

INSERT INTO reviewer_group_member (reviewer_id, reviewer_group)
SELECT reviewer_id, 'spatial'
FROM reviewer
WHERE login_name = 'spatial-reviewer';

INSERT INTO reviewer_group_member (reviewer_id, reviewer_group)
SELECT reviewer_id, 'security'
FROM reviewer
WHERE login_name = 'security-reviewer';

INSERT INTO review (
    pull_request_id,
    reviewer_id,
    review_state,
    commit_id
)
SELECT
    pr.pull_request_id,
    reviewer.reviewer_id,
    'approved',
    pr.head_commit_id
FROM pull_request pr
JOIN reviewer
    ON reviewer.login_name = 'spatial-reviewer';

INSERT INTO review (
    pull_request_id,
    reviewer_id,
    review_state,
    commit_id
)
SELECT
    pr.pull_request_id,
    reviewer.reviewer_id,
    'approved',
    pr.head_commit_id
FROM pull_request pr
JOIN reviewer
    ON reviewer.login_name = 'security-reviewer';

INSERT INTO conversation (
    pull_request_id,
    topic,
    resolved
)
SELECT pull_request_id, 'Use geography for earth-distance queries', true
FROM pull_request;

INSERT INTO status_check (
    pull_request_id,
    check_name,
    status,
    commit_id,
    completed_at
)
SELECT
    pull_request_id,
    check_name,
    'passed',
    head_commit_id,
    now()
FROM pull_request
CROSS JOIN (
    VALUES
        ('unit-tests'),
        ('schema-validation'),
        ('security-scan')
) AS checks(check_name);

INSERT INTO branch_protection_policy (
    branch_id,
    required_reviews,
    require_conversation_resolution,
    require_status_checks,
    require_linear_history,
    prohibit_force_push,
    prohibit_deletion,
    prohibit_direct_push,
    administrator_bypass
)
SELECT
    branch_id,
    2,
    true,
    true,
    true,
    true,
    true,
    true,
    false
FROM branch
WHERE branch_name = 'main';

INSERT INTO approval_requirement (
    policy_id,
    required_reviewer_group,
    required_count
)
SELECT policy_id, 'spatial', 1
FROM branch_protection_policy;

INSERT INTO approval_requirement (
    policy_id,
    required_reviewer_group,
    required_count
)
SELECT policy_id, 'security', 1
FROM branch_protection_policy;

INSERT INTO spatial_facility (
    facility_name,
    facility_type,
    location,
    metadata
)
VALUES
(
    'Lucknow Office',
    'office',
    ST_SetSRID(ST_Point(80.9462, 26.8467), 4326)::geography,
    '{"capacity": 120, "region": "UP"}'
),
(
    'Kanpur Depot',
    'depot',
    ST_SetSRID(ST_Point(80.3319, 26.4499), 4326)::geography,
    '{"capacity": 80, "region": "UP"}'
),
(
    'Prayagraj Depot',
    'depot',
    ST_SetSRID(ST_Point(81.8463, 25.4358), 4326)::geography,
    '{"capacity": 65, "region": "UP"}'
),
(
    'Ayodhya Sensor',
    'sensor',
    ST_SetSRID(ST_Point(82.1998, 26.7997), 4326)::geography,
    '{"telemetry": true}'
);

INSERT INTO spatial_zone (zone_name, boundary)
VALUES (
    'Central Service Zone',
    ST_SetSRID(
        ST_GeomFromText(
            'POLYGON((
                80.70 26.65,
                81.20 26.65,
                81.20 27.00,
                80.70 27.00,
                80.70 26.65
            ))'
        ),
        4326
    )::geography
);

-- Extension metadata and installed-version inspection.
SELECT
    extname AS extension_name,
    extversion AS installed_version
FROM pg_extension
ORDER BY extname;

-- PostGIS-specific capability inspection.
SELECT
    PostGIS_Version() AS postgis_version,
    PostGIS_Lib_Version() AS postgis_library_version;

-- Retrieve spatial facilities as human-readable WKT.
SELECT
    facility_name,
    facility_type,
    ST_AsText(location::geometry) AS wkt
FROM spatial_facility
ORDER BY facility_name;

-- Nearest-neighbour style query. The spatial index can assist the
-- bounding-box ordering operator; ST_Distance then provides exact distance.
SELECT
    facility_name,
    ROUND(
        ST_Distance(
            location,
            ST_SetSRID(ST_Point(80.9462, 26.8467), 4326)::geography
        )::numeric,
        2
    ) AS distance_meters
FROM spatial_facility
WHERE facility_type = 'depot'
ORDER BY
    location <-> ST_SetSRID(
        ST_Point(80.9462, 26.8467),
        4326
    )::geography
LIMIT 3;

-- Containment query using a database-side spatial predicate.
SELECT
    f.facility_name,
    z.zone_name,
    ST_Covers(z.boundary, f.location) AS inside_zone
FROM spatial_facility f
CROSS JOIN spatial_zone z
ORDER BY f.facility_name;

-- Spatial aggregation.
SELECT
    facility_type,
    COUNT(*) AS facility_count,
    jsonb_agg(metadata ORDER BY facility_name) AS metadata_samples
FROM spatial_facility
GROUP BY facility_type
ORDER BY facility_type;

-- Geometry validation and SRID inspection.
SELECT
    facility_name,
    ST_SRID(location::geometry) AS srid,
    ST_GeometryType(location::geometry) AS geometry_type,
    ST_IsValid(location::geometry) AS valid_geometry
FROM spatial_facility;

-- Polygon area in square metres. Geography uses geodetic calculations.
SELECT
    zone_name,
    ROUND(ST_Area(boundary)::numeric, 2) AS area_square_metres
FROM spatial_zone;

-- Determine whether all required status checks passed for each PR.
WITH required_checks AS (
    SELECT
        pull_request_id,
        COUNT(*) FILTER (WHERE status = 'passed') AS passed_checks,
        COUNT(*) AS total_checks
    FROM status_check
    GROUP BY pull_request_id
)
SELECT
    pr.pull_request_id,
    pr.title,
    COALESCE(rc.passed_checks, 0) AS passed_checks,
    COALESCE(rc.total_checks, 0) AS total_checks,
    COALESCE(rc.passed_checks, 0) = COALESCE(rc.total_checks, 0)
        AND COALESCE(rc.total_checks, 0) > 0 AS checks_satisfied
FROM pull_request pr
LEFT JOIN required_checks rc
    ON rc.pull_request_id = pr.pull_request_id;

-- Approval eligibility considers reviewer activity, approval state,
-- head-commit freshness, and reviewer-group requirements.
WITH current_approvals AS (
    SELECT
        r.pull_request_id,
        r.reviewer_id,
        r.commit_id,
        r.submitted_at,
        r.review_state,
        rpm.reviewer_group
    FROM review r
    JOIN reviewer rv
        ON rv.reviewer_id = r.reviewer_id
       AND rv.active
    JOIN reviewer_group_member rpm
        ON rpm.reviewer_id = r.reviewer_id
    WHERE r.review_state = 'approved'
),
approval_counts AS (
    SELECT
        ca.pull_request_id,
        ca.reviewer_group,
        COUNT(DISTINCT ca.reviewer_id) AS approved_reviewers
    FROM current_approvals ca
    JOIN pull_request pr
        ON pr.pull_request_id = ca.pull_request_id
       AND ca.commit_id = pr.head_commit_id
    GROUP BY ca.pull_request_id, ca.reviewer_group
)
SELECT
    pr.pull_request_id,
    pr.title,
    apr.required_reviewer_group,
    apr.required_count,
    COALESCE(ac.approved_reviewers, 0) AS approved_count,
    COALESCE(ac.approved_reviewers, 0) >= apr.required_count
        AS requirement_satisfied
FROM pull_request pr
JOIN branch_protection_policy bpp
    ON bpp.branch_id = pr.target_branch_id
JOIN approval_requirement apr
    ON apr.policy_id = bpp.policy_id
LEFT JOIN approval_counts ac
    ON ac.pull_request_id = pr.pull_request_id
   AND ac.reviewer_group = apr.required_reviewer_group
ORDER BY pr.pull_request_id, apr.required_reviewer_group;

-- Full merge-eligibility report.
WITH check_state AS (
    SELECT
        pull_request_id,
        bool_and(status = 'passed') AS checks_passed,
        COUNT(*) > 0 AS has_checks
    FROM status_check
    GROUP BY pull_request_id
),
conversation_state AS (
    SELECT
        pull_request_id,
        bool_and(resolved) AS conversations_resolved
    FROM conversation
    GROUP BY pull_request_id
),
approval_state AS (
    SELECT
        pr.pull_request_id,
        bool_and(
            COALESCE(approval_counts.approved_reviewers, 0)
            >= apr.required_count
        ) AS approvals_satisfied
    FROM pull_request pr
    JOIN branch_protection_policy bpp
        ON bpp.branch_id = pr.target_branch_id
    JOIN approval_requirement apr
        ON apr.policy_id = bpp.policy_id
    LEFT JOIN (
        SELECT
            r.pull_request_id,
            rpm.reviewer_group,
            COUNT(DISTINCT r.reviewer_id) AS approved_reviewers
        FROM review r
        JOIN reviewer rv
            ON rv.reviewer_id = r.reviewer_id
           AND rv.active
        JOIN reviewer_group_member rpm
            ON rpm.reviewer_id = r.reviewer_id
        JOIN pull_request pr2
            ON pr2.pull_request_id = r.pull_request_id
           AND r.commit_id = pr2.head_commit_id
        WHERE r.review_state = 'approved'
        GROUP BY r.pull_request_id, rpm.reviewer_group
    ) approval_counts
        ON approval_counts.pull_request_id = pr.pull_request_id
       AND approval_counts.reviewer_group = apr.required_reviewer_group
    GROUP BY pr.pull_request_id
)
SELECT
    pr.pull_request_id,
    pr.title,
    pr.state,
    pr.target_branch_id,
    COALESCE(cs.has_checks AND cs.checks_passed, false)
        AS checks_satisfied,
    COALESCE(cvs.conversations_resolved, true)
        AS conversations_satisfied,
    COALESCE(aps.approvals_satisfied, false)
        AS approvals_satisfied,
    (
        pr.state = 'open'
        AND COALESCE(cs.has_checks AND cs.checks_passed, false)
        AND COALESCE(cvs.conversations_resolved, true)
        AND COALESCE(aps.approvals_satisfied, false)
        AND bpp.prohibit_direct_push
    ) AS merge_eligible
FROM pull_request pr
JOIN branch_protection_policy bpp
    ON bpp.branch_id = pr.target_branch_id
LEFT JOIN check_state cs
    ON cs.pull_request_id = pr.pull_request_id
LEFT JOIN conversation_state cvs
    ON cvs.pull_request_id = pr.pull_request_id
LEFT JOIN approval_state aps
    ON aps.pull_request_id = pr.pull_request_id;

-- Transactional example: a merge must update the PR state and timestamp
-- atomically. The eligibility report should be checked before this action.
BEGIN;

UPDATE pull_request
SET
    state = 'merged',
    merged_at = now()
WHERE pull_request_id = 1
  AND state = 'open';

COMMIT;

-- PostGIS function examples useful in production spatial workflows.
SELECT
    ST_Distance(
        ST_SetSRID(ST_Point(80.9462, 26.8467), 4326)::geography,
        ST_SetSRID(ST_Point(80.3319, 26.4499), 4326)::geography
    ) AS distance_meters;

SELECT
    ST_AsText(
        ST_Centroid(boundary::geometry)
    ) AS zone_centroid
FROM spatial_zone;

-- Extension inventory from PostgreSQL's authoritative catalog.
SELECT
    e.extname,
    e.extversion,
    n.nspname AS installed_schema
FROM pg_extension e
JOIN pg_namespace n
    ON n.oid = e.extnamespace
ORDER BY e.extname;
