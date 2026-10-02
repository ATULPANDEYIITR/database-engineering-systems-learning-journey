'use strict';

/**
 * Entity Relationship Modeling
 * ----------------------------
 * JavaScript-specific implementation of an ER modeling engine.
 *
 * This file focuses on an event-driven model workflow:
 * - entity and attribute definitions
 * - cardinality and participation
 * - relationship creation
 * - associative entities
 * - model validation
 * - change events
 * - policy checks
 * - asynchronous persistence simulation
 *
 * It is executable with Node.js without npm dependencies.
 */

// ---------------------------------------------------------------------------
// ER primitives
// ---------------------------------------------------------------------------

const AttributeKind = Object.freeze({
    SIMPLE: 'simple',
    COMPOSITE: 'composite',
    MULTIVALUED: 'multivalued',
    DERIVED: 'derived'
});

class Attribute {
    constructor(name, dataType, {
        kind = AttributeKind.SIMPLE,
        required = false,
        children = [],
        description = ''
    } = {}) {
        this.name = name;
        this.dataType = dataType;
        this.kind = kind;
        this.required = required;
        this.children = [...children];
        this.description = description;
    }

    validate() {
        if (!this.name.trim()) {
            throw new Error('Attribute name cannot be empty.');
        }

        if (this.kind === AttributeKind.COMPOSITE && this.children.length === 0) {
            throw new Error(
                `Composite attribute '${this.name}' requires child attributes.`
            );
        }

        if (this.kind !== AttributeKind.COMPOSITE && this.children.length > 0) {
            throw new Error(
                `Only composite attributes may contain children: ${this.name}`
            );
        }

        for (const child of this.children) {
            child.validate();
        }
    }

    leafAttributes() {
        this.validate();

        if (this.kind !== AttributeKind.COMPOSITE) {
            return [this];
        }

        return this.children.flatMap(child => child.leafAttributes());
    }
}

class Entity {
    constructor(name, description = '') {
        this.name = name;
        this.description = description;
        this.attributes = new Map();
        this.primaryKey = [];
    }

    addAttribute(attribute) {
        attribute.validate();

        if (this.attributes.has(attribute.name)) {
            throw new Error(
                `Entity '${this.name}' already has attribute '${attribute.name}'.`
            );
        }

        this.attributes.set(attribute.name, attribute);
        return this;
    }

    setPrimaryKey(...names) {
        if (names.length === 0) {
            throw new Error(`Entity '${this.name}' requires a primary key.`);
        }

        for (const name of names) {
            if (!this.attributes.has(name)) {
                throw new Error(
                    `Cannot use missing attribute '${name}' as a primary key.`
                );
            }

            if (this.attributes.get(name).kind === AttributeKind.DERIVED) {
                throw new Error(
                    `Derived attribute '${name}' cannot be a primary key.`
                );
            }
        }

        this.primaryKey = [...names];
        return this;
    }

    validate() {
        const errors = [];

        if (!this.name.trim()) {
            errors.push('Entity name is empty.');
        }

        if (this.attributes.size === 0) {
            errors.push(`Entity '${this.name}' has no attributes.`);
        }

        if (this.primaryKey.length === 0) {
            errors.push(`Entity '${this.name}' has no primary key.`);
        }

        for (const attribute of this.attributes.values()) {
            try {
                attribute.validate();
            } catch (error) {
                errors.push(error.message);
            }
        }

        return errors;
    }
}

class Endpoint {
    constructor(entity, minimum, maximum) {
        this.entity = entity;
        this.minimum = minimum;
        this.maximum = maximum;
    }

    validate() {
        if (![0, 1].includes(this.minimum)) {
            throw new Error('Minimum ER cardinality must be 0 or 1.');
        }

        if (this.maximum !== null && this.maximum < 1) {
            throw new Error('Maximum cardinality must be positive or null.');
        }

        if (
            this.maximum !== null &&
            this.minimum > this.maximum
        ) {
            throw new Error('Minimum cardinality cannot exceed maximum.');
        }
    }

    get optional() {
        return this.minimum === 0;
    }

    get many() {
        return this.maximum === null;
    }

    notation() {
        const max = this.maximum === null ? 'N' : String(this.maximum);
        return `(${this.minimum},${max})`;
    }
}

class Relationship {
    constructor(
        name,
        left,
        right,
        {
            description = '',
            attributes = []
        } = {}
    ) {
        this.name = name;
        this.left = left;
        this.right = right;
        this.description = description;
        this.attributes = [...attributes];
    }

