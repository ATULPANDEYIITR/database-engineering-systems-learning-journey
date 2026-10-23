DROP SCHEMA IF EXISTS procedure_trigger_lab CASCADE;

CREATE SCHEMA procedure_trigger_lab;

SET search_path TO procedure_trigger_lab;

-- Procedures expose controlled multi-step database operations.
-- Functions are used where PostgreSQL requires a return value or where
-- trigger functions are needed.

CREATE TYPE transaction_type AS ENUM ('CREDIT', 'DEBIT');

CREATE TYPE account_status AS ENUM ('ACTIVE', 'SUSPENDED', 'CLOSED');

CREATE TABLE customers (
    customer_id BIGSERIAL PRIMARY KEY,
    customer_name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),

    CONSTRAINT customers_name_not_blank
        CHECK (btrim(customer_name) <> ''),

    CONSTRAINT customers_email_not_blank
        CHECK (btrim(email) <> '')
);

CREATE TABLE accounts (
    account_id BIGSERIAL PRIMARY KEY,
    customer_id BIGINT NOT NULL
        REFERENCES customers(customer_id),
    account_number TEXT NOT NULL UNIQUE,
    balance NUMERIC(14, 2) NOT NULL DEFAULT 0,
    status account_status NOT NULL DEFAULT 'ACTIVE',
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),

    CONSTRAINT accounts_number_not_blank
        CHECK (btrim(account_number) <> ''),

    CONSTRAINT accounts_balance_nonnegative
        CHECK (balance >= 0)
);

CREATE TABLE account_transactions (
    transaction_id BIGSERIAL PRIMARY KEY,
    account_id BIGINT NOT NULL
        REFERENCES accounts(account_id),
    amount NUMERIC(14, 2) NOT NULL,
    transaction_kind transaction_type NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),

    CONSTRAINT transactions_positive_amount
        CHECK (amount > 0)
);

CREATE TABLE account_audit (
    audit_id BIGSERIAL PRIMARY KEY,
    account_id BIGINT NOT NULL
        REFERENCES accounts(account_id),
    old_balance NUMERIC(14, 2),
    new_balance NUMERIC(14, 2),
    action TEXT NOT NULL,
    changed_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    changed_by TEXT NOT NULL DEFAULT CURRENT_USER,

    CONSTRAINT audit_action_valid
        CHECK (
            action IN (
                'INSERT',
                'BALANCE_UPDATE',
                'STATUS_UPDATE'
            )
        )
);

CREATE INDEX idx_transactions_account_created
    ON account_transactions(account_id, created_at DESC);

CREATE INDEX idx_audit_account_changed
    ON account_audit(account_id, changed_at DESC);

CREATE OR REPLACE FUNCTION validate_account_before_write()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF btrim(NEW.account_number) = '' THEN
        RAISE EXCEPTION
            USING MESSAGE = 'Account number cannot be empty',
                  ERRCODE = '23514';
    END IF;

    IF NEW.balance < 0 THEN
        RAISE EXCEPTION
            USING MESSAGE = 'Account balance cannot be negative',
                  ERRCODE = '23514';
    END IF;

    IF TG_OP = 'UPDATE'
       AND abs(NEW.balance - OLD.balance) > 10000 THEN
        RAISE EXCEPTION
            USING MESSAGE =
                'Single balance update cannot exceed 10000',
                  ERRCODE = 'P0001';
    END IF;

    NEW.updated_at := clock_timestamp();

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_accounts_validate_before_write
BEFORE INSERT OR UPDATE
ON accounts
FOR EACH ROW
EXECUTE FUNCTION validate_account_before_write();


CREATE OR REPLACE FUNCTION audit_account_change()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        INSERT INTO account_audit (
            account_id,
            old_balance,
            new_balance,
            action
        )
        VALUES (
            NEW.account_id,
            NULL,
            NEW.balance,
            'INSERT'
        );

    ELSIF TG_OP = 'UPDATE'
           AND OLD.balance IS DISTINCT FROM NEW.balance THEN
        INSERT INTO account_audit (
            account_id,
            old_balance,
            new_balance,
            action
        )
        VALUES (
            NEW.account_id,
            OLD.balance,
            NEW.balance,
            'BALANCE_UPDATE'
        );
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_accounts_audit_after_write
AFTER INSERT OR UPDATE
ON accounts
FOR EACH ROW
EXECUTE FUNCTION audit_account_change();


CREATE OR REPLACE FUNCTION apply_transaction()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.transaction_kind = 'CREDIT' THEN
        UPDATE accounts
        SET balance = balance + NEW.amount
        WHERE account_id = NEW.account_id;

    ELSIF NEW.transaction_kind = 'DEBIT' THEN
        UPDATE accounts
        SET balance = balance - NEW.amount
        WHERE account_id = NEW.account_id
          AND balance >= NEW.amount;

        IF NOT FOUND THEN
            RAISE EXCEPTION
                USING MESSAGE = 'Insufficient funds',
                      ERRCODE = 'P0001';
        END IF;
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_transactions_apply_balance
AFTER INSERT
ON account_transactions
FOR EACH ROW
EXECUTE FUNCTION apply_transaction();


