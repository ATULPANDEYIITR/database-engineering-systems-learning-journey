'use strict';

/*
 * Database Design Principles
 * Logical vs. physical design, design objectives
 *
 * This Node.js program models an academic enrollment database from a
 * different perspective than the Python implementation:
 *
 * - logical entities are represented as immutable definitions;
 * - physical indexes are evaluated against an event-driven workload;
 * - schema policy changes emit events;
 * - query observations are used to detect missing access paths;
 * - a policy evaluator separates correctness requirements from performance
 *   decisions.
 *
 * Runtime: Node.js 18+ or another modern JavaScript runtime supporting
 * classes, private fields, Map, Set, and async/await.
 */


// ---------------------------------------------------------------------------
// Logical model
// ---------------------------------------------------------------------------

class Attribute {
    constructor(name, dataType, { nullable = false, description = '' } = {}) {
        this.name = name;
        this.dataType = dataType;
        this.nullable = nullable;
        this.description = description;
        Object.freeze(this);
    }
}


class ForeignKey {
    constructor(columns, referencedTable, referencedColumns, onDelete = 'RESTRICT') {
        this.columns = Object.freeze([...columns]);
        this.referencedTable = referencedTable;
        this.referencedColumns = Object.freeze([...referencedColumns]);
        this.onDelete = onDelete;
        Object.freeze(this);
    }
}


class LogicalTable {
    constructor(name, attributes, primaryKey, candidateKeys = [], foreignKeys = []) {
        this.name = name;
        this.attributes = Object.freeze([...attributes]);
        this.primaryKey = Object.freeze([...primaryKey]);
        this.candidateKeys = Object.freeze(candidateKeys.map(key => Object.freeze([...key])));
        this.foreignKeys = Object.freeze([...foreignKeys]);
        Object.freeze(this);
    }

    attributeNames() {
        return new Set(this.attributes.map(attribute => attribute.name));
    }

    validate() {
        const errors = [];
        const names = this.attributes.map(attribute => attribute.name);
        const uniqueNames = new Set(names);

        if (names.length !== uniqueNames.size) {
            errors.push(`${this.name}: duplicate attribute name`);
        }

        if (this.primaryKey.length === 0) {
            errors.push(`${this.name}: missing primary key`);
        }

        const attributes = this.attributeNames();

        for (const column of this.primaryKey) {
            if (!attributes.has(column)) {
                errors.push(`${this.name}: primary-key column ${column} does not exist`);
            }
        }

        for (const key of this.candidateKeys) {
            for (const column of key) {
                if (!attributes.has(column)) {
                    errors.push(`${this.name}: candidate-key column ${column} does not exist`);
                }
            }
        }

        for (const foreignKey of this.foreignKeys) {
            if (foreignKey.columns.length !== foreignKey.referencedColumns.length) {
                errors.push(`${this.name}: foreign-key column counts differ`);
            }

            for (const column of foreignKey.columns) {
                if (!attributes.has(column)) {
                    errors.push(`${this.name}: foreign-key column ${column} does not exist`);
                }
            }
        }

        return errors;
    }
}


class LogicalSchema {
    constructor(tables) {
        this.tables = new Map(tables.map(table => [table.name, table]));
    }

    validate() {
        const errors = [];

        for (const table of this.tables.values()) {
            errors.push(...table.validate());

            for (const foreignKey of table.foreignKeys) {
                const referenced = this.tables.get(foreignKey.referencedTable);

                if (!referenced) {
                    errors.push(
                        `${table.name}: references missing table ${foreignKey.referencedTable}`
                    );
                    continue;
                }

                const referencedKey = referenced.primaryKey;

                if (
                    referencedKey.length !== foreignKey.referencedColumns.length ||
                    !referencedKey.every(
                        (column, index) =>
                            column === foreignKey.referencedColumns[index]
                    )
                ) {
                    errors.push(
                        `${table.name}: foreign key does not reference the declared primary key`
                    );
                }
            }
        }

        return errors;
    }
}


