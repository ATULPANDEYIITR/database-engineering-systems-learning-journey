# Database Design Patterns: Audit Tables, Soft Deletes, and Status Models

## Purpose and scope

Enterprise database design must represent both the current state of a business entity and the history of changes that produced that state. An equipment registry illustrates the problem: a pump may be requested, approved, placed in service, sent for maintenance, or retired. A record may also be removed from ordinary application views because it was entered incorrectly or transferred out of scope. These events must not be confused with one another.

Three database patterns address different requirements:

- **Audit tables** preserve attributable evidence of changes, including the actor, timestamp, previous values, resulting values, and reason.
- **Soft deletes** make records unavailable to ordinary application queries without physically removing the underlying row.
- **Status models** represent valid business states and restrict which transitions are allowed.

The patterns work together, but none replaces the others. An audit table does not itself prevent invalid state transitions. A soft-delete flag does not explain why a record was removed. A status column does not preserve earlier values.

The Python, JavaScript, C++, Java, and PostgreSQL implementations model these distinctions through an equipment-maintenance scenario.

## Audit tables

### Current state and historical evidence

A normal business table stores the current representation of an entity. If the `equipment` row contains `status = 'maintenance'`, that value describes the current state. It does not show when the equipment entered service, who approved it, or why it was sent for maintenance.

An audit table records individual events. A typical event contains:

| Field | Purpose |
|---|---|
| `audit_id` | Unique identifier or sequence for the event |
| `equipment_id` | Reference to the affected equipment |
| `action` | Type of operation, such as creation, rename, status change, deletion, or restoration |
| `actor_id` | Identity of the user or service responsible for the operation |
| `occurred_at` | Time at which the event was recorded |
| `old_values` | Relevant values before the change |
| `new_values` | Relevant values after the change |
| `reason` | Business justification supplied for the operation |
| `correlation_id` | Identifier connecting related operations across a workflow |

The old and new values can be stored in structured columns or a JSON document. PostgreSQL's `JSONB` type allows the audit schema to capture different fields for different actions while retaining queryable data. Frequently filtered values, such as entity identity and event time, should remain ordinary relational columns.

An audit event is not a replacement for the current entity. Queries for the current equipment status should normally read the equipment table. Queries for the lifecycle should read the audit table.

### Recording changes consistently

The Python repository records an event whenever a supported mutation succeeds. Its `_record_event` method receives the entity, actor, action, old values, new values, correlation identifier, and optional reason.

The JavaScript service follows an event-driven design. It emits an audit event after the in-memory record and event collection have been updated. The event subscriber receives a copy, preventing a listener from changing the repository's internal objects through a shared reference.

The C++ registry centralizes event creation in `appendEvent`, assigning a monotonically increasing sequence number. The Java implementation uses an immutable `AuditEntry` record and copies its maps, preventing callers from modifying an existing entry through a mutable map reference.

The PostgreSQL implementation records creation and update events through triggers. Entity changes and trigger-generated audit entries participate in the same transaction. If the transaction rolls back, both changes are rolled back.

### Audit integrity and limitations

An audit table is useful only when the application can trust the completeness and attribution of its events. The application should derive actor identity from authenticated server-side context rather than accept arbitrary actor names from a public request.

Append-only behavior should be enforced through database privileges and, where appropriate, triggers. The SQL implementation rejects ordinary updates and deletes against the audit table. This is not protection against a database owner or superuser who can alter the schema, disable triggers, or change permissions.

High-assurance environments may require separate ownership, tightly restricted access, independent log shipping, tamper detection, retention controls, and monitored backups. Sensitive information should not be copied indiscriminately into audit payloads. Audit records also need an explicit retention and access policy.

Timestamps support ordering and investigation, but timestamps alone are not a reliable unique event sequence. Two events can occur at the same instant, and application clocks may differ. The SQL audit identifier provides an additional ordering key within the database.

## Soft deletes

### Logical deletion rather than physical removal

A soft delete changes a record's visibility without removing the row. The equipment record remains available for investigation and, when permitted, restoration.

The implementations use a deletion flag together with deletion metadata:

- `is_deleted` or `deleted` indicates whether the record is hidden from ordinary queries.
- `deleted_at` records the deletion time.
- `deleted_by` identifies the actor responsible for the operation.

