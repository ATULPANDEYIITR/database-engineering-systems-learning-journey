#!/usr/bin/env python3
"""
PostgreSQL Views: views, materialized views, and practical use cases.

The script models a small repository analytics system in memory. It demonstrates
the same conceptual separation used by PostgreSQL:

- A normal view represents a reusable query whose result is evaluated when read.
- A materialized view represents persisted query results that require refresh.
- View-like projections can enforce a stable reporting interface.
- Materialized results are useful when aggregation is expensive and freshness
  requirements permit scheduled or explicit refreshes.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from statistics import mean
from typing import Iterable


@dataclass(frozen=True)
class PullRequest:
    number: int
    repository: str
    author: str
    state: str
    additions: int
    deletions: int
    merged_at: datetime | None


@dataclass(frozen=True)
class Review:
    pull_request: int
    reviewer: str
    state: str


@dataclass(frozen=True)
class Repository:
    name: str
    team: str
    active: bool


class RepositoryDatabase:
    """Small in-memory data source used to demonstrate view semantics."""

    def __init__(
        self,
        repositories: Iterable[Repository],
        pull_requests: Iterable[PullRequest],
        reviews: Iterable[Review],
    ) -> None:
        self.repositories = list(repositories)
        self.pull_requests = list(pull_requests)
        self.reviews = list(reviews)

    def repository_activity_view(self) -> list[dict]:
        """
        Dynamic-view behavior.

        Nothing is stored for this result. Every invocation derives the current
        result from the underlying rows, just as a PostgreSQL view does.
        """
        result = []

        for repository in self.repositories:
            prs = [
                pr
                for pr in self.pull_requests
                if pr.repository == repository.name
            ]

            merged = [pr for pr in prs if pr.merged_at is not None]
            additions = sum(pr.additions for pr in prs)
            deletions = sum(pr.deletions for pr in prs)

            result.append(
                {
                    "repository": repository.name,
                    "team": repository.team,
                    "active": repository.active,
                    "pull_requests": len(prs),
                    "merged_pull_requests": len(merged),
                    "additions": additions,
                    "deletions": deletions,
                }
            )

        return result

    def review_quality_view(self) -> list[dict]:
        """Dynamic reporting projection based on review decisions."""
        result = []

        for pr in self.pull_requests:
            reviews = [
                review
                for review in self.reviews
                if review.pull_request == pr.number
            ]

            approvals = sum(review.state == "APPROVED" for review in reviews)
            change_requests = sum(
                review.state == "CHANGES_REQUESTED" for review in reviews
            )

            result.append(
                {
                    "pull_request": pr.number,
                    "repository": pr.repository,
                    "review_count": len(reviews),
                    "approvals": approvals,
                    "changes_requested": change_requests,
                    "review_complete": bool(reviews)
                    and change_requests == 0
                    and approvals >= 1,
                }
            )

        return result


class MaterializedRepositoryReport:
    """
    Persisted analytical snapshot.

    PostgreSQL materialized views store the result physically. This class
    reproduces that important semantic distinction: reads use the stored
    snapshot until refresh() is called.
    """

    def __init__(self, source: RepositoryDatabase) -> None:
        self.source = source
        self._rows: list[dict] = []
        self.refreshed_at: datetime | None = None

    def refresh(self) -> None:
        """Recompute the expensive report and replace its stored snapshot."""
        activity = self.source.repository_activity_view()

        self._rows = []
        for row in activity:
            pr_sizes = [
                pr.additions + pr.deletions
                for pr in self.source.pull_requests
                if pr.repository == row["repository"]
            ]

            self._rows.append(
                {
                    **row,
                    "average_change_size": round(mean(pr_sizes), 2)
                    if pr_sizes
                    else 0.0,
                }
            )

        self.refreshed_at = datetime.now(timezone.utc)

    def rows(self) -> list[dict]:
        """Return a copy so callers cannot mutate the stored snapshot."""
        return [dict(row) for row in self._rows]


def print_table(title: str, rows: list[dict]) -> None:
    print(f"\n{title}")
    print("-" * len(title))

    if not rows:
        print("(no rows)")
        return

    columns = list(rows[0])
    widths = {
        column: max(
            len(column),
            *(len(str(row[column])) for row in rows),
        )
        for column in columns
    }

    print(" | ".join(column.ljust(widths[column]) for column in columns))
    print("-+-".join("-" * widths[column] for column in columns))

    for row in rows:
        print(
            " | ".join(
                str(row[column]).ljust(widths[column])
                for column in columns
            )
        )


def main() -> None:
    now = datetime.now(timezone.utc)

    repositories = [
        Repository("payments-api", "platform", True),
        Repository("customer-portal", "web", True),
        Repository("legacy-reporting", "data", False),
    ]

    pull_requests = [
        PullRequest(
            101, "payments-api", "alice", "MERGED", 180, 42, now - timedelta(days=4)
        ),
        PullRequest(
            102, "payments-api", "bob", "OPEN", 75, 13, None
        ),
        PullRequest(
            201, "customer-portal", "carol", "MERGED", 320, 110, now - timedelta(days=2)
        ),
        PullRequest(
            202, "customer-portal", "dave", "OPEN", 20, 5, None
        ),
    ]

    reviews = [
        Review(101, "reviewer-a", "APPROVED"),
        Review(101, "reviewer-b", "APPROVED"),
        Review(102, "reviewer-a", "CHANGES_REQUESTED"),
        Review(201, "reviewer-c", "APPROVED"),
        Review(202, "reviewer-d", "APPROVED"),
    ]

    database = RepositoryDatabase(repositories, pull_requests, reviews)

    # A normal view reflects current base-table state every time it is read.
    print_table(
        "Dynamic repository activity view",
        database.repository_activity_view(),
    )

    # A materialized view has no data until it is refreshed.
    report = MaterializedRepositoryReport(database)
    report.refresh()

    print_table(
        "Materialized repository report",
        report.rows(),
    )
    print(f"\nMaterialized at: {report.refreshed_at.isoformat()}")

    # Demonstrate freshness semantics: underlying data changes immediately,
    # while the materialized snapshot remains stale until refresh().
    database.pull_requests.append(
        PullRequest(
            203,
            "payments-api",
            "erin",
            "MERGED",
            55,
            8,
            now,
        )
    )

    print_table(
        "Dynamic view after new pull request",
        database.repository_activity_view(),
    )

    print_table(
        "Materialized report before refresh",
        report.rows(),
    )

    report.refresh()

    print_table(
        "Materialized report after refresh",
        report.rows(),
    )

    # Validation that catches a common reporting mistake: a materialized
    # result can be valid but stale. Production code should track refresh time
    # when freshness affects business decisions.
    if report.refreshed_at is None:
        raise RuntimeError("Report was never refreshed")

    age = datetime.now(timezone.utc) - report.refreshed_at
    if age.total_seconds() < 0:
        raise RuntimeError("Materialized timestamp is invalid")

    print("\nUse-case guidance:")
    print("- Use normal views for reusable, security-conscious query interfaces.")
    print("- Use materialized views for expensive reports where bounded staleness is acceptable.")
    print("- Refresh materialized data according to the application's freshness requirement.")
    print("- Never assume a materialized result reflects the base tables immediately.")


if __name__ == "__main__":
    main()
