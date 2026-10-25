# PostgreSQL JSON and JSONB: Querying, Indexing, and Document Management

## Overview

PostgreSQL supports JSON documents alongside conventional relational data. This project demonstrates how to store structured attributes, validate document shapes, query nested values, index frequently accessed properties, update documents safely, and report on document contents.

The implementations use a product inventory domain. Product identifiers, names, categories, prices, and lifecycle state are relational attributes. Flexible properties such as hardware specifications, wireless capabilities, calibration requirements, and connection types are represented as JSON documents.

The five implementations provide complementary perspectives:

- **Python:** An in-memory document repository with validation, containment queries, path extraction, selected-field indexes, and document updates.
- **JavaScript:** An event-driven document store with immutable document snapshots, indexed lookups, and change notifications.
- **C++17:** A typed document model and repository designed around STL containers, deterministic serialization, containment, and indexed lookups.
- **Java 17:** An enterprise-oriented service with immutable domain records, explicit validation, document state, and synchronized repository operations.
- **PostgreSQL:** A relational schema with JSON and JSONB columns, constraints, GIN and expression indexes, triggers, transactional updates, and reporting queries.

The in-memory implementations simulate selected database behaviors. They are educational models rather than replacements for PostgreSQL's parser, storage engine, concurrency control, or query planner.

## 1. JSON and JSONB

PostgreSQL provides two primary JSON storage types.

| Property | `json` | `jsonb` |
|---|---|---|
| Storage | Stores the supplied JSON text representation | Stores a decomposed binary representation |
| Input validation | Validates JSON syntax | Validates JSON syntax and converts the document to its internal representation |
| Whitespace and object-key formatting | Preserves the original textual representation | Does not preserve the original formatting |
| Object-key ordering | Preserves the input text's ordering | Does not guarantee the original ordering |
| Duplicate object keys | Preserves them in the stored text | Keeps one value for a duplicate key, generally the last occurrence |
| Query operations | Supports JSON extraction operators | Supports extraction, containment, existence operators, JSONPath, and other operations |
| Indexing | Does not support the same JSONB GIN indexing capabilities | Supports GIN indexes and expression indexes |
| Typical use | Retaining the original JSON representation | Query-intensive document storage |

The PostgreSQL schema stores `raw_attributes` as `json` and `attributes` as `jsonb`. This makes the storage distinction explicit. The application queries use `attributes`, since its indexing and containment capabilities are central to the workflow.

Storing both representations consumes extra space and requires the application to keep them synchronized. A production system should store both only when preserving the original representation serves a defined requirement. Otherwise, a single `jsonb` column is usually sufficient for query-oriented document storage.

### JSON syntax and database values

A JSON document can contain objects, arrays, strings, numbers, booleans, and `null`.

For example, an inventory document may contain:

- `brand`: a string identifying the manufacturer.
- `wireless`: a boolean capability.
- `specs`: an object containing RAM and storage capacity.
- `ports`: an array of connection types.
- `calibration`: an optional nested object.

JSON `null` is a value within a document. SQL `NULL` represents an absent database value or an unknown value in SQL expressions. A missing JSON key is a third, distinct condition.

These distinctions affect filters, constraints, and reporting.

## 2. Choosing a Document Model

The relational and document parts of the product model serve different purposes.

| Relational column | JSONB property | Reason |
|---|---|---|
| `sku` | None | Requires stable identity and uniqueness |
| `name` | None | Frequently displayed and validated |
| `category` | None | Supports relational filtering and indexing |
| `price` | None | Requires numeric precision and comparison |
| `attributes` | `brand`, `wireless`, `specs`, `ports` | Holds variable product characteristics |
| `tags` | None | Uses PostgreSQL's native `text[]` representation |
| `document_version` | None | Tracks successful document modifications |

Flexible document storage should not replace relational columns indiscriminately.

Keep a property relational when it requires independent identity, frequent joins, referential integrity, stable constraints, or extensive aggregation. JSONB is particularly useful for optional or evolving properties that naturally belong to a single entity.