The metadata must agree with the flag. A deleted record requires both a timestamp and an actor. An active record must not retain stale deletion metadata.

The Python `Equipment.validate` method checks this invariant. Java uses the same domain rule. The PostgreSQL table has a `CHECK` constraint that rejects inconsistent combinations regardless of which application writes the row.

### Visibility is not business status

Deletion and business status are independent dimensions.

An equipment record may be approved but soft-deleted because it belongs to the wrong department. Restoring the record should recover its approved status rather than reset it to the initial requested state.

This separation prevents a common design mistake: creating a status such as `deleted` inside the same enum that represents operational lifecycle states. Deletion describes record visibility; approval, maintenance, and retirement describe business lifecycle.

The Python and JavaScript repositories provide separate active and include-deleted queries. The C++ implementation excludes deleted equipment from `activeEquipment()`. The Java implementation filters deleted records in `listActive()`. PostgreSQL provides an `active_equipment` view that excludes logically deleted rows.

Application code should use active-record filters consistently. A forgotten filter can expose records that users expect to be hidden. Administrative, recovery, and audit workflows may need explicit access to deleted records.

### Uniqueness and restoration

Soft deletion does not automatically release unique values. In the SQL schema, `asset_tag` remains unique across active and deleted records. This prevents a second equipment row from reusing a tag that still belongs to a retained record.

If the business requires tag reuse, the schema could replace the table-level uniqueness rule with a partial unique index:

`CREATE UNIQUE INDEX equipment_active_tag_unique ON equipment(asset_tag) WHERE is_deleted = FALSE;`

That alternative introduces a restoration conflict. If a new active row has reused a deleted row's tag, restoring the original record would violate the partial unique index. Restoration must therefore check uniqueness and either reject the operation or follow an explicit reassignment policy.

Soft deletion also increases storage and index maintenance costs because the retained rows continue to exist. Retention policies should specify whether old records are permanently removed, archived, anonymized, or retained for a regulated period.

## Status models

### Representing a valid business lifecycle

A status model should describe the states an entity can occupy and the transitions allowed between them. It should not be a collection of arbitrary strings that any caller can assign.

The equipment examples use the following lifecycle:

`requested -> approved -> in_service -> maintenance -> in_service`

Approved, in-service, and maintenance equipment may also transition to `retired` according to the configured rules. A retired record has no outgoing transitions in this model.

The transition graph is represented as a map from each status to the set of permitted destination statuses. The Python dictionary, JavaScript `Map`, C++ map, and Java enum-based transition table express the same domain rule through appropriate language-specific structures.

The model rejects a direct transition from `requested` to `retired`. The operation fails before changing the status or appending an audit event. This avoids an audit entry that falsely records an operation that was never accepted.

### Enforcing transitions at the database layer

Application validation improves error messages and prevents invalid commands from proceeding through normal service paths. It is not sufficient by itself when several applications or administrative scripts can update the same database.

The PostgreSQL schema stores permitted pairs in `status_transition_rules`. A trigger checks any status change against this table and raises a constraint-related error when no matching transition exists.

A transition table has an operational advantage over hard-coded trigger conditions: authorized lifecycle rules can be inspected as data. A more complex enterprise design may add effective dates, required roles, approval conditions, or versioned policy definitions. Such extensions need controlled policy administration and validation so that configuration changes cannot accidentally authorize invalid workflows.

The sample trigger enforces transition existence, not every possible authorization rule. A real service must also verify whether the actor is permitted to request the transition and whether any required business evidence exists.

## Optimistic concurrency control

Audit completeness does not prevent concurrent updates from overwriting one another. Consider two users who load equipment version 4. One changes the name, while the other changes the status. If both write unconditionally, the later write may overwrite the earlier user's data.

The implementations maintain a positive integer `version`. A mutation includes the version observed by the caller and is accepted only if that version matches the current record.

A relational update uses a conditional predicate:

`UPDATE equipment SET name = $1, version = version + 1 WHERE equipment_id = $2 AND version = $3 AND is_deleted = FALSE RETURNING equipment_id, version;`

If no row is returned, the request used stale data or addressed a record that is not visible under the specified policy. The API should distinguish these cases where authorization and disclosure rules permit.

