from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Iterable


class PullRequestState(Enum):
    DRAFT = "draft"
    OPEN = "open"
    CLOSED = "closed"
    MERGED = "merged"


class ReviewState(Enum):
    COMMENTED = "commented"
    APPROVED = "approved"
    CHANGES_REQUESTED = "changes_requested"
    DISMISSED = "dismissed"


class MergeStrategy(Enum):
    MERGE_COMMIT = "merge_commit"
    SQUASH = "squash"
    REBASE = "rebase"


@dataclass(frozen=True)
class Commit:
    sha: str
    message: str
    author: str


@dataclass
class Review:
    reviewer: str
    state: ReviewState
    commit_sha: str
    comments: list[str] = field(default_factory=list)


@dataclass
class StatusCheck:
    name: str
    passed: bool


@dataclass
class PullRequest:
    number: int
    source_branch: str
    target_branch: str
    state: PullRequestState
    commits: list[Commit]
    reviews: list[Review] = field(default_factory=list)
    checks: list[StatusCheck] = field(default_factory=list)
    conversations_open: int = 0
    draft: bool = False
    base_revision: int = 1
    target_revision: int = 1
    merge_strategy: MergeStrategy | None = None


@dataclass(frozen=True)
class BranchProtection:
    branch: str
    required_reviews: int
    required_checks: tuple[str, ...]
    require_conversation_resolution: bool = True
    allow_force_push: bool = False
    allow_direct_push: bool = False
    require_linear_history: bool = False


@dataclass(frozen=True)
class Repository:
    name: str
    protected_branches: tuple[BranchProtection, ...]


class GovernanceError(Exception):
    """Raised when a repository operation violates workflow rules."""


def validate_branch_name(branch: str) -> None:
    if not branch or branch.startswith("/") or ".." in branch:
        raise GovernanceError("Invalid branch name")
    if branch.endswith(".lock") or " " in branch:
        raise GovernanceError("Branch names cannot contain spaces or end with .lock")


def request_review(pr: PullRequest, reviewer: str) -> None:
    if pr.state != PullRequestState.OPEN or pr.draft:
        raise GovernanceError("Reviews can only be requested on an active non-draft PR")
    if not reviewer.strip():
        raise GovernanceError("Reviewer must be non-empty")
    print(f"Review requested from {reviewer} for PR #{pr.number}")


def submit_review(
    pr: PullRequest,
    reviewer: str,
    state: ReviewState,
    commit_sha: str,
    comments: Iterable[str] = (),
) -> None:
    if pr.state != PullRequestState.OPEN:
        raise GovernanceError("Cannot review a closed or merged PR")
    if not any(commit.sha == commit_sha for commit in pr.commits):
        raise GovernanceError("Review must reference a commit belonging to the PR")

    if state == ReviewState.APPROVED and any(
        r.reviewer == reviewer and r.state == ReviewState.CHANGES_REQUESTED
        for r in pr.reviews
    ):
        raise GovernanceError(
            "A reviewer who previously requested changes must submit a new review"
        )

    pr.reviews.append(
        Review(
            reviewer=reviewer,
            state=state,
            commit_sha=commit_sha,
            comments=list(comments),
        )
    )


def synchronize_base(pr: PullRequest, current_target_revision: int) -> None:
    if current_target_revision < pr.target_revision:
        raise GovernanceError("Target branch revision cannot move backwards")

    pr.target_revision = current_target_revision
    pr.base_revision = current_target_revision
    print(f"PR #{pr.number} synchronized with target revision {current_target_revision}")


def resolve_conversation(pr: PullRequest) -> None:
    if pr.conversations_open > 0:
        pr.conversations_open -= 1


def _latest_approval_by_reviewer(pr: PullRequest) -> dict[str, Review]:
    latest: dict[str, Review] = {}
    for review in pr.reviews:
        latest[review.reviewer] = review
    return latest


