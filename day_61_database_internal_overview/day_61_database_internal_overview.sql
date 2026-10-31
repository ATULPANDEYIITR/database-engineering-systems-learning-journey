DROP SCHEMA IF EXISTS database_internals CASCADE;

CREATE SCHEMA database_internals;

SET search_path TO database_internals, public;

CREATE TYPE branch_state AS ENUM (
    'ACTIVE',
    'READ_ONLY',
    'ARCHIVED'
);

CREATE TYPE page_type AS ENUM (
    'HEAP',
    'INDEX'
);

CREATE TYPE transaction_state AS ENUM (
    'ACTIVE',
    'COMMITTED',
    'ROLLED_BACK'
);

CREATE TYPE review_access AS ENUM (
    'SEQUENTIAL',
    'INDEXED'
);

CREATE TABLE repositories (
    repository_id BIGSERIAL PRIMARY KEY,
    repository_name TEXT NOT NULL UNIQUE,
    owner_name TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (length(trim(repository_name)) BETWEEN 1 AND 120),
    CHECK (length(trim(owner_name)) BETWEEN 1 AND 120)
);

CREATE TABLE branches (
    branch_id BIGSERIAL PRIMARY KEY,
    repository_id BIGINT NOT NULL
        REFERENCES repositories(repository_id)
        ON DELETE CASCADE,
    branch_name TEXT NOT NULL,
    state branch_state NOT NULL DEFAULT 'ACTIVE',
    head_commit_id BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (repository_id, branch_name),
    CHECK (length(trim(branch_name)) BETWEEN 1 AND 255)
);

CREATE TABLE commits (
    commit_id BIGSERIAL PRIMARY KEY,
    repository_id BIGINT NOT NULL
        REFERENCES repositories(repository_id)
        ON DELETE CASCADE,
    commit_hash TEXT NOT NULL,
    parent_commit_id BIGINT
        REFERENCES commits(commit_id),
    author_name TEXT NOT NULL,
    message TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (repository_id, commit_hash),
    CHECK (commit_hash ~ '^[0-9a-f]{40,64}$'),
    CHECK (length(trim(author_name)) BETWEEN 1 AND 120),
    CHECK (length(trim(message)) BETWEEN 1 AND 5000)
);

ALTER TABLE branches
    ADD CONSTRAINT branches_head_commit_fk
    FOREIGN KEY (head_commit_id)
    REFERENCES commits(commit_id);

CREATE TABLE database_pages (
    page_id BIGSERIAL PRIMARY KEY,
    repository_id BIGINT NOT NULL
        REFERENCES repositories(repository_id)
        ON DELETE CASCADE,
    page_type page_type NOT NULL,
    page_number INTEGER NOT NULL,
    page_lsn BIGINT NOT NULL DEFAULT 0,
    is_dirty BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (repository_id, page_number),
    CHECK (page_number >= 0),
    CHECK (page_lsn >= 0)
);

CREATE TABLE repository_rows (
    row_id BIGSERIAL PRIMARY KEY,
    repository_id BIGINT NOT NULL
        REFERENCES repositories(repository_id)
        ON DELETE CASCADE,
    page_id BIGINT NOT NULL
        REFERENCES database_pages(page_id)
        ON DELETE RESTRICT,
    customer_id BIGINT NOT NULL,
    customer_name TEXT NOT NULL,
    balance NUMERIC(15,2) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (repository_id, row_id),
    CHECK (customer_id > 0),
    CHECK (length(trim(customer_name)) BETWEEN 1 AND 120),
    CHECK (balance BETWEEN -10000000 AND 10000000)
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
    source_commit_id BIGINT NOT NULL
        REFERENCES commits(commit_id),
    title TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'OPEN',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    closed_at TIMESTAMPTZ,
    CHECK (state IN ('DRAFT', 'OPEN', 'MERGED', 'CLOSED')),
    CHECK (source_branch_id <> target_branch_id),
    CHECK (length(trim(title)) BETWEEN 1 AND 500)
);

CREATE TABLE engine_transactions (
    transaction_id BIGSERIAL PRIMARY KEY,
    repository_id BIGINT NOT NULL
        REFERENCES repositories(repository_id)
        ON DELETE CASCADE,
    state transaction_state NOT NULL DEFAULT 'ACTIVE',
    started_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMPTZ,
    CHECK (
        (state = 'ACTIVE' AND finished_at IS NULL)
        OR
        (state <> 'ACTIVE' AND finished_at IS NOT NULL)
    )
);

