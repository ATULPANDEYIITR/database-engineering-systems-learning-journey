DROP SCHEMA IF EXISTS repository_governance CASCADE;
CREATE SCHEMA repository_governance;
SET search_path = repository_governance, public;

-- PostgreSQL functions are used here as database-level business rules.
-- SQL-language functions are appropriate for deterministic queries.
-- PL/pgSQL functions are used where conditional workflow logic is required.

CREATE TYPE pull_request_state AS ENUM (
    'draft',
    'open',
    'closed',
    'merged'
);

CREATE TYPE review_state AS ENUM (
    'commented',
    'approved',
    'changes_requested',
    'dismissed'
);

CREATE TYPE merge_strategy AS ENUM (
    'merge_commit',
    'squash',
    'rebase'
);

CREATE TABLE repositories (
    repository_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    repository_name text NOT NULL UNIQUE,
    created_at timestamptz NOT NULL DEFAULT now(),
    CHECK (length(trim(repository_name)) >= 2)
);

CREATE TABLE repository_users (
    user_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    repository_id bigint NOT NULL
        REFERENCES repositories(repository_id) ON DELETE CASCADE,
    username text NOT NULL,
    role_name text NOT NULL,
    active boolean NOT NULL DEFAULT true,
    UNIQUE (repository_id, username),
    CHECK (length(trim(username)) >= 2),
    CHECK (role_name IN ('developer', 'reviewer', 'maintainer', 'administrator'))
);

CREATE TABLE branches (
    branch_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    repository_id bigint NOT NULL
        REFERENCES repositories(repository_id) ON DELETE CASCADE,
    branch_name text NOT NULL,
    revision bigint NOT NULL DEFAULT 1,
    UNIQUE (repository_id, branch_name),
    CHECK (revision > 0),
    CHECK (
        branch_name !~ '\.\.' AND
        branch_name !~ '\s' AND
        branch_name !~ '/$'
    )
);

CREATE TABLE branch_protection (
    protection_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    branch_id bigint NOT NULL UNIQUE
        REFERENCES branches(branch_id) ON DELETE CASCADE,
    required_reviews integer NOT NULL DEFAULT 0,
    require_resolved_conversations boolean NOT NULL DEFAULT true,
    restrict_direct_push boolean NOT NULL DEFAULT true,
    restrict_force_push boolean NOT NULL DEFAULT true,
    restrict_deletion boolean NOT NULL DEFAULT true,
    require_linear_history boolean NOT NULL DEFAULT false,
    CHECK (required_reviews >= 0)
);

CREATE TABLE protected_status_requirements (
    protection_id bigint NOT NULL
        REFERENCES branch_protection(protection_id) ON DELETE CASCADE,
    check_name text NOT NULL,
    PRIMARY KEY (protection_id, check_name),
    CHECK (length(trim(check_name)) > 0)
);

CREATE TABLE pull_requests (
    pull_request_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    repository_id bigint NOT NULL
        REFERENCES repositories(repository_id) ON DELETE CASCADE,
    number integer NOT NULL,
    source_branch_id bigint NOT NULL
        REFERENCES branches(branch_id),
    target_branch_id bigint NOT NULL
        REFERENCES branches(branch_id),
    state pull_request_state NOT NULL DEFAULT 'open',
    draft boolean NOT NULL DEFAULT false,
    base_revision bigint NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    merged_at timestamptz,
    merge_strategy merge_strategy,
    UNIQUE (repository_id, number),
    CHECK (number > 0),
    CHECK (source_branch_id <> target_branch_id),
    CHECK (base_revision > 0),
    CHECK (
        (state = 'merged' AND merged_at IS NOT NULL AND merge_strategy IS NOT NULL)
        OR
        (state <> 'merged' AND merged_at IS NULL)
    )
);

CREATE TABLE commits (
    commit_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    pull_request_id bigint NOT NULL
        REFERENCES pull_requests(pull_request_id) ON DELETE CASCADE,
    sha text NOT NULL,
    message text NOT NULL,
    author_user_id bigint NOT NULL
        REFERENCES repository_users(user_id),
    sequence_no integer NOT NULL,
    UNIQUE (pull_request_id, sha),
    UNIQUE (pull_request_id, sequence_no),
    CHECK (length(sha) >= 7),
    CHECK (length(trim(message)) > 0),
    CHECK (sequence_no > 0)
);

