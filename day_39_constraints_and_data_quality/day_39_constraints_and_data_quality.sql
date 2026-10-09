-- Constraints and Data Quality: PostgreSQL 15+
-- CHECK, NOT NULL, UNIQUE, relational integrity, and business rules.
--
-- Execute this script in a dedicated PostgreSQL database.
-- The schema is isolated under data_quality_demo.

BEGIN;

CREATE SCHEMA IF NOT EXISTS data_quality_demo;
SET search_path TO data_quality_demo, public;

CREATE TABLE department (
    department_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    department_code VARCHAR(20) NOT NULL UNIQUE,
    department_name VARCHAR(100) NOT NULL UNIQUE,
    annual_budget NUMERIC(14, 2) NOT NULL
        CHECK (annual_budget >= 0),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT department_code_not_blank
        CHECK (length(btrim(department_code)) > 0),
    CONSTRAINT department_name_not_blank
        CHECK (length(btrim(department_name)) > 0)
);

CREATE TABLE employee (
    employee_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    employee_code VARCHAR(20) NOT NULL,
    email VARCHAR(254) NOT NULL,
    full_name VARCHAR(100) NOT NULL,
    age SMALLINT NOT NULL,
    salary NUMERIC(12, 2) NOT NULL,
    department_id BIGINT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT employee_code_unique UNIQUE (employee_code),
    CONSTRAINT employee_email_unique UNIQUE (email),

    CONSTRAINT employee_code_not_blank
        CHECK (length(btrim(employee_code)) > 0),
    CONSTRAINT employee_email_not_blank
        CHECK (length(btrim(email)) > 0),
    CONSTRAINT employee_email_basic_shape
        CHECK (
            position('@' IN email) > 1
            AND position('.' IN split_part(email, '@', 2)) > 1
        ),
    CONSTRAINT employee_full_name_not_blank
        CHECK (length(btrim(full_name)) BETWEEN 1 AND 100),
    CONSTRAINT employee_age_range
        CHECK (age BETWEEN 18 AND 100),
    CONSTRAINT employee_salary_nonnegative
        CHECK (salary >= 0),
    CONSTRAINT employee_salary_scale
        CHECK (salary = round(salary, 2)),

    CONSTRAINT employee_department_fk
        FOREIGN KEY (department_id)
        REFERENCES department(department_id)
        ON UPDATE RESTRICT
        ON DELETE RESTRICT
);

-- A regular UNIQUE constraint permits only one row for each non-NULL value
-- but PostgreSQL ordinarily treats NULL values as distinct. NOT NULL is
-- therefore essential for mandatory identifiers.

CREATE TABLE quality_rule (
    rule_code VARCHAR(50) PRIMARY KEY,
    description TEXT NOT NULL,
    severity VARCHAR(10) NOT NULL
        CHECK (severity IN ('INFO', 'WARNING', 'ERROR')),
    is_blocking BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT quality_rule_code_not_blank
        CHECK (length(btrim(rule_code)) > 0),
    CONSTRAINT quality_rule_description_not_blank
        CHECK (length(btrim(description)) > 0)
);

CREATE TABLE quality_audit (
    audit_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    entity_name VARCHAR(100) NOT NULL,
    entity_key VARCHAR(100),
    rule_code VARCHAR(50) NOT NULL,
    attempted_value JSONB,
    error_message TEXT NOT NULL,
    detected_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT quality_audit_rule_fk
        FOREIGN KEY (rule_code)
        REFERENCES quality_rule(rule_code),
    CONSTRAINT quality_audit_message_not_blank
        CHECK (length(btrim(error_message)) > 0)
);

CREATE INDEX employee_department_active_idx
    ON employee(department_id, is_active);

CREATE INDEX employee_created_at_idx
    ON employee(created_at DESC);

CREATE INDEX quality_audit_rule_time_idx
    ON quality_audit(rule_code, detected_at DESC);

INSERT INTO department (
    department_code,
    department_name,
    annual_budget
)
VALUES
    ('ENG', 'Engineering', 250000.00),
    ('FIN', 'Finance', 150000.00),
    ('OPS', 'Operations', 200000.00);

