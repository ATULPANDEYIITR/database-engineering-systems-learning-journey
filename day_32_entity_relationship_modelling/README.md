# Entity Relationship Modeling

Entity Relationship Modeling (ERM) is a conceptual method for describing data in terms of **entities**, their **attributes**, and the **relationships** between entity instances. An ER model is created before or alongside physical database design so that the structure of a domain can be reasoned about independently from SQL tables, programming-language classes, or application screens.

This repository uses three implementations to examine the same subject from different technical perspectives:

- The Python implementation builds an ER metamodel, validates it, maps it toward relational tables, generates SQL, creates a Mermaid ER representation, and applies the model to a course-registration service.
- The JavaScript implementation treats the ER model as an event-driven object structure. It demonstrates model mutation events, asynchronous validation before persistence, policy evaluation, cardinality, composite attributes, and associative entities.
- The C++ implementation develops a complete asset-maintenance case study in which work orders, assets, locations, and technicians form a connected domain model. Many-to-many relationships are resolved through explicit associative entities with relationship-specific attributes.

The implementations deliberately distinguish conceptual modeling from physical implementation. An ER model explains what the domain means and how its parts are related. A relational mapping explains how those decisions can be represented in tables.

## The Core ER Model

An ER model normally starts with three questions:

- **What things need independent identity?** These become entity types such as `Student`, `Course`, `Asset`, or `Technician`.
- **What facts describe those things?** These become attributes such as `student_id`, `title`, `serialNumber`, or `skill`.
- **How can instances of those things be connected?** These become relationships such as a department owning courses, a course having offerings, or a work order involving assets.

The distinction between an entity and an attribute is important. A `Course` can have an independent identifier and participate in many relationships, so it is naturally modeled as an entity. A course `title` normally has no independent identity and is therefore an attribute of `Course`.

The distinction is domain-dependent. A value that begins as an attribute can become an entity when it needs its own lifecycle, attributes, relationships, or identity.

## Entities

An entity type represents a class of distinguishable domain objects.

The Python model contains entities including:

- `Student`
- `Instructor`
- `Department`
- `Course`
- `CourseOffering`
- `Enrollment`

The C++ case study uses:

- `Location`
- `Asset`
- `Technician`
- `WorkOrder`
- `WorkOrderAsset`
- `WorkOrderTechnician`

Each entity is represented by an `Entity` structure or class containing its attributes and primary key.

An entity instance is a particular occurrence of an entity type. For example, `Asset` is an entity type while an asset with identifier `AST-100` is an instance.

Entity identity matters because relationships must connect distinguishable instances. Without stable identity, it becomes difficult to state precisely which object participates in a relationship.

## Attributes

Attributes describe properties of entities or, in some cases, relationships.

The implementations distinguish several useful attribute categories.

### Simple attributes

A simple attribute is treated as an indivisible value at the conceptual level.

Examples include:

- `student_id`
- `course_id`
- `credits`
- `serialNumber`
- `capacity`
- `skill`

The Python and JavaScript implementations represent the data type, required status, name, and description of each attribute.

### Composite attributes

A composite attribute can be decomposed into meaningful components.

The Python model defines `Student.name` as a composite attribute with `first_name` and `last_name`.

The C++ model defines `Asset.physicalAddress` as a composite attribute with `building` and `floor`.

Composite attributes are useful when the domain requires the individual components separately. In relational mapping, the leaf attributes can become individual columns.

A composite attribute should not be confused with a structured programming object automatically. ER modeling is concerned with the semantic structure of the data, not merely the syntax used to store it in a programming language.

### Multivalued attributes

A multivalued attribute can have several values for one entity instance.

The Python model gives `Student` a multivalued `phone_numbers` attribute.

A relational table should not normally contain a single column containing values such as `"9876..., 9123..., 9011..."`. That representation makes individual values harder to constrain, search, update, and reference.

The Python relational mapper therefore creates a separate relation for the multivalued attribute. Its conceptual meaning is preserved while the physical representation becomes row-oriented.

