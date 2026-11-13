"use strict";

/*
 * Query Optimizer: Cost Estimation, Statistics and Plan Selection
 *
 * Node.js 18+
 *
 * Distinct engineering perspective:
 * - Asynchronous statistics catalog
 * - Event-driven statistics updates
 * - Immutable query descriptions
 * - Map-based catalog and optimizer state
 * - Selectivity estimation
 * - Access-path evaluation
 * - Greedy connected join ordering
 * - Hash and nested-loop join costing
 * - Plan validation and diagnostic reporting
 *
 * Dependencies: Node.js standard library only.
 */

const { EventEmitter } = require("node:events");

// ============================================================
// 1. CONSTANTS AND ERRORS
// ============================================================

const ScanType = Object.freeze({
    SEQUENTIAL: "Sequential Scan",
    INDEX: "Index Scan"
});

const JoinType = Object.freeze({
    HASH: "Hash Join",
    NESTED_LOOP: "Nested Loop"
});

class OptimizerError extends Error {}
class StatisticsError extends OptimizerError {}
class ValidationError extends OptimizerError {}

const DEFAULT_COSTS = Object.freeze({
    sequentialPage: 1.0,
    randomPage: 4.0,
    tuple: 0.01,
    operator: 0.0025,
    hashBuild: 0.015,
    nestedLoop: 0.005,
    cacheDiscount: 0.75
});

// ============================================================
// 2. VALIDATION UTILITIES
// ============================================================

function assertFinitePositive(value, label, allowZero = false) {
    if (
        typeof value !== "number" ||
        !Number.isFinite(value) ||
        (allowZero ? value < 0 : value <= 0)
    ) {
        throw new ValidationError(`${label} is invalid.`);
    }
}

function validateIdentifier(value, label) {
    if (
        typeof value !== "string" ||
        !/^[a-zA-Z_][a-zA-Z0-9_]*$/.test(value)
    ) {
        throw new ValidationError(`Invalid ${label}.`);
    }
}

function clamp(value, minimum = 0, maximum = 1) {
    return Math.min(maximum, Math.max(minimum, value));
}

// ============================================================
// 3. STATISTICS MODELS
// ============================================================

class ColumnStats {
    constructor({
        name,
        ndv,
        nullFraction = 0,
        mcv = {},
        histogram = null
    }) {
        validateIdentifier(name, "column name");

        assertFinitePositive(ndv, "Distinct values");

        if (nullFraction < 0 || nullFraction > 1) {
            throw new StatisticsError("Invalid null fraction.");
        }

        const frequencies = new Map(Object.entries(mcv));

        let total = 0;

        for (const frequency of frequencies.values()) {
            if (
                !Number.isFinite(frequency) ||
                frequency < 0 ||
                frequency > 1
            ) {
                throw new StatisticsError("Invalid MCV frequency.");
            }
            total += frequency;
        }

        if (total > 1) {
            throw new StatisticsError("MCV frequencies exceed 1.");
        }

        if (histogram !== null) {
            if (
                !Array.isArray(histogram) ||
                histogram.length < 2 ||
                !histogram.every(Number.isFinite)
            ) {
                throw new StatisticsError("Invalid histogram.");
            }

            for (let i = 1; i < histogram.length; i++) {
                if (histogram[i] <= histogram[i - 1]) {
                    throw new StatisticsError(
                        "Histogram boundaries must increase."
                    );
                }
            }
        }

        this.name = name;
        this.ndv = ndv;
        this.nullFraction = nullFraction;
        this.mcv = frequencies;
        this.histogram = histogram ? [...histogram] : null;

        Object.freeze(this);
    }
}

class RelationStats {
    constructor({
        name,
        rows,
        pages,
        columns,
        indexes = [],
        analyzedAt = Date.now()
    }) {
        validateIdentifier(name, "relation name");

        assertFinitePositive(rows, "Row count", true);
        assertFinitePositive(pages, "Page count", true);

        if (rows > 0 && pages === 0) {
            throw new StatisticsError(
                "A nonempty relation requires pages."
            );
        }

        if (!Number.isFinite(analyzedAt)) {
            throw new StatisticsError("Invalid analysis timestamp.");
        }

        const columnMap = new Map(
            columns.map(column => [column.name, column])
        );

        const indexMap = new Map();

        for (const index of indexes) {
            validateIdentifier(index.column, "index column");

            if (!columnMap.has(index.column)) {
                throw new StatisticsError(
                    "Index references an unknown column."
                );
            }

            assertFinitePositive(index.pages, "Index pages");

            indexMap.set(index.column, Object.freeze({
                ...index
            }));
        }

        this.name = name;
        this.rows = rows;
        this.pages = pages;
        this.columns = columnMap;
        this.indexes = indexMap;
        this.analyzedAt = analyzedAt;
    }
}

