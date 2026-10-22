# PL/pgSQL: Variables, Control Flow, and Functions

## Scope

This learning artifact treats PL/pgSQL as PostgreSQL's procedural layer for implementing reusable database-side behavior.

The five executable implementations use one coherent repository-governance domain. The central workflow evaluates Pull Requests against review, approval, status-check, conversation, and branch-protection conditions.

The focus is deliberately narrower than general repository governance:

- Variables store intermediate database state.
- Control flow decides how that state affects execution.
- Functions package reusable database behavior.
- Exception handling protects invalid operations.
- Loops process sets of records when procedural iteration is appropriate.
- SQL remains responsible for relational retrieval and set-based operations.

The relationship between the concepts can be represented as:

`relational data → variables → control flow → function result → state transition`

## PL/pgSQL Variables

A PL/pgSQL function can declare local variables in its `DECLARE` section.

The SQL implementation uses variables such as:

- `v_changed_files` for Pull Request size.
- `v_additions` and `v_deletions` for change magnitude.
- `v_approvals` for the number of approved reviews.
- `v_required_reviews` for the branch policy requirement.
- `v_failed_checks` for failed CI or validation checks.
- `v_unresolved` for unresolved review conversations.
- `v_score` for a calculated risk classification.
- `v_check` as a record variable during iteration.

Variables have explicit PostgreSQL types. This provides stronger guarantees than treating every intermediate value as an untyped application-level value.

The `SELECT ... INTO` construct assigns query results to local variables. The implementation also checks `FOUND` immediately after important lookups so that a missing Pull Request or missing policy is handled explicitly.

A useful distinction is:

| Mechanism | Purpose |
|---|---|
| Table column | Persistent relational state |
| Function parameter | Input supplied by the caller |
| Local variable | Temporary procedural state |
| Function return value | Result exposed to the caller |
| Record variable | Row-shaped value used during procedural processing |

The implementation avoids storing persistent information in variables. Variables exist only for the duration of the function invocation.

## Control Flow

The repository policy provides realistic conditions for procedural branching.

The merge evaluator first checks whether the Pull Request exists. It then verifies that a branch-protection policy exists for the target branch.

Subsequent conditions validate:

- Pull Request state.
- Source and target branch separation.
- Presence of changed files.
- Required approval count.
- Status-check results.
- Existence of status checks when checks are mandatory.
- Unresolved review conversations.

The SQL function uses `IF`, `ELSIF`, and `ELSE` for mutually exclusive risk classifications.

The risk calculation follows this structure:

`small change → LOW`

`moderate change → MEDIUM`

`large or insufficiently reviewed change → HIGH`

The implementation also uses early `RETURN` statements for policy failures. This prevents later checks from running after a decisive failure has already been identified.

## Loops and Record Processing

`count_failed_checks` demonstrates a PL/pgSQL `FOR` loop.

The function retrieves status-check records for a Pull Request and processes each row through a record variable. A counter is incremented when a check has failed.

This is useful when procedural behavior is required for each row. It is not automatically preferable to set-based SQL.

For a simple aggregate such as counting failed rows, a set-based query can usually be shorter and more efficient:

`SELECT count(*) FROM status_checks WHERE ...`

The loop is included because procedural iteration is an important PL/pgSQL control-flow mechanism and because it becomes useful when each iteration requires more complex procedural actions.

## Functions

The SQL implementation contains separate functions for separate responsibilities.

### `calculate_pr_risk`

This function reads Pull Request size, line changes, review activity, and unresolved conversations.

It assigns a local risk score and converts the score into `LOW`, `MEDIUM`, or `HIGH`.

The function demonstrates:

- Parameters.
- Local variables.
- `SELECT ... INTO`.
- `FOUND`.
- Arithmetic.
- Conditional branching.
- Scalar return values.

### `count_failed_checks`

This function demonstrates procedural iteration.

It returns the number of unsuccessful status checks associated with a Pull Request.

### `evaluate_merge_eligibility`

This function represents the main policy evaluator.

It returns a table containing:

- `eligible`
- `reason`

The function evaluates one policy condition at a time and stops at the first blocking condition.

Returning a structured result is useful when callers need both a Boolean decision and an explanation.

### `merge_pull_request`

This function uses the eligibility function before changing persistent state.

It records the decision in `merge_audit` and changes the Pull Request state only when all required conditions pass.

The operation therefore separates:

`evaluation → audit → state transition`

This is more maintainable than embedding every rule directly in an update statement.

## Exception Handling and Failure States

