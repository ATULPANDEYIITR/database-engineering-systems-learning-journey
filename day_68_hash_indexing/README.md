# Hash Indexing: Hash Tables and Hash-Based Access

## 1. Technical Scope

Hash indexing is an indexing technique that uses a hash function to map a search key to a location in an index structure.

Instead of examining every record, a hash-based access mechanism calculates a bucket location and searches the corresponding bucket.

This approach is particularly useful for equality-based retrieval.

The implementations cover two related but distinct areas:

- In-memory hash tables used by application programs.
- Hash indexes used by PostgreSQL to accelerate database access.

The practical scenario is an enterprise customer and financial transaction directory. Customer identifiers, account numbers, and transaction references provide suitable keys for demonstrating hash-based retrieval.

## 2. Core Concepts

### 2.1 Hash Function

A hash function converts a key into a numerical hash value.

A bucket index is calculated using:

`bucket_index = hash(key) % capacity`

For example, if the hash value is 137 and the table has 16 buckets:

`137 % 16 = 9`

The corresponding key is directed to bucket 9.

A suitable hash function should distribute keys reasonably evenly across the available buckets.

Important properties include:

- Deterministic output for the same key within the relevant hashing context.
- Efficient computation.
- Reasonable distribution across buckets.
- Compatibility with the equality rules of the key type.

An important distinction exists between ordinary hash functions and cryptographic hash functions.

Ordinary hash functions are designed primarily for data structures. Cryptographic functions such as SHA-256 are designed for properties such as collision resistance and preimage resistance.

A cryptographic digest is not automatically a suitable replacement for a hash-table bucket function.

### 2.2 Hash Table

A hash table stores key-value pairs.

Its fundamental operations are:

| Operation | Purpose | Average complexity |
|---|---|---:|
| Insert | Add or update a key-value pair | O(1) |
| Search | Retrieve a value by key | O(1) |
| Delete | Remove an entry | O(1) |
| Resize | Reorganize the table | O(n) |

The average complexities assume a suitable hash distribution and controlled load factor.

The worst-case complexity of searching, inserting, or deleting can reach O(n) when many keys occupy the same bucket or probing sequence.

### 2.3 Buckets

A bucket is a logical storage location selected through the hash function.

A bucket can contain:

- One entry.
- Multiple entries.
- No entries.

Multiple keys can map to the same bucket. This condition is called a collision.

A collision is not necessarily a hash-function failure. It is an expected possibility when a finite number of buckets stores a potentially much larger number of keys.

## 3. Collision Resolution

### 3.1 Separate Chaining

Separate chaining stores multiple entries in the same bucket.

The Python, JavaScript, C++17, and Java 17 implementations provide separate-chaining indexes.

The structure is:

`Key -> Hash Function -> Bucket -> Linked Entries`

For example:

| Bucket | Entries |
|---|---|
| 0 | CUST-1001, CUST-1005 |
| 1 | CUST-1002 |
| 2 | Empty |
| 3 | CUST-1003, CUST-1004 |

The bucket index identifies the location. The actual key comparison identifies the requested entry.

Advantages:

- Straightforward collision handling.
- Deletion does not require moving other entries.
- The table can accommodate multiple entries in one bucket.
- Performance is relatively stable under reasonable hash distribution.

Limitations:

- Additional memory is required for bucket structures.
- Pointer-based structures can have poor cache locality.
- Long chains increase lookup time.

### 3.2 Open Addressing

Open addressing stores entries directly inside the hash table's underlying array.

When the calculated position is occupied, the algorithm searches for another available position.

The C++17, JavaScript, and Java implementations demonstrate linear probing.

The probing formula is:

`position = (hash(key) + offset) % capacity`

The offset increases until an appropriate position is found.

For example:

| Position | State |
|---|---|
| 0 | EMP-101 |
| 1 | EMP-102 |
| 2 | EMP-103 |
| 3 | Empty |

If two keys initially map to position 0, subsequent positions are examined.

Advantages:

- No separate linked list is required.
- Array-based storage improves locality.
- Memory management is relatively straightforward.

Limitations:

- Clustering can increase the number of probes.
- Performance deteriorates at high load factors.
- Deletion requires special handling.

### 3.3 Tombstones

An open-addressing table cannot treat every deleted position as an unused position.

Consider this sequence:

1. Key A is inserted at position 2.
2. Key B collides and is inserted at position 3.
3. Key A is deleted.

If position 2 is immediately marked empty, a lookup for B may stop at position 2 and incorrectly report that B does not exist.

A tombstone represents a deleted position.

The three states are:

| State | Meaning |
|---|---|
| EMPTY | No entry has occupied this position in the current probing sequence |
| OCCUPIED | A valid entry exists |
| DELETED | An entry was removed, but probing must continue |

