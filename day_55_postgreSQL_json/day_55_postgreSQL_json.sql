-- PostgreSQL JSON and JSONB: document storage, querying, validation, indexing,
-- transactional updates, and reporting.
--
-- Compatible with PostgreSQL 15 or later.
-- Run in a disposable database because this script recreates its own schema.

BEGIN;

DROP SCHEMA IF EXISTS json_lab CASCADE;
CREATE SCHEMA json_lab;

SET search_path = json_lab, public;

CREATE TABLE product (
    product_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    sku text NOT NULL UNIQUE,
    name text NOT NULL CHECK (length(btrim(name)) BETWEEN 1 AND 120),
    category text NOT NULL CHECK (category ~ '^[a-z][a-z0-9_-]{0,49}$'),
    price numeric(12, 2) NOT NULL CHECK (price >= 0),
    -- JSON preserves the supplied textual representation of JSON values.
    raw_attributes json NOT NULL,
    -- JSONB is used for normalized storage, containment, operators, and indexes.
    attributes jsonb NOT NULL DEFAULT '{}'::jsonb,
    tags text[] NOT NULL DEFAULT '{}',
    document_version integer NOT NULL DEFAULT 1 CHECK (document_version > 0),
    active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CHECK (jsonb_typeof(attributes) = 'object'),
    CHECK (jsonb_typeof(raw_attributes::jsonb) = 'object'),
    CHECK (octet_length(attributes::text) <= 16384)
);

CREATE TABLE attribute_change (
    change_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    product_id bigint NOT NULL REFERENCES product(product_id) ON DELETE CASCADE,
    old_version integer NOT NULL,
    new_version integer NOT NULL,
    changed_keys text[] NOT NULL,
    changed_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CHECK (new_version = old_version + 1)
);

