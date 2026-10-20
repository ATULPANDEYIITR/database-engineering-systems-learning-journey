-- PostgreSQL Views, Materialized Views, and Use Cases
--
-- This script is self-contained and creates a dedicated schema so that it
-- does not modify unrelated application objects.
--
-- Normal views store query definitions and calculate results when queried.
-- Materialized views store the result physically and therefore require
-- REFRESH MATERIALIZED VIEW when source data changes.

DROP SCHEMA IF EXISTS view_learning CASCADE;
CREATE SCHEMA view_learning;
SET search_path TO view_learning, public;

CREATE TABLE repositories (
    repository_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    repository_name TEXT NOT NULL UNIQUE,
    owner_team TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (btrim(repository_name) <> ''),
    CHECK (btrim(owner_team) <> '')
);

CREATE TABLE branches (
    branch_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    repository_id BIGINT NOT NULL
        REFERENCES repositories(repository_id) ON DELETE CASCADE,
    branch_name TEXT NOT NULL,
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    is_protected BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE (repository_id, branch_name),
    CHECK (btrim(branch_name) <> '')
);

CREATE TABLE commits (
    commit_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    repository_id BIGINT NOT NULL
        REFERENCES repositories(repository_id) ON DELETE CASCADE,
    commit_sha CHAR(40) NOT NULL UNIQUE,
    author_name TEXT NOT NULL,
    committed_at TIMESTAMPTZ NOT NULL,
    message TEXT NOT NULL,
    CHECK (commit_sha ~ '^[0-9a-f]{40}$'),
    CHECK (btrim(author_name) <> ''),
    CHECK (btrim(message) <> '')
);

CREATE TABLE pull_requests (
    pull_request_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    repository_id BIGINT NOT NULL
        REFERENCES repositories(repository_id) ON DELETE CASCADE,
    number INTEGER NOT NULL,
    source_branch_id BIGINT NOT NULL
        REFERENCES branches(branch_id),
    target_branch_id BIGINT NOT NULL
        REFERENCES branches(branch_id),
    author_name TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'OPEN',
    additions INTEGER NOT NULL DEFAULT 0,
    deletions INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    merged_at TIMESTAMPTZ,
    UNIQUE (repository_id, number),
    CHECK (state IN ('DRAFT', 'OPEN', 'MERGED', 'CLOSED')),
    CHECK (additions >= 0),
    CHECK (deletions >= 0),
    CHECK (source_branch_id <> target_branch_id),
    CHECK (
        (state = 'MERGED' AND merged_at IS NOT NULL)
        OR
        (state <> 'MERGED' AND merged_at IS NULL)
    ),
    CHECK (btrim(author_name) <> '')
);

CREATE TABLE reviewers (
    reviewer_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    reviewer_name TEXT NOT NULL UNIQUE,
    team TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    CHECK (btrim(reviewer_name) <> ''),
    CHECK (btrim(team) <> '')
);

CREATE TABLE reviews (
    review_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    pull_request_id BIGINT NOT NULL
        REFERENCES pull_requests(pull_request_id) ON DELETE CASCADE,
    reviewer_id BIGINT NOT NULL
        REFERENCES reviewers(reviewer_id),
    state TEXT NOT NULL,
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    dismissed_at TIMESTAMPTZ,
    CHECK (
        state IN ('APPROVED', 'CHANGES_REQUESTED', 'COMMENTED')
    ),
    CHECK (
        dismissed_at IS NULL
        OR dismissed_at >= submitted_at
    )
);

CREATE TABLE review_comments (
    comment_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    pull_request_id BIGINT NOT NULL
        REFERENCES pull_requests(pull_request_id) ON DELETE CASCADE,
    reviewer_id BIGINT NOT NULL
        REFERENCES reviewers(reviewer_id),
    file_path TEXT NOT NULL,
    line_number INTEGER,
    comment_text TEXT NOT NULL,
    resolved_at TIMESTAMPTZ,
    CHECK (btrim(file_path) <> ''),
    CHECK (btrim(comment_text) <> ''),
    CHECK (line_number IS NULL OR line_number > 0)
);