CREATE TABLE write_ahead_log (
    lsn BIGSERIAL PRIMARY KEY,
    transaction_id BIGINT NOT NULL
        REFERENCES engine_transactions(transaction_id)
        ON DELETE RESTRICT,
    page_id BIGINT NOT NULL
        REFERENCES database_pages(page_id)
        ON DELETE RESTRICT,
    operation TEXT NOT NULL,
    row_id BIGINT,
    old_balance NUMERIC(15,2),
    new_balance NUMERIC(15,2),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (operation IN ('INSERT', 'UPDATE', 'DELETE', 'PAGE_FLUSH')),
    CHECK (
        operation <> 'UPDATE'
        OR (row_id IS NOT NULL AND old_balance IS NOT NULL
            AND new_balance IS NOT NULL)
    )
);

CREATE TABLE buffer_frames (
    frame_id BIGSERIAL PRIMARY KEY,
    page_id BIGINT NOT NULL UNIQUE
        REFERENCES database_pages(page_id)
        ON DELETE CASCADE,
    pin_count INTEGER NOT NULL DEFAULT 0,
    is_dirty BOOLEAN NOT NULL DEFAULT FALSE,
    last_accessed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (pin_count >= 0)
);

CREATE TABLE index_entries (
    index_entry_id BIGSERIAL PRIMARY KEY,
    page_id BIGINT NOT NULL
        REFERENCES database_pages(page_id)
        ON DELETE CASCADE,
    customer_id BIGINT NOT NULL,
    row_id BIGINT NOT NULL,
    UNIQUE (page_id, customer_id, row_id),
    CHECK (customer_id > 0),
    CHECK (row_id > 0)
);

CREATE TABLE status_checks (
    status_check_id BIGSERIAL PRIMARY KEY,
    pull_request_id BIGINT NOT NULL
        REFERENCES pull_requests(pull_request_id)
        ON DELETE CASCADE,
    check_name TEXT NOT NULL,
    status TEXT NOT NULL,
    completed_at TIMESTAMPTZ,
    UNIQUE (pull_request_id, check_name),
    CHECK (status IN ('PENDING', 'PASS', 'FAIL', 'ERROR')),
    CHECK (length(trim(check_name)) BETWEEN 1 AND 200)
);

CREATE INDEX idx_repository_rows_customer
    ON repository_rows(repository_id, customer_id);

CREATE INDEX idx_repository_rows_page
    ON repository_rows(page_id);

CREATE INDEX idx_wal_transaction
    ON write_ahead_log(transaction_id, lsn);

CREATE INDEX idx_buffer_lru
    ON buffer_frames(last_accessed_at);

CREATE INDEX idx_status_checks_pr_status
    ON status_checks(pull_request_id, status);

CREATE INDEX idx_commits_repository_created
    ON commits(repository_id, created_at DESC);

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at := CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$;

CREATE TRIGGER repository_rows_updated_at
BEFORE UPDATE ON repository_rows
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

CREATE OR REPLACE FUNCTION validate_branch_head()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    commit_repository BIGINT;
BEGIN
    IF NEW.head_commit_id IS NULL THEN
        RETURN NEW;
    END IF;

    SELECT repository_id
    INTO commit_repository
    FROM commits
    WHERE commit_id = NEW.head_commit_id;

    IF commit_repository IS NULL THEN
        RAISE EXCEPTION
            'head commit % does not exist',
            NEW.head_commit_id;
    END IF;

    IF commit_repository <> NEW.repository_id THEN
        RAISE EXCEPTION
            'branch repository and commit repository differ';
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER branches_validate_head
BEFORE INSERT OR UPDATE ON branches
FOR EACH ROW
EXECUTE FUNCTION validate_branch_head();

CREATE OR REPLACE FUNCTION prevent_archived_branch_changes()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF OLD.state = 'ARCHIVED'
       AND (
           NEW.state <> OLD.state
           OR NEW.head_commit_id IS DISTINCT FROM OLD.head_commit_id
       )
    THEN
        RAISE EXCEPTION
            'archived branch % cannot change',
            OLD.branch_name;
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER branches_archive_guard
BEFORE UPDATE ON branches
FOR EACH ROW
EXECUTE FUNCTION prevent_archived_branch_changes();