INSERT INTO quality_rule (
    rule_code,
    description,
    severity,
    is_blocking
)
VALUES
    ('REQUIRED_FIELD', 'Mandatory employee values must be present.', 'ERROR', TRUE),
    ('UNIQUE_EMPLOYEE_CODE', 'Employee codes identify one employee.', 'ERROR', TRUE),
    ('UNIQUE_EMAIL', 'Normalized employee email addresses must be unique.', 'ERROR', TRUE),
    ('AGE_RANGE', 'Employee age must be between 18 and 100.', 'ERROR', TRUE),
    ('SALARY_RANGE', 'Salary cannot be negative.', 'ERROR', TRUE),
    ('DEPARTMENT_REFERENCE', 'Employees must reference a registered department.', 'ERROR', TRUE),
    ('EMAIL_FORMAT', 'Email must satisfy the accepted basic structure.', 'WARNING', FALSE);

-- Case-insensitive uniqueness is enforced independently of application code.
-- The expression index prevents differently cased values from duplicating
-- the same logical email. The ordinary UNIQUE constraint also prevents
-- exact duplicates and documents the base column's uniqueness.
CREATE UNIQUE INDEX employee_email_case_insensitive_uq
    ON employee (lower(btrim(email)));

INSERT INTO employee (
    employee_code,
    email,
    full_name,
    age,
    salary,
    department_id,
    is_active
)
SELECT
    sample.employee_code,
    sample.email,
    sample.full_name,
    sample.age,
    sample.salary,
    department.department_id,
    sample.is_active
FROM (
    VALUES
        ('E-501', 'alice@example.com', 'Alice Sharma', 32, 65000.00, 'ENG', TRUE),
        ('E-502', 'rahul@example.com', 'Rahul Verma', 41, 82000.00, 'FIN', TRUE),
        ('E-503', 'meera@example.com', 'Meera Singh', 27, 54000.00, 'OPS', FALSE)
) AS sample(
    employee_code,
    email,
    full_name,
    age,
    salary,
    department_code,
    is_active
)
JOIN department
    ON department.department_code = sample.department_code;

-- Import staging separates raw data from trusted production records.
CREATE TABLE employee_import_staging (
    staging_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_row_number INTEGER NOT NULL UNIQUE CHECK (source_row_number > 0),
    employee_code TEXT,
    email TEXT,
    full_name TEXT,
    age_text TEXT,
    salary_text TEXT,
    department_code TEXT,
    active_text TEXT,
    imported_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMPTZ,
    processing_status VARCHAR(20) NOT NULL DEFAULT 'PENDING'
        CHECK (
            processing_status IN ('PENDING', 'ACCEPTED', 'REJECTED')
        ),
    rejection_reason TEXT
);

INSERT INTO employee_import_staging (
    source_row_number,
    employee_code,
    email,
    full_name,
    age_text,
    salary_text,
    department_code,
    active_text
)
VALUES
    (1, 'E-504', 'new@example.com', 'New Employee', '29', '47000.00', 'ENG', 'true'),
    (2, 'E-501', 'duplicate-code@example.com', 'Duplicate Code', '30', '50000.00', 'FIN', 'true'),
    (3, 'E-505', 'ALICE@EXAMPLE.COM', 'Duplicate Email', '30', '50000.00', 'ENG', 'true'),
    (4, 'E-506', 'underage@example.com', 'Underage Applicant', '17', '35000.00', 'FIN', 'true'),
    (5, 'E-507', 'negative@example.com', 'Negative Salary', '34', '-500.00', 'OPS', 'true'),
    (6, 'E-508', 'unknown@example.com', 'Unknown Department', '30', '45000.00', 'LEGAL', 'true'),
    (7, NULL, 'missing-code@example.com', 'Missing Code', '28', '40000.00', 'OPS', 'true');

