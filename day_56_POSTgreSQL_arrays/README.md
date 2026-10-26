# PostgreSQL Arrays: Array Operations and Practical Use Cases

## Scope

This project studies PostgreSQL arrays as first-class database values and connects them with equivalent collection-processing techniques in Python, JavaScript, C++17, and Java 17.

The implementations focus on practical operations such as:

- array creation and validation
- normalization
- concatenation
- duplicate removal
- containment
- overlap detection
- difference and intersection
- positional access
- slicing
- unnesting
- aggregation
- filtering
- workflow evaluation
- transactional updates
- database-level validation

The examples use repository and pull-request metadata as a realistic setting because labels, required checks, changed files, reviewer roles, and similar compact collections can naturally be represented as arrays when the elements do not require independent relational identity.

## Core Concept

A PostgreSQL array stores multiple values of one PostgreSQL data type inside a single column.

Examples include:

- `text[]` for labels
- `integer[]` for quantities or identifiers
- `bigint[]` for referenced record identifiers
- multidimensional numeric arrays for matrix-like data

An array is ordered. PostgreSQL array positions are normally addressed using one-based indexes.

For example, an array such as `ARRAY['database', 'security', 'backend']` has three elements and positions 1, 2, and 3.

Arrays are not simply strings containing delimiters. PostgreSQL understands their element boundaries, dimensions, operators, functions, and data types.

## When Arrays Fit

Arrays are useful when a collection:

- belongs directly to one parent row
- is relatively compact
- contains values of one logical type
- is commonly read with the parent
- does not require independent relational identity
- does not require extensive metadata for every element

Typical examples include:

| Use case | Suitable array |
|---|---|
| Repository labels | `text[]` |
| Required CI checks | `text[]` |
| Reviewer roles | `text[]` |
| Changed file paths | `text[]` |
| Small sets of feature flags | `text[]` |
| Numeric measurements | `numeric[]` |
| Ordered identifiers | `bigint[]` |

Arrays become less suitable when individual elements need their own foreign keys, ownership, timestamps, permissions, lifecycle, or frequent independent updates.

## Relationship Between Arrays and Relational Design

The PostgreSQL model deliberately distinguishes compact collections from independently identifiable entities.

The repository workflow follows this structure:

`Repository`
→ `Branch`
→ `Commit`
→ `Pull Request`
→ `Review`
→ `Review Comment`
→ `Status Check`
→ `Branch Protection Policy`

Arrays are used inside those entities for compact collections such as:

- repository labels
- branch required checks
- commit changed files
- pull-request labels
- pull-request commit identifiers
- reviewer roles
- required status checks

Reviews, comments, commits, branches, and status checks remain separate tables because they have their own identity, relationships, state, and constraints.

This distinction prevents an array from becoming a substitute for relational modeling where relational structure is actually required.

## PostgreSQL Operations Implemented

### Creation

PostgreSQL supports array literals and constructors.

The SQL implementation uses expressions such as:

`ARRAY['database', 'security', 'postgresql']`

Typed arrays are used where PostgreSQL needs explicit type information, such as:

`ARRAY['security', 'database']::text[]`

### Normalization

The `normalize_text_array` function:

1. expands the input with `unnest`
2. trims whitespace
3. removes empty elements
4. converts values to lowercase
5. removes duplicates
6. reconstructs the array in sorted order

This creates a deterministic representation suitable for labels and similar metadata.

A trigger applies this normalization automatically to pull-request labels before insertion or update.

### Concatenation

The `||` operator combines arrays.

For example, an existing label array can be extended with another array without manually reconstructing each element.

### Appending

`array_append` adds one element to the end of an array.

The transaction example uses it to add a release label while first checking that the pull request remains open.

### Removing

`array_remove` returns an array without matching elements.

The operation does not modify the stored row unless its result is explicitly assigned during an `UPDATE`.

### Containment

The `@>` operator tests whether the left array contains every element of the right array.

The example uses it to identify pull requests containing both `security` and `database`.

This is different from equality. Array containment asks whether required elements exist, while equality compares array values as arrays.

### Overlap

The `&&` operator tests whether two arrays share at least one element.

This is useful for questions such as whether a pull request has any label from a restricted or monitored set.

### Membership

`ANY` provides element-level membership testing.

The SQL script uses:

`'release-reviewed' = ANY(labels)`

to avoid appending a duplicate label.

### Position

`array_position` returns the position of the first matching element.

The example exposes the position of the `security` label.

### Cardinality

`cardinality` reports the number of elements in an array.

This is useful for validation and reporting.

It is distinct from `array_length`, which is dimension-oriented and can behave differently for empty arrays or multidimensional structures.

### Slicing