CREATE OR REPLACE FUNCTION refresh_page_dirty_state()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    UPDATE database_pages
    SET is_dirty = TRUE,
        page_lsn = GREATEST(page_lsn, COALESCE(NEW.page_lsn, 0))
    WHERE page_id = NEW.page_id;

    RETURN NEW;
END;
$$;

CREATE TRIGGER repository_row_page_dirty
AFTER INSERT OR UPDATE ON repository_rows
FOR EACH ROW
EXECUTE FUNCTION refresh_page_dirty_state();

CREATE OR REPLACE FUNCTION start_engine_transaction(
    p_repository_id BIGINT
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    v_transaction_id BIGINT;
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM repositories
        WHERE repository_id = p_repository_id
    ) THEN
        RAISE EXCEPTION
            'repository % does not exist',
            p_repository_id;
    END IF;

    INSERT INTO engine_transactions(repository_id)
    VALUES (p_repository_id)
    RETURNING transaction_id
    INTO v_transaction_id;

    RETURN v_transaction_id;
END;
$$;

CREATE OR REPLACE PROCEDURE finish_engine_transaction(
    p_transaction_id BIGINT,
    p_state transaction_state
)
LANGUAGE plpgsql
AS $$
BEGIN
    IF p_state = 'ACTIVE' THEN
        RAISE EXCEPTION
            'finish state cannot remain ACTIVE';
    END IF;

    UPDATE engine_transactions
    SET state = p_state,
        finished_at = CURRENT_TIMESTAMP
    WHERE transaction_id = p_transaction_id
      AND state = 'ACTIVE';

    IF NOT FOUND THEN
        RAISE EXCEPTION
            'active transaction % not found',
            p_transaction_id;
    END IF;
END;
$$;

CREATE OR REPLACE FUNCTION update_customer_balance(
    p_transaction_id BIGINT,
    p_row_id BIGINT,
    p_new_balance NUMERIC(15,2)
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    v_page_id BIGINT;
    v_old_balance NUMERIC(15,2);
    v_lsn BIGINT;
BEGIN
    IF p_new_balance NOT BETWEEN -10000000 AND 10000000 THEN
        RAISE EXCEPTION 'balance outside supported range';
    END IF;

    SELECT page_id, balance
    INTO v_page_id, v_old_balance
    FROM repository_rows
    WHERE row_id = p_row_id
    FOR UPDATE;

    IF v_page_id IS NULL THEN
        RAISE EXCEPTION
            'row % does not exist',
            p_row_id;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM engine_transactions
        WHERE transaction_id = p_transaction_id
          AND state = 'ACTIVE'
    ) THEN
        RAISE EXCEPTION
            'transaction % is not active',
            p_transaction_id;
    END IF;

    INSERT INTO write_ahead_log(
        transaction_id,
        page_id,
        operation,
        row_id,
        old_balance,
        new_balance
    )
    VALUES (
        p_transaction_id,
        v_page_id,
        'UPDATE',
        p_row_id,
        v_old_balance,
        p_new_balance
    )
    RETURNING lsn INTO v_lsn;

    UPDATE repository_rows
    SET balance = p_new_balance
    WHERE row_id = p_row_id;

    UPDATE database_pages
    SET is_dirty = TRUE,
        page_lsn = v_lsn
    WHERE page_id = v_page_id;

    RETURN v_lsn;
END;
$$;

CREATE OR REPLACE VIEW repository_storage_report AS
SELECT
    r.repository_id,
    r.repository_name,
    COUNT(DISTINCT p.page_id) AS page_count,
    COUNT(rr.row_id) AS row_count,
    COUNT(*) FILTER (WHERE p.is_dirty) AS dirty_page_count,
    COALESCE(SUM(rr.balance), 0) AS total_balance
FROM repositories r
LEFT JOIN database_pages p
    ON p.repository_id = r.repository_id
LEFT JOIN repository_rows rr
    ON rr.page_id = p.page_id
GROUP BY
    r.repository_id,
    r.repository_name;