### Derived attributes

A derived attribute can be calculated from other stored facts.

The Python model includes `Student.registration_count`, described as a value calculated from enrollment records.

A derived value should not automatically become a stored source-of-truth column. If the number of registrations can be calculated from enrollment records, independently storing the number introduces the possibility that the count and its underlying records disagree.

The distinction is between the **fact from which a value is derived** and the **calculated representation of that fact**.

## Keys and Entity Identity

A key identifies an entity instance.

The implementations explicitly require entities to define primary keys. The model rejects an entity that has no key and rejects an attempt to use a derived attribute as a key.

A primary key can contain one attribute or several attributes.

A single-attribute key is shown by examples such as:

- `Student.student_id`
- `Course.course_id`
- `Asset.assetId`
- `WorkOrder.workOrderId`

A composite key contains multiple attributes. The C++ case study uses:

`WorkOrderAsset(workOrderId, assetId)`

This is meaningful because one association between a work order and an asset should occur only once in that associative entity.

A key is not simply an arbitrary convenient field. A good identifier should remain stable enough for its intended identity role and should not depend on a value that can legitimately change as part of normal business activity.

## Relationships

A relationship represents a meaningful association between entity instances.

The Python university model contains relationships such as:

`Department OFFERS Course`

and:

`Course HAS_OFFERING CourseOffering`

The C++ asset model contains relationships such as:

`Location LOCATED_AT Asset`

and associations involving `WorkOrder`, `Asset`, and `Technician`.

A relationship should have a domain-specific name that communicates the meaning of the connection. A name such as `ASSOCIATED_WITH` often communicates less than a precise name such as `LOCATED_AT`, `TEACHES`, or `HAS_OFFERING`.

Relationships are not merely foreign-key columns. A foreign key is one common relational implementation of a relationship. The conceptual relationship exists before the physical foreign-key representation is selected.

## Cardinality

Cardinality describes how many instances can participate in a relationship.

The implementations represent the minimum and maximum cardinality at each endpoint.

The notation `(0,N)` means that participation is optional and that many related instances are allowed.

The notation `(1,1)` means that participation is mandatory and exactly one related instance is required.

This separates two ideas that are often incorrectly merged:

- **Maximum cardinality** answers how many related instances are allowed.
- **Minimum cardinality** answers whether participation is optional or mandatory.

### One-to-one

A one-to-one relationship has maximum cardinality one at both endpoints.

Conceptually:

`Entity A (0,1) <-> (0,1) Entity B`

or a mandatory variation such as:

`Entity A (1,1) <-> (0,1) Entity B`

The exact minimum values depend on the business domain.

A one-to-one relationship often requires an additional design decision when mapped to a relational schema: which table should contain the foreign key, whether the relationship should be merged into one table, and whether uniqueness must be enforced on the foreign key.

### One-to-many

A one-to-many relationship allows one instance on one side to relate to many instances on the other.

The university model uses a relationship in which a department can own multiple courses while each course belongs to one department.

Conceptually:

`Department (0,N) <-> (1,1) Course`

In a relational design, the foreign key normally belongs on the many side:

`Course.department_id -> Department.department_id`

The foreign key does not mean that the course table conceptually owns the relationship. It is the physical representation selected because each course needs to identify its one parent department.

### Many-to-many

A many-to-many relationship allows multiple instances on both sides.

Students and course offerings provide a natural example. A student can attend multiple offerings, while an offering can contain multiple students.

Directly placing a single foreign key in either entity table cannot represent all pairings. An associative entity or associative relation is therefore introduced.

The Python model resolves this through `Enrollment`.

The C++ model resolves work-order relationships through `WorkOrderAsset` and `WorkOrderTechnician`.

## Participation

Participation describes whether an entity's involvement in a relationship is optional or mandatory.

An endpoint with minimum cardinality `0` represents optional participation.

An endpoint with minimum cardinality `1` represents mandatory participation.

