/**
 * Cardinality: One-to-One, One-to-Many, Many-to-Many
 *
 * This Node.js program models a course registration service using an
 * event-driven architecture. It intentionally uses JavaScript-specific
 * features such as Map, Set, classes, async functions, custom errors,
 * immutable event payloads, and event listeners.
 *
 * Relationship model:
 *   Student <-> StudentProfile  : one-to-one
 *   Department -> Course        : one-to-many
 *   Student <-> Course          : many-to-many via Enrollment
 */

"use strict";

const { EventEmitter } = require("node:events");


// ---------------------------------------------------------------------------
// Domain errors
// ---------------------------------------------------------------------------

class CardinalityError extends Error {
    constructor(message) {
        super(message);
        this.name = "CardinalityError";
    }
}

class ReferenceError extends Error {
    constructor(message) {
        super(message);
        this.name = "ReferenceError";
    }
}


// ---------------------------------------------------------------------------
// Domain entities
// ---------------------------------------------------------------------------

class Student {
    constructor(id, name, email) {
        this.id = id;
        this.name = name;
        this.email = email;
        this.profileId = null;

        // A Set prevents duplicate course references and gives efficient
        // average-time membership checks.
        this.courseIds = new Set();
    }
}

class StudentProfile {
    constructor(id, studentId, phone, city) {
        this.id = id;
        this.studentId = studentId;
        this.phone = phone;
        this.city = city;
    }
}

class Department {
    constructor(id, name) {
        this.id = id;
        this.name = name;
        this.courseIds = new Set();
    }
}

class Course {
    constructor(id, title, departmentId) {
        this.id = id;
        this.title = title;
        this.departmentId = departmentId;
    }
}

class Enrollment {
    constructor(studentId, courseId, enrolledAt, status = "active") {
        this.studentId = studentId;
        this.courseId = courseId;
        this.enrolledAt = enrolledAt;
        this.status = status;
    }
}


// ---------------------------------------------------------------------------
// Event-driven relationship service
// ---------------------------------------------------------------------------

class CardinalityService extends EventEmitter {
    constructor() {
        super();

        this.students = new Map();
        this.profiles = new Map();
        this.departments = new Map();
        this.courses = new Map();

        // JavaScript does not provide value-based equality for ordinary
        // objects in Set, so enrollment keys are represented separately.
        this.enrollments = new Map();
    }

    addStudent(student) {
        this.assertNew(this.students, student.id, "student");
        this.students.set(student.id, student);

        this.emit("student.created", {
            studentId: student.id
        });
    }

    addDepartment(department) {
        this.assertNew(
            this.departments,
            department.id,
            "department"
        );

        this.departments.set(department.id, department);

        this.emit("department.created", {
            departmentId: department.id
        });
    }

    addProfile(profile) {
        this.requireReference(
            this.students,
            profile.studentId,
            "student"
        );

        this.assertNew(this.profiles, profile.id, "profile");

        const student = this.students.get(profile.studentId);

        // The existing profileId is the one-to-one uniqueness guard.
        if (student.profileId !== null) {
            throw new CardinalityError(
                `Student ${student.id} already has profile ${student.profileId}.`
            );
        }

        this.profiles.set(profile.id, profile);
        student.profileId = profile.id;

        this.emit("profile.attached", {
            profileId: profile.id,
            studentId: profile.studentId
        });
    }

    addCourse(course) {
        this.requireReference(
            this.departments,
            course.departmentId,
            "department"
        );

        this.assertNew(this.courses, course.id, "course");

        this.courses.set(course.id, course);

        const department = this.departments.get(course.departmentId);
        department.courseIds.add(course.id);

        this.emit("course.created", {
            courseId: course.id,
            departmentId: course.departmentId
        });
    }

    enroll(studentId, courseId) {
        this.requireReference(this.students, studentId, "student");
        this.requireReference(this.courses, courseId, "course");

        const key = this.enrollmentKey(studentId, courseId);

        if (this.enrollments.has(key)) {
            throw new CardinalityError(
                `${studentId} is already related to ${courseId}.`
            );
        }

        const enrollment = new Enrollment(
            studentId,
            courseId,
            new Date().toISOString()
        );

        this.enrollments.set(key, enrollment);

        this.students.get(studentId).courseIds.add(courseId);

        this.emit("enrollment.created", {
            studentId,
            courseId,
            relationshipKey: key
        });

        return enrollment;
    }

    withdraw(studentId, courseId) {
        const key = this.enrollmentKey(studentId, courseId);

        if (!this.enrollments.has(key)) {
            throw new ReferenceError(
                `Enrollment ${key} does not exist.`
            );
        }

        this.enrollments.delete(key);
        this.students.get(studentId)?.courseIds.delete(courseId);

        this.emit("enrollment.removed", {
            studentId,
            courseId,
            relationshipKey: key
        });
    }

