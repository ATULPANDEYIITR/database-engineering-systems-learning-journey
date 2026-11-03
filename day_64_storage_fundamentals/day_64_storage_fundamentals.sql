DROP SCHEMA IF EXISTS repository_governance CASCADE;
CREATE SCHEMA repository_governance;

SET search_path TO repository_governance;

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
    repository_id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    owner_name TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (owner_name, name)
);

CREATE TABLE users (
    user_id BIGSERIAL PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE repository_members (
    repository_id BIGINT NOT NULL REFERENCES repositories(repository_id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    repository_role TEXT NOT NULL CHECK (
        repository_role IN ('admin', 'maintainer', 'developer', 'reviewer')
    ),
    PRIMARY KEY (repository_id, user_id)
);

CREATE TABLE branches (
    branch_id BIGSERIAL PRIMARY KEY,
    repository_id BIGINT NOT NULL REFERENCES repositories(repository_id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    protected BOOLEAN NOT NULL DEFAULT FALSE,
    head_commit_id BIGINT,
    UNIQUE (repository_id, name)
);

CREATE TABLE commits (
    commit_id BIGSERIAL PRIMARY KEY,
    repository_id BIGINT NOT NULL REFERENCES repositories(repository_id) ON DELETE CASCADE,
    sha TEXT NOT NULL,
    parent_commit_id BIGINT REFERENCES commits(commit_id),
    author_id BIGINT NOT NULL REFERENCES users(user_id),
    message TEXT NOT NULL CHECK (length(trim(message)) > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (repository_id, sha)
);

ALTER TABLE branches
ADD CONSTRAINT branches_head_fk
FOREIGN KEY (head_commit_id) REFERENCES commits(commit_id);

CREATE TABLE pull_requests (
    pull_request_id BIGSERIAL PRIMARY KEY,
    repository_id BIGINT NOT NULL REFERENCES repositories(repository_id) ON DELETE CASCADE,
    number INTEGER NOT NULL,
    source_branch_id BIGINT NOT NULL REFERENCES branches(branch_id),
    target_branch_id BIGINT NOT NULL REFERENCES branches(branch_id),
    author_id BIGINT NOT NULL REFERENCES users(user_id),
    title TEXT NOT NULL CHECK (length(trim(title)) > 0),
    state pull_request_state NOT NULL DEFAULT 'open',
    draft BOOLEAN NOT NULL DEFAULT FALSE,
    base_head_commit_id BIGINT REFERENCES commits(commit_id),
    merge_strategy merge_strategy NOT NULL DEFAULT 'squash',
    unresolved_conversations INTEGER NOT NULL DEFAULT 0 CHECK (
        unresolved_conversations >= 0
    ),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    merged_at TIMESTAMPTZ,
    UNIQUE (repository_id, number),
    CHECK (source_branch_id <> target_branch_id)
);

CREATE TABLE pull_request_commits (
    pull_request_id BIGINT NOT NULL
        REFERENCES pull_requests(pull_request_id) ON DELETE CASCADE,
    commit_id BIGINT NOT NULL REFERENCES commits(commit_id),
    position INTEGER NOT NULL CHECK (position > 0),
    PRIMARY KEY (pull_request_id, commit_id),
    UNIQUE (pull_request_id, position)
);

CREATE TABLE reviews (
    review_id BIGSERIAL PRIMARY KEY,
    pull_request_id BIGINT NOT NULL
        REFERENCES pull_requests(pull_request_id) ON DELETE CASCADE,
    reviewer_id BIGINT NOT NULL REFERENCES users(user_id),
    state review_state NOT NULL,
    reviewed_commit_id BIGINT NOT NULL REFERENCES commits(commit_id),
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    dismissed_at TIMESTAMPTZ
);

CREATE TABLE review_comments (
    comment_id BIGSERIAL PRIMARY KEY,
    review_id BIGINT NOT NULL REFERENCES reviews(review_id) ON DELETE CASCADE,
    author_id BIGINT NOT NULL REFERENCES users(user_id),
    body TEXT NOT NULL CHECK (length(trim(body)) > 0),
    resolved BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE status_checks (
    status_check_id BIGSERIAL PRIMARY KEY,
    pull_request_id BIGINT NOT NULL
        REFERENCES pull_requests(pull_request_id) ON DELETE CASCADE,
    check_name TEXT NOT NULL,
    passed BOOLEAN NOT NULL,
    required BOOLEAN NOT NULL DEFAULT TRUE,
    message TEXT,
    completed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (pull_request_id, check_name)
);

CREATE TABLE branch_protection_policies (
    policy_id BIGSERIAL PRIMARY KEY,
    branch_id BIGINT NOT NULL UNIQUE REFERENCES branches(branch_id) ON DELETE CASCADE,
    required_reviews INTEGER NOT NULL DEFAULT 1 CHECK (required_reviews >= 0),
    restrict_direct_push BOOLEAN NOT NULL DEFAULT TRUE,
    restrict_force_push BOOLEAN NOT NULL DEFAULT TRUE,
    require_conversation_resolution BOOLEAN NOT NULL DEFAULT TRUE,
    require_linear_history BOOLEAN NOT NULL DEFAULT FALSE,
    allow_admin_bypass BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE required_status_checks (
    policy_id BIGINT NOT NULL
        REFERENCES branch_protection_policies(policy_id) ON DELETE CASCADE,
    check_name TEXT NOT NULL,
    PRIMARY KEY (policy_id, check_name)
);

CREATE TABLE merge_eligibility_audit (
    audit_id BIGSERIAL PRIMARY KEY,
    pull_request_id BIGINT NOT NULL
        REFERENCES pull_requests(pull_request_id) ON DELETE CASCADE,
    evaluated_by BIGINT NOT NULL REFERENCES users(user_id),
    eligible BOOLEAN NOT NULL,
    reasons TEXT[] NOT NULL DEFAULT '{}',
    evaluated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_commits_repository_sha
ON commits(repository_id, sha);

CREATE INDEX idx_pull_requests_target_state
ON pull_requests(target_branch_id, state);

CREATE INDEX idx_reviews_pr_state
ON reviews(pull_request_id, state);

CREATE INDEX idx_comments_review_resolved
ON review_comments(review_id, resolved);

CREATE INDEX idx_status_checks_pr_name
ON status_checks(pull_request_id, check_name);

CREATE INDEX idx_pr_commits_position
ON pull_request_commits(pull_request_id, position);

INSERT INTO users (username) VALUES
('platform-admin'),
('developer-1'),
('reviewer-1'),
('reviewer-2'),
('reviewer-3');

INSERT INTO repositories (name, owner_name)
VALUES ('storage-platform', 'platform-admin');

INSERT INTO repository_members (repository_id, user_id, repository_role)
SELECT r.repository_id, u.user_id,
       CASE u.username
           WHEN 'platform-admin' THEN 'admin'
           WHEN 'developer-1' THEN 'developer'
           ELSE 'reviewer'
       END
FROM repositories r
CROSS JOIN users u
WHERE r.name = 'storage-platform'
  AND r.owner_name = 'platform-admin';

INSERT INTO branches (repository_id, name, protected)
SELECT repository_id, 'main', TRUE
FROM repositories
WHERE name = 'storage-platform';

INSERT INTO branches (repository_id, name, protected)
SELECT repository_id, 'feature/storage-pages', FALSE
FROM repositories
WHERE name = 'storage-platform';

INSERT INTO commits (repository_id, sha, author_id, message)
SELECT r.repository_id, 'a001', u.user_id, 'Initialize repository'
FROM repositories r
JOIN users u ON u.username = 'developer-1'
WHERE r.name = 'storage-platform';

INSERT INTO commits (
    repository_id,
    sha,
    parent_commit_id,
    author_id,
    message
)
SELECT r.repository_id,
       'b101',
       c.commit_id,
       u.user_id,
       'Implement page allocation'
FROM repositories r
JOIN commits c
  ON c.repository_id = r.repository_id
 AND c.sha = 'a001'
JOIN users u ON u.username = 'developer-1'
WHERE r.name = 'storage-platform';

INSERT INTO commits (
    repository_id,
    sha,
    parent_commit_id,
    author_id,
    message
)
SELECT r.repository_id,
       'b102',
       c.commit_id,
       u.user_id,
       'Validate physical storage boundaries'
FROM repositories r
JOIN commits c
  ON c.repository_id = r.repository_id
 AND c.sha = 'b101'
JOIN users u ON u.username = 'developer-1'
WHERE r.name = 'storage-platform';

UPDATE branches b
SET head_commit_id = c.commit_id
FROM commits c
JOIN repositories r ON r.repository_id = c.repository_id
WHERE b.repository_id = r.repository_id
  AND b.name = 'main'
  AND c.sha = 'a001';

UPDATE branches b
SET head_commit_id = c.commit_id
FROM commits c
JOIN repositories r ON r.repository_id = c.repository_id
WHERE b.repository_id = r.repository_id
  AND b.name = 'feature/storage-pages'
  AND c.sha = 'b102';

INSERT INTO pull_requests (
    repository_id,
    number,
    source_branch_id,
    target_branch_id,
    author_id,
    title,
    state,
    draft,
    base_head_commit_id,
    merge_strategy
)
SELECT r.repository_id,
       1,
       source.branch_id,
       target.branch_id,
       author.user_id,
       'Implement physical storage model',
       'open',
       FALSE,
       target.head_commit_id,
       'squash'
FROM repositories r
JOIN branches source
  ON source.repository_id = r.repository_id
 AND source.name = 'feature/storage-pages'
JOIN branches target
  ON target.repository_id = r.repository_id
 AND target.name = 'main'
JOIN users author ON author.username = 'developer-1'
WHERE r.name = 'storage-platform';

INSERT INTO pull_request_commits (pull_request_id, commit_id, position)
SELECT pr.pull_request_id, c.commit_id,
       CASE c.sha WHEN 'b101' THEN 1 WHEN 'b102' THEN 2 END
FROM pull_requests pr
JOIN commits c
  ON c.repository_id = pr.repository_id
WHERE pr.number = 1
  AND c.sha IN ('b101', 'b102');

INSERT INTO reviews (
    pull_request_id,
    reviewer_id,
    state,
    reviewed_commit_id
)
SELECT pr.pull_request_id,
       u.user_id,
       'approved',
       c.commit_id
FROM pull_requests pr
JOIN users u ON u.username = 'reviewer-1'
JOIN commits c
  ON c.repository_id = pr.repository_id
 AND c.sha = 'b102'
WHERE pr.number = 1;

INSERT INTO reviews (
    pull_request_id,
    reviewer_id,
    state,
    reviewed_commit_id
)
SELECT pr.pull_request_id,
       u.user_id,
       'approved',
       c.commit_id
FROM pull_requests pr
JOIN users u ON u.username = 'reviewer-2'
JOIN commits c
  ON c.repository_id = pr.repository_id
 AND c.sha = 'b102'
WHERE pr.number = 1;

INSERT INTO review_comments (
    review_id,
    author_id,
    body,
    resolved
)
SELECT rv.review_id,
       u.user_id,
       'Allocation logic is bounded and validated.',
       TRUE
FROM reviews rv
JOIN users u ON u.username = 'reviewer-1'
JOIN pull_requests pr ON pr.pull_request_id = rv.pull_request_id
WHERE pr.number = 1
  AND rv.reviewer_id = u.user_id;

INSERT INTO status_checks (
    pull_request_id,
    check_name,
    passed,
    required,
    message
)
SELECT pull_request_id,
       'unit-tests',
       TRUE,
       TRUE,
       'All tests passed'
FROM pull_requests
WHERE number = 1;

INSERT INTO status_checks (
    pull_request_id,
    check_name,
    passed,
    required,
    message
)
SELECT pull_request_id,
       'storage-integrity',
       TRUE,
       TRUE,
       'Physical storage boundaries validated'
FROM pull_requests
WHERE number = 1;

INSERT INTO branch_protection_policies (
    branch_id,
    required_reviews,
    restrict_direct_push,
    restrict_force_push,
    require_conversation_resolution,
    require_linear_history,
    allow_admin_bypass
)
SELECT branch_id,
       2,
       TRUE,
       TRUE,
       TRUE,
       FALSE,
       FALSE
FROM branches
WHERE name = 'main';

INSERT INTO required_status_checks (policy_id, check_name)
SELECT policy_id, 'unit-tests'
FROM branch_protection_policies;

INSERT INTO required_status_checks (policy_id, check_name)
SELECT policy_id, 'storage-integrity'
FROM branch_protection_policies;

CREATE OR REPLACE FUNCTION evaluate_merge_eligibility(
    p_pull_request_id BIGINT,
    p_evaluator BIGINT
)
RETURNS TABLE (
    eligible BOOLEAN,
    reasons TEXT[]
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_pr RECORD;
    v_policy RECORD;
    v_approval_count INTEGER;
    v_required_check_count INTEGER;
    v_failed_check_count INTEGER;
    v_unresolved INTEGER;
    v_reasons TEXT[] := ARRAY[]::TEXT[];
BEGIN
    SELECT pr.*,
           target.head_commit_id AS target_head,
           source.head_commit_id AS source_head
    INTO v_pr
    FROM pull_requests pr
    JOIN branches target ON target.branch_id = pr.target_branch_id
    JOIN branches source ON source.branch_id = pr.source_branch_id
    WHERE pr.pull_request_id = p_pull_request_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Unknown pull request %', p_pull_request_id;
    END IF;

    IF v_pr.state <> 'open' THEN
        v_reasons := array_append(v_reasons, 'Pull request is not open.');
    END IF;

    IF v_pr.draft THEN
        v_reasons := array_append(v_reasons, 'Pull request is still a draft.');
    END IF;

    IF v_pr.base_head_commit_id IS DISTINCT FROM v_pr.target_head THEN
        v_reasons := array_append(
            v_reasons,
            'Target branch changed after pull request creation.'
        );
    END IF;

    SELECT bp.*
    INTO v_policy
    FROM branch_protection_policies bp
    WHERE bp.branch_id = v_pr.target_branch_id;

    IF NOT FOUND THEN
        eligible := cardinality(v_reasons) = 0;
        reasons := v_reasons;
        RETURN NEXT;
        RETURN;
    END IF;

    SELECT count(DISTINCT reviewer_id)
    INTO v_approval_count
    FROM reviews
    WHERE pull_request_id = p_pull_request_id
      AND state = 'approved'
      AND dismissed_at IS NULL
      AND reviewed_commit_id IN (v_pr.source_head, v_pr.target_head);

    IF v_approval_count < v_policy.required_reviews THEN
        v_reasons := array_append(
            v_reasons,
            format(
                'Required approvals: %s; current approvals: %s.',
                v_policy.required_reviews,
                v_approval_count
            )
        );
    END IF;

    IF EXISTS (
        SELECT 1
        FROM reviews
        WHERE pull_request_id = p_pull_request_id
          AND state = 'changes_requested'
          AND dismissed_at IS NULL
          AND reviewed_commit_id IN (v_pr.source_head, v_pr.target_head)
    ) THEN
        v_reasons := array_append(
            v_reasons,
            'An active reviewer requested changes.'
        );
    END IF;

    SELECT count(*)
    INTO v_required_check_count
    FROM required_status_checks
    WHERE policy_id = v_policy.policy_id;

    SELECT count(*)
    INTO v_failed_check_count
    FROM required_status_checks rsc
    LEFT JOIN status_checks sc
      ON sc.pull_request_id = p_pull_request_id
     AND sc.check_name = rsc.check_name
    WHERE rsc.policy_id = v_policy.policy_id
      AND (sc.status_check_id IS NULL OR sc.passed = FALSE);

    IF v_failed_check_count > 0 THEN
        v_reasons := array_append(
            v_reasons,
            format(
                '%s required status check(s) are missing or failed.',
                v_failed_check_count
            )
        );
    END IF;

    SELECT unresolved_conversations
    INTO v_unresolved
    FROM pull_requests
    WHERE pull_request_id = p_pull_request_id;

    IF v_policy.require_conversation_resolution
       AND v_unresolved > 0 THEN
        v_reasons := array_append(
            v_reasons,
            'Unresolved review conversations remain.'
        );
    END IF;

    eligible := cardinality(v_reasons) = 0;
    reasons := v_reasons;

    INSERT INTO merge_eligibility_audit (
        pull_request_id,
        evaluated_by,
        eligible,
        reasons
    )
    VALUES (
        p_pull_request_id,
        p_evaluator,
        eligible,
        v_reasons
    );

    RETURN NEXT;
END;
$$;

CREATE OR REPLACE FUNCTION enforce_branch_protection()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_branch branches%ROWTYPE;
    v_pr pull_requests%ROWTYPE;
BEGIN
    SELECT *
    INTO v_branch
    FROM branches
    WHERE branch_id = NEW.target_branch_id;

    IF v_branch.protected THEN
        SELECT *
        INTO v_pr
        FROM pull_requests
        WHERE pull_request_id = NEW.pull_request_id;

        IF NEW.state = 'merged' AND v_pr.state <> 'open' THEN
            RAISE EXCEPTION
                'Only an open pull request may transition to merged.';
        END IF;
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_branch_protection_transition
BEFORE UPDATE OF state ON pull_requests
FOR EACH ROW
EXECUTE FUNCTION enforce_branch_protection();

CREATE VIEW merge_readiness AS
SELECT
    pr.pull_request_id,
    pr.number,
    r.name AS repository,
    source.name AS source_branch,
    target.name AS target_branch,
    pr.state,
    pr.draft,
    pr.unresolved_conversations,
    bp.required_reviews,
    count(DISTINCT rv.reviewer_id)
        FILTER (
            WHERE rv.state = 'approved'
              AND rv.dismissed_at IS NULL
              AND rv.reviewed_commit_id IN (
                  source.head_commit_id,
                  target.head_commit_id
              )
        ) AS valid_approvals,
    count(DISTINCT sc.status_check_id)
        FILTER (WHERE sc.passed) AS passed_checks
FROM pull_requests pr
JOIN repositories r ON r.repository_id = pr.repository_id
JOIN branches source ON source.branch_id = pr.source_branch_id
JOIN branches target ON target.branch_id = pr.target_branch_id
LEFT JOIN branch_protection_policies bp
       ON bp.branch_id = target.branch_id
LEFT JOIN reviews rv
       ON rv.pull_request_id = pr.pull_request_id
LEFT JOIN status_checks sc
       ON sc.pull_request_id = pr.pull_request_id
GROUP BY
    pr.pull_request_id,
    pr.number,
    r.name,
    source.name,
    target.name,
    pr.state,
    pr.draft,
    pr.unresolved_conversations,
    bp.required_reviews;

-- Retrieval: pull request and branch state.
SELECT
    pr.number,
    pr.title,
    pr.state,
    source.name AS source_branch,
    target.name AS target_branch,
    source.head_commit_id AS source_head,
    target.head_commit_id AS target_head
FROM pull_requests pr
JOIN branches source ON source.branch_id = pr.source_branch_id
JOIN branches target ON target.branch_id = pr.target_branch_id
WHERE pr.number = 1;

-- Review reporting.
SELECT
    u.username AS reviewer,
    rv.state,
    c.sha AS reviewed_commit,
    count(rc.comment_id) AS comment_count
FROM reviews rv
JOIN users u ON u.user_id = rv.reviewer_id
JOIN commits c ON c.commit_id = rv.reviewed_commit_id
LEFT JOIN review_comments rc ON rc.review_id = rv.review_id
WHERE rv.pull_request_id = (
    SELECT pull_request_id
    FROM pull_requests
    WHERE number = 1
)
GROUP BY u.username, rv.state, c.sha
ORDER BY u.username;

-- Status-check evaluation.
SELECT
    sc.check_name,
    sc.passed,
    sc.required,
    sc.message
FROM status_checks sc
JOIN pull_requests pr
  ON pr.pull_request_id = sc.pull_request_id
WHERE pr.number = 1
ORDER BY sc.check_name;

-- Aggregation: repositories and protected branches.
SELECT
    r.name,
    count(b.branch_id) AS branch_count,
    count(*) FILTER (WHERE b.protected) AS protected_branch_count
FROM repositories r
LEFT JOIN branches b ON b.repository_id = r.repository_id
GROUP BY r.name;

-- CTE: identify required checks that are not passing.
WITH required AS (
    SELECT
        pr.pull_request_id,
        rsc.check_name
    FROM pull_requests pr
    JOIN branch_protection_policies bp
      ON bp.branch_id = pr.target_branch_id
    JOIN required_status_checks rsc
      ON rsc.policy_id = bp.policy_id
    WHERE pr.number = 1
),
check_state AS (
    SELECT
        required.pull_request_id,
        required.check_name,
        COALESCE(sc.passed, FALSE) AS passed
    FROM required
    LEFT JOIN status_checks sc
      ON sc.pull_request_id = required.pull_request_id
     AND sc.check_name = required.check_name
)
SELECT *
FROM check_state
WHERE passed = FALSE;

-- Transactional merge eligibility evaluation.
BEGIN;

SELECT *
FROM evaluate_merge_eligibility(
    (
        SELECT pull_request_id
        FROM pull_requests
        WHERE number = 1
        FOR UPDATE
    ),
    (
        SELECT user_id
        FROM users
        WHERE username = 'platform-admin'
    )
);

COMMIT;