function buildLogicalSchema() {
    const student = new LogicalTable(
        'student',
        [
            new Attribute('student_id', 'INTEGER'),
            new Attribute('student_number', 'VARCHAR(20)'),
            new Attribute('full_name', 'VARCHAR(120)'),
            new Attribute('email', 'VARCHAR(254)'),
            new Attribute('birth_date', 'DATE', { nullable: true })
        ],
        ['student_id'],
        [['student_number'], ['email']]
    );

    const course = new LogicalTable(
        'course',
        [
            new Attribute('course_id', 'INTEGER'),
            new Attribute('course_code', 'VARCHAR(20)'),
            new Attribute('course_name', 'VARCHAR(160)'),
            new Attribute('credit_hours', 'SMALLINT')
        ],
        ['course_id'],
        [['course_code']]
    );

    const instructor = new LogicalTable(
        'instructor',
        [
            new Attribute('instructor_id', 'INTEGER'),
            new Attribute('employee_number', 'VARCHAR(20)'),
            new Attribute('full_name', 'VARCHAR(120)'),
            new Attribute('email', 'VARCHAR(254)')
        ],
        ['instructor_id'],
        [['employee_number'], ['email']]
    );

    const term = new LogicalTable(
        'academic_term',
        [
            new Attribute('term_id', 'INTEGER'),
            new Attribute('term_code', 'VARCHAR(20)'),
            new Attribute('start_date', 'DATE'),
            new Attribute('end_date', 'DATE')
        ],
        ['term_id'],
        [['term_code']]
    );

    const section = new LogicalTable(
        'course_section',
        [
            new Attribute('section_id', 'INTEGER'),
            new Attribute('course_id', 'INTEGER'),
            new Attribute('instructor_id', 'INTEGER'),
            new Attribute('term_id', 'INTEGER'),
            new Attribute('room_code', 'VARCHAR(30)'),
            new Attribute('capacity', 'INTEGER')
        ],
        ['section_id'],
        [['course_id', 'term_id', 'instructor_id', 'room_code']],
        [
            new ForeignKey(['course_id'], 'course', ['course_id']),
            new ForeignKey(['instructor_id'], 'instructor', ['instructor_id']),
            new ForeignKey(['term_id'], 'academic_term', ['term_id'])
        ]
    );

    const enrollment = new LogicalTable(
        'enrollment',
        [
            new Attribute('student_id', 'INTEGER'),
            new Attribute('section_id', 'INTEGER'),
            new Attribute('enrolled_on', 'DATE'),
            new Attribute('grade', 'VARCHAR(2)', { nullable: true })
        ],
        ['student_id', 'section_id'],
        [],
        [
            new ForeignKey(['student_id'], 'student', ['student_id']),
            new ForeignKey(['section_id'], 'course_section', ['section_id'])
        ]
    );

    return new LogicalSchema([
        student,
        course,
        instructor,
        term,
        section,
        enrollment
    ]);
}


// ---------------------------------------------------------------------------
// Physical design
// ---------------------------------------------------------------------------

class IndexDefinition {
    constructor({
        name,
        table,
        columns,
        unique = false,
        coveringColumns = []
    }) {
        this.name = name;
        this.table = table;
        this.columns = Object.freeze([...columns]);
        this.unique = unique;
        this.coveringColumns = Object.freeze([...coveringColumns]);
        Object.freeze(this);
    }

    canSupport(predicates) {
        /*
         * B-tree indexes are most useful when the query predicates use a
         * leftmost prefix of the indexed columns. This simplified evaluator
         * models that principle without pretending to be a database optimizer.
         */
        const predicateSet = new Set(predicates);

        return this.columns.length > 0 &&
            predicateSet.has(this.columns[0]);
    }
}


class PhysicalDesign {
    constructor(indexes, partitioning) {
        this.indexes = Object.freeze([...indexes]);
        this.partitioning = new Map(Object.entries(partitioning));
    }

    indexesFor(table) {
        return this.indexes.filter(index => index.table === table);
    }