    getProfile(studentId) {
        this.requireReference(this.students, studentId, "student");

        const profileId = this.students.get(studentId).profileId;

        return profileId === null
            ? null
            : this.profiles.get(profileId);
    }

    getCoursesForDepartment(departmentId) {
        this.requireReference(
            this.departments,
            departmentId,
            "department"
        );

        const department = this.departments.get(departmentId);

        return [...department.courseIds]
            .map(courseId => this.courses.get(courseId))
            .filter(Boolean);
    }

    getCoursesForStudent(studentId) {
        this.requireReference(this.students, studentId, "student");

        return [...this.students.get(studentId).courseIds]
            .map(courseId => this.courses.get(courseId))
            .filter(Boolean);
    }

    getStudentsForCourse(courseId) {
        this.requireReference(this.courses, courseId, "course");

        const students = [];

        for (const enrollment of this.enrollments.values()) {
            if (
                enrollment.courseId === courseId &&
                enrollment.status === "active"
            ) {
                students.push(
                    this.students.get(enrollment.studentId)
                );
            }
        }

        return students.filter(Boolean);
    }

    findSharedCourses(firstStudentId, secondStudentId) {
        const firstCourses = this.getCoursesForStudent(firstStudentId)
            .map(course => course.id);

        const secondCourseIds = new Set(
            this.getCoursesForStudent(secondStudentId)
                .map(course => course.id)
        );

        return firstCourses.filter(
            courseId => secondCourseIds.has(courseId)
        );
    }

    async validateRelationshipGraph() {
        // An async API makes this service compatible with a future database
        // implementation without changing the public validation contract.
        await Promise.resolve();

        const errors = [];

        for (const profile of this.profiles.values()) {
            const student = this.students.get(profile.studentId);

            if (!student) {
                errors.push(
                    `Profile ${profile.id} references missing student ` +
                    `${profile.studentId}.`
                );
                continue;
            }

            if (student.profileId !== profile.id) {
                errors.push(
                    `Student ${student.id} does not point back to ` +
                    `profile ${profile.id}.`
                );
            }
        }

        for (const course of this.courses.values()) {
            const department = this.departments.get(course.departmentId);

            if (!department) {
                errors.push(
                    `Course ${course.id} references missing department ` +
                    `${course.departmentId}.`
                );
                continue;
            }

            if (!department.courseIds.has(course.id)) {
                errors.push(
                    `Department ${department.id} lacks reverse reference ` +
                    `to course ${course.id}.`
                );
            }
        }

        for (const [key, enrollment] of this.enrollments.entries()) {
            const expectedKey = this.enrollmentKey(
                enrollment.studentId,
                enrollment.courseId
            );

            if (key !== expectedKey) {
                errors.push(
                    `Enrollment map key ${key} does not match its relationship.`
                );
            }

            if (!this.students.has(enrollment.studentId)) {
                errors.push(
                    `Enrollment ${key} references missing student.`
                );
            }

            if (!this.courses.has(enrollment.courseId)) {
                errors.push(
                    `Enrollment ${key} references missing course.`
                );
            }
        }

        return errors;
    }

    enrollmentKey(studentId, courseId) {
        // The separator makes the composite relationship key explicit.
        return `${studentId}::${courseId}`;
    }

    assertNew(map, id, entityName) {
        if (map.has(id)) {
            throw new CardinalityError(
                `${entityName} ${id} already exists.`
            );
        }
    }

    requireReference(map, id, entityName) {
        if (!map.has(id)) {
            throw new ReferenceError(
                `${entityName} ${id} does not exist.`
            );
        }
    }
}


// ---------------------------------------------------------------------------
// Event consumers
// ---------------------------------------------------------------------------

function installAuditLog(service) {
    const events = [
        "student.created",
        "department.created",
        "profile.attached",
        "course.created",
        "enrollment.created",
        "enrollment.removed"
    ];

    for (const eventName of events) {
        service.on(eventName, payload => {
            console.log(
                `[AUDIT] ${eventName}: ${JSON.stringify(payload)}`
            );
        });
    }
}


// ---------------------------------------------------------------------------
// Sample data
// ---------------------------------------------------------------------------

