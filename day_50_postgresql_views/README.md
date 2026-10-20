# PostgreSQL Views, Materialized Views, and Use Cases

## Scope

This project examines PostgreSQL views and materialized views through a repository-development reporting scenario.

The central distinction is:

> A **view** stores a query definition and evaluates that query when it is read. A **materialized view** stores the query result and must be refreshed when the stored result needs to reflect newer source data.

The five implementations use the same domain but deliberately emphasize different technical perspectives:

| File | Primary perspective | Main implementation |
|---|---|---|
| Python | Workflow simulation | Dynamic projections and explicit materialized snapshots |
| JavaScript | Event-driven application behavior | Dynamic reporting, asynchronous refresh, events |
| C++17 | Systems-oriented reporting engine | Validated domain objects and computed metrics |
| Java 17 | Enterprise domain modeling | Records, enums, immutable snapshots, streams |
| PostgreSQL | Relational implementation | Views, materialized views, CTEs, constraints, indexes, transactions |

The examples use repositories, branches, commits, pull requests, reviewers, reviews, comments, status checks, and branch-protection policies because these entities generate realistic operational and analytical queries.

## Core distinction

A normal PostgreSQL view is a named query.

Conceptually:

`base tables → view definition → query execution → current result`

The rows in the base tables remain the authoritative data. Querying the view evaluates its underlying query using the database's current transaction-visible data.

A materialized view changes the storage model:

`base tables → query execution → stored result → later reads`

The stored result is therefore a snapshot. Source-table changes do not automatically rewrite the materialized view. A refresh operation is required.

This distinction creates a direct trade-off:

| Property | Normal view | Materialized view |
|---|---|---|
| Stores result rows | No | Yes |
| Reflects current committed source data | Yes, subject to transaction visibility | Only after refresh |
| Refresh required | No | Yes |
| Repeated expensive aggregation | Recomputed | Can be read from stored results |
| Storage overhead | Low | Additional storage |
| Staleness risk | No snapshot staleness | Yes |
| Useful for | Reusable interfaces and current reporting | Expensive analytical queries and bounded-staleness reporting |
| Indexes on result | Not ordinary indexes on the view result | Yes, indexes can be created on the materialized view |

## Repository reporting model

The PostgreSQL implementation contains these principal relationships:

    repositories
        |
        +-- branches
        |     |
        |     +-- branch_protection_policies
        |
        +-- commits
        |
        +-- pull_requests
                |
                +-- reviews ---- reviewers
                |
                +-- review_comments
                |
                +-- status_checks

A pull request connects a source branch with a target branch. Reviews, comments, and status checks are separate operational records associated with that pull request.

The model intentionally keeps these entities separate so that reporting queries can answer different questions without collapsing unrelated concepts into one table.

## Normal views

### Repository activity

`v_repository_activity` provides a reusable current-state reporting interface.

It aggregates pull-request activity by repository and returns:

- Repository identity
- Owner team
- Active state
- Total pull requests
- Merged pull requests
- Total additions and deletions

A `LEFT JOIN` is important here. It preserves repositories that currently have no pull requests. An inner join would remove those repositories from the report.

The aggregation is performed when the view is queried.

### Review status

`v_pull_request_review_status` isolates review-related information from repository activity.

It reports:

- Number of reviews
- Active approvals
- Active change requests
- Unresolved review comments

This separation matters because a pull request's lifecycle state and its review state are different dimensions.

A pull request can be `OPEN` while having no approval, multiple approvals, or a request for changes. A repository activity view should not be treated as a substitute for a review-status view.

### Status checks

`v_pull_request_check_status` summarizes checks associated with each pull request.

It distinguishes:

- Passed checks
- Failed checks
- Pending checks
- Total checks

The result is useful for operational dashboards and merge-policy evaluation.

## Materialized view

`mv_repository_daily_report` stores a precomputed repository-level report.

It contains:

- Pull-request count
- Merged count
- Open count
- Additions
- Deletions
- Average change size

This is a reasonable materialized-view use case because the report contains aggregation over multiple operational tables and can be read repeatedly by dashboards or scheduled reporting processes.

The materialized result does not automatically change when `pull_requests` changes.

The operational sequence is therefore:

    INSERT / UPDATE source data
            |
            v
       Base tables change
            |
            +----------------------+
            |                      |
            v                      v
       Normal view            Materialized view
       reads current data     retains previous snapshot
            |                      |
            |                      v
            |                REFRESH MATERIALIZED VIEW
            |                      |
            +----------+-----------+
                       |
                       v
                 Updated report