    candidateIndexes(table, predicates) {
        return this.indexesFor(table).filter(index => index.canSupport(predicates));
    }
}


function buildPhysicalDesign() {
    return new PhysicalDesign(
        [
            new IndexDefinition({
                name: 'ux_student_email',
                table: 'student',
                columns: ['email'],
                unique: true
            }),
            new IndexDefinition({
                name: 'ux_student_student_number',
                table: 'student',
                columns: ['student_number'],
                unique: true
            }),
            new IndexDefinition({
                name: 'ix_section_term_course',
                table: 'course_section',
                columns: ['term_id', 'course_id']
            }),
            new IndexDefinition({
                name: 'ix_enrollment_student_section',
                table: 'enrollment',
                columns: ['student_id', 'section_id']
            }),
            new IndexDefinition({
                name: 'ix_enrollment_section_student',
                table: 'enrollment',
                columns: ['section_id', 'student_id']
            })
        ],
        {
            enrollment: 'Range by academic term after workload and partition-maintenance analysis',
            course_section: 'Range by academic term only if section volume justifies partitioning'
        }
    );
}


// ---------------------------------------------------------------------------
// Event-driven workload observation
// ---------------------------------------------------------------------------

class WorkloadMonitor {
    #events = [];

    recordQuery({ name, table, predicates, rowsExamined, rowsReturned, durationMs }) {
        if (rowsExamined < rowsReturned) {
            throw new RangeError(
                `${name}: rowsExamined cannot be lower than rowsReturned`
            );
        }

        if (durationMs < 0) {
            throw new RangeError(`${name}: duration cannot be negative`);
        }

        this.#events.push(Object.freeze({
            type: 'query',
            timestamp: new Date().toISOString(),
            name,
            table,
            predicates: [...predicates],
            rowsExamined,
            rowsReturned,
            durationMs
        }));
    }

    get events() {
        return [...this.#events];
    }

    selectivityFor(event) {
        if (event.rowsExamined === 0) {
            return 0;
        }

        return event.rowsReturned / event.rowsExamined;
    }

    identifyPotentialProblems() {
        return this.#events.filter(event =>
            event.type === 'query' &&
            event.rowsExamined >= 100_000 &&
            event.rowsReturned <= event.rowsExamined * 0.01
        );
    }
}


class SchemaEventBus {
    #handlers = new Map();

    on(eventType, handler) {
        if (!this.#handlers.has(eventType)) {
            this.#handlers.set(eventType, []);
        }

        this.#handlers.get(eventType).push(handler);
    }

    emit(eventType, payload) {
        const handlers = this.#handlers.get(eventType) || [];

        for (const handler of handlers) {
            handler(payload);
        }
    }
}


// ---------------------------------------------------------------------------
// Policy evaluation
// ---------------------------------------------------------------------------

class DesignPolicy {
    constructor({
        maxUnindexedHighFrequencyQueries = 0,
        requireForeignKeys = true,
        requireCandidateKeyForNaturalIdentifiers = true
    } = {}) {
        this.maxUnindexedHighFrequencyQueries =
            maxUnindexedHighFrequencyQueries;
        this.requireForeignKeys = requireForeignKeys;
        this.requireCandidateKeyForNaturalIdentifiers =
            requireCandidateKeyForNaturalIdentifiers;
    }

    evaluate(schema, physicalDesign, workload) {
        const findings = [];

        if (this.requireForeignKeys) {
            for (const table of schema.tables.values()) {
                for (const foreignKey of table.foreignKeys) {
                    if (!schema.tables.has(foreignKey.referencedTable)) {
                        findings.push({
                            severity: 'error',
                            message:
                                `${table.name} has a foreign key to a missing table`
                        });
                    }
                }
            }
        }

        for (const query of workload) {
            if (query.frequencyPerDay < 1000) {
                continue;
            }

            const supported = physicalDesign.candidateIndexes(
                query.table,
                query.predicates
            );

            if (supported.length === 0) {
                findings.push({
                    severity: 'warning',
                    message:
                        `${query.name} is frequent but has no modeled supporting index`
                });
            }
        }

        return findings;
    }
}


