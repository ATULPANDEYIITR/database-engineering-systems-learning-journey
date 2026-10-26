DROP SCHEMA IF EXISTS postgres_arrays CASCADE;
CREATE SCHEMA postgres_arrays;

SET search_path = postgres_arrays, public;

-- PostgreSQL arrays are useful when a small, ordered collection belongs
-- directly to one row and does not need independent foreign-key identity.

CREATE TYPE review_state AS ENUM (
    'pending',
    'approved',
    'changes_requested',
    'dismissed'
);

CREATE TYPE check_state AS ENUM (
    'pending',
    'passed',
    'failed'
);

CREATE TABLE repository (
    repository_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    repository_name text NOT NULL UNIQUE,
    default_branch text NOT NULL DEFAULT 'main',
    allowed_labels text[] NOT NULL DEFAULT '{}',
    CONSTRAINT repository_name_not_blank
        CHECK (btrim(repository_name) <> ''),
    CONSTRAINT repository_default_branch_not_blank
        CHECK (btrim(default_branch) <> '')
);

CREATE TABLE branch (
    branch_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    repository_id bigint NOT NULL REFERENCES repository(repository_id)
        ON DELETE CASCADE,
    branch_name text NOT NULL,
    protected boolean NOT NULL DEFAULT false,
    required_checks text[] NOT NULL DEFAULT '{}',
    CONSTRAINT branch_name_not_blank
        CHECK (btrim(branch_name) <> ''),
    CONSTRAINT branch_unique_name
        UNIQUE (repository_id, branch_name)
);

CREATE TABLE commit_record (
    commit_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    repository_id bigint NOT NULL REFERENCES repository(repository_id)
        ON DELETE CASCADE,
    branch_id bigint NOT NULL REFERENCES branch(branch_id)
        ON DELETE CASCADE,
    commit_hash text NOT NULL UNIQUE,
    message text NOT NULL,
    changed_files text[] NOT NULL DEFAULT '{}',
    CONSTRAINT commit_hash_not_blank
        CHECK (btrim(commit_hash) <> ''),
    CONSTRAINT commit_message_not_blank
        CHECK (btrim(message) <> '')
);

CREATE TABLE pull_request (
    pull_request_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    repository_id bigint NOT NULL REFERENCES repository(repository_id)
        ON DELETE CASCADE,
    source_branch_id bigint NOT NULL REFERENCES branch(branch_id),
    target_branch_id bigint NOT NULL REFERENCES branch(branch_id),
    title text NOT NULL,
    labels text[] NOT NULL DEFAULT '{}',
    commit_ids bigint[] NOT NULL DEFAULT '{}',
    is_draft boolean NOT NULL DEFAULT true,
    is_closed boolean NOT NULL DEFAULT false,
    merged_at timestamptz,
    CONSTRAINT pull_request_title_not_blank
        CHECK (btrim(title) <> ''),
    CONSTRAINT pull_request_distinct_branches
        CHECK (source_branch_id <> target_branch_id)
);

CREATE TABLE reviewer (
    reviewer_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    reviewer_name text NOT NULL UNIQUE,
    active boolean NOT NULL DEFAULT true,
    roles text[] NOT NULL DEFAULT '{}',
    CONSTRAINT reviewer_name_not_blank
        CHECK (btrim(reviewer_name) <> '')
);

CREATE TABLE review (
    review_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    pull_request_id bigint NOT NULL REFERENCES pull_request(pull_request_id)
        ON DELETE CASCADE,
    reviewer_id bigint NOT NULL REFERENCES reviewer(reviewer_id),
    state review_state NOT NULL,
    submitted_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    stale boolean NOT NULL DEFAULT false,
    dismissed boolean NOT NULL DEFAULT false,
    CONSTRAINT review_reviewer_unique
        UNIQUE (pull_request_id, reviewer_id, submitted_at)
);

CREATE TABLE review_comment (
    comment_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    review_id bigint NOT NULL REFERENCES review(review_id)
        ON DELETE CASCADE,
    file_path text,
    line_number integer,
    body text NOT NULL,
    resolved boolean NOT NULL DEFAULT false,
    CONSTRAINT review_comment_body_not_blank
        CHECK (btrim(body) <> ''),
    CONSTRAINT review_comment_line_valid
        CHECK (line_number IS NULL OR line_number > 0)
);

