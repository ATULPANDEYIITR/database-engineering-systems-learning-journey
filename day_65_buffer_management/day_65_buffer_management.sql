-- ============================================================
-- BUFFER MANAGEMENT SYSTEM
-- PostgreSQL 18
--
-- Models:
--   Database buffer pools
--   Buffer frames
--   Cached pages
--   Cache hits and misses
--   LRU replacement
--   Page pinning
--   Dirty-page tracking
--   Write-back operations
--   Buffer statistics
--   Storage failures
-- ============================================================

BEGIN;

CREATE SCHEMA IF NOT EXISTS buffer_management;

SET search_path TO buffer_management, public;

-- ------------------------------------------------------------
-- 1. ENUMERATIONS
-- ------------------------------------------------------------

CREATE TYPE frame_state AS ENUM (
    'FREE',
    'CLEAN',
    'DIRTY'
);

CREATE TYPE eviction_policy AS ENUM (
    'LRU',
    'LFU'
);

CREATE TYPE io_operation AS ENUM (
    'READ',
    'WRITE',
    'EVICTION',
    'PIN',
    'UNPIN',
    'FLUSH',
    'INVALIDATION'
);

CREATE TYPE io_status AS ENUM (
    'SUCCESS',
    'FAILED'
);

-- ------------------------------------------------------------
-- 2. BUFFER POOLS
-- ------------------------------------------------------------

CREATE TABLE buffer_pools (
    pool_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    pool_name VARCHAR(100) NOT NULL UNIQUE,

    capacity INTEGER NOT NULL
        CHECK (capacity > 0),

    page_size INTEGER NOT NULL
        CHECK (page_size > 0),

    policy eviction_policy NOT NULL DEFAULT 'LRU',

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    active BOOLEAN NOT NULL DEFAULT TRUE
);

-- ------------------------------------------------------------
-- 3. PHYSICAL PAGE CATALOG
-- ------------------------------------------------------------

CREATE TABLE database_pages (
    page_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    database_name VARCHAR(100) NOT NULL,

    table_name VARCHAR(100) NOT NULL,

    page_number BIGINT NOT NULL
        CHECK (page_number >= 0),

    page_data BYTEA NOT NULL,

    version BIGINT NOT NULL DEFAULT 1
        CHECK (version > 0),

    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    UNIQUE (database_name, table_name, page_number)
);

-- ------------------------------------------------------------
-- 4. BUFFER FRAMES
-- ------------------------------------------------------------

CREATE TABLE buffer_frames (
    frame_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    pool_id BIGINT NOT NULL
        REFERENCES buffer_pools(pool_id)
        ON DELETE CASCADE,

    frame_number INTEGER NOT NULL
        CHECK (frame_number >= 0),

    page_id BIGINT
        REFERENCES database_pages(page_id),

    state frame_state NOT NULL DEFAULT 'FREE',

    pin_count INTEGER NOT NULL DEFAULT 0
        CHECK (pin_count >= 0),

    access_count BIGINT NOT NULL DEFAULT 0
        CHECK (access_count >= 0),

    last_accessed_at TIMESTAMPTZ,

    loaded_at TIMESTAMPTZ,

    dirty_since TIMESTAMPTZ,

    UNIQUE (pool_id, frame_number),

    -- One cached copy of a page per pool.
    UNIQUE (pool_id, page_id),

    CHECK (
        (state = 'FREE' AND page_id IS NULL)
        OR
        (state IN ('CLEAN', 'DIRTY') AND page_id IS NOT NULL)
    ),

    CHECK (
        (state = 'DIRTY' AND dirty_since IS NOT NULL)
        OR
        (state <> 'DIRTY')
    )
);

CREATE INDEX idx_buffer_frames_lru
ON buffer_frames (
    pool_id,
    last_accessed_at ASC
)
WHERE state <> 'FREE' AND pin_count = 0;

CREATE INDEX idx_buffer_frames_dirty
ON buffer_frames (
    pool_id,
    dirty_since
)
WHERE state = 'DIRTY';

CREATE INDEX idx_buffer_frames_pinned
ON buffer_frames (
    pool_id,
    pin_count
)
WHERE pin_count > 0;

-- ------------------------------------------------------------
-- 5. BUFFER POOL STATISTICS
-- ------------------------------------------------------------