// ============================================================
// 4. ASYNCHRONOUS STATISTICS CATALOG
// ============================================================

class StatisticsCatalog extends EventEmitter {

    constructor() {
        super();
        this.relations = new Map();
        this.revision = 0;
    }

    async register(stats) {
        await Promise.resolve();

        if (this.relations.has(stats.name)) {
            throw new StatisticsError(
                `Duplicate relation: ${stats.name}`
            );
        }

        this.relations.set(stats.name, stats);
        this.revision++;

        this.emit("statistics:registered", {
            relation: stats.name,
            revision: this.revision
        });
    }

    async update(stats) {
        await Promise.resolve();

        if (!this.relations.has(stats.name)) {
            throw new StatisticsError(
                `Cannot update missing relation: ${stats.name}`
            );
        }

        this.relations.set(stats.name, stats);
        this.revision++;

        this.emit("statistics:updated", {
            relation: stats.name,
            revision: this.revision
        });
    }

    get(name) {
        const stats = this.relations.get(name);

        if (!stats) {
            throw new StatisticsError(
                `Statistics unavailable for ${name}`
            );
        }

        return stats;
    }

    isFresh(name, maxAgeMs = 86400000) {
        if (maxAgeMs < 0) {
            throw new ValidationError("Invalid statistics age.");
        }

        return Date.now() - this.get(name).analyzedAt <= maxAgeMs;
    }
}

// ============================================================
// 5. SELECTIVITY ESTIMATION
// ============================================================

class CardinalityEstimator {

    constructor(catalog) {
        this.catalog = catalog;
    }

    estimate(relationName, predicate) {
        const relation = this.catalog.get(relationName);
        const column = relation.columns.get(predicate.column);

        if (!column) {
            throw new ValidationError(
                `Unknown column ${predicate.column}.`
            );
        }

        switch (predicate.operator) {

            case "=": {
                if (predicate.value === null) {
                    return column.nullFraction;
                }

                if (column.mcv.has(String(predicate.value))) {
                    return column.mcv.get(String(predicate.value));
                }

                return (
                    (1 - column.nullFraction) / column.ndv
                );
            }

            case "<":
            case ">":
            case "BETWEEN": {
                if (!column.histogram) {
                    return predicate.operator === "BETWEEN"
                        ? 0.25
                        : 0.33;
                }

                const bounds = column.histogram;
                const low = predicate.operator === ">"
                    ? predicate.value
                    : predicate.operator === "BETWEEN"
                        ? predicate.value
                        : bounds[0];

                const high = predicate.operator === "<"
                    ? predicate.value
                    : predicate.operator === "BETWEEN"
                        ? predicate.upper
                        : bounds[bounds.length - 1];

                if (
                    !Number.isFinite(low) ||
                    !Number.isFinite(high) ||
                    low > high
                ) {
                    throw new ValidationError("Invalid range.");
                }

                const minimum = bounds[0];
                const maximum = bounds[bounds.length - 1];

                if (high <= minimum || low >= maximum) {
                    return 0;
                }

                return clamp(
                    (
                        Math.min(high, maximum)
                        - Math.max(low, minimum)
                    ) / (maximum - minimum)
                );
            }

            default:
                throw new ValidationError(
                    `Unsupported operator: ${predicate.operator}`
                );
        }
    }

    estimateRows(relationName, predicates) {
        const relation = this.catalog.get(relationName);

        const selectivity = predicates.reduce(
            (result, predicate) =>
                result * this.estimate(relationName, predicate),
            1
        );

        return relation.rows * selectivity;
    }
}

// ============================================================
// 6. PHYSICAL PLAN FACTORY
// ============================================================

