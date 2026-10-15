# Production-Grade Relational Schema Design: Repository Governance

## Project scope

This project models the data and rules required to govern changes to a software repository. It treats Pull Requests, Code Review, Approvals, and Branch Protection as related but distinct areas.

The central data-modeling problem is not simply storing a pull request and its status. A reliable system must preserve the relationship between a proposed changeset, the exact commit reviewed, the people who evaluated it, the automated checks executed against it, the policy applicable to the target branch, and the decision that permits or rejects a merge.

The implementations use different approaches to the same domain:

- Python provides an executable domain model and a collection of integrity and policy tests.
- JavaScript represents event-driven repository activity and processes review and CI events.
- C++ builds a repository-governance engine with explicit data structures and a merge-eligibility algorithm.
- Java models the domain using immutable records, mutable aggregate objects, and a dedicated governance service.
- PostgreSQL provides the relational schema, constraints, indexes, policy queries, and a transactional merge function.

These implementations are complementary case studies. They are not interchangeable production implementations of a Git hosting service.

## Relational modeling principles

A production-grade schema separates entities according to their identity, lifecycle, relationships, and update frequency. It also distinguishes durable historical evidence from mutable current state.

The principal relationships are:

| Entity | Relationship and purpose |
|---|---|
| Repository | Owns branches, commits, pull requests, membership, and branch policies. |
| Branch | Belongs to one repository and identifies its current commit. |
| Commit | Identifies a repository-specific revision and its author and message. |
| Pull Request | Connects a source branch and target branch and records the proposed base and head revisions. |
| Review | Records one reviewer's decision about a particular revision of a pull request. |
| Review comment | Belongs to a review and may identify a file and line. |
| Reviewer | Represents a reviewer's identity and active status. |
| Reviewer team | Associates reviewers with policy-relevant teams. |
| Status check | Records the result of an automated check against a specific pull request revision. |
| Branch protection policy | Defines merge requirements for a repository branch. |
| Required check | Identifies an automated check that must pass before merging. |
| Eligible approver team | Restricts which teams may supply qualifying approvals. |
| Merge audit | Records significant repository-governance decisions. |

The repository identifier is the ownership boundary. A commit SHA alone is not sufficient as the relational primary key because the schema must also establish which repository owns the referenced commit. The PostgreSQL implementation therefore uses `(repository_id, commit_sha)` as the commit primary key.

Composite foreign keys preserve this ownership relationship. A branch cannot point to a commit in another repository, and a pull request cannot refer to a commit belonging to an unrelated repository.

## Domain boundaries and data integrity

### Pull Requests represent proposed changes

A Pull Request connects a source branch to a target branch. Its `base_sha` records the target revision against which the proposal was prepared, while `head_sha` identifies the proposed revision.

These fields serve different purposes. If the target branch advances after a pull request opens, its base revision may become outdated. If the source branch advances, the pull request's head revision must be updated. Reviews and CI evidence tied to the previous head cannot automatically be treated as evidence for the new changeset.

The pull request lifecycle is represented explicitly through `draft`, `open`, `closed`, and `merged` states. Draft requests are not mergeable. Closed requests are not mergeable until reopened under the applicable rules. Merged requests retain their resulting merge identifier and strategy.

The PostgreSQL schema uses a check constraint to require merge metadata for merged requests and prohibit that metadata on requests that have not been merged. Application services must still control valid lifecycle transitions. A check constraint validates the resulting row, but does not by itself prove that a request followed a valid transition history.

The `pull_request_commits` relationship provides an ordered changeset membership model. It preserves the set and sequence of commits associated with a proposal rather than relying on a single text field.

### Code Review records technical evaluation

Code Review is represented by `pull_request_reviews` and `review_comments`.

A review stores its reviewer, decision, submission time, and reviewed commit. The decision values distinguish comments, approvals, requested changes, and dismissed reviews. A review comment can be general or inline. Inline comments require both a file path and a positive line number.

A comment and a review are separate records because one review may produce several discussions. Each discussion can be resolved independently, while the review retains its original decision and history.

The PostgreSQL schema enforces non-empty comment text, valid inline locations, and resolution metadata. The Python, JavaScript, C++, and Java implementations apply corresponding validation in their domain models.

Review quality cannot be fully established by relational constraints. A database can ensure that a review references valid entities, but it cannot determine whether a security concern was correctly understood or whether a proposed change is maintainable. Those responsibilities belong to the review process and its human participants.

### Approvals are policy-qualified decisions

An approval is a review decision, not a permanent authorization to merge.

The latest review from a reviewer is the relevant decision for that reviewer. If a reviewer approves a commit and later requests changes, the earlier approval must not remain effective merely because it exists in the database. A dismissed review is also excluded from the eligible approval count.