The implementations preserve this distinction and reuse deleted positions during insertion.

## 4. Load Factor and Resizing

The load factor measures the relationship between stored entries and available capacity.

`Load factor = Number of entries / Number of buckets`

For example:

- Capacity: 100
- Stored entries: 60
- Load factor: 0.60

A high load factor increases the probability of collisions and longer probing sequences.

The chaining implementations use a configurable maximum load factor and expand the table when the threshold is exceeded.

The open-addressing implementations use a more conservative threshold because occupied positions and tombstones affect the available probing space.

Resizing generally involves:

1. Allocating a larger table.
2. Recalculating bucket positions.
3. Reinserting existing entries.
4. Updating the table's internal state.

Existing bucket positions cannot simply be copied because the modulo operation changes when capacity changes.

Resizing costs O(n), but geometric expansion makes its amortized insertion cost efficient.

## 5. Hash Distribution and Collision Analysis

A hash function should distribute frequently occurring keys across buckets.

Poor distribution creates concentrated chains or probing clusters.

The implementations expose operational statistics such as:

- Capacity.
- Number of stored entries.
- Load factor.
- Occupied buckets.
- Maximum chain length.
- Collision count.
- Deleted-slot count.

These measurements help identify performance degradation.

The collision counter in the chaining examples measures insertion events where the target bucket already contains another entry. It is not necessarily the same as the number of distinct colliding key pairs.

For a table with n uniformly distributed keys and m buckets, the expected number of occupied buckets is:

`m × (1 - (1 - 1/m)^n)`

A high collision rate should trigger investigation into the hash function, key distribution, capacity, and input patterns.

## 6. Python Implementation

The Python file provides two generic hash-table implementations.

### 6.1 ChainedHashTable

The `ChainedHashTable` class uses:

- Lists of buckets.
- Entry dataclasses.
- Python's built-in `hash()` function.
- Dynamic resizing.
- Key validation.
- Exception-based missing-key handling.

Its `put()` method updates an existing key instead of inserting a duplicate.

The `get()` method retrieves the corresponding value and raises `KeyError` when the key is missing.

The `remove()` method deletes an entry from its bucket without affecting other entries.

### 6.2 OpenAddressHashTable

The open-addressing implementation uses:

- An array of slots.
- Explicit EMPTY and DELETED states.
- Linear probing.
- Tombstone reuse.
- Dynamic resizing.

This demonstrates why deletion in open addressing requires more careful state management than deletion in separate chaining.

### 6.3 Stable Hashing

The `stable_hash()` function uses SHA-256.

Python's built-in string hashing is intentionally randomized across interpreter processes. Consequently, its output should not be treated as a persistent identifier.

SHA-256 produces a deterministic digest for the same input.

The keyed hashing demonstration uses BLAKE2 with a randomly generated process-local key.

For security-sensitive systems, untrusted inputs should also have size limits and appropriate resource controls.

## 7. JavaScript Implementation

The JavaScript implementation emphasizes event-driven index management and native runtime capabilities.

### 7.1 HashIndex

The custom `HashIndex` class uses:

- Arrays of buckets.
- JavaScript objects for entries.
- FNV-1a as a demonstration hash function.
- Dynamic resizing.
- EventEmitter notifications.

The index emits events when:

- A new entry is inserted.
- An existing entry is updated.
- An entry is accessed.
- An entry is deleted.
- The table is resized.

This supports operational monitoring without embedding logging responsibilities into every business operation.

### 7.2 LinearProbingIndex

The second implementation demonstrates direct array storage and tombstones.

It uses JavaScript's object identity rules for key comparison and supports updating existing entries.

### 7.3 Native Map

JavaScript's `Map` provides a built-in key-value structure.

It supports:

- Key insertion.
- Key retrieval.
- Key existence checks.
- Key deletion.
- Entry iteration.

A native `Map` should normally be preferred over implementing a custom hash table in production application code unless specialized behavior is required.

### 7.4 Asynchronous Hashing

The example uses Node.js cryptographic facilities for SHA-256 and HMAC-SHA-256.

These are useful for integrity and authentication-related operations, but they serve different purposes from ordinary in-memory bucket selection.

The HMAC example uses a randomly generated secret key. The secret must be managed securely in an actual deployment.

## 8. C++17 Implementation

The C++17 file presents a transaction directory with generic hash-index classes.

### 8.1 ChainedHashIndex

The implementation uses:

- `std::vector` for bucket storage.
- `std::list` for separate chaining.
- `std::pair` for key-value entries.
- `std::hash` for key hashing.
- `std::optional` for missing-key representation.

The `rehash()` method allocates a new bucket structure and redistributes all entries.

### 8.2 LinearProbingIndex

The open-addressing implementation defines three explicit slot states.

