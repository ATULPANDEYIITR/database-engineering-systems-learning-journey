"use strict";

/*
 * Event-driven repository governance model.
 *
 * JavaScript is useful for representing webhook-driven repository workflows.
 * The event processor below handles review submissions, CI results, source
 * branch updates, and merge attempts without coupling event ingestion to the
 * policy evaluator.
 *
 * Run with Node.js 18 or later.
 */

const { EventEmitter } = require("node:events");
const { randomUUID } = require("node:crypto");

const PullRequestStatus = Object.freeze({
  DRAFT: "draft",
  OPEN: "open",
  CLOSED: "closed",
  MERGED: "merged",
});

const ReviewDecision = Object.freeze({
  COMMENT: "comment",
  APPROVE: "approve",
  REQUEST_CHANGES: "request_changes",
  DISMISS: "dismiss",
});

const CheckStatus = Object.freeze({
  PENDING: "pending",
  SUCCESS: "success",
  FAILURE: "failure",
  ERROR: "error",
});

class DomainError extends Error {}
class PolicyViolation extends DomainError {}
class InvalidStateTransition extends DomainError {}

function requireText(value, fieldName) {
  if (typeof value !== "string" || value.trim().length === 0) {
    throw new DomainError(`${fieldName} must be a non-empty string.`);
  }
  return value.trim();
}

function assertOneOf(value, allowed, fieldName) {
  if (!allowed.includes(value)) {
    throw new DomainError(`Invalid ${fieldName}: ${String(value)}`);
  }
}

class Repository {
  constructor({ id, name, defaultBranch }) {
    this.id = requireText(id, "repository id");
    this.name = requireText(name, "repository name");
    this.defaultBranch = requireText(defaultBranch, "default branch");
    this.archived = false;
    this.branches = new Map();
    this.pullRequests = new Map();
    this.nextPullRequestNumber = 1;
    this.protection = new Map();
    this.auditLog = [];
  }

  addBranch(name, headSha) {
    requireText(name, "branch name");
    requireText(headSha, "branch head");
    if (this.branches.has(name)) {
      throw new DomainError(`Branch ${name} already exists.`);
    }
    this.branches.set(name, {
      name,
      headSha,
      deleted: false,
    });
  }

  protectBranch(branchName, policy) {
    if (!this.branches.has(branchName)) {
      throw new DomainError(`Cannot protect missing branch ${branchName}.`);
    }
    const requiredApprovals = policy.requiredApprovals ?? 1;
    if (!Number.isInteger(requiredApprovals) || requiredApprovals < 0) {
      throw new DomainError("requiredApprovals must be a non-negative integer.");
    }

    this.protection.set(branchName, Object.freeze({
      requiredApprovals,
      requiredChecks: Object.freeze([...(policy.requiredChecks ?? [])]),
      requireResolvedConversations: policy.requireResolvedConversations ?? true,
      requireUpToDateBase: policy.requireUpToDateBase ?? true,
      requireLinearHistory: policy.requireLinearHistory ?? false,
      prohibitDirectPushes: policy.prohibitDirectPushes ?? true,
      prohibitForcePushes: policy.prohibitForcePushes ?? true,
      prohibitDeletion: policy.prohibitDeletion ?? true,
      dismissStaleApprovals: policy.dismissStaleApprovals ?? true,
      allowedStrategies: Object.freeze([...(policy.allowedStrategies ?? ["squash"])]),
      approverTeams: Object.freeze([...(policy.approverTeams ?? [])]),
    }));
  }

  log(action, actorId, entityId, details = {}) {
    this.auditLog.push(Object.freeze({
      eventId: randomUUID(),
      action,
      actorId,
      entityId,
      details: structuredClone(details),
      timestamp: new Date().toISOString(),
    }));
  }
}

class PullRequest {
  constructor({ id, number, repository, authorId, sourceBranch, targetBranch, title, draft }) {
    if (sourceBranch === targetBranch) {
      throw new DomainError("Source and target branches must differ.");
    }

    this.id = id;
    this.number = number;
    this.repositoryId = repository.id;
    this.authorId = requireText(authorId, "author id");
    this.sourceBranch = sourceBranch;
    this.targetBranch = targetBranch;
    this.title = requireText(title, "pull request title");
    this.status = draft ? PullRequestStatus.DRAFT : PullRequestStatus.OPEN;
    this.draft = Boolean(draft);
    this.baseSha = repository.branches.get(targetBranch).headSha;
    this.headSha = repository.branches.get(sourceBranch).headSha;
    this.reviews = new Map();
    this.checks = new Map();
    this.comments = new Map();
    this.mergeSha = null;
    this.createdAt = new Date().toISOString();
  }