PostgreSQL supports array subscripting and slicing.

The example demonstrates positional access with:

`labels[1]`

and uses array operations elsewhere to construct derived collections.

### Unnesting

`unnest` converts array elements into rows.

`WITH ORDINALITY` also provides the element position.

This is important when array data must participate in relational reporting, aggregation, filtering, or joins.

The SQL implementation uses:

`CROSS JOIN LATERAL unnest(pr.labels) WITH ORDINALITY`

to produce one row per label while preserving its position.

### Aggregation

`array_agg` performs the reverse conceptual operation.

Multiple relational rows can be collected into an array:

`array_agg(branch_name ORDER BY branch_name)`

Ordering inside `array_agg` makes the resulting array deterministic.

## Python Implementation

The Python program models PostgreSQL-style array behavior using lists and sets.

`Product` is a dataclass representing a domain object with:

- identifiers
- tags
- quantities
- priorities

Validation occurs during object construction.

The implementation includes:

- normalization
- unique append
- prepend
- concatenation
- difference
- intersection
- all-element containment
- any-element containment
- one-based positional reporting
- one-based slicing
- array zipping
- matrix flattening
- inventory reporting

Sets are used for membership-heavy operations. This avoids repeatedly scanning the entire collection when a lookup structure provides a clear performance benefit.

The Python implementation also validates mismatched array lengths and invalid quantities.

The relationship between `quantities` and `priorities` demonstrates an important practical concern: parallel arrays introduce a positional dependency. If two arrays describe corresponding values, their lengths and indexes must remain synchronized.

## JavaScript Implementation

The JavaScript implementation uses a different engineering style.

`InventoryItem` provides domain validation, while `EventBus` models event-driven state changes.

JavaScript-specific features include:

- `Set` for membership
- `Map` for event listeners
- `Promise.all` for independent asynchronous report generation
- array methods such as `filter`, `map`, `reduce`, and `flat`
- immutable-style copies using spread syntax

The `processInventory` function processes multiple inventory objects concurrently.

The event system emits an `array.updated` event after an updated tag array is produced.

This demonstrates an important distinction between an in-memory JavaScript array and a PostgreSQL array. JavaScript arrays are application-memory structures, while PostgreSQL arrays are typed database values subject to database constraints, indexes, transactions, and SQL operators.

## C++17 Implementation

The C++ program models an array-based repository governance case.

`PullRequestRecord` contains:

- labels
- changed files
- status checks
- identifying metadata

`ArrayEngine` provides reusable collection operations.

The implementation uses:

- `std::vector`
- `std::unordered_set`
- `std::all_of`
- exception handling
- structured bindings
- explicit validation

The `MergeEligibilityEngine` combines array-derived label decisions with status-check evaluation.

A pull request is considered eligible only when:

- its identity is valid
- required checks pass
- required governance labels exist

The program then changes one status check to `FAIL` and reevaluates the same workflow.

This makes the array operations part of a stateful decision process instead of isolated collection examples.

## Java 17 Implementation

The Java implementation represents an enterprise-style repository governance workflow.

The domain contains:

- `ReviewState`
- `CheckState`
- `StatusCheck`
- `Review`
- `PullRequest`
- `ArrayOperations`
- `MergeEligibilityService`

Java records provide immutable domain representations for reviews, checks, and pull requests.

`List.copyOf` prevents external callers from modifying validated collections through shared mutable references.

The `MergeEligibilityService` separates policy evaluation from collection manipulation.

A pull request requires:

- passed checks
- an approval
- no blocking change-requested review
- required governance labels

The example then creates a second state containing a requested change and demonstrates the resulting eligibility decision.

This separation is important in enterprise systems: array manipulation should not itself determine the complete business policy. Collection operations provide data, while domain services interpret that data.

## PostgreSQL Relational Model

The SQL implementation creates the `postgres_arrays` schema.

The principal tables are:

| Table | Purpose |
|---|---|
| `repository` | Repository identity and allowed labels |
| `branch` | Branch state and required checks |
| `commit_record` | Commit metadata and changed files |
| `pull_request` | Proposed changes and compact metadata |
| `reviewer` | Reviewer identity and roles |
| `review` | Review decisions |
| `review_comment` | Review discussions and resolution state |
| `status_check` | Automated check results |
| `branch_protection_policy` | Merge enforcement rules |

Arrays are used where collections belong naturally to their parent.

Relational tables are used where entities need independent identity.

## Constraints and Validation

The database uses:

- primary keys
- foreign keys
- unique constraints
- check constraints
- enumerated types
- triggers
- transaction control

Examples include:

- non-empty repository names
- valid branch names
- distinct source and target branches
- non-negative review counts
- non-empty comment bodies
- valid comment line numbers
- repository-consistent commit identifiers

