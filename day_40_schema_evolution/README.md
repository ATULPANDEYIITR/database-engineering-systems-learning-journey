# Schema Evolution: Changing Schemas Safely Over Time

## Scope

Schema evolution is the controlled modification of a data contract while preserving the correctness and availability of systems that store, produce, consume, or transform that data.

A schema may describe a relational table, an API payload, a serialized event, a configuration document, or an application domain object. A change that is valid for a new application release can still break an older consumer, invalidate historical records, or make a database migration unsafe.

This project examines schema evolution through six complementary artifacts. Python implements schema validation and a transactional migration runner. JavaScript models versioned service contracts and event-driven migration. C++ presents a repository-style customer-data migration case study with atomic replacement. Java implements enterprise migration stages and explicit compatibility policies. PostgreSQL represents schema versions, customer records, backfill operations, constraints, and migration history.

The central engineering problem is not simply how to change a schema. It is how to coordinate that change across existing data and independently deployed software.

## Schema versions and compatibility

A schema version identifies a specific contract. In this project, customer records progress from an initial identity representation to a richer contact representation and then to a stricter representation with explicit fields.

| Version | Contract | Evolution concern |
|---|---|---|
| V1 | Customer identifier and name | Existing producers may know only these fields. |
| V2 | Name plus optional contact information | Old records and old writers may omit the new field. |
| V3 | Renamed display field and required contact information | Historical records must be transformed before the new requirements are enforced. |

A version number alone does not establish compatibility. Compatibility depends on the direction of communication and the behavior of producers and consumers.

**Backward compatibility** means a newer consumer can handle data produced under an older contract.

**Forward compatibility** means an older consumer can handle data produced under a newer contract. This often requires the older consumer to ignore unknown fields instead of rejecting them.

**Full compatibility** generally requires both directions to work under the compatibility rules of the particular protocol or schema system.

**Data migration** transforms persisted records into a new representation. **Application deployment** changes the software that reads or writes those records. These operations are related, but they are not interchangeable. Deploying new software does not automatically repair historical data.

A field addition is not always safe. Adding an optional field is usually less disruptive than adding a required field. A rename can break consumers even when the underlying value has not changed. A type change can lose information or alter serialization. Removing a field can break any consumer that still depends on it.

## Expand, backfill, enforce, and contract

The implementations use a staged migration approach.

| Stage | Purpose | Operational condition |
|---|---|---|
| Expand | Introduce new fields or structures without immediately removing the old representation. | Existing applications can continue operating. |
| Backfill | Transform historical records and measure data quality. | Missing or invalid values are identified and repaired. |
| Enforce | Apply the new contract through validation and database constraints. | Historical data satisfies the new requirements. |
| Contract | Remove obsolete fields or compatibility paths. | Old readers, old writers, and rollback dependencies have been retired. |

This sequence reduces the need for a coordinated, instantaneous deployment of every service.

Consider renaming `full_name` to `display_name`. A direct rename may break a running application that still queries `full_name`. A safer rollout adds `display_name`, copies existing values, updates consumers, moves writers to the new field, and removes the old field only after compatibility requirements have been satisfied.

During a mixed-version deployment, dual-read or dual-write behavior may be necessary. Such behavior must define precedence when both fields contain different values. Otherwise, temporary compatibility code can create persistent data inconsistencies.

## Python implementation

The Python program uses immutable `Field` and `Schema` definitions to express data contracts. Each field records its name, expected type, required status, and optional default. The validator checks unknown fields, missing values, nullability, and type correctness.

The exact integer check is important because Python treats `bool` as a subclass of `int`. Without an explicit check, a boolean could accidentally satisfy an integer contract.

`SchemaRegistry` stores schemas by version and associates adjacent versions with transformation functions. `evolve()` validates the source record, executes each migration in sequence, and validates the result against the next contract. A transformation cannot silently skip an intermediate version.

`MigrationRunner` applies database migrations inside explicit SQLite transactions. It records successful versions in `migration_history`. If a migration fails, the runner rolls back the schema change and its history entry. The included failure case creates a table and deliberately raises an exception to verify that neither operation persists.

The database example starts with a customer table, adds a nullable phone field, and then rebuilds the table to introduce a constrained country code. Rebuilding is used because adding certain required columns to populated SQLite tables has limitations.

The tests cover missing required fields, unknown fields, boolean-versus-integer validation, missing migration paths, and mutable default isolation. The mutable-default test ensures that one validated record cannot modify the default subsequently used by another record.

The implementation is intended for learning and controlled migrations. A production system also needs migration checksums, durable operational logging, recovery procedures, backup verification, and coordination between concurrently running application versions.

## JavaScript implementation

The JavaScript implementation focuses on service contracts and event-driven state changes.

The schema catalog contains three versions of a customer payload. Each version declares required and optional fields and defines its own validation rules. The `validate()` function rejects unknown properties, missing required properties, invalid identifiers, and malformed values.

