DROP SCHEMA IF EXISTS plpgsql_variables_control_flow CASCADE;
CREATE SCHEMA plpgsql_variables_control_flow;
SET search_path TO plpgsql_variables_control_flow;

-- The schema models repository-governance data so PL/pgSQL variables,
-- branching, loops, functions, and exception handling operate on
-- realistic relational state.

CREATE TYPE pull_request_state AS ENUM (
    'open',
    'merged',
    'closed'
);

CREATE TYPE review_state AS ENUM (
    'commented',
    'changes_requested',
    'approved',
    'dismissed'
);

CREATE TABLE repositories (
    repository_id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    default_branch TEXT NOT NULL DEFAULT 'main',
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CHECK (length(trim(name)) BETWEEN 1 AND 100),
    CHECK (length(trim(default_branch)) BETWEEN 1 AND 100)
);

CREATE TABLE branches (
    branch_id BIGSERIAL PRIMARY KEY,
    repository_id BIGINT NOT NULL
        REFERENCES repositories(repository_id)
        ON DELETE CASCADE,
    branch_name TEXT NOT NULL,
    is_protected BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE (repository_id, branch_name),
    CHECK (length(trim(branch_name)) BETWEEN 1 AND 100)
);

CREATE TABLE repository_users (
    user_id BIGSERIAL PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    CHECK (username ~ '^[A-Za-z0-9_.-]{1,50}$')
);

CREATE TABLE pull_requests (
    pull_request_id BIGSERIAL PRIMARY KEY,
    repository_id BIGINT NOT NULL
        REFERENCES repositories(repository_id)
        ON DELETE CASCADE,
    source_branch_id BIGINT NOT NULL
        REFERENCES branches(branch_id),
    target_branch_id BIGINT NOT NULL
        REFERENCES branches(branch_id),
    author_id BIGINT NOT NULL
        REFERENCES repository_users(user_id),
    title TEXT NOT NULL,
    state pull_request_state NOT NULL DEFAULT 'open',
    changed_files INTEGER NOT NULL DEFAULT 0,
    additions INTEGER NOT NULL DEFAULT 0,
    deletions INTEGER NOT NULL DEFAULT 0,
    unresolved_conversations INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    merged_at TIMESTAMPTZ,
    CHECK (length(trim(title)) BETWEEN 1 AND 250),
    CHECK (changed_files >= 0),
    CHECK (additions >= 0),
    CHECK (deletions >= 0),
    CHECK (unresolved_conversations >= 0),
    CHECK (source_branch_id <> target_branch_id)
);

CREATE TABLE commits (
    commit_id BIGSERIAL PRIMARY KEY,
    pull_request_id BIGINT NOT NULL
        REFERENCES pull_requests(pull_request_id)
        ON DELETE CASCADE,
    commit_hash TEXT NOT NULL UNIQUE,
    author_id BIGINT NOT NULL
        REFERENCES repository_users(user_id),
    message TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CHECK (commit_hash ~ '^[0-9a-f]{7,64}$'),
    CHECK (length(trim(message)) > 0)
);

CREATE TABLE review_assignments (
    pull_request_id BIGINT NOT NULL
        REFERENCES pull_requests(pull_request_id)
        ON DELETE CASCADE,
    reviewer_id BIGINT NOT NULL
        REFERENCES repository_users(user_id),
    requested_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (pull_request_id, reviewer_id)
);

