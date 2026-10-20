"use strict";

/*
 * PostgreSQL Views: complementary JavaScript model.
 *
 * This Node.js program models a reporting service that exposes two different
 * read semantics:
 *
 * 1. A dynamic projection evaluates current repository data on every request.
 * 2. A cached analytical projection is refreshed explicitly and can therefore
 *    become stale.
 *
 * The event-driven layer demonstrates why applications often separate query
 * interfaces from expensive analytical refresh jobs.
 */

const EventEmitter = require("node:events");
const crypto = require("node:crypto");

function assertNonEmpty(value, field) {
    if (typeof value !== "string" || value.trim() === "") {
        throw new TypeError(`${field} must be a non-empty string`);
    }
}

function assertNonNegativeInteger(value, field) {
    if (!Number.isInteger(value) || value < 0) {
        throw new TypeError(`${field} must be a non-negative integer`);
    }
}

class RepositoryStore extends EventEmitter {
    constructor() {
        super();
        this.repositories = new Map();
        this.pullRequests = new Map();
        this.reviews = [];
    }

    addRepository(name, team, active = true) {
        assertNonEmpty(name, "repository");
        assertNonEmpty(team, "team");

        if (this.repositories.has(name)) {
            throw new Error(`Repository already exists: ${name}`);
        }

        this.repositories.set(name, { name, team, active });
        this.emit("repository.changed", { repository: name });
    }

    addPullRequest(pr) {
        if (!Number.isInteger(pr.number) || pr.number <= 0) {
            throw new TypeError("Pull request number must be positive");
        }

        assertNonEmpty(pr.repository, "repository");
        assertNonEmpty(pr.author, "author");
        assertNonNegativeInteger(pr.additions, "additions");
        assertNonNegativeInteger(pr.deletions, "deletions");

        if (!this.repositories.has(pr.repository)) {
            throw new Error(`Unknown repository: ${pr.repository}`);
        }

        if (this.pullRequests.has(pr.number)) {
            throw new Error(`Pull request already exists: ${pr.number}`);
        }

        this.pullRequests.set(pr.number, {
            number: pr.number,
            repository: pr.repository,
            author: pr.author,
            state: pr.state,
            additions: pr.additions,
            deletions: pr.deletions,
            mergedAt: pr.mergedAt ?? null
        });

        this.emit("pull-request.changed", { number: pr.number });
    }

    addReview(review) {
        if (!this.pullRequests.has(review.pullRequest)) {
            throw new Error(`Unknown pull request: ${review.pullRequest}`);
        }

        assertNonEmpty(review.reviewer, "reviewer");

        const validStates = new Set([
            "APPROVED",
            "CHANGES_REQUESTED",
            "COMMENTED"
        ]);

        if (!validStates.has(review.state)) {
            throw new Error(`Invalid review state: ${review.state}`);
        }

        this.reviews.push({
            pullRequest: review.pullRequest,
            reviewer: review.reviewer,
            state: review.state
        });

        this.emit("review.changed", { pullRequest: review.pullRequest });
    }

    dynamicRepositoryView() {
        /*
         * This method deliberately recalculates its result. A PostgreSQL view
         * similarly stores the query definition rather than ordinary result
         * rows.
         */
        return [...this.repositories.values()].map((repository) => {
            const prs = [...this.pullRequests.values()].filter(
                (pr) => pr.repository === repository.name
            );

            return {
                repository: repository.name,
                team: repository.team,
                pullRequests: prs.length,
                merged: prs.filter((pr) => pr.mergedAt !== null).length,
                totalChanges: prs.reduce(
                    (sum, pr) => sum + pr.additions + pr.deletions,
                    0
                )
            };
        });
    }

    reviewView() {
        return [...this.pullRequests.values()].map((pr) => {
            const reviews = this.reviews.filter(
                (review) => review.pullRequest === pr.number
            );

            return {
                pullRequest: pr.number,
                repository: pr.repository,
                approvals: reviews.filter(
                    (review) => review.state === "APPROVED"
                ).length,
                changeRequests: reviews.filter(
                    (review) => review.state === "CHANGES_REQUESTED"
                ).length,
                comments: reviews.filter(
                    (review) => review.state === "COMMENTED"
                ).length
            };
        });
    }
}

