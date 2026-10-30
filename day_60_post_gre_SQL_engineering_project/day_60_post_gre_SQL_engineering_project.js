"use strict";

/*
 * PostgreSQL operations monitor.
 *
 * Commands:
 *   node postgres_monitor.js
 *   node postgres_monitor.js self-test
 *   node postgres_monitor.js health
 *   node postgres_monitor.js report
 *   node postgres_monitor.js watch 15000
 *
 * Connection settings are read from the standard PG* environment variables.
 * The program invokes psql directly and never constructs a shell command.
 */

const { execFile } = require("node:child_process");
const { promisify } = require("node:util");
const { EventEmitter } = require("node:events");

const execFileAsync = promisify(execFile);

const HEALTH_SQL = `
SELECT jsonb_build_object(
    'database', current_database(),
    'server_version', current_setting('server_version'),
    'server_version_num', current_setting('server_version_num')::integer,
    'max_connections', current_setting('max_connections')::integer,
    'superuser_reserved_connections',
        current_setting('superuser_reserved_connections')::integer,
    'used_connections', (
        SELECT count(*)
        FROM pg_stat_activity
        WHERE datname = current_database()
    ),
    'blocked_sessions', (
        SELECT count(*)
        FROM pg_stat_activity AS activity
        WHERE activity.datname = current_database()
          AND cardinality(pg_blocking_pids(activity.pid)) > 0
    ),
    'oldest_transaction_seconds', (
        SELECT COALESCE(
            EXTRACT(EPOCH FROM max(clock_timestamp() - xact_start))::integer,
            0
        )
        FROM pg_stat_activity
        WHERE datname = current_database()
          AND xact_start IS NOT NULL
    ),
    'database_size_bytes', pg_database_size(current_database()),
    'is_replica', pg_is_in_recovery()
)::text;
`;

const REPORT_SQL = `
SELECT jsonb_pretty(
    jsonb_build_object(
        'database', current_database(),
        'server_version', current_setting('server_version'),
        'database_size_bytes', pg_database_size(current_database()),
        'connections', jsonb_build_object(
            'maximum', current_setting('max_connections')::integer,
            'used', (
                SELECT count(*)
                FROM pg_stat_activity
                WHERE datname = current_database()
            ),
            'by_state', COALESCE((
                SELECT jsonb_object_agg(state_name, connection_count)
                FROM (
                    SELECT COALESCE(state, 'unknown') AS state_name,
                           count(*) AS connection_count
                    FROM pg_stat_activity
                    WHERE datname = current_database()
                    GROUP BY COALESCE(state, 'unknown')
                ) AS connection_states
            ), '{}'::jsonb)
        ),
        'blocked_sessions', COALESCE((
            SELECT jsonb_agg(
                jsonb_build_object(
                    'pid', pid,
                    'application', application_name,
                    'state', state,
                    'wait_event_type', wait_event_type,
                    'wait_event', wait_event
                )
                ORDER BY pid
            )
            FROM pg_stat_activity
            WHERE datname = current_database()
              AND cardinality(pg_blocking_pids(pid)) > 0
        ), '[]'::jsonb),
        'long_transactions', COALESCE((
            SELECT jsonb_agg(
                jsonb_build_object(
                    'pid', pid,
                    'application', application_name,
                    'state', state,
                    'duration_seconds',
                        EXTRACT(EPOCH FROM clock_timestamp() - xact_start)::integer
                )
                ORDER BY xact_start
            )
            FROM pg_stat_activity
            WHERE datname = current_database()
              AND xact_start < clock_timestamp() - interval '5 minutes'
        ), '[]'::jsonb),
        'largest_relations', COALESCE((
            SELECT jsonb_agg(
                jsonb_build_object(
                    'schema', schemaname,
                    'table', relname,
                    'total_size_bytes', total_bytes,
                    'table_size_bytes', table_bytes
                )
                ORDER BY total_bytes DESC
            )
            FROM (
                SELECT
                    schemaname,
                    relname,
                    pg_total_relation_size(
                        format('%I.%I', schemaname, relname)::regclass
                    ) AS total_bytes,
                    pg_relation_size(
                        format('%I.%I', schemaname, relname)::regclass
                    ) AS table_bytes
                FROM pg_stat_user_tables
                ORDER BY pg_total_relation_size(
                    format('%I.%I', schemaname, relname)::regclass
                ) DESC
                LIMIT 10
            ) AS relation_sizes
        ), '[]'::jsonb)
    )
)::text;
`;