A successful mutation increments the version and records the audit event in the same database transaction. The version protects against lost updates; the audit table explains the accepted changes. These are separate responsibilities.

## Python implementation

The Python program implements an in-memory equipment repository with typed domain objects, an explicit transition graph, and domain-specific exceptions.

`EquipmentRepository.create` normalizes the asset tag and rejects duplicate registration. `transition` checks the transition graph and expected version before changing the operational state. `soft_delete` records deletion metadata and hides the record from the ordinary retrieval method. `restore` clears deletion metadata without erasing the status history.

The repository centralizes event creation in `_record_event`. The history query filters audit events by equipment identity, while `verify_audit_coverage` checks whether each retained entity has a creation event and whether event timestamps are ordered.

The idempotency demonstration prevents a retried deletion request from generating another event. Reusing an operation key for a different record or actor is rejected.

The test suite covers invalid transitions, duplicate asset tags, soft deletion, restoration, stale versions, audit export, and repeated operations. It uses Python's standard library and requires no third-party dependencies.

The repository lock serializes in-process mutations. This is useful for a demonstration but does not provide cross-process concurrency control or crash durability. A production implementation should use a database transaction, conditional updates or row locks, and an audit insert in the same transaction.

## JavaScript implementation

The JavaScript service uses private class fields to keep the record map, asset-tag index, audit collection, and idempotency map internal to the service.

The event emitter provides a notification boundary for audit consumers. Consumers receive structured copies of the emitted events, and the service records the event before notifying listeners. An in-memory event emitter is not a durable messaging system: a process failure can lose its state, and a subscriber cannot participate automatically in a database transaction.

The `structuredClone` helper protects internal objects from accidental mutation through returned values. The `Object.freeze` call on the audit event also communicates that the event should not be modified. Freezing is shallow, which is why the event's nested value maps are cloned separately.

The service distinguishes validation errors, missing records, invalid transitions, stale versions, and idempotency conflicts. Its demo verifies that a repeated deletion returns the original event identifier, that restoration preserves the record, and that invalid status changes and stale writes are rejected.

A production JavaScript service should place these rules behind a transactional repository. If events must be published reliably to other services, an outbox table written in the same transaction as the entity update is more dependable than direct in-memory emission.

## C++ case study

The C++ program models an industrial equipment registry where lifecycle changes must remain valid and traceable.

`EquipmentRegistry` owns the entity collection, asset-tag index, and audit sequence. A `MutationResult` returns both the resulting entity and the audit sequence associated with the operation. The status graph uses a map of sets, which makes transition lookup logarithmic in the number of statuses represented by the ordered map and logarithmic in the number of allowed destinations in the selected set.

The program demonstrates creation, approval, activation, soft deletion, restoration, invalid backward transitions, and stale-version rejection. The `history` method filters the append-only event collection by entity identity. The coverage check verifies that each registered entity has a creation event and that the retained sequence increases.

The implementation uses standard containers and domain exceptions, so it compiles with C++17. Its in-memory containers do not provide transactional rollback. If a durable audit write fails after an entity has changed, the operation would be incomplete unless a database transaction or equivalent recovery mechanism coordinates both writes.

The example also demonstrates why the business status should not be changed merely to hide a record. A record's visibility changes while its operational lifecycle remains meaningful.

## Java implementation

The Java program uses an enum for operational states, a second enum for audit actions, and immutable `AuditEntry` records for historical events. The service owns the transition policy and exposes methods for creation, status changes, renaming, deletion, restoration, and lifecycle history.

The `Equipment` domain object validates deletion metadata and version consistency. The transition map explicitly declares valid state changes, while `verifyVersion` rejects stale mutations. The idempotency map links an operation key to the original audit event, so retries can return the recorded outcome without repeating the state change.

The `List` returned by `history` is produced through a stream operation and cannot be used to modify the service's internal audit collection. The record constructor also copies the supplied maps.

The implementation demonstrates domain-level validation and state modeling, not a complete transaction manager. In an enterprise service, repository methods should update the entity and append the audit entry within one database transaction. Database uniqueness constraints remain necessary because Java collections cannot enforce uniqueness across multiple application instances.

## PostgreSQL relational design

### Entity and actor relationships

The schema separates user identity, equipment state, audit history, transition rules, and idempotency records.