The SQL functions use `RAISE EXCEPTION` for conditions that indicate invalid or inconsistent database state.

Examples include:

- Referencing a nonexistent Pull Request.
- Missing eligibility results.
- A Pull Request changing state unexpectedly during a merge.
- Attempting to move a merged Pull Request back to another state.

The schema also uses declarative constraints for failures that should never be permitted.

Examples include:

- Negative changed-file counts.
- Negative additions or deletions.
- Negative approval requirements.
- Empty branch names.
- Empty Pull Request titles.
- Invalid branch relationships.
- Invalid review-comment content.

This demonstrates an important design distinction:

**Constraints protect data invariants; PL/pgSQL functions implement procedural decisions.**

A database should not rely exclusively on procedural validation when a rule can be expressed directly as a constraint.

## Trigger-Based State Protection

The `prevent_invalid_merge_state` trigger function protects a Pull Request state invariant.

A merged Pull Request cannot transition back to `open` or `closed`.

The trigger also ensures that a merge timestamp exists when the state becomes `merged`.

This is different from the merge function.

The merge function decides whether a Pull Request is eligible.

The trigger protects a state invariant regardless of which SQL operation attempts the update.

## Python Implementation

The Python program models the same domain without a database server.

`PullRequest`, `Review`, and `PullRequestState` provide explicit domain structures.

The implementation demonstrates:

- Dataclasses.
- Enums.
- Lists and dictionaries.
- Validation functions.
- Generator-style counting.
- Dictionary aggregation.
- Exception handling.
- Reusable functions.
- Explicit state transitions.

`evaluate_merge_eligibility` separates policy evaluation from the `safe_merge` state transition.

This mirrors the database design while making the procedural state visible in ordinary Python objects.

`process_status_checks` normalizes status-check names and builds a dictionary that can be evaluated efficiently.

The validation function rejects empty or unsafe identifiers before they enter the workflow model.

## JavaScript Implementation

The JavaScript implementation emphasizes event-driven processing.

`RepositoryWorkflow` extends `EventEmitter` and emits events when:

- A Pull Request is created.
- A status check completes.
- A Pull Request is merged.

The status checks are asynchronous functions returning Promises. This models CI-like processing without requiring an external service.

A `Map` stores status-check results, making the implementation naturally suited to event-driven updates.

The program also uses:

- Classes.
- Promises.
- `async` and `await`.
- `Map`.
- Event emitters.
- UUID generation.
- Custom exceptions.
- Input validation.

The asynchronous status checks are intentionally deterministic so the program remains self-contained.

The implementation does not attempt to reproduce PostgreSQL's execution model. It instead demonstrates how the same policy domain behaves when procedural work is coordinated through asynchronous events.

## C++ Implementation

The C++ program implements a repository-governance engine.

Its principal design object is `RepositoryGovernance`, which owns branch-protection policies and evaluates Pull Requests against them.

The implementation uses:

- `enum class` for explicit state types.
- `struct` for domain records.
- `std::map` for branch-policy lookup.
- `std::vector` for reviews and checks.
- Exceptions for invalid governance operations.
- Result objects for merge decisions.

`EligibilityResult` contains both a Boolean result and a collection of blocking reasons.

The engine does not mutate a Pull Request during evaluation. Mutation occurs only after successful eligibility evaluation.

This separation reduces accidental state changes during validation.

The branch-protection model contains policy-specific fields such as required approvals, successful checks, resolved conversations, direct-push restrictions, force-push restrictions, deletion restrictions, and linear-history requirements.

## Java Implementation

The Java program represents an enterprise-oriented governance service.

Java records are used for immutable value-oriented types:

- `Review`
- `StatusCheck`
- `BranchPolicy`
- `EligibilityResult`

The mutable `PullRequest` class represents lifecycle state.

The `MergeEligibilityService` owns branch policies and performs merge evaluation.

Java streams are used to count approved reviews, while ordinary collections represent policies and checks.

The model makes state transitions explicit:

`OPEN → MERGED`

and prevents an invalid merged-state reversal.

`MergeStrategy` expresses the selected merge mechanism as a domain value rather than a free-form string.

This structure makes policy evaluation independently testable and keeps domain rules out of the program entry point.

## PostgreSQL Relational Model

The SQL schema models:

| Table | Purpose |
|---|---|
| `repositories` | Repository identity and default branch |
| `branches` | Repository branches and protection status |
| `repository_users` | Repository participants |
| `pull_requests` | Proposed repository changes |
| `commits` | Commits associated with Pull Requests |
| `review_assignments` | Requested reviewers |
| `reviews` | Reviewer decisions |
| `review_comments` | Review discussion and resolution state |
| `status_checks` | Automated validation results |
| `branch_protection_policies` | Target-branch governance requirements |
| `merge_audit` | Recorded eligibility decisions |