CREATE TABLE buffer_statistics (
    pool_id BIGINT PRIMARY KEY
        REFERENCES buffer_pools(pool_id)
        ON DELETE CASCADE,

    requests BIGINT NOT NULL DEFAULT 0
        CHECK (requests >= 0),

    hits BIGINT NOT NULL DEFAULT 0
        CHECK (hits >= 0),

    misses BIGINT NOT NULL DEFAULT 0
        CHECK (misses >= 0),

    evictions BIGINT NOT NULL DEFAULT 0
        CHECK (evictions >= 0),

    disk_reads BIGINT NOT NULL DEFAULT 0
        CHECK (disk_reads >= 0),

    disk_writes BIGINT NOT NULL DEFAULT 0
        CHECK (disk_writes >= 0),

    failed_evictions BIGINT NOT NULL DEFAULT 0
        CHECK (failed_evictions >= 0),

    CHECK (hits + misses = requests)
);

-- ------------------------------------------------------------
-- 6. STORAGE AND BUFFER OPERATION AUDIT
-- ------------------------------------------------------------

CREATE TABLE buffer_io_log (
    log_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    pool_id BIGINT NOT NULL
        REFERENCES buffer_pools(pool_id),

    frame_id BIGINT
        REFERENCES buffer_frames(frame_id)
        ON DELETE SET NULL,

    page_id BIGINT,

    operation io_operation NOT NULL,

    status io_status NOT NULL,

    details TEXT,

    duration_ms NUMERIC(12, 3)
        CHECK (duration_ms IS NULL OR duration_ms >= 0),

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_buffer_io_pool_time
ON buffer_io_log(pool_id, created_at DESC);

CREATE INDEX idx_buffer_io_failures
ON buffer_io_log(pool_id, created_at DESC)
WHERE status = 'FAILED';

-- ------------------------------------------------------------
-- 7. INITIAL BUFFER POOL
-- ------------------------------------------------------------

INSERT INTO buffer_pools (
    pool_name,
    capacity,
    page_size,
    policy
)
VALUES
    ('transaction_pool', 4, 8192, 'LRU'),
    ('analytics_pool', 6, 8192, 'LFU');

INSERT INTO buffer_statistics (pool_id)
SELECT pool_id
FROM buffer_pools;

-- ------------------------------------------------------------
-- 8. INITIAL DATABASE PAGES
-- ------------------------------------------------------------

INSERT INTO database_pages (
    database_name,
    table_name,
    page_number,
    page_data
)
VALUES
    ('enterprise_db', 'customers', 0, convert_to('CUSTOMER_PAGE_0', 'UTF8')),
    ('enterprise_db', 'customers', 1, convert_to('CUSTOMER_PAGE_1', 'UTF8')),
    ('enterprise_db', 'orders', 0, convert_to('ORDER_PAGE_0', 'UTF8')),
    ('enterprise_db', 'orders', 1, convert_to('ORDER_PAGE_1', 'UTF8')),
    ('enterprise_db', 'products', 0, convert_to('PRODUCT_PAGE_0', 'UTF8')),
    ('enterprise_db', 'products', 1, convert_to('PRODUCT_PAGE_1', 'UTF8')),
    ('enterprise_db', 'transactions', 0, convert_to('TRANSACTION_PAGE_0', 'UTF8'));

-- ------------------------------------------------------------
-- 9. FRAME INITIALIZATION
-- ------------------------------------------------------------

INSERT INTO buffer_frames (
    pool_id,
    frame_number
)
SELECT
    p.pool_id,
    n.frame_number
FROM buffer_pools p
CROSS JOIN LATERAL
    generate_series(0, p.capacity - 1) AS n(frame_number);

-- ------------------------------------------------------------
-- 10. STATISTICS VALIDATION TRIGGER
-- ------------------------------------------------------------

CREATE OR REPLACE FUNCTION validate_buffer_statistics()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.hits + NEW.misses <> NEW.requests THEN
        RAISE EXCEPTION
            'Invalid statistics: hits + misses must equal requests';
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_validate_buffer_statistics
BEFORE INSERT OR UPDATE ON buffer_statistics
FOR EACH ROW
EXECUTE FUNCTION validate_buffer_statistics();

-- ------------------------------------------------------------
-- 11. BUFFER POOL METADATA VALIDATION
-- ------------------------------------------------------------

CREATE OR REPLACE FUNCTION validate_frame_capacity()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    configured_capacity INTEGER;
BEGIN
    SELECT capacity
    INTO configured_capacity
    FROM buffer_pools
    WHERE pool_id = NEW.pool_id;

    IF configured_capacity IS NULL THEN
        RAISE EXCEPTION 'Buffer pool does not exist';
    END IF;

    IF NEW.frame_number >= configured_capacity THEN
        RAISE EXCEPTION
            'Frame number exceeds configured buffer pool capacity';
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_validate_frame_capacity
BEFORE INSERT OR UPDATE OF pool_id, frame_number
ON buffer_frames
FOR EACH ROW
EXECUTE FUNCTION validate_frame_capacity();

-- ------------------------------------------------------------
-- 12. CACHE PAGE RETRIEVAL
--
-- Returns the cached frame when a hit occurs.
-- Otherwise loads a page from the page catalog.
-- Evicts the least recently used unpinned frame when needed.
-- ------------------------------------------------------------

CREATE OR REPLACE FUNCTION fetch_page(
    p_pool_id BIGINT,
    p_page_id BIGINT
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    selected_frame BIGINT;
    selected_frame_number INTEGER;
    page_size_limit INTEGER;
    page_exists BOOLEAN;
    frame_record RECORD;
    current_page_data BYTEA;
    current_state frame_state;
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM buffer_pools
        WHERE pool_id = p_pool_id
          AND active = TRUE
    ) THEN
        RAISE EXCEPTION 'Buffer pool is missing or inactive';
    END IF;

    SELECT page_size
    INTO page_size_limit
    FROM buffer_pools
    WHERE pool_id = p_pool_id;

    SELECT page_data
    INTO current_page_data
    FROM database_pages
    WHERE page_id = p_page_id;

    page_exists := FOUND;

    IF NOT page_exists THEN
        RAISE EXCEPTION 'Database page % does not exist', p_page_id;
    END IF;

    IF octet_length(current_page_data) > page_size_limit THEN
        RAISE EXCEPTION 'Page exceeds configured buffer page size';
    END IF;

    -- Serialize access to a pool so concurrent callers cannot
    -- allocate the same frame or select conflicting victims.
    PERFORM 1
    FROM buffer_pools
    WHERE pool_id = p_pool_id
    FOR UPDATE;

    -- Cache hit.
    SELECT frame_id
    INTO selected_frame
    FROM buffer_frames
    WHERE pool_id = p_pool_id
      AND page_id = p_page_id
    FOR UPDATE;

    IF FOUND THEN
        UPDATE buffer_frames
        SET access_count = access_count + 1,
            last_accessed_at = clock_timestamp()
        WHERE frame_id = selected_frame;

        UPDATE buffer_statistics
        SET requests = requests + 1,
            hits = hits + 1
        WHERE pool_id = p_pool_id;

        INSERT INTO buffer_io_log (
            pool_id,
            frame_id,
            page_id,
            operation,
            status,
            details
        )
        VALUES (
            p_pool_id,
            selected_frame,
            p_page_id,
            'READ',
            'SUCCESS',
            'Cache hit'
        );

        RETURN selected_frame;
    END IF;

    -- Cache miss.
    UPDATE buffer_statistics
    SET requests = requests + 1,
        misses = misses + 1,
        disk_reads = disk_reads + 1
    WHERE pool_id = p_pool_id;

    -- Select an available free frame first.
    SELECT frame_id, frame_number
    INTO selected_frame, selected_frame_number
    FROM buffer_frames
    WHERE pool_id = p_pool_id
      AND state = 'FREE'
    ORDER BY frame_number
    LIMIT 1
    FOR UPDATE;

    IF NOT FOUND THEN
        -- LRU replacement excludes pinned pages.
        SELECT
            frame_id,
            frame_number,
            page_id,
            state
        INTO frame_record
        FROM buffer_frames
        WHERE pool_id = p_pool_id
          AND pin_count = 0
          AND state <> 'FREE'
        ORDER BY last_accessed_at ASC NULLS FIRST, frame_number
        LIMIT 1
        FOR UPDATE;

        IF NOT FOUND THEN
            UPDATE buffer_statistics
            SET failed_evictions = failed_evictions + 1
            WHERE pool_id = p_pool_id;

            INSERT INTO buffer_io_log (
                pool_id,
                page_id,
                operation,
                status,
                details
            )
            VALUES (
                p_pool_id,
                p_page_id,
                'EVICTION',
                'FAILED',
                'All frames are pinned'
            );

            RAISE EXCEPTION
                'Buffer pool exhausted: all frames are pinned';
        END IF;

        selected_frame := frame_record.frame_id;
        selected_frame_number := frame_record.frame_number;

        -- Write dirty victim before replacing its contents.
        IF frame_record.state = 'DIRTY' THEN
            UPDATE database_pages
            SET page_data = (
                SELECT page_data
                FROM database_pages
                WHERE page_id = frame_record.page_id
            ),
            version = version + 1,
            updated_at = CURRENT_TIMESTAMP
            WHERE page_id = frame_record.page_id;

            UPDATE buffer_statistics
            SET disk_writes = disk_writes + 1
            WHERE pool_id = p_pool_id;
        END IF;

        UPDATE buffer_statistics
        SET evictions = evictions + 1
        WHERE pool_id = p_pool_id;

        INSERT INTO buffer_io_log (
            pool_id,
            frame_id,
            page_id,
            operation,
            status,
            details
        )
        VALUES (
            p_pool_id,
            selected_frame,
            frame_record.page_id,
            'EVICTION',
            'SUCCESS',
            'Unpinned LRU frame selected'
        );
    END IF;

    UPDATE buffer_frames
    SET page_id = p_page_id,
        state = 'CLEAN',
        pin_count = 0,
        access_count = 1,
        last_accessed_at = clock_timestamp(),
        loaded_at = clock_timestamp(),
        dirty_since = NULL
    WHERE frame_id = selected_frame;

    INSERT INTO buffer_io_log (
        pool_id,
        frame_id,
        page_id,
        operation,
        status,
        details
    )
    VALUES (
        p_pool_id,
        selected_frame,
        p_page_id,
        'READ',
        'SUCCESS',
        'Cache miss; page loaded from storage catalog'
    );

    RETURN selected_frame;
END;
$$;

-- ------------------------------------------------------------
-- 13. PIN A PAGE
-- ------------------------------------------------------------

CREATE OR REPLACE FUNCTION pin_page(
    p_pool_id BIGINT,
    p_page_id BIGINT
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    selected_frame BIGINT;
BEGIN
    selected_frame := fetch_page(p_pool_id, p_page_id);

    UPDATE buffer_frames
    SET pin_count = pin_count + 1
    WHERE frame_id = selected_frame;

    INSERT INTO buffer_io_log (
        pool_id,
        frame_id,
        page_id,
        operation,
        status,
        details
    )
    VALUES (
        p_pool_id,
        selected_frame,
        p_page_id,
        'PIN',
        'SUCCESS',
        'Page pinned'
    );

    RETURN selected_frame;
END;
$$;

-- ------------------------------------------------------------
-- 14. UNPIN A PAGE
-- ------------------------------------------------------------

CREATE OR REPLACE FUNCTION unpin_page(
    p_pool_id BIGINT,
    p_page_id BIGINT,
    p_mark_dirty BOOLEAN DEFAULT FALSE
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
    selected_frame BIGINT;
BEGIN
    SELECT frame_id
    INTO selected_frame
    FROM buffer_frames
    WHERE pool_id = p_pool_id
      AND page_id = p_page_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Page is not cached';
    END IF;

    UPDATE buffer_frames
    SET pin_count = pin_count - 1,
        state = CASE
            WHEN p_mark_dirty THEN 'DIRTY'::frame_state
            ELSE state
        END,
        dirty_since = CASE
            WHEN p_mark_dirty THEN COALESCE(
                dirty_since,
                clock_timestamp()
            )
            ELSE dirty_since
        END
    WHERE frame_id = selected_frame
      AND pin_count > 0;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Cannot unpin a page that is not pinned';
    END IF;

    INSERT INTO buffer_io_log (
        pool_id,
        frame_id,
        page_id,
        operation,
        status,
        details
    )
    VALUES (
        p_pool_id,
        selected_frame,
        p_page_id,
        'UNPIN',
        'SUCCESS',
        CASE
            WHEN p_mark_dirty THEN 'Unpinned and marked dirty'
            ELSE 'Unpinned'
        END
    );
END;
$$;

-- ------------------------------------------------------------
-- 15. MODIFY A BUFFERED PAGE
--
-- PostgreSQL BYTEA manipulation is used to simulate page changes.
-- ------------------------------------------------------------

CREATE OR REPLACE FUNCTION modify_page(
    p_pool_id BIGINT,
    p_page_id BIGINT,
    p_offset INTEGER,
    p_payload BYTEA
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
    selected_frame BIGINT;
    configured_page_size INTEGER;
    old_data BYTEA;
BEGIN
    IF p_offset < 0 THEN
        RAISE EXCEPTION 'Offset cannot be negative';
    END IF;

    selected_frame := pin_page(p_pool_id, p_page_id);

    SELECT page_size
    INTO configured_page_size
    FROM buffer_pools
    WHERE pool_id = p_pool_id;

    SELECT page_data
    INTO old_data
    FROM database_pages
    WHERE page_id = p_page_id;

    IF p_offset + octet_length(p_payload) > configured_page_size THEN
        PERFORM unpin_page(p_pool_id, p_page_id, FALSE);

        RAISE EXCEPTION 'Write exceeds page boundaries';
    END IF;

    UPDATE database_pages
    SET page_data =
        CASE
            WHEN p_offset = 0 THEN
                p_payload ||
                substring(
                    old_data
                    FROM octet_length(p_payload) + 1
                )
            ELSE
                substring(old_data FROM 1 FOR p_offset) ||
                p_payload ||
                substring(
                    old_data
                    FROM p_offset + octet_length(p_payload) + 1
                )
        END
    WHERE page_id = p_page_id;

    PERFORM unpin_page(p_pool_id, p_page_id, TRUE);
END;
$$;

-- ------------------------------------------------------------
-- 16. FLUSH A SINGLE DIRTY PAGE
-- ------------------------------------------------------------

CREATE OR REPLACE FUNCTION flush_page(
    p_pool_id BIGINT,
    p_page_id BIGINT
)
RETURNS BOOLEAN
LANGUAGE plpgsql
AS $$
DECLARE
    selected_frame BIGINT;
BEGIN
    SELECT frame_id
    INTO selected_frame
    FROM buffer_frames
    WHERE pool_id = p_pool_id
      AND page_id = p_page_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Page is not cached';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM buffer_frames
        WHERE frame_id = selected_frame
          AND pin_count > 0
    ) THEN
        RAISE EXCEPTION 'Cannot flush a pinned page';
    END IF;

    UPDATE buffer_frames
    SET state = 'CLEAN',
        dirty_since = NULL
    WHERE frame_id = selected_frame
      AND state = 'DIRTY';

    IF FOUND THEN
        UPDATE database_pages
        SET version = version + 1,
            updated_at = CURRENT_TIMESTAMP
        WHERE page_id = p_page_id;

        UPDATE buffer_statistics
        SET disk_writes = disk_writes + 1
        WHERE pool_id = p_pool_id;

        INSERT INTO buffer_io_log (
            pool_id,
            frame_id,
            page_id,
            operation,
            status,
            details
        )
        VALUES (
            p_pool_id,
            selected_frame,
            p_page_id,
            'FLUSH',
            'SUCCESS',
            'Dirty page flushed'
        );

        RETURN TRUE;
    END IF;

    RETURN FALSE;
END;
$$;

-- ------------------------------------------------------------
-- 17. BUFFER POOL REPORTING VIEW
-- ------------------------------------------------------------

CREATE OR REPLACE VIEW buffer_pool_report AS
SELECT
    p.pool_id,
    p.pool_name,
    p.capacity,
    COUNT(f.frame_id) FILTER (
        WHERE f.state <> 'FREE'
    ) AS occupied_frames,
    p.capacity - COUNT(f.frame_id) FILTER (
        WHERE f.state <> 'FREE'
    ) AS free_frames,
    COUNT(f.frame_id) FILTER (
        WHERE f.state = 'DIRTY'
    ) AS dirty_frames,
    COUNT(f.frame_id) FILTER (
        WHERE f.pin_count > 0
    ) AS pinned_frames,
    COALESCE(s.requests, 0) AS requests,
    COALESCE(s.hits, 0) AS hits,
    COALESCE(s.misses, 0) AS misses,
    ROUND(
        COALESCE(
            s.hits::NUMERIC / NULLIF(s.requests, 0),
            0
        ),
        4
    ) AS hit_ratio,
    ROUND(
        COALESCE(
            s.misses::NUMERIC / NULLIF(s.requests, 0),
            0
        ),
        4
    ) AS miss_ratio,
    COALESCE(s.evictions, 0) AS evictions,
    COALESCE(s.disk_reads, 0) AS disk_reads,
    COALESCE(s.disk_writes, 0) AS disk_writes,
    COALESCE(s.failed_evictions, 0) AS failed_evictions
FROM buffer_pools p
LEFT JOIN buffer_frames f
    ON f.pool_id = p.pool_id
LEFT JOIN buffer_statistics s
    ON s.pool_id = p.pool_id
GROUP BY
    p.pool_id,
    p.pool_name,
    p.capacity,
    s.requests,
    s.hits,
    s.misses,
    s.evictions,
    s.disk_reads,
    s.disk_writes,
    s.failed_evictions;

-- ------------------------------------------------------------
-- 18. CTE: LRU EVICTION CANDIDATES
-- ------------------------------------------------------------

CREATE OR REPLACE VIEW buffer_eviction_candidates AS
WITH ranked_frames AS (
    SELECT
        f.frame_id,
        f.pool_id,
        f.page_id,
        f.frame_number,
        f.state,
        f.pin_count,
        f.last_accessed_at,
        ROW_NUMBER() OVER (
            PARTITION BY f.pool_id
            ORDER BY
                f.last_accessed_at ASC NULLS FIRST,
                f.frame_number
        ) AS eviction_rank
    FROM buffer_frames f
    WHERE f.state <> 'FREE'
      AND f.pin_count = 0
)
SELECT *
FROM ranked_frames
WHERE eviction_rank = 1;

-- ------------------------------------------------------------
-- 19. CTE: CACHE EFFICIENCY ANALYSIS
-- ------------------------------------------------------------

CREATE OR REPLACE VIEW cache_efficiency AS
SELECT
    pool_id,
    pool_name,
    requests,
    hits,
    misses,
    hit_ratio,
    miss_ratio,
    CASE
        WHEN requests = 0 THEN 'NO ACTIVITY'
        WHEN hit_ratio >= 0.90 THEN 'EXCELLENT'
        WHEN hit_ratio >= 0.70 THEN 'GOOD'
        WHEN hit_ratio >= 0.40 THEN 'MODERATE'
        ELSE 'LOW'
    END AS efficiency_class
FROM buffer_pool_report;

-- ------------------------------------------------------------
-- 20. DEMONSTRATION WORKFLOW
-- ------------------------------------------------------------

DO $$
DECLARE
    transaction_pool BIGINT;
    page_customer BIGINT;
    page_order BIGINT;
    page_product BIGINT;
BEGIN
    SELECT pool_id
    INTO transaction_pool
    FROM buffer_pools
    WHERE pool_name = 'transaction_pool';

    SELECT page_id INTO page_customer
    FROM database_pages
    WHERE table_name = 'customers'
      AND page_number = 0;

    SELECT page_id INTO page_order
    FROM database_pages
    WHERE table_name = 'orders'
      AND page_number = 0;

    SELECT page_id INTO page_product
    FROM database_pages
    WHERE table_name = 'products'
      AND page_number = 0;

    -- Initial misses.
    PERFORM fetch_page(transaction_pool, page_customer);
    PERFORM fetch_page(transaction_pool, page_order);
    PERFORM fetch_page(transaction_pool, page_product);

    -- Repeated access produces hits.
    PERFORM fetch_page(transaction_pool, page_customer);
    PERFORM fetch_page(transaction_pool, page_order);

    -- Modify and mark a page dirty.
    PERFORM modify_page(
        transaction_pool,
        page_customer,
        0,
        convert_to('UPDATED_CUSTOMER', 'UTF8')
    );

    -- Flush dirty page.
    PERFORM flush_page(transaction_pool, page_customer);
END;
$$;

-- ------------------------------------------------------------
-- 21. TRANSACTIONAL PAGE ACCESS
-- ------------------------------------------------------------

BEGIN;

SELECT fetch_page(
    (
        SELECT pool_id
        FROM buffer_pools
        WHERE pool_name = 'transaction_pool'
    ),
    (
        SELECT page_id
        FROM database_pages
        WHERE table_name = 'orders'
          AND page_number = 1
    )
);

COMMIT;

-- ------------------------------------------------------------
-- 22. RETRIEVAL QUERIES
-- ------------------------------------------------------------

-- Buffer pool health.
SELECT *
FROM buffer_pool_report
ORDER BY pool_id;

-- Cache efficiency.
SELECT *
FROM cache_efficiency
ORDER BY hit_ratio DESC;

-- Current cached pages.
SELECT
    p.pool_name,
    f.frame_number,
    f.page_id,
    f.state,
    f.pin_count,
    f.access_count,
    f.last_accessed_at
FROM buffer_frames f
JOIN buffer_pools p
    ON p.pool_id = f.pool_id
ORDER BY p.pool_name, f.frame_number;

-- Dirty-page identification.
SELECT
    p.pool_name,
    f.frame_id,
    f.page_id,
    f.dirty_since
FROM buffer_frames f
JOIN buffer_pools p
    ON p.pool_id = f.pool_id
WHERE f.state = 'DIRTY'
ORDER BY f.dirty_since;

-- ------------------------------------------------------------
-- 23. VALIDATION QUERIES
-- ------------------------------------------------------------

-- Check configured capacity versus allocated frames.
SELECT
    p.pool_name,
    p.capacity,
    COUNT(f.frame_id) AS allocated_frames,
    COUNT(f.frame_id) = p.capacity AS capacity_valid
FROM buffer_pools p
LEFT JOIN buffer_frames f
    ON f.pool_id = p.pool_id
GROUP BY p.pool_id, p.pool_name, p.capacity;

-- Find pinned frames that may delay eviction.
SELECT
    pool_id,
    frame_id,
    page_id,
    pin_count
FROM buffer_frames
WHERE pin_count > 0;

-- Find failed I/O operations.
SELECT *
FROM buffer_io_log
WHERE status = 'FAILED'
ORDER BY created_at DESC;

-- ------------------------------------------------------------
-- 24. AGGREGATION AND PERFORMANCE REPORTING
-- ------------------------------------------------------------

SELECT
    p.pool_name,
    COUNT(f.frame_id) AS frame_count,
    SUM(f.access_count) AS total_page_accesses,
    AVG(f.access_count) AS average_accesses,
    MAX(f.access_count) AS maximum_accesses,
    COUNT(*) FILTER (
        WHERE f.state = 'DIRTY'
    ) AS dirty_count,
    COUNT(*) FILTER (
        WHERE f.pin_count > 0
    ) AS pinned_count
FROM buffer_pools p
LEFT JOIN buffer_frames f
    ON f.pool_id = p.pool_id
GROUP BY p.pool_id, p.pool_name;

-- Operation distribution.
SELECT
    pool_id,
    operation,
    status,
    COUNT(*) AS operation_count,
    AVG(duration_ms) AS average_duration_ms
FROM buffer_io_log
GROUP BY pool_id, operation, status
ORDER BY pool_id, operation;

-- ------------------------------------------------------------
-- 25. ELIGIBILITY DETERMINATION
-- ------------------------------------------------------------

-- A pool can accept another page when a free frame exists
-- or an unpinned frame can be selected for replacement.

SELECT
    p.pool_id,
    p.pool_name,
    CASE
        WHEN EXISTS (
            SELECT 1
            FROM buffer_frames f
            WHERE f.pool_id = p.pool_id
              AND f.state = 'FREE'
        ) THEN TRUE

        WHEN EXISTS (
            SELECT 1
            FROM buffer_frames f
            WHERE f.pool_id = p.pool_id
              AND f.pin_count = 0
              AND f.state <> 'FREE'
        ) THEN TRUE

        ELSE FALSE
    END AS can_accept_page
FROM buffer_pools p
WHERE p.active = TRUE;

COMMIT;