`app_users` provides stable actor references. `equipment` stores the current entity representation. `equipment_audit` references both the affected equipment and the actor responsible for the event. `status_transition_rules` defines the permitted state graph. `idempotency_keys` associates a repeated request key with the operation's recorded outcome.

Foreign keys prevent an equipment record from referring to a nonexistent creator or updater. `ON DELETE RESTRICT` avoids removing referenced users or equipment while dependent history exists.

### Constraints and indexes

The schema enforces unique asset tags, non-empty labels, positive versions, valid deletion metadata, and JSON object types for audit payloads. The status-transition trigger prevents unconfigured transitions. The audit triggers record changes in the same transaction as the entity operation.

The active-status index supports queries that filter out deleted equipment and then filter or sort by status and asset tag. The deleted-record index supports recovery and retention queries. The composite audit-history index supports retrieving events for a specific equipment record in event-time order.

Index selection should follow actual query patterns. Indexes consume storage and add write overhead, so production deployments should verify plans and query latency against realistic data volumes.

### Transaction and trigger behavior

The example uses transaction-local PostgreSQL settings to carry actor identity, audit reason, and correlation identifier into the update trigger. The actor identifier should be derived from authenticated server-side context. A client must not be allowed to impersonate another user simply by choosing a setting value.

The SQL trigger inserts audit events for entity creation and supported updates. Unsupported updates fail instead of silently changing data without an expected audit action. The immutable-audit trigger rejects ordinary update and delete statements against historical rows.

Triggers are not a substitute for access control. Table ownership, role permissions, schema permissions, and the application's transaction boundaries determine who can alter the rules or bypass ordinary write paths. A production deployment should also prevent application roles from directly modifying fields that are intended to be service-controlled.

The example is designed for PostgreSQL and uses `JSONB`, enum types, PL/pgSQL, `clock_timestamp()`, transaction-local settings, and identity columns. It recreates a dedicated demo schema, so it should be executed in a disposable learning database rather than a production database.

## Common failure modes and design trade-offs

### Treating the audit log as the current-state store

Reconstructing current state from every historical event can be expensive and sensitive to missing events, event ordering, and schema changes. The current entity table remains the authoritative representation for ordinary reads in this design. Event-sourced architectures are a different design choice and require explicit event versioning, replay rules, and recovery procedures.

### Deleting a row with cascading audit removal

A physical delete combined with `ON DELETE CASCADE` can erase the evidence the audit table was intended to preserve. The schema uses restrictive references to avoid this accidental history loss. Permanent erasure should be a separately authorized and audited retention operation.

### Using a status field for every concern

Combining operational status, visibility, approval, and processing outcome into one enum creates invalid combinations and excessive transitions. Separate attributes or related entities are appropriate when the concepts have independent lifecycles.

### Assuming audit events prove authorization

An event containing an actor identifier proves only that the database recorded that identifier. The application must validate authentication and authorization, and the database should constrain the credentials and operations available to each role.

### Retrying mutations without idempotency

A client may retry after a timeout even though the server completed the operation. Without an idempotency mechanism, retries can create duplicate events or repeated side effects. Operation keys must be unique within the intended scope and associated with a stable request identity and outcome. Reusing a key for different inputs must be rejected rather than silently accepted.

### Restoring without conflict checks

Restoration can violate current uniqueness or business rules, especially if another record has reused an identifier or asset tag. The restore operation must validate all constraints before committing the change.

### Relying on application checks alone

A validation method protects only code paths that invoke it. Database constraints, triggers, conditional updates, foreign keys, and restrictive privileges provide additional protection when several services or operational tools access the same database.

## Production considerations

A production design should define which operations require reasons, who may perform each transition, whether approvals are required, and how restoration conflicts are resolved. It should also define the retention period for deleted entities and audit events, the treatment of sensitive fields in audit payloads, and the permissions available to operators.

Entity mutations and audit writes should be atomic. Optimistic version checks should be part of the database update predicate rather than a separate read followed by an unconditional write. Idempotency records should be persisted and committed with the associated operation when retry safety is required.

Audit data should have a clear trust boundary. Ordinary application roles should not be able to rewrite history, and administrative changes to audit controls should themselves be monitored. Database backups and recovery tests must include both current-state records and their audit history.
