'use strict';

/*
 * PL/pgSQL learning companion:
 * Variables, control flow, and functions.
 *
 * This Node.js program uses an event-driven workflow to evaluate
 * Pull Requests. The structure complements the database implementation
 * by emphasizing callbacks, promises, Maps, classes, validation, and
 * asynchronous policy checks.
 */

const { EventEmitter } = require('node:events');
const crypto = require('node:crypto');

class WorkflowError extends Error {
    constructor(message) {
        super(message);
        this.name = 'WorkflowError';
    }
}

class PullRequest {
    constructor({
        number,
        title,
        sourceBranch,
        targetBranch,
        changedFiles,
        additions,
        deletions,
        requiredReviews,
        reviews = [],
        statusChecks = new Map()
    }) {
        this.number = number;
        this.title = title;
        this.sourceBranch = sourceBranch;
        this.targetBranch = targetBranch;
        this.changedFiles = changedFiles;
        this.additions = additions;
        this.deletions = deletions;
        this.requiredReviews = requiredReviews;
        this.reviews = reviews;
        this.statusChecks = statusChecks;
        this.state = 'OPEN';
        this.auditId = crypto.randomUUID();
    }
}

function validateBranchName(branchName) {
    if (typeof branchName !== 'string') {
        throw new TypeError('Branch name must be a string');
    }

    const normalized = branchName.trim();

    if (!normalized) {
        throw new WorkflowError('Branch name cannot be empty');
    }

    if (normalized.length > 100) {
        throw new WorkflowError('Branch name exceeds 100 characters');
    }

    if (/[;\0]/.test(normalized)) {
        throw new WorkflowError('Branch name contains an unsafe character');
    }

    return normalized;
}

function countApprovals(pullRequest) {
    let approvals = 0;

    for (const review of pullRequest.reviews) {
        if (review.state === 'APPROVED') {
            approvals += 1;
        }
    }

    return approvals;
}

function evaluatePullRequest(pullRequest) {
    const reasons = [];

    if (pullRequest.state !== 'OPEN') {
        reasons.push('Pull Request is not open');
    }

    if (pullRequest.sourceBranch === pullRequest.targetBranch) {
        reasons.push('source and target branches must differ');
    }

    if (pullRequest.changedFiles <= 0) {
        reasons.push('no changed files');
    }

    const approvals = countApprovals(pullRequest);

    if (approvals < pullRequest.requiredReviews) {
        reasons.push(
            `requires ${pullRequest.requiredReviews} approvals but has ${approvals}`
        );
    }

    if (pullRequest.statusChecks.size === 0) {
        reasons.push('no status checks recorded');
    }

    for (const [checkName, passed] of pullRequest.statusChecks) {
        if (!passed) {
            reasons.push(`status check failed: ${checkName}`);
        }
    }

    return {
        eligible: reasons.length === 0,
        reasons
    };
}

function calculateRisk(pullRequest) {
    let score = 0;

    if (pullRequest.changedFiles > 20) {
        score += 2;
    } else if (pullRequest.changedFiles > 10) {
        score += 1;
    }

    const lineDelta = Math.abs(
        pullRequest.additions - pullRequest.deletions
    );

    if (lineDelta > 500) {
        score += 2;
    } else if (lineDelta > 200) {
        score += 1;
    }

    if (pullRequest.reviews.length === 0) {
        score += 2;
    }

    if (score >= 4) return 'HIGH';
    if (score >= 2) return 'MEDIUM';
    return 'LOW';
}

function createStatusChecks(entries) {
    const checks = new Map();

    for (const [name, passed] of entries) {
        const normalized = String(name).trim().toLowerCase();

        if (normalized) {
            checks.set(normalized, Boolean(passed));
        }
    }

    return checks;
}

function mergePullRequest(pullRequest) {
    const evaluation = evaluatePullRequest(pullRequest);

    if (!evaluation.eligible) {
        throw new WorkflowError(evaluation.reasons.join('; '));
    }

    pullRequest.state = 'MERGED';
    return pullRequest;
}

function delay(milliseconds) {
    return new Promise(resolve => setTimeout(resolve, milliseconds));
}