CREATE TABLE query_audit (
    audit_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    operation text NOT NULL,
    product_id bigint,
    outcome text NOT NULL CHECK (outcome IN ('accepted', 'rejected')),
    details jsonb NOT NULL DEFAULT '{}'::jsonb,
    recorded_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

-- B-tree indexes serve relational equality, uniqueness, and ordered retrieval.
CREATE INDEX product_category_active_idx
    ON product(category, product_id)
    WHERE active;

-- GIN supports containment and key-existence predicates on JSONB.
CREATE INDEX product_attributes_path_gin_idx
    ON product USING gin (attributes jsonb_path_ops);

-- This expression index targets a frequently queried scalar property.
CREATE INDEX product_brand_idx
    ON product ((attributes ->> 'brand'))
    WHERE active;

CREATE INDEX product_tags_gin_idx
    ON product USING gin (tags);

CREATE OR REPLACE FUNCTION validate_product_attributes()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF jsonb_typeof(NEW.attributes) IS DISTINCT FROM 'object' THEN
        RAISE EXCEPTION 'attributes must be a JSON object';
    END IF;

    IF octet_length(NEW.attributes::text) > 16384 THEN
        RAISE EXCEPTION 'attributes exceed 16 KiB';
    END IF;

    IF NEW.attributes ? 'specs'
       AND jsonb_typeof(NEW.attributes -> 'specs') <> 'object' THEN
        RAISE EXCEPTION 'specs must be a JSON object when provided';
    END IF;

    IF NEW.attributes #> '{specs,ram_gb}' IS NOT NULL
       AND NEW.attributes #> '{specs,ram_gb}' <> 'null'::jsonb THEN
        IF jsonb_typeof(NEW.attributes #> '{specs,ram_gb}') <> 'number'
           OR (NEW.attributes #>> '{specs,ram_gb}')::numeric < 0 THEN
            RAISE EXCEPTION 'specs.ram_gb must be a non-negative number';
        END IF;
    END IF;

    NEW.updated_at := clock_timestamp();
    RETURN NEW;
END;
$$;

CREATE TRIGGER product_attributes_validation
BEFORE INSERT OR UPDATE OF attributes ON product
FOR EACH ROW
EXECUTE FUNCTION validate_product_attributes();

CREATE OR REPLACE FUNCTION record_attribute_change()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    changed text[];
BEGIN
    IF TG_OP = 'INSERT' THEN
        INSERT INTO attribute_change (
            product_id, old_version, new_version, changed_keys
        )
        VALUES (
            NEW.product_id, 0, NEW.document_version,
            ARRAY(SELECT key FROM jsonb_object_keys(NEW.attributes) AS key ORDER BY key)
        );
        RETURN NEW;
    END IF;

    IF NEW.attributes IS DISTINCT FROM OLD.attributes THEN
        SELECT COALESCE(array_agg(key ORDER BY key), '{}')
        INTO changed
        FROM (
            SELECT key
            FROM jsonb_object_keys(OLD.attributes || NEW.attributes) AS key
            WHERE OLD.attributes -> key IS DISTINCT FROM NEW.attributes -> key
        ) AS differences;

        NEW.document_version := OLD.document_version + 1;

        INSERT INTO attribute_change (
            product_id, old_version, new_version, changed_keys
        )
        VALUES (
            NEW.product_id, OLD.document_version, NEW.document_version, changed
        );
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER product_attribute_change_history
BEFORE UPDATE OF attributes ON product
FOR EACH ROW
EXECUTE FUNCTION record_attribute_change();

-- SQL NULL and JSON null are different:
-- SQL NULL means an absent database value; 'null'::jsonb is a JSON value.
INSERT INTO product (sku, name, category, price, raw_attributes, attributes, tags)
VALUES
(
    'LAP-001',
    'Engineering Laptop',
    'electronics',
    1299.99,
    '{"brand":"Northstar","wireless":true,"specs":{"ram_gb":32,"storage_gb":1024},"ports":["USB-C","HDMI"]}',
    '{"brand":"Northstar","wireless":true,"specs":{"ram_gb":32,"storage_gb":1024},"ports":["USB-C","HDMI"]}',
    ARRAY['developer', 'portable']
),
(
    'MON-001',
    'Operations Monitor',
    'electronics',
    349.50,
    '{"brand":"Northstar","wireless":false,"specs":{"ram_gb":0,"storage_gb":0},"ports":["HDMI","DisplayPort"]}',
    '{"brand":"Northstar","wireless":false,"specs":{"ram_gb":0,"storage_gb":0},"ports":["HDMI","DisplayPort"]}',
    ARRAY['office']
),
(
    'SRV-001',
    'Analytics Server',
    'infrastructure',
    4599.00,
    '{"brand":"Contoso","wireless":false,"specs":{"ram_gb":256,"storage_gb":8192},"rack_units":2}',
    '{"brand":"Contoso","wireless":false,"specs":{"ram_gb":256,"storage_gb":8192},"rack_units":2}',
    ARRAY['datacenter', 'analytics']
),
(
    'CAM-001',
    'Inspection Camera',
    'industrial',
    899.00,
    '{"brand":"Optiview","wireless":true,"specs":{"ram_gb":8},"calibration":{"required":true,"interval_days":90},"serial_note":null}',
    '{"brand":"Optiview","wireless":true,"specs":{"ram_gb":8},"calibration":{"required":true,"interval_days":90},"serial_note":null}',
    ARRAY['inspection', 'industrial']
);

-- 1. Relational retrieval with a JSON scalar projection.
SELECT product_id, sku, name, price, attributes ->> 'brand' AS brand
FROM product
WHERE category = 'electronics' AND active
ORDER BY product_id;

-- 2. Object containment: nested values can be matched without full document equality.
SELECT sku, name
FROM product
WHERE attributes @> '{"specs":{"ram_gb":32}}'::jsonb;

-- 3. Key existence, scalar extraction, and JSON type inspection.
SELECT
    sku,
    attributes ? 'calibration' AS has_calibration,
    attributes ->> 'wireless' AS wireless_text,
    jsonb_typeof(attributes -> 'serial_note') AS serial_note_type
FROM product
ORDER BY product_id;

-- 4. JSON array expansion with lateral processing.
SELECT p.sku, port.value AS port
FROM product AS p
CROSS JOIN LATERAL jsonb_array_elements_text(
    CASE
        WHEN jsonb_typeof(p.attributes -> 'ports') = 'array'
        THEN p.attributes -> 'ports'
        ELSE '[]'::jsonb
    END
) AS port(value)
ORDER BY p.sku, port.value;

-- 5. Aggregation over extracted numeric values.
SELECT
    category,
    count(*) AS product_count,
    round(avg(price), 2) AS average_price,
    round(avg((attributes #>> '{specs,ram_gb}')::numeric), 2) AS average_ram_gb
FROM product
WHERE active
  AND jsonb_typeof(attributes #> '{specs,ram_gb}') = 'number'
GROUP BY category
ORDER BY category;

-- 6. JSONPath: evaluate a predicate over nested numeric values.
SELECT sku, name
FROM product
WHERE jsonb_path_exists(
    attributes,
    '$.specs.ram_gb ? (@ >= 32)'
)
ORDER BY sku;

-- 7. Distinguish SQL NULL, missing keys, and JSON null.
SELECT
    sku,
    attributes ? 'serial_note' AS key_exists,
    attributes -> 'serial_note' = 'null'::jsonb AS is_json_null,
    attributes ->> 'serial_note' IS NULL AS text_extraction_is_sql_null
FROM product
WHERE sku = 'CAM-001';

-- 8. Set-based document reporting using a CTE.
WITH extracted AS (
    SELECT
        sku,
        category,
        attributes ->> 'brand' AS brand,
        CASE
            WHEN jsonb_typeof(attributes #> '{specs,ram_gb}') = 'number'
            THEN (attributes #>> '{specs,ram_gb}')::numeric
        END AS ram_gb
    FROM product
    WHERE active
)
SELECT brand, count(*) AS products, max(ram_gb) AS maximum_ram_gb
FROM extracted
GROUP BY brand
ORDER BY brand;

-- 9. Atomic JSONB patch and version history.
-- jsonb_set replaces a nested value while retaining unrelated document keys.
UPDATE product
SET attributes = jsonb_set(
    attributes,
    '{warranty_years}',
    '3'::jsonb,
    true
)
WHERE sku = 'MON-001';

-- Add a nested field without overwriting the other specs.
UPDATE product
SET attributes = jsonb_set(
    attributes,
    '{specs,storage_gb}',
    '2048'::jsonb,
    true
)
WHERE sku = 'LAP-001';

SELECT p.sku, p.document_version, p.attributes, c.changed_keys
FROM product AS p
JOIN attribute_change AS c USING (product_id)
ORDER BY p.product_id, c.change_id;

-- 10. Demonstrate a savepoint: an invalid write is rolled back without losing
-- earlier successful work in the transaction.
SAVEPOINT before_invalid_document;

DO $$
BEGIN
    BEGIN
        INSERT INTO product (
            sku, name, category, price, raw_attributes, attributes
        )
        VALUES (
            'BAD-001',
            'Invalid RAM',
            'electronics',
            10.00,
            '{"specs":{"ram_gb":-5}}',
            '{"specs":{"ram_gb":-5}}'
        );
    EXCEPTION WHEN OTHERS THEN
        INSERT INTO query_audit (operation, outcome, details)
        VALUES (
            'insert_product',
            'rejected',
            jsonb_build_object('reason', SQLERRM, 'sku', 'BAD-001')
        );
    END;
END;
$$;

RELEASE SAVEPOINT before_invalid_document;

-- 11. Inspect the document change history.
SELECT product_id, old_version, new_version, changed_keys, changed_at
FROM attribute_change
ORDER BY change_id;

-- 12. Query-plan inspection for index-aware execution.
-- The planner may choose a sequential scan for a small table.
EXPLAIN
SELECT product_id, sku
FROM product
WHERE attributes @> '{"brand":"Northstar"}'::jsonb;

EXPLAIN
SELECT product_id, sku
FROM product
WHERE attributes ->> 'brand' = 'Northstar'
  AND active;

-- 13. Relational and JSONB eligibility report.
CREATE VIEW product_document_report AS
SELECT
    product_id,
    sku,
    category,
    price,
    attributes ->> 'brand' AS brand,
    attributes #>> '{specs,ram_gb}' AS ram_gb_text,
    jsonb_object_length(attributes) AS top_level_attribute_count,
    document_version,
    active
FROM product;

SELECT *
FROM product_document_report
ORDER BY product_id;

COMMIT;