CREATE TABLE status_checks (
    status_check_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    pull_request_id BIGINT NOT NULL
        REFERENCES pull_requests(pull_request_id) ON DELETE CASCADE,
    check_name TEXT NOT NULL,
    status TEXT NOT NULL,
    completed_at TIMESTAMPTZ,
    UNIQUE (pull_request_id, check_name),
    CHECK (status IN ('PENDING', 'PASS', 'FAIL')),
    CHECK (
        status = 'PENDING'
        OR completed_at IS NOT NULL
    ),
    CHECK (btrim(check_name) <> '')
);

CREATE TABLE branch_protection_policies (
    policy_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    branch_id BIGINT NOT NULL UNIQUE
        REFERENCES branches(branch_id) ON DELETE CASCADE,
    required_reviews INTEGER NOT NULL DEFAULT 0,
    require_status_checks BOOLEAN NOT NULL DEFAULT FALSE,
    require_conversation_resolution BOOLEAN NOT NULL DEFAULT FALSE,
    allow_force_push BOOLEAN NOT NULL DEFAULT FALSE,
    allow_direct_push BOOLEAN NOT NULL DEFAULT FALSE,
    require_linear_history BOOLEAN NOT NULL DEFAULT FALSE,
    allow_admin_bypass BOOLEAN NOT NULL DEFAULT FALSE,
    CHECK (required_reviews >= 0)
);

CREATE INDEX idx_pull_requests_repository_state
    ON pull_requests(repository_id, state);

CREATE INDEX idx_reviews_pull_request_state
    ON reviews(pull_request_id, state);

CREATE INDEX idx_status_checks_pull_request_status
    ON status_checks(pull_request_id, status);

CREATE INDEX idx_review_comments_pull_request_resolution
    ON review_comments(pull_request_id, resolved_at);

INSERT INTO repositories
    (repository_name, owner_team)
VALUES
    ('payments-api', 'platform'),
    ('customer-portal', 'web'),
    ('analytics-service', 'data');

INSERT INTO branches
    (repository_id, branch_name, is_default, is_protected)
SELECT repository_id, 'main', TRUE, TRUE
FROM repositories;

INSERT INTO branches
    (repository_id, branch_name)
SELECT repository_id, 'feature/payments-tax'
FROM repositories
WHERE repository_name = 'payments-api';

INSERT INTO branches
    (repository_id, branch_name)
SELECT repository_id, 'feature/customer-export'
FROM repositories
WHERE repository_name = 'customer-portal';

INSERT INTO branches
    (repository_id, branch_name)
SELECT repository_id, 'feature/warehouse'
FROM repositories
WHERE repository_name = 'analytics-service';

INSERT INTO commits
    (repository_id, commit_sha, author_name, committed_at, message)
SELECT
    repository_id,
    'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
    'alice',
    CURRENT_TIMESTAMP - INTERVAL '4 days',
    'Add tax calculation'
FROM repositories
WHERE repository_name = 'payments-api';

INSERT INTO commits
    (repository_id, commit_sha, author_name, committed_at, message)
SELECT
    repository_id,
    'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
    'carol',
    CURRENT_TIMESTAMP - INTERVAL '2 days',
    'Add customer export'
FROM repositories
WHERE repository_name = 'customer-portal';

INSERT INTO pull_requests
    (
        repository_id,
        number,
        source_branch_id,
        target_branch_id,
        author_name,
        state,
        additions,
        deletions,
        merged_at
    )
SELECT
    r.repository_id,
    101,
    source.branch_id,
    target.branch_id,
    'alice',
    'MERGED',
    180,
    42,
    CURRENT_TIMESTAMP - INTERVAL '3 days'
FROM repositories r
JOIN branches source
    ON source.repository_id = r.repository_id
   AND source.branch_name = 'feature/payments-tax'
JOIN branches target
    ON target.repository_id = r.repository_id
   AND target.branch_name = 'main'
WHERE r.repository_name = 'payments-api';