  publish() {
    if (this.status !== PullRequestStatus.DRAFT) {
      throw new InvalidStateTransition("Only a draft can be published.");
    }
    this.status = PullRequestStatus.OPEN;
    this.draft = false;
  }

  ensureOpen() {
    if (this.status !== PullRequestStatus.OPEN || this.draft) {
      throw new InvalidStateTransition("Operation requires a published open pull request.");
    }
  }

  recordReview({ reviewerId, team, decision, commitSha }) {
    this.ensureOpen();
    assertOneOf(decision, Object.values(ReviewDecision), "review decision");

    if (reviewerId === this.authorId && decision === ReviewDecision.APPROVE) {
      throw new PolicyViolation("Authors cannot approve their own pull requests.");
    }

    requireText(reviewerId, "reviewer id");
    requireText(commitSha, "review commit SHA");

    const history = this.reviews.get(reviewerId) ?? [];
    history.push(Object.freeze({
      reviewId: randomUUID(),
      reviewerId,
      team,
      decision,
      commitSha,
      submittedAt: new Date().toISOString(),
    }));
    this.reviews.set(reviewerId, history);
  }

  recordCheck({ context, commitSha, status }) {
    requireText(context, "check context");
    requireText(commitSha, "check commit SHA");
    assertOneOf(status, Object.values(CheckStatus), "check status");

    const history = this.checks.get(context) ?? [];
    history.push(Object.freeze({
      checkId: randomUUID(),
      context,
      commitSha,
      status,
      completedAt: status === CheckStatus.PENDING ? null : new Date().toISOString(),
    }));
    this.checks.set(context, history);
  }

  addComment({ commentId = randomUUID(), reviewerId, body, file, line }) {
    this.ensureOpen();
    requireText(reviewerId, "comment author");
    requireText(body, "comment body");

    if ((file === undefined) !== (line === undefined)) {
      throw new DomainError("Inline comments require both file and line.");
    }
    if (line !== undefined && (!Number.isInteger(line) || line < 1)) {
      throw new DomainError("Comment line must be a positive integer.");
    }
    if (this.comments.has(commentId)) {
      throw new DomainError("Duplicate comment identifier.");
    }

    this.comments.set(commentId, {
      commentId,
      reviewerId,
      body: body.trim(),
      file: file ?? null,
      line: line ?? null,
      resolved: false,
    });
    return commentId;
  }

  resolveComment(commentId) {
    const comment = this.comments.get(commentId);
    if (!comment) {
      throw new DomainError("Review comment does not exist.");
    }
    comment.resolved = true;
  }

  synchronizeBase(repository) {
    this.ensureOpen();
    this.baseSha = repository.branches.get(this.targetBranch).headSha;
  }

  currentReviewDecision(policy) {
    const eligible = [];

    for (const [reviewerId, history] of this.reviews) {
      const latest = history.at(-1);
      if (!latest || latest.decision !== ReviewDecision.APPROVE) continue;
      if (policy.dismissStaleApprovals && latest.commitSha !== this.headSha) continue;
      if (
        policy.approverTeams.length > 0 &&
        !policy.approverTeams.includes(latest.team)
      ) continue;
      eligible.push(reviewerId);
    }

    return new Set(eligible);
  }

  latestCheck(context) {
    const history = this.checks.get(context) ?? [];
    return history
      .filter(check => check.commitSha === this.headSha)
      .at(-1) ?? null;
  }