CREATE TABLE status_check (
    status_check_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    pull_request_id bigint NOT NULL REFERENCES pull_request(pull_request_id)
        ON DELETE CASCADE,
    check_name text NOT NULL,
    state check_state NOT NULL,
    completed_at timestamptz,
    CONSTRAINT status_check_name_not_blank
        CHECK (btrim(check_name) <> ''),
    CONSTRAINT status_check_unique
        UNIQUE (pull_request_id, check_name)
);

CREATE TABLE branch_protection_policy (
    policy_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    branch_id bigint NOT NULL UNIQUE REFERENCES branch(branch_id)
        ON DELETE CASCADE,
    required_review_count integer NOT NULL DEFAULT 1,
    require_conversation_resolution boolean NOT NULL DEFAULT true,
    require_linear_history boolean NOT NULL DEFAULT false,
    allow_direct_push boolean NOT NULL DEFAULT false,
    allow_force_push boolean NOT NULL DEFAULT false,
    allow_branch_deletion boolean NOT NULL DEFAULT false,
    required_status_checks text[] NOT NULL DEFAULT '{}',
    CONSTRAINT review_count_nonnegative
        CHECK (required_review_count >= 0)
);

CREATE INDEX idx_pull_request_target
    ON pull_request(target_branch_id);

CREATE INDEX idx_review_pull_request_state
    ON review(pull_request_id, state);

CREATE INDEX idx_status_check_pull_request_state
    ON status_check(pull_request_id, state);

CREATE INDEX idx_pull_request_labels_gin
    ON pull_request USING gin(labels);

CREATE INDEX idx_branch_required_checks_gin
    ON branch USING gin(required_checks);

CREATE INDEX idx_commit_changed_files_gin
    ON commit_record USING gin(changed_files);

CREATE OR REPLACE FUNCTION normalize_text_array(input text[])
RETURNS text[]
LANGUAGE sql
IMMUTABLE
AS $$
    SELECT COALESCE(
        array_agg(DISTINCT lower(btrim(value)) ORDER BY lower(btrim(value))),
        '{}'::text[]
    )
    FROM unnest(COALESCE(input, '{}'::text[])) AS value
    WHERE btrim(value) <> '';
$$;

CREATE OR REPLACE FUNCTION normalize_pull_request_arrays()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.labels := normalize_text_array(NEW.labels);
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_normalize_pull_request_arrays
BEFORE INSERT OR UPDATE OF labels
ON pull_request
FOR EACH ROW
EXECUTE FUNCTION normalize_pull_request_arrays();

CREATE OR REPLACE FUNCTION validate_commit_ids()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    invalid_count integer;
BEGIN
    SELECT count(*)
    INTO invalid_count
    FROM unnest(COALESCE(NEW.commit_ids, '{}'::bigint[])) AS requested(commit_id)
    LEFT JOIN commit_record c
        ON c.commit_id = requested.commit_id
       AND c.repository_id = NEW.repository_id
    WHERE c.commit_id IS NULL;

    IF invalid_count > 0 THEN
        RAISE EXCEPTION
            'pull request % references commits outside its repository',
            NEW.pull_request_id;
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_validate_commit_ids
BEFORE INSERT OR UPDATE OF repository_id, commit_ids
ON pull_request
FOR EACH ROW
EXECUTE FUNCTION validate_commit_ids();

INSERT INTO repository (
    repository_name,
    default_branch,
    allowed_labels
)
VALUES
(
    'payment-platform',
    'main',
    ARRAY['database', 'security', 'postgresql', 'backend']
),
(
    'analytics-platform',
    'main',
    ARRAY['sql', 'reporting', 'data']
);

INSERT INTO branch (
    repository_id,
    branch_name,
    protected,
    required_checks
)
SELECT
    repository_id,
    branch_name,
    protected,
    required_checks
FROM (
    SELECT
        r.repository_id,
        'main'::text AS branch_name,
        true AS protected,
        ARRAY['unit-tests', 'security-scan']::text[] AS required_checks
    FROM repository r
    WHERE r.repository_name = 'payment-platform'

    UNION ALL

    SELECT
        r.repository_id,
        'feature/array-operations',
        false,
        '{}'::text[]
    FROM repository r
    WHERE r.repository_name = 'payment-platform'

    UNION ALL

    SELECT
        r.repository_id,
        'main',
        true,
        ARRAY['tests']::text[]
    FROM repository r
    WHERE r.repository_name = 'analytics-platform'
) AS seed;

INSERT INTO branch_protection_policy (
    branch_id,
    required_review_count,
    require_conversation_resolution,
    require_linear_history,
    allow_direct_push,
    allow_force_push,
    allow_branch_deletion,
    required_status_checks
)
SELECT
    b.branch_id,
    CASE WHEN b.branch_name = 'main' THEN 2 ELSE 0 END,
    true,
    false,
    false,
    false,
    false,
    b.required_checks