For example, `specs.ram_gb` works well as a JSONB property when different product categories have different specifications. If RAM becomes a central business metric requiring extensive joins and strict domain constraints, a normalized specification table or dedicated relational column may become preferable.

## 3. Querying JSON and JSONB

PostgreSQL provides operators for extracting values, testing key existence, checking containment, and evaluating JSONPath expressions.

### Extraction operators

| Operator | Result | Example |
|---|---|---|
| `->` | JSON or JSONB value | `attributes -> 'specs'` |
| `->>` | Text value | `attributes ->> 'brand'` |
| `#>` | JSON or JSONB value at a path | `attributes #> '{specs,ram_gb}'` |
| `#>>` | Text value at a path | `attributes #>> '{specs,ram_gb}'` |
| `?` | Tests whether a top-level object key or string array element exists | `attributes ? 'wireless'` |
| `@>` | Tests JSONB containment | `attributes @> '{"wireless":true}'` |

Extraction operators return SQL `NULL` when the requested key or path cannot be found. Text extraction converts the selected JSON value to text, so numeric calculations generally require an explicit cast.

For example, a query that calculates average RAM must extract `specs.ram_gb`, verify its JSON type, and convert it to a numeric SQL value. The PostgreSQL script uses these checks before performing aggregation.

### Containment

The JSONB containment operator `@>` checks whether one document contains the structure specified by another document.

The predicate `attributes @> '{"specs":{"ram_gb":32}}'::jsonb` matches a document with the nested RAM property equal to `32`, even if that document contains additional keys.

Containment does not require complete document equality. It is useful for searching a subset of nested properties without specifying every property in the stored document.

Array containment has its own semantics. JSONB array containment does not require identical array ordering, and duplicate array elements do not behave like a multiset with duplicate-sensitive matching. The in-memory implementations illustrate containment, but their array matching is not intended to reproduce every PostgreSQL edge case.

### JSONPath

PostgreSQL JSONPath supports structured path expressions and predicates. The script uses `jsonb_path_exists` to find products whose nested RAM capacity satisfies a numeric threshold.

JSONPath is valuable when a query needs conditional traversal or more complex predicates than a direct extraction or containment expression. Its use should still be evaluated against realistic data volumes and query plans.

### Expanding arrays

`jsonb_array_elements_text` converts elements of a JSON array into rows. A lateral join makes each document's array available to the query.

This is useful when a document contains several connection types and a report needs one row per product and connection type. The PostgreSQL example protects the function call by checking that the selected value is an array.

For workloads that repeatedly join or aggregate array elements, a normalized child table may provide stronger constraints and a more efficient relational model.

## 4. Indexing JSONB

An index should support a known query pattern. Creating indexes on every JSON property increases storage, maintenance work, and write latency.

### GIN index with `jsonb_path_ops`

The PostgreSQL script defines:

- A GIN index on `attributes` using `jsonb_path_ops`.
- A B-tree expression index on `attributes ->> 'brand'`.
- A partial B-tree index for active products by category.
- A GIN index on the relational `tags` array.

The `jsonb_path_ops` operator class is suited to supported JSONB containment and JSONPath search patterns. It creates a more specialized index than the default JSONB GIN operator class, but it does not support every key-existence operation supported by the default class.

When key-existence predicates such as `attributes ? 'wireless'` are a major workload, evaluate the default `jsonb_ops` operator class instead.

### Expression indexes

The expression index on `attributes ->> 'brand'` supports equality predicates on the extracted brand text.

The query must use a compatible expression for PostgreSQL to use the index. A general GIN index and a scalar expression index solve different problems:

- GIN indexes support document-oriented operations over many JSONB properties.
- B-tree expression indexes support selected scalar comparisons and ordering patterns.

The partial index on `(category, product_id)` includes only active products. It is useful when queries filter active inventory by category and retrieve products in identifier order.

### Query plans

