# Storage Fundamentals: Repository Governance Workflow

## Scope

This project implements a repository-development governance model using five executable artifacts:

| File | Engineering perspective |
|---|---|
| Python | Object-oriented simulation of pull request and merge governance |
| JavaScript | Event-driven repository workflow and policy evaluation |
| C++17 | Explicit merge-eligibility engine using STL domain models |
| Java 17 | Enterprise-style governance service with domain types and policy objects |
| PostgreSQL | Relational model, constraints, indexes, triggers, views, functions, and transactional evaluation |

The implementations model a repository workflow in which proposed changes move from a source branch toward a protected target branch. The model separates proposed changes, branch state, review decisions, approval decisions, automated checks, repository policy, and final merge eligibility.

## Domain Model

The central relationship is:

Repository  
→ Branches  
→ Commits  
→ Pull Requests  
→ Reviews  
→ Review Comments  
→ Conversations  
→ Status Checks  
→ Branch Protection Policies  
→ Approval Requirements  
→ Merge Eligibility  
→ Merge

Each stage has a different responsibility.

A branch identifies a line of development and has a current commit at its head. A commit represents a versioned change. A pull request proposes a set of source-branch changes against a target branch. Reviews evaluate those changes. Approvals represent explicit review decisions. Status checks represent automated validation. Branch protection defines repository-level conditions. Merge eligibility combines those conditions into a decision.

## Pull Request Lifecycle

A pull request is modeled as a stateful proposal.

The supported states are:

| State | Meaning |
|---|---|
| `draft` | Work exists but is not ready for normal merge evaluation |
| `open` | Proposed changes are available for review |
| `closed` | Proposal has been closed without merging |
| `merged` | Proposed changes have been accepted into the target branch |

A draft pull request can be marked ready. An open pull request can be reviewed, synchronized, closed, or merged when governance requirements are satisfied. A closed pull request can be reopened. A merged pull request is terminal in the implementations.

The source branch contains the proposed changes. The target branch represents the branch into which those changes may eventually be integrated.

The target branch state is captured when the pull request is created. If the target branch advances later, the original base state no longer represents the current target state. The implementations therefore treat synchronization as necessary before merge eligibility can be granted when branch protection requires a current base.

## Pull Request Mechanics

A pull request records:

- source branch
- target branch
- author
- title
- proposed commits
- initial target-branch head
- current state
- draft status
- reviews
- status checks
- unresolved conversations
- merge strategy

The proposed changes are not themselves the target branch.

This distinction is important:

`source branch state` → proposed changes

`target branch state` → current integration destination

`pull request` → workflow object connecting those two states

A change in the target branch can therefore invalidate assumptions made when the pull request was opened.

The implementations support merge strategies including merge commits, squash merging, and rebase-style integration.

## Changesets and Commits

A commit contains a unique identifier, message, and parent relationship.

A pull request references the commits associated with its proposed changes. The source branch can continue advancing while review is taking place.

The Python, C++17, and Java implementations explicitly model commit ancestry. The PostgreSQL implementation stores commit relationships with a self-referencing foreign key.

A pull request therefore represents a proposed changeset rather than an independent copy of repository history.

## Code Review

Code Review evaluates the proposed changes.

It is distinct from the pull request itself.

The pull request provides the workflow container. Code Review supplies human evaluation of the proposed implementation.

Reviews can contain:

- reviewer identity
- review state
- reviewed commit
- comments
- dismissal state

Supported review states include:

- `commented`
- `approved`
- `changes_requested`
- `dismissed`

An inline or review comment identifies an observation about the proposed changes. A conversation can remain unresolved until the relevant issue has been addressed.

Review quality depends on the reviewer examining the appropriate commit state. The implementations therefore associate reviews with a specific commit. Older reviews can become stale when the source branch changes.

## Review Responsibilities

A reviewer should evaluate the scope and correctness of the proposed change rather than treating approval as a generic repository permission.

Typical review criteria represented by the implementations include:

- correctness of the proposed behavior
- validation of boundaries
- consistency with repository policy
- test coverage through status checks
- failure handling
- security-sensitive behavior
- unintended changes
- maintainability

The distinction between comments and approvals is deliberate. A comment can provide feedback without approving the changes.

A requested-change review can prevent merge eligibility even when other reviewers have approved the pull request.

## Approvals

An approval is a review decision.