Migration functions transform V1 into V2 and V2 into V3. A missing email is assigned a clearly marked migration-domain address in the V1-to-V2 transformation. Such an address allows the structural migration to proceed, but it must not be mistaken for a verified customer email. Real applications should preserve provenance for synthetic or unverified values and must not send customer communications to them.

`ContractCatalog` extends Node.js `EventEmitter`. Saving a record emits a `record.saved` event. Activating a new schema emits `schema.activated`, allowing observers to record migration activity or update operational monitoring.

The bulk migration first prepares every replacement record in a separate map. Only after all transformations succeed are the replacements published. This avoids partially updating the in-memory collection when one record fails validation.

The catalog also tracks record revisions to illustrate optimistic concurrency. A client supplies the revision it previously read. If another update has changed the record, the write is rejected rather than silently overwriting the newer version.

The contract fingerprint uses SHA-256 over a stable representation of version and field names. This can help identify contract changes in automated checks, but it is not a complete semantic schema comparison. Production fingerprints should also include types, constraints, defaults, nullability, serialization rules, and relevant compatibility settings.

## C++ case study

The C++ program models a customer directory undergoing a transition from an identity-only contract to a representation that requires contact information.

`CustomerV1`, `CustomerV2`, and `CustomerV3` are distinct domain types. Separate validation functions prevent the program from treating all versions as interchangeable structures. `std::optional<std::string>` represents the nullable email introduced during expansion.

The migration from V1 to V2 preserves the fact that an old record may not contain an email. The V2-to-V3 conversion rejects a record with no email rather than manufacturing a value that appears to be verified. This demonstrates why a structural change and a business-data repair must be treated as separate responsibilities.

`CustomerRepository` uses an ordered map to represent the legacy dataset and constructs an expanded snapshot. `VersionedStore` validates a complete replacement dataset before publishing it. Duplicate identifiers or invalid records prevent the replacement from being accepted.

The replacement method also checks an expected revision. This provides a simple optimistic-concurrency mechanism: a migration prepared against an outdated dataset cannot replace a newer revision without detection.

The `Deployment` model represents the expand, backfill, enforce, and contract stages as explicit states. A transition to enforcement requires a completed backfill. Contracting is blocked while old readers or writers remain active.

Ordered-map insertion has logarithmic lookup and insertion costs, making a complete batch replacement approximately O(n log n). This is appropriate for a compact case study, but a large production migration should usually use bounded batches, progress checkpoints, retry-safe operations, and explicit handling of concurrent writes.

The in-memory atomic replacement is not equivalent to a durable database transaction. Process failure, storage durability, multi-process concurrency, and crash recovery require mechanisms supplied by the actual persistence layer.

## Java implementation

The Java program emphasizes enterprise domain modeling and policy decisions.

Records represent customer data for each schema version. Their compact constructors enforce basic invariants when instances are created, preventing invalid objects from entering the migration workflow through ordinary construction.

`ChangeRisk` classifies proposed schema changes. `CompatibilityPolicy` evaluates each change against explicit conditions, including whether a default exists and whether older consumers remain deployed. The result contains both a compatibility decision and an explanation of the rule applied.

The policy is intentionally conservative. A field removal, rename, or type change is not accepted while old consumers remain active. A required field can be added more safely when an appropriate default or staged rollout makes the transition compatible. The exact decision still depends on business semantics and consumer behavior.

`MigrationService` models the deployment stages as an enum and rejects invalid transitions. It requires the backfill to be complete before enforcement and prevents contract removal while legacy applications remain active. Migration history records adjacent version transitions and timestamps.

`CustomerService` validates a complete replacement collection before publishing it. Duplicate identifiers are rejected, and a revision check prevents a stale migration batch from replacing a more recent state.

These in-memory components illustrate domain rules rather than replacing a durable migration platform. An enterprise implementation would persist migration history, coordinate workers across processes, acquire suitable database locks, and expose operational state for deployment automation.

## PostgreSQL relational model

The SQL script represents schema evolution through three related structures:

- `customers` stores the actual business records, including the fields introduced during successive changes.
- `schema_versions` records the versions that have been applied, their descriptions, and their checksums.
- `migration_events` records lifecycle events and their structured metadata in `JSONB`.

Primary keys, uniqueness constraints, check constraints, and non-null constraints enforce data integrity at the database layer. These rules remain effective regardless of which application performs a write.

The initial customer records include a missing email to represent historical data that cannot immediately satisfy a stricter contract. The expansion introduces nullable columns before attempting to enforce stronger requirements.

The backfill fills the country code and normalizes existing email values. Missing emails are queried separately instead of being represented as valid customer addresses. The script uses a regular-expression check to enforce the country-code format and validates the constraint after installation.