async function runStatusCheck(name, pullRequest) {
    await delay(15);

    if (!name || pullRequest.changedFiles < 0) {
        throw new WorkflowError(`Invalid status-check request: ${name}`);
    }

    /*
     * A deterministic rule keeps this executable without external
     * services while still modeling asynchronous CI processing.
     */
    if (name === 'unit-tests') {
        return pullRequest.changedFiles <= 100;
    }

    if (name === 'lint') {
        return pullRequest.title.length >= 10;
    }

    if (name === 'security-scan') {
        return pullRequest.additions < 1000;
    }

    return true;
}

class RepositoryWorkflow extends EventEmitter {
    constructor() {
        super();
        this.pullRequests = new Map();
    }

    addPullRequest(pullRequest) {
        if (this.pullRequests.has(pullRequest.number)) {
            throw new WorkflowError(
                `Pull Request #${pullRequest.number} already exists`
            );
        }

        this.pullRequests.set(pullRequest.number, pullRequest);
        this.emit('pullRequest.created', pullRequest);
    }

    async executeChecks(pullRequest) {
        const checkNames = ['unit-tests', 'lint', 'security-scan'];

        for (const checkName of checkNames) {
            const passed = await runStatusCheck(checkName, pullRequest);
            pullRequest.statusChecks.set(checkName, passed);

            this.emit('statusCheck.completed', {
                pullRequest,
                checkName,
                passed
            });
        }
    }

    async merge(number) {
        const pullRequest = this.pullRequests.get(number);

        if (!pullRequest) {
            throw new WorkflowError(`Unknown Pull Request #${number}`);
        }

        await this.executeChecks(pullRequest);
        const merged = mergePullRequest(pullRequest);

        this.emit('pullRequest.merged', merged);
        return merged;
    }
}

function buildPullRequests() {
    return [
        new PullRequest({
            number: 201,
            title: 'Add branch governance policy',
            sourceBranch: validateBranchName('feature/governance'),
            targetBranch: validateBranchName('main'),
            changedFiles: 7,
            additions: 180,
            deletions: 35,
            requiredReviews: 2,
            reviews: [
                { reviewer: 'alice', state: 'APPROVED' },
                { reviewer: 'bob', state: 'APPROVED' }
            ]
        }),
        new PullRequest({
            number: 202,
            title: 'Change review workflow',
            sourceBranch: validateBranchName('feature/review-workflow'),
            targetBranch: validateBranchName('main'),
            changedFiles: 15,
            additions: 420,
            deletions: 80,
            requiredReviews: 2,
            reviews: [
                { reviewer: 'alice', state: 'APPROVED' }
            ]
        })
    ];
}

async function main() {
    const workflow = new RepositoryWorkflow();

    workflow.on('pullRequest.created', pr => {
        console.log(`Created PR #${pr.number}`);
    });

    workflow.on('statusCheck.completed', event => {
        console.log(
            `  ${event.checkName}: ${event.passed ? 'PASS' : 'FAIL'}`
        );
    });

    workflow.on('pullRequest.merged', pr => {
        console.log(`  PR #${pr.number} merged`);
    });

    for (const pullRequest of buildPullRequests()) {
        workflow.addPullRequest(pullRequest);
    }

    for (const pullRequest of workflow.pullRequests.values()) {
        console.log(`\nPR #${pullRequest.number}: ${pullRequest.title}`);
        console.log(`Risk: ${calculateRisk(pullRequest)}`);

        try {
            await workflow.merge(pullRequest.number);
        } catch (error) {
            if (error instanceof WorkflowError) {
                console.log(`Merge rejected: ${error.message}`);
            } else {
                console.error(`Unexpected failure: ${error.message}`);
            }
        }
    }

    console.log('\nFinal states:');

    for (const pullRequest of workflow.pullRequests.values()) {
        const result = evaluatePullRequest(pullRequest);
        console.log(
            `PR #${pullRequest.number}: ${pullRequest.state}; ` +
            `currently eligible=${result.eligible}`
        );
    }
}

main().catch(error => {
    console.error(`Fatal workflow error: ${error.message}`);
    process.exitCode = 1;
});
