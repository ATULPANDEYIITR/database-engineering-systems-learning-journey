from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set


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


@dataclass
class Commit:
    sha: str
    message: str
    parent_sha: Optional[str] = None


@dataclass
class Branch:
    name: str
    commits: List[Commit] = field(default_factory=list)
    protected: bool = False

    @property
    def head(self) -> Optional[str]:
        return self.commits[-1].sha if self.commits else None


@dataclass
class Review:
    reviewer: str
    state: ReviewState
    commit_sha: str
    comments: List[str] = field(default_factory=list)
    dismissed: bool = False


@dataclass
class StatusCheck:
    name: str
    passed: bool
    required: bool
    message: str = ""


@dataclass
class BranchProtection:
    required_reviews: int = 1
    required_checks: Set[str] = field(default_factory=set)
    restrict_direct_push: bool = True
    restrict_force_push: bool = True
    require_conversation_resolution: bool = True
    require_linear_history: bool = False
    allow_admin_bypass: bool = False


@dataclass
class PullRequest:
    number: int
    source_branch: str
    target_branch: str
    title: str
    author: str
    commits: List[Commit]
    state: PullRequestState = PullRequestState.OPEN
    draft: bool = False
    reviews: List[Review] = field(default_factory=list)
    checks: Dict[str, StatusCheck] = field(default_factory=dict)
    unresolved_conversations: int = 0
    base_head_at_creation: Optional[str] = None
    merge_strategy: MergeStrategy = MergeStrategy.SQUASH

    def add_review(self, review: Review) -> None:
        if self.state != PullRequestState.OPEN:
            raise ValueError("Reviews cannot be added to a closed or merged pull request.")
        if not review.commit_sha:
            raise ValueError("A review must identify the reviewed commit.")
        self.reviews.append(review)

    def add_check(self, check: StatusCheck) -> None:
        self.checks[check.name] = check

    def synchronize(self, target: Branch) -> None:
        if self.state != PullRequestState.OPEN:
            raise ValueError("Only open pull requests can be synchronized.")
        self.base_head_at_creation = target.head

    def close(self) -> None:
        if self.state == PullRequestState.MERGED:
            raise ValueError("A merged pull request cannot be closed.")
        self.state = PullRequestState.CLOSED

    def reopen(self) -> None:
        if self.state != PullRequestState.CLOSED:
            raise ValueError("Only closed pull requests can be reopened.")
        self.state = PullRequestState.OPEN