## Refresh semantics

A materialized view should have a defined freshness policy.

Possible policies include:

| Reporting requirement | Suitable approach |
|---|---|
| Must reflect current source state | Normal view |
| Small dashboard query with inexpensive aggregation | Normal view |
| Expensive aggregation read frequently | Materialized view |
| Daily operational report | Scheduled materialized-view refresh |
| Near-real-time analytics | Normal view or another incremental/streaming architecture |
| Historical snapshot reporting | Materialized view or dedicated snapshot tables |

A materialized view is not automatically a performance improvement. Refreshing it also costs database resources. The correct decision depends on read frequency, query cost, source-table write frequency, acceptable staleness, and storage requirements.

## PostgreSQL implementation

The SQL script uses PostgreSQL-specific features where they provide meaningful behavior.

### Constraints

The schema uses:

- Primary keys
- Foreign keys
- Unique constraints
- Check constraints
- Identity columns

Examples include preventing negative addition/deletion counts, preventing invalid pull-request states, requiring a merged timestamp for merged pull requests, and preventing a pull request from targeting the same branch from which it originates.

These rules belong in the database because they protect integrity regardless of which application writes the data.

### Indexes

Indexes are created for recurring access patterns:

- Pull requests by repository and state
- Reviews by pull request and state
- Status checks by pull request and status
- Unresolved review comments by pull request

The materialized view also receives a unique index on `repository_id`.

That unique index has a practical purpose beyond ordinary lookup performance: it permits PostgreSQL to use `REFRESH MATERIALIZED VIEW CONCURRENTLY` when the materialized-view requirements are otherwise satisfied.

### CTE-backed reporting

`v_pull_request_merge_eligibility` uses common table expressions to calculate:

- Active approvals
- Active change requests
- Unresolved comments
- Status-check results

It then combines these values with branch-protection policy.

The result is a derived eligibility decision rather than persisted workflow state.

This distinction prevents a reporting view from becoming a second source of truth for the operational tables.

## Transaction behavior

The SQL script includes transactions that demonstrate source-data visibility.

Within a transaction, a changed pull-request row is visible to the normal view according to PostgreSQL transaction visibility.

The materialized view does not automatically recalculate because the source modification does not implicitly refresh it.

The example rolls the change back to preserve the initial dataset.

This illustrates two independent concepts:

- Transaction visibility controls what a query can see from source tables.
- Materialized-view refresh controls when persisted derived data is recomputed.

## Python implementation

The Python program models a repository database with dataclasses.

`RepositoryDatabase.repository_activity_view()` recalculates repository metrics every time it is called.

This intentionally mirrors the semantic behavior of a normal database view:

    Current source objects
            |
            v
        Query logic
            |
            v
       Current derived rows

`MaterializedRepositoryReport` stores a copied result in `_rows`.

Its `refresh()` method recomputes the report. Its `rows()` method only reads the stored snapshot.

The program then inserts a new pull request after the first refresh. The dynamic report sees it immediately, while the materialized report does not see it until `refresh()` is called.

The use of copied dictionaries also prevents a caller from accidentally mutating the internal materialized snapshot.

## JavaScript implementation

The JavaScript implementation treats reporting as an event-driven application concern.

`RepositoryStore` extends `EventEmitter` and emits events when repositories, pull requests, reviews, and reports change.

The dynamic projection is calculated by `dynamicRepositoryView()`.

`MaterializedReport.refresh()` is asynchronous. The asynchronous boundary models the fact that real systems often refresh expensive analytical data in a background job rather than during an ordinary user request.

The example also calculates a SHA-256 hash of the stored snapshot. The hash is not a replacement for database integrity controls, but it demonstrates how an application can fingerprint a reporting snapshot when auditing or cache diagnostics are useful.

Input validation rejects:

- Invalid pull-request numbers
- Unknown repositories
- Duplicate identifiers
- Negative change counts
- Invalid review states
- Empty names

## C++17 implementation

The C++ implementation emphasizes explicit data structures and computational control.

The `GovernanceEngine` owns the operational records and validates relationships before inserting data.

`repositoryActivityView()` performs a fresh scan of the current data.

`MaterializedRepositoryReport` stores a vector of `RepositoryMetrics` until `refresh()` replaces it.

This makes the storage/performance trade-off explicit:

**Dynamic calculation**

`O(number of repositories × number of pull requests)`

**Stored snapshot read**

`O(number of reported rows)`