    validate(entityNames) {
        const errors = [];

        if (!this.name.trim()) {
            errors.push('Relationship name is empty.');
        }

        try {
            this.left.validate();
            this.right.validate();
        } catch (error) {
            errors.push(error.message);
        }

        if (!entityNames.has(this.left.entity)) {
            errors.push(
                `Relationship '${this.name}' references unknown entity '${this.left.entity}'.`
            );
        }

        if (!entityNames.has(this.right.entity)) {
            errors.push(
                `Relationship '${this.name}' references unknown entity '${this.right.entity}'.`
            );
        }

        for (const attribute of this.attributes) {
            try {
                attribute.validate();
            } catch (error) {
                errors.push(error.message);
            }
        }

        return errors;
    }

    get type() {
        const leftMany = this.left.maximum === null;
        const rightMany = this.right.maximum === null;

        if (leftMany && rightMany) return 'many-to-many';
        if (leftMany || rightMany) return 'one-to-many';
        return 'one-to-one';
    }
}

// ---------------------------------------------------------------------------
// Event-driven ER model
// ---------------------------------------------------------------------------

class ERModel extends EventTarget {
    constructor(name) {
        super();
        this.name = name;
        this.entities = new Map();
        this.relationships = [];
        this.version = 0;
    }

    emitChange(type, payload) {
        this.version += 1;

        this.dispatchEvent(
            new CustomEvent('modelchange', {
                detail: {
                    type,
                    version: this.version,
                    payload
                }
            })
        );
    }

    addEntity(entity) {
        if (this.entities.has(entity.name)) {
            throw new Error(`Duplicate entity '${entity.name}'.`);
        }

        this.entities.set(entity.name, entity);
        this.emitChange('entity-added', { entity: entity.name });
        return entity;
    }

    addRelationship(relationship) {
        const errors = relationship.validate(
            new Set(this.entities.keys())
        );

        if (errors.length > 0) {
            throw new Error(errors.join(' '));
        }

        this.relationships.push(relationship);
        this.emitChange(
            'relationship-added',
            {
                relationship: relationship.name,
                type: relationship.type
            }
        );

        return relationship;
    }

    relationshipsFor(entityName) {
        return this.relationships.filter(
            relationship =>
                relationship.left.entity === entityName ||
                relationship.right.entity === entityName
        );
    }

    validate() {
        const errors = [];

        for (const entity of this.entities.values()) {
            errors.push(...entity.validate());
        }

        const names = new Set(this.entities.keys());

        for (const relationship of this.relationships) {
            errors.push(...relationship.validate(names));
        }

        return errors;
    }

    describe() {
        return {
            model: this.name,
            version: this.version,
            entities: [...this.entities.values()].map(entity => ({
                name: entity.name,
                primaryKey: entity.primaryKey,
                attributes: [...entity.attributes.values()].map(attribute => ({
                    name: attribute.name,
                    dataType: attribute.dataType,
                    kind: attribute.kind,
                    required: attribute.required
                }))
            })),
            relationships: this.relationships.map(relationship => ({
                name: relationship.name,
                type: relationship.type,
                left: {
                    entity: relationship.left.entity,
                    cardinality: relationship.left.notation()
                },
                right: {
                    entity: relationship.right.entity,
                    cardinality: relationship.right.notation()
                }
            }))
        };
    }
}

// ---------------------------------------------------------------------------
// JavaScript-specific event and asynchronous behavior
// ---------------------------------------------------------------------------

function attachAuditLogger(model) {
    model.addEventListener('modelchange', event => {
        const { type, version, payload } = event.detail;

        console.log(
            `[MODEL EVENT] v${version} ${type}`,
            JSON.stringify(payload)
        );
    });
}

function delay(milliseconds) {
    return new Promise(resolve => setTimeout(resolve, milliseconds));
}

async function persistModelSnapshot(model) {
    /*
     * This simulates an asynchronous repository write. The important
     * JavaScript behavior is that model validation happens before the
     * asynchronous boundary, preventing invalid state from being persisted.
     */
    const errors = model.validate();

    if (errors.length > 0) {
        throw new Error(
            `Model cannot be persisted:\n${errors.join('\n')}`
        );
    }

    await delay(40);

    return JSON.stringify(model.describe(), null, 2);
}

// ---------------------------------------------------------------------------
// Domain model: online learning platform
// ---------------------------------------------------------------------------