CREATE OR REPLACE VIEW pull_request_engine_report AS
SELECT
    pr.pull_request_id,
    r.repository_name,
    sb.branch_name AS source_branch,
    tb.branch_name AS target_branch,
    pr.state,
    COUNT(DISTINCT sc.status_check_id) AS status_checks,
    COUNT(DISTINCT sc.status_check_id)
        FILTER (WHERE sc.status = 'PASS') AS passing_checks,
    COUNT(DISTINCT sc.status_check_id)
        FILTER (WHERE sc.status IN ('FAIL', 'ERROR'))
        AS failing_checks
FROM pull_requests pr
JOIN repositories r
    ON r.repository_id = pr.repository_id
JOIN branches sb
    ON sb.branch_id = pr.source_branch_id
JOIN branches tb
    ON tb.branch_id = pr.target_branch_id
LEFT JOIN status_checks sc
    ON sc.pull_request_id = pr.pull_request_id
GROUP BY
    pr.pull_request_id,
    r.repository_name,
    sb.branch_name,
    tb.branch_name,
    pr.state;

INSERT INTO repositories (
    repository_name,
    owner_name
)
VALUES (
    'database-engine-lab',
    'platform-engineering'
);

INSERT INTO commits (
    repository_id,
    commit_hash,
    author_name,
    message
)
SELECT
    repository_id,
    repeat('a', 40),
    'Asha Rao',
    'initialize storage engine'
FROM repositories
WHERE repository_name = 'database-engine-lab';

INSERT INTO branches (
    repository_id,
    branch_name,
    state,
    head_commit_id
)
SELECT
    r.repository_id,
    'main',
    'ACTIVE',
    c.commit_id
FROM repositories r
JOIN commits c
    ON c.repository_id = r.repository_id
WHERE r.repository_name = 'database-engine-lab'
  AND c.commit_hash = repeat('a', 40);

INSERT INTO database_pages (
    repository_id,
    page_type,
    page_number
)
SELECT
    repository_id,
    'HEAP',
    0
FROM repositories
WHERE repository_name = 'database-engine-lab';

INSERT INTO database_pages (
    repository_id,
    page_type,
    page_number
)
SELECT
    repository_id,
    'HEAP',
    1
FROM repositories
WHERE repository_name = 'database-engine-lab';

INSERT INTO repository_rows (
    repository_id,
    page_id,
    customer_id,
    customer_name,
    balance
)
SELECT
    r.repository_id,
    p.page_id,
    data.customer_id,
    data.customer_name,
    data.balance
FROM repositories r
JOIN database_pages p
    ON p.repository_id = r.repository_id
   AND p.page_number = 0
CROSS JOIN (
    VALUES
        (101, 'Asha', 1250.00::NUMERIC),
        (102, 'Ravi', 840.00::NUMERIC),
        (101, 'Meera', 2190.00::NUMERIC),
        (103, 'Kabir', 450.00::NUMERIC)
) AS data(customer_id, customer_name, balance)
WHERE r.repository_name = 'database-engine-lab';

INSERT INTO repository_rows (
    repository_id,
    page_id,
    customer_id,
    customer_name,
    balance
)
SELECT
    r.repository_id,
    p.page_id,
    data.customer_id,
    data.customer_name,
    data.balance
FROM repositories r
JOIN database_pages p
    ON p.repository_id = r.repository_id
   AND p.page_number = 1
CROSS JOIN (
    VALUES
        (104, 'Nisha', 3300.00::NUMERIC),
        (102, 'Arjun', 910.00::NUMERIC),
        (105, 'Isha', 720.00::NUMERIC),
        (101, 'Dev', 1500.00::NUMERIC)
) AS data(customer_id, customer_name, balance)
WHERE r.repository_name = 'database-engine-lab';

INSERT INTO index_entries (
    page_id,
    customer_id,
    row_id
)
SELECT
    rr.page_id,
    rr.customer_id,
    rr.row_id
FROM repository_rows rr;

INSERT INTO pull_requests (
    repository_id,
    source_branch_id,
    target_branch_id,
    source_commit_id,
    title
)
SELECT
    r.repository_id,
    source_branch.branch_id,
    target_branch.branch_id,
    c.commit_id,
    'Optimize indexed customer lookup'
FROM repositories r
JOIN branches source_branch
    ON source_branch.repository_id = r.repository_id
   AND source_branch.branch_name = 'main'
