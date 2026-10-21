# PostgreSQL Functions for Repository Governance

This project studies PostgreSQL functions through a realistic repository-governance model. The database represents Pull Requests, commits, reviews, review comments, status checks, branch-protection policies, reviewer eligibility, and merge decisions.

The central distinction is preserved throughout the implementation:

- **Pull Request**: the workflow object used to propose a changeset from a source branch into a target branch.
- **Code Review**: the evaluation activity performed against that changeset.
- **Approval**: a particular review decision indicating that an eligible reviewer accepts the current changeset.
- **Branch Protection**: the repository-level policy that determines which conditions must hold before a protected branch can accept a merge.

The implementations use these concepts as the domain while focusing technically on functions, procedural functions, validation, state evaluation, and reusable business rules.

## PostgreSQL Function Model

A PostgreSQL function packages database logic behind a callable interface.

Two function styles are used:

| Function type | Implementation role |
|---|---|
| SQL function | Compact, declarative queries such as retrieving a review state or counting current approvals |
| PL/pgSQL function | Conditional governance evaluation requiring variables, branching, loops, and explicit failure states |
| Trigger function | Database-level integrity enforcement when review records are inserted or updated |

The SQL functions include `latest_reviewer_state()` and `current_approval_count()`.

`latest_reviewer_state()` returns the most recent review state submitted by a reviewer for a particular Pull Request. The ordering uses submission time and review identifier so that multiple reviews from the same reviewer have deterministic precedence.

`current_approval_count()` deliberately counts approvals associated with the latest commit in the Pull Request. This models the important distinction between an approval decision and an approval that remains applicable to the current changeset.

A new commit can therefore make earlier approvals ineffective until reviewers submit new approvals against the new commit.

## Procedural Function

The central procedural function is `evaluate_merge_eligibility()`.

It is implemented with PL/pgSQL because merge eligibility requires several dependent checks:

- The Pull Request must exist.
- The Pull Request must be open.
- A draft Pull Request cannot be merged.
- The Pull Request must be synchronized with the target branch.
- The target branch must have a protection policy.
- The number of current eligible approvals must satisfy the policy.
- Required status checks must pass.
- Required review conversations must be resolved.

The function returns a relational result containing an eligibility value and a concrete failure reason.

This design makes a policy function useful both to application code and to SQL reporting.

Conceptually, the workflow is:

Repository state → Pull Request state → Review state → Approval applicability → Branch policy → Function evaluation → Merge decision

## SQL Function Versus Procedural Function

A SQL-language function is appropriate when the operation can be expressed naturally as one relational query.

For example, approval counting is primarily a query over reviews and commits. The database optimizer can plan that query without procedural control flow.

PL/pgSQL becomes useful when the rule requires explicit decision-making. `evaluate_merge_eligibility()` stores intermediate records, evaluates conditions, iterates over required status checks, and returns distinct failure conditions.

The distinction is architectural rather than merely syntactic.

| Requirement | Suitable mechanism |
|---|---|
| Return one derived value from a query | SQL function |
| Encapsulate a reusable relational query | SQL function |
| Conditional policy evaluation | PL/pgSQL |
| Iterate over policy requirements | PL/pgSQL |
| Reject invalid cross-record relationships | Trigger function |
| Produce a reusable reporting surface | Function plus view |

## Pull Request Lifecycle

The model represents the important lifecycle states as:

`draft → open → merged`

with a separate closing path:

`open → closed → open`

A draft Pull Request is a proposal that is not yet ready for the protected merge workflow. Once ready, it becomes an open Pull Request and can receive review decisions.

The source branch identifies where the changes originate. The target branch identifies the branch that would receive them.

The Pull Request stores `base_revision`, allowing the function to detect whether the target branch has advanced since the Pull Request was prepared.

A mismatch indicates that the Pull Request needs synchronization before it can satisfy the modeled merge policy.

The relational model stores individual commits rather than treating a Pull Request as an undifferentiated block of changes. This permits reviews to reference a specific changeset.