function buildLearningPlatformModel() {
    const model = new ERModel('Online Learning Platform');

    const learner = new Entity(
        'Learner',
        'A person enrolled in one or more learning paths.'
    );

    learner
        .addAttribute(
            new Attribute('learnerId', 'string', {
                required: true,
                description: 'Stable learner identifier'
            })
        )
        .addAttribute(
            new Attribute('email', 'string', {
                required: true,
                description: 'Unique contact address'
            })
        )
        .addAttribute(
            new Attribute('name', 'string', {
                kind: AttributeKind.COMPOSITE,
                children: [
                    new Attribute('firstName', 'string', {
                        required: true
                    }),
                    new Attribute('lastName', 'string', {
                        required: true
                    })
                ]
            })
        )
        .setPrimaryKey('learnerId');

    model.addEntity(learner);

    const course = new Entity(
        'Course',
        'Reusable course definition.'
    );

    course
        .addAttribute(
            new Attribute('courseId', 'string', {
                required: true
            })
        )
        .addAttribute(
            new Attribute('title', 'string', {
                required: true
            })
        )
        .addAttribute(
            new Attribute('durationHours', 'integer', {
                required: true
            })
        )
        .setPrimaryKey('courseId');

    model.addEntity(course);

    const instructor = new Entity(
        'Instructor',
        'Person responsible for course delivery.'
    );

    instructor
        .addAttribute(
            new Attribute('instructorId', 'string', {
                required: true
            })
        )
        .addAttribute(
            new Attribute('displayName', 'string', {
                required: true
            })
        )
        .setPrimaryKey('instructorId');

    model.addEntity(instructor);

    const session = new Entity(
        'CourseSession',
        'A scheduled delivery of a course.'
    );

    session
        .addAttribute(
            new Attribute('sessionId', 'string', {
                required: true
            })
        )
        .addAttribute(
            new Attribute('startsAt', 'datetime', {
                required: true
            })
        )
        .addAttribute(
            new Attribute('capacity', 'integer', {
                required: true
            })
        )
        .setPrimaryKey('sessionId');

    model.addEntity(session);

    const attendance = new Entity(
        'Attendance',
        'Associative entity between learner and course session.'
    );

    attendance
        .addAttribute(
            new Attribute('attendanceId', 'string', {
                required: true
            })
        )
        .addAttribute(
            new Attribute('recordedAt', 'datetime', {
                required: true
            })
        )
        .addAttribute(
            new Attribute('state', 'string', {
                required: true
            })
        )
        .setPrimaryKey('attendanceId');

    model.addEntity(attendance);

    model.addRelationship(
        new Relationship(
            'DELIVERS',
            new Endpoint('Instructor', 0, null),
            new Endpoint('CourseSession', 1, null),
            {
                description:
                    'An instructor may deliver multiple sessions; each session requires teaching coverage.'
            }
        )
    );

    model.addRelationship(
        new Relationship(
            'SCHEDULES',
            new Endpoint('Course', 0, null),
            new Endpoint('CourseSession', 1, 1),
            {
                description:
                    'A reusable course can have multiple scheduled sessions.'
            }
        )
    );

    model.addRelationship(
        new Relationship(
            'HAS_ATTENDANCE',
            new Endpoint('CourseSession', 0, null),
            new Endpoint('Attendance', 1, 1)
        )
    );

    model.addRelationship(
        new Relationship(
            'LEARNER_ATTENDANCE',
            new Endpoint('Learner', 0, null),
            new Endpoint('Attendance', 1, 1)
        )
    );

    return model;
}

// ---------------------------------------------------------------------------
// Policy evaluator
// ---------------------------------------------------------------------------

class ERDesignPolicy {
    constructor({
        requirePrimaryKeys = true,
        rejectDanglingRelationships = true,
        rejectDerivedKeys = true,
        requireNamedRelationships = true
    } = {}) {
        this.requirePrimaryKeys = requirePrimaryKeys;
        this.rejectDanglingRelationships = rejectDanglingRelationships;
        this.rejectDerivedKeys = rejectDerivedKeys;
        this.requireNamedRelationships = requireNamedRelationships;
    }