JOIN branches target_branch
    ON target_branch.repository_id = r.repository_id
   AND target_branch.branch_name = 'main'
JOIN commits c
    ON c.repository_id = r.repository_id
WHERE FALSE;

-- The relational model intentionally prevents a pull request from using
-- identical source and target branches. A real application would create
-- a separate feature branch before inserting this workflow row.

INSERT INTO engine_transactions (repository_id)
SELECT repository_id
FROM repositories
WHERE repository_name = 'database-engine-lab';

WITH active_transaction AS (
    SELECT transaction_id
    FROM engine_transactions
    WHERE repository_id = (
        SELECT repository_id
        FROM repositories
        WHERE repository_name = 'database-engine-lab'
    )
    AND state = 'ACTIVE'
    ORDER BY transaction_id DESC
    LIMIT 1
),
target_row AS (
    SELECT row_id
    FROM repository_rows
    WHERE customer_name = 'Asha'
    ORDER BY row_id
    LIMIT 1
)
SELECT update_customer_balance(
    active_transaction.transaction_id,
    target_row.row_id,
    1750.00
)
FROM active_transaction
CROSS JOIN target_row;

UPDATE engine_transactions
SET state = 'COMMITTED',
    finished_at = CURRENT_TIMESTAMP
WHERE transaction_id = (
    SELECT MAX(transaction_id)
    FROM engine_transactions
);

-- Query 1: storage layout and dirty-page state.
SELECT *
FROM repository_storage_report
ORDER BY repository_id;

-- Query 2: sequential heap access.
SELECT
    row_id,
    customer_name,
    balance
FROM repository_rows
WHERE repository_id = (
    SELECT repository_id
    FROM repositories
    WHERE repository_name = 'database-engine-lab'
)
AND customer_id = 101
ORDER BY row_id;

-- Query 3: indexed access path.
SELECT
    rr.row_id,
    rr.customer_name,
    rr.balance,
    ie.page_id
FROM index_entries ie
JOIN repository_rows rr
    ON rr.row_id = ie.row_id
WHERE ie.customer_id = 101
ORDER BY rr.row_id;

-- Query 4: CTE-based buffer-pressure report.
WITH page_access AS (
    SELECT
        bf.page_id,
        bf.pin_count,
        bf.is_dirty,
        bf.last_accessed_at,
        dp.page_type,
        dp.page_lsn
    FROM buffer_frames bf
    JOIN database_pages dp
        ON dp.page_id = bf.page_id
)
SELECT
    page_type,
    COUNT(*) AS resident_pages,
    COUNT(*) FILTER (WHERE is_dirty) AS dirty_pages,
    MAX(page_lsn) AS newest_lsn
FROM page_access
GROUP BY page_type;

-- Query 5: WAL analysis.
SELECT
    transaction_id,
    COUNT(*) AS log_records,
    MIN(lsn) AS first_lsn,
    MAX(lsn) AS last_lsn
FROM write_ahead_log
GROUP BY transaction_id
ORDER BY transaction_id;

-- Query 6: storage aggregation by customer.
SELECT
    customer_id,
    COUNT(*) AS row_count,
    COUNT(DISTINCT page_id) AS pages_touched,
    SUM(balance) AS aggregate_balance,
    AVG(balance) AS average_balance
FROM repository_rows
GROUP BY customer_id
ORDER BY customer_id;

-- Query 7: query planner inspection for the customer index.
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT
    row_id,
    customer_name,
    balance
FROM repository_rows
WHERE repository_id = 1
  AND customer_id = 101;

-- Query 8: transaction workflow state.
SELECT
    transaction_id,
    state,
    started_at,
    finished_at
FROM engine_transactions
ORDER BY transaction_id;

-- Transactional page-flush example.
BEGIN;

UPDATE database_pages
SET is_dirty = FALSE
WHERE page_id = (
    SELECT page_id
    FROM database_pages
    ORDER BY page_id
    LIMIT 1
);

COMMIT;

-- Validation example:
-- The following statement is intentionally not executed because it would
-- violate the positive customer_id constraint.
-- INSERT INTO repository_rows (
--     repository_id, page_id, customer_id, customer_name, balance
-- )
-- VALUES (1, 1, -1, 'Invalid', 100.00);