function createService() {
    const service = new CardinalityService();

    installAuditLog(service);

    service.addStudent(
        new Student(
            "S100",
            "Atul Pandey",
            "atul@example.edu"
        )
    );

    service.addStudent(
        new Student(
            "S101",
            "Priya Sharma",
            "priya@example.edu"
        )
    );

    service.addStudent(
        new Student(
            "S102",
            "Rahul Singh",
            "rahul@example.edu"
        )
    );

    service.addDepartment(
        new Department("D10", "Computer Science")
    );

    service.addDepartment(
        new Department("D20", "Management")
    );

    service.addProfile(
        new StudentProfile(
            "P100",
            "S100",
            "+91-9876543210",
            "Lucknow"
        )
    );

    service.addProfile(
        new StudentProfile(
            "P101",
            "S101",
            "+91-9123456780",
            "Delhi"
        )
    );

    service.addCourse(
        new Course(
            "C101",
            "Database Systems",
            "D10"
        )
    );

    service.addCourse(
        new Course(
            "C102",
            "Distributed Systems",
            "D10"
        )
    );

    service.addCourse(
        new Course(
            "C103",
            "Software Engineering",
            "D10"
        )
    );

    service.addCourse(
        new Course(
            "C201",
            "Product Management",
            "D20"
        )
    );

    service.enroll("S100", "C101");
    service.enroll("S100", "C102");
    service.enroll("S101", "C101");
    service.enroll("S101", "C103");
    service.enroll("S102", "C101");
    service.enroll("S102", "C201");

    return service;
}


// ---------------------------------------------------------------------------
// Demonstrations
// ---------------------------------------------------------------------------

async function runDemonstration() {
    console.log("CARDINALITY RELATIONSHIP MODEL");
    console.log("================================");

    const service = createService();

    console.log("\nONE-TO-ONE");
    const profile = service.getProfile("S100");
    console.log(
        `S100 -> profile ${profile.id}, ${profile.city}`
    );

    try {
        service.addProfile(
            new StudentProfile(
                "P999",
                "S100",
                "+91-0000000000",
                "Mumbai"
            )
        );
    } catch (error) {
        console.log(
            `Expected one-to-one rejection: ${error.message}`
        );
    }

    console.log("\nONE-TO-MANY");

    const departmentCourses =
        service.getCoursesForDepartment("D10");

    for (const course of departmentCourses) {
        console.log(
            `D10 -> ${course.id}: ${course.title}`
        );
    }

    console.log("\nMANY-TO-MANY");

    for (const studentId of ["S100", "S101", "S102"]) {
        const courses = service.getCoursesForStudent(studentId);

        console.log(
            `${studentId} -> ${courses.map(c => c.id).join(", ")}`
        );
    }

    const studentsInDatabaseCourse =
        service.getStudentsForCourse("C101");

    console.log(
        `C101 <- ${studentsInDatabaseCourse
            .map(student => student.id)
            .join(", ")}`
    );

    console.log(
        "Courses shared by S100 and S101:",
        service.findSharedCourses("S100", "S101")
    );

    console.log("\nMANY-TO-MANY DUPLICATE PROTECTION");

    try {
        service.enroll("S100", "C101");
    } catch (error) {
        console.log(
            `Expected duplicate rejection: ${error.message}`
        );
    }

    console.log("\nREFERENCE VALIDATION");

    try {
        service.enroll("S404", "C101");
    } catch (error) {
        console.log(
            `Expected missing-student rejection: ${error.message}`
        );
    }

    try {
        service.addCourse(
            new Course(
                "C404",
                "Invalid Course",
                "D404"
            )
        );
    } catch (error) {
        console.log(
            `Expected missing-department rejection: ${error.message}`
        );
    }

    console.log("\nRELATIONSHIP MUTATION");

    console.log(
        `Before withdrawal: ${
            service.getCoursesForStudent("S100")
                .map(course => course.id)
                .join(", ")
        }`
    );

    service.withdraw("S100", "C102");

    console.log(
        `After withdrawal: ${
            service.getCoursesForStudent("S100")
                .map(course => course.id)
                .join(", ")
        }`
    );

    service.enroll("S100", "C102");

    console.log(
        `After re-enrollment: ${
            service.getCoursesForStudent("S100")
                .map(course => course.id)
                .join(", ")
        }`
    );

    console.log("\nINTEGRITY VALIDATION");

    const errors = await service.validateRelationshipGraph();

    if (errors.length === 0) {
        console.log(
            "Relationship graph is internally consistent."
        );
    } else {
        for (const error of errors) {
            console.log(`ERROR: ${error}`);
        }
    }

    console.log("\nASYNC WORKFLOW");

    // In production, this same point could await database validation,
    // transaction completion, or an external persistence operation.
    await new Promise(resolve => setTimeout(resolve, 10));

    console.log(
        "Asynchronous relationship validation completed."
    );

    console.log("\nPERFORMANCE MODEL");

    console.log(
        "Student -> courses uses Set membership with average O(1) lookup."
    );

    console.log(
        "Department -> courses uses Set membership with average O(1) lookup."
    );

    console.log(
        "Course -> students scans enrollments in this in-memory model; " +
        "a production database would normally index course_id."
    );

    console.log(
        "The many-to-many association is stored independently so that " +
        "relationship attributes such as enrollment date and status have " +
        "a natural place to live."
    );
}

runDemonstration().catch(error => {
    console.error("Fatal relationship-model error:", error);
    process.exitCode = 1;
});