class ConfigurationError extends Error {
    constructor(message) {
        super(message);
        this.name = "ConfigurationError";
    }
}

class PsqlClient {
    constructor(options = {}) {
        this.executable = options.executable || "psql";
        this.timeout = options.timeout || 15000;
        this.maxBuffer = options.maxBuffer || 2 * 1024 * 1024;
    }

    async query(sql, timeout = this.timeout) {
        if (typeof sql !== "string" || sql.trim().length === 0) {
            throw new ConfigurationError("SQL query cannot be empty");
        }

        try {
            const { stdout, stderr } = await execFileAsync(
                this.executable,
                [
                    "-X",
                    "-q",
                    "-A",
                    "-t",
                    "-v",
                    "ON_ERROR_STOP=1",
                    "-c",
                    sql
                ],
                {
                    encoding: "utf8",
                    timeout,
                    maxBuffer: this.maxBuffer,
                    windowsHide: true,
                    env: process.env
                }
            );

            if (stderr.trim()) {
                process.stderr.write(`${stderr.trim()}\n`);
            }

            const output = stdout.trim();
            if (!output) {
                throw new Error("PostgreSQL returned an empty response");
            }

            try {
                return JSON.parse(output);
            } catch (error) {
                throw new Error(
                    `Could not parse PostgreSQL JSON response: ${error.message}`
                );
            }
        } catch (error) {
            if (error.code === "ENOENT") {
                throw new ConfigurationError(
                    "psql was not found. Install PostgreSQL client tools and add psql to PATH."
                );
            }
            if (error.killed) {
                throw new Error(`PostgreSQL query exceeded ${timeout} ms`);
            }
            throw new Error(`PostgreSQL query failed: ${error.message}`);
        }
    }
}

class HealthPolicy {
    constructor(options = {}) {
        this.connectionWarningRatio = options.connectionWarningRatio ?? 0.80;
        this.maximumTransactionAgeSeconds =
            options.maximumTransactionAgeSeconds ?? 300;

        if (
            this.connectionWarningRatio <= 0 ||
            this.connectionWarningRatio > 1
        ) {
            throw new ConfigurationError(
                "connectionWarningRatio must be greater than 0 and at most 1"
            );
        }

        if (this.maximumTransactionAgeSeconds < 1) {
            throw new ConfigurationError(
                "maximumTransactionAgeSeconds must be positive"
            );
        }
    }

    evaluate(metrics) {
        const maximum = Number(metrics.max_connections);
        const used = Number(metrics.used_connections);
        const blocked = Number(metrics.blocked_sessions);
        const transactionAge = Number(
            metrics.oldest_transaction_seconds
        );

        if (
            !Number.isFinite(maximum) ||
            maximum <= 0 ||
            !Number.isFinite(used) ||
            used < 0 ||
            !Number.isFinite(blocked) ||
            blocked < 0 ||
            !Number.isFinite(transactionAge) ||
            transactionAge < 0
        ) {
            throw new Error("PostgreSQL returned invalid health metrics");
        }

        const alerts = [];

        if (used / maximum >= this.connectionWarningRatio) {
            alerts.push("Connection usage is above the configured threshold");
        }

        if (blocked > 0) {
            alerts.push(`${blocked} session(s) are blocked`);
        }

        if (transactionAge > this.maximumTransactionAgeSeconds) {
            alerts.push(
                `A transaction has been open for ${transactionAge} seconds`
            );
        }

        if (metrics.is_replica === true) {
            alerts.push("Connected server is a standby rather than a primary");
        }

        return {
            healthy: alerts.length === 0,
            alerts,
            connectionUtilization: Number((used / maximum).toFixed(4))
        };
    }
}