## Code Review

Code Review is represented by the `reviews` table and `review_comments` table.

A review contains:

- reviewer
- review state
- referenced commit
- submission timestamp

The supported states are:

- `commented`
- `approved`
- `changes_requested`
- `dismissed`

Inline review comments identify a file path and optionally a line number. Comments also have a resolution state.

This separates the existence of a review decision from the discussion generated during that review.

A reviewer can therefore approve a changeset while comments are still present, while branch protection may independently require all review conversations to be resolved before merging.

The database trigger `validate_review_commit()` prevents a review from referencing a commit belonging to another Pull Request. This is a database integrity rule rather than an application convention.

## Approvals

An approval is not simply the existence of a review row whose state is `approved`.

The implementation treats an approval as applicable only when:

- the reviewer is active,
- the reviewer has an eligible repository role,
- the latest review from that reviewer is an approval,
- the approval references the current Pull Request changeset.

This is why a new commit can reduce the current approval count even though historical approval records remain stored.

Historical reviews are not deleted when they become stale. Keeping them provides an audit trail while the function evaluates their current effectiveness.

The Java implementation expresses this same domain rule with explicit records and an eligibility service. The C++ implementation represents the policy engine with concrete data structures and explicit evaluation results.

## Branch Protection

Branch protection is represented independently from Pull Requests and reviews.

The `branch_protection` table controls repository-level conditions such as:

- required review count
- resolved conversation requirement
- direct-push restrictions
- force-push restrictions
- deletion restrictions
- linear-history requirements

Required status checks are normalized into `protected_status_requirements`.

This means a protected branch can require `unit-tests` and `security-scan` without embedding those requirements into individual Pull Request rows.

The relationship is therefore:

**Pull Request** proposes the change.

**Code Review** evaluates the change.

**Approval** records a qualifying review decision.

**Branch Protection** defines the conditions that make the proposed merge acceptable.

The four mechanisms are related but are not interchangeable.

## Python Implementation

The Python program models repository workflow behavior using dataclasses and enumerations.

`PullRequest`, `Review`, `Commit`, `StatusCheck`, `BranchProtection`, and `Repository` represent the domain state.

The implementation demonstrates several important workflow transitions.

`request_review()` validates that the Pull Request is active and not a draft.

`submit_review()` requires the referenced commit to belong to the Pull Request.

`synchronize_base()` updates the Pull Request's base revision after target-branch movement.

`merge_eligibility()` combines review, status-check, conversation, branch-protection, and synchronization rules.

`merge_pull_request()` performs the final state transition only after eligibility succeeds.

The example deliberately introduces a new commit after two approvals. The first eligibility evaluation succeeds after the conversation is resolved. The new commit then makes the previous approvals stale because they reference the old changeset. New approvals are required before the merge succeeds.

## JavaScript Implementation

The JavaScript program uses an event-driven repository object.

The `Repository` class manages branches and Pull Requests and exposes event listeners for changes such as:

- Pull Request creation
- Pull Request readiness
- review submission
- status-check completion
- synchronization
- merge completion

This provides a complementary perspective to the database model. PostgreSQL functions centralize durable database rules, while event-driven application code can react to workflow changes.

`evaluatePolicy()` remains separate from event handling. This separation prevents event listeners from becoming the authoritative source of merge policy.

The example demonstrates unresolved review conversations, successful status checks, two approvals, a new commit, stale approvals, renewed approvals, and a final squash merge.

The use of `Map` for checks and reviewer state makes replacement of a reviewer's latest decision explicit.

## C++ Implementation

The C++ program implements a repository-governance engine.

`GovernanceEngine` stores branch-protection policies and evaluates Pull Requests against them.

The implementation emphasizes explicit policy evaluation rather than database persistence. It uses:

- `std::map` for policies and latest-review lookup
- `std::set` for required checks and eligible reviewers
- `std::vector` for ordered commits and review history
- `std::optional` for the merge strategy
- enumerations for workflow states

