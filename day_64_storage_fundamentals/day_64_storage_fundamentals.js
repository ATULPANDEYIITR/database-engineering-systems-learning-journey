'use strict';

const EventEmitter = require('node:events');
const crypto = require('node:crypto');

const PullRequestState = Object.freeze({
    DRAFT: 'draft',
    OPEN: 'open',
    CLOSED: 'closed',
    MERGED: 'merged'
});

const ReviewState = Object.freeze({
    COMMENTED: 'commented',
    APPROVED: 'approved',
    CHANGES_REQUESTED: 'changes_requested',
    DISMISSED: 'dismissed'
});

class Commit {
    constructor(sha, message, parentSha = null) {
        if (!sha || !message) {
            throw new Error('Commit SHA and message are required.');
        }
        this.sha = sha;
        this.message = message;
        this.parentSha = parentSha;
    }
}

class Branch {
    constructor(name, protectedBranch = false) {
        this.name = name;
        this.protected = protectedBranch;
        this.commits = [];
    }

    get head() {
        return this.commits.length ? this.commits[this.commits.length - 1].sha : null;
    }
}

class Review {
    constructor(reviewer, state, commitSha, comments = []) {
        if (!reviewer || !commitSha) {
            throw new Error('Reviewer and reviewed commit are required.');
        }
        if (!Object.values(ReviewState).includes(state)) {
            throw new Error(`Invalid review state: ${state}`);
        }
        this.reviewer = reviewer;
        this.state = state;
        this.commitSha = commitSha;
        this.comments = [...comments];
        this.dismissed = false;
    }
}

class PullRequest {
    constructor(number, source, target, title, author, baseHead, draft = false) {
        this.number = number;
        this.sourceBranch = source;
        this.targetBranch = target;
        this.title = title;
        this.author = author;
        this.baseHeadAtCreation = baseHead;
        this.draft = draft;
        this.state = draft ? PullRequestState.DRAFT : PullRequestState.OPEN;
        this.commits = [];
        this.reviews = [];
        this.checks = new Map();
        this.unresolvedConversations = 0;
        this.mergeStrategy = 'squash';
    }

    markReady() {
        if (!this.draft) {
            throw new Error('Pull request is already ready.');
        }
        this.draft = false;
        this.state = PullRequestState.OPEN;
    }

    addReview(review) {
        if (this.state !== PullRequestState.OPEN) {
            throw new Error('Only open pull requests can receive reviews.');
        }
        this.reviews.push(review);
    }

    addCheck(name, passed, required = true, message = '') {
        this.checks.set(name, { name, passed, required, message });
    }

    reopen() {
        if (this.state !== PullRequestState.CLOSED) {
            throw new Error('Only closed pull requests can be reopened.');
        }
        this.state = PullRequestState.OPEN;
    }

    close() {
        if (this.state === PullRequestState.MERGED) {
            throw new Error('Merged pull requests cannot be closed.');
        }
        this.state = PullRequestState.CLOSED;
    }
}

class Repository extends EventEmitter {
    constructor(name, owner) {
        super();
        this.name = name;
        this.owner = owner;
        this.branches = new Map();
        this.pullRequests = new Map();
        this.protection = new Map();
        this.nextNumber = 1;

        this.on('pullRequestCreated', pr =>
            console.log(`event: pull_request.created #${pr.number}`)
        );
        this.on('mergeRejected', data =>
            console.log(`event: merge.rejected #${data.number}`)
        );
        this.on('merged', pr =>
            console.log(`event: pull_request.merged #${pr.number}`)
        );
    }

    createBranch(name, protectedBranch = false) {
        if (this.branches.has(name)) {
            throw new Error(`Branch already exists: ${name}`);
        }
        const branch = new Branch(name, protectedBranch);
        this.branches.set(name, branch);
        return branch;
    }

    commit(branchName, sha, message) {
        const branch = this.branches.get(branchName);
        if (!branch) throw new Error(`Unknown branch: ${branchName}`);

        if (branch.commits.some(c => c.sha === sha)) {
            throw new Error(`Duplicate commit SHA: ${sha}`);
        }

        branch.commits.push(new Commit(sha, message, branch.head));
    }

    createPullRequest(sourceName, targetName, title, author, draft = false) {
        const source = this.branches.get(sourceName);
        const target = this.branches.get(targetName);

        if (!source || !target) throw new Error('Source and target branches must exist.');
        if (sourceName === targetName) throw new Error('Source and target must differ.');

        const pr = new PullRequest(
            this.nextNumber++,
            sourceName,
            targetName,
            title,
            author,
            target.head,
            draft
        );

        pr.commits = [...source.commits];
        this.pullRequests.set(pr.number, pr);
        this.emit('pullRequestCreated', pr);
        return pr;
    }

    configureProtection(branchName, policy) {
        if (!this.branches.has(branchName)) {
            throw new Error('Unknown branch.');
        }

        const defaults = {
            requiredReviews: 1,
            requiredChecks: new Set(),
            restrictDirectPush: true,
            restrictForcePush: true,
            requireConversations: true,
            requireLinearHistory: false,
            allowAdminBypass: false
        };

        this.protection.set(branchName, {
            ...defaults,
            ...policy,
            requiredChecks: new Set(policy.requiredChecks || [])
        });

        this.branches.get(branchName).protected = true;
    }

