# Temporal Data Modeling: Historical Records, Effective Dates, and Event Time

## Scope

Temporal data modeling represents facts together with the time dimensions needed to interpret them correctly. A conventional database row often describes the current state of an entity. A temporal model preserves when a fact applied, when the system learned it, or when an event actually occurred.

These distinctions matter in payroll, pricing, inventory, insurance, compliance, financial reporting, logistics, and operational monitoring. A salary correction entered in August can apply retroactively from July. A shipment event can occur at 10:01 but reach a processing service at 10:13. A report must be able to distinguish the business reality from the information available when the report was originally produced.

The six implementations use a common domain of historical business facts and delayed operational events. They employ different mechanisms suited to each language and execution environment.

## Temporal terminology

### Valid time and effective dates

Valid time identifies the period during which a fact applies in the business domain. An effective-dated salary record might state that an employee's salary is INR 78,000 from April 1 through June 30.

The examples represent such periods as half-open intervals:

`[valid_from, valid_to)`

The starting instant is included, while the ending instant is excluded. Therefore, a salary ending on April 1 and a replacement salary starting on April 1 do not overlap. This convention avoids ambiguity at transition boundaries.

An open-ended interval has no specified end. It represents a fact that remains effective until another event or business decision closes the period.

### Transaction time and recording time

Transaction time describes when a database or information system recorded a fact. The implementations use a recording timestamp to distinguish the date a fact became effective from the date the system learned about it.

Consider a salary effective July 1 but recorded on August 10. A query asking for the salary applicable on August 1 should return the corrected salary if the query uses the current historical record. A reconstruction of what the payroll system knew on August 1 must not include a fact that was recorded nine days later.

A recording timestamp alone is not sufficient for a complete bitemporal database. A fully bitemporal model also preserves the periods during which each version was considered recorded truth, including when a correction superseded an earlier assertion.

### Event time and ingestion time

Event time is the timestamp at which an event occurred in the source domain. Ingestion time is when a receiving system accepted the event.

These timestamps answer different operational questions:

- Event-time aggregation measures when business activity happened.
- Ingestion-time analysis measures delivery latency and processing delays.
- Late-arrival detection identifies events that arrive substantially behind the observed event-time frontier.
- Replay reconstructs event-time ordering from retained events instead of treating arrival order as business chronology.

A watermark is an operational estimate of event-time progress. It helps a stream processor decide when to finalize windows or reduce the expectation of further events. It cannot prove that an older event will never arrive.

## Temporal modeling architecture

The implementations separate three responsibilities.

| Responsibility | Primary mechanism | Question answered |
|---|---|---|
| Effective-dated state | Historical versions with validity intervals | What fact applied at a particular business time? |
| Historical knowledge | Recording timestamps and retained corrections | What did the system know at a particular time? |
| Event processing | Event timestamps, ingestion timestamps, and windows | When did activity happen, and when was it received? |

These mechanisms can coexist in one application. They should not be collapsed into a single timestamp because business validity, data recording, and event occurrence are not interchangeable.

## Python implementation

The Python script provides an executable temporal ledger, an event-time processor, a SQLite-backed relational demonstration, and automated tests.

### Effective-dated salary ledger

`SalaryVersion` is an immutable data structure containing the employee identifier, salary amount, validity interval, recording timestamp, and version identifier. Its validation rejects nonpositive salaries, missing employee identifiers, timezone-naive timestamps, and invalid interval boundaries.

`TemporalSalaryLedger` maintains employee salary history. When a version is added, the ledger checks existing intervals for overlap. The check prevents two salary facts from simultaneously claiming to be effective for the same employee.

The `salary_at` method evaluates valid time independently of recording time. The `payroll_as_known_at` method also restricts candidate facts to those recorded by the requested knowledge time. These operations demonstrate why a simple query for the latest row is insufficient for historical reconstruction.

### Event-time processing

`Event` retains an event identifier, event type, entity identifier, event timestamp, ingestion timestamp, and payload.

`EventTimeWindow` detects duplicate event identifiers, tracks the maximum observed event time, identifies arrivals older than the configured lateness boundary, and retains late events. Its window query uses the same half-open interval convention as the salary ledger.

The demonstration deliberately receives a cancellation event whose event timestamp precedes events already observed by the processor. The event is late but is not discarded. Its original timestamp remains available for correct historical aggregation.

### SQLite integrity demonstration

The SQLite example creates an employee table and an effective-dated salary table. It uses foreign keys, positive salary checks, interval checks, and a trigger that rejects overlapping effective periods.

The SQLite schema is intentionally simpler than the PostgreSQL schema. SQLite does not provide PostgreSQL's native range types or exclusion constraints, so a trigger performs the overlap check. The example also enables foreign-key enforcement explicitly.

The tests exercise boundary transitions, invalid timestamps, overlapping intervals, and late events. The script uses only the Python standard library.

## JavaScript implementation

The JavaScript file emphasizes event-driven processing, encapsulated state, immutable records, and deterministic replay in Node.js.

### Effective-dated registry