`EXPLAIN` displays the execution plan selected by PostgreSQL. It does not execute the query in the same way as `EXPLAIN ANALYZE`.

A sequential scan is not necessarily a problem. Small tables may be cheaper to scan than to access through an index. PostgreSQL's decisions depend on statistics, selectivity, estimated row counts, and cost settings.

For meaningful index evaluation:

- Populate representative data volumes.
- Run `ANALYZE` after significant data changes.
- Compare plans for realistic predicates.
- Use `EXPLAIN (ANALYZE, BUFFERS)` when actual execution measurements are appropriate.
- Evaluate write overhead and index size as well as read performance.

## 5. Python Implementation

The Python file implements `ProductRepository`, which stores immutable product records in a dictionary keyed by identifier.

### Validation

`DocumentError` represents application-level validation failures. The repository validates product names, categories, prices, and attribute structures before storing a record.

The JSON validator rejects unsupported values, non-finite numbers, excessive nesting, and documents exceeding a size limit. JSON serialization and deserialization produce a detached document representation so callers cannot mutate stored nested dictionaries through the original input.

The `Decimal` type represents product prices, avoiding the binary floating-point precision issues that can arise when representing currency with `float`.

### Indexes and queries

The category index maps each category to a set of product identifiers. The attribute index maps selected top-level scalar properties to matching identifiers.

These indexes demonstrate the basic trade-off between faster equality lookups and additional maintenance during writes.

`query_category` retrieves products through the category index. `query_attribute` retrieves matching products through the scalar attribute index. `contains_attributes` recursively checks whether selected JSON-like properties match a required structure.

`extract_path` walks nested dictionaries and lists, returning `None` when a requested path is absent or invalid.

### Updating documents

`update_attributes` validates the merged document before replacing the stored record. It updates the selected-field indexes to keep query results consistent with the new attributes.

The demonstration includes successful nested extraction, containment checks, attribute updates, and rejected invalid input.

The in-memory indexes are deliberately limited. They do not implement PostgreSQL's GIN structures, query planner, transaction isolation, or concurrent update handling.

## 6. JavaScript Implementation

The JavaScript file uses Node.js standard-library functionality and an event-driven document store.

### Event-driven behavior

`JsonDocumentStore` extends `EventEmitter`. Successful creation and update operations emit events containing identifiers and change metadata.

This separates document mutation from downstream consumers. An application could use such events to refresh a cache, update a search index, or notify a monitoring service. Those external effects would need their own reliability controls in a production deployment.

### JSON validation and extraction

The `validateJson` function checks supported JSON values, nesting depth, and object keys. `cloneJson` serializes and parses values to detach stored data from caller-owned references.

`extractPath` walks object keys and array indexes. `containsJson` implements recursive object and array containment for the example's supported data shapes.

The `canonical` function sorts object keys before producing a deterministic serialization. This is useful for the demonstration's equality indexes, but it is not a substitute for PostgreSQL's internal JSONB representation or a general-purpose canonical JSON standard.

### Index maintenance

Private class fields hold the document store and its indexes. Private methods add and remove identifiers from index entries. Updates construct a replacement document, replace the stored value, refresh indexes, and emit an event.

JavaScript's numeric type is IEEE 754 double precision. The example therefore represents prices as integer cents and rejects values that are not safe, non-negative integers. This prevents fractional-cent values and avoids precision errors for the supported range.

The implementation is single-process and in-memory. Its event handlers are synchronous, and it does not provide durable storage, cross-process locking, or database transactions.

## 7. C++17 Implementation

The C++17 program models documents with a `Json` class backed by `std::variant`.

The supported value types are null, boolean, finite number, string, array, and object. Objects use `std::map`, providing deterministic key ordering for the demonstration's serialization.

### Typed document operations

The `Json` class provides:

- Object lookup using `get`.
- Deterministic serialization using `canonical`.
- Recursive containment using `contains`.
- Type-aware comparisons between scalar JSON values.