Stale approvals require particular care. When a pull request's head changes, a policy may invalidate approvals tied to older revisions. The implementations therefore compare the reviewed commit with the current pull request head when stale-approval dismissal is enabled.

Eligibility can also depend on reviewer status and team membership. An inactive reviewer must not contribute an approval. If a policy restricts approvals to specified teams, the reviewer must belong to at least one eligible team.

The relational implementation uses `latest_review_decisions` to obtain each reviewer's most recent decision and combines it with reviewer status, revision identity, and team membership when calculating eligible approvals. This avoids counting every historical approval as a separate vote.

A production deployment should define whether reviewer eligibility is evaluated using current team membership or membership at the time of review. The sample uses current membership, which simplifies policy evaluation but means later membership changes can alter the eligibility of an earlier review.

### Branch Protection defines repository-level rules

Branch Protection is a repository governance policy attached to a particular target branch. It determines which merge conditions apply to proposals targeting that branch.

The PostgreSQL design stores policy attributes in `branch_protection_policies`. Required status checks, eligible approver teams, and allowed merge strategies are normalized into separate tables. This avoids storing multiple values in comma-separated text columns or embedding policy lists in unvalidated JSON.

The policy includes required approval counts, stale-approval behavior, up-to-date-base requirements, conversation resolution, linear history, signed-commit verification, direct-push restrictions, force-push restrictions, deletion restrictions, and administrator bypass configuration.

These fields represent distinct rules:

- Required reviews determine how much review evidence must exist.
- Eligible approver teams constrain whose approvals count.
- Required checks establish which automated checks must succeed.
- Conversation resolution prevents merging while review discussions remain open.
- Linear-history policy constrains the permitted commit-history shape.
- Direct-push and force-push restrictions govern changes made outside the normal merge workflow.
- Deletion restrictions protect the branch itself.
- Bypass configuration describes a potential exception to normal policy enforcement.

A stored bypass flag is not, by itself, a complete bypass authorization mechanism. A production service must separately authenticate the actor, verify the actor's role, record the reason for bypass, and define which restrictions can legally be bypassed.

## Python implementation

The Python script uses dataclasses and enumerations to make domain state explicit. Repository records, commits, reviewers, and policies are distinct from mutable pull requests, branches, reviews, comments, and checks.

`RepositoryStore` serves as an in-memory repository layer. Its dictionaries provide direct lookup by identifier, while compound branch keys preserve branch-name uniqueness within a repository. Methods such as `add_commit`, `add_branch`, and `open_pull_request` validate ownership and existence before modifying the store.

`merge_blockers` calculates the reasons a merge is currently prohibited. It evaluates the pull request lifecycle, source-branch consistency, target policy, current approvals, current-head status checks, unresolved comments, and the selected merge strategy.

The implementation deliberately distinguishes a recorded approval from an eligible approval. `active_approvals` first finds the latest review per reviewer, then excludes non-approval decisions, inactive reviewers, stale reviews, and reviewers outside eligible teams.

The `unittest` cases exercise failed merges, successful merges, self-approval rejection, direct-push protection, stale approvals, and duplicate branch names. These tests illustrate why integrity checks and workflow tests are complementary: a valid data structure does not guarantee that a particular transition is authorized.

The in-memory store is educational rather than a concurrent production database. It does not provide durable storage, isolation between concurrent requests, authenticated identities, cryptographic commit verification, or real Git tree construction. Its synthetic merge identifier demonstrates a state transition and must not be treated as a real Git object SHA.

## JavaScript implementation

The JavaScript file uses an event-driven design. `RepositoryEventProcessor` listens for review submissions, check completions, and pull-request synchronization events. This resembles the integration layer of a repository host receiving webhook events from review and CI systems.

`PullRequest` maintains review history and status-check history by context. This is important because the latest result for a required check may differ from an earlier result. The `latestCheck` method only considers evidence attached to the current head revision.

The implementation uses immutable event records and structured audit details where appropriate. `GovernanceService` separates repository registration and pull-request creation from the pull request's merge evaluation.

The model also distinguishes publication of a draft from opening an ordinary pull request. Review submission requires a published request, and merge evaluation rejects requests that are not open.

The event processor is synchronous within this example. A production event consumer would need durable event delivery, duplicate-event detection, retry policies, event ordering, authentication of webhook signatures, and idempotent state updates. Events may be delivered more than once or arrive out of order. A robust service must prevent a late event for an older commit from replacing valid evidence for the current head.

## C++ case study

The C++ program models a payments-service repository protected by a two-approval policy. The required checks are unit tests and a dependency audit. Eligible approvals must come from designated security or platform reviewers.

`Repository` owns commits, branches, reviewers, branch-protection policies, and pull requests. This ownership structure allows validation methods to check relationships before accepting a new entity.