This makes the deletion and probing rules visible in the domain structure.

The implementation also tracks deleted positions to decide when resizing is necessary.

### 8.3 TransactionDirectory

The transaction directory models an enterprise transaction lookup workflow.

Its transaction records contain:

- Transaction identifier.
- Account identifier.
- Amount.
- Transaction status.

Validation prevents:

- Empty identifiers.
- Negative transaction amounts.
- Non-finite numeric amounts.
- Unsupported transaction statuses.

The transaction identifier acts as the hash-index key.

### 8.4 Standard Library Hashing

The example also demonstrates `std::unordered_map`.

This is the standard C++ associative hash container.

It provides average constant-time access under suitable hash distribution.

Its `bucket_count()` and `load_factor()` functions expose useful operational information.

## 9. Java 17 Implementation

The Java implementation emphasizes enterprise domain modeling, validation, and concurrent access.

### 9.1 Domain Records

The following records represent immutable business data:

- `Customer`
- `Transaction`
- `IndexPolicy`
- `IndexStatistics`

Compact record constructors validate input at object creation.

This prevents invalid domain objects from entering the indexing workflow.

### 9.2 KeyValueIndex Interface

The interface defines the core operations:

- `put()`
- `find()`
- `delete()`
- `size()`
- `statistics()`

The separate-chaining implementation provides a concrete implementation of this contract.

This separates the indexing interface from the internal collision-resolution strategy.

### 9.3 Policy-Based Configuration

`IndexPolicy` defines:

- Maximum load factor.
- Initial capacity.
- Whether existing keys may be updated.

This allows the same indexing mechanism to operate under different business rules.

### 9.4 ConcurrentHashMap

The enterprise customer service uses `ConcurrentHashMap`.

It supports concurrent access by multiple threads.

The `putIfAbsent()` operation prevents duplicate customer identifiers during registration.

Thread-safe individual map operations do not automatically make multi-step business workflows atomic. Operations involving multiple records or external resources require appropriate transaction coordination.

## 10. PostgreSQL Hash Indexing

PostgreSQL supports multiple index access methods.

The SQL implementation demonstrates native PostgreSQL hash indexes.

### 10.1 Hash Index Creation

The general syntax is:

`CREATE INDEX index_name ON table_name USING HASH (column_name);`

The example creates hash indexes on:

- Transaction references.
- Account numbers.
- Customer codes.
- Transaction statuses.

These indexes are intended for equality-based lookup.

For example, searching for a transaction reference using equality can be supported by its hash index.

### 10.2 Hash Index Characteristics

PostgreSQL hash indexes:

- Support equality comparisons.
- Do not support range scans.
- Do not provide ordered retrieval.
- Are not unique indexes.
- Can be used by the query planner when appropriate.

Hash indexes are WAL-logged and crash-safe in modern PostgreSQL versions.

They use bucket and overflow-page structures internally.

Their performance depends on data distribution, table size, index maintenance, and query selectivity.

### 10.3 B-tree Comparison

The SQL script also creates B-tree indexes.

| Capability | Hash | B-tree |
|---|---|---|
| Equality lookup | Yes | Yes |
| Range lookup | No | Yes |
| Ordered retrieval | No | Yes |
| Sorting support | No | Yes |
| Unique index support | No | Yes |
| Composite indexing | No | Yes |
| Equality-based access | Yes | Yes |

A B-tree index is generally more versatile.

Hash indexing is appropriate when equality-based access is the primary requirement and measurements justify its use.

### 10.4 Relational Constraints and Hash Indexes

Primary keys and unique constraints provide relational integrity.

The PostgreSQL implementation uses primary keys and unique constraints for customer identifiers, account numbers, and transaction references.

These constraints require appropriate unique indexes.

A PostgreSQL hash index cannot replace a unique B-tree index required by a unique constraint.

The separate hash indexes demonstrate additional equality-based access paths.

### 10.5 Query Planning

Creating an index does not guarantee that PostgreSQL will use it.

The planner estimates the cost of different execution strategies.

It considers factors such as:

- Table size.
- Estimated number of matching rows.
- Available indexes.
- Data distribution statistics.
- Estimated I/O and processing costs.

`EXPLAIN` displays the selected execution plan.

`ANALYZE` updates planner statistics.

The SQL script includes both commands to demonstrate the relationship between indexing and query optimization.

## 11. Database Workflow

The PostgreSQL model follows this structure:

`Customers -> Accounts -> Transactions -> Indexes -> Retrieval -> Reporting`

The workflow includes:

1. Registering customers.
2. Creating accounts associated with customers.
3. Recording transactions associated with accounts.
4. Retrieving transactions through indexed identifiers.
5. Updating transaction states.
6. Recording changes in the audit table.
7. Generating account and customer reports.