It indicates that an eligible reviewer has evaluated the relevant proposed changes and approved them.

The implementations count distinct valid reviewers rather than counting review records blindly. Dismissed reviews are excluded. Reviews associated with stale commit states can also be excluded from current approval calculations.

For example, a policy can require two approvals:

`Required approvals = 2`

`Current valid approvals = 1`

`Merge eligibility = false`

When the second valid approval is recorded, that particular condition can become satisfied.

Approval does not independently force a merge. It contributes one condition to a larger repository-governance decision.

## Stale and Dismissed Approvals

An approval is associated with a reviewed commit.

If the proposed changes subsequently change, the earlier review may no longer represent the current source state. The implementations use commit identity to distinguish current reviews from stale ones.

A dismissed approval is also excluded from the active approval count.

This produces an important distinction:

`review decision` → what a reviewer decided

`approval validity for merge` → whether that decision satisfies the current repository policy

The second depends on repository state and governance rules.

## Branch Protection

Branch Protection governs the target branch.

It is not a review and it is not a pull request.

A protected branch can enforce conditions such as:

- required reviews
- required status checks
- restricted direct pushes
- restricted force pushes
- conversation resolution
- linear-history requirements
- administrator bypass policy

The target branch can therefore remain protected even when a particular pull request is closed or rejected.

The relationship is:

`Pull Request` proposes changes.

`Code Review` evaluates changes.

`Approval` records a review decision.

`Branch Protection` enforces repository-level conditions.

`Merge Eligibility` evaluates whether all relevant conditions currently permit integration.

## Required Status Checks

Status checks represent automated validation.

Examples used in the implementations include:

- `unit-tests`
- `storage-integrity`

A required check must exist and pass before the pull request can become merge eligible.

This separates automated validation from human review.

A pull request may have sufficient approvals but still be blocked because an automated check failed.

The reverse is also possible: all checks can pass while the required number of approvals has not been reached.

## Review Conversations

Review comments can form conversations requiring resolution.

The models track unresolved conversation counts at the pull-request level.

When a branch policy requires conversation resolution, any remaining unresolved conversation blocks merge eligibility.

This rule addresses a governance condition rather than evaluating the technical correctness of the comment itself.

## Merge Eligibility

Merge eligibility is a derived decision.

A protected target branch can require all of the following:

1. Pull request is open.
2. Pull request is not a draft.
3. Proposed changes exist.
4. Target branch has not advanced unexpectedly.
5. Required approvals exist.
6. No active reviewer has requested changes.
7. Required status checks exist and pass.
8. Required review conversations are resolved.
9. Other branch-level requirements are satisfied.

The implementations collect failure reasons rather than returning only a Boolean value.

Example:

`eligible = false`

`reasons = [required approvals missing, storage-integrity check failed]`

This makes policy evaluation auditable and easier to debug.

## Merge Strategies

The implementations model three common integration strategies.

| Strategy | Behavior |
|---|---|
| Merge commit | Adds an explicit integration commit |
| Squash | Represents the proposed changes as one target-branch commit |
| Rebase | Replays source commits with new identities |

The strategy does not replace branch protection. A merge strategy controls how accepted changes are integrated after eligibility has been established.

## Synchronizing the Base Branch

A pull request records the target branch head when it is created.

Suppose:

`main = A`

A feature pull request is opened against `main` at `A`.

Later:

`main = A → C`

The pull request was originally evaluated against `A`, not `C`.

The implementations therefore compare the recorded base commit with the current target head.

If they differ, the pull request must be synchronized before the protected merge can proceed.

This protects the merge decision from silently ignoring changes that entered the target branch after review began.

## Merge Conflicts

A merge conflict occurs when proposed changes cannot be integrated cleanly with the current target state.

The implementations model the prerequisite state comparison and synchronization requirement rather than implementing a complete textual three-way merge engine.

This is a deliberate boundary.

The governance engine answers:

`Is the pull request based on the required target state?`

It does not attempt to reconstruct arbitrary source-code conflict resolution.

Conflict resolution belongs to the branch and changeset workflow before final merge eligibility is established.

## Reopening and Closing Pull Requests

Closing a pull request removes it from the active merge workflow.

The models prevent closed pull requests from receiving normal review activity or being merged.

A closed pull request can be reopened.

A merged pull request cannot be reopened as an ordinary open proposal because the integration has already occurred.