CREATE TABLE reviews (
    review_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    pull_request_id bigint NOT NULL
        REFERENCES pull_requests(pull_request_id) ON DELETE CASCADE,
    reviewer_user_id bigint NOT NULL
        REFERENCES repository_users(user_id),
    state review_state NOT NULL,
    commit_id bigint NOT NULL
        REFERENCES commits(commit_id),
    submitted_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE review_comments (
    comment_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    review_id bigint NOT NULL
        REFERENCES reviews(review_id) ON DELETE CASCADE,
    file_path text NOT NULL,
    line_number integer,
    body text NOT NULL,
    resolved boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    CHECK (length(trim(file_path)) > 0),
    CHECK (line_number IS NULL OR line_number > 0),
    CHECK (length(trim(body)) > 0)
);

CREATE TABLE status_checks (
    status_check_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    pull_request_id bigint NOT NULL
        REFERENCES pull_requests(pull_request_id) ON DELETE CASCADE,
    check_name text NOT NULL,
    passed boolean NOT NULL,
    completed_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (pull_request_id, check_name)
);

CREATE INDEX idx_pr_target_state
    ON pull_requests(target_branch_id, state);

CREATE INDEX idx_reviews_pr_reviewer
    ON reviews(pull_request_id, reviewer_user_id, submitted_at DESC);

CREATE INDEX idx_comments_unresolved
    ON review_comments(review_id)
    WHERE resolved = false;

CREATE INDEX idx_status_checks_pr
    ON status_checks(pull_request_id, check_name);

INSERT INTO repositories(repository_name)
VALUES ('payments-platform');

INSERT INTO repository_users(repository_id, username, role_name)
SELECT repository_id, v.username, v.role_name
FROM repositories r
CROSS JOIN (
    VALUES
        ('alice', 'developer'),
        ('bob', 'reviewer'),
        ('carol', 'reviewer'),
        ('dave', 'maintainer')
) AS v(username, role_name)
WHERE r.repository_name = 'payments-platform';

INSERT INTO branches(repository_id, branch_name, revision)
SELECT repository_id, 'main', 15
FROM repositories
WHERE repository_name = 'payments-platform';

INSERT INTO branches(repository_id, branch_name, revision)
SELECT repository_id, 'feature/payment-audit', 4
FROM repositories
WHERE repository_name = 'payments-platform';

INSERT INTO branch_protection(
    branch_id,
    required_reviews,
    require_resolved_conversations,
    restrict_direct_push,
    restrict_force_push,
    restrict_deletion,
    require_linear_history
)
SELECT branch_id, 2, true, true, true, true, true
FROM branches
WHERE branch_name = 'main';

INSERT INTO protected_status_requirements(protection_id, check_name)
SELECT protection_id, v.check_name
FROM branch_protection bp
CROSS JOIN (VALUES ('unit-tests'), ('security-scan')) v(check_name);

INSERT INTO pull_requests(
    repository_id,
    number,
    source_branch_id,
    target_branch_id,
    state,
    draft,
    base_revision
)
SELECT
    r.repository_id,
    101,
    source.branch_id,
    target.branch_id,
    'open',
    false,
    target.revision
FROM repositories r
JOIN branches source
    ON source.repository_id = r.repository_id
   AND source.branch_name = 'feature/payment-audit'
JOIN branches target
    ON target.repository_id = r.repository_id
   AND target.branch_name = 'main'
WHERE r.repository_name = 'payments-platform';

INSERT INTO commits(
    pull_request_id,
    sha,
    message,
    author_user_id,
    sequence_no
)
SELECT
    pr.pull_request_id,
    v.sha,
    v.message,
    u.user_id,
    v.sequence_no
FROM pull_requests pr
JOIN repository_users u
    ON u.repository_id = pr.repository_id
   AND u.username = 'alice'
CROSS JOIN (
    VALUES
        ('1111111', 'Validate payment ownership', 1),
        ('2222222', 'Add payment authorization guard', 2)
) v(sha, message, sequence_no)
WHERE pr.number = 101;

INSERT INTO reviews(
    pull_request_id,
    reviewer_user_id,
    state,
    commit_id
)
SELECT
    pr.pull_request_id,
    reviewer.user_id,
    'approved',
    c.commit_id
FROM pull_requests pr
JOIN commits c
    ON c.pull_request_id = pr.pull_request_id
   AND c.sha = '2222222'
JOIN repository_users reviewer
    ON reviewer.repository_id = pr.repository_id
   AND reviewer.username IN ('bob', 'carol')
WHERE pr.number = 101;

INSERT INTO status_checks(pull_request_id, check_name, passed)
SELECT pr.pull_request_id, v.check_name, v.passed
FROM pull_requests pr
CROSS JOIN (
    VALUES
        ('unit-tests', true),
        ('security-scan', true)
) v(check_name, passed)
WHERE pr.number = 101;

INSERT INTO review_comments(
    review_id,
    file_path,
    line_number,
    body,
    resolved
)
SELECT
    review_id,
    'src/payment.py',
    42,
    'Authorization boundary is explicit.',
    true
FROM reviews
WHERE pull_request_id = (
    SELECT pull_request_id
    FROM pull_requests
    WHERE number = 101
)
LIMIT 1;

-- SQL function: compact reusable query returning the latest review
-- submitted by a particular reviewer for a Pull Request.
CREATE OR REPLACE FUNCTION latest_reviewer_state(
    p_pull_request_id bigint,
    p_reviewer_user_id bigint
)
RETURNS review_state
LANGUAGE sql
STABLE
AS $$
    SELECT r.state
    FROM reviews r
    WHERE r.pull_request_id = p_pull_request_id
      AND r.reviewer_user_id = p_reviewer_user_id
    ORDER BY r.submitted_at DESC, r.review_id DESC
    LIMIT 1
$$;

-- SQL function: count approvals that apply to the current changeset.
CREATE OR REPLACE FUNCTION current_approval_count(
    p_pull_request_id bigint
)
RETURNS integer
LANGUAGE sql
STABLE
AS $$
    WITH current_commit AS (
        SELECT commit_id
        FROM commits
        WHERE pull_request_id = p_pull_request_id
        ORDER BY sequence_no DESC
        LIMIT 1
    ),
    latest_review AS (
        SELECT DISTINCT ON (reviewer_user_id)
            reviewer_user_id,
            state,
            commit_id
        FROM reviews
        WHERE pull_request_id = p_pull_request_id
        ORDER BY reviewer_user_id, submitted_at DESC, review_id DESC
    )
    SELECT count(*)::integer
    FROM latest_review lr
    JOIN current_commit cc
      ON cc.commit_id = lr.commit_id
    WHERE lr.state = 'approved'
$$;

-- PL/pgSQL function: procedural merge eligibility evaluation.
CREATE OR REPLACE FUNCTION evaluate_merge_eligibility(
    p_pull_request_id bigint
)
RETURNS TABLE (
    eligible boolean,
    failure_reason text
)
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    pr record;
    protection record;
    required_count integer;
    actual_approvals integer;
    missing_check text;
BEGIN
    SELECT
        pr.*,
        target.branch_name AS target_branch,
        target.revision AS target_revision
    INTO pr
    FROM pull_requests pr
    JOIN branches target
      ON target.branch_id = pr.target_branch_id
    WHERE pr.pull_request_id = p_pull_request_id;

    IF NOT FOUND THEN
        RETURN QUERY SELECT false, 'Pull Request does not exist';
        RETURN;
    END IF;

    IF pr.state <> 'open' THEN
        RETURN QUERY SELECT false, 'Pull Request is not open';
    END IF;

    IF pr.draft THEN
        RETURN QUERY SELECT false, 'Pull Request is still a draft';
    END IF;

    IF pr.base_revision <> pr.target_revision THEN
        RETURN QUERY SELECT false, 'Pull Request is behind target branch';
    END IF;

    SELECT bp.*
    INTO protection
    FROM branch_protection bp
    JOIN branches b
      ON b.branch_id = bp.branch_id
    WHERE b.branch_id = pr.target_branch_id;

    IF NOT FOUND THEN
        RETURN QUERY SELECT false, 'Target branch is not protected';
        RETURN;
    END IF;

    SELECT count(*)
    INTO actual_approvals
    FROM (
        SELECT DISTINCT ON (r.reviewer_user_id)
            r.reviewer_user_id,
            r.state,
            r.commit_id
        FROM reviews r
        WHERE r.pull_request_id = p_pull_request_id
        ORDER BY r.reviewer_user_id, r.submitted_at DESC, r.review_id DESC
    ) latest
    JOIN commits c
      ON c.commit_id = latest.commit_id
    JOIN repository_users ru
      ON ru.user_id = latest.reviewer_user_id
    WHERE latest.state = 'approved'
      AND c.pull_request_id = p_pull_request_id
      AND c.sequence_no = (
          SELECT max(sequence_no)
          FROM commits
          WHERE pull_request_id = p_pull_request_id
      )
      AND ru.active = true
      AND ru.role_name IN ('reviewer', 'maintainer', 'administrator');

    required_count := protection.required_reviews;

    IF actual_approvals < required_count THEN
        RETURN QUERY SELECT
            false,
            format(
                'Current approvals: %s; required: %s',
                actual_approvals,
                required_count
            );
    END IF;

    FOR missing_check IN
        SELECT psr.check_name
        FROM protected_status_requirements psr
        WHERE psr.protection_id = protection.protection_id
          AND NOT EXISTS (
              SELECT 1
              FROM status_checks sc
              WHERE sc.pull_request_id = p_pull_request_id
                AND sc.check_name = psr.check_name
                AND sc.passed = true
          )
    LOOP
        RETURN QUERY SELECT
            false,
            'Required status check missing or failed: ' || missing_check;
    END LOOP;

    IF protection.require_resolved_conversations
       AND EXISTS (
           SELECT 1
           FROM review_comments rc
           JOIN reviews r
             ON r.review_id = rc.review_id
           WHERE r.pull_request_id = p_pull_request_id
             AND rc.resolved = false
       )
    THEN
        RETURN QUERY SELECT false, 'Unresolved review conversations remain';
    END IF;

    RETURN QUERY SELECT true, 'Pull Request satisfies merge policy';
END;
$$;

-- A trigger function prevents reviews from referencing unrelated commits.
CREATE OR REPLACE FUNCTION validate_review_commit()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM commits c
        WHERE c.commit_id = NEW.commit_id
          AND c.pull_request_id = NEW.pull_request_id
    ) THEN
        RAISE EXCEPTION
            'Review % references commit % outside Pull Request %',
            NEW.review_id,
            NEW.commit_id,
            NEW.pull_request_id;
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_validate_review_commit
BEFORE INSERT OR UPDATE ON reviews
FOR EACH ROW
EXECUTE FUNCTION validate_review_commit();