The repository stores products in an ordered map. Category and attribute indexes use maps of sets of identifiers, which provide deterministic output and avoid duplicate identifiers in an index entry.

### Update consistency

`updateAttributes` constructs a replacement document before changing the existing state. It then removes the old index entries, stores the replacement, and inserts the new index entries.

This sequence demonstrates the need to keep primary records and secondary indexes synchronized. Unlike a database transaction, it does not offer rollback if an unexpected failure occurs during index maintenance. A production implementation would use stronger transactional boundaries or a data structure that supports safe rollback.

The program intentionally avoids external libraries. It does not include a general JSON text parser, Unicode normalization, or PostgreSQL-compatible JSONPath support. Its `Json` class is a typed data model rather than a complete JSON implementation.

## 8. Java 17 Implementation

The Java file models a small enterprise document service.

### Domain records and immutability

The `Product` record defines a product's identity, name, category, price, attributes, tags, and lifecycle state. Its compact constructor validates domain invariants.

`freezeJson` recursively copies supported values into unmodifiable maps and lists. Numeric values are converted to `BigDecimal`, which provides decimal arithmetic and avoids relying on binary floating-point representations for prices.

The service uses synchronized methods to serialize operations on a single service instance. This does not replace database-level transaction management or distributed concurrency control.

### Repository operations

`DocumentService` provides creation, category lookup, scalar attribute lookup, containment filtering, nested path extraction, and attribute updates.

The secondary indexes map normalized category or attribute keys to sets of product identifiers. The service replaces immutable document snapshots during updates and maintains the indexes around each successful replacement.

### Validation and limitations

The implementation rejects invalid prices, malformed category values, unsupported JSON data types, excessive nesting, and oversized attribute documents.

Its containment and equality rules cover the included examples, not every detail of PostgreSQL's JSONB type semantics. A production service should also define schema-version policies, authorization checks, request limits, observability, and database transaction boundaries.

## 9. PostgreSQL Schema and Workflow

The SQL script creates a dedicated `json_lab` schema containing product records, document change history, and query audit records.

### Relational integrity

The `product` table enforces:

- Unique product SKUs.
- Valid names and categories.
- Non-negative numeric prices.
- A positive document version.
- Object-shaped JSONB attributes.
- A maximum serialized document size.

The `attribute_change` table records document version transitions and the keys that changed. Foreign-key enforcement prevents a change record from referring to a nonexistent product.

The `query_audit` table stores the outcome and structured details of a rejected write in the example. Such an audit record is not equivalent to a complete security audit trail.

### Trigger-based validation

The `validate_product_attributes` trigger validates document structure and the `specs.ram_gb` property before a write proceeds.

The `record_attribute_change` trigger tracks document modifications and increments the document version when attributes change. It also records the set of changed top-level keys.

Triggers help enforce rules for writes that pass through the database, including writes made by different application clients. They should be designed carefully because trigger logic also affects write latency and transaction behavior.

### Atomic updates

`jsonb_set` replaces a selected property without requiring the application to reconstruct the entire document. It can also create the final path component when the `create_if_missing` argument is true, provided the earlier path components exist.

The script uses `jsonb_set` to add a warranty property and update nested storage capacity. These changes participate in ordinary PostgreSQL transaction semantics.

A JSONB update still creates a new row version under PostgreSQL's MVCC model. Frequently changing large documents can therefore generate table and index bloat, making autovacuum monitoring and document-size control important.

### Error handling

The script demonstrates a nested PL/pgSQL exception block around an invalid insert. The invalid statement is rolled back to the exception block's implicit subtransaction boundary, while the rejected outcome can be recorded in the enclosing transaction.

Database constraints and triggers provide authoritative validation for database writes. Application validation improves error messages and prevents unnecessary requests, but it should not be the only enforcement layer for important invariants.

## 10. JSONB Security and Data Quality

JSONB storage does not automatically guarantee that every document has the correct business meaning.