This creates explicit state transitions instead of treating a pull request as an unstructured record.

## Administrator and Bypass Controls

Branch protection can include administrator bypass policy.

The PostgreSQL schema stores `allow_admin_bypass`, while the application models expose administrator-related policy state.

A bypass mechanism is a governance exception, not an approval.

This distinction matters because bypassing a protection condition does not transform an administrator action into a reviewer approval.

Production systems should audit bypass operations independently because they can weaken ordinary repository controls.

## Python Implementation

The Python implementation uses dataclasses and enumerations to represent repository objects.

The principal classes are:

- `Commit`
- `Branch`
- `Review`
- `StatusCheck`
- `BranchProtection`
- `PullRequest`
- `Repository`

The `Repository.merge_eligibility()` method evaluates branch state, approvals, requested changes, status checks, and conversation requirements.

The example creates a protected `main` branch and a feature branch implementing a physical storage model. Two approvals and two passing status checks are required before the merge succeeds.

The implementation also demonstrates failure handling for direct pushes to a protected branch.

## JavaScript Implementation

The JavaScript implementation uses classes, `Map`, `Set`, immutable configuration patterns, and Node.js `EventEmitter`.

Repository events include:

- pull request creation
- merge rejection
- successful merge

This makes the implementation event-driven rather than a direct line-by-line translation of the Python model.

`evaluateMerge()` returns both eligibility and a list of policy failures. `merge()` consumes that decision and changes the pull request state only after all required conditions pass.

The example also uses Node's standard `crypto` module to derive a deterministic squash-commit identifier.

## C++17 Implementation

The C++ implementation uses explicit domain classes, structures, enumerations, STL containers, algorithms, and exceptions.

The `Repository::evaluateMerge()` function evaluates:

- pull request state
- draft state
- target branch synchronization
- reviewer approvals
- requested changes
- status checks
- unresolved conversations

The use of `std::set` for approvals provides distinct-reviewer semantics. `std::map` provides indexed lookup for branches, pull requests, protection policies, and status checks.

The implementation does not depend on third-party libraries.

## Java 17 Implementation

The Java implementation uses records for immutable value-oriented domain objects such as commits, status checks, review comments, and branch protection policies.

Mutable workflow objects are represented by classes.

The main domain types are:

- `Commit`
- `Review`
- `ReviewComment`
- `Branch`
- `BranchProtectionPolicy`
- `PullRequest`
- `Repository`
- `MergeEvaluation`

The repository evaluates merge eligibility through a dedicated service-style method rather than embedding all governance behavior in the pull request object.

This separates the proposed change from repository-level policy.

## PostgreSQL Data Model

The PostgreSQL implementation stores repository governance as relational data.

The principal relationships are:

`repositories`  
→ `branches`  
→ `commits`

and:

`pull_requests`  
→ `pull_request_commits`  
→ `commits`

and:

`pull_requests`  
→ `reviews`  
→ `review_comments`

and:

`pull_requests`  
→ `status_checks`

and:

`branches`  
→ `branch_protection_policies`  
→ `required_status_checks`

The `merge_eligibility_audit` table records eligibility evaluations and their failure reasons.

## Relational Integrity

Foreign keys prevent references to nonexistent repository objects.

Unique constraints prevent duplicate repository names within an owner, duplicate branch names within a repository, duplicate commit identifiers within a repository, and duplicate status-check names for a pull request.

Check constraints enforce valid values such as:

- positive review requirements
- nonnegative unresolved conversations
- nonempty commit messages
- nonempty pull request titles
- distinct source and target branches

The database therefore enforces structural correctness instead of relying exclusively on application code.

## PostgreSQL Indexing

Indexes are provided for common governance queries.

Important indexes include:

| Index | Purpose |
|---|---|
| Repository and commit SHA | Commit lookup |
| Target branch and PR state | Protected-branch workflow queries |
| Pull request and review state | Approval evaluation |
| Review and comment resolution | Conversation queries |
| Pull request and check name | Status-check evaluation |
| Pull request and commit position | Changeset reconstruction |

These indexes reduce lookup work as repository activity grows.

## PostgreSQL Merge Evaluation

The `evaluate_merge_eligibility()` function evaluates a pull request inside PostgreSQL.

It checks:

- pull request state
- draft state
- target-branch synchronization
- required approvals
- requested changes
- required status checks
- unresolved conversations