INSERT INTO pull_requests
    (
        repository_id,
        number,
        source_branch_id,
        target_branch_id,
        author_name,
        state,
        additions,
        deletions
    )
SELECT
    r.repository_id,
    102,
    source.branch_id,
    target.branch_id,
    'bob',
    'OPEN',
    75,
    13
FROM repositories r
JOIN branches source
    ON source.repository_id = r.repository_id
   AND source.branch_name = 'feature/payments-tax'
JOIN branches target
    ON target.repository_id = r.repository_id
   AND target.branch_name = 'main'
WHERE r.repository_name = 'payments-api';

INSERT INTO pull_requests
    (
        repository_id,
        number,
        source_branch_id,
        target_branch_id,
        author_name,
        state,
        additions,
        deletions,
        merged_at
    )
SELECT
    r.repository_id,
    201,
    source.branch_id,
    target.branch_id,
    'carol',
    'MERGED',
    320,
    110,
    CURRENT_TIMESTAMP - INTERVAL '2 days'
FROM repositories r
JOIN branches source
    ON source.repository_id = r.repository_id
   AND source.branch_name = 'feature/customer-export'
JOIN branches target
    ON target.repository_id = r.repository_id
   AND target.branch_name = 'main'
WHERE r.repository_name = 'customer-portal';

INSERT INTO pull_requests
    (
        repository_id,
        number,
        source_branch_id,
        target_branch_id,
        author_name,
        state,
        additions,
        deletions
    )
SELECT
    r.repository_id,
    202,
    source.branch_id,
    target.branch_id,
    'dave',
    'OPEN',
    20,
    5
FROM repositories r
JOIN branches source
    ON source.repository_id = r.repository_id
   AND source.branch_name = 'feature/customer-export'
JOIN branches target
    ON target.repository_id = r.repository_id
   AND target.branch_name = 'main'
WHERE r.repository_name = 'customer-portal';

INSERT INTO reviewers (reviewer_name, team)
VALUES
    ('reviewer-a', 'platform'),
    ('reviewer-b', 'platform'),
    ('reviewer-c', 'web'),
    ('reviewer-d', 'web');

INSERT INTO reviews
    (pull_request_id, reviewer_id, state)
SELECT pr.pull_request_id, r.reviewer_id, 'APPROVED'
FROM pull_requests pr
JOIN repositories repo
    ON repo.repository_id = pr.repository_id
JOIN reviewers r
    ON r.reviewer_name = 'reviewer-a'
WHERE repo.repository_name = 'payments-api'
  AND pr.number = 101;

INSERT INTO reviews
    (pull_request_id, reviewer_id, state)
SELECT pr.pull_request_id, r.reviewer_id, 'APPROVED'
FROM pull_requests pr
JOIN repositories repo
    ON repo.repository_id = pr.repository_id
JOIN reviewers r
    ON r.reviewer_name = 'reviewer-b'
WHERE repo.repository_name = 'payments-api'
  AND pr.number = 101;

INSERT INTO reviews
    (pull_request_id, reviewer_id, state)
SELECT pr.pull_request_id, r.reviewer_id, 'CHANGES_REQUESTED'
FROM pull_requests pr
JOIN repositories repo
    ON repo.repository_id = pr.repository_id
JOIN reviewers r
    ON r.reviewer_name = 'reviewer-a'
WHERE repo.repository_name = 'payments-api'
  AND pr.number = 102;

INSERT INTO reviews
    (pull_request_id, reviewer_id, state)
SELECT pr.pull_request_id, r.reviewer_id, 'APPROVED'
FROM pull_requests pr
JOIN repositories repo
    ON repo.repository_id = pr.repository_id
JOIN reviewers r
    ON r.reviewer_name = 'reviewer-c'
WHERE repo.repository_name = 'customer-portal'
  AND pr.number = 201;

INSERT INTO reviews
    (pull_request_id, reviewer_id, state)
SELECT pr.pull_request_id, r.reviewer_id, 'APPROVED'
FROM pull_requests pr
JOIN repositories repo
    ON repo.repository_id = pr.repository_id