-- The view exposes the procedural function as a reporting surface.
CREATE OR REPLACE VIEW pull_request_merge_report AS
SELECT
    pr.repository_id,
    pr.pull_request_id,
    pr.number,
    target.branch_name AS target_branch,
    pr.state,
    pr.draft,
    current_approval_count(pr.pull_request_id) AS current_approvals,
    protection.required_reviews,
    e.eligible,
    e.failure_reason
FROM pull_requests pr
JOIN branches target
  ON target.branch_id = pr.target_branch_id
LEFT JOIN branch_protection protection
  ON protection.branch_id = target.branch_id
CROSS JOIN LATERAL evaluate_merge_eligibility(pr.pull_request_id) e;

-- Function invocation as a direct SQL query.
SELECT *
FROM pull_request_merge_report
WHERE number = 101;

SELECT latest_reviewer_state(
    (
        SELECT pull_request_id
        FROM pull_requests
        WHERE number = 101
    ),
    (
        SELECT user_id
        FROM repository_users
        WHERE username = 'bob'
    )
);

-- Demonstrate a stale approval after a new changeset.
INSERT INTO commits(
    pull_request_id,
    sha,
    message,
    author_user_id,
    sequence_no
)
SELECT
    pr.pull_request_id,
    '3333333',
    'Harden duplicate payment handling',
    u.user_id,
    3