function makePlan(operation, cost, rows, details = {}, children = []) {
    if (
        !Number.isFinite(cost) ||
        cost < 0 ||
        !Number.isFinite(rows) ||
        rows < 0
    ) {
        throw new OptimizerError("Invalid plan estimate.");
    }

    return Object.freeze({
        operation,
        cost,
        rows,
        details: Object.freeze({ ...details }),
        children: Object.freeze([...children])
    });
}

function explain(plan, depth = 0) {
    const indentation = "  ".repeat(depth);

    const details = Object.entries(plan.details)
        .map(([key, value]) => `${key}=${value}`)
        .join(", ");

    let output =
        `${indentation}${plan.operation} ` +
        `(cost=${plan.cost.toFixed(3)}, ` +
        `rows=${plan.rows.toFixed(2)})`;

    if (details) {
        output += `\n${indentation}  ${details}`;
    }

    for (const child of plan.children) {
        output += "\n" + explain(child, depth + 1);
    }

    return output;
}

// ============================================================
// 7. ACCESS PATH EVALUATION
// ============================================================

class AccessPathEvaluator {

    constructor(catalog, estimator, config = DEFAULT_COSTS) {
        this.catalog = catalog;
        this.estimator = estimator;
        this.config = Object.freeze({ ...config });
    }

    candidates(relationName, predicates) {
        const relation = this.catalog.get(relationName);
        const rows = this.estimator.estimateRows(
            relationName,
            predicates
        );

        const cfg = this.config;

        const sequentialCost =
            relation.pages * cfg.sequentialPage
            + relation.rows * cfg.tuple
            + relation.rows * predicates.length * cfg.operator;

        const candidates = [
            makePlan(
                ScanType.SEQUENTIAL,
                sequentialCost,
                rows,
                { relation: relationName }
            )
        ];

        for (const predicate of predicates) {
            const index = relation.indexes.get(predicate.column);

            if (!index || predicate.operator !== "=") {
                continue;
            }

            const height = Math.max(
                1,
                Math.ceil(Math.log2(index.pages + 1))
            );

            const heapPages = relation.rows === 0
                ? 0
                : rows * relation.pages / relation.rows;

            const indexCost =
                height * cfg.randomPage
                + heapPages * cfg.randomPage * cfg.cacheDiscount
                + rows * cfg.tuple;

            candidates.push(
                makePlan(
                    ScanType.INDEX,
                    indexCost,
                    rows,
                    {
                        relation: relationName,
                        index: predicate.column
                    }
                )
            );
        }

        return candidates.sort((a, b) => a.cost - b.cost);
    }
}

// ============================================================
// 8. JOIN PLANNING
// ============================================================

class JoinPlanner {

    constructor(catalog, accessPaths, config = DEFAULT_COSTS) {
        this.catalog = catalog;
        this.accessPaths = accessPaths;
        this.config = config;
    }

    estimateRows(leftRows, rightRows, join) {
        const leftColumn = this.catalog
            .get(join.left.relation)
            .columns.get(join.left.column);

        const rightColumn = this.catalog
            .get(join.right.relation)
            .columns.get(join.right.column);

        if (!leftColumn || !rightColumn) {
            throw new ValidationError("Invalid join column.");
        }

        return leftRows * rightRows /
            Math.max(leftColumn.ndv, rightColumn.ndv, 1);
    }

    buildCandidates(left, right, join) {
        const cfg = this.config;

        const rows = this.estimateRows(
            left.rows,
            right.rows,
            join
        );

        const hashBuild = Math.min(left.rows, right.rows);
        const hashProbe = Math.max(left.rows, right.rows);

        const hashCost =
            left.cost + right.cost
            + hashBuild * cfg.hashBuild
            + hashProbe * cfg.operator
            + (left.rows + right.rows) * cfg.tuple;

        const nestedCost =
            left.cost + right.cost
            + left.rows * right.rows * cfg.nestedLoop
            + rows * cfg.tuple;

        return [
            makePlan(
                JoinType.HASH,
                hashCost,
                rows,
                { buildRows: hashBuild.toFixed(2) },
                [left, right]
            ),
            makePlan(
                JoinType.NESTED_LOOP,
                nestedCost,
                rows,
                { outerRows: left.rows.toFixed(2) },
                [left, right]
            )
        ];
    }
}

// ============================================================
// 9. QUERY MODEL AND OPTIMIZATION
// ============================================================

class QueryOptimizer {