JOIN reviewers r
    ON r.reviewer_name = 'reviewer-d'
WHERE repo.repository_name = 'customer-portal'
  AND pr.number = 202;

INSERT INTO review_comments
    (pull_request_id, reviewer_id, file_path, line_number, comment_text)
SELECT pr.pull_request_id, r.reviewer_id, 'src/tax.py', 42,
       'Please validate the currency before calculation.'
FROM pull_requests pr
JOIN reviewers r ON r.reviewer_name = 'reviewer-a'
WHERE pr.number = 102;

INSERT INTO review_comments
    (pull_request_id, reviewer_id, file_path, line_number, comment_text, resolved_at)
SELECT pr.pull_request_id, r.reviewer_id, 'src/export.py', 17,
       'Confirm the export field is backward compatible.',
       CURRENT_TIMESTAMP
FROM pull_requests pr
JOIN reviewers r ON r.reviewer_name = 'reviewer-c'
WHERE pr.number = 201;

INSERT INTO status_checks
    (pull_request_id, check_name, status, completed_at)
SELECT
    pr.pull_request_id,
    'unit-tests',
    CASE WHEN pr.number IN (101, 201) THEN 'PASS' ELSE 'PENDING' END,
    CASE WHEN pr.number IN (101, 201) THEN CURRENT_TIMESTAMP ELSE NULL END
FROM pull_requests pr;

INSERT INTO status_checks
    (pull_request_id, check_name, status, completed_at)
SELECT
    pr.pull_request_id,
    'security-scan',
    CASE WHEN pr.number = 101 THEN 'PASS' ELSE 'PENDING' END,
    CASE WHEN pr.number = 101 THEN CURRENT_TIMESTAMP ELSE NULL END
FROM pull_requests pr;

INSERT INTO branch_protection_policies
    (
        branch_id,
        required_reviews,
        require_status_checks,
        require_conversation_resolution,
        allow_force_push,
        allow_direct_push,
        require_linear_history,
        allow_admin_bypass
    )
SELECT
    branch_id,
    2,
    TRUE,
    TRUE,
    FALSE,
    FALSE,
    TRUE,
    FALSE
FROM branches
WHERE branch_name = 'main';

-- A normal view provides a stable reporting interface without storing
-- duplicated result rows.
CREATE OR REPLACE VIEW v_repository_activity AS
SELECT
    r.repository_id,
    r.repository_name,
    r.owner_team,
    r.is_active,
    COUNT(pr.pull_request_id) AS pull_request_count,
    COUNT(pr.pull_request_id)
        FILTER (WHERE pr.state = 'MERGED') AS merged_count,
    COALESCE(SUM(pr.additions + pr.deletions), 0) AS total_changes
FROM repositories r
LEFT JOIN pull_requests pr
    ON pr.repository_id = r.repository_id
GROUP BY
    r.repository_id,
    r.repository_name,
    r.owner_team,
    r.is_active;

-- Review metrics are deliberately separate from repository activity so that
-- review decisions are not confused with pull-request lifecycle state.
CREATE OR REPLACE VIEW v_pull_request_review_status AS
SELECT
    pr.pull_request_id,
    r.repository_name,
    pr.number,
    pr.state,
    COUNT(rv.review_id) AS review_count,
    COUNT(rv.review_id)
        FILTER (WHERE rv.state = 'APPROVED'
                AND rv.dismissed_at IS NULL) AS active_approvals,
    COUNT(rv.review_id)
        FILTER (WHERE rv.state = 'CHANGES_REQUESTED'
                AND rv.dismissed_at IS NULL) AS active_change_requests,
    COUNT(rc.comment_id)
        FILTER (WHERE rc.resolved_at IS NULL) AS unresolved_comments
FROM pull_requests pr
JOIN repositories r
    ON r.repository_id = pr.repository_id
LEFT JOIN reviews rv
    ON rv.pull_request_id = pr.pull_request_id
LEFT JOIN review_comments rc
    ON rc.pull_request_id = pr.pull_request_id