For example, a university department may exist before it has any courses:

`Department (0,N)`

A course, in the chosen model, must belong to a department:

`Course (1,1)`

This distinction has practical consequences. When mapped to a relational schema, a mandatory many-side foreign key may be represented as `NOT NULL`, while optional participation may allow the foreign-key column to be null, depending on the exact relationship and lifecycle rules.

Cardinality and participation should be documented separately because a relationship can be one-to-many while still allowing optional participation on either endpoint.

## Associative Entities

An associative entity resolves a many-to-many relationship into two relationships that can be represented relationally.

The Python model contains:

`Enrollment`

It has its own attributes:

- `enrollment_id`
- `enrolled_on`
- `status`
- `grade`

Those attributes belong to the act of enrollment rather than to `Student` or `CourseOffering`.

The C++ model provides an even clearer example with:

`WorkOrderAsset`

and:

`WorkOrderTechnician`

`WorkOrderTechnician.hoursWorked` belongs to the association between a technician and a work order. It would be semantically incorrect to put one `hoursWorked` value directly on `Technician` because a technician can work different numbers of hours on different work orders.

Likewise, the C++ `WorkOrderAsset.role` belongs to the association because the same asset can have different roles in different work orders.

This is one of the most important practical reasons for introducing associative entities: the relationship itself can carry data.

## Identifying and Non-Identifying Relationships

The C++ case study distinguishes a relationship whose parent identity contributes to the child's identity from one in which the child has its own independent identifier.

`WorkOrderAsset` uses:

`(workOrderId, assetId)`

as its primary key.

The parent identifiers are therefore part of the association's identity.

By contrast, the Python `Enrollment` entity uses:

`enrollment_id`

as its primary key.

The student and offering references identify related records but do not form the enrollment record's declared primary key.

This distinction affects schema design, key propagation, and lifecycle semantics.

## Relationship Attributes

An attribute can describe a relationship rather than either participating entity.

Consider:

`WorkOrderTechnician.hoursWorked`

A technician has many work orders, and a work order has many technicians. The number of hours cannot be determined solely from the technician or solely from the work order.

The value belongs to their specific pairing.

The same principle applies to the Python `Enrollment` attributes `enrolled_on`, `status`, and `grade`. A student's status is not globally an attribute of the student. It is the student's state within a particular course offering.

## Python Implementation

The Python program is structured as an ER modeling engine followed by a university registration application.

### ER metamodel

`Attribute`, `Entity`, `Endpoint`, `Relationship`, and `ERModel` form the conceptual modeling layer.

`Attribute` supports simple, composite, multivalued, and derived forms.

`Entity` stores attributes and validates primary-key definitions.

`Endpoint` stores minimum and maximum cardinality.

`Relationship` connects two endpoints and determines whether the relationship is one-to-one, one-to-many, or many-to-many.

`ERModel` owns the complete model and validates references between entities.

### Relational mapping

`map_er_model_to_sql()` demonstrates how conceptual decisions can be transformed into relational structures.

The mapping includes:

- Entity types become SQL tables.
- Leaf attributes of composite attributes become columns.
- Primary keys become table primary keys.
- One-to-many relationships place the referenced key on the many side.
- Many-to-many relationships become association tables.
- Multivalued attributes become separate relations.
- Relationship attributes are stored in the generated association table.

`generate_sql()` then produces PostgreSQL-compatible DDL.

This is intentionally a mapping demonstration rather than a complete database migration engine. A production schema generator would require additional handling for identifier quoting, naming policies, indexes, unique constraints, check constraints, schema namespaces, cascading behavior, and dialect-specific types.

### Application-level enforcement

`RegistrationService` demonstrates a second layer of rules.

The ER model describes relationships such as Student to Enrollment and CourseOffering to Enrollment. The service then applies operational rules such as:

- a student must exist before enrollment;
- an offering must exist before enrollment;
- an enrollment identifier must be unique;
- a student cannot have two active enrollment records for the same offering;
- an offering cannot exceed its capacity;
- only an active enrollment can be dropped;
- grades are restricted to the accepted set.