The `Eligibility` structure separates a Boolean decision from its failure reasons.

This is important for operational systems because a blocked merge should explain which governance conditions failed.

The implementation also models linear-history protection. A policy requiring linear history rejects a merge-commit strategy while allowing strategies such as rebase when other conditions are satisfied.

## Java Implementation

The Java program represents repository governance as an enterprise-oriented domain model.

Java records are used for immutable value-like objects such as `Commit`, `Review`, `StatusCheck`, `BranchProtection`, and `MergeDecision`.

`PullRequest` owns state transitions and validates operations that modify its domain state.

`MergeEligibilityService` owns policy evaluation rather than placing every governance rule inside the Pull Request object.

This separation creates a useful boundary:

`PullRequest` manages state.

`BranchProtection` describes policy.

`MergeEligibilityService` evaluates policy against state.

`MergeDecision` carries both the result and failure reasons.

Java collections and streams are used where they improve the representation of reviewer and approval evaluation. The example again makes approvals changeset-sensitive, so a new commit requires fresh approvals.

## PostgreSQL Schema

The database contains these primary relationships:

    repositories
        |
        +-- repository_users
        |
        +-- branches
               |
               +-- branch_protection
               |      |
               |      +-- protected_status_requirements
               |
               +-- pull_requests
                      |
                      +-- commits
                      |
                      +-- reviews
                      |     |
                      |     +-- review_comments
                      |
                      +-- status_checks

The schema uses PostgreSQL enumerated types for workflow states.

Foreign keys preserve relationships between repository objects. Unique constraints prevent duplicate repository names, branch names within a repository, Pull Request numbers within a repository, commit sequence numbers within a Pull Request, and status-check names within a Pull Request.

Check constraints enforce local invariants such as positive revisions and review counts.

## PostgreSQL Trigger Function

`validate_review_commit()` is a trigger function rather than a normal callable business function.

Its purpose is database integrity.

A review contains both a Pull Request identifier and a commit identifier. A foreign key can verify that the referenced commit exists, but it cannot by itself guarantee that the commit belongs to the same Pull Request.

The trigger performs that cross-record validation.

This illustrates a useful distinction:

- Functions can calculate or evaluate business information.
- Trigger functions can automatically enforce rules during table modifications.

The trigger executes before review insertion or update, so invalid relationships are rejected before they become persistent data.

## Transactions and Concurrency

The final merge operation uses a transaction.

The Pull Request row is locked with `FOR UPDATE` before eligibility is evaluated and the merged state is written.

This matters because merge eligibility is a state-dependent decision. Without transactional protection, two concurrent operations could evaluate the same Pull Request based on assumptions that become invalid before either transaction completes.

The transaction therefore groups:

`lock → evaluate → state transition → commit`

If eligibility fails, the procedural function raises an exception and the transaction does not complete the merge.

## Stale Approvals

Stale approvals are one of the most important relationships in the model.

Suppose the current commit is `2222222` and two eligible reviewers approve it.

The database function counts both approvals.

If commit `3333333` is subsequently added, the current changeset becomes `3333333`.

The previous approvals remain historically recorded, but they no longer satisfy the current-commit condition.

This prevents an approval from silently applying to code that the reviewer never evaluated.

The same principle is implemented in Python, C++, JavaScript, and Java so that the five implementations share the same governance scenario while using different technical mechanisms.

## Status Checks

Status checks are modeled separately from reviews.

A review answers whether a reviewer has evaluated the code.

A status check represents an automated repository condition such as tests or security validation.

The branch-protection policy specifies which checks are required.

The procedural PostgreSQL function iterates through required checks and returns a failure for every missing or unsuccessful requirement.

This avoids treating successful review as sufficient by itself.

## Conversations

Review discussions have their own state through `review_comments.resolved`.

An unresolved comment is not itself a review state. A reviewer can submit an approval while a discussion remains unresolved.