GROUP BY
    pr.pull_request_id,
    r.repository_name,
    pr.number,
    pr.state;

-- Status-check state is exposed separately because a reporting consumer may
-- need it without joining the complete operational schema.
CREATE OR REPLACE VIEW v_pull_request_check_status AS
SELECT
    pr.pull_request_id,
    r.repository_name,
    pr.number,
    COUNT(sc.status_check_id) AS check_count,
    COUNT(sc.status_check_id)
        FILTER (WHERE sc.status = 'PASS') AS passed_checks,
    COUNT(sc.status_check_id)
        FILTER (WHERE sc.status = 'FAIL') AS failed_checks,
    COUNT(sc.status_check_id)
        FILTER (WHERE sc.status = 'PENDING') AS pending_checks,
    BOOL_AND(sc.status = 'PASS') AS all_checks_pass
FROM pull_requests pr
JOIN repositories r
    ON r.repository_id = pr.repository_id
LEFT JOIN status_checks sc
    ON sc.pull_request_id = pr.pull_request_id
GROUP BY
    pr.pull_request_id,
    r.repository_name,
    pr.number;

-- A materialized view is appropriate for a repeated dashboard query whose
-- source joins and aggregates are more expensive than a simple lookup.
CREATE MATERIALIZED VIEW mv_repository_daily_report AS
SELECT
    r.repository_id,
    r.repository_name,
    r.owner_team,
    COUNT(pr.pull_request_id) AS pull_request_count,
    COUNT(pr.pull_request_id)
        FILTER (WHERE pr.state = 'MERGED') AS merged_count,
    COUNT(pr.pull_request_id)
        FILTER (WHERE pr.state = 'OPEN') AS open_count,
    COALESCE(SUM(pr.additions), 0) AS additions,
    COALESCE(SUM(pr.deletions), 0) AS deletions,
    COALESCE(
        ROUND(
            AVG(pr.additions + pr.deletions)::NUMERIC,
            2
        ),
        0
    ) AS average_change_size
FROM repositories r
LEFT JOIN pull_requests pr
    ON pr.repository_id = r.repository_id
GROUP BY
    r.repository_id,
    r.repository_name,
    r.owner_team;

CREATE UNIQUE INDEX ux_mv_repository_daily_report
    ON mv_repository_daily_report(repository_id);

-- This CTE computes merge eligibility without storing it. It combines
-- approval, unresolved-discussion, and status-check information.
CREATE OR REPLACE VIEW v_pull_request_merge_eligibility AS
WITH review_state AS (
    SELECT
        pr.pull_request_id,
        COALESCE(
            COUNT(rv.review_id)
            FILTER (
                WHERE rv.state = 'APPROVED'
                  AND rv.dismissed_at IS NULL
            ),
            0
        ) AS approvals,
        COALESCE(
            COUNT(rv.review_id)
            FILTER (
                WHERE rv.state = 'CHANGES_REQUESTED'
                  AND rv.dismissed_at IS NULL
            ),
            0
        ) AS change_requests
    FROM pull_requests pr
    LEFT JOIN reviews rv
        ON rv.pull_request_id = pr.pull_request_id
    GROUP BY pr.pull_request_id
),
comment_state AS (
    SELECT
        pull_request_id,
        COUNT(*) FILTER (WHERE resolved_at IS NULL) AS unresolved_comments
    FROM review_comments
    GROUP BY pull_request_id
),
check_state AS (
    SELECT
        pull_request_id,
        COUNT(*) AS checks,
        COUNT(*) FILTER (WHERE status = 'PASS') AS passed_checks,
        COUNT(*) FILTER (WHERE status = 'FAIL') AS failed_checks
    FROM status_checks
    GROUP BY pull_request_id
)
SELECT
    pr.pull_request_id,
    repo.repository_name,
    pr.number,
    pr.state,
    bp.required_reviews,
    COALESCE(rs.approvals, 0) AS approvals,
    COALESCE(rs.change_requests, 0) AS change_requests,
    COALESCE(cs.unresolved_comments, 0) AS unresolved_comments,
    COALESCE(ch.checks, 0) AS checks,
    COALESCE(ch.passed_checks, 0) AS passed_checks,
    COALESCE(ch.failed_checks, 0) AS failed_checks,
    (
        pr.state = 'OPEN'
        AND COALESCE(rs.change_requests, 0) = 0
        AND COALESCE(rs.approvals, 0) >= bp.required_reviews
        AND (
            NOT bp.require_conversation_resolution
            OR COALESCE(cs.unresolved_comments, 0) = 0
        )
        AND (
            NOT bp.require_status_checks
            OR (
                COALESCE(ch.checks, 0) > 0
                AND COALESCE(ch.failed_checks, 0) = 0
                AND COALESCE(ch.passed_checks, 0) = COALESCE(ch.checks, 0)
            )
        )
    ) AS merge_eligible