class PostgresMonitor extends EventEmitter {
    constructor(client, policy) {
        super();
        this.client = client;
        this.policy = policy;
    }

    async collectHealth() {
        const metrics = await this.client.query(HEALTH_SQL);
        const evaluation = this.policy.evaluate(metrics);
        const result = {
            collectedAt: new Date().toISOString(),
            metrics,
            evaluation
        };

        this.emit("sample", result);

        if (evaluation.healthy) {
            this.emit("healthy", result);
        } else {
            this.emit("alert", result);
        }

        return result;
    }

    async collectReport() {
        const report = await this.client.query(REPORT_SQL);
        this.emit("report", report);
        return report;
    }
}

function delay(milliseconds) {
    return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

function validateInterval(value) {
    const interval = Number(value);

    if (
        !Number.isInteger(interval) ||
        interval < 5000 ||
        interval > 300000
    ) {
        throw new ConfigurationError(
            "Watch interval must be an integer between 5000 and 300000 milliseconds"
        );
    }

    return interval;
}

async function runWatch(monitor, intervalMs) {
    let stopped = false;

    const stop = () => {
        stopped = true;
    };

    process.once("SIGINT", stop);

    console.log(`Monitoring PostgreSQL every ${intervalMs} ms. Press Ctrl+C to stop.`);

    try {
        while (!stopped) {
            try {
                const result = await monitor.collectHealth();
                process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
            } catch (error) {
                console.error(`Monitoring error: ${error.message}`);
            }

            if (!stopped) {
                await delay(intervalMs);
            }
        }
    } finally {
        process.removeListener("SIGINT", stop);
        console.log("Monitoring stopped.");
    }
}

function runSelfTest() {
    const policy = new HealthPolicy();

    const healthy = policy.evaluate({
        max_connections: 180,
        used_connections: 50,
        blocked_sessions: 0,
        oldest_transaction_seconds: 15,
        is_replica: false
    });

    const unhealthy = policy.evaluate({
        max_connections: 100,
        used_connections: 95,
        blocked_sessions: 2,
        oldest_transaction_seconds: 600,
        is_replica: false
    });

    if (!healthy.healthy) {
        throw new Error("Healthy metrics were incorrectly rejected");
    }

    if (unhealthy.healthy || unhealthy.alerts.length !== 3) {
        throw new Error("Unhealthy metrics were incorrectly accepted");
    }

    let intervalRejected = false;

    try {
        validateInterval("100");
    } catch (error) {
        intervalRejected = true;
    }

    if (!intervalRejected) {
        throw new Error("Invalid monitoring interval was accepted");
    }

    console.log("Self-test passed.");
    console.log(JSON.stringify({ healthy, unhealthy }, null, 2));
}

async function main() {
    const command = process.argv[2] || "self-test";

    if (command === "self-test") {
        runSelfTest();
        return;
    }

    const client = new PsqlClient();
    const monitor = new PostgresMonitor(client, new HealthPolicy());

    monitor.on("alert", (result) => {
        process.stderr.write(
            `ALERT: ${result.evaluation.alerts.join("; ")}\n`
        );
    });

    monitor.on("healthy", () => {
        process.stderr.write("HEALTHY: PostgreSQL checks passed.\n");
    });

    if (command === "health") {
        const result = await monitor.collectHealth();
        console.log(JSON.stringify(result, null, 2));
        if (!result.evaluation.healthy) {
            process.exitCode = 2;
        }
        return;
    }

    if (command === "report") {
        const report = await monitor.collectReport();
        console.log(JSON.stringify(report, null, 2));
        return;
    }

    if (command === "watch") {
        const interval = validateInterval(process.argv[3] || "15000");
        await runWatch(monitor, interval);
        return;
    }

    throw new ConfigurationError(
        "Command must be self-test, health, report, or watch"
    );
}

main().catch((error) => {
    console.error(`ERROR: ${error.message}`);
    process.exitCode = 1;
});