The branch-protection policy determines whether unresolved discussions prevent merging.

This keeps review activity distinct from branch-level enforcement.

The resulting relationship is:

`Review comment → discussion state`

`Branch protection → whether unresolved discussion blocks merge`

The two concepts therefore remain independent while still interacting during merge evaluation.

## Performance Considerations

The database uses indexes for access patterns that are directly relevant to governance evaluation.

`idx_pr_target_state` supports finding Pull Requests by target branch and state.

`idx_reviews_pr_reviewer` supports retrieval of review history for a Pull Request and reviewer.

`idx_comments_unresolved` is a partial index because merge evaluation only needs unresolved comments when the policy requires conversation resolution.

`idx_status_checks_pr` supports required status-check lookup.

The current approval function uses ordered review history and current commit identification. For a large repository, the review-history query may become a significant workload. Appropriate indexing and careful query planning are therefore important when the number of reviews grows substantially.

## Security and Integrity Considerations

Repository governance should not depend exclusively on client-side validation.

The SQL implementation places important integrity rules in the database:

- foreign keys prevent orphaned records,
- unique constraints prevent conflicting identifiers,
- check constraints enforce local invariants,
- trigger functions enforce cross-record review consistency,
- transactional locking protects the merge transition.

The application implementations also reject invalid states before performing transitions.

Production systems should use least-privilege database roles. A reporting role should not automatically receive permissions to modify Pull Requests or branch policies.

Function privileges should also be reviewed carefully when functions perform privileged operations. A function that can modify protected repository state represents a meaningful authorization boundary.

## Failure Conditions Represented

The implementations explicitly handle:

- nonexistent Pull Requests
- invalid branch names
- empty Pull Requests
- invalid reviewers
- reviews against unrelated commits
- closed or merged Pull Requests
- draft Pull Requests
- missing status checks
- failed status checks
- insufficient approvals
- stale approvals
- unresolved conversations
- unsynchronized target branches
- missing branch protection
- linear-history violations
- invalid merge strategies
- invalid database relationships

These failures are represented as exceptions, rejected state transitions, policy failure records, or database constraint violations depending on the implementation.

## Function Design Principles Demonstrated

The project applies several principles relevant to PostgreSQL function design.

**Keep declarative logic declarative.**

Simple relational derivations are implemented as SQL-language functions rather than procedural loops.

**Use procedural functions for branching policy.**

PL/pgSQL is appropriate when multiple dependent conditions and explicit failure paths are required.

**Keep integrity close to the data.**

Cross-record invariants that must hold regardless of the calling application are enforced with trigger functions and constraints.

**Return structured results when diagnostics matter.**

The merge-eligibility function returns both a Boolean decision and a reason rather than returning only a Boolean.

**Keep historical decisions immutable.**

Old approvals remain stored so that repository activity can be audited even when those approvals are no longer applicable to the current changeset.

**Make state transitions explicit.**

A Pull Request does not become merged merely because enough rows exist. The transition requires the policy function to confirm that the complete protected-branch policy is satisfied.

## Practical Relationship

The complete model can be represented as:

    Source Branch
         |
         | proposes changes
         v
    Pull Request
         |
         | contains
         v
       Commits
         |
         | evaluated through
         v
     Code Review
         |
         +---- Review Comments
         |
         +---- Review Decisions
                    |
                    | current eligible approval
                    v
            Approval Requirement
                    |
                    v
             Branch Protection
                    |
                    +---- Required Reviews
                    +---- Required Checks
                    +---- Conversation Rules
                    +---- History Restrictions
                    |
                    v
           PostgreSQL Function
                    |
                    v
            Merge Eligibility
                    |
                    v
                  Merge

The essential boundary remains clear: a Pull Request provides the proposal workflow, Code Review evaluates the changes, Approvals record review decisions, and Branch Protection enforces repository-level conditions. PostgreSQL functions provide reusable, centralized mechanisms for evaluating those rules against authoritative relational state.
```
