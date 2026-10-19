-- PostgreSQL Index Access Methods
-- B-tree, Hash, GIN, GiST, and BRIN
--
-- This script is PostgreSQL-specific.
-- It builds a realistic repository-analytics schema and demonstrates why
-- different predicates require different index access methods.
--
-- GiST uses PostgreSQL's built-in range types, so PostGIS is not required.
-- GIN demonstrates both array containment and JSONB containment.
-- BRIN demonstrates timestamp range filtering on a table whose insertion
-- order follows created_at.

DROP SCHEMA IF EXISTS postgres_index_lab CASCADE;
CREATE SCHEMA postgres_index_lab;
SET search_path TO postgres_index_lab, public;

CREATE TABLE repositories (
    repository_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    repository_name TEXT NOT NULL UNIQUE,
    owner_team TEXT NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE pull_requests (
    pull_request_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    repository_id BIGINT NOT NULL
        REFERENCES repositories(repository_id),
    author_name TEXT NOT NULL,
    state TEXT NOT NULL
        CHECK (state IN ('draft', 'open', 'merged', 'closed')),
    title TEXT NOT NULL,
    labels TEXT[] NOT NULL DEFAULT '{}',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL,
    merged_at TIMESTAMPTZ,
    lifecycle TSTZRANGE GENERATED ALWAYS AS (
        tstzrange(
            created_at,
            COALESCE(merged_at, 'infinity'::timestamptz),
            '[)'
        )
    ) STORED,
    CHECK (
        merged_at IS NULL
        OR merged_at >= created_at
    )
);

CREATE TABLE repository_events (
    event_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    repository_id BIGINT NOT NULL
        REFERENCES repositories(repository_id),
    event_type TEXT NOT NULL,
    event_time TIMESTAMPTZ NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb
);

INSERT INTO repositories (repository_name, owner_team)
VALUES
    ('platform-api', 'Platform'),
    ('data-services', 'Data'),
    ('security-core', 'Security');

-- Pull requests are inserted in chronological order so the BRIN index on
-- created_at can benefit from physical correlation in this demonstration.
INSERT INTO pull_requests
    (repository_id, author_name, state, title, labels, metadata, created_at, merged_at)
VALUES
    (1, 'anika', 'merged',
     'Add PostgreSQL query audit',
     ARRAY['postgresql', 'database'],
     '{"risk":"medium","component":"storage"}',
     '2026-01-05 09:00+05:30',
     '2026-01-07 14:00+05:30'),

    (1, 'rahul', 'open',
     'Harden authentication policy',
     ARRAY['security', 'backend'],
     '{"risk":"high","component":"authentication"}',
     '2026-01-12 10:00+05:30',
     NULL),

    (2, 'meera', 'open',
     'Optimize GIN search',
     ARRAY['postgresql', 'performance', 'gin'],
     '{"risk":"medium","component":"search"}',
     '2026-01-20 11:00+05:30',
     NULL),

    (2, 'vikas', 'closed',
     'Remove obsolete API',
     ARRAY['maintenance'],
     '{"risk":"low","component":"api"}',
     '2026-01-28 12:00+05:30',
     '2026-01-30 09:00+05:30'),

    (3, 'anika', 'merged',
     'Add audit event storage',
     ARRAY['security', 'database'],
     '{"risk":"high","component":"audit"}',
     '2026-02-05 09:30+05:30',
     '2026-02-09 16:00+05:30'),

    (3, 'rahul', 'open',
     'Index release metadata',
     ARRAY['postgresql', 'release'],
     '{"risk":"medium","component":"release"}',
     '2026-02-14 13:00+05:30',
     NULL),

    (1, 'meera', 'merged',
     'Improve repository metrics',
     ARRAY['analytics', 'performance'],
     '{"risk":"medium","component":"metrics"}',
     '2026-02-21 15:00+05:30',
     '2026-02-24 10:00+05:30'),

    (2, 'vikas', 'open',
     'Protect sensitive columns',
     ARRAY['security', 'postgresql'],
     '{"risk":"critical","component":"database"}',
     '2026-03-02 08:30+05:30',
     NULL),

    (3, 'anika', 'merged',
     'Tune historical queries',
     ARRAY['performance', 'postgresql'],
     '{"risk":"medium","component":"reporting"}',
     '2026-03-09 10:00+05:30',
     '2026-03-12 17:00+05:30'),

    (1, 'rahul', 'open',
     'Document backup verification',
     ARRAY['operations'],
     '{"risk":"low","component":"backup"}',
     '2026-03-17 11:30+05:30',
     NULL),

    (2, 'meera', 'merged',
     'Add range-based reporting',
     ARRAY['postgresql', 'analytics'],
     '{"risk":"medium","component":"reporting"}',
     '2026-03-24 14:00+05:30',
     '2026-03-27 12:00+05:30'),

    (3, 'vikas', 'open',
     'Review security telemetry',
     ARRAY['security', 'analytics'],
     '{"risk":"critical","component":"telemetry"}',
     '2026-04-02 09:00+05:30',
     NULL);

INSERT INTO repository_events
    (repository_id, event_type, event_time, payload)
VALUES
    (1, 'deployment', '2026-01-08 10:00+05:30',
     '{"environment":"production","status":"success"}'),
    (2, 'incident', '2026-02-06 15:00+05:30',
     '{"severity":"high","service":"search"}'),
    (3, 'security_review', '2026-03-03 12:00+05:30',
     '{"severity":"critical","finding_count":3}'),
    (2, 'deployment', '2026-03-25 16:00+05:30',
     '{"environment":"staging","status":"success"}');

-- B-tree:
-- General-purpose structure for equality, ordering, and range predicates.
CREATE INDEX idx_pr_state_btree
    ON pull_requests USING btree (state);

CREATE INDEX idx_pr_created_btree
    ON pull_requests USING btree (created_at);

CREATE INDEX idx_pr_repository_created_btree
    ON pull_requests USING btree (repository_id, created_at);

-- Hash:
-- Equality-focused access method. It does not provide B-tree ordering.
CREATE INDEX idx_pr_repository_hash
    ON pull_requests USING hash (repository_id);

-- GIN:
-- Array containment uses the array operator class.
-- JSONB containment uses the jsonb_ops default operator class.
CREATE INDEX idx_pr_labels_gin
    ON pull_requests USING gin (labels);

CREATE INDEX idx_pr_metadata_gin
    ON pull_requests USING gin (metadata);

-- GiST:
-- PostgreSQL range types expose overlap (&&), containment, adjacency, and
-- other range operators that can be indexed through GiST.
CREATE INDEX idx_pr_lifecycle_gist
    ON pull_requests USING gist (lifecycle);

-- BRIN:
-- BRIN stores summaries for ranges of heap pages rather than one entry
-- for every tuple. It is useful when created_at is correlated with the
-- physical insertion order.
CREATE INDEX idx_pr_created_brin
    ON pull_requests USING brin (
        created_at
    )
    WITH (pages_per_range = 4);

ANALYZE repositories;
ANALYZE pull_requests;
ANALYZE repository_events;

-- B-tree equality.
EXPLAIN (ANALYZE, BUFFERS)
SELECT pull_request_id, title, state
FROM pull_requests
WHERE state = 'open';

-- B-tree range and ordering.
EXPLAIN (ANALYZE, BUFFERS)
SELECT pull_request_id, title, created_at
FROM pull_requests
WHERE created_at >= '2026-02-01 00:00+05:30'
  AND created_at <  '2026-03-01 00:00+05:30'
ORDER BY created_at DESC;

-- Hash equality.
-- The planner may choose the B-tree or a sequential scan depending on
-- statistics and cost, so the existence of a hash index does not force
-- its use.
EXPLAIN (ANALYZE, BUFFERS)
SELECT pull_request_id, title
FROM pull_requests
WHERE repository_id = 2;

-- GIN array containment.
SELECT pull_request_id, title, labels
FROM pull_requests
WHERE labels @> ARRAY['security', 'postgresql']
ORDER BY pull_request_id;

-- GIN array overlap.
SELECT pull_request_id, title, labels
FROM pull_requests
WHERE labels && ARRAY['security', 'performance']
ORDER BY pull_request_id;

-- GIN JSONB containment.
SELECT pull_request_id, title, metadata
FROM pull_requests
WHERE metadata @> '{"risk":"critical"}'::jsonb
ORDER BY pull_request_id;

-- GiST range overlap.
-- The requested interval intersects a PR lifecycle range.
SELECT pull_request_id, title, lifecycle
FROM pull_requests
WHERE lifecycle && tstzrange(
    '2026-02-01 00:00+05:30',
    '2026-02-15 00:00+05:30',
    '[)'
)
ORDER BY pull_request_id;

-- GiST range containment.
SELECT pull_request_id, title, lifecycle
FROM pull_requests
WHERE lifecycle <@ tstzrange(
    '2026-02-01 00:00+05:30',
    '2026-03-01 00:00+05:30',
    '[)'
)
ORDER BY pull_request_id;

-- BRIN range query.
EXPLAIN (ANALYZE, BUFFERS)
SELECT pull_request_id, title, created_at
FROM pull_requests
WHERE created_at >= '2026-03-01 00:00+05:30'
  AND created_at <  '2026-04-01 00:00+05:30';

-- Compare the same predicate against the planner's complete index set.
-- The planner is allowed to reject an index when its cost estimate says
-- that another plan is cheaper.
EXPLAIN (ANALYZE, BUFFERS)
SELECT count(*)
FROM pull_requests
WHERE created_at >= '2026-03-01 00:00+05:30'
  AND created_at <  '2026-04-01 00:00+05:30';

-- Demonstrate that an index does not automatically make a low-selectivity
-- predicate cheap. Most rows are open in this small demonstration only if
-- the data distribution warrants it; the actual decision belongs to the
-- PostgreSQL planner.
EXPLAIN (ANALYZE, BUFFERS)
SELECT pull_request_id
FROM pull_requests
WHERE state IN ('open', 'merged', 'closed');

-- Query the catalog to inspect the actual index access methods.
SELECT
    indexrelid::regclass AS index_name,
    am.amname AS access_method,
    pg_size_pretty(pg_relation_size(indexrelid)) AS index_size
FROM pg_index
JOIN pg_class AS index_class
    ON index_class.oid = pg_index.indexrelid
JOIN pg_am AS am
    ON am.oid = index_class.relam
WHERE indrelid = 'pull_requests'::regclass
ORDER BY index_name;

-- Transactional demonstration:
-- Index definitions participate in PostgreSQL DDL and are visible to
-- concurrent transactions according to normal PostgreSQL transactional DDL
-- rules. The data operation below demonstrates ordinary integrity checks.
BEGIN;

INSERT INTO pull_requests
    (repository_id, author_name, state, title, labels, metadata, created_at)
VALUES
    (1, 'platform-admin', 'draft',
     'Validate index maintenance workflow',
     ARRAY['postgresql', 'maintenance'],
     '{"risk":"low","component":"database"}',
     '2026-04-10 09:00+05:30');

SAVEPOINT before_invalid_row;

-- This statement is intentionally invalid and would violate the lifecycle
-- CHECK if merged_at precedes created_at. It is rolled back to the savepoint.
INSERT INTO pull_requests
    (repository_id, author_name, state, title, labels, metadata, created_at, merged_at)
VALUES
    (1, 'platform-admin', 'merged',
     'Invalid temporal state',
     ARRAY['postgresql'],
     '{"risk":"high"}',
     '2026-04-11 12:00+05:30',
     '2026-04-10 12:00+05:30');

ROLLBACK TO SAVEPOINT before_invalid_row;
COMMIT;

-- The final query confirms the valid transactional row remains present.
SELECT pull_request_id, title, state, created_at
FROM pull_requests
WHERE title = 'Validate index maintenance workflow';

-- Practical design comparison:
SELECT
    'B-tree' AS method,
    'Equality, ordering, ranges' AS strongest_use,
    'General-purpose ordered tree' AS structural_property
UNION ALL
SELECT
    'Hash',
    'Equality',
    'Hash buckets'
UNION ALL
SELECT
    'GIN',
    'Array/JSONB containment',
    'Inverted posting structure'
UNION ALL
SELECT
    'GiST',
    'Range/operator-class searches',
    'Generalized search tree'
UNION ALL
SELECT
    'BRIN',
    'Large physically correlated tables',
    'Block-range summaries';