A document can be valid JSON and still contain the wrong types, missing required properties, unexpected nested structures, or values outside an acceptable business range.

Useful controls include:

- **Shape validation:** Check that required fields have expected JSON types.
- **Range validation:** Enforce numeric limits and valid enumerated values.
- **Document limits:** Restrict nesting depth and serialized size.
- **Safe SQL parameters:** Pass user-supplied JSON through bound parameters rather than concatenating it into SQL statements.
- **Access control:** Use database roles and privileges to limit who can read or modify document data.
- **Versioning:** Track schema versions when applications evolve document structures.
- **Auditability:** Record relevant changes without logging secrets or sensitive document contents unnecessarily.

JSON property names should be treated as data, not trusted SQL identifiers. Dynamic SQL requires careful identifier handling and parameterization. Application code should also avoid unrestricted recursive processing of user-supplied structures.

The JavaScript and Python validators reject some unsupported values before storage. These checks are useful, but database-level constraints remain important when multiple clients can write to the same tables.

## 11. Performance and Operational Trade-Offs

| Design choice | Benefit | Cost or limitation |
|---|---|---|
| JSONB storage | Flexible structured properties and document operators | Less direct enforcement of arbitrary nested business rules |
| GIN index | Supports suitable containment and document-search predicates | Additional storage and write maintenance |
| B-tree expression index | Efficient lookups for a selected extracted scalar | Tied to the indexed expression and workload |
| Partial index | Avoids indexing rows outside a common filter | Helps only queries compatible with the predicate |
| Recursive application validation | Clear errors before database writes | Adds processing cost and duplicates some database checks |
| Document change history | Supports auditing and debugging | Consumes storage and adds write overhead |
| Normalized child table | Strong relational constraints and convenient joins | Requires a more explicit relational schema |
| Large JSON documents | Keeps related optional properties together | May increase row-version, update, and indexing costs |

The in-memory indexes use hash-based or ordered containers, depending on the implementation. Their lookup complexity depends on the selected container and the number of matching identifiers.

PostgreSQL's GIN index has a different internal structure and maintenance model. Its actual performance depends on the document distribution, operator class, query selectivity, table statistics, and write workload.

## 12. Running the Implementations

### Python

Save the Python source as `jsonb_workflow.py` and run `python jsonb_workflow.py` using Python 3.10 or later.

### JavaScript

Save the JavaScript source as `jsonb_workflow.js` and run `node jsonb_workflow.js` using Node.js 18 or later.

### C++17

Save the C++ source as `jsonb_workflow.cpp`. Compile with `g++ -std=c++17 -O2 -Wall -Wextra -pedantic jsonb_workflow.cpp -o jsonb_workflow` and run the resulting executable.

### Java 17

Save the Java source as `JsonDocumentGovernance.java`. Compile with `javac JsonDocumentGovernance.java` and run `java JsonDocumentGovernance`.

### PostgreSQL

Save the SQL source as `jsonb_workflow.sql` and execute it against a disposable PostgreSQL 15 or later database using a role with permission to create schemas, tables, functions, triggers, and indexes.

For example, the script can be executed through `psql` using `psql -v ON_ERROR_STOP=1 -d your_database -f jsonb_workflow.sql`.

The SQL script recreates the `json_lab` schema. It must not be run against a database containing unrelated objects that need to be preserved.

## 13. Practical Interpretation

The implementations establish a consistent distinction between relational facts and flexible document properties.

Python, JavaScript, C++17, and Java 17 show how an application can validate, inspect, query, and update JSON-like documents while maintaining selected lookup indexes. Their indexes and containment algorithms are intentionally simplified models.

PostgreSQL provides the production-oriented database mechanisms: native JSON and JSONB types, nested extraction operators, containment predicates, JSONPath, GIN indexes, expression indexes, relational constraints, triggers, and transactions.

The key design decision is not whether every attribute should be stored in JSONB. It is whether each attribute's variability, integrity requirements, access patterns, and update frequency justify document storage rather than a conventional relational representation.