    evaluate(model) {
        const findings = [];

        for (const entity of model.entities.values()) {
            if (
                this.requirePrimaryKeys &&
                entity.primaryKey.length === 0
            ) {
                findings.push({
                    severity: 'error',
                    entity: entity.name,
                    message: 'Entity has no primary key.'
                });
            }

            if (this.rejectDerivedKeys) {
                for (const key of entity.primaryKey) {
                    const attribute = entity.attributes.get(key);

                    if (
                        attribute &&
                        attribute.kind === AttributeKind.DERIVED
                    ) {
                        findings.push({
                            severity: 'error',
                            entity: entity.name,
                            message:
                                `Derived attribute '${key}' is used as a key.`
                        });
                    }
                }
            }
        }

        const entityNames = new Set(model.entities.keys());

        for (const relationship of model.relationships) {
            if (
                this.requireNamedRelationships &&
                relationship.name.trim().length === 0
            ) {
                findings.push({
                    severity: 'error',
                    relationship: relationship.name,
                    message: 'Relationship requires a meaningful name.'
                });
            }

            if (this.rejectDanglingRelationships) {
                for (const endpoint of [
                    relationship.left,
                    relationship.right
                ]) {
                    if (!entityNames.has(endpoint.entity)) {
                        findings.push({
                            severity: 'error',
                            relationship: relationship.name,
                            message:
                                `Endpoint references missing entity '${endpoint.entity}'.`
                        });
                    }
                }
            }
        }

        return findings;
    }
}

// ---------------------------------------------------------------------------
// Demonstrations
// ---------------------------------------------------------------------------

function demonstrateCardinality(model) {
    console.log('\nRELATIONSHIP CARDINALITY');

    for (const relationship of model.relationships) {
        console.log(
            `${relationship.name}: ` +
            `${relationship.left.entity} ${relationship.left.notation()} ` +
            `<-> ` +
            `${relationship.right.entity} ${relationship.right.notation()} ` +
            `[${relationship.type}]`
        );
    }

    console.log(
        '\nCardinality answers how many instances can participate; ' +
        'participation answers whether participation is optional or mandatory.'
    );
}

function demonstrateCompositeAndDerivedAttributes() {
    console.log('\nATTRIBUTE TYPES');

    const address = new Attribute('address', 'object', {
        kind: AttributeKind.COMPOSITE,
        children: [
            new Attribute('street', 'string', { required: true }),
            new Attribute('city', 'string', { required: true }),
            new Attribute('postalCode', 'string', { required: true })
        ]
    });

    console.log(
        'Composite attribute leaves:',
        address.leafAttributes().map(attribute => attribute.name)
    );

    const accountBalance = new Attribute(
        'balance',
        'decimal',
        {
            kind: AttributeKind.DERIVED,
            description: 'Calculated from ledger transactions'
        }
    );

    console.log(
        'Derived attribute:',
        accountBalance.name,
        'is stored conceptually as a derivation, not as the source of truth.'
    );
}

function demonstrateInvalidModel() {
    console.log('\nINVALID MODEL HANDLING');

    const model = new ERModel('Invalid Example');
    const employee = new Entity('Employee');

    employee.addAttribute(
        new Attribute('employeeId', 'string', {
            required: true
        })
    );

    model.addEntity(employee);

    try {
        model.addRelationship(
            new Relationship(
                'ASSIGNED_TO',
                new Endpoint('Employee', 1, 1),
                new Endpoint('DepartmentThatDoesNotExist', 0, null)
            )
        );
    } catch (error) {
        console.log('Rejected dangling relationship:', error.message);
    }

    try {
        employee.setPrimaryKey('missingId');
    } catch (error) {
        console.log('Rejected invalid key:', error.message);
    }
}

async function main() {
    console.log('='.repeat(78));
    console.log('ENTITY RELATIONSHIP MODELING');
    console.log('='.repeat(78));

    const model = buildLearningPlatformModel();
    attachAuditLogger(model);

    demonstrateCardinality(model);
    demonstrateCompositeAndDerivedAttributes();

    const policy = new ERDesignPolicy();
    const findings = policy.evaluate(model);

    console.log('\nMODEL POLICY');
    if (findings.length === 0) {
        console.log('No policy violations detected.');
    } else {
        console.table(findings);
    }

    console.log('\nMODEL DESCRIPTION');
    console.log(JSON.stringify(model.describe(), null, 2));

    console.log('\nASYNC SNAPSHOT');
    try {
        const snapshot = await persistModelSnapshot(model);
        console.log(snapshot);
    } catch (error) {
        console.error('Persistence failed:', error.message);
    }

    demonstrateInvalidModel();

    console.log('\nJAVASCRIPT-SPECIFIC DESIGN NOTE');
    console.log(
        'EventTarget makes model changes observable, while async persistence ' +
        'creates an explicit validation boundary before a snapshot is stored.'
    );
}

main().catch(error => {
    console.error('Fatal model-processing error:', error.message);
    process.exitCode = 1;
});