The `validate_commit_ids` trigger prevents a pull request from referencing commit identifiers belonging to another repository.

This is important because PostgreSQL cannot express every cross-row array relationship with a simple foreign-key declaration. A `bigint[]` containing identifiers does not automatically behave like a conventional foreign-key column for every array element. Explicit validation is therefore necessary when arrays contain references to relational entities.

## Array Indexing

Three GIN indexes are included for array-oriented search:

- pull-request labels
- branch required checks
- commit changed files

The label index supports containment and overlap-style queries efficiently on suitable workloads.

A normal B-tree index is not generally the right structure for arbitrary membership searches inside a `text[]` column.

Indexes should still be justified by actual query patterns and data volume. An index introduces storage and write-maintenance costs.

## Transactional Update

The SQL script demonstrates a transaction that:

1. locks an open pull request
2. verifies its current state
3. appends a label if it is absent
4. commits the change

The row lock protects the state observed by the workflow from being invalidated by a competing update between validation and modification.

Transactions are particularly important when an array update is part of a larger business operation.

## Merge Eligibility Query

The final eligibility query combines:

- branch protection policy
- approval counts
- active reviewers
- stale-review state
- dismissed reviews
- status-check results
- unresolved comments
- draft state
- closed state

The query uses common table expressions to separate these calculations before producing the final `merge_eligible` value.

The array columns participate in the governance model, but they are not treated as the entire workflow.

## Edge Cases

The implementations explicitly consider:

- empty arrays
- duplicate elements
- blank strings
- invalid positions
- mismatched parallel arrays
- missing required elements
- failed status checks
- inactive reviewers
- stale approvals
- dismissed reviews
- unresolved review comments
- invalid commit identifiers
- closed pull requests
- draft pull requests

Empty arrays are represented as typed empty arrays such as `'{}'::text[]` when PostgreSQL needs an unambiguous type.

## Performance Considerations

For an array containing `n` elements:

- direct traversal is generally `O(n)`
- copying an array is generally `O(n)`
- unnesting is `O(n)` in the number of produced elements
- set-based membership operations can reduce repeated application-side searches
- GIN indexes can improve suitable containment and overlap queries

The PostgreSQL planner should determine whether an index is beneficial based on table size, statistics, selectivity, and query structure.

Arrays can become inefficient when they are repeatedly expanded, independently updated, or joined against many other entities.

## Security Considerations

Array values should not be treated as trusted simply because they are structurally valid.

The SQL model enforces important rules at the database layer.

Examples include:

- validating referenced commit identifiers
- restricting empty textual values
- preventing invalid review counts
- checking review and comment state
- controlling branch protection behavior
- avoiding duplicate labels during transactional updates

The schema also separates identity-bearing records from compact arrays. This reduces the risk of hiding authorization-sensitive relationships inside unstructured collections.

Application-level validation remains useful, but database constraints provide the authoritative protection for persisted data.

## Array Versus Normalized Table

| Requirement | Array | Separate table |
|---|---|---|
| Small row-owned collection | Strong fit | Often unnecessary |
| Simple membership filtering | Strong fit | Strong fit |
| Ordered values | Strong fit | Requires explicit ordering |
| Independent element identity | Weak fit | Strong fit |
| Foreign-key relationships per element | Limited | Strong fit |
| Element-level metadata | Limited | Strong fit |
| Frequent individual updates | Less suitable | Strong fit |
| Large collections | Can become unwieldy | Usually preferable |
| Complex joins involving elements | Often requires `unnest` | Natural relational operation |

The correct choice depends on the data's lifecycle and query requirements, not simply on whether multiple values exist.

## Practical Workflow

A realistic array-backed workflow can be represented as:

`Input collection`
→ `Validate`
→ `Normalize`
→ `Persist`
→ `Query with array operators`
→ `Unnest when relational processing is needed`
→ `Evaluate business rules`
→ `Transactionally update`
→ `Report`

For repository metadata, the workflow becomes:

`Repository`
→ `Branches`
→ `Pull Request`
→ `Array metadata`
→ `Reviews`
→ `Status Checks`
→ `Protection Policy`
→ `Merge Eligibility`

The arrays support the workflow, while relational entities preserve identity, state, and integrity.

## Important Distinction

A PostgreSQL array is a typed database value, not a replacement for relational modeling.

The strongest use cases in this project are compact collections such as labels, roles, changed-file paths, and required checks.

The weakest use cases are collections whose individual elements need independent lifecycle management, foreign keys, permissions, audit history, or complex attributes.

The five implementations therefore use arrays deliberately rather than treating every collection as an array.