FROM pull_requests pr
JOIN repository_users u
    ON u.repository_id = pr.repository_id
   AND u.username = 'alice'
WHERE pr.number = 101;

SELECT *
FROM evaluate_merge_eligibility(
    (
        SELECT pull_request_id
        FROM pull_requests
        WHERE number = 101
    )
);

-- Transactional merge operation.
-- The row lock prevents two concurrent transactions from approving
-- the same Pull Request for merge based on the same policy snapshot.
BEGIN;

SELECT pull_request_id
FROM pull_requests
WHERE number = 101
FOR UPDATE;

DO $$
DECLARE
    v_eligible boolean;
    v_reason text;
BEGIN
    SELECT e.eligible, e.failure_reason
    INTO v_eligible, v_reason
    FROM evaluate_merge_eligibility(
        (
            SELECT pull_request_id
            FROM pull_requests
            WHERE number = 101
        )
    ) e
    LIMIT 1;

    IF NOT v_eligible THEN
        RAISE EXCEPTION 'Merge blocked: %', v_reason;
    END IF;

    UPDATE pull_requests
    SET
        state = 'merged',
        merge_strategy = 'squash',
        merged_at = now()
    WHERE number = 101;
END;
$$;

COMMIT;

SELECT *
FROM pull_request_merge_report
WHERE number = 101;