    constructor(catalog, config = DEFAULT_COSTS) {
        this.catalog = catalog;
        this.estimator = new CardinalityEstimator(catalog);

        this.accessPaths = new AccessPathEvaluator(
            catalog,
            this.estimator,
            config
        );

        this.joinPlanner = new JoinPlanner(
            catalog,
            this.accessPaths,
            config
        );
    }

    validate(query) {
        if (
            !Array.isArray(query.relations) ||
            query.relations.length === 0
        ) {
            throw new ValidationError("Query has no relations.");
        }

        if (query.relations.length > 10) {
            throw new ValidationError(
                "Greedy optimizer supports at most 10 relations."
            );
        }

        if (new Set(query.relations).size !== query.relations.length) {
            throw new ValidationError("Duplicate relation.");
        }

        for (const relation of query.relations) {
            this.catalog.get(relation);
        }

        for (const join of query.joins) {
            if (
                !query.relations.includes(join.left.relation) ||
                !query.relations.includes(join.right.relation)
            ) {
                throw new ValidationError(
                    "Join references an unknown relation."
                );
            }
        }
    }

    optimize(query) {
        this.validate(query);

        const pending = [...query.relations];

        const plans = new Map();

        for (const relation of pending) {
            const predicates = query.predicates[relation] || [];

            plans.set(
                relation,
                this.accessPaths.candidates(
                    relation,
                    predicates
                )[0]
            );
        }

        let connected = new Set([pending.shift()]);
        let current = plans.get([...connected][0]);

        while (pending.length > 0) {
            const candidates = [];

            for (const relation of pending) {
                for (const join of query.joins) {
                    const connects =
                        (
                            join.left.relation === relation &&
                            connected.has(join.right.relation)
                        ) ||
                        (
                            join.right.relation === relation &&
                            connected.has(join.left.relation)
                        );

                    if (!connects) continue;

                    const options = this.joinPlanner.buildCandidates(
                        current,
                        plans.get(relation),
                        join
                    );

                    candidates.push({
                        relation,
                        plan: options.reduce(
                            (best, item) =>
                                item.cost < best.cost ? item : best
                        )
                    });
                }
            }

            if (candidates.length === 0) {
                throw new ValidationError(
                    "Disconnected join graph."
                );
            }

            candidates.sort((a, b) => a.plan.cost - b.plan.cost);

            const selected = candidates[0];

            current = selected.plan;
            connected.add(selected.relation);

            pending.splice(
                pending.indexOf(selected.relation),
                1
            );
        }

        return current;
    }
}

// ============================================================
// 10. SAMPLE STATISTICS
// ============================================================

async function createCatalog() {
    const catalog = new StatisticsCatalog();

    catalog.on("statistics:registered", event => {
        console.log(
            `[CATALOG] Registered ${event.relation}, revision ${event.revision}`
        );
    });

    catalog.on("statistics:updated", event => {
        console.log(
            `[CATALOG] Updated ${event.relation}, revision ${event.revision}`
        );
    });

    const definitions = [
        new RelationStats({
            name: "customers",
            rows: 100000,
            pages: 1000,
            columns: [
                new ColumnStats({
                    name: "customer_id",
                    ndv: 100000
                }),
                new ColumnStats({
                    name: "region",
                    ndv: 10,
                    mcv: {
                        North: 0.35,
                        South: 0.25,
                        East: 0.20,
                        West: 0.15
                    }
                })
            ],
            indexes: [
                {
                    column: "customer_id",
                    pages: 250
                },
                {
                    column: "region",
                    pages: 80
                }
            ]
        }),

        new RelationStats({
            name: "orders",
            rows: 1000000,
            pages: 12000,
            columns: [
                new ColumnStats({
                    name: "order_id",
                    ndv: 1000000
                }),
                new ColumnStats({
                    name: "customer_id",
                    ndv: 100000
                }),
                new ColumnStats({
                    name: "status",
                    ndv: 4,
                    mcv: {
                        COMPLETED: 0.65,
                        PENDING: 0.20,
                        CANCELLED: 0.10,
                        FAILED: 0.05
                    }
                }),
                new ColumnStats({
                    name: "amount",
                    ndv: 50000,
                    histogram: [
                        0, 100, 250, 500, 1000, 5000, 10000
                    ]
                })
            ],
            indexes: [
                {
                    column: "customer_id",
                    pages: 2000
                },
                {
                    column: "status",
                    pages: 500
                },
                {
                    column: "order_id",
                    pages: 2500
                }
            ]
        }),

        new RelationStats({
            name: "payments",
            rows: 850000,
            pages: 9000,
            columns: [
                new ColumnStats({
                    name: "payment_id",
                    ndv: 850000
                }),
                new ColumnStats({
                    name: "order_id",
                    ndv: 800000
                }),
                new ColumnStats({
                    name: "payment_status",
                    ndv: 3,
                    mcv: {
                        SUCCESS: 0.80,
                        PENDING: 0.15,
                        FAILED: 0.05
                    }
                })
            ],
            indexes: [
                {
                    column: "order_id",
                    pages: 1800
                },
                {
                    column: "payment_id",
                    pages: 2000
                }
            ]
        })
    ];

    for (const definition of definitions) {
        await catalog.register(definition);
    }

    return catalog;
}