This demonstrates an important boundary. ER cardinality does not automatically express every business rule. Capacity, state transitions, and domain-specific validation often require additional constraints or application logic.

The program also writes JSON, SQL, Mermaid, and CSV artifacts into `er_model_output`.

## JavaScript Implementation

The JavaScript implementation uses an event-driven object model.

`Attribute`, `Entity`, `Endpoint`, and `Relationship` provide the modeling primitives, while `ERModel` owns the complete structure.

The model extends `EventTarget`. Whenever an entity or relationship is added, the model emits a `modelchange` event containing the change type, model version, and affected object.

This makes the model observable without hard-coding logging into every operation.

The example domain is an online learning platform with:

- `Learner`
- `Course`
- `Instructor`
- `CourseSession`
- `Attendance`

The `Attendance` entity functions as an association between a learner and a course session. This avoids attempting to store multiple learner identifiers inside one course-session attribute.

The JavaScript version also demonstrates `async` and `await` through `persistModelSnapshot()`. Model validation occurs before the asynchronous persistence boundary. If validation fails, the snapshot is rejected instead of being written.

`ERDesignPolicy` provides a separate policy layer. It checks conditions such as missing primary keys and dangling relationship endpoints.

The separation between the model and policy evaluator is deliberate. A conceptual modeling engine can define structural validity while an organization can apply additional design policies.

## C++ Case Study

The C++ program models maintenance operations for physical assets.

The central entity types are:

`Location`

A physical facility or operational area.

`Asset`

A tracked physical item with a stable identifier, serial number, category, location, and status.

`Technician`

A person qualified to perform maintenance.

`WorkOrder`

A maintenance request or scheduled activity.

`WorkOrderAsset`

An associative entity between work orders and assets.

`WorkOrderTechnician`

An associative entity between work orders and technicians.

The relationship structure includes:

`Location (0,N) <-> (1,1) Asset`

This means a location can contain many assets while each asset is located at one location in the chosen model.

The work-order associations are represented as separate entities because both assets and technicians can participate in multiple work orders.

### Why the associative entities matter

Suppose a work order references three assets and two technicians.

A single `WorkOrder` row cannot naturally contain an arbitrary collection of asset relationships while also maintaining normal referential integrity.

`WorkOrderAsset` instead stores one row per work-order/asset pairing.

The composite primary key:

`(workOrderId, assetId)`

prevents the same asset from being linked to the same work order twice.

`WorkOrderTechnician` uses:

`(workOrderId, technicianId)`

for the same reason.

The model can therefore represent:

`WO-5001 -> AST-100`

and:

`WO-5001 -> AST-200`

without placing multiple identifiers into a single attribute.

### Relationship-specific data

`WorkOrderAsset.role` describes the asset's role in a particular work order.

`WorkOrderTechnician.hoursWorked` describes the technician's effort on a particular work order.

These are not ordinary attributes of the parent entities. Their ownership is determined by the relationship context.

## Relational Mapping

ER modeling and relational modeling are closely connected but not identical.

A common mapping pattern is:

| ER concept | Relational representation |
| --- | --- |
| Entity type | Table |
| Simple attribute | Column |
| Entity primary identifier | Primary key |
| One-to-many relationship | Foreign key on the many side |
| Many-to-many relationship | Associative table |
| Relationship attribute | Column in the association table |
| Multivalued attribute | Separate related table |
| Composite attribute | Usually multiple columns for its components |
| Mandatory participation | Often represented with `NOT NULL` or additional constraints |
| Uniqueness requirement | `UNIQUE` constraint or key |

The exact physical design depends on database requirements. ER modeling should not be reduced to mechanically adding foreign-key columns because some conceptual relationships require additional constraints, indexes, association attributes, or lifecycle rules.

## Integrity Constraints

A useful ER model captures structural rules before implementation.

The implementations validate several forms of integrity.