FROM branch b;

INSERT INTO reviewer (
    reviewer_name,
    active,
    roles
)
VALUES
('Asha', true, ARRAY['maintainer', 'database']),
('Rahul', true, ARRAY['reviewer', 'security']),
('Inactive Reviewer', false, ARRAY['reviewer']);

INSERT INTO commit_record (
    repository_id,
    branch_id,
    commit_hash,
    message,
    changed_files
)
SELECT
    r.repository_id,
    b.branch_id,
    'abc1001',
    'Add PostgreSQL array operations',
    ARRAY[
        'sql/arrays.sql',
        'tests/arrays.sql'
    ]
FROM repository r
JOIN branch b
    ON b.repository_id = r.repository_id
   AND b.branch_name = 'feature/array-operations'
WHERE r.repository_name = 'payment-platform';

INSERT INTO commit_record (
    repository_id,
    branch_id,
    commit_hash,
    message,
    changed_files
)
SELECT
    r.repository_id,
    b.branch_id,
    'abc1002',
    'Add array validation trigger',
    ARRAY[
        'sql/arrays.sql',
        'sql/triggers.sql'
    ]
FROM repository r
JOIN branch b
    ON b.repository_id = r.repository_id
   AND b.branch_name = 'feature/array-operations'
WHERE r.repository_name = 'payment-platform';

INSERT INTO pull_request (
    repository_id,
    source_branch_id,
    target_branch_id,
    title,
    labels,
    commit_ids,
    is_draft,
    is_closed
)
SELECT
    r.repository_id,
    source_branch.branch_id,
    target_branch.branch_id,
    'Add array-based repository metadata',
    ARRAY[
        'PostgreSQL',
        'database',
        'security',
        'database'
    ],
    ARRAY[c1.commit_id, c2.commit_id],
    false,
    false
FROM repository r
JOIN branch source_branch
    ON source_branch.repository_id = r.repository_id
   AND source_branch.branch_name = 'feature/array-operations'
JOIN branch target_branch
    ON target_branch.repository_id = r.repository_id
   AND target_branch.branch_name = 'main'
JOIN commit_record c1
    ON c1.commit_hash = 'abc1001'
JOIN commit_record c2
    ON c2.commit_hash = 'abc1002'
WHERE r.repository_name = 'payment-platform';

INSERT INTO review (
    pull_request_id,
    reviewer_id,
    state,
    stale,
    dismissed
)
SELECT
    pr.pull_request_id,
    rv.reviewer_id,
    'approved',
    false,
    false
FROM pull_request pr
JOIN reviewer rv
    ON rv.reviewer_name = 'Asha'
WHERE pr.title = 'Add array-based repository metadata';

INSERT INTO review (
    pull_request_id,
    reviewer_id,
    state,
    stale,
    dismissed
)
SELECT
    pr.pull_request_id,
    rv.reviewer_id,
    'approved',
    false,
    false
FROM pull_request pr
JOIN reviewer rv
    ON rv.reviewer_name = 'Rahul'
WHERE pr.title = 'Add array-based repository metadata';

INSERT INTO review_comment (
    review_id,
    file_path,
    line_number,
    body,
    resolved
)
SELECT
    review_id,
    'sql/arrays.sql',
    1,
    'Array normalization is enforced before persistence.',
    true
FROM review
ORDER BY review_id
LIMIT 1;

INSERT INTO status_check (
    pull_request_id,
    check_name,
    state,
    completed_at
)
SELECT
    pr.pull_request_id,
    checks.check_name,
    'passed',
    clock_timestamp()
FROM pull_request pr
CROSS JOIN (
    VALUES
        ('unit-tests'),
        ('security-scan')
) AS checks(check_name)
WHERE pr.title = 'Add array-based repository metadata';

-- Array containment uses @>, while overlap uses &&.
SELECT
    pull_request_id,
    title,
    labels
FROM pull_request
WHERE labels @> ARRAY['security', 'database']::text[];

SELECT
    pull_request_id,
    title,
    labels
FROM pull_request
WHERE labels && ARRAY['security', 'compliance']::text[];

-- Cardinality returns the number of elements and differs from array_length
-- when dealing with empty arrays.
SELECT
    repository_name,
    allowed_labels,
    cardinality(allowed_labels) AS label_count
FROM repository;

-- Unnest converts array elements into rows and exposes practical reporting.
SELECT
    pr.pull_request_id,
    pr.title,
    element.position,
    element.label
