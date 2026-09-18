# Join strategy: join keys, cardinality, duplicate rows, and NULL behavior

## Topic introduction

A relational join combines rows from two relations according to a matching condition. Joins are fundamental to SQL, relational databases, data engineering, analytics, reporting, ETL pipelines, data warehouses, and application backends.

A join is not simply a mechanism for "putting two tables together." The correctness of a join depends on several related questions:

- What is the join key?
- What does one row represent in each relation?
- Is the key unique?
- What is the relationship between the two relations?
- Can duplicate keys exist?
- What happens when a key is NULL?
- Which rows should survive when there is no match?
- How many output rows should be expected?
- Which physical join strategy is appropriate?
- How much memory and computation will the join require?

The central principle is that **join logic and data cardinality are inseparable**. A syntactically valid join can still produce analytically incorrect results if its key or grain is misunderstood.

The three implementations in this study use the same conceptual subject from different perspectives:

- Python builds a teaching-oriented relational join engine.
- JavaScript demonstrates equivalent join behavior using `Map`, `Set`, arrays, validation, and executable assertions.
- C++ develops an industry-style customer-order analytics and reconciliation case study with explicit data structures, nullable values, composite keys, validation, diagnostics, and hash-based execution.

---

## Fundamental concepts

### Relation

In relational terminology, a relation can be viewed practically as a table containing rows and columns.

For example, a customer relation might contain:

| customer_id | name | segment |
|---:|---|---|
| 1 | Asha | retail |
| 2 | Ravi | business |
| 3 | Meera | retail |

An order relation might contain:

| order_id | customer_id | amount |
|---|---:|---:|
| O1 | 1 | 100 |
| O2 | 1 | 200 |
| O3 | 2 | 500 |

The `customer_id` column connects the two relations.

### Join key

A join key is the attribute or set of attributes used to determine whether rows correspond.

A simple join can use:

`customers.customer_id = orders.customer_id`

A composite join can use:

`country = country AND customer_id = customer_id`

A good join key should represent the same logical entity on both sides.

A key can be:

- a primary key
- a foreign key
- a natural key
- a surrogate key
- a composite key
- a derived business key

The technical existence of a column does not guarantee that it is a correct join key.

### Grain

The grain describes what one row represents.

Examples:

- one row per customer
- one row per order
- one row per product
- one row per transaction
- one row per customer per month
- one row per account per day

Suppose `customers` contains one row per customer and `orders` contains one row per order. Joining them on `customer_id` produces order-level output because each customer can match multiple orders.

Understanding grain is one of the most important safeguards against incorrect analytical joins.

---

## Core join types

### INNER JOIN

An inner join returns only rows for which the join predicate evaluates to TRUE.

Conceptually:

`A INNER JOIN B ON A.key = B.key`

If customer 1 has three orders, the customer can appear three times in the result.

An inner join does not preserve unmatched rows.

### LEFT OUTER JOIN

A left join preserves every row from the left relation.

If a customer has no order, the customer remains in the result and the right-side attributes are NULL.

The Python implementation provides `left_outer_hash_join`.

The C++ implementation represents an unmatched order using `std::optional<Order>`.

### RIGHT OUTER JOIN

A right join preserves every row from the right relation.

The Python implementation includes a right outer join implementation by reversing the left-join perspective.

Right joins are often expressible by reversing the table order and using a left join.

### FULL OUTER JOIN

A full outer join preserves:

- matching rows
- unmatched left rows
- unmatched right rows

Unmatched attributes from the opposite relation become NULL.

The Python implementation provides `full_outer_join`.

### CROSS JOIN

A cross join creates the Cartesian product.

If relation A contains `N` rows and relation B contains `M` rows:

`output rows = N × M`

For example:

- 2 colors
- 3 sizes

produce:

`2 × 3 = 6`

combinations.

A cross join can be intentional, such as generating a product-and-size matrix. An accidental Cartesian product can create extremely large outputs.

---

## Join keys and key quality

A join key should be evaluated from both a technical and business perspective.

### Technical compatibility

The key values should use compatible representations.

Potential problems include:

- integer versus string representations
- leading zeros
- inconsistent case
- whitespace
- different date formats
- different country-code conventions
- inconsistent identifiers
- truncated identifiers
- different units

For example, `"00123"` and `123` may refer to the same business identifier but are not identical values in every data system.