PostgreSQL's `NOT VALID` option allows an eligible check constraint to be installed without immediately scanning every historical row. `VALIDATE CONSTRAINT` subsequently verifies existing records. This separates constraint installation from validation, though the operations still acquire locks and consume resources that must be considered during production deployment.

The index on `(country_code, created_at DESC)` supports queries that filter by country and retrieve recent customer records. It would not be justified solely because the columns exist; its usefulness depends on actual query patterns and data distribution.

The `customer_directory` view exposes a stable application-facing projection. A later migration adds `display_name`, backfills it from `full_name`, and updates the view while retaining the legacy column. This models a rename as an expand-and-contract operation rather than an immediate destructive change.

The final transaction demonstrates a rejected country code. A value such as `IND` violates the two-character constraint. The database reports the failure, and rollback leaves no invalid customer record behind.

The script deliberately does not drop `full_name`. Removing it would be safe only after all dependent readers and writers had moved to `display_name` and the rollback window had expired.

## Migration failure modes

### Incomplete backfill

A migration may add a column successfully while leaving historical rows null. Applying `NOT NULL` immediately afterward can fail. The migration process should inspect missing values, validate the repaired data, and only then enforce the constraint.

### Incorrect defaults

A default can make a structural migration possible without supplying meaningful business information. A default country code, status, or consent value must reflect an explicit domain rule. It must not be selected merely to silence a constraint failure.

### Partial deployment

New application instances may write fields that old instances do not recognize. Old instances may overwrite values maintained by new instances. Compatibility testing must cover both old-reader/new-writer and new-reader/old-writer combinations where both combinations can occur during deployment.

### Destructive rollback

After new data has been written, reverting the application version may not be enough. The new representation may contain information that cannot be represented in the old schema. Rollback planning must account for data loss, not just code deployment.

### Duplicate migration execution

Deployment automation can retry after timeouts or uncertain responses. A migration should be either transactionally atomic or explicitly idempotent. The Python migration runner uses a unique version key and transaction to prevent the same successful migration from being recorded twice.

### Concurrent writes during migration

A backfill may race with application updates. Depending on the design, the system may need dual writes, change capture, row-level version checks, a final reconciliation pass, or a controlled write pause. An offline snapshot alone does not solve concurrent modification.

## Compatibility and data integrity

Schema compatibility and data integrity answer different questions.

Compatibility asks whether different software versions can communicate or operate against the same representation. Integrity asks whether the resulting records satisfy the rules of the domain.

An older reader may be structurally compatible with a record that contains an additional optional field, yet still mishandle its meaning. A new reader may accept an old record structurally, yet reject it because a required business value is absent.

Validation should therefore exist at appropriate boundaries:

- Producers validate the records they emit.
- Consumers validate incoming data before using it.
- Migration code validates both the source and transformed representations.
- Databases enforce durable constraints that must hold for every writer.

Validation at multiple boundaries is not unnecessary duplication when each boundary protects a different failure mode. Application checks improve error reporting, while database constraints protect stored data from concurrent requests, alternate services, and operational scripts.

## Performance and production considerations

Migration cost depends on the number of records, the transformation complexity, indexes, locking behavior, transaction size, and the replication topology.

A single large transaction provides clear atomicity but may create substantial lock duration, write-ahead-log volume, replication lag, and rollback cost. Batched migrations reduce transaction size and make progress easier to observe, but require resumability and careful handling of records modified during processing.

For large tables, a production plan should estimate the scan and update workload, inspect query plans, monitor lock waits and replication lag, and define acceptable deployment impact. New indexes may need a concurrent creation strategy when supported by the database and operational constraints.

Schema changes should be tested against realistic historical data rather than only empty development databases. Tests should include nulls, duplicates, unexpected values, maximum field sizes, malformed serialized records, partially migrated datasets, and interrupted migration attempts.

Migration history should identify exactly which change was applied and whether the data transformation completed. Checksums can detect accidental modification of migration definitions, but they do not prove that the resulting database matches the intended schema. Periodic schema inspection and post-migration data checks are still necessary.

## Security and governance

Schema evolution can change the exposure of sensitive information. A newly added field may require different access controls, retention rules, encryption, audit logging, or data-classification treatment. A migration must not copy sensitive values into logs or diagnostics unnecessarily.

A schema change can also alter authorization behavior indirectly. For example, a newly introduced tenant identifier or ownership field must not receive a permissive default that accidentally grants cross-tenant access. Required security attributes should be backfilled from trusted sources and validated before enforcement.

Production migration privileges should be separated from ordinary application write privileges. Migration scripts should run under an appropriately scoped database identity, and destructive contract operations should require explicit deployment authorization.

The decision to remove a legacy field should be supported by evidence that the field is no longer used, not simply by the existence of a newer schema version. Monitoring, dependency inventories, migration history, and rollback requirements collectively determine when a change is safe to finalize.