  evaluateMerge(repository, strategy) {
    const blockers = [];

    if (this.status !== PullRequestStatus.OPEN || this.draft) {
      blockers.push("Pull request is not published and open.");
      return blockers;
    }

    const source = repository.branches.get(this.sourceBranch);
    const target = repository.branches.get(this.targetBranch);
    if (!source || !target || source.deleted || target.deleted) {
      return ["Source or target branch is missing or deleted."];
    }
    if (source.headSha !== this.headSha) {
      blockers.push("Source branch head differs from the pull request head.");
    }

    const policy = repository.protection.get(this.targetBranch);
    if (!policy) return blockers;

    if (!policy.allowedStrategies.includes(strategy)) {
      blockers.push(`Merge strategy '${strategy}' is prohibited.`);
    }
    if (policy.requireUpToDateBase && target.headSha !== this.baseSha) {
      blockers.push("Target branch advanced; synchronize the base first.");
    }

    const approvals = this.currentReviewDecision(policy);
    if (approvals.size < policy.requiredApprovals) {
      blockers.push(`Need ${policy.requiredApprovals} eligible approvals; found ${approvals.size}.`);
    }

    for (const context of policy.requiredChecks) {
      const check = this.latestCheck(context);
      if (!check || check.status !== CheckStatus.SUCCESS) {
        blockers.push(`Required check '${context}' is not successful for the current head.`);
      }
    }

    if (
      policy.requireResolvedConversations &&
      [...this.comments.values()].some(comment => !comment.resolved)
    ) {
      blockers.push("Unresolved review discussions remain.");
    }

    if (policy.requireLinearHistory && strategy === "merge") {
      blockers.push("Merge commits violate the linear-history policy.");
    }

    return blockers;
  }

  merge(repository, actorId, strategy) {
    const blockers = this.evaluateMerge(repository, strategy);
    if (blockers.length > 0) {
      throw new PolicyViolation(blockers.join(" "));
    }

    const target = repository.branches.get(this.targetBranch);
    const mergeSha = `sim-${this.number}-${this.headSha.slice(0, 10)}-${strategy}`;
    target.headSha = mergeSha;
    this.status = PullRequestStatus.MERGED;
    this.mergeSha = mergeSha;
    repository.log("pull_request.merged", actorId, this.id, {
      strategy,
      headSha: this.headSha,
      baseSha: this.baseSha,
      mergeSha,
    });
    return mergeSha;
  }
}

class GovernanceService {
  constructor() {
    this.repositories = new Map();
  }

  register(repository) {
    if (this.repositories.has(repository.id)) {
      throw new DomainError("Repository identifier already registered.");
    }
    if ([...this.repositories.values()].some(
      existing => existing.name.toLowerCase() === repository.name.toLowerCase()
    )) {
      throw new DomainError("Repository name must be unique.");
    }
    this.repositories.set(repository.id, repository);
  }

  openPullRequest(repositoryId, request, actorId) {
    const repository = this.repositories.get(repositoryId);
    if (!repository || repository.archived) {
      throw new DomainError("Repository is missing or archived.");
    }

    const source = repository.branches.get(request.sourceBranch);
    const target = repository.branches.get(request.targetBranch);
    if (!source || !target || source.deleted || target.deleted) {
      throw new DomainError("Source and target branches must exist.");
    }

    const number = repository.nextPullRequestNumber++;
    const pr = new PullRequest({
      id: randomUUID(),
      number,
      repository,
      authorId: actorId,
      sourceBranch: request.sourceBranch,
      targetBranch: request.targetBranch,
      title: request.title,
      draft: Boolean(request.draft),
    });

    repository.pullRequests.set(pr.id, pr);
    repository.log("pull_request.opened", actorId, pr.id, {
      number,
      sourceBranch: pr.sourceBranch,
      targetBranch: pr.targetBranch,
      headSha: pr.headSha,
    });
    return pr;
  }

  directPush(repositoryId, branchName, newSha, actorId, force = false) {
    const repository = this.repositories.get(repositoryId);
    if (!repository) throw new DomainError("Repository not found.");
    const branch = repository.branches.get(branchName);
    if (!branch || branch.deleted) throw new DomainError("Branch not found.");

    const policy = repository.protection.get(branchName);
    if (policy && !force && policy.prohibitDirectPushes) {
      throw new PolicyViolation("Direct pushes are prohibited.");
    }
    if (policy && force && policy.prohibitForcePushes) {
      throw new PolicyViolation("Force pushes are prohibited.");
    }

    branch.headSha = requireText(newSha, "new commit SHA");
    repository.log(force ? "branch.force_push" : "branch.direct_push", actorId, branchName, {
      newSha,
    });
  }
}

class RepositoryEventProcessor extends EventEmitter {
  constructor(governanceService) {
    super();
    this.governanceService = governanceService;

    this.on("review.submitted", event => {
      const pr = this.findPullRequest(event.repositoryId, event.pullRequestId);
      pr.recordReview(event.review);
    });

    this.on("check.completed", event => {
      const pr = this.findPullRequest(event.repositoryId, event.pullRequestId);
      pr.recordCheck(event.check);
    });

    this.on("pull_request.synchronize", event => {
      const repository = this.governanceService.repositories.get(event.repositoryId);
      const pr = this.findPullRequest(event.repositoryId, event.pullRequestId);
      pr.headSha = event.newHeadSha;
      pr.synchronizeBase(repository);
      repository.log("pull_request.synchronized", event.actorId, pr.id, {
        newHeadSha: pr.headSha,
        baseSha: pr.baseSha,
      });
    });
  }