CREATE OR REPLACE FUNCTION create_customer_account(
    p_customer_name TEXT,
    p_email TEXT,
    p_account_number TEXT,
    p_opening_balance NUMERIC(14, 2)
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    v_customer_id BIGINT;
    v_account_id BIGINT;
BEGIN
    IF btrim(p_customer_name) = '' THEN
        RAISE EXCEPTION 'Customer name cannot be empty';
    END IF;

    IF btrim(p_email) = '' THEN
        RAISE EXCEPTION 'Email cannot be empty';
    END IF;

    IF btrim(p_account_number) = '' THEN
        RAISE EXCEPTION 'Account number cannot be empty';
    END IF;

    IF p_opening_balance < 0 THEN
        RAISE EXCEPTION 'Opening balance cannot be negative';
    END IF;

    INSERT INTO customers (
        customer_name,
        email
    )
    VALUES (
        btrim(p_customer_name),
        lower(btrim(p_email))
    )
    RETURNING customer_id INTO v_customer_id;

    INSERT INTO accounts (
        customer_id,
        account_number,
        balance
    )
    VALUES (
        v_customer_id,
        btrim(p_account_number),
        p_opening_balance
    )
    RETURNING account_id INTO v_account_id;

    RETURN v_account_id;
END;
$$;


CREATE OR REPLACE PROCEDURE transfer_funds(
    p_source_account BIGINT,
    p_destination_account BIGINT,
    p_amount NUMERIC(14, 2)
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_source_balance NUMERIC(14, 2);
    v_source_status account_status;
    v_destination_status account_status;
BEGIN
    IF p_source_account = p_destination_account THEN
        RAISE EXCEPTION 'Source and destination accounts must differ';
    END IF;

    IF p_amount IS NULL OR p_amount <= 0 THEN
        RAISE EXCEPTION 'Transfer amount must be positive';
    END IF;

    /*
     * FOR UPDATE serializes concurrent transfers touching these rows.
     * Ordering by account ID avoids lock-order inversion between
     * concurrent transfers in opposite directions.
     */
    IF p_source_account < p_destination_account THEN
        SELECT balance, status
        INTO v_source_balance, v_source_status
        FROM accounts
        WHERE account_id = p_source_account
        FOR UPDATE;

        SELECT status
        INTO v_destination_status
        FROM accounts
        WHERE account_id = p_destination_account
        FOR UPDATE;
    ELSE
        SELECT status
        INTO v_destination_status
        FROM accounts
        WHERE account_id = p_destination_account
        FOR UPDATE;

        SELECT balance, status
        INTO v_source_balance, v_source_status
        FROM accounts
        WHERE account_id = p_source_account
        FOR UPDATE;
    END IF;

    IF v_source_balance IS NULL THEN
        RAISE EXCEPTION 'Source account does not exist';
    END IF;

    IF v_destination_status IS NULL THEN
        RAISE EXCEPTION 'Destination account does not exist';
    END IF;

    IF v_source_status <> 'ACTIVE'
       OR v_destination_status <> 'ACTIVE' THEN
        RAISE EXCEPTION
            'Both accounts must be active';
    END IF;

    IF v_source_balance < p_amount THEN
        RAISE EXCEPTION 'Insufficient funds';
    END IF;

    /*
     * The trigger on account_transactions updates account balances.
     * The procedure therefore coordinates the business operation while
     * the trigger maintains the derived balance automatically.
     */
    INSERT INTO account_transactions (
        account_id,
        amount,
        transaction_kind
    )
    VALUES (
        p_source_account,
        p_amount,
        'DEBIT'
    );

    INSERT INTO account_transactions (
        account_id,
        amount,
        transaction_kind
    )
    VALUES (
        p_destination_account,
        p_amount,
        'CREDIT'
    );
END;
$$;


-- Sample data.

INSERT INTO customers (customer_name, email)
VALUES
    ('Aarav Mehta', 'aarav@example.com'),
    ('Meera Sharma', 'meera@example.com'),
    ('Kabir Singh', 'kabir@example.com');

INSERT INTO accounts (
    customer_id,
    account_number,
    balance
)
SELECT customer_id, 'ACCT-1001', 10000
FROM customers
WHERE email = 'aarav@example.com';

INSERT INTO accounts (
    customer_id,
    account_number,
    balance
)
SELECT customer_id, 'ACCT-1002', 5000
FROM customers
WHERE email = 'meera@example.com';

INSERT INTO accounts (
    customer_id,
    account_number,
    balance
)
SELECT customer_id, 'ACCT-1003', 2500
FROM customers
WHERE email = 'kabir@example.com';


-- Trigger-driven balance maintenance.

INSERT INTO account_transactions (
    account_id,
    amount,
    transaction_kind
)
SELECT account_id, 750, 'CREDIT'
FROM accounts
WHERE account_number = 'ACCT-1001';

INSERT INTO account_transactions (
    account_id,
    amount,
    transaction_kind
)
SELECT account_id, 500, 'DEBIT'
FROM accounts
WHERE account_number = 'ACCT-1002';


-- Procedure-driven multi-row operation.

CALL transfer_funds(
    (
        SELECT account_id
        FROM accounts
        WHERE account_number = 'ACCT-1001'
    ),
    (
        SELECT account_id
        FROM accounts
        WHERE account_number = 'ACCT-1002'
    ),
    1000
);


-- Procedure returning a generated identifier.

SELECT create_customer_account(
    'Nisha Verma',
    'nisha@example.com',
    'ACCT-1004',
    3000
);


-- Retrieval query showing the resulting state.

SELECT
    a.account_number,
    c.customer_name,
    a.balance,
    a.status,
    a.updated_at
FROM accounts AS a
JOIN customers AS c
    ON c.customer_id = a.customer_id
ORDER BY a.account_id;


-- CTE reporting transaction totals.

WITH transaction_totals AS (
    SELECT
        account_id,
        SUM(
            CASE
                WHEN transaction_kind = 'CREDIT'
                    THEN amount
                ELSE 0
            END
        ) AS total_credits,
        SUM(
            CASE
                WHEN transaction_kind = 'DEBIT'
                    THEN amount
                ELSE 0
            END
        ) AS total_debits,
        COUNT(*) AS transaction_count
    FROM account_transactions
    GROUP BY account_id
)
SELECT
    a.account_number,
    c.customer_name,
    a.balance,
    COALESCE(t.total_credits, 0) AS total_credits,
    COALESCE(t.total_debits, 0) AS total_debits,
    COALESCE(t.transaction_count, 0) AS transaction_count
FROM accounts AS a
JOIN customers AS c
    ON c.customer_id = a.customer_id
LEFT JOIN transaction_totals AS t
    ON t.account_id = a.account_id
ORDER BY a.account_number;


-- View separating reporting logic from transactional tables.

CREATE OR REPLACE VIEW account_activity_summary AS
SELECT
    a.account_id,
    a.account_number,
    c.customer_name,
    a.balance,
    COUNT(t.transaction_id) AS transaction_count,
    COALESCE(
        SUM(
            CASE
                WHEN t.transaction_kind = 'CREDIT'
                    THEN t.amount
                ELSE 0
            END
        ),
        0
    ) AS credits,
    COALESCE(
        SUM(
            CASE
                WHEN t.transaction_kind = 'DEBIT'
                    THEN t.amount
                ELSE 0
            END
        ),
        0
    ) AS debits
FROM accounts AS a
JOIN customers AS c
    ON c.customer_id = a.customer_id
LEFT JOIN account_transactions AS t
    ON t.account_id = a.account_id
GROUP BY
    a.account_id,
    a.account_number,
    c.customer_name,
    a.balance;


SELECT *
FROM account_activity_summary
ORDER BY account_number;


-- Trigger failure demonstration.
-- The statement is wrapped in a transaction so the example does not leave
-- invalid business state in the database.

BEGIN;

DO $$
DECLARE
    v_account_id BIGINT;
BEGIN
    SELECT account_id
    INTO v_account_id
    FROM accounts
    WHERE account_number = 'ACCT-1002';

    BEGIN
        INSERT INTO account_transactions (
            account_id,
            amount,
            transaction_kind
        )
        VALUES (
            v_account_id,
            999999999,
            'DEBIT'
        );
    EXCEPTION
        WHEN OTHERS THEN
            RAISE NOTICE 'Expected trigger failure: %', SQLERRM;
    END;
END;
$$;

COMMIT;


-- Demonstrate explicit transaction rollback for a procedure call.

BEGIN;

CALL transfer_funds(
    (
        SELECT account_id
        FROM accounts
        WHERE account_number = 'ACCT-1001'
    ),
    (
        SELECT account_id
        FROM accounts
        WHERE account_number = 'ACCT-1003'
    ),
    250
);

SELECT
    account_number,
    balance
FROM accounts
WHERE account_number IN ('ACCT-1001', 'ACCT-1003')
ORDER BY account_number;

ROLLBACK;


-- The rollback leaves the balances unchanged.

SELECT
    account_number,
    balance
FROM accounts
WHERE account_number IN ('ACCT-1001', 'ACCT-1003')
ORDER BY account_number;


-- Audit history generated automatically by the triggers.

SELECT
    audit_id,
    account_id,
    old_balance,
    new_balance,
    action,
    changed_at,
    changed_by
FROM account_audit
ORDER BY audit_id;