The merge evaluator builds a list of blockers instead of stopping at the first ordinary policy failure. This gives the calling service a complete view of outstanding requirements. The evaluator selects the latest review from each reviewer, checks revision identity, and excludes inactive or ineligible reviewers.

Status checks are filtered by the pull request's current head. A successful check against an older revision does not satisfy the policy for the current revision. Review comments are also considered independently of the approval count, since an approved review can still contain unresolved discussion threads.

The demonstration initially encounters an unresolved comment. Once the comment is resolved, the request becomes eligible and is merged through the permitted squash strategy.

The C++ design uses ordered maps for predictable lookup and deterministic iteration. With \(n\) stored entities, `std::map` lookup takes \(O(\log n)\) time. Merge evaluation scans review and check histories, so its cost depends on the size of those histories. A production service could maintain indexes or materialized state to reduce repeated work, provided it preserves correct behavior when new reviews or checks arrive.

The program does not model concurrent writers. A real service would need a database transaction or equivalent compare-and-swap mechanism around the eligibility decision and target-branch update.

## Java enterprise model

The Java program uses records for commits, reviewers, reviews, comments, status checks, and protection policies. Records provide concise immutable representations of evidence and policy values.

`Repository` acts as an aggregate root for branches, commits, reviewers, pull requests, and policies. `PullRequest` controls its own lifecycle and validates review, comment, and check relationships. `GovernanceService` calculates merge eligibility and performs the resulting state transition.

This division of responsibility is useful in enterprise applications because policy evaluation can be tested independently from request handling. The domain types also reduce the number of loosely structured values passed between services.

The latest review map prevents an earlier approval from overriding a later review decision. The full review history remains available for audit and diagnosis. Immutable check records preserve the evidence submitted by CI, while merge eligibility considers only checks for the current head.

The model intentionally rejects a merge when the pull request is not open, the target branch has advanced, the approval requirement is not met, a required check has failed, or a review discussion remains unresolved.

The sample uses in-memory collections and a synthetic merge identifier. A production implementation should persist aggregates and audit events, use transaction boundaries appropriate to the storage layer, enforce optimistic or pessimistic concurrency control, and separate authenticated identity from user-supplied actor strings.

## PostgreSQL relational model

### Primary keys and foreign keys

The schema uses identity columns for internal relational identifiers and repository-scoped commit identifiers for Git revision references.

Foreign keys prevent deletion of entities still referenced by governance history. `ON DELETE RESTRICT` is used where deleting a repository, branch, commit, review, or pull request could invalidate an audit trail.

The branch-to-commit relationship is composite. The database checks both the repository identifier and the commit SHA. The same pattern is used for pull request base, head, and merge revisions.

The repository default branch is also related to the branch table. Because repositories and branches depend on one another during initial creation, the default-branch foreign key is deferred until transaction completion.

### Constraints and triggers

The schema includes constraints for non-empty identifiers, unique repository names, unique branch names within repositories, unique pull request numbers within repositories, valid lifecycle states, valid review decisions, valid check states, and valid merge strategies.

The pull request merge-metadata constraint requires a merged request to have a merge SHA, a strategy, and a merge timestamp. An unmerged request must not contain those values.

Triggers add validation that depends on related rows or multiple columns. The review-eligibility trigger rejects self-approval and inactive reviewers. The check-integrity and review-integrity triggers verify that evidence commits belong to the request's repository.

Triggers complement foreign keys rather than replace them. A foreign key is preferable for straightforward existence and ownership rules because the database can enforce it directly. Triggers are useful when validation requires inspecting related records or enforcing a rule not expressed by a simple foreign key.

### Normalized policy tables

`policy_required_checks`, `policy_approver_teams`, and `policy_merge_strategies` represent one policy value per row.

This structure supports direct equality joins, foreign-key enforcement, uniqueness, and indexes. It also permits a policy to change without requiring application code to parse serialized lists.

The design uses a single active policy row per repository branch. A production system requiring policy history should preserve immutable policy versions or effective-date intervals rather than overwrite the only copy of a policy.

### Eligibility view

The `merge_eligibility` view calculates a policy decision from the current pull request, policy, latest review decisions, required checks, and unresolved discussions.

It exposes both the decision and supporting counts. This is useful for administrative interfaces and diagnostics because an operator can see whether the request lacks approvals, checks, or resolved discussions.

The view is a reporting and evaluation mechanism, not a concurrency lock. A query returning `policy_eligible = TRUE` does not guarantee that the target branch will remain unchanged until a later merge statement executes.

### Transactional merge function

`merge_pull_request` validates the request and selected strategy, locks the pull request and target branch, checks the active policy, and evaluates merge eligibility. If the checks pass, it creates a synthetic merge record, advances the target branch, updates the pull request, and writes an audit entry in the same database transaction.

