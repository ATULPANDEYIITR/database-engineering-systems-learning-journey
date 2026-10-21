"use strict";

/*
 * PostgreSQL functions often expose repository-governance rules as callable
 * database operations. This JavaScript model mirrors that idea at the
 * application boundary: domain events update state, while policy evaluation
 * remains a separate operation.
 */

const PRState = Object.freeze({
  DRAFT: "draft",
  OPEN: "open",
  CLOSED: "closed",
  MERGED: "merged",
});

const ReviewState = Object.freeze({
  COMMENTED: "commented",
  APPROVED: "approved",
  CHANGES_REQUESTED: "changes_requested",
  DISMISSED: "dismissed",
});

class GovernanceError extends Error {
  constructor(message) {
    super(message);
    this.name = "GovernanceError";
  }
}

class Repository {
  constructor(name) {
    this.name = name;
    this.branches = new Map();
    this.pullRequests = new Map();
    this.listeners = new Map();
  }

  addBranch(name, protection = null) {
    if (!/^[A-Za-z0-9._/-]+$/.test(name) || name.includes("..")) {
      throw new GovernanceError(`Invalid branch name: ${name}`);
    }

    this.branches.set(name, {
      name,
      revision: 1,
      protection,
    });
  }

  createPullRequest({
    number,
    sourceBranch,
    targetBranch,
    commits,
    draft = false,
  }) {
    const source = this.branches.get(sourceBranch);
    const target = this.branches.get(targetBranch);

    if (!source || !target) {
      throw new GovernanceError("Source and target branches must exist");
    }

    if (sourceBranch === targetBranch) {
      throw new GovernanceError("A pull request cannot target its own source branch");
    }

    if (!Array.isArray(commits) || commits.length === 0) {
      throw new GovernanceError("A pull request requires at least one commit");
    }

    const pr = {
      number,
      sourceBranch,
      targetBranch,
      commits: [...commits],
      reviews: [],
      checks: new Map(),
      openConversations: new Set(),
      draft,
      state: draft ? PRState.DRAFT : PRState.OPEN,
      baseRevision: target.revision,
    };

    if (this.pullRequests.has(number)) {
      throw new GovernanceError(`PR #${number} already exists`);
    }

    this.pullRequests.set(number, pr);
    this.emit("pull_request.created", pr);
    return pr;
  }

  on(event, listener) {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, []);
    }
    this.listeners.get(event).push(listener);
  }

  emit(event, payload) {
    for (const listener of this.listeners.get(event) ?? []) {
      listener(payload);
    }
  }

  markReady(number) {
    const pr = this.getPR(number);

    if (!pr.draft) {
      return;
    }

    pr.draft = false;
    pr.state = PRState.OPEN;
    this.emit("pull_request.ready", pr);
  }

  addReview(number, review) {
    const pr = this.getPR(number);

    if (pr.state !== PRState.OPEN) {
      throw new GovernanceError("Reviews require an open PR");
    }

    if (!pr.commits.some((commit) => commit.sha === review.commitSha)) {
      throw new GovernanceError("Review must reference a PR commit");
    }

    if (!Object.values(ReviewState).includes(review.state)) {
      throw new GovernanceError("Unknown review state");
    }

    if (!review.reviewer.trim()) {
      throw new GovernanceError("Reviewer name cannot be empty");
    }

    pr.reviews.push({
      reviewer: review.reviewer,
      state: review.state,
      commitSha: review.commitSha,
      submittedAt: Date.now(),
    });

    this.emit("review.submitted", review);
  }

  setStatus(number, name, passed) {
    const pr = this.getPR(number);

    if (typeof passed !== "boolean") {
      throw new GovernanceError("Status result must be boolean");
    }

    pr.checks.set(name, passed);
    this.emit("check.completed", {
      pullRequest: number,
      name,
      passed,
    });
  }

  openConversation(number, conversationId) {
    const pr = this.getPR(number);
    pr.openConversations.add(conversationId);
  }

  resolveConversation(number, conversationId) {
    const pr = this.getPR(number);
    pr.openConversations.delete(conversationId);
  }

  synchronize(number) {
    const pr = this.getPR(number);
    const target = this.branches.get(pr.targetBranch);

    if (pr.baseRevision === target.revision) {
      return false;
    }

    pr.baseRevision = target.revision;
    this.emit("pull_request.synchronized", pr);
    return true;
  }

  addCommit(number, commit) {
    const pr = this.getPR(number);

    if (pr.state !== PRState.OPEN) {
      throw new GovernanceError("Cannot update a closed or merged PR");
    }

    if (!commit?.sha || !commit?.message) {
      throw new GovernanceError("Commit requires sha and message");
    }

    pr.commits.push({
      sha: commit.sha,
      message: commit.message,
    });

    this.emit("pull_request.updated", pr);
  }

  getPR(number) {
    const pr = this.pullRequests.get(number);
    if (!pr) {
      throw new GovernanceError(`PR #${number} does not exist`);
    }
    return pr;
  }
}