CREATE TABLE reviews (
    review_id BIGSERIAL PRIMARY KEY,
    pull_request_id BIGINT NOT NULL
        REFERENCES pull_requests(pull_request_id)
        ON DELETE CASCADE,
    reviewer_id BIGINT NOT NULL
        REFERENCES repository_users(user_id),
    state review_state NOT NULL,
    body TEXT NOT NULL DEFAULT '',
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE review_comments (
    comment_id BIGSERIAL PRIMARY KEY,
    review_id BIGINT NOT NULL
        REFERENCES reviews(review_id)
        ON DELETE CASCADE,
    author_id BIGINT NOT NULL
        REFERENCES repository_users(user_id),
    body TEXT NOT NULL,
    resolved BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CHECK (length(trim(body)) > 0)
);

CREATE TABLE status_checks (
    status_check_id BIGSERIAL PRIMARY KEY,
    pull_request_id BIGINT NOT NULL
        REFERENCES pull_requests(pull_request_id)
        ON DELETE CASCADE,
    check_name TEXT NOT NULL,
    passed BOOLEAN NOT NULL,
    completed_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (pull_request_id, check_name),
    CHECK (length(trim(check_name)) > 0)
);

CREATE TABLE branch_protection_policies (
    policy_id BIGSERIAL PRIMARY KEY,
    branch_id BIGINT NOT NULL UNIQUE
        REFERENCES branches(branch_id)
        ON DELETE CASCADE,
    required_reviews INTEGER NOT NULL DEFAULT 0,
    require_status_checks BOOLEAN NOT NULL DEFAULT TRUE,
    require_resolved_conversations BOOLEAN NOT NULL DEFAULT TRUE,
    allow_direct_push BOOLEAN NOT NULL DEFAULT FALSE,
    allow_force_push BOOLEAN NOT NULL DEFAULT FALSE,
    allow_branch_deletion BOOLEAN NOT NULL DEFAULT FALSE,
    require_linear_history BOOLEAN NOT NULL DEFAULT FALSE,
    CHECK (required_reviews >= 0)
);

CREATE TABLE merge_audit (
    audit_id BIGSERIAL PRIMARY KEY,
    pull_request_id BIGINT NOT NULL
        REFERENCES pull_requests(pull_request_id)
        ON DELETE CASCADE,
    decision BOOLEAN NOT NULL,
    reason TEXT NOT NULL,
    evaluated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

CREATE INDEX idx_pull_requests_repository_state
    ON pull_requests(repository_id, state);

CREATE INDEX idx_reviews_pull_request_state
    ON reviews(pull_request_id, state);

CREATE INDEX idx_status_checks_pull_request
    ON status_checks(pull_request_id);

CREATE INDEX idx_review_comments_unresolved
    ON review_comments(review_id)
    WHERE resolved = FALSE;

INSERT INTO repositories (name, default_branch)
VALUES
    ('governance-platform', 'main'),
    ('deployment-service', 'main');

INSERT INTO branches (repository_id, branch_name, is_protected)
SELECT repository_id, 'main', TRUE
FROM repositories;

INSERT INTO branches (repository_id, branch_name)
SELECT repository_id, branch_name
FROM repositories
CROSS JOIN (
    VALUES
        ('feature/governance'),
        ('feature/review-policy'),
        ('feature/observability')
) AS branch_values(branch_name);

INSERT INTO repository_users (username)
VALUES
    ('alice'),
    ('bob'),
    ('carol'),
    ('david'),
    ('erin');

INSERT INTO branch_protection_policies (
    branch_id,
    required_reviews,
    require_status_checks,
    require_resolved_conversations,
    allow_direct_push,
    allow_force_push,
    allow_branch_deletion,
    require_linear_history
)
SELECT
    branch_id,
    2,
    TRUE,
    TRUE,
    FALSE,
    FALSE,
    FALSE,
    TRUE
FROM branches
WHERE branch_name = 'main';

INSERT INTO pull_requests (
    repository_id,
    source_branch_id,
    target_branch_id,
    author_id,
    title,
    changed_files,
    additions,
    deletions
)
SELECT
    r.repository_id,
    source.branch_id,
    target.branch_id,
    u.user_id,
    'Introduce repository governance functions',
    8,
    180,
    40
FROM repositories r
JOIN branches source
    ON source.repository_id = r.repository_id
   AND source.branch_name = 'feature/governance'
JOIN branches target
    ON target.repository_id = r.repository_id
   AND target.branch_name = 'main'
JOIN repository_users u
    ON u.username = 'alice'
WHERE r.name = 'governance-platform';

INSERT INTO pull_requests (
    repository_id,
    source_branch_id,
    target_branch_id,
    author_id,
    title,
    changed_files,
    additions,
    deletions,
    unresolved_conversations
)
SELECT
    r.repository_id,
    source.branch_id,
    target.branch_id,
    u.user_id,
    'Refactor review policy',
    18,
    450,
    90,
    1
FROM repositories r
JOIN branches source
    ON source.repository_id = r.repository_id
   AND source.branch_name = 'feature/review-policy'
JOIN branches target
    ON target.repository_id = r.repository_id
   AND target.branch_name = 'main'
JOIN repository_users u
    ON u.username = 'bob'
WHERE r.name = 'governance-platform';

INSERT INTO review_assignments (pull_request_id, reviewer_id)
SELECT pr.pull_request_id, u.user_id
FROM pull_requests pr
JOIN repository_users u
    ON u.username IN ('bob', 'carol')
WHERE pr.title = 'Introduce repository governance functions';

INSERT INTO review_assignments (pull_request_id, reviewer_id)
SELECT pr.pull_request_id, u.user_id
FROM pull_requests pr
JOIN repository_users u
    ON u.username IN ('alice', 'carol')
WHERE pr.title = 'Refactor review policy';

INSERT INTO reviews (
    pull_request_id,
    reviewer_id,
    state,
    body
)
SELECT
    pr.pull_request_id,
    u.user_id,
    'approved',
    'Repository-level validation is sound.'
FROM pull_requests pr
JOIN repository_users u
    ON u.username = 'bob'
WHERE pr.title = 'Introduce repository governance functions';

INSERT INTO reviews (
    pull_request_id,
    reviewer_id,
    state,
    body
)
SELECT
    pr.pull_request_id,
    u.user_id,
    'approved',
    'The workflow rules are consistent.'
FROM pull_requests pr
JOIN repository_users u
    ON u.username = 'carol'
WHERE pr.title = 'Introduce repository governance functions';

INSERT INTO reviews (
    pull_request_id,
    reviewer_id,
    state,
    body
)
SELECT
    pr.pull_request_id,
    u.user_id,
    'approved',
    'Initial review completed.'
FROM pull_requests pr
JOIN repository_users u
    ON u.username = 'alice'
WHERE pr.title = 'Refactor review policy';

INSERT INTO review_comments (
    review_id,
    author_id,
    body,
    resolved
)
SELECT
    rv.review_id,
    author.user_id,
    'Please resolve the remaining workflow ambiguity.',
    FALSE
FROM reviews rv
JOIN pull_requests pr
    ON pr.pull_request_id = rv.pull_request_id
JOIN repository_users author
    ON author.username = 'david'
WHERE pr.title = 'Refactor review policy';

INSERT INTO status_checks (
    pull_request_id,
    check_name,
    passed
)
SELECT
    pr.pull_request_id,
    checks.check_name,
    checks.passed
FROM pull_requests pr
CROSS JOIN (
    VALUES
        ('unit-tests', TRUE),
        ('lint', TRUE),
        ('security-scan', TRUE)
) AS checks(check_name, passed)
WHERE pr.title = 'Introduce repository governance functions';

INSERT INTO status_checks (
    pull_request_id,
    check_name,
    passed
)
SELECT
    pr.pull_request_id,
    checks.check_name,
    checks.passed
FROM pull_requests pr
CROSS JOIN (
    VALUES
        ('unit-tests', TRUE),
        ('lint', FALSE),
        ('security-scan', TRUE)
) AS checks(check_name, passed)
WHERE pr.title = 'Refactor review policy';

-- This function demonstrates PL/pgSQL variables, IF/ELSIF control flow,
-- aggregation into local variables, and a returned classification.
CREATE OR REPLACE FUNCTION calculate_pr_risk(
    p_pull_request_id BIGINT
)
RETURNS TEXT
LANGUAGE plpgsql
AS $$
DECLARE
    v_changed_files INTEGER;
    v_additions INTEGER;
    v_deletions INTEGER;
    v_review_count INTEGER;
    v_unresolved INTEGER;
    v_score INTEGER := 0;
    v_line_delta INTEGER;
BEGIN
    SELECT
        changed_files,
        additions,
        deletions,
        unresolved_conversations
    INTO
        v_changed_files,
        v_additions,
        v_deletions,
        v_unresolved
    FROM pull_requests
    WHERE pull_request_id = p_pull_request_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION
            'Pull Request % does not exist',
            p_pull_request_id;
    END IF;

    SELECT count(*)
    INTO v_review_count
    FROM reviews
    WHERE pull_request_id = p_pull_request_id;

    v_line_delta := abs(v_additions - v_deletions);

    IF v_changed_files > 20 THEN
        v_score := v_score + 2;
    ELSIF v_changed_files > 10 THEN
        v_score := v_score + 1;
    END IF;

    IF v_line_delta > 500 THEN
        v_score := v_score + 2;
    ELSIF v_line_delta > 200 THEN
        v_score := v_score + 1;
    END IF;

    IF v_review_count = 0 THEN
        v_score := v_score + 2;
    END IF;

    IF v_unresolved > 0 THEN
        v_score := v_score + 1;
    END IF;

    IF v_score >= 4 THEN
        RETURN 'HIGH';
    ELSIF v_score >= 2 THEN
        RETURN 'MEDIUM';
    ELSE
        RETURN 'LOW';
    END IF;
END;
$$;

-- A loop is useful when evaluating a collection of required status checks.
CREATE OR REPLACE FUNCTION count_failed_checks(
    p_pull_request_id BIGINT
)
RETURNS INTEGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_check RECORD;
    v_failures INTEGER := 0;
BEGIN
    FOR v_check IN
        SELECT check_name, passed
        FROM status_checks
        WHERE pull_request_id = p_pull_request_id
        ORDER BY check_name
    LOOP
        IF NOT v_check.passed THEN
            v_failures := v_failures + 1;
        END IF;
    END LOOP;

    RETURN v_failures;
END;
$$;

-- This function evaluates the complete merge policy. It intentionally
-- separates local variables for approvals, failed checks, unresolved
-- conversations, and policy requirements.
CREATE OR REPLACE FUNCTION evaluate_merge_eligibility(
    p_pull_request_id BIGINT
)
RETURNS TABLE (
    eligible BOOLEAN,
    reason TEXT
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_state pull_request_state;
    v_source_branch BIGINT;
    v_target_branch BIGINT;
    v_changed_files INTEGER;
    v_unresolved INTEGER;
    v_required_reviews INTEGER;
    v_approvals INTEGER;
    v_failed_checks INTEGER;
    v_require_checks BOOLEAN;
    v_require_resolved BOOLEAN;
    v_found_policy BOOLEAN := FALSE;
BEGIN
    SELECT
        pr.state,
        pr.source_branch_id,
        pr.target_branch_id,
        pr.changed_files,
        pr.unresolved_conversations
    INTO
        v_state,
        v_source_branch,
        v_target_branch,
        v_changed_files,
        v_unresolved
    FROM pull_requests pr
    WHERE pr.pull_request_id = p_pull_request_id;

    IF NOT FOUND THEN
        RETURN QUERY
        SELECT FALSE, 'Pull Request does not exist';
        RETURN;
    END IF;

    SELECT
        bpp.required_reviews,
        bpp.require_status_checks,
        bpp.require_resolved_conversations
    INTO
        v_required_reviews,
        v_require_checks,
        v_require_resolved
    FROM branch_protection_policies bpp
    WHERE bpp.branch_id = v_target_branch;

    v_found_policy := FOUND;

    IF NOT v_found_policy THEN
        RETURN QUERY
        SELECT FALSE, 'Target branch has no protection policy';
        RETURN;
    END IF;

    SELECT count(*)
    INTO v_approvals
    FROM reviews
    WHERE pull_request_id = p_pull_request_id
      AND state = 'approved';

    v_failed_checks := count_failed_checks(p_pull_request_id);

    IF v_state <> 'open' THEN
        RETURN QUERY
        SELECT FALSE, 'Pull Request is not open';
        RETURN;
    END IF;

    IF v_source_branch = v_target_branch THEN
        RETURN QUERY
        SELECT FALSE, 'Source and target branches must differ';
        RETURN;
    END IF;

    IF v_changed_files = 0 THEN
        RETURN QUERY
        SELECT FALSE, 'Pull Request contains no changes';
        RETURN;
    END IF;

    IF v_approvals < v_required_reviews THEN
        RETURN QUERY
        SELECT
            FALSE,
            format(
                'Required approvals: %s; actual approvals: %s',
                v_required_reviews,
                v_approvals
            );
        RETURN;
    END IF;

    IF v_require_checks AND v_failed_checks > 0 THEN
        RETURN QUERY
        SELECT
            FALSE,
            format(
                'Failed status checks: %s',
                v_failed_checks
            );
        RETURN;
    END IF;

    IF v_require_checks
       AND NOT EXISTS (
           SELECT 1
           FROM status_checks
           WHERE pull_request_id = p_pull_request_id
       )
    THEN
        RETURN QUERY
        SELECT FALSE, 'Required status checks are missing';
        RETURN;
    END IF;

    IF v_require_resolved AND v_unresolved > 0 THEN
        RETURN QUERY
        SELECT
            FALSE,
            format(
                'Unresolved conversations: %s',
                v_unresolved
            );
        RETURN;
    END IF;

    RETURN QUERY
    SELECT TRUE, 'Pull Request satisfies merge policy';
END;
$$;

-- The merge function uses a transaction-safe state transition and records
-- the decision before changing the Pull Request state.
CREATE OR REPLACE FUNCTION merge_pull_request(
    p_pull_request_id BIGINT
)
RETURNS TEXT
LANGUAGE plpgsql
AS $$
DECLARE
    v_eligible BOOLEAN;
    v_reason TEXT;
BEGIN
    SELECT eligible, reason
    INTO v_eligible, v_reason
    FROM evaluate_merge_eligibility(p_pull_request_id)
    LIMIT 1;

    IF v_eligible IS NULL THEN
        RAISE EXCEPTION
            'No eligibility result for Pull Request %',
            p_pull_request_id;
    END IF;

    INSERT INTO merge_audit (
        pull_request_id,
        decision,
        reason
    )
    VALUES (
        p_pull_request_id,
        v_eligible,
        v_reason
    );

    IF NOT v_eligible THEN
        RETURN 'MERGE REJECTED: ' || v_reason;
    END IF;

    UPDATE pull_requests
    SET
        state = 'merged',
        merged_at = clock_timestamp()
    WHERE pull_request_id = p_pull_request_id
      AND state = 'open';

    IF NOT FOUND THEN
        RAISE EXCEPTION
            'Pull Request % changed state during merge',
            p_pull_request_id;
    END IF;

    RETURN 'MERGE SUCCESSFUL';
END;
$$;

-- A trigger function keeps the state transition invariant in the database.
CREATE OR REPLACE FUNCTION prevent_invalid_merge_state()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF OLD.state = 'merged' AND NEW.state <> 'merged' THEN
        RAISE EXCEPTION
            'A merged Pull Request cannot transition back to %',
            NEW.state;
    END IF;

    IF NEW.state = 'merged'
       AND NEW.merged_at IS NULL
    THEN
        NEW.merged_at := clock_timestamp();
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_prevent_invalid_merge_state
BEFORE UPDATE OF state ON pull_requests
FOR EACH ROW
EXECUTE FUNCTION prevent_invalid_merge_state();

-- Basic function calls.
SELECT
    pr.pull_request_id,
    pr.title,
    calculate_pr_risk(pr.pull_request_id) AS risk,
    count_failed_checks(pr.pull_request_id) AS failed_checks
FROM pull_requests pr
ORDER BY pr.pull_request_id;

-- CTE + function-based policy evaluation.
WITH evaluations AS (
    SELECT
        pr.pull_request_id,
        pr.title,
        evaluate_merge_eligibility(pr.pull_request_id)
            AS evaluation
    FROM pull_requests pr
)
SELECT
    pull_request_id,
    title,
    (evaluation).eligible,
    (evaluation).reason
FROM evaluations
ORDER BY pull_request_id;

-- Demonstrate a successful function-controlled state transition.
BEGIN;

SELECT merge_pull_request(
    (
        SELECT pull_request_id
        FROM pull_requests
        WHERE title = 'Introduce repository governance functions'
    )
);

COMMIT;

-- The second Pull Request remains open because it has an insufficient
-- approval count, a failed status check, and an unresolved conversation.
SELECT merge_pull_request(
    (
        SELECT pull_request_id
        FROM pull_requests
        WHERE title = 'Refactor review policy'
    )
);

-- Reporting query showing variables/functions alongside relational data.
SELECT
    r.name AS repository,
    pr.pull_request_id,
    pr.title,
    pr.state,
    calculate_pr_risk(pr.pull_request_id) AS risk,
    (
        SELECT count(*)
        FROM reviews rv
        WHERE rv.pull_request_id = pr.pull_request_id
          AND rv.state = 'approved'
    ) AS approvals,
    count_failed_checks(pr.pull_request_id) AS failed_checks
FROM repositories r
JOIN pull_requests pr
    ON pr.repository_id = r.repository_id
ORDER BY pr.pull_request_id;