Foreign keys maintain relationships between these entities.

Check constraints protect basic invariants at the database layer.

Partial indexing on unresolved review comments demonstrates an index targeted at a frequently queried subset rather than indexing every possible column indiscriminately.

## Set-Based SQL and Procedural SQL

PL/pgSQL should not replace ordinary SQL unnecessarily.

A relational query is generally preferable when the task can be expressed naturally as a set operation.

For example, counting approved reviews is naturally represented as an aggregate query.

Procedural code becomes more valuable when the workflow requires:

- Multiple intermediate variables.
- Branch-dependent decisions.
- Sequential validation.
- Explicit failure messages.
- Iterative processing.
- Controlled state transitions.
- Exception handling.

The implementation deliberately combines both approaches.

SQL retrieves and aggregates relational state.

PL/pgSQL interprets that state through procedural rules.

## Transactional Merge Workflow

The merge operation is demonstrated inside a transaction:

`BEGIN`

`merge_pull_request(...)`

`COMMIT`

The function records an audit decision before updating the Pull Request.

The database therefore retains evidence of the evaluation even when the Pull Request remains blocked.

A production implementation would normally place the full merge operation and any associated repository metadata changes inside one transaction so that partial state cannot be committed.

Concurrency remains an important limitation. If multiple workers can modify the same Pull Request simultaneously, row locking such as `SELECT ... FOR UPDATE` may be required around the state transition.

## Edge Cases

The implementations explicitly handle several failure conditions.

### Missing Pull Request

A function lookup can return no row. The SQL implementation checks `FOUND` rather than silently operating on null variables.

### Missing Branch Policy

A target branch without a protection policy is treated as a governance failure in the merge evaluator.

### No Reviews

The risk functions treat the absence of reviews as elevated risk.

### Insufficient Approvals

A Pull Request with fewer approvals than required remains ineligible.

### Failed Status Checks

A required failed check prevents merging.

### Missing Status Checks

When status checks are required, an empty check collection is treated as a failure rather than an implicit success.

### Unresolved Conversations

A policy requiring resolved discussions blocks a Pull Request when unresolved conversations remain.

### Invalid State Transition

The trigger prevents a merged Pull Request from moving back to an earlier state.

## Performance Considerations

The database implementation uses indexes for recurring access paths:

- Repository and state filtering on Pull Requests.
- Pull Request and review state filtering.
- Pull Request lookup for status checks.
- Unresolved review comments.

The procedural functions avoid unnecessary repeated queries where one query can populate several local variables.

The C++ implementation uses `std::map` for branch-policy lookup and linear traversal for the small collections associated with each Pull Request.

The Java implementation uses a `HashMap` for branch-policy retrieval.

The JavaScript implementation uses a `Map` for status-check state and processes asynchronous checks sequentially to keep the example deterministic.

For a large production system, independent status checks could be executed concurrently, while database aggregation should generally remain set-based rather than processing millions of rows through a PL/pgSQL loop.

## Security and Integrity

Branch names and identifiers are validated before entering the application-level workflow models.

The PostgreSQL implementation uses parameters rather than dynamically constructed SQL statements inside its functions, reducing SQL-injection exposure.

Foreign keys prevent orphaned reviews, comments, checks, and Pull Requests.

Check constraints prevent structurally invalid numeric values.

Database-side policy evaluation is useful when merge eligibility is considered an integrity-sensitive operation because callers cannot bypass the rules merely by implementing different application logic.

Production authorization still requires a separate access-control layer. A PL/pgSQL function deciding that a Pull Request is eligible does not by itself prove that the calling database role is authorized to invoke the operation.

## Relationship Between the Implementations

The implementations intentionally use different perspectives rather than being line-by-line translations.

| Implementation | Primary perspective |
|---|---|
| Python | Procedural repository workflow simulation |
| JavaScript | Asynchronous and event-driven policy processing |
| C++17 | Repository governance and merge-eligibility engine |
| Java 17 | Enterprise domain model and policy service |
| PostgreSQL | Database-resident procedural workflow |

All five implementations share the same conceptual boundary:

`data → validation → variables/state → control flow → decision → controlled state change`

The PostgreSQL implementation is the direct study of PL/pgSQL itself. The other four implementations provide contrasting ways to express equivalent procedural ideas in application runtimes while preserving the same repository-governance domain.