function evaluatePolicy(repository, pr, eligibleReviewers) {
  const target = repository.branches.get(pr.targetBranch);
  const protection = target?.protection;
  const failures = [];

  if (!target) {
    failures.push("target branch does not exist");
    return failures;
  }

  if (!protection) {
    failures.push("target branch is not protected");
    return failures;
  }

  if (pr.state !== PRState.OPEN) {
    failures.push("PR is not open");
  }

  if (pr.draft) {
    failures.push("PR is still a draft");
  }

  if (pr.baseRevision !== target.revision) {
    failures.push("PR must be synchronized with the target branch");
  }

  for (const requiredCheck of protection.requiredChecks) {
    if (pr.checks.get(requiredCheck) !== true) {
      failures.push(`required check '${requiredCheck}' has not passed`);
    }
  }

  const latestByReviewer = new Map();

  for (const review of pr.reviews) {
    if (eligibleReviewers.has(review.reviewer)) {
      latestByReviewer.set(review.reviewer, review);
    }
  }

  const currentCommit = pr.commits.at(-1)?.sha;

  const approvals = [...latestByReviewer.values()].filter(
    (review) =>
      review.state === ReviewState.APPROVED &&
      review.commitSha === currentCommit
  );

  if (approvals.length < protection.requiredReviews) {
    failures.push(
      `${approvals.length} current approval(s), ` +
      `${protection.requiredReviews} required`
    );
  }

  if (
    protection.requireConversationResolution &&
    pr.openConversations.size > 0
  ) {
    failures.push("unresolved review conversations remain");
  }

  return failures;
}

function merge(repository, number, eligibleReviewers, strategy) {
  const pr = repository.getPR(number);
  const failures = evaluatePolicy(repository, pr, eligibleReviewers);

  if (failures.length > 0) {
    throw new GovernanceError(
      `Merge blocked for PR #${number}: ${failures.join("; ")}`
    );
  }

  const target = repository.branches.get(pr.targetBranch);

  if (
    target.protection.requireLinearHistory &&
    strategy === "merge_commit"
  ) {
    throw new GovernanceError("Linear-history protection rejects merge commits");
  }

  pr.state = PRState.MERGED;
  pr.mergeStrategy = strategy;
  target.revision += 1;

  repository.emit("pull_request.merged", {
    number,
    strategy,
    targetRevision: target.revision,
  });
}

function main() {
  const repository = new Repository("orders-platform");

  repository.addBranch("main", {
    requiredReviews: 2,
    requiredChecks: ["tests", "security"],
    requireConversationResolution: true,
    requireLinearHistory: true,
  });

  repository.addBranch("feature/order-guard");

  repository.on("pull_request.merged", (event) => {
    console.log(
      `PR #${event.number} merged with ${event.strategy}; ` +
      `main revision is ${event.targetRevision}`
    );
  });

  const pr = repository.createPullRequest({
    number: 52,
    sourceBranch: "feature/order-guard",
    targetBranch: "main",
    commits: [
      { sha: "c001", message: "Validate order ownership" },
      { sha: "c002", message: "Reject duplicate requests" },
    ],
  });

  repository.openConversation(pr.number, "conversation-7");

  repository.addReview(pr.number, {
    reviewer: "security-reviewer",
    state: ReviewState.APPROVED,
    commitSha: "c002",
  });

  repository.addReview(pr.number, {
    reviewer: "platform-reviewer",
    state: ReviewState.APPROVED,
    commitSha: "c002",
  });

  repository.setStatus(pr.number, "tests", true);
  repository.setStatus(pr.number, "security", true);

  let failures = evaluatePolicy(
    repository,
    pr,
    new Set(["security-reviewer", "platform-reviewer"])
  );

  console.log("Before conversation resolution:", failures);

  repository.resolveConversation(pr.number, "conversation-7");

  failures = evaluatePolicy(
    repository,
    pr,
    new Set(["security-reviewer", "platform-reviewer"])
  );

  console.log("After conversation resolution:", failures);

  repository.addCommit(pr.number, {
    sha: "c003",
    message: "Improve duplicate request handling",
  });

  failures = evaluatePolicy(
    repository,
    pr,
    new Set(["security-reviewer", "platform-reviewer"])
  );

  console.log("After new commit:", failures);

  repository.addReview(pr.number, {
    reviewer: "security-reviewer",
    state: ReviewState.APPROVED,
    commitSha: "c003",
  });

  repository.addReview(pr.number, {
    reviewer: "platform-reviewer",
    state: ReviewState.APPROVED,
    commitSha: "c003",
  });

  merge(
    repository,
    pr.number,
    new Set(["security-reviewer", "platform-reviewer"]),
    "squash"
  );
}

try {
  main();
} catch (error) {
  if (error instanceof GovernanceError) {
    console.error(`Governance error: ${error.message}`);
    process.exitCode = 1;
  } else {
    throw error;
  }
}