-- The query identifies staging problems before any production insert.
-- Invalid numeric text is checked before casting to avoid aborting the query.
CREATE OR REPLACE VIEW employee_staging_quality AS
SELECT
    s.staging_id,
    s.source_row_number,
    s.employee_code,
    s.email,
    CASE
        WHEN NULLIF(btrim(s.employee_code), '') IS NULL
            THEN 'REQUIRED_EMPLOYEE_CODE'
        WHEN NULLIF(btrim(s.email), '') IS NULL
            THEN 'REQUIRED_EMAIL'
        WHEN NULLIF(btrim(s.full_name), '') IS NULL
            THEN 'REQUIRED_FULL_NAME'
        WHEN s.email !~* '^[^[:space:]@]+@[^[:space:]@]+\.[^[:space:]@]+$'
            THEN 'EMAIL_FORMAT'
        WHEN s.age_text !~ '^[0-9]+$'
            THEN 'AGE_NOT_INTEGER'
        WHEN s.salary_text !~ '^[0-9]+(\.[0-9]{1,2})?$'
            THEN 'SALARY_FORMAT_OR_RANGE'
        WHEN s.active_text NOT IN ('true', 'false')
            THEN 'ACTIVE_FLAG_FORMAT'
        WHEN EXISTS (
            SELECT 1
            FROM employee e
            WHERE upper(btrim(e.employee_code)) =
                  upper(btrim(s.employee_code))
        )
            THEN 'DUPLICATE_EMPLOYEE_CODE'
        WHEN EXISTS (
            SELECT 1
            FROM employee e
            WHERE lower(btrim(e.email)) = lower(btrim(s.email))
        )
            THEN 'DUPLICATE_EMAIL'
        WHEN s.age_text ~ '^[0-9]+$'
             AND s.age_text::INTEGER NOT BETWEEN 18 AND 100
            THEN 'AGE_RANGE'
        WHEN s.salary_text ~ '^[0-9]+(\.[0-9]{1,2})?$'
             AND s.salary_text::NUMERIC < 0
            THEN 'SALARY_RANGE'
        WHEN NOT EXISTS (
            SELECT 1
            FROM department d
            WHERE d.department_code = s.department_code
              AND d.is_active
        )
            THEN 'DEPARTMENT_REFERENCE'
        ELSE 'VALID'
    END AS quality_status
FROM employee_import_staging s;

SELECT source_row_number, employee_code, email, quality_status
FROM employee_staging_quality
ORDER BY source_row_number;

-- A transaction gives a batch all-or-nothing behavior. The staging checks
-- identify expected failures before inserting accepted records.
BEGIN;

WITH valid_staging AS (
    SELECT
        s.staging_id,
        upper(btrim(s.employee_code)) AS employee_code,
        lower(btrim(s.email)) AS email,
        btrim(s.full_name) AS full_name,
        s.age_text::SMALLINT AS age,
        s.salary_text::NUMERIC(12, 2) AS salary,
        d.department_id,
        s.active_text::BOOLEAN AS is_active
    FROM employee_import_staging s
    JOIN employee_staging_quality q
        ON q.staging_id = s.staging_id
       AND q.quality_status = 'VALID'
    JOIN department d
        ON d.department_code = s.department_code
       AND d.is_active
    WHERE s.processing_status = 'PENDING'
)
INSERT INTO employee (
    employee_code,
    email,
    full_name,
    age,
    salary,
    department_id,
    is_active
)
SELECT
    employee_code,
    email,
    full_name,
    age,
    salary,
    department_id,
    is_active
FROM valid_staging
ON CONFLICT DO NOTHING;

UPDATE employee_import_staging s
SET
    processing_status = CASE
        WHEN q.quality_status = 'VALID' THEN 'ACCEPTED'
        ELSE 'REJECTED'
    END,
    rejection_reason = CASE
        WHEN q.quality_status = 'VALID' THEN NULL
        ELSE q.quality_status
    END,
    processed_at = CURRENT_TIMESTAMP
FROM employee_staging_quality q
WHERE q.staging_id = s.staging_id
  AND s.processing_status = 'PENDING';

INSERT INTO quality_audit (
    entity_name,
    entity_key,
    rule_code,
    attempted_value,
    error_message
)
SELECT
    'employee_import_staging',
    s.source_row_number::TEXT,
    CASE q.quality_status
        WHEN 'REQUIRED_EMPLOYEE_CODE' THEN 'REQUIRED_FIELD'
        WHEN 'REQUIRED_EMAIL' THEN 'REQUIRED_FIELD'
        WHEN 'REQUIRED_FULL_NAME' THEN 'REQUIRED_FIELD'
        WHEN 'EMAIL_FORMAT' THEN 'EMAIL_FORMAT'
        WHEN 'AGE_RANGE' THEN 'AGE_RANGE'
        WHEN 'SALARY_RANGE' THEN 'SALARY_RANGE'
        WHEN 'DEPARTMENT_REFERENCE' THEN 'DEPARTMENT_REFERENCE'
        WHEN 'DUPLICATE_EMPLOYEE_CODE' THEN 'UNIQUE_EMPLOYEE_CODE'
        WHEN 'DUPLICATE_EMAIL' THEN 'UNIQUE_EMAIL'
        ELSE 'REQUIRED_FIELD'
    END,
    jsonb_build_object(
        'employee_code', s.employee_code,
        'email', s.email,
        'age', s.age_text,
        'salary', s.salary_text,
        'department_code', s.department_code
    ),
    'Staging validation failed: ' || q.quality_status