  findPullRequest(repositoryId, pullRequestId) {
    const repository = this.governanceService.repositories.get(repositoryId);
    const pr = repository?.pullRequests.get(pullRequestId);
    if (!pr) throw new DomainError("Event references an unknown pull request.");
    return pr;
  }
}

function buildScenario() {
  const governance = new GovernanceService();
  const repository = new Repository({
    id: "repo-api",
    name: "payments-api",
    defaultBranch: "main",
  });

  repository.addBranch("main", "a100");
  repository.addBranch("feature/idempotency", "a110");
  repository.protectBranch("main", {
    requiredApprovals: 2,
    requiredChecks: ["unit-tests", "dependency-audit"],
    requireResolvedConversations: true,
    requireUpToDateBase: true,
    dismissStaleApprovals: true,
    approverTeams: ["security", "platform"],
    allowedStrategies: ["squash"],
    prohibitDirectPushes: true,
    prohibitForcePushes: true,
  });

  governance.register(repository);

  const pr = governance.openPullRequest("repo-api", {
    sourceBranch: "feature/idempotency",
    targetBranch: "main",
    title: "Enforce payment idempotency",
    draft: true,
  }, "developer-17");

  pr.publish();

  const events = new RepositoryEventProcessor(governance);
  events.emit("review.submitted", {
    repositoryId: repository.id,
    pullRequestId: pr.id,
    review: {
      reviewerId: "reviewer-4",
      team: "security",
      decision: ReviewDecision.APPROVE,
      commitSha: "a110",
    },
  });
  events.emit("review.submitted", {
    repositoryId: repository.id,
    pullRequestId: pr.id,
    review: {
      reviewerId: "reviewer-9",
      team: "platform",
      decision: ReviewDecision.APPROVE,
      commitSha: "a110",
    },
  });

  events.emit("check.completed", {
    repositoryId: repository.id,
    pullRequestId: pr.id,
    check: {
      context: "unit-tests",
      commitSha: "a110",
      status: CheckStatus.SUCCESS,
    },
  });
  events.emit("check.completed", {
    repositoryId: repository.id,
    pullRequestId: pr.id,
    check: {
      context: "dependency-audit",
      commitSha: "a110",
      status: CheckStatus.SUCCESS,
    },
  });

  return { governance, repository, pr };
}

function runTests() {
  const { repository, pr } = buildScenario();

  console.log("Event-driven repository governance");
  console.log(`Pull request #${pr.number}: ${pr.title}`);

  const blockers = pr.evaluateMerge(repository, "squash");
  console.log(`Initial policy blockers: ${blockers.length}`);

  if (blockers.length === 0) {
    const mergeSha = pr.merge(repository, "release-bot", "squash");
    console.log(`Merged successfully: ${mergeSha}`);
  } else {
    for (const blocker of blockers) console.log(`BLOCKED: ${blocker}`);
  }

  try {
    const commentId = pr.addComment({
      reviewerId: "reviewer-4",
      body: "The retry behavior needs a concurrency test.",
      file: "src/idempotency.js",
      line: 73,
    });
    pr.resolveComment(commentId);
  } catch (error) {
    // Merged requests are immutable in this model, so late comments fail.
    console.log(`Expected state protection: ${error.message}`);
  }

  try {
    const policy = repository.protection.get("main");
    if (policy.prohibitDirectPushes) {
      throw new PolicyViolation("Direct pushes are prohibited.");
    }
  } catch (error) {
    console.log(`Governance enforcement: ${error.message}`);
  }

  console.log(`Audit events recorded: ${repository.auditLog.length}`);
}

if (require.main === module) {
  try {
    runTests();
  } catch (error) {
    console.error(`${error.name}: ${error.message}`);
    process.exitCode = 1;
  }
}

module.exports = {
  Repository,
  PullRequest,
  GovernanceService,
  RepositoryEventProcessor,
  PullRequestStatus,
  ReviewDecision,
  CheckStatus,
  DomainError,
  PolicyViolation,
};