`EffectiveDatedRegistry` stores temporal records by entity identifier. Private class fields prevent callers from directly modifying the internal map. Each record is frozen after construction, and its validity interval is checked before insertion.

The `at` method retrieves the fact effective at a specified instant. The `asKnownAt` method adds a recording-time constraint. These methods distinguish a current historical reconstruction from an inquiry about what was known at an earlier point.

Timestamps are represented as epoch milliseconds internally. The parsing function requires an explicit timezone and rejects invalid values. This avoids silently treating a timezone-naive input as a universally meaningful instant.

### Event-driven processing

`TemporalEventStream` uses listener registration to notify consumers when an event is accepted, identified as late, or ingested. The returned unsubscribe function removes a listener without requiring consumers to manipulate internal collections.

Event identifiers provide in-memory deduplication. Event-time windows sort by timestamp and then by identifier, producing deterministic output when multiple events have the same timestamp.

`replayEvents` provides sequential asynchronous replay. Awaiting each handler preserves the order in which events are passed to that handler. A production consumer would also need to address durable deduplication, handler failures, checkpointing, retry policy, and atomic coordination between processing results and progress tracking.

The executable assertions cover effective-date boundaries, duplicate ingestion, invalid timestamp formats, late arrivals, and invalid windows.

## C++ case study: repository governance over time

The C++ program presents an operational governance engine in which repository decisions depend on the state of a Pull Request, its current commit, its reviews, and its status checks.

This scenario demonstrates an important temporal principle: a decision made against an earlier state is not automatically valid for a later state.

### Commit-specific decisions

The `PullRequest` structure records a head commit, base commit, review records, status checks, source and target branches, and workflow state. Each review and check identifies the commit it evaluates.

The `RepositoryGovernance` class evaluates merge eligibility against a branch protection policy. Approval counts include only eligible reviewers who approved the current head commit. Required status checks must also have succeeded for that exact commit.

When a new commit is pushed, earlier reviews remain in the audit history but no longer satisfy the current-head approval condition. The same rule invalidates checks tied to the previous head.

### Governance rules

The example policy requires two approvals, resolved review conversations, code-owner approval for protected files, successful unit tests, and a successful security scan. It also requires linear history and restricts merge strategies.

The engine reports individual blockers rather than returning only a Boolean decision. This makes it possible to distinguish an unresolved conversation from a missing check or a stale approval.

The case study also models draft, open, closed, and merged states. Synchronization updates the base commit and records whether a conflict remains. Closing a merged request as unmerged is prohibited, and reopening is restricted to closed requests.

The implementation uses sets for reviewer eligibility, required checks, and prohibited strategies. For a Pull Request with R review records and C status checks, eligibility evaluation scans those collections and is approximately linear in the number of records for a fixed-size policy. Larger repositories can index checks and reviews by commit and policy identifier.

The bypass actor illustrates an explicit governance exception. A production implementation should make such exceptions separately auditable, restrict them to authorized principals, and avoid interpreting a bypass as ordinary approval.

## Java implementation: enterprise domain model

The Java program models repository governance through explicit domain types and a dedicated service.

### Domain types and state transitions

Enums represent Pull Request state, review state, check conclusion, and merge strategy. Records represent commits, file changes, review comments, reviews, and status checks. Record constructors validate required values and reject invalid change counts or comment locations.

The `PullRequest` class owns mutable workflow state. It controls whether the request can be edited, reviewed, closed, or reopened. A draft must be marked ready before ordinary merge evaluation can succeed.

Review comments are represented separately from overall review decisions. Resolving an inline comment changes its resolution state without pretending that the reviewer has submitted a new approval.

### Governance service

`GovernanceService` registers commits and Pull Requests, evaluates policy, and applies the merge transition only after eligibility succeeds.

The policy includes reviewer eligibility, an approval threshold, code-owner paths, required checks, permitted merge strategies, stale-review handling, conversation requirements, base synchronization, linear-history requirements, and explicit exception actors.

The approval calculation uses a set of reviewer identities. Multiple approval records from the same reviewer therefore do not count as multiple independent approvers. A review must refer to the current head commit and must belong to an eligible reviewer other than the author.

Required checks are evaluated by both name and commit identifier. A successful check on an older commit cannot satisfy a condition for the current head.

The merge service changes the request to `MERGED` and records merge metadata only after policy evaluation succeeds. In a distributed production system, this check and the actual repository merge must be coordinated so that the head commit, reviews, and check results cannot change between evaluation and merge.

The example models direct-push, force-push, and deletion permissions as separate policy decisions. These are not substitutes for merge eligibility. Actual repository hosting platforms enforce additional identity, token, ruleset, and administrative controls.

## PostgreSQL implementation: relational temporal integrity

The SQL script creates a PostgreSQL schema containing employee salary history, temporal audit records, domain events, processing watermarks, and corrections.

### Effective-dated facts

The `salary_versions` table stores salary amounts, currency codes, validity ranges, recording timestamps, and source references.

PostgreSQL's `tstzrange` type represents timestamp ranges. The `[)` convention includes the lower boundary and excludes the upper boundary. The GiST exclusion constraint combines employee equality with range overlap, preventing overlapping salary periods for one employee while allowing adjacent intervals.