### Semantic compatibility

Two columns having the same name does not mean they represent the same thing.

For example:

`customer_id`

could mean a global customer identifier in one system and a branch-local identifier in another.

A correct join requires semantic compatibility, not merely syntactic similarity.

### Primary key and foreign key relationship

A common relational structure is:

- customer primary key: `customer_id`
- order foreign key: `customer_id`

If the customer table truly contains one row per customer, the relationship is usually:

`customer 1 : N orders`

The customer key is unique on the customer side, while the foreign key can repeat on the order side.

---

## Cardinality

Cardinality describes how rows on one side can relate to rows on the other side.

The major patterns are:

| Cardinality | Meaning |
|---|---|
| 1:1 | One row matches at most one row |
| 1:N | One row can match many rows |
| N:1 | Many rows can match one row |
| N:N | Many rows can match many rows |

### 1:1

Suppose both relations have a unique `customer_id`.

One matching key contributes at most one output row.

This relationship is often useful for enrichment, provided uniqueness has actually been validated.

### 1:N

A customer table and order table commonly form a 1:N relationship.

Example:

One customer:

`customer_id = 7`

Orders:

`O1, O2, O3`

The join produces three rows for customer 7.

This is not a duplicate-row error. It is the expected result of the relationship.

### N:1

If the left side contains many transaction rows and the right side contains one account row, the relationship is N:1 from left to right.

This is logically the reverse perspective of 1:N.

### N:N

Many-to-many relationships are especially important because output size can increase rapidly.

If a join key appears:

- 3 times on the left
- 4 times on the right

then the matching key contributes:

`3 × 4 = 12`

rows.

This multiplication is mathematically correct according to relational join semantics.

It can still be wrong for a business calculation if the intended grain was one row per account.

---

## Duplicate rows

Duplicate join keys are not automatically bad data.

A repeated foreign key is often expected.

For example:

| order_id | customer_id |
|---|---:|
| O1 | 10 |
| O2 | 10 |
| O3 | 10 |

The repeated value `10` is normal if `customer_id` identifies the customer who placed each order.

The important question is whether the duplicate is expected at the selected grain.

### Duplicate multiplication

For a given key `k`:

`output(k) = left_count(k) × right_count(k)`

The Python function `expected_join_output_upper_bound` calculates this exact contribution for an equality inner join.

The JavaScript function `expectedJoinOutputSize` provides the equivalent diagnostic.

The C++ function `expected_join_size` performs the same calculation and includes overflow checks.

### Why this matters for analytics

Consider two tables:

`account_events`

| account_id | event |
|---:|---|
| 7 | login |
| 7 | payment |
| 7 | logout |

`transactions`

| account_id | transaction |
|---:|---|
| 7 | T1 |
| 7 | T2 |

Joining them directly on `account_id` creates six rows.

If an analyst subsequently sums transaction amounts, the same transaction can appear multiple times because it is paired with every matching event.

The join itself is not necessarily wrong. The analytical grain is wrong for that aggregation.

---

## NULL behavior

NULL is one of the most important special cases in SQL joins.

NULL does not mean an ordinary value such as zero or an empty string.

It represents missing, unknown, or inapplicable information depending on the data model.

### Ordinary SQL equality

In SQL:

`NULL = NULL`

does not evaluate to TRUE.

It evaluates to UNKNOWN.

A join condition retains a pair only when the predicate evaluates to TRUE.

Therefore two rows with NULL join keys do not match under ordinary equality joins.

The Python implementation demonstrates this through `sql_equal`.

The JavaScript implementation separates `sqlEqual` from `nullSafeEqual`.

The C++ implementation uses `std::optional<int>` so that a missing integer can be represented explicitly.

### Why Python and JavaScript need special treatment

Python evaluates:

`None == None`

as TRUE.

JavaScript evaluates:

`null === null`

as TRUE.

SQL ordinary equality has different semantics.

The implementations therefore deliberately avoid directly using language equality for ordinary SQL-style NULL joins.

### Null-safe matching

Some business rules explicitly require missing values to match missing values.

The Python function `null_safe_equal` and JavaScript function `nullSafeEqual` demonstrate this policy.

This should be an explicit decision rather than an accidental consequence of programming-language equality.

### Outer joins and NULL

In a left join, NULL can arise for two different reasons:

- the source row already contained NULL
- the row did not find a match and the database supplied NULL for the missing side

These cases can look identical in the result, so source-level semantics may need to be retained when distinguishing them matters.

---

## Composite join keys

A composite key consists of multiple attributes.

Example:

`country + customer_id`

A shipment might use:

| country | customer_id | shipment |
|---|---:|---|
| IN | 10 | S1 |
| US | 10 | S2 |

If `customer_id` is only unique within a country, joining on `customer_id` alone is insufficient.

The correct condition is conceptually:

`shipments.country = customers.country`

and

`shipments.customer_id = customers.customer_id`

The Python implementation uses tuples for composite keys.

The JavaScript implementation serializes the component values into a deterministic key representation.

The C++ implementation defines `CompositeKey` and a corresponding `CompositeKeyHash`.

### Composite NULL behavior

Under ordinary equality semantics, a NULL component does not match.

If a composite key has three components and one component is NULL, the complete equality predicate does not evaluate to TRUE under ordinary SQL equality.

---

## Semi joins

A semi join asks:

"Does at least one matching row exist?"

It returns rows from one relation without adding columns from the other relation.

Example:

Customers:

`1, 2, 3`

Orders:

`1, 1, 3`

A semi join returns customers:

`1, 3`

Customer 1 appears once even though it has two orders.

This makes a semi join useful for existence checks.

The Python function is `semi_join`.

The JavaScript function is `semiJoin`.

The C++ function is `semi_join`.

---

## Anti joins

An anti join asks:

"Does no matching row exist?"

Using the same data:

Customers:

`1, 2, 3`

Orders:

`1, 1, 3`

The anti join returns:

`2`

Anti joins are useful for finding:

- customers without orders
- products without sales
- records missing from a reference table
- failed reconciliations
- unmatched entities
- data-quality exceptions

---

## Join strategies

The logical join describes the result that is required. A database engine can choose different physical strategies to produce that result.

### Nested-loop join

The basic algorithm is:

1. Take one row from the outer relation.
2. Scan the inner relation.
3. Test the join predicate.
4. Emit matching pairs.
5. Repeat.

For `N` left rows and `M` right rows:

`O(N × M)`

This can be perfectly reasonable for small inputs.

The Python implementation is `nested_loop_inner_join`.

The JavaScript implementation is `nestedLoopInnerJoin`.

The C++ implementation is `nested_loop_join`.

### Hash join

A hash join generally:

1. Builds a hash structure for one relation.
2. Uses the join key as the hash key.
3. Scans the other relation.
4. Performs hash lookups.
5. Emits every matching pair.

Expected complexity is approximately:

`O(N + M)`

The implementation requires additional memory.

The critical implementation detail is duplicate preservation.

An incorrect hash join might store:

`key -> one row`

A correct implementation for general relational joins needs:

`key -> collection of matching rows`

Otherwise duplicate matches disappear.

### Sort-merge join

A sort-merge join uses ordered inputs.

Conceptually:

1. Sort both relations by join key if required.
2. Scan both ordered sequences.
3. Advance the appropriate side.
4. Emit all matching combinations.

Once sorted, the merge phase is approximately linear.

Sort-merge joins can be attractive when:

- data is already sorted
- sorted output is useful
- large sequential processing is preferable
- hash memory requirements are undesirable

### Indexed nested-loop join

An index can turn an inner scan into an indexed lookup.

Conceptually:

`for each outer row -> lookup matching inner rows`

This can be highly effective when the outer side is small or the lookup is selective and the index is appropriate.

---

## Choosing a join strategy

A simplified decision process considers:

| Factor | Possible impact |
|---|---|
| Input size | Large inputs make inefficient scans expensive |
| Key distribution | Heavy duplication can enlarge the output |
| Existing indexes | May make indexed lookups efficient |
| Sorted data | Can favor merge-based execution |
| Available memory | Can constrain hash joins |
| Selectivity | Highly selective predicates can reduce work |
| Data skew | One extremely frequent key can create large match groups |
| Output size | Sometimes dominates the cost regardless of strategy |

A real database optimizer also considers statistics, available indexes, cardinality estimates, predicate selectivity, physical storage, join order, memory limits, parallelism, and cost models.

The strategy should therefore be viewed as an execution decision rather than a property of the SQL syntax itself.

---

## Python implementation