FROM pull_requests pr
JOIN repositories repo
    ON repo.repository_id = pr.repository_id
JOIN branches target
    ON target.branch_id = pr.target_branch_id
JOIN branch_protection_policies bp
    ON bp.branch_id = target.branch_id
LEFT JOIN review_state rs
    ON rs.pull_request_id = pr.pull_request_id
LEFT JOIN comment_state cs
    ON cs.pull_request_id = pr.pull_request_id
LEFT JOIN check_state ch
    ON ch.pull_request_id = pr.pull_request_id;

-- Basic view retrieval.
SELECT *
FROM v_repository_activity
ORDER BY repository_name;

-- Review-specific reporting.
SELECT *
FROM v_pull_request_review_status
ORDER BY repository_name, number;

-- Status-check reporting.
SELECT *
FROM v_pull_request_check_status
ORDER BY repository_name, number;

-- CTE-backed merge eligibility evaluation.
SELECT *
FROM v_pull_request_merge_eligibility
ORDER BY repository_name, number;

-- Materialized view retrieval.
SELECT *
FROM mv_repository_daily_report
ORDER BY repository_name;

-- Demonstrate the difference between live and persisted results.
BEGIN;

INSERT INTO pull_requests
    (
        repository_id,
        number,
        source_branch_id,
        target_branch_id,
        author_name,
        state,
        additions,
        deletions
    )
SELECT
    r.repository_id,
    104,
    source.branch_id,
    target.branch_id,
    'erin',
    'OPEN',
    55,
    8
FROM repositories r
JOIN branches source
    ON source.repository_id = r.repository_id
   AND source.branch_name = 'feature/payments-tax'
JOIN branches target
    ON target.repository_id = r.repository_id
   AND target.branch_name = 'main'
WHERE r.repository_name = 'payments-api';

-- The normal view sees the new row because it reads current base data.
SELECT *
FROM v_repository_activity
WHERE repository_name = 'payments-api';

-- The materialized view still contains the previous snapshot.
SELECT *
FROM mv_repository_daily_report
WHERE repository_name = 'payments-api';

ROLLBACK;

-- Refresh after committed source changes when the reporting snapshot must
-- include them. CONCURRENTLY requires a suitable unique index, which was
-- created above.
REFRESH MATERIALIZED VIEW mv_repository_daily_report;

SELECT *
FROM mv_repository_daily_report
ORDER BY repository_name;

-- A transaction demonstrates that view reads participate in ordinary
-- PostgreSQL transaction visibility.
BEGIN;

UPDATE pull_requests
SET additions = additions + 10
WHERE pull_request_id = (
    SELECT pull_request_id
    FROM pull_requests
    WHERE number = 102
);

SELECT
    number,
    additions
FROM pull_requests
WHERE number = 102;

SELECT
    repository_name,
    total_changes
FROM v_repository_activity
WHERE repository_name = 'payments-api';

ROLLBACK;

-- After rollback, the base row and therefore the normal view return to the
-- previous committed state.
SELECT
    number,
    additions
FROM pull_requests
WHERE number = 102;

-- A materialized view is intentionally not refreshed automatically by a
-- normal DML statement. Refresh scheduling should match the required
-- freshness window rather than being treated as an implicit property.