FROM employee_import_staging s
JOIN employee_staging_quality q
    ON q.staging_id = s.staging_id
WHERE q.quality_status <> 'VALID';

COMMIT;

-- Verify the resulting records and import decisions.
SELECT
    e.employee_code,
    e.email,
    e.full_name,
    e.age,
    e.salary,
    d.department_name,
    e.is_active
FROM employee e
JOIN department d USING (department_id)
ORDER BY e.employee_code;

SELECT
    processing_status,
    COUNT(*) AS rows_in_state
FROM employee_import_staging
GROUP BY processing_status
ORDER BY processing_status;

SELECT
    d.department_name,
    COUNT(e.employee_id) AS employee_count,
    COUNT(e.employee_id) FILTER (WHERE e.is_active) AS active_employees,
    MIN(e.salary) AS minimum_salary,
    MAX(e.salary) AS maximum_salary,
    ROUND(AVG(e.salary), 2) AS average_salary
FROM department d
LEFT JOIN employee e USING (department_id)
GROUP BY d.department_id, d.department_name
ORDER BY d.department_name;

SELECT
    rule_code,
    COUNT(*) AS failure_count,
    MAX(detected_at) AS most_recent_failure
FROM quality_audit
GROUP BY rule_code
ORDER BY failure_count DESC, rule_code;

-- This transaction deliberately attempts a negative salary. The CHECK
-- constraint rejects it. The exception block catches the failure and keeps
-- the surrounding script executable.
DO $$
BEGIN
    BEGIN
        INSERT INTO employee (
            employee_code,
            email,
            full_name,
            age,
            salary,
            department_id
        )
        SELECT
            'E-999',
            'invalid@example.com',
            'Invalid Salary',
            30,
            -1.00,
            department_id
        FROM department
        WHERE department_code = 'FIN';

        RAISE EXCEPTION 'Expected salary constraint to reject the record.';
    EXCEPTION
        WHEN check_violation THEN
            RAISE NOTICE 'Expected rejection: negative salary violates CHECK.';
    END;
END;
$$;

-- A NULL test demonstrates NOT NULL independently of application validation.
DO $$
BEGIN
    BEGIN
        INSERT INTO employee (
            employee_code,
            email,
            full_name,
            age,
            salary,
            department_id
        )
        SELECT
            'E-998',
            'null-name@example.com',
            NULL,
            30,
            40000.00,
            department_id
        FROM department
        WHERE department_code = 'FIN';

        RAISE EXCEPTION 'Expected NOT NULL constraint to reject the record.';
    EXCEPTION
        WHEN not_null_violation THEN
            RAISE NOTICE 'Expected rejection: full_name cannot be NULL.';
    END;
END;
$$;

-- A normalized duplicate-email test demonstrates expression-index enforcement.
DO $$
BEGIN
    BEGIN
        INSERT INTO employee (
            employee_code,
            email,
            full_name,
            age,
            salary,
            department_id
        )
        SELECT
            'E-997',
            ' ALICE@EXAMPLE.COM ',
            'Duplicate Email Test',
            30,
            40000.00,
            department_id
        FROM department
        WHERE department_code = 'FIN';

        RAISE EXCEPTION 'Expected case-insensitive unique index to reject duplicate.';
    EXCEPTION
        WHEN unique_violation THEN
            RAISE NOTICE 'Expected rejection: normalized email already exists.';
    END;
END;
$$;

-- This view is useful for recurring operational monitoring.
CREATE OR REPLACE VIEW department_data_quality_metrics AS
SELECT
    d.department_code,
    d.department_name,
    COUNT(e.employee_id) AS employee_count,
    COUNT(e.employee_id) FILTER (
        WHERE e.is_active
    ) AS active_employee_count,
    COUNT(e.employee_id) FILTER (
        WHERE e.salary = 0
    ) AS zero_salary_count,
    COUNT(e.employee_id) FILTER (
        WHERE e.email IS NULL OR length(btrim(e.email)) = 0
    ) AS missing_email_count
FROM department d
LEFT JOIN employee e USING (department_id)
GROUP BY d.department_id, d.department_code, d.department_name;

SELECT *
FROM department_data_quality_metrics
ORDER BY department_name;

-- Inspect query planning for the indexed department/active lookup.
EXPLAIN
SELECT employee_code, full_name
FROM employee
WHERE department_id = (
    SELECT department_id
    FROM department
    WHERE department_code = 'ENG'
)
AND is_active = TRUE;

RESET search_path;