class MaterializedReport {
    constructor(store) {
        this.store = store;
        this.snapshot = [];
        this.refreshedAt = null;
        this.refreshInProgress = false;
    }

    async refresh() {
        if (this.refreshInProgress) {
            throw new Error("Refresh already in progress");
        }

        this.refreshInProgress = true;

        try {
            /*
             * The asynchronous boundary represents a scheduled/background
             * refresh. The database equivalent is REFRESH MATERIALIZED VIEW.
             */
            await new Promise((resolve) => setTimeout(resolve, 10));

            const rows = this.store.dynamicRepositoryView();

            this.snapshot = rows.map((row) => {
                const prs = [...this.store.pullRequests.values()].filter(
                    (pr) => pr.repository === row.repository
                );

                const sizes = prs.map(
                    (pr) => pr.additions + pr.deletions
                );

                const averageChangeSize =
                    sizes.length === 0
                        ? 0
                        : sizes.reduce((a, b) => a + b, 0) / sizes.length;

                return {
                    ...row,
                    averageChangeSize: Number(
                        averageChangeSize.toFixed(2)
                    )
                };
            });

            this.refreshedAt = new Date();
            this.store.emit("report.refreshed", {
                refreshedAt: this.refreshedAt
            });
        } finally {
            this.refreshInProgress = false;
        }
    }

    read() {
        return this.snapshot.map((row) => ({ ...row }));
    }
}

function printRows(title, rows) {
    console.log(`\n${title}`);
    console.table(rows);
}

async function main() {
    const store = new RepositoryStore();
    const report = new MaterializedReport(store);

    store.on("pull-request.changed", ({ number }) => {
        console.log(`Event: pull request ${number} changed`);
    });

    store.on("report.refreshed", ({ refreshedAt }) => {
        console.log(`Event: materialized report refreshed at ${refreshedAt.toISOString()}`);
    });

    store.addRepository("payments-api", "platform");
    store.addRepository("customer-portal", "web");

    store.addPullRequest({
        number: 101,
        repository: "payments-api",
        author: "alice",
        state: "MERGED",
        additions: 180,
        deletions: 42,
        mergedAt: new Date(Date.now() - 86400000)
    });

    store.addPullRequest({
        number: 102,
        repository: "payments-api",
        author: "bob",
        state: "OPEN",
        additions: 70,
        deletions: 12
    });

    store.addPullRequest({
        number: 201,
        repository: "customer-portal",
        author: "carol",
        state: "MERGED",
        additions: 300,
        deletions: 100,
        mergedAt: new Date(Date.now() - 172800000)
    });

    store.addReview({
        pullRequest: 101,
        reviewer: "reviewer-a",
        state: "APPROVED"
    });

    store.addReview({
        pullRequest: 102,
        reviewer: "reviewer-b",
        state: "CHANGES_REQUESTED"
    });

    printRows("Dynamic repository view", store.dynamicRepositoryView());
    printRows("Review reporting view", store.reviewView());

    await report.refresh();
    printRows("Materialized report", report.read());

    /*
     * A new source row is visible to the dynamic view immediately. The
     * materialized snapshot intentionally remains unchanged until refresh.
     */
    store.addPullRequest({
        number: 103,
        repository: "payments-api",
        author: "diana",
        state: "MERGED",
        additions: 40,
        deletions: 10,
        mergedAt: new Date()
    });

    printRows(
        "Dynamic view after source change",
        store.dynamicRepositoryView()
    );

    printRows(
        "Materialized report before refresh",
        report.read()
    );

    await report.refresh();

    printRows(
        "Materialized report after refresh",
        report.read()
    );

    const reportHash = crypto
        .createHash("sha256")
        .update(JSON.stringify(report.read()))
        .digest("hex");

    console.log(`Snapshot integrity hash: ${reportHash}`);
    console.log(
        "A persisted reporting snapshot must be treated as potentially stale until refreshed."
    );
}

main().catch((error) => {
    console.error(`Application failure: ${error.message}`);
    process.exitCode = 1;
});