def merge_eligibility(
    repository: Repository,
    pr: PullRequest,
    eligible_reviewers: set[str],
) -> tuple[bool, list[str]]:
    reasons: list[str] = []

    protection = next(
        (p for p in repository.protected_branches if p.branch == pr.target_branch),
        None,
    )

    if protection is None:
        reasons.append("Target branch has no explicit protection policy")

    if pr.state != PullRequestState.OPEN:
        reasons.append("Pull Request is not open")

    if pr.draft:
        reasons.append("Pull Request is still a draft")

    if not pr.commits:
        reasons.append("Pull Request contains no commits")

    if pr.base_revision != pr.target_revision:
        reasons.append("Pull Request is behind the target branch")

    if any(not check.passed for check in pr.checks):
        reasons.append("One or more status checks failed")

    if protection:
        latest_reviews = _latest_approval_by_reviewer(pr)

        valid_approvals = sum(
            1
            for reviewer, review in latest_reviews.items()
            if reviewer in eligible_reviewers
            and review.state == ReviewState.APPROVED
            and review.commit_sha == pr.commits[-1].sha
        )

        if valid_approvals < protection.required_reviews:
            reasons.append(
                f"Only {valid_approvals} current eligible approval(s); "
                f"{protection.required_reviews} required"
            )

        if protection.require_conversation_resolution and pr.conversations_open:
            reasons.append("Unresolved review conversations remain")

        for required in protection.required_checks:
            check = next((c for c in pr.checks if c.name == required), None)
            if check is None:
                reasons.append(f"Required status check '{required}' is missing")
            elif not check.passed:
                reasons.append(f"Required status check '{required}' failed")

    return not reasons, reasons


def merge_pull_request(
    repository: Repository,
    pr: PullRequest,
    eligible_reviewers: set[str],
    strategy: MergeStrategy,
) -> None:
    allowed, reasons = merge_eligibility(repository, pr, eligible_reviewers)
    if not allowed:
        raise GovernanceError("Merge blocked: " + "; ".join(reasons))

    protection = next(
        p for p in repository.protected_branches if p.branch == pr.target_branch
    )

    if protection.require_linear_history and strategy == MergeStrategy.MERGE_COMMIT:
        raise GovernanceError("Merge commits violate the linear-history policy")

    pr.merge_strategy = strategy
    pr.state = PullRequestState.MERGED
    print(f"PR #{pr.number} merged using {strategy.value}")


def close_pull_request(pr: PullRequest) -> None:
    if pr.state == PullRequestState.MERGED:
        raise GovernanceError("Merged PR cannot be closed")
    pr.state = PullRequestState.CLOSED


def reopen_pull_request(pr: PullRequest) -> None:
    if pr.state != PullRequestState.CLOSED:
        raise GovernanceError("Only closed PRs can be reopened")
    pr.state = PullRequestState.OPEN


def main() -> None:
    protection = BranchProtection(
        branch="main",
        required_reviews=2,
        required_checks=("unit-tests", "security-scan"),
        require_conversation_resolution=True,
        require_linear_history=True,
    )

    repository = Repository(
        name="payments-service",
        protected_branches=(protection,),
    )

    validate_branch_name("feature/payment-validation")

    commits = [
        Commit("a1b2c3", "Validate payment amount", "alice"),
        Commit("d4e5f6", "Add authorization guard", "alice"),
    ]

    pr = PullRequest(
        number=104,
        source_branch="feature/payment-validation",
        target_branch="main",
        state=PullRequestState.OPEN,
        commits=commits,
        conversations_open=1,
        base_revision=10,
        target_revision=10,
    )

    request_review(pr, "bob")
    request_review(pr, "carol")

    submit_review(
        pr,
        "bob",
        ReviewState.APPROVED,
        "d4e5f6",
        ["Authorization path is clear."],
    )
    submit_review(
        pr,
        "carol",
        ReviewState.APPROVED,
        "d4e5f6",
        ["Validation and error handling are acceptable."],
    )

    pr.checks.extend(
        [
            StatusCheck("unit-tests", True),
            StatusCheck("security-scan", True),
        ]
    )

    allowed, reasons = merge_eligibility(
        repository,
        pr,
        {"bob", "carol"},
    )
    print("Eligible:", allowed)
    if reasons:
        print("Reasons:", reasons)

    resolve_conversation(pr)

    # A stale approval is simulated by adding a new commit after approval.
    pr.commits.append(
        Commit("g7h8i9", "Handle duplicate payment request", "alice")
    )

    allowed, reasons = merge_eligibility(
        repository,
        pr,
        {"bob", "carol"},
    )
    print("After new commit:", allowed)
    print("Reasons:", reasons)

    # Reviewers must re-approve the current changeset.
    submit_review(pr, "bob", ReviewState.APPROVED, "g7h8i9")
    submit_review(pr, "carol", ReviewState.APPROVED, "g7h8i9")

    merge_pull_request(
        repository,
        pr,
        {"bob", "carol"},
        MergeStrategy.REBASE,
    )

    print("Final state:", pr.state.value)


if __name__ == "__main__":
    main()