### Entity integrity

Every modeled entity should have a primary key.

The Python, JavaScript, and C++ implementations all treat missing primary keys as invalid model conditions.

### Referential integrity

A relationship endpoint must reference a known entity.

At the application level, the C++ repository also prevents an association from referencing an unknown asset, work order, location, or technician.

The Python registration service similarly rejects enrollment against unknown students and offerings.

### Domain integrity

Domain values must obey rules appropriate to the application.

Examples include:

- offering capacity must be positive;
- enrollment status must use a defined state set;
- grade values must be recognized;
- technician hours must remain within an acceptable range;
- asset and work-order identifiers cannot be empty.

These rules are different from cardinality. Cardinality describes how entity instances can relate. Domain integrity constrains the values and states of the data.

## Normalization Relationship

ER modeling often precedes normalization because a good conceptual model makes functional dependencies easier to identify.

Consider a work order involving several technicians.

A poor design could store:

`technician_1`, `technician_2`, `technician_3`

inside `WorkOrder`.

That design creates a repeating structure, limits the number of technicians, and makes querying and referential integrity awkward.

An associative entity avoids those problems:

`WorkOrderTechnician(workOrderId, technicianId, hoursWorked)`

Each row represents one relationship occurrence.

The same reasoning applies to student enrollment and work-order assets.

Normalization is not identical to ER modeling, but the two reinforce one another. ER modeling expresses the conceptual structure, while normalization analyzes dependency and redundancy properties of a relational representation.

## Common Modeling Errors

### Treating every noun as an entity

Not every noun in a requirements document deserves an entity.

A value such as `Course.title` may not require independent identity. Creating unnecessary entities can increase joins and complicate the model without adding semantic value.

An entity should generally have a meaningful identity and a reason to exist independently in the domain.

### Treating every relationship as an attribute

A relationship is not equivalent to a text field containing another object's name.

For example, `WorkOrder.assignedTechnicianNames` does not properly model work-order/technician relationships.

It loses referential structure and makes many-to-many relationships difficult to enforce.

### Storing multiple values in one scalar field

Values such as:

`"AST-100, AST-200, AST-300"`

should not be used as a substitute for an association table when the values represent independent related instances.

The C++ `WorkOrderAsset` design demonstrates the relational alternative.

### Confusing cardinality with participation

`1:N` alone does not tell the complete story.

The difference between:

`(0,N)`

and:

`(1,N)`

is operationally important because the first permits zero related instances while the second requires at least one.

### Putting relationship attributes on the wrong entity

`hoursWorked` belongs to the relationship between a technician and a work order.

Putting it on `Technician` would imply that the technician has one global hours-worked value rather than a value that changes for each work order.

### Using unstable values as identifiers

An email address, display name, or physical location can change.

If such a value is used as an identifier, changes can propagate through many relationships.

Stable surrogate or domain identifiers may be preferable when the natural business value is mutable.

## Edge Cases

An ER model needs explicit treatment of unusual cases.

### Empty relationship participation

A department may exist before it has courses. This is represented by minimum cardinality `0`.

### Mandatory parent reference

If every course must belong to a department, the course endpoint uses minimum cardinality `1`.

In a relational implementation this may translate into a non-null foreign key.

### Duplicate associations

An association table can accidentally contain two identical parent pairings.

Composite keys such as `(workOrderId, assetId)` prevent this duplicate relationship occurrence.

### Relationship-specific attributes

If an association has attributes, the association must have a representation capable of owning those attributes.

This is why `WorkOrderTechnician` is modeled explicitly.

### Changing relationships

A relationship can change without changing the identity of the participating entities. For example, an asset can move from one location to another while the asset itself remains the same entity instance.

The model therefore separates `Asset` identity from the `LOCATED_AT` relationship.

### Derived information

A value such as registration count may change whenever enrollment data changes. Treating it as a derived value avoids creating two independent sources of truth.

## Validation and Failure Handling

The implementations reject structurally invalid models rather than silently accepting them.