The Python script builds a compact relational engine from standard-library components.

### `sql_equal`

`sql_equal` explicitly models ordinary SQL equality by rejecting NULL operands.

This is necessary because Python's native `None == None` behavior differs from SQL.

### `nested_loop_inner_join`

This is the most direct implementation of an equality join.

It demonstrates the fundamental operation:

`compare every possible pair`

The implementation is easy to understand and has `O(N × M)` worst-case complexity.

### `hash_inner_join`

The hash implementation creates:

`join_key -> list of rows`

The list is essential because duplicate keys must be preserved.

### Outer joins

`left_outer_hash_join`, `right_outer_hash_join`, and `full_outer_join` demonstrate unmatched-row preservation.

### Composite keys

`composite_hash_join` uses tuples to represent multi-column keys.

### Semi and anti joins

`semi_join` and `anti_join` use key sets to perform existence and non-existence checks without multiplying output rows.

### Data validation

`validate_expected_one_to_one` detects duplicate keys when a one-to-one relationship is expected.

This illustrates an important engineering principle:

**Business assumptions about cardinality should be validated when they affect correctness.**

---

## JavaScript implementation

The JavaScript implementation focuses on application-level data processing.

### `Map`

JavaScript's `Map` is used as a hash-table-like structure for hash joins.

A duplicate-preserving structure is used:

`Map<key, array of matching rows>`

rather than:

`Map<key, single row>`

This prevents duplicate right-side rows from being silently discarded.

### `Set`

`Set` is useful for semi and anti joins because existence can be tested without constructing full joined rows.

### Null semantics

The JavaScript implementation separates:

- `sqlEqual`
- `nullSafeEqual`

This makes the distinction between JavaScript language semantics and SQL semantics explicit.

### Composite keys

`compositeHashJoin` constructs a representation containing all key components.

The important concept is independent of the specific representation:

A composite join key must include every attribute required to identify the relationship.

### Assertions

`demonstrateAssertions` verifies important behavioral properties:

- a 1:1 join produces the expected number of rows
- NULL does not match NULL under ordinary SQL-style equality
- a semi join does not multiply the left relation

Executable assertions turn conceptual rules into testable behavior.

---

## C++ case study

The C++ program models a customer-order analytics system.

The central scenario contains:

- customers
- orders
- shipments
- nullable customer identifiers
- customer segments
- order amounts

The case study progresses from a direct nested-loop join to a hash join and then to more specialized operations.

### Customer-order relationship

The customer relation is intended to contain one row per customer.

The order relation contains multiple orders for a customer.

This establishes a 1:N relationship:

`Customer 1 -> many Orders`

The resulting join has one row per order.

### Nested-loop implementation

`nested_loop_join` directly compares every customer with every order.

Its complexity is:

`O(N × M)`

It is included because it clearly exposes the logical mechanics of joining.

### Hash implementation

`hash_join` indexes orders by `customer_id`.

The index stores vectors of pointers:

`customer_id -> vector<Order*>`

The vector is important because several orders can share the same customer.

### Memory trade-off

The hash join uses additional memory to build the index.

This creates a standard trade-off:

- more memory
- fewer repeated scans
- better expected lookup performance

The appropriate strategy depends on the workload.

---

## C++ nullable values

The C++ implementation uses:

`std::optional<int>`

for nullable customer identifiers.

This is preferable to inventing a special integer such as `-1` to represent NULL.

A sentinel value can create ambiguity if that value is actually valid.

`std::optional` explicitly separates:

- a present integer
- an absent value

The program then implements SQL-like equality through `sql_equal`.

---

## C++ composite keys

`CompositeKey` contains:

- `country`
- `customer_id`

`CompositeKeyHash` allows the structure to be used as a key in an `unordered_map`.

The example demonstrates why composite keys are necessary when an identifier is only unique within a larger namespace.

---

## C++ semi and anti joins

The C++ case study uses `unordered_set<int>` for existence checks.

A semi join inserts order customer identifiers into a set and then scans customers.

An anti join performs the same lookup and selects customers whose keys are absent.

This avoids unnecessary row multiplication.

---

## Cardinality diagnostics

The C++ program includes `expected_join_size`.

For each matching key:

`left_count × right_count`

is added to the expected output.

This is useful before expensive analytical operations because an unexpected result size can indicate:

- incorrect join key
- unintended many-to-many relationship
- duplicate reference data
- incorrect grain
- missing predicate
- data-quality issue

The implementation also checks for `size_t` overflow when calculating expected size.

---

## Edge cases

Important join edge cases include:

### Empty left relation

An inner join produces no rows.

A left join also produces no rows because there are no left rows to preserve.

### Empty right relation

An inner join produces no rows.

A left join produces one output row for every left row, with NULL values for right-side attributes.

### NULL on both sides

Ordinary equality does not match them.

### Duplicate keys on both sides

Matching duplicate groups multiply:

`left duplicates × right duplicates`

### Missing foreign key

An inner join drops the unmatched row.

A left join preserves it.

### Unmatched right rows

A full outer join preserves them.

### Accidental cross join

No join predicate can produce `N × M` rows.

### Composite key with missing component

Under ordinary equality semantics, a NULL component prevents the match.

---

## Common mistakes

### Joining on a non-unique field

A field such as `name` may not uniquely identify a person or organization.

Names can repeat.

### Joining on only part of a composite key

If uniqueness requires:

`country + customer_id`

joining only on `customer_id` can create false matches.

### Assuming a foreign key is unique

Foreign keys commonly repeat.

Repeated foreign keys are normal in 1:N relationships.

### Using `DISTINCT` to hide a bad join

`DISTINCT` may remove visible duplicates without fixing the underlying relationship.

If a join creates six rows where the intended grain requires one row, removing duplicates can also remove legitimate distinctions.

### Aggregating after an unintended many-to-many join

This can inflate:

- revenue
- counts
- balances
- quantities
- risk measures
- operational KPIs

### Ignoring NULL

Treating NULL as an ordinary value can lead to incorrect matches or missing rows.

### Using the wrong outer join

An inner join can silently remove unmatched records when the business requirement is to retain them.

### Accidentally creating a Cartesian product

Missing or incorrect join predicates can produce extremely large outputs.

### Replacing duplicate hash values

A hash index that stores only one row per key is incorrect for general joins when duplicate keys are possible.

---

## Important distinctions

### Join key versus primary key

A join key is any value or set of values used for matching.

A primary key is a schema-level constraint intended to uniquely identify rows.

A join can use a primary key, but it does not have to.

### Duplicate key versus duplicate row

Two rows can have the same join key but contain different attributes.

They are not necessarily identical rows.

For example:

| customer_id | order_id |
|---:|---|
| 10 | O1 |
| 10 | O2 |

The customer key is duplicated, but the rows represent different orders.

### Logical join versus physical join strategy

The logical operation might be an inner equality join.

The database engine can physically execute it using:

- nested loop
- hash join
- sort-merge join
- indexed lookup

SQL describes the desired result, while the optimizer chooses an execution strategy.

### NULL versus empty string

NULL represents missing or unknown information.

An empty string is a value.

They should not be treated as interchangeable without an explicit business rule.

### Semi join versus inner join

An inner join can multiply rows.

A semi join only tests whether a match exists and returns the left row once.

---

## Performance considerations

### Nested loops

Worst-case complexity:

`O(N × M)`

Memory overhead is low, but repeated scans can become expensive.

### Hash joins

Expected complexity:

`O(N + M)`

Memory:

`O(build-side rows)`

Hash joins can perform very well for equality joins but can consume substantial memory.

### Sort-merge joins

If sorting is required, sorting adds computational cost.

If inputs are already sorted, the merge phase can be highly efficient.

### Output dominates cost

Even an efficient hash join cannot avoid producing required output rows.

If a many-to-many relationship legitimately generates millions of matching combinations, those rows must still be processed.

### Data skew

A highly duplicated key can create a very large match group.

For example:

- one left key appears 1,000 times
- the same right key appears 10,000 times

That key alone generates:

`1,000 × 10,000 = 10,000,000`

rows.

This is a data-distribution issue, not merely an algorithm-selection issue.

### Memory pressure

Hash joins require memory for their build structure.

Large joins may require:

- batching
- partitioning
- spilling to disk
- distributed execution
- careful build-side selection

The exact implementation depends on the database engine.

---

## Security considerations

Join operations can contribute indirectly to security problems when data is not validated.

Important considerations include:

- preventing unauthorized data combinations
- respecting row-level security
- avoiding cross-tenant joins
- validating tenant identifiers
- preventing accidental exposure through outer joins
- controlling access to sensitive attributes
- avoiding dynamic SQL construction from untrusted input
- auditing sensitive-data enrichment operations

For multi-tenant systems, a join that matches only on `customer_id` may be unsafe if customer identifiers are only unique within a tenant.

A safer logical relationship may require:

`tenant_id + customer_id`

as the composite key.

This is both a data-integrity issue and an access-control issue.

---

## Implementation considerations

A robust join workflow should establish:

1. The grain of each input.
2. The intended join relationship.
3. The join key.
4. Key uniqueness expectations.
5. NULL behavior.
6. Expected output cardinality.
7. Required join type.
8. Suitable physical strategy.
9. Memory constraints.
10. Post-join validation.

For production analytical pipelines, row-count checks are often useful:

`input rows -> expected relationship -> output rows`

Unexpected changes should be investigated rather than automatically hidden.

---

## Testing considerations

Join implementations should test at least:

- empty inputs
- one matching row
- no matching rows
- duplicate keys
- duplicate keys on both sides
- NULL keys
- composite keys
- unmatched left rows
- unmatched right rows
- all rows unmatched
- all rows matched
- large key groups
- expected cardinality
- uniqueness violations

The supplied Python, JavaScript, and C++ implementations each include executable demonstrations of several of these conditions.

---

## Practical applications

Join strategies are used in:

- customer analytics
- financial reporting
- banking systems
- transaction reconciliation
- fraud analysis
- inventory management
- supply-chain systems
- healthcare data integration
- security analytics
- event processing
- recommendation systems
- feature engineering
- data warehouses
- ETL and ELT pipelines
- business intelligence
- operational reporting
- master-data management

A common production workflow is:

`transaction data -> reference data -> enrichment -> validation -> aggregation`

The correctness of the enrichment step depends heavily on join-key semantics and cardinality.

---

## Language comparison

| Concern | Python | JavaScript | C++ |
|---|---|---|---|
| Basic join modeling | Dictionaries and lists | Arrays and `Map` | Vectors and hash maps |
| Hash index | `dict` | `Map` | `unordered_map` |
| Existence checks | Sets/dictionaries | `Set` | `unordered_set` |
| Nullable values | `None` | `null` | `std::optional` |
| Composite keys | Tuples | Serialized key representation | Custom key + hash |
| Validation | Exceptions | Exceptions and assertions | Exceptions |
| Educational clarity | High | High for application logic | High for systems-level control |
| Memory control | Mostly managed automatically | Managed automatically | Explicit data structures and object lifetime |
| Performance control | Good high-level experimentation | Good application-level experimentation | Fine-grained systems-level control |

Python is particularly useful for rapidly testing relational concepts and data-quality rules.

JavaScript is useful when join-like operations are performed inside web applications, browser applications, Node.js services, or client-side data-processing workflows.

C++ exposes more details about data structures, hashing, memory representation, nullable types, overflow handling, and algorithmic implementation.

---

## Production relevance

A production-grade database engine performs substantially more work than the compact examples in this repository.

A real query optimizer can consider:

- table statistics
- histograms
- estimated cardinality
- predicate selectivity
- index availability
- join ordering
- partitioning
- memory limits
- parallel execution
- data locality
- storage layout
- cache behavior
- skew
- intermediate result sizes

The educational implementations intentionally expose the core mechanisms rather than reproducing a complete database engine.

The most important production lesson is that **correctness starts with the relationship between the data models, not with the choice of join syntax**.

---

## Key rules

1. A join key must represent the same logical entity on both sides.
2. Always understand the grain of each relation before joining.
3. A repeated key is not automatically an error.
4. A 1:N join naturally produces multiple output rows.
5. An N:N join can multiply matching rows dramatically.
6. Ordinary SQL equality does not match NULL with NULL.
7. Composite keys require all relevant key components.
8. Semi joins test existence without multiplying the left relation.
9. Anti joins identify rows with no corresponding match.
10. Hash joins trade memory for faster expected equality lookups.
11. Cross joins produce Cartesian products.
12. Validate uniqueness when business logic assumes a 1:1 relationship.
13. Estimate join cardinality before expensive downstream processing.
14. Do not use duplicate removal as a substitute for understanding join logic.
15. A logically correct join can still be inappropriate for a particular analytical grain.