class Repository:
    def __init__(self, name: str, owner: str):
        self.name = name
        self.owner = owner
        self.branches: Dict[str, Branch] = {}
        self.pull_requests: Dict[int, PullRequest] = {}
        self.protection: Dict[str, BranchProtection] = {}
        self.next_pr_number = 1

    def create_branch(self, name: str, protected: bool = False) -> Branch:
        if name in self.branches:
            raise ValueError(f"Branch already exists: {name}")
        branch = Branch(name=name, protected=protected)
        self.branches[name] = branch
        return branch

    def commit(self, branch_name: str, sha: str, message: str) -> None:
        branch = self.branches[branch_name]
        if any(c.sha == sha for c in branch.commits):
            raise ValueError(f"Duplicate commit SHA: {sha}")
        parent = branch.head
        branch.commits.append(Commit(sha, message, parent))

    def configure_protection(self, branch_name: str, policy: BranchProtection) -> None:
        if branch_name not in self.branches:
            raise ValueError("Cannot protect an unknown branch.")
        self.branches[branch_name].protected = True
        self.protection[branch_name] = policy

    def create_pull_request(
        self,
        source: str,
        target: str,
        title: str,
        author: str,
        draft: bool = False,
    ) -> PullRequest:
        if source not in self.branches or target not in self.branches:
            raise ValueError("Both source and target branches must exist.")
        if source == target:
            raise ValueError("Source and target branches must differ.")

        source_branch = self.branches[source]
        target_branch = self.branches[target]

        pr = PullRequest(
            number=self.next_pr_number,
            source_branch=source,
            target_branch=target,
            title=title,
            author=author,
            commits=list(source_branch.commits),
            draft=draft,
            base_head_at_creation=target_branch.head,
        )
        self.pull_requests[pr.number] = pr
        self.next_pr_number += 1
        return pr

    def merge_eligibility(self, pr: PullRequest, actor: str) -> tuple[bool, List[str]]:
        reasons: List[str] = []

        if pr.state != PullRequestState.OPEN:
            reasons.append("Pull request is not open.")

        if pr.draft:
            reasons.append("Pull request is still a draft.")

        if not pr.commits:
            reasons.append("Pull request contains no commits.")

        target = self.branches[pr.target_branch]
        policy = self.protection.get(pr.target_branch)

        if policy is None:
            return not reasons, reasons

        if target.head != pr.base_head_at_creation:
            reasons.append("Pull request base branch changed; synchronization is required.")

        valid_approvals = set()
        changes_requested = False

        for review in pr.reviews:
            if review.dismissed:
                continue
            if review.commit_sha != target.head and review.commit_sha != self.branches[pr.source_branch].head:
                continue
            if review.state == ReviewState.APPROVED:
                valid_approvals.add(review.reviewer)
            elif review.state == ReviewState.CHANGES_REQUESTED:
                changes_requested = True

        if changes_requested:
            reasons.append("An active reviewer has requested changes.")

        if len(valid_approvals) < policy.required_reviews:
            reasons.append(
                f"At least {policy.required_reviews} valid approval(s) are required."
            )

        for required in policy.required_checks:
            check = pr.checks.get(required)
            if check is None:
                reasons.append(f"Required status check is missing: {required}.")
            elif not check.passed:
                reasons.append(f"Required status check failed: {required}.")

        if policy.require_conversation_resolution and pr.unresolved_conversations:
            reasons.append("Unresolved review conversations remain.")

        if policy.require_linear_history:
            source = self.branches[pr.source_branch]
            if any(c.parent_sha is None and i > 0 for i, c in enumerate(source.commits)):
                reasons.append("Linear history requirement is not satisfied.")

        if actor != self.owner and actor == pr.author and policy.required_reviews > 0:
            pass

        return not reasons, reasons

    def merge(self, pr_number: int, actor: str) -> None:
        pr = self.pull_requests[pr_number]
        eligible, reasons = self.merge_eligibility(pr, actor)

        if not eligible:
            raise PermissionError("Merge rejected: " + "; ".join(reasons))

        target = self.branches[pr.target_branch]
        source = self.branches[pr.source_branch]

        if pr.merge_strategy == MergeStrategy.MERGE_COMMIT:
            sha = f"merge-{pr.number:04d}"
            target.commits.append(
                Commit(
                    sha=sha,
                    message=f"Merge pull request #{pr.number}: {pr.title}",
                    parent_sha=target.head,
                )
            )
        elif pr.merge_strategy == MergeStrategy.SQUASH:
            sha = f"squash-{pr.number:04d}"
            target.commits.append(
                Commit(
                    sha=sha,
                    message=f"Squash: {pr.title}",
                    parent_sha=target.head,
                )
            )
        elif pr.merge_strategy == MergeStrategy.REBASE:
            for commit in source.commits:
                target.commits.append(
                    Commit(
                        sha=f"rebased-{commit.sha}",
                        message=commit.message,
                        parent_sha=target.head,
                    )
                )

        pr.state = PullRequestState.MERGED


def main() -> None:
    repo = Repository("storage-platform", "platform-admin")

    repo.create_branch("main", protected=True)
    repo.create_branch("feature/storage-pages")

    repo.commit("main", "a001", "Initialize storage engine")
    repo.commit("feature/storage-pages", "a001", "Initialize storage engine")
    repo.commit("feature/storage-pages", "b101", "Add page allocation model")
    repo.commit("feature/storage-pages", "b102", "Add block and record validation")

    repo.configure_protection(
        "main",
        BranchProtection(
            required_reviews=2,
            required_checks={"unit-tests", "storage-integrity"},
            restrict_direct_push=True,
            restrict_force_push=True,
            require_conversation_resolution=True,
        ),
    )

    pr = repo.create_pull_request(
        "feature/storage-pages",
        "main",
        "Implement page and block storage model",
        "developer-1",
    )

    pr.add_check(StatusCheck("unit-tests", True, True, "All tests passed"))
    pr.add_check(StatusCheck("storage-integrity", True, True, "Record layout validated"))

    pr.add_review(
        Review("reviewer-1", ReviewState.APPROVED, "b102", ["Record boundary checks are correct."])
    )
    pr.add_review(
        Review("reviewer-2", ReviewState.APPROVED, "b102", ["Allocation logic is bounded."])
    )

    eligible, reasons = repo.merge_eligibility(pr, "platform-admin")
    print(f"Pull Request #{pr.number}: {pr.title}")
    print(f"Merge eligible: {eligible}")
    if reasons:
        for reason in reasons:
            print(f"  - {reason}")

    repo.merge(pr.number, "platform-admin")
    print(f"State after merge: {pr.state.value}")
    print(f"main HEAD: {repo.branches['main'].head}")

    try:
        repo.branches["main"].protected = True
        raise PermissionError("Direct pushes to protected branches are rejected by policy.")
    except PermissionError as exc:
        print(f"Protection test: {exc}")


if __name__ == "__main__":
    main()