The constraint protects the temporal invariant at the database layer. Application-level checks remain useful for error messages, but they cannot replace database integrity under concurrent writes.

The as-of query uses the range-containment operator `@>` to retrieve the salary effective at a specified instant. The historical-knowledge query adds a recording-time restriction. These queries intentionally answer different questions.

### Audit records and transaction time

The `temporal_audit` table retains before-images and after-images for salary record changes. A trigger writes the corresponding audit row for insert, update, and delete operations.

Audit history provides evidence of database modifications, but it is not equivalent to a fully bitemporal table. A production bitemporal design would explicitly preserve both valid-time and system-time intervals, enforce the relevant non-overlap rules, and define how corrections supersede previous assertions.

Database audit triggers also have operational limitations. Permissions, trigger disabling, replication behavior, privileged users, and backup retention must be addressed when audit evidence is used for compliance.

### Event time and corrections

The `domain_events` table separates `event_time` from `ingested_at`. The event-time index supports temporal range queries, while the entity-time index supports chronological history for a particular entity. A GIN index supports suitable queries against JSONB payloads.

The event aggregation query groups events by event type within an event-time window. A separate expression counts events that arrived more than five minutes after their event timestamp.

`processing_watermarks` records the latest observed event-time frontier and an allowed-lateness interval. It describes processing progress rather than guaranteeing completeness.

The `temporal_corrections` table preserves corrections as separate records. The reconstruction query selects the latest correction known by a specified recording time and applies it to the corresponding original event. The original event remains intact, preserving the distinction between source evidence and later correction.

The script uses PostgreSQL-specific range types, exclusion constraints, JSONB, PL/pgSQL triggers, filtered aggregates, and window functions. It is designed to run in PostgreSQL with permission to create the schema and extension.

## Distinguishing temporal queries

Temporal systems commonly need several forms of inquiry.

| Query type | Time constraint | Typical application |
|---|---|---|
| Current state | Current instant in valid time | Current salary, price, or capacity |
| Historical valid state | Requested business instant | Salary applicable on May 15 |
| Historical knowledge | Business instant and recording cutoff | Salary known when a past payroll was processed |
| Event-time window | Event timestamp range | Orders created during a reporting interval |
| Ingestion latency | Difference between ingestion and event timestamps | Delayed source feeds |
| Corrected reconstruction | Business event time plus correction knowledge time | Restated historical operational reports |

A query that ignores the intended temporal dimension may produce a plausible but incorrect result. For example, ordering events by ingestion time can misrepresent business chronology, while filtering salary records only by recording date can return a fact that was not effective during the requested business period.

## Edge cases and operational constraints

### Boundary conditions

Adjacent intervals should meet at exactly one boundary without overlapping. Open-ended periods require explicit treatment because an absent end represents an unbounded future interval rather than a missing value to be guessed.

### Late-arriving events

Late events can alter previously calculated aggregates. A processor must decide whether to revise earlier results, issue correction events, retain provisional windows, or reject data beyond an explicit lateness policy. The decision depends on reporting requirements and the cost of recomputation.

### Duplicate delivery

A source may deliver the same event more than once. Stable event identifiers and unique constraints can prevent duplicate storage, but storage deduplication does not automatically make external side effects idempotent.

### Retroactive corrections

A correction may be entered today while applying to a period in the past. Overwriting the old value destroys the ability to explain prior decisions. Versioned facts or append-only corrections preserve that evidence.

### Clock and timezone quality

A timestamp must represent an unambiguous instant. Systems should normalize instants to UTC for comparison and retain original timezone or source metadata when it matters for business interpretation. Clock skew, incorrect source clocks, daylight-saving transitions, and inconsistent timestamp precision can all affect event ordering.

### Concurrency

Two transactions can independently observe that a temporal interval is available and then attempt overlapping inserts. Application-only validation is vulnerable to this race. Database constraints, appropriate transaction isolation, or explicit locking are needed to enforce temporal uniqueness reliably.

### Performance

Historical queries benefit from indexes that match the temporal predicate. Range-based data can use range-aware indexes, while event pipelines benefit from indexes on event time and entity identifiers. Index design should follow actual query patterns because additional indexes increase write cost and storage consumption.

Large historical tables may require partitioning, retention policies, archival storage, or precomputed temporal aggregates. Partitioning by ingestion time is not always appropriate when most queries filter by event time.

## Production considerations

Temporal data models require explicit retention, correction, and reconstruction policies. The system should define whether history is immutable, whether corrections supersede or amend facts, how late events affect published results, and which timestamp is authoritative for each business operation.

Temporal audit data can contain sensitive information. Access control should cover historical versions and audit images as well as current records. Database roles should restrict unauthorized changes to history, and backups should preserve the relationships between original facts, corrections, and audit entries.

A reliable temporal design makes its time semantics visible in the schema, validates interval boundaries, retains the information needed for historical reconstruction, and evaluates operational events using the timestamp appropriate to the question being asked.