// ---------------------------------------------------------------------------
// In-memory logical data model
// ---------------------------------------------------------------------------

class EnrollmentRepository {
    #students = new Map();
    #sections = new Map();
    #enrollments = new Map();

    addStudent(student) {
        if (!Number.isInteger(student.studentId) || student.studentId <= 0) {
            throw new Error('studentId must be a positive integer');
        }

        if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(student.email)) {
            throw new Error('student email is invalid');
        }

        if (this.#students.has(student.studentId)) {
            throw new Error('student primary key already exists');
        }

        for (const existing of this.#students.values()) {
            if (existing.email === student.email) {
                throw new Error('student email must be unique');
            }
            if (existing.studentNumber === student.studentNumber) {
                throw new Error('student number must be unique');
            }
        }

        this.#students.set(student.studentId, Object.freeze({ ...student }));
    }

    addSection(section) {
        if (section.capacity <= 0) {
            throw new Error('section capacity must be positive');
        }

        if (this.#sections.has(section.sectionId)) {
            throw new Error('section primary key already exists');
        }

        this.#sections.set(section.sectionId, Object.freeze({ ...section }));
    }

    enrollmentKey(studentId, sectionId) {
        return `${studentId}:${sectionId}`;
    }

    enroll(studentId, sectionId, enrolledOn) {
        if (!this.#students.has(studentId)) {
            throw new Error('student foreign key does not exist');
        }

        const section = this.#sections.get(sectionId);

        if (!section) {
            throw new Error('section foreign key does not exist');
        }

        const key = this.enrollmentKey(studentId, sectionId);

        if (this.#enrollments.has(key)) {
            throw new Error('duplicate enrollment');
        }

        const enrolledCount = [...this.#enrollments.values()]
            .filter(row => row.sectionId === sectionId)
            .length;

        if (enrolledCount >= section.capacity) {
            throw new Error('section capacity exceeded');
        }

        this.#enrollments.set(
            key,
            {
                studentId,
                sectionId,
                enrolledOn,
                grade: null
            }
        );
    }

    assignGrade(studentId, sectionId, grade) {
        const allowed = new Set(['A+', 'A', 'B+', 'B', 'C+', 'C', 'D', 'F', 'I']);
        const key = this.enrollmentKey(studentId, sectionId);

        if (!allowed.has(grade)) {
            throw new Error(`invalid grade: ${grade}`);
        }

        const enrollment = this.#enrollments.get(key);

        if (!enrollment) {
            throw new Error('cannot assign a grade to a missing enrollment');
        }

        enrollment.grade = grade;
    }

    snapshot() {
        return {
            students: [...this.#students.entries()],
            sections: [...this.#sections.entries()],
            enrollments: [...this.#enrollments.entries()]
        };
    }

    restore(snapshot) {
        this.#students = new Map(snapshot.students);
        this.#sections = new Map(snapshot.sections);
        this.#enrollments = new Map(snapshot.enrollments);
    }

    countEnrollments() {
        return this.#enrollments.size;
    }
}


// ---------------------------------------------------------------------------
// Async transaction-like workflow
// ---------------------------------------------------------------------------

async function executeEnrollmentTransaction(repository, requests) {
    /*
     * JavaScript applications often perform database operations through
     * asynchronous APIs. A real transaction must be created by the database
     * client; this snapshot is only an educational atomicity model.
     */
    const snapshot = repository.snapshot();

    try {
        for (const request of requests) {
            await Promise.resolve();

            repository.enroll(
                request.studentId,
                request.sectionId,
                request.enrolledOn
            );
        }

        return {
            committed: true,
            count: repository.countEnrollments()
        };
    } catch (error) {
        repository.restore(snapshot);

        return {
            committed: false,
            error: error.message,
            count: repository.countEnrollments()
        };
    }
}


// ---------------------------------------------------------------------------
// Query workload
// ---------------------------------------------------------------------------

function runWorkloadMonitor(physicalDesign) {
    const monitor = new WorkloadMonitor();

    monitor.recordQuery({
        name: 'Student transcript lookup',
        table: 'enrollment',
        predicates: ['student_id'],
        rowsExamined: 2_000_000,
        rowsReturned: 42,
        durationMs: 6.2
    });

    monitor.recordQuery({
        name: 'Section roster lookup',
        table: 'enrollment',
        predicates: ['section_id'],
        rowsExamined: 2_000_000,
        rowsReturned: 80,
        durationMs: 7.1
    });

    monitor.recordQuery({
        name: 'Room-only administrative lookup',
        table: 'course_section',
        predicates: ['room_code'],
        rowsExamined: 30_000,
        rowsReturned: 8_000,
        durationMs: 29.4
    });

    console.log('\nWORKLOAD OBSERVATIONS');
    console.log('='.repeat(72));

    for (const event of monitor.events) {
        const candidates = physicalDesign.candidateIndexes(
            event.table,
            event.predicates
        );

        console.log(`\n${event.name}`);
        console.log(`  Rows examined: ${event.rowsExamined.toLocaleString()}`);
        console.log(`  Rows returned: ${event.rowsReturned.toLocaleString()}`);
        console.log(`  Selectivity: ${(monitor.selectivityFor(event) * 100).toFixed(4)}%`);
        console.log(`  Duration: ${event.durationMs.toFixed(1)} ms`);
        console.log(
            `  Supporting indexes: ${
                candidates.length
                    ? candidates.map(index => index.name).join(', ')
                    : 'none'
            }`
        );
    }

    console.log('\nPotential access-path problems:');

    for (const event of monitor.identifyPotentialProblems()) {
        console.log(`  ${event.name}`);
    }
}


// ---------------------------------------------------------------------------
// Schema evolution event
// ---------------------------------------------------------------------------

function demonstrateSchemaEvolution() {
    const eventBus = new SchemaEventBus();

    eventBus.on('column-added', event => {
        console.log(
            `\nSchema event: ${event.table}.${event.column} added as ${event.type}`
        );
        console.log(
            'Migration review should verify existing rows, application compatibility, '
            + 'default semantics, constraints, and deployment ordering.'
        );
    });

    eventBus.on('index-added', event => {
        console.log(
            `Physical event: index ${event.indexName} added to ${event.table}`
        );
    });

    eventBus.emit('column-added', {
        table: 'course_section',
        column: 'status',
        type: 'VARCHAR(20)'
    });

    eventBus.emit('index-added', {
        table: 'course_section',
        indexName: 'ix_section_status_term'
    });
}


// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

async function main() {
    console.log('DATABASE DESIGN PRINCIPLES');
    console.log('='.repeat(72));
    console.log(
        'Academic enrollment case study: separating business semantics from '
        + 'storage and workload decisions.'
    );

    const schema = buildLogicalSchema();
    const schemaErrors = schema.validate();

    console.log('\nLOGICAL DESIGN VALIDATION');
    console.log('='.repeat(72));

    if (schemaErrors.length > 0) {
        for (const error of schemaErrors) {
            console.error(`ERROR: ${error}`);
        }
        process.exitCode = 1;
        return;
    }

    console.log('Logical schema is internally consistent.');
    console.log(
        '\nThe enrollment relationship uses a composite key '
        + '(student_id, section_id), while student_number, email, and '
        + 'course_code are candidate keys representing alternate identifiers.'
    );

    console.log('\nNORMALIZATION BOUNDARY');
    console.log('='.repeat(72));
    console.log(
        'Student identity facts belong to student, course facts belong to '
        + 'course, offering facts belong to course_section, and the '
        + 'student-section relationship belongs to enrollment.'
    );
    console.log(
        'This decomposition reduces update anomalies because a course name '
        + 'is not copied into every enrollment row.'
    );

    const physicalDesign = buildPhysicalDesign();

    console.log('\nPHYSICAL DESIGN');
    console.log('='.repeat(72));

    for (const index of physicalDesign.indexes) {
        console.log(
            `${index.name}: ${index.table}(${index.columns.join(', ')})`
            + (index.unique ? ' UNIQUE' : '')
        );
    }

    console.log('\nPartitioning policies:');

    for (const [table, strategy] of physicalDesign.partitioning) {
        console.log(`  ${table}: ${strategy}`);
    }

    const workload = [
        {
            name: 'Student transcript lookup',
            table: 'enrollment',
            predicates: ['student_id'],
            frequencyPerDay: 25000
        },
        {
            name: 'Section roster lookup',
            table: 'enrollment',
            predicates: ['section_id'],
            frequencyPerDay: 18000
        },
        {
            name: 'Course sections by term',
            table: 'course_section',
            predicates: ['term_id', 'course_id'],
            frequencyPerDay: 7500
        },
        {
            name: 'Student by email',
            table: 'student',
            predicates: ['email'],
            frequencyPerDay: 40000
        },
        {
            name: 'Room-only search',
            table: 'course_section',
            predicates: ['room_code'],
            frequencyPerDay: 100
        }
    ];

    const policy = new DesignPolicy();
    const findings = policy.evaluate(schema, physicalDesign, workload);

    console.log('\nDESIGN POLICY FINDINGS');
    console.log('='.repeat(72));

    if (findings.length === 0) {
        console.log('No policy findings.');
    } else {
        for (const finding of findings) {
            console.log(`[${finding.severity}] ${finding.message}`);
        }
    }

    runWorkloadMonitor(physicalDesign);

    console.log('\nDATA INTEGRITY');
    console.log('='.repeat(72));

    const repository = new EnrollmentRepository();

    repository.addStudent({
        studentId: 1,
        studentNumber: 'S1001',
        fullName: 'Asha Rao',
        email: 'asha.rao@example.edu'
    });

    repository.addStudent({
        studentId: 2,
        studentNumber: 'S1002',
        fullName: 'Ravi Shah',
        email: 'ravi.shah@example.edu'
    });

    repository.addSection({
        sectionId: 501,
        courseId: 301,
        instructorId: 77,
        termId: 20261,
        roomCode: 'DB-204',
        capacity: 2
    });

    repository.enroll(1, 501, '2026-08-15');
    repository.assignGrade(1, 501, 'A');

    try {
        repository.enroll(1, 501, '2026-08-16');
    } catch (error) {
        console.log(`Expected duplicate-key failure: ${error.message}`);
    }

    try {
        repository.enroll(999, 501, '2026-08-16');
    } catch (error) {
        console.log(`Expected foreign-key failure: ${error.message}`);
    }

    const transactionResult = await executeEnrollmentTransaction(
        repository,
        [
            {
                studentId: 2,
                sectionId: 501,
                enrolledOn: '2026-08-16'
            },
            {
                studentId: 999,
                sectionId: 501,
                enrolledOn: '2026-08-16'
            }
        ]
    );

    console.log(
        `\nBatch committed: ${transactionResult.committed}`
    );
    console.log(
        `Enrollment count after batch: ${transactionResult.count}`
    );

    demonstrateSchemaEvolution();

    console.log('\nDESIGN OBJECTIVES');
    console.log('='.repeat(72));
    console.log(
        'Correctness: keys, foreign keys, domain validation, and relationship '
        + 'constraints protect business facts.'
    );
    console.log(
        'Performance: indexes and partitioning are selected from actual access '
        + 'patterns rather than added indiscriminately.'
    );
    console.log(
        'Maintainability: logical ownership of facts limits duplication and '
        + 'makes schema changes easier to reason about.'
    );
    console.log(
        'Scalability: high-volume relationship tables are candidates for '
        + 'partitioning only when measured workload and operational needs '
        + 'justify the extra complexity.'
    );
    console.log(
        'Security: physical implementation must enforce appropriate access '
        + 'boundaries instead of relying solely on application conventions.'
    );

    console.log('\nThe model keeps logical meaning independent from physical access paths.');
}


main().catch(error => {
    console.error(`Fatal error: ${error.message}`);
    process.exitCode = 1;
});