An exception aborts the transaction unless the caller explicitly catches it within a savepoint or exception-handling block. The demonstration catches an expected failure so that the rest of the SQL script can execute.

The merge function models relational workflow consistency, not the construction of an actual Git commit. A production integration must coordinate with a trusted Git service that constructs the resulting tree and commit, verifies object identity, and confirms that the resulting commit matches the branch update.

The row locks help serialize concurrent merge attempts against the same target branch. Production deployments should still define transaction isolation, retry handling for deadlocks or serialization failures, and a concurrency protocol that ensures the validated target head is the one actually updated.

## Indexing and query performance

The schema creates indexes for common governance queries:

- Repository, state, and creation time support pull-request queue views.
- Repository, target branch, and state support reviews awaiting merge into a protected branch.
- Pull request, reviewer, and submission time support retrieval of current review decisions.
- Partial indexing of unresolved comments supports the discussion-resolution requirement.
- Pull request, commit, check context, and execution time support status-check lookup.
- Repository and event time support chronological audit inspection.

Indexes improve lookup performance at the cost of additional storage and write work. They should be validated against actual query plans and workload distributions. Indexing every column would add maintenance overhead without necessarily improving the queries that matter.

The latest-review view uses PostgreSQL's `DISTINCT ON` feature to select one record per reviewer and pull request. This is concise and effective for the chosen model, but other SQL engines require a window-function implementation such as `ROW_NUMBER()`.

## Failure modes and production boundaries

The model highlights several failures that a production governance system must handle explicitly.

| Failure | Required behavior |
|---|---|
| Duplicate branch or pull request identity | Reject the insert through a unique constraint. |
| Review references an unrelated commit | Reject the evidence through ownership validation. |
| Author approves their own request | Reject the review decision. |
| Reviewer is inactive | Exclude or reject the reviewer according to the operation. |
| New commit appears after approval | Apply stale-approval policy to the previous review. |
| Required check passed on an older head | Treat the current revision as unchecked. |
| Required check fails or remains pending | Reject the merge. |
| Review discussion remains unresolved | Reject the merge when the policy requires resolution. |
| Target branch advances | Require base synchronization and repeat eligibility evaluation. |
| Protected branch receives a direct push | Reject the operation unless an authorized exception applies. |
| Two merges race against the same branch | Serialize updates and re-evaluate the branch head. |
| Audit evidence is deleted | Prevent destructive deletion or preserve it in a separate immutable audit store. |

Some protections cannot be implemented by schema constraints alone. Direct-push and force-push restrictions must be enforced at the Git hosting or repository service boundary, not merely by storing Boolean values in a policy table. Likewise, commit signatures require verification against trusted keys and a defined trust policy.

The schema's `allow_administrator_bypass` attribute is configuration data, not proof that a caller may bypass a policy. A production implementation must authenticate the actor, evaluate authorization, record the bypass reason, and audit the exact requirements that were skipped.

The examples use application-level checks for certain lifecycle and policy rules because those rules require comparing multiple entities or current workflow state. For a multi-service deployment, the authoritative merge operation must re-evaluate those rules inside a transaction or equivalent atomic operation.

## Security and auditability

Repository governance data can reveal sensitive implementation details and internal security findings. Access controls should distinguish ordinary repository readers, reviewers, maintainers, administrators, and service identities.

Review comments should be retained according to the organization's audit and retention requirements. Audit records should capture the actor, action, affected pull request, relevant commit identifiers, selected merge strategy, and decision context.

The PostgreSQL sample uses an audit table and structured JSONB details. A production system should restrict direct modification of audit history and may export events to a separately controlled append-only audit service.

Database credentials should follow least-privilege principles. The merge service should receive only the privileges required to evaluate policy, record evidence, and update permitted state. Ordinary application users should not be able to modify protection rules or change branch heads directly.

The model's signed-commit field is only a verification result. It does not prove that a signature is trustworthy unless the verification process establishes the signing identity, key trust, revocation status, and the exact commit object that was checked.

## Modeling limitations

The project deliberately keeps the schema focused on repository governance rather than implementing all capabilities of a Git hosting platform.

It does not implement Git object storage, patch generation, three-way merge computation, cryptographic identity verification, branch ancestry traversal, merge-queue scheduling, team synchronization from an identity provider, or webhook authentication.

The SQL sample uses synthetic merge identifiers and simplified policy evaluation to demonstrate relational design and transaction structure. A production service must replace those parts with trusted Git operations, complete authorization checks, robust lifecycle enforcement, and concurrency controls appropriate to its deployment.

The key architectural distinction remains explicit: a Pull Request proposes a changeset, Code Review evaluates it, Approvals contribute policy-qualified decisions, and Branch Protection establishes the conditions that the repository must enforce before merging.