The foreign keys maintain relational consistency.

The check constraints validate transaction amounts, statuses, and identifier formats.

The audit trigger records transaction changes.

The status-update procedure uses row locking to protect the transaction being modified.

Its state-transition rules prevent invalid transitions from terminal states.

The example transaction uses a savepoint to demonstrate partial rollback.

## 12. Important Edge Cases

| Edge case | Required handling |
|---|---|
| Two keys map to the same bucket | Collision resolution |
| Existing key is inserted again | Update or reject according to policy |
| Missing key is searched | Return an explicit missing-key result |
| Entry is deleted | Preserve remaining entries |
| Open-addressing slot is deleted | Use a tombstone |
| Load factor becomes excessive | Resize and redistribute |
| Key is invalid | Reject before indexing |
| Hash distribution becomes uneven | Monitor chain lengths and collisions |
| Concurrent access occurs | Use appropriate concurrency controls |
| Hash index is not selected | Inspect the execution plan |

## 13. Security Considerations

Hash tables can be vulnerable to algorithmic-complexity attacks when attackers can construct large collections of keys that produce concentrated collisions.

Security controls include:

- Restricting untrusted input sizes.
- Using suitable hash functions.
- Applying randomized or keyed hashing where appropriate.
- Monitoring collision patterns.
- Enforcing request and resource limits.
- Validating keys before insertion.
- Avoiding exposure of internal implementation details.
- Managing cryptographic secrets separately from application data.

Database indexes do not replace authentication, authorization, input validation, or SQL parameterization.

Hashing passwords also requires a dedicated password-hashing algorithm rather than ordinary SHA-256.

## 14. Performance Considerations

The main performance variables are:

| Variable | Performance impact |
|---|---|
| Hash function quality | Affects bucket distribution |
| Load factor | Affects collisions and probing |
| Capacity | Determines available positions |
| Collision strategy | Determines additional lookup work |
| Resizing frequency | Affects insertion latency |
| Key size | Affects hashing cost |
| Memory locality | Affects cache performance |
| Concurrent access | Introduces synchronization considerations |

Average O(1) lookup should not be interpreted as a guaranteed constant execution time.

A poorly distributed hash function or high collision rate can produce O(n) lookup behavior.

For PostgreSQL, index creation should be justified using realistic query patterns and execution plans rather than assuming that every equality search benefits from a hash index.

## 15. Running the Implementations

| File | Runtime | Execution |
|---|---|---|
| Python | Python 3.10+ | `python hash_indexing.py` |
| JavaScript | Node.js 18+ | `node hash_indexing.js` |
| C++17 | C++17 compiler | Compile and execute `hash_indexing.cpp` |
| Java | Java 17 | `javac HashIndexingDemo.java` followed by `java HashIndexingDemo` |
| PostgreSQL | PostgreSQL 14+ | Execute `hash_indexing.sql` using `psql` |

The Python and JavaScript examples use standard-library facilities.

The C++17 implementation uses the standard template library.

The Java implementation uses Java 17 standard APIs.

The PostgreSQL script creates its objects within the `hash_index_lab` schema.

## 16. Validation and Expected Behavior

The implementations include executable assertions or equivalent checks.

The principal expected behaviors are:

- Inserting a new key increases the number of entries.
- Updating an existing key does not create a duplicate.
- Retrieving an existing key returns its associated value.
- Retrieving a missing key produces an explicit missing-key result.
- Deleting an existing key removes it.
- Deleting a missing key does not corrupt the index.
- Resizing preserves existing key-value associations.
- Tombstones do not interrupt valid probing sequences.
- Invalid domain records are rejected.
- PostgreSQL constraints reject invalid relational data.
- Transaction status changes follow defined transition rules.

## 17. Implementation Comparison

| Implementation | Primary data structure | Collision strategy | Additional capability |
|---|---|---|---|
| Python | List of bucket lists | Separate chaining | Dataclasses and statistics |
| JavaScript | Array of bucket arrays | Separate chaining and linear probing | Event-driven monitoring |
| C++17 | Vector and linked lists | Separate chaining and linear probing | Generic transaction directory |
| Java 17 | Collections and generic arrays | Separate chaining and linear probing | Domain records and concurrent access |
| PostgreSQL | Native database index structures | PostgreSQL hash access method | SQL retrieval and relational workflows |

The custom implementations make the internal mechanics visible. Native `Map`, `HashMap`, `ConcurrentHashMap`, and `unordered_map` provide production-oriented alternatives in their respective runtimes.

PostgreSQL hash indexes operate within a database storage and transaction-management system. They should not be treated as interchangeable with application-level hash tables.

The distinction is important: an in-memory hash table manages application data structures, whereas a database hash index provides an access path to persistent relational records.