The function returns an eligibility flag and an array of failure reasons.

It also writes an audit record.

This makes the database capable of serving as a policy-evaluation layer rather than merely storing repository data.

## Database Trigger

The `enforce_branch_protection()` trigger validates state transitions involving protected branches.

The trigger prevents a merged transition from being treated as a valid transition when the pull request is not currently open.

The trigger complements application-level policy evaluation.

Application code can provide detailed workflow logic, while database constraints and triggers protect data integrity when multiple clients access the database.

## Transaction Handling

The SQL script evaluates merge eligibility inside a transaction and locks the selected pull request during evaluation.

This provides a consistent database view while the eligibility decision is being recorded.

A production merge operation would normally combine eligibility verification, state transition, audit recording, and integration metadata in a transaction designed around the repository's concurrency model.

The important principle is that a merge decision should not be evaluated against one state and committed against an unrelated later state without concurrency controls.

## Failure Modes

The implementations deliberately model several failure conditions:

| Failure | Result |
|---|---|
| Unknown branch | Validation error |
| Duplicate commit | Rejected |
| Source equals target | Rejected |
| Closed PR review | Rejected |
| Draft PR merge | Rejected |
| Insufficient approvals | Merge blocked |
| Requested changes | Merge blocked |
| Missing status check | Merge blocked |
| Failed status check | Merge blocked |
| Stale target branch | Synchronization required |
| Unresolved conversation | Merge blocked |
| Direct push to protected branch | Rejected |
| Merged PR close attempt | Rejected |

These failures represent different governance layers and are not collapsed into one generic error.

## Security Considerations

Repository governance protects the integrity of the target branch.

Important controls include:

- direct-push restrictions
- force-push restrictions
- reviewer eligibility
- approval thresholds
- stale-review handling
- required automated checks
- conversation resolution
- administrator bypass policy
- audit records
- immutable commit identity relationships

Approval should not be treated as authentication. A review decision is meaningful only when the reviewer is authorized to participate in the repository's review policy.

A production implementation should also protect repository credentials, enforce authentication and authorization outside the workflow model, retain audit logs, and protect branch-policy configuration from unauthorized modification.

## Performance Considerations

The application implementations use direct maps and sets for frequent lookups.

For example:

`Map` and `dict` provide efficient branch and pull-request lookup.

`Set` provides efficient distinct-reviewer tracking.

Status checks are keyed by name rather than scanned repeatedly.

The PostgreSQL implementation uses indexes corresponding to common lookup patterns.

Merge evaluation still has to inspect relevant reviews and checks. In large repositories, these collections should be bounded by pull request identity and indexed appropriately.

The model avoids repeatedly scanning unrelated repositories or branches.

## Distinguishing the Four Governance Areas

The four concepts have different scopes.

| Area | Primary purpose | Scope |
|---|---|---|
| Pull Request | Propose and coordinate changes | Individual proposed change |
| Code Review | Evaluate proposed changes | Review activity |
| Approval | Record a review decision | Individual reviewer decision |
| Branch Protection | Enforce repository conditions | Target branch governance |

A pull request can exist without approval.

A review can contain comments without approval.

An approval can exist while merge eligibility remains false.

A protected branch can reject a fully reviewed pull request because a required automated check failed.

These are related mechanisms, but they are not interchangeable.

## Practical Workflow

A realistic workflow represented by the implementations is:

`Developer creates feature branch`

→ `Developer commits changes`

→ `Pull Request opened`

→ `Reviewers inspect proposed changes`

→ `Comments and conversations recorded`

→ `Requested changes resolved`

→ `Approvals recorded`

→ `Automated status checks complete`

→ `Target branch synchronized`

→ `Branch protection evaluated`

→ `Merge eligibility calculated`

→ `Changes merged`

The final merge is therefore a governed state transition rather than a consequence of approval alone.

## Educational Focus

The implementation demonstrates how repository governance can be modeled as a stateful technical system.

The most important distinction is between data representing a proposed change and data representing the current state of the repository.

A pull request captures a proposed integration. Reviews capture human evaluation. Approvals capture decisions. Status checks capture automated validation. Branch protection defines enforcement rules. Merge eligibility combines these inputs into a controlled decision.

The five implementations express the same governance domain through different engineering paradigms while retaining the same core distinctions and failure conditions.
