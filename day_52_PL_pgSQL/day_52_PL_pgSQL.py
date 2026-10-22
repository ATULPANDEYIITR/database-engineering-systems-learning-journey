#!/usr/bin/env python3
"""
PL/pgSQL learning companion: variables, control flow, and functions.

The script builds a small in-memory repository model that mirrors the
database concepts implemented in the PostgreSQL deliverable:
- typed variables
- conditional branches
- loops
- exception handling
- reusable functions
- validation
- aggregation
- state transitions
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable


class PullRequestState(Enum):
    OPEN = "open"
    MERGED = "merged"
    CLOSED = "closed"


@dataclass(frozen=True)
class Review:
    reviewer: str
    approved: bool
    comment: str = ""


@dataclass
class PullRequest:
    number: int
    title: str
    source_branch: str
    target_branch: str
    state: PullRequestState = PullRequestState.OPEN
    changed_files: int = 0
    additions: int = 0
    deletions: int = 0
    required_reviews: int = 2
    reviews: list[Review] = field(default_factory=list)
    status_checks: dict[str, bool] = field(default_factory=dict)

    @property
    def net_change(self) -> int:
        return self.additions - self.deletions


class WorkflowError(Exception):
    """Raised when a repository workflow operation is invalid."""


def validate_identifier(value: str, field_name: str) -> str:
    """Validate a branch/repository identifier before using it."""
    cleaned = value.strip()

    if not cleaned:
        raise ValueError(f"{field_name} cannot be empty")

    if len(cleaned) > 100:
        raise ValueError(f"{field_name} is too long")

    forbidden = {";", "--", "\x00"}
    if any(token in cleaned for token in forbidden):
        raise ValueError(f"{field_name} contains an unsafe sequence")

    return cleaned


def review_score(pr: PullRequest) -> float:
    """
    Calculate an approval ratio.

    A separate local variable is deliberately used to show the same
    conceptual role as a PL/pgSQL DECLARE variable.
    """
    total_reviews = len(pr.reviews)

    if total_reviews == 0:
        return 0.0

    approvals = sum(1 for review in pr.reviews if review.approved)
    return approvals / total_reviews


def evaluate_merge_eligibility(pr: PullRequest) -> tuple[bool, list[str]]:
    """
    Evaluate a Pull Request using explicit control-flow decisions.
    """
    reasons: list[str] = []

    if pr.state is not PullRequestState.OPEN:
        reasons.append("Pull Request is not open")

    if pr.source_branch == pr.target_branch:
        reasons.append("source and target branches must differ")

    if pr.changed_files <= 0:
        reasons.append("Pull Request contains no changed files")

    approvals = 0

    for review in pr.reviews:
        if review.approved:
            approvals += 1

    if approvals < pr.required_reviews:
        reasons.append(
            f"requires {pr.required_reviews} approvals but has {approvals}"
        )

    if not pr.status_checks:
        reasons.append("no status checks were recorded")
    else:
        for check_name, passed in pr.status_checks.items():
            if not passed:
                reasons.append(f"status check failed: {check_name}")

    return len(reasons) == 0, reasons


def estimate_review_risk(pr: PullRequest) -> str:
    """
    Demonstrate multi-branch control flow using workload indicators.
    """
    score = 0

    if pr.changed_files > 20:
        score += 2
    elif pr.changed_files > 10:
        score += 1

    if abs(pr.net_change) > 500:
        score += 2
    elif abs(pr.net_change) > 200:
        score += 1

    if len(pr.reviews) == 0:
        score += 2

    if score >= 4:
        return "HIGH"
    if score >= 2:
        return "MEDIUM"
    return "LOW"


def process_status_checks(
    checks: Iterable[tuple[str, bool]],
) -> dict[str, bool]:
    """
    Process status checks with a loop and normalize their names.
    """
    result: dict[str, bool] = {}

    for name, passed in checks:
        normalized = name.strip().lower()

        if not normalized:
            continue

        result[normalized] = bool(passed)

    return result


def safe_merge(pr: PullRequest) -> str:
    """
    Perform a guarded state transition.

    Exception handling is intentionally local because callers may want
    to continue processing other Pull Requests after one failure.
    """
    try:
        eligible, reasons = evaluate_merge_eligibility(pr)

        if not eligible:
            raise WorkflowError("; ".join(reasons))

        pr.state = PullRequestState.MERGED
        return f"PR #{pr.number} merged successfully"

    except WorkflowError as exc:
        return f"PR #{pr.number} rejected: {exc}"


def build_sample_pull_requests() -> list[PullRequest]:
    """Construct realistic records used by the executable demonstration."""
    feature_api = PullRequest(
        number=101,
        title="Add repository governance API",
        source_branch=validate_identifier("feature/governance-api", "source"),
        target_branch=validate_identifier("main", "target"),
        changed_files=8,
        additions=240,
        deletions=55,
        required_reviews=2,
        reviews=[
            Review("alice", True, "Policy validation looks correct"),
            Review("bob", True, "Database constraints are appropriate"),
            Review("carol", False, "Add an audit field"),
        ],
        status_checks=process_status_checks(
            [
                ("unit-tests", True),
                ("lint", True),
                ("security-scan", True),
            ]
        ),
    )

    incomplete = PullRequest(
        number=102,
        title="Refactor branch policy",
        source_branch="feature/policy",
        target_branch="main",
        changed_files=14,
        additions=410,
        deletions=100,
        required_reviews=2,
        reviews=[Review("alice", True)],
        status_checks=process_status_checks(
            [
                ("unit-tests", True),
                ("lint", False),
            ]
        ),
    )

    return [feature_api, incomplete]


def summarize_repository(prs: Iterable[PullRequest]) -> dict[str, int]:
    """
    Aggregate state using dictionary variables and explicit control flow.
    """
    summary = {
        "open": 0,
        "merged": 0,
        "closed": 0,
        "eligible": 0,
    }

    for pr in prs:
        summary[pr.state.value] += 1

        eligible, _ = evaluate_merge_eligibility(pr)
        if eligible:
            summary["eligible"] += 1

    return summary


def main() -> None:
    pull_requests = build_sample_pull_requests()

    print("PL/pgSQL Concepts: Variables, Control Flow, Functions")
    print("=" * 56)

    for pr in pull_requests:
        eligible, reasons = evaluate_merge_eligibility(pr)
        risk = estimate_review_risk(pr)

        print(f"\nPR #{pr.number}: {pr.title}")
        print(f"  State: {pr.state.value}")
        print(f"  Review risk: {risk}")
        print(f"  Approval ratio: {review_score(pr):.2%}")
        print(f"  Merge eligible: {eligible}")

        if reasons:
            print("  Blocking conditions:")
            for reason in reasons:
                print(f"    - {reason}")

        print(f"  Action: {safe_merge(pr)}")

    summary = summarize_repository(pull_requests)

    print("\nRepository summary")
    for state, count in summary.items():
        print(f"  {state}: {count}")

    # Demonstrate an exception boundary around invalid input.
    try:
        validate_identifier("", "branch")
    except ValueError as exc:
        print(f"\nValidation failure handled safely: {exc}")


if __name__ == "__main__":
    main()