// ============================================================
// 11. TESTS
// ============================================================

async function runTests(catalog, optimizer) {
    const estimate = optimizer.estimator.estimate(
        "customers",
        {
            column: "region",
            operator: "=",
            value: "North"
        }
    );

    if (Math.abs(estimate - 0.35) > 1e-9) {
        throw new Error("MCV estimation test failed.");
    }

    const rows = optimizer.estimator.estimateRows(
        "customers",
        [
            {
                column: "region",
                operator: "=",
                value: "North"
            }
        ]
    );

    if (rows !== 35000) {
        throw new Error("Cardinality test failed.");
    }

    const alternatives = optimizer.accessPaths.candidates(
        "orders",
        [
            {
                column: "status",
                operator: "=",
                value: "COMPLETED"
            }
        ]
    );

    if (alternatives.length < 2) {
        throw new Error("Index alternative missing.");
    }

    try {
        new ColumnStats({
            name: "invalid",
            ndv: 0
        });
        throw new Error("Invalid statistics were accepted.");
    } catch (error) {
        if (!(error instanceof ValidationError)) {
            throw error;
        }
    }

    console.log("[TEST] All tests passed.");
}

// ============================================================
// 12. EXECUTION
// ============================================================

async function main() {
    const catalog = await createCatalog();

    const optimizer = new QueryOptimizer(catalog);

    await runTests(catalog, optimizer);

    const query = Object.freeze({
        relations: [
            "customers",
            "orders",
            "payments"
        ],

        predicates: {
            customers: [
                {
                    column: "region",
                    operator: "=",
                    value: "North"
                }
            ],

            orders: [
                {
                    column: "status",
                    operator: "=",
                    value: "COMPLETED"
                },
                {
                    column: "amount",
                    operator: "BETWEEN",
                    value: 100,
                    upper: 1000
                }
            ],

            payments: [
                {
                    column: "payment_status",
                    operator: "=",
                    value: "SUCCESS"
                }
            ]
        },

        joins: [
            {
                left: {
                    relation: "customers",
                    column: "customer_id"
                },
                right: {
                    relation: "orders",
                    column: "customer_id"
                }
            },
            {
                left: {
                    relation: "orders",
                    column: "order_id"
                },
                right: {
                    relation: "payments",
                    column: "order_id"
                }
            }
        ]
    });

    console.log("\nQUERY OPTIMIZATION");
    console.log("==================");

    for (const relation of query.relations) {
        const predicates = query.predicates[relation] || [];

        const alternatives = optimizer.accessPaths.candidates(
            relation,
            predicates
        );

        console.log(`\n${relation}`);
        console.log(
            `Estimated rows: ${alternatives[0].rows.toFixed(2)}`
        );

        for (const alternative of alternatives) {
            console.log(
                `${alternative.operation}: ${alternative.cost.toFixed(3)}`
            );
        }

        if (!catalog.isFresh(relation)) {
            console.warn(
                `[WARNING] Stale statistics: ${relation}`
            );
        }
    }

    const plan = optimizer.optimize(query);

    console.log("\nSELECTED EXECUTION PLAN");
    console.log("=======================");
    console.log(explain(plan));

    console.log("\nTOTAL COST:", plan.cost.toFixed(3));
    console.log("ESTIMATED ROWS:", plan.rows.toFixed(2));
}

main().catch(error => {
    console.error("[OPTIMIZER ERROR]", error.message);
    process.exitCode = 1;
});