FROM pull_request pr
CROSS JOIN LATERAL unnest(pr.labels)
    WITH ORDINALITY AS element(label, position)
ORDER BY pr.pull_request_id, element.position;

-- Array positions are 1-based.
SELECT
    pull_request_id,
    array_position(labels, 'security') AS security_position
FROM pull_request;

-- Concatenation creates a new array.
SELECT
    pull_request_id,
    labels || ARRAY['production']::text[] AS enriched_labels
FROM pull_request;

-- Remove matching elements without changing the stored row.
SELECT
    pull_request_id,
    array_remove(labels, 'database') AS labels_without_database
FROM pull_request;

-- Aggregate relational values into an array.
SELECT
    repository_id,
    array_agg(branch_name ORDER BY branch_name) AS branches
FROM branch
GROUP BY repository_id;

-- Evaluate merge eligibility from branch protection, approvals,
-- unresolved conversations, required checks, and draft/closed state.
WITH protection AS (
    SELECT
        bp.branch_id,
        bp.required_review_count,
        bp.require_conversation_resolution,
        bp.required_status_checks
    FROM branch_protection_policy bp
),
review_counts AS (
    SELECT
        pr.pull_request_id,
        count(*) FILTER (
            WHERE r.state = 'approved'
              AND NOT r.stale
              AND NOT r.dismissed
              AND rv.active
        ) AS valid_approvals
    FROM pull_request pr
    LEFT JOIN review r
        ON r.pull_request_id = pr.pull_request_id
    LEFT JOIN reviewer rv
        ON rv.reviewer_id = r.reviewer_id
    GROUP BY pr.pull_request_id
),
check_results AS (
    SELECT
        pr.pull_request_id,
        bool_and(sc.state = 'passed') AS all_checks_passed,
        array_agg(sc.check_name ORDER BY sc.check_name)
            FILTER (WHERE sc.state <> 'passed') AS failed_or_pending_checks
    FROM pull_request pr
    LEFT JOIN status_check sc
        ON sc.pull_request_id = pr.pull_request_id
    GROUP BY pr.pull_request_id
),
unresolved AS (
    SELECT
        pr.pull_request_id,
        count(rc.comment_id) FILTER (
            WHERE NOT rc.resolved
        ) AS unresolved_comments
    FROM pull_request pr
    LEFT JOIN review r
        ON r.pull_request_id = pr.pull_request_id
    LEFT JOIN review_comment rc
        ON rc.review_id = r.review_id
    GROUP BY pr.pull_request_id
)
SELECT
    pr.pull_request_id,
    pr.title,
    protection.required_review_count,
    review_counts.valid_approvals,
    check_results.all_checks_passed,
    unresolved.unresolved_comments,
    (
        NOT pr.is_draft
        AND NOT pr.is_closed
        AND review_counts.valid_approvals >= protection.required_review_count
        AND check_results.all_checks_passed
        AND (
            NOT protection.require_conversation_resolution
            OR unresolved.unresolved_comments = 0
        )
    ) AS merge_eligible
FROM pull_request pr
JOIN protection
    ON protection.branch_id = pr.target_branch_id
JOIN review_counts
    ON review_counts.pull_request_id = pr.pull_request_id
JOIN check_results
    ON check_results.pull_request_id = pr.pull_request_id
JOIN unresolved
    ON unresolved.pull_request_id = pr.pull_request_id;

-- Transactional example: add a label only when the pull request exists
-- and remains open. The row lock prevents a concurrent workflow from
-- changing the state between validation and update.
BEGIN;

SELECT pull_request_id
FROM pull_request
WHERE pull_request_id = 1
  AND NOT is_closed
FOR UPDATE;

UPDATE pull_request
SET labels = array_append(labels, 'release-reviewed')
WHERE pull_request_id = 1
  AND NOT is_closed
  AND NOT ('release-reviewed' = ANY(labels));

COMMIT;

-- Array indexing can help when the indexed element has a stable meaning.
-- For general membership searches, the GIN index on labels is preferable.
SELECT
    pull_request_id,
    labels[1] AS primary_label
FROM pull_request;

-- Validate arrays for forbidden values at query time.
SELECT
    pull_request_id,
    labels
FROM pull_request
WHERE EXISTS (
    SELECT 1
    FROM unnest(labels) AS label
    WHERE label IN ('secret', 'password', 'private-key')
);

-- Practical distinction:
-- ARRAY is appropriate for compact row-owned collections.
-- A separate relation is preferable when elements require their own
-- identity, foreign keys, frequent independent updates, or rich metadata.