The implementation uses linear scans for clarity because the dataset is deliberately small. A production-scale C++ service would normally use indexes, hash maps, database-side aggregation, or a database query engine rather than repeatedly scanning all records.

## Java 17 implementation

The Java implementation models reporting as an enterprise service.

Records provide immutable domain values for:

- Repositories
- Pull requests
- Reviews
- Repository reports

Enums constrain lifecycle and review states to known values.

`RepositoryService.repositoryActivityView()` uses streams for filtering and aggregation.

`MaterializedReportService` stores an immutable snapshot using `List.copyOf()`.

The service is synchronized when replacing or reading the snapshot so that concurrent callers cannot observe a partially replaced application-level result.

This does not attempt to reproduce PostgreSQL's internal materialized-view implementation. It models the important application-level contract: the report is a stored derived result with an explicit refresh boundary.

## Views as interfaces

A useful way to think about a view is as a database-level interface.

Instead of allowing every reporting consumer to depend directly on a complex collection of joins, a view can expose a controlled projection:

    Operational schema
            |
            | Complex joins
            | Filters
            | Aggregation
            v
        Named view
            |
            v
      Reporting consumers

This can reduce repeated SQL and provide a stable interface for applications.

Views can also hide implementation details. If the underlying schema changes while the public columns of the view remain compatible, consumers may require fewer changes.

A view does not automatically provide security. Column exposure, row filtering, permissions, `security_invoker`, `security_barrier`, and the underlying objects must be considered according to the security model.

## Materialized views as analytical caches

A materialized view can be treated as a database-managed analytical cache.

The important difference from an ordinary application cache is that PostgreSQL owns the stored relational result and its indexes.

The pattern is useful when:

- The source query is expensive.
- The result is read frequently.
- Source changes are more frequent than reporting requirements.
- A known freshness window is acceptable.
- Precomputed aggregation materially reduces query cost.

It is less suitable when every read requires the newest source state and refresh cost would approach the cost of executing the original query.

## Failure modes

### Stale materialized data

A materialized view can successfully return old data.

This is not necessarily a database failure. It is a consequence of its storage semantics.

The application must know the acceptable freshness window.

### Expensive refresh

Refreshing a large materialized view can consume CPU, memory, I/O, and locks depending on the operation and workload.

Refresh frequency should therefore be chosen using actual query and workload measurements.

### Duplicate business logic

Creating multiple similar views with slightly different definitions can create inconsistent reports.

A shared view should be preferred when several consumers require the same semantics.

### Incorrect aggregation

One-to-many joins can multiply rows.

For example, joining pull requests simultaneously to reviews and comments can produce multiple combinations for the same pull request. Aggregates must therefore be designed carefully, often using separate CTEs or pre-aggregation before joining.

The SQL implementation avoids that particular multiplication problem by aggregating reviews, comments, and status checks independently before combining their results.

### Missing indexes

A view itself does not normally receive an ordinary index over its computed result. Performance depends on the underlying query and indexes on base tables.

A materialized view can have indexes because its result is physically stored.

## Security considerations

Views should expose only the columns required by their consumers.

Sensitive operational columns should not be included simply because the underlying tables contain them.

When views are used as a controlled reporting interface, database permissions should be granted deliberately.

Materialized views require the same consideration. Persisting a derived result can create another copy of potentially sensitive information, increasing storage and access-control responsibilities.

Reporting queries should also avoid constructing SQL by concatenating untrusted input. Parameterized queries should be used by client applications.

## Performance considerations

A normal view does not inherently make a query faster. It primarily provides reusable query structure and an abstraction boundary.

Performance comes from the query plan and the underlying indexes.

A materialized view can make repeated reads substantially cheaper because aggregation and joins have already been executed during refresh.

The trade-off is:

    Normal view
    --------------------------------
    Freshness:          High
    Read cost:          Potentially high
    Storage:            Low
    Refresh operation:  None

    Materialized view
    --------------------------------
    Freshness:          Bounded by refresh
    Read cost:          Potentially low
    Storage:            Higher
    Refresh operation:  Required

The appropriate design depends on workload characteristics rather than the name of the feature.

## Practical decision boundary

Use a **normal view** when the principal requirement is a reusable, current relational projection.

Use a **materialized view** when the principal requirement is efficient repeated access to an expensive derived result and the system can tolerate controlled staleness.

Use neither as a substitute for carefully designed operational tables. Views and materialized views are derived access mechanisms; the underlying relational model remains responsible for authoritative transactional state.
