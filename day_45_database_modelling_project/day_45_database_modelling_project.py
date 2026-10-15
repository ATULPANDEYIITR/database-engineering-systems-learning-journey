"""
Production-grade relational schema design laboratory.

This executable case study models a repository-governance platform with
repositories, branches, pull requests, commits, code reviews, approvals,
status checks, and branch-protection policies.

The in-memory domain model emphasizes relational integrity, explicit state
transitions, auditability, transaction-like merge validation, and separation
of workflow state from governance policy.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Iterable
import unittest
import uuid


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return str(uuid.uuid4())


class DomainError(Exception):
    """Base exception for rejected domain operations."""


class IntegrityError(DomainError):
    """Raised when an operation violates a domain integrity constraint."""


class InvalidTransitionError(DomainError):
    """Raised when an entity cannot enter a requested state."""


class PermissionDeniedError(DomainError):
    """Raised when an actor lacks permission for an operation."""


class PullRequestState(str, Enum):
    DRAFT = "draft"
    OPEN = "open"
    CLOSED = "closed"
    MERGED = "merged"


class ReviewState(str, Enum):
    COMMENTED = "commented"
    APPROVED = "approved"
    CHANGES_REQUESTED = "changes_requested"
    DISMISSED = "dismissed"


class CheckState(str, Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILURE = "failure"
    ERROR = "error"
    SKIPPED = "skipped"


class MergeStrategy(str, Enum):
    MERGE_COMMIT = "merge_commit"
    SQUASH = "squash"
    REBASE = "rebase"


@dataclass(frozen=True)
class Repository:
    id: str
    name: str
    default_branch: str
    archived: bool = False


@dataclass
class Branch:
    id: str
    repository_id: str
    name: str
    head_sha: str
    protected: bool = False
    deleted: bool = False


@dataclass(frozen=True)
class Commit:
    sha: str
    repository_id: str
    author_id: str
    message: str
    parent_shas: tuple[str, ...]
    created_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True)
class Reviewer:
    id: str
    display_name: str
    teams: frozenset[str] = frozenset()
    active: bool = True


@dataclass
class ReviewComment:
    id: str
    review_id: str
    body: str
    file_path: str | None = None
    line_number: int | None = None
    resolved: bool = False
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        if not self.body.strip():
            raise IntegrityError("Review comment cannot be empty.")
        if self.line_number is not None and self.line_number < 1:
            raise IntegrityError("Inline comment line must be positive.")
        if (self.file_path is None) != (self.line_number is None):
            raise IntegrityError(
                "Inline comments require both a file path and line number."
            )


@dataclass
class Review:
    id: str
    pull_request_id: str
    reviewer_id: str
    commit_sha: str
    state: ReviewState
    submitted_at: datetime = field(default_factory=utc_now)


@dataclass
class StatusCheck:
    id: str
    pull_request_id: str
    context: str
    commit_sha: str
    state: CheckState
    completed_at: datetime | None = None


@dataclass(frozen=True)
class BranchProtection:
    repository_id: str
    branch_name: str
    required_approvals: int = 1
    required_checks: frozenset[str] = frozenset()
    require_code_owner_review: bool = False
    require_conversation_resolution: bool = True
    require_linear_history: bool = False
    require_signed_commits: bool = False
    restrict_direct_pushes: bool = True
    prohibit_force_pushes: bool = True
    prohibit_deletion: bool = True
    dismiss_stale_approvals: bool = True
    require_up_to_date_branch: bool = True
    restrict_approvers_to_teams: frozenset[str] = frozenset()
    allow_administrator_bypass: bool = False
    allowed_merge_strategies: frozenset[MergeStrategy] = frozenset(
        {MergeStrategy.SQUASH}
    )

    def __post_init__(self) -> None:
        if self.required_approvals < 0:
            raise IntegrityError("Required approvals cannot be negative.")
        if not self.branch_name.strip():
            raise IntegrityError("Protected branch name cannot be empty.")
        if any(not context.strip() for context in self.required_checks):
            raise IntegrityError("Required check names cannot be empty.")
        if not self.allowed_merge_strategies:
            raise IntegrityError("At least one merge strategy is required.")


@dataclass
class PullRequest:
    id: str
    repository_id: str
    number: int
    author_id: str
    source_branch: str
    target_branch: str
    title: str
    state: PullRequestState
    base_sha: str
    head_sha: str
    draft: bool = False
    merged_sha: str | None = None
    merge_strategy: MergeStrategy | None = None
    created_at: datetime = field(default_factory=utc_now)
    closed_at: datetime | None = None
    merged_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.number < 1:
            raise IntegrityError("Pull request number must be positive.")
        if not self.title.strip():
            raise IntegrityError("Pull request title cannot be empty.")
        if self.source_branch == self.target_branch:
            raise IntegrityError("Source and target branches must differ.")
        if self.draft and self.state != PullRequestState.DRAFT:
            raise IntegrityError("Draft flag and pull request state disagree.")


@dataclass(frozen=True)
class AuditEvent:
    entity_type: str
    entity_id: str
    action: str
    actor_id: str
    details: str
    occurred_at: datetime = field(default_factory=utc_now)


@dataclass
class RepositoryStore:
    repositories: dict[str, Repository] = field(default_factory=dict)
    branches: dict[tuple[str, str], Branch] = field(default_factory=dict)
    commits: dict[str, Commit] = field(default_factory=dict)
    reviewers: dict[str, Reviewer] = field(default_factory=dict)
    pull_requests: dict[str, PullRequest] = field(default_factory=dict)
    reviews: dict[str, Review] = field(default_factory=dict)
    comments: dict[str, ReviewComment] = field(default_factory=dict)
    checks: dict[str, StatusCheck] = field(default_factory=dict)
    protections: dict[tuple[str, str], BranchProtection] = field(
        default_factory=dict
    )
    audit_events: list[AuditEvent] = field(default_factory=list)
    next_pr_number: dict[str, int] = field(default_factory=dict)

    def add_repository(self, repository: Repository) -> None:
        if repository.id in self.repositories:
            raise IntegrityError("Repository identifier already exists.")
        if any(
            item.name.lower() == repository.name.lower()
            for item in self.repositories.values()
        ):
            raise IntegrityError("Repository name must be unique.")
        if not repository.name.strip():
            raise IntegrityError("Repository name cannot be empty.")
        self.repositories[repository.id] = repository
        self.next_pr_number[repository.id] = 1

    def add_branch(self, branch: Branch) -> None:
        if branch.repository_id not in self.repositories:
            raise IntegrityError("Branch references an unknown repository.")
        key = (branch.repository_id, branch.name)
        if key in self.branches:
            raise IntegrityError("Branch name must be unique per repository.")
        if branch.head_sha not in self.commits:
            raise IntegrityError("Branch head must reference an existing commit.")
        if self.commits[branch.head_sha].repository_id != branch.repository_id:
            raise IntegrityError("Branch head belongs to another repository.")
        self.branches[key] = branch

    def add_commit(self, commit: Commit) -> None:
        if not commit.sha.strip():
            raise IntegrityError("Commit SHA cannot be empty.")
        if commit.sha in self.commits:
            raise IntegrityError("Commit SHA already exists.")
        if commit.repository_id not in self.repositories:
            raise IntegrityError("Commit references an unknown repository.")
        if not commit.author_id.strip() or not commit.message.strip():
            raise IntegrityError("Commit author and message are required.")
        for parent_sha in commit.parent_shas:
            parent = self.commits.get(parent_sha)
            if parent is None:
                raise IntegrityError("Commit parent does not exist.")
            if parent.repository_id != commit.repository_id:
                raise IntegrityError("Commit parent belongs to another repository.")
        self.commits[commit.sha] = commit

    def configure_protection(self, policy: BranchProtection) -> None:
        if policy.repository_id not in self.repositories:
            raise IntegrityError("Protection references an unknown repository.")
        branch = self.branches.get((policy.repository_id, policy.branch_name))
        if branch is None or branch.deleted:
            raise IntegrityError("Protected branch does not exist.")
        branch.protected = True
        self.protections[(policy.repository_id, policy.branch_name)] = policy

    def open_pull_request(
        self,
        repository_id: str,
        author_id: str,
        source_branch: str,
        target_branch: str,
        title: str,
        head_sha: str,
        draft: bool = False,
    ) -> PullRequest:
        repository = self.repositories.get(repository_id)
        if repository is None or repository.archived:
            raise IntegrityError("Repository is missing or archived.")

        source = self.branches.get((repository_id, source_branch))
        target = self.branches.get((repository_id, target_branch))
        if source is None or target is None or source.deleted or target.deleted:
            raise IntegrityError("Both branches must exist and be active.")
        if source_branch == target_branch:
            raise IntegrityError("A pull request cannot target its own source.")
        if source.head_sha != head_sha:
            raise IntegrityError("Pull request head must match the source branch.")
        if self.commits[head_sha].repository_id != repository_id:
            raise IntegrityError("Pull request head belongs to another repository.")

        number = self.next_pr_number[repository_id]
        self.next_pr_number[repository_id] = number + 1
        state = PullRequestState.DRAFT if draft else PullRequestState.OPEN
        pr = PullRequest(
            id=new_id(),
            repository_id=repository_id,
            number=number,
            author_id=author_id,
            source_branch=source_branch,
            target_branch=target_branch,
            title=title,
            state=state,
            base_sha=target.head_sha,
            head_sha=head_sha,
            draft=draft,
        )
        self.pull_requests[pr.id] = pr
        self.audit_events.append(
            AuditEvent("pull_request", pr.id, "opened", author_id, state.value)
        )
        return pr

    def publish_draft(self, pr_id: str, actor_id: str) -> None:
        pr = self._pull_request(pr_id)
        if pr.state != PullRequestState.DRAFT or not pr.draft:
            raise InvalidTransitionError("Only a draft can be published.")
        pr.state = PullRequestState.OPEN
        pr.draft = False
        self.audit_events.append(
            AuditEvent("pull_request", pr.id, "published", actor_id, "")
        )

    def add_review(
        self,
        pr_id: str,
        reviewer_id: str,
        state: ReviewState,
        commit_sha: str,
    ) -> Review:
        pr = self._pull_request(pr_id)
        reviewer = self.reviewers.get(reviewer_id)
        if reviewer is None or not reviewer.active:
            raise PermissionDeniedError("Reviewer is unknown or inactive.")
        if reviewer_id == pr.author_id:
            raise PermissionDeniedError("Pull request authors cannot approve their own changes.")
        if pr.state != PullRequestState.OPEN:
            raise InvalidTransitionError("Reviews require an open pull request.")
        if commit_sha not in self.commits:
            raise IntegrityError("Review commit does not exist.")
        if self.commits[commit_sha].repository_id != pr.repository_id:
            raise IntegrityError("Review commit belongs to another repository.")

        review = Review(new_id(), pr.id, reviewer_id, commit_sha, state)
        self.reviews[review.id] = review
        self.audit_events.append(
            AuditEvent("review", review.id, "submitted", reviewer_id, state.value)
        )
        return review

    def add_comment(
        self,
        review_id: str,
        body: str,
        file_path: str | None = None,
        line_number: int | None = None,
    ) -> ReviewComment:
        if review_id not in self.reviews:
            raise IntegrityError("Comment references an unknown review.")
        comment = ReviewComment(
            id=new_id(),
            review_id=review_id,
            body=body,
            file_path=file_path,
            line_number=line_number,
        )
        self.comments[comment.id] = comment
        return comment

    def add_check(
        self,
        pr_id: str,
        context: str,
        commit_sha: str,
        state: CheckState,
    ) -> StatusCheck:
        pr = self._pull_request(pr_id)
        if not context.strip():
            raise IntegrityError("Status-check context cannot be empty.")
        if commit_sha not in self.commits:
            raise IntegrityError("Check commit does not exist.")
        if self.commits[commit_sha].repository_id != pr.repository_id:
            raise IntegrityError("Check commit belongs to another repository.")
        check = StatusCheck(
            id=new_id(),
            pull_request_id=pr.id,
            context=context,
            commit_sha=commit_sha,
            state=state,
            completed_at=utc_now() if state != CheckState.PENDING else None,
        )
        self.checks[check.id] = check
        return check

    def resolve_comment(self, comment_id: str, actor_id: str) -> None:
        comment = self.comments.get(comment_id)
        if comment is None:
            raise IntegrityError("Comment does not exist.")
        if comment.resolved:
            return
        comment.resolved = True
        self.audit_events.append(
            AuditEvent("review_comment", comment.id, "resolved", actor_id, "")
        )

    def synchronize_with_base(self, pr_id: str, actor_id: str) -> None:
        pr = self._pull_request(pr_id)
        if pr.state not in {PullRequestState.OPEN, PullRequestState.DRAFT}:
            raise InvalidTransitionError("Only an active pull request can synchronize.")
        target = self.branches[(pr.repository_id, pr.target_branch)]
        source = self.branches[(pr.repository_id, pr.source_branch)]
        if source.head_sha != pr.head_sha:
            raise IntegrityError("Source branch and pull request head diverged.")
        pr.base_sha = target.head_sha
        self.audit_events.append(
            AuditEvent("pull_request", pr.id, "synchronized_base", actor_id, target.head_sha)
        )

    def reopen_pull_request(self, pr_id: str, actor_id: str) -> None:
        pr = self._pull_request(pr_id)
        if pr.state != PullRequestState.CLOSED:
            raise InvalidTransitionError("Only a closed, unmerged request can reopen.")
        if self.repositories[pr.repository_id].archived:
            raise IntegrityError("Archived repositories cannot reopen pull requests.")
        source = self.branches.get((pr.repository_id, pr.source_branch))
        target = self.branches.get((pr.repository_id, pr.target_branch))
        if source is None or target is None or source.deleted or target.deleted:
            raise IntegrityError("Source and target branches must still exist.")
        pr.state = PullRequestState.OPEN
        pr.closed_at = None
        self.audit_events.append(
            AuditEvent("pull_request", pr.id, "reopened", actor_id, "")
        )

    def close_pull_request(self, pr_id: str, actor_id: str) -> None:
        pr = self._pull_request(pr_id)
        if pr.state not in {PullRequestState.OPEN, PullRequestState.DRAFT}:
            raise InvalidTransitionError("Only an active request can be closed.")
        pr.state = PullRequestState.CLOSED
        pr.closed_at = utc_now()
        self.audit_events.append(
            AuditEvent("pull_request", pr.id, "closed", actor_id, "")
        )

    def active_approvals(self, pr: PullRequest) -> set[str]:
        policy = self.protections.get((pr.repository_id, pr.target_branch))
        latest: dict[str, Review] = {}
        for review in self.reviews.values():
            if review.pull_request_id != pr.id:
                continue
            previous = latest.get(review.reviewer_id)
            if previous is None or review.submitted_at > previous.submitted_at:
                latest[review.reviewer_id] = review

        approvals: set[str] = set()
        for reviewer_id, review in latest.items():
            if review.state != ReviewState.APPROVED:
                continue
            reviewer = self.reviewers.get(reviewer_id)
            if reviewer is None or not reviewer.active:
                continue
            if policy and policy.dismiss_stale_approvals and review.commit_sha != pr.head_sha:
                continue
            if policy and policy.restrict_approvers_to_teams:
                if not reviewer.teams.intersection(policy.restrict_approvers_to_teams):
                    continue
            approvals.add(reviewer_id)
        return approvals

    def merge_blockers(self, pr_id: str, strategy: MergeStrategy) -> list[str]:
        pr = self._pull_request(pr_id)
        blockers: list[str] = []

        if pr.state != PullRequestState.OPEN or pr.draft:
            blockers.append("Pull request must be published and open.")
            return blockers

        repository = self.repositories[pr.repository_id]
        if repository.archived:
            blockers.append("Repository is archived.")
            return blockers

        source = self.branches.get((pr.repository_id, pr.source_branch))
        target = self.branches.get((pr.repository_id, pr.target_branch))
        if source is None or target is None or source.deleted or target.deleted:
            blockers.append("Source and target branches must exist.")
            return blockers

        if source.head_sha != pr.head_sha:
            blockers.append("Pull request head differs from source branch head.")

        policy = self.protections.get((pr.repository_id, pr.target_branch))
        if policy is None:
            return blockers

        if strategy not in policy.allowed_merge_strategies:
            blockers.append(f"Merge strategy {strategy.value} is prohibited.")

        if policy.require_up_to_date_branch and target.head_sha != pr.base_sha:
            blockers.append("Target branch advanced; synchronize and re-evaluate.")

        approvals = self.active_approvals(pr)
        if len(approvals) < policy.required_approvals:
            blockers.append(
                f"Need {policy.required_approvals} eligible approvals; "
                f"found {len(approvals)}."
            )

        latest_checks: dict[str, StatusCheck] = {}
        for check in self.checks.values():
            if check.pull_request_id != pr.id or check.commit_sha != pr.head_sha:
                continue
            old = latest_checks.get(check.context)
            if old is None or (
                check.completed_at or datetime.min.replace(tzinfo=timezone.utc)
            ) > (
                old.completed_at or datetime.min.replace(tzinfo=timezone.utc)
            ):
                latest_checks[check.context] = check

        for context in sorted(policy.required_checks):
            check = latest_checks.get(context)
            if check is None:
                blockers.append(f"Required check '{context}' is missing for current head.")
            elif check.state != CheckState.SUCCESS:
                blockers.append(
                    f"Required check '{context}' is {check.state.value}."
                )

        unresolved = [
            comment
            for comment in self.comments.values()
            if comment.review_id in self.reviews
            and self.reviews[comment.review_id].pull_request_id == pr.id
            and not comment.resolved
        ]
        if policy.require_conversation_resolution and unresolved:
            blockers.append(f"{len(unresolved)} review comment(s) remain unresolved.")

        if policy.require_linear_history and strategy == MergeStrategy.MERGE_COMMIT:
            blockers.append("Merge commits are prohibited by linear-history policy.")

        if policy.require_signed_commits:
            blockers.append(
                "Signature verification requires trusted signature metadata, "
                "which this model does not store."
            )

        return blockers

    def merge_pull_request(
        self,
        pr_id: str,
        actor_id: str,
        strategy: MergeStrategy,
    ) -> str:
        pr = self._pull_request(pr_id)
        blockers = self.merge_blockers(pr_id, strategy)
        if blockers:
            raise DomainError("Merge rejected: " + " ".join(blockers))

        # This simulation uses a deterministic synthetic merge SHA. A real Git
        # host computes the object from the selected merge strategy and tree.
        merge_sha = f"merge-{pr.number}-{pr.head_sha[:12]}-{strategy.value}"
        target = self.branches[(pr.repository_id, pr.target_branch)]
        parent_shas = (target.head_sha, pr.head_sha)
        if merge_sha not in self.commits:
            self.add_commit(
                Commit(
                    sha=merge_sha,
                    repository_id=pr.repository_id,
                    author_id=actor_id,
                    message=f"Merge pull request #{pr.number}: {pr.title}",
                    parent_shas=parent_shas,
                )
            )

        # No domain mutation occurs until eligibility has been checked.
        target.head_sha = merge_sha
        pr.state = PullRequestState.MERGED
        pr.merged_sha = merge_sha
        pr.merge_strategy = strategy
        pr.merged_at = utc_now()
        self.audit_events.append(
            AuditEvent("pull_request", pr.id, "merged", actor_id, merge_sha)
        )
        return merge_sha

    def direct_push(self, repository_id: str, branch_name: str, actor_id: str, sha: str) -> None:
        branch = self.branches.get((repository_id, branch_name))
        if branch is None or branch.deleted:
            raise IntegrityError("Branch does not exist.")
        if sha not in self.commits:
            raise IntegrityError("Commit does not exist.")
        if self.commits[sha].repository_id != repository_id:
            raise IntegrityError("Commit belongs to another repository.")
        policy = self.protections.get((repository_id, branch_name))
        if policy and policy.restrict_direct_pushes:
            raise PermissionDeniedError("Direct pushes are prohibited by branch protection.")
        branch.head_sha = sha
        self.audit_events.append(
            AuditEvent("branch", branch.id, "direct_push", actor_id, sha)
        )

    def force_push(
        self, repository_id: str, branch_name: str, actor_id: str, sha: str
    ) -> None:
        branch = self.branches.get((repository_id, branch_name))
        if branch is None or branch.deleted:
            raise IntegrityError("Branch does not exist.")
        policy = self.protections.get((repository_id, branch_name))
        if policy and policy.prohibit_force_pushes:
            raise PermissionDeniedError("Force pushes are prohibited.")
        if sha not in self.commits or self.commits[sha].repository_id != repository_id:
            raise IntegrityError("Target commit is invalid.")
        branch.head_sha = sha
        self.audit_events.append(
            AuditEvent("branch", branch.id, "force_push", actor_id, sha)
        )

    def delete_branch(self, repository_id: str, branch_name: str, actor_id: str) -> None:
        branch = self.branches.get((repository_id, branch_name))
        if branch is None or branch.deleted:
            raise IntegrityError("Branch does not exist.")
        repository = self.repositories[repository_id]
        policy = self.protections.get((repository_id, branch_name))
        if branch_name == repository.default_branch:
            raise PermissionDeniedError("Default branch cannot be deleted.")
        if policy and policy.prohibit_deletion:
            raise PermissionDeniedError("Protected branch deletion is prohibited.")
        branch.deleted = True
        self.audit_events.append(
            AuditEvent("branch", branch.id, "deleted", actor_id, branch_name)
        )

    def _pull_request(self, pr_id: str) -> PullRequest:
        pr = self.pull_requests.get(pr_id)
        if pr is None:
            raise IntegrityError("Pull request does not exist.")
        return pr


def build_demo_store() -> tuple[RepositoryStore, PullRequest]:
    store = RepositoryStore()
    repository = Repository("repo-platform", "release-service", "main")
    store.add_repository(repository)

    store.add_commit(Commit("c100", repository.id, "developer", "Initial release", ()))
    store.add_commit(Commit("c110", repository.id, "developer", "Add rate limiting", ("c100",)))
    store.add_commit(Commit("c120", repository.id, "developer", "Harden request validation", ("c110",)))
    store.add_branch(Branch("branch-main", repository.id, "main", "c100"))
    store.add_branch(Branch("branch-feature", repository.id, "feature/rate-limit", "c120"))

    store.reviewers["reviewer-security"] = Reviewer(
        "reviewer-security", "Security Reviewer", frozenset({"security"})
    )
    store.reviewers["reviewer-maintainer"] = Reviewer(
        "reviewer-maintainer", "Service Maintainer", frozenset({"maintainers"})
    )

    store.configure_protection(
        BranchProtection(
            repository_id=repository.id,
            branch_name="main",
            required_approvals=2,
            required_checks=frozenset({"unit-tests", "security-scan"}),
            require_conversation_resolution=True,
            require_up_to_date_branch=True,
            restrict_approvers_to_teams=frozenset({"security", "maintainers"}),
            allowed_merge_strategies=frozenset({MergeStrategy.SQUASH}),
        )
    )

    pr = store.open_pull_request(
        repository.id,
        "developer",
        "feature/rate-limit",
        "main",
        "Add API rate limiting",
        "c120",
    )
    return store, pr


class RepositoryGovernanceTests(unittest.TestCase):
    def test_merge_blocked_until_policy_is_satisfied(self) -> None:
        store, pr = build_demo_store()
        blockers = store.merge_blockers(pr.id, MergeStrategy.SQUASH)
        self.assertTrue(any("approvals" in item for item in blockers))
        self.assertTrue(any("unit-tests" in item for item in blockers))

    def test_complete_governance_workflow(self) -> None:
        store, pr = build_demo_store()

        security_review = store.add_review(
            pr.id, "reviewer-security", ReviewState.APPROVED, "c120"
        )
        maintainer_review = store.add_review(
            pr.id, "reviewer-maintainer", ReviewState.APPROVED, "c120"
        )
        comment = store.add_comment(
            security_review.id,
            "Rate-limit configuration is validated at startup.",
            "src/rate_limit.py",
            42,
        )
        store.resolve_comment(comment.id, "reviewer-maintainer")

        store.add_check(pr.id, "unit-tests", "c120", CheckState.SUCCESS)
        store.add_check(pr.id, "security-scan", "c120", CheckState.SUCCESS)

        self.assertEqual(
            store.merge_blockers(pr.id, MergeStrategy.SQUASH), []
        )
        merge_sha = store.merge_pull_request(pr.id, "release-bot", MergeStrategy.SQUASH)
        self.assertTrue(merge_sha.startswith("merge-"))
        self.assertEqual(pr.state, PullRequestState.MERGED)
        self.assertEqual(store.branches[(pr.repository_id, "main")].head_sha, merge_sha)

    def test_author_cannot_approve_own_request(self) -> None:
        store, pr = build_demo_store()
        store.reviewers["developer"] = Reviewer("developer", "Developer")
        with self.assertRaises(PermissionDeniedError):
            store.add_review(pr.id, "developer", ReviewState.APPROVED, "c120")

    def test_direct_push_is_rejected(self) -> None:
        store, pr = build_demo_store()
        with self.assertRaises(PermissionDeniedError):
            store.direct_push(pr.repository_id, "main", "developer", "c110")

    def test_stale_approval_does_not_count(self) -> None:
        store, pr = build_demo_store()
        store.add_review(pr.id, "reviewer-security", ReviewState.APPROVED, "c110")
        self.assertNotIn("reviewer-security", store.active_approvals(pr))

    def test_duplicate_branch_is_rejected(self) -> None:
        store, pr = build_demo_store()
        with self.assertRaises(IntegrityError):
            store.add_branch(
                Branch("duplicate", pr.repository_id, "main", "c100")
            )


def main() -> None:
    store, pr = build_demo_store()
    print("Repository governance evaluation")
    print(f"Repository: {store.repositories[pr.repository_id].name}")
    print(f"Pull request: #{pr.number} {pr.title}")
    print(f"Source: {pr.source_branch} at {pr.head_sha}")
    print(f"Target: {pr.target_branch} at {pr.base_sha}")

    for blocker in store.merge_blockers(pr.id, MergeStrategy.SQUASH):
        print(f"BLOCKED: {blocker}")

    print("\nRunning governance tests")
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(
        RepositoryGovernanceTests
    )
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        raise SystemExit(1)


if __name__ == "__main__":
    main()