Examples include:

- an entity without a primary key;
- a primary key referring to a nonexistent attribute;
- a derived attribute used as a key;
- an unknown relationship endpoint;
- invalid minimum or maximum cardinality;
- a composite attribute without children;
- duplicate attributes;
- duplicate entities;
- duplicate association records;
- references to nonexistent domain records.

This behavior is important for tooling. A modeling system that silently accepts an invalid relationship can produce a physically valid-looking schema that represents the wrong domain.

## Performance Considerations

Conceptual ER notation does not prescribe runtime performance.

The physical implementation determines lookup and traversal characteristics.

The C++ case study stores entities in `std::unordered_map`, making identifier lookup expected O(1) on average.

Its association records are stored in vectors. Finding all assets for a work order therefore requires an O(E) scan over the association records.

For a production relational database, indexes on foreign-key columns such as `workOrderId` and `assetId` would make relationship traversal substantially more efficient for large association tables.

The Python implementation similarly uses dictionaries for entity definitions and operational records, while its generated relational design can be further optimized with database indexes.

The important distinction is that ER modeling describes semantic relationships, while indexing is a physical optimization for accessing those relationships.

## Design Boundaries

The examples separate several layers that are often mixed together.

**Conceptual layer**

Defines entities, attributes, keys, relationships, cardinality, and participation.

**Mapping layer**

Transforms conceptual structures into tables, columns, foreign keys, and associative relations.

**Domain layer**

Enforces application-specific rules such as capacity, state transitions, valid grades, or hours worked.

**Storage layer**

Persists the resulting records and indexes.

Keeping these layers distinct makes the model easier to reason about and prevents a single database implementation detail from being mistaken for the underlying business relationship.

## Practical Interpretation

A useful ER model should allow a reader to answer questions directly from the structure.

For the university model:

- Can a course exist without a department? The chosen cardinality says no.
- Can a department have no courses? Yes.
- Can one course have multiple offerings? Yes.
- Can one student attend multiple offerings? Yes.
- Can an offering contain multiple students? Yes.
- Where does an enrollment date belong? To the enrollment association.
- Where does a student's registration count come from? From enrollment data.

For the asset-maintenance model:

- Can a location contain many assets? Yes.
- Does each asset have one location in the chosen model? Yes.
- Can an asset appear in several work orders? Yes.
- Can a work order involve several assets? Yes.
- Can a technician work on several work orders? Yes.
- Can several technicians work on one work order? Yes.
- Where does technician effort belong? To `WorkOrderTechnician`.
- How is duplicate work-order/asset participation prevented? Through the composite association key.

These questions demonstrate why an ER model is more than a diagram. It is a formal representation of domain structure and constraints.

## Implementation Relationship

The three programs intentionally use different perspectives.

The Python implementation emphasizes **model construction and relational transformation**. It is useful for understanding how ER concepts can be represented as data structures and converted toward SQL.

The JavaScript implementation emphasizes **observable model state and application workflow**. `EventTarget` makes model changes visible, while asynchronous persistence demonstrates a validation boundary before a snapshot is accepted.

The C++ implementation emphasizes **a concrete domain system**. Its asset-maintenance repository shows how associative entities, composite keys, referential integrity, relationship-specific attributes, and relationship traversal interact in a realistic system.

The conceptual principles remain the same even though the implementation techniques differ.

## Limitations

These implementations are educational modeling engines rather than complete database design products.

They do not attempt to cover every ER notation variant, every database dialect, advanced inheritance strategies, temporal modeling, distributed consistency, full schema migration, transaction isolation, or vendor-specific constraint behavior.

Cardinality and participation are represented explicitly, but production database enforcement may require additional unique constraints, foreign-key actions, triggers, checks, indexes, or transaction boundaries.

The generated SQL also represents a mapping strategy rather than a universally correct physical schema for every database engine.

The value of the examples lies in making the conceptual relationships explicit and then showing how those relationships can be translated into executable structures.