    evaluateMerge(prNumber, actor) {
        const pr = this.pullRequests.get(prNumber);
        if (!pr) throw new Error('Unknown pull request.');

        const reasons = [];
        const target = this.branches.get(pr.targetBranch);
        const source = this.branches.get(pr.sourceBranch);
        const policy = this.protection.get(pr.targetBranch);

        if (pr.state !== PullRequestState.OPEN) reasons.push('Pull request is not open.');
        if (pr.draft) reasons.push('Pull request is still a draft.');
        if (!pr.commits.length) reasons.push('Pull request has no changes.');

        if (!policy) return { eligible: reasons.length === 0, reasons };

        if (target.head !== pr.baseHeadAtCreation) {
            reasons.push('Target branch changed after the pull request was opened.');
        }

        const approvals = new Set();
        let changesRequested = false;

        for (const review of pr.reviews) {
            if (review.dismissed) continue;

            const currentReview =
                review.commitSha === source.head || review.commitSha === target.head;

            if (!currentReview) continue;

            if (review.state === ReviewState.APPROVED) {
                approvals.add(review.reviewer);
            } else if (review.state === ReviewState.CHANGES_REQUESTED) {
                changesRequested = true;
            }
        }

        if (changesRequested) {
            reasons.push('Active review requests changes.');
        }

        if (approvals.size < policy.requiredReviews) {
            reasons.push(`At least ${policy.requiredReviews} approval(s) are required.`);
        }

        for (const checkName of policy.requiredChecks) {
            const check = pr.checks.get(checkName);
            if (!check) reasons.push(`Missing required status check: ${checkName}.`);
            else if (!check.passed) reasons.push(`Failed required status check: ${checkName}.`);
        }

        if (policy.requireConversations && pr.unresolvedConversations > 0) {
            reasons.push('Unresolved review conversations remain.');
        }

        return { eligible: reasons.length === 0, reasons };
    }

    merge(prNumber, actor) {
        const pr = this.pullRequests.get(prNumber);
        const result = this.evaluateMerge(prNumber, actor);

        if (!result.eligible) {
            this.emit('mergeRejected', { number: prNumber, reasons: result.reasons });
            throw new Error(`Merge rejected: ${result.reasons.join(' ')}`);
        }

        const target = this.branches.get(pr.targetBranch);
        const source = this.branches.get(pr.sourceBranch);

        if (pr.mergeStrategy === 'squash') {
            const sha = crypto
                .createHash('sha256')
                .update(`${pr.number}:${pr.title}:${source.head}`)
                .digest('hex')
                .slice(0, 12);

            target.commits.push(
                new Commit(sha, `Squash: ${pr.title}`, target.head)
            );
        } else if (pr.mergeStrategy === 'merge') {
            target.commits.push(
                new Commit(
                    `merge-${pr.number}`,
                    `Merge pull request #${pr.number}: ${pr.title}`,
                    target.head
                )
            );
        }

        pr.state = PullRequestState.MERGED;
        this.emit('merged', pr);
    }
}

function main() {
    const repo = new Repository('storage-platform', 'platform-admin');

    repo.createBranch('main', true);
    repo.createBranch('feature/page-storage');

    repo.commit('main', 'a001', 'Initialize repository');
    repo.commit('feature/page-storage', 'a001', 'Initialize repository');
    repo.commit('feature/page-storage', 'b101', 'Implement page allocation');
    repo.commit('feature/page-storage', 'b102', 'Validate block boundaries');

    repo.configureProtection('main', {
        requiredReviews: 2,
        requiredChecks: ['unit-tests', 'storage-integrity'],
        restrictDirectPush: true,
        restrictForcePush: true,
        requireConversations: true
    });

    const pr = repo.createPullRequest(
        'feature/page-storage',
        'main',
        'Implement physical storage model',
        'developer-1'
    );

    pr.addCheck('unit-tests', true);
    pr.addCheck('storage-integrity', true);

    pr.addReview(new Review(
        'reviewer-1',
        ReviewState.APPROVED,
        'b102',
        ['Boundary validation is correct.']
    ));

    pr.addReview(new Review(
        'reviewer-2',
        ReviewState.APPROVED,
        'b102',
        ['Allocation behavior is bounded.']
    ));

    const evaluation = repo.evaluateMerge(pr.number, 'platform-admin');

    console.log(`PR #${pr.number}: ${pr.title}`);
    console.log(`Merge eligible: ${evaluation.eligible}`);

    if (!evaluation.eligible) {
        for (const reason of evaluation.reasons) {
            console.log(`- ${reason}`);
        }
    } else {
        repo.merge(pr.number, 'platform-admin');
        console.log(`Merged state: ${pr.state}`);
        console.log(`main HEAD: ${repo.branches.get('main').head}`);
    }

    try {
        if (repo.branches.get('main').protected) {
            throw new Error('Direct push denied by branch protection.');
        }
    } catch (error) {
        console.log(`Protection test: ${error.message}`);
    }
}

main();
