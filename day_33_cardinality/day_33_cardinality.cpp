#include <algorithm>
#include <cassert>
#include <chrono>
#include <exception>
#include <iomanip>
#include <iostream>
#include <optional>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>

/*
 * Cardinality case study:
 *
 * A university registration platform has three relationships:
 *
 *   Student <-> StudentProfile
 *       one-to-one
 *
 *   Department -> Course
 *       one-to-many
 *
 *   Student <-> Course
 *       many-to-many through Enrollment
 *
 * The program implements a merge-like governance layer for relationship
 * mutations: every operation validates references and cardinality before
 * changing the in-memory state.
 *
 * C++17 is sufficient to compile this program.
 */


// ---------------------------------------------------------------------------
// Domain exceptions
// ---------------------------------------------------------------------------

class CardinalityError : public std::runtime_error {
public:
    explicit CardinalityError(const std::string& message)
        : std::runtime_error(message) {}
};

class NotFoundError : public std::runtime_error {
public:
    explicit NotFoundError(const std::string& message)
        : std::runtime_error(message) {}
};


// ---------------------------------------------------------------------------
// Domain entities
// ---------------------------------------------------------------------------

struct Student {
    std::string id;
    std::string name;
    std::string email;

    // nullopt means that this student does not currently have a profile.
    std::optional<std::string> profileId;

    // A hash set models the student's many course relationships.
    std::unordered_set<std::string> courseIds;
};

struct StudentProfile {
    std::string id;
    std::string studentId;
    std::string phone;
    std::string city;
};

struct Department {
    std::string id;
    std::string name;

    // One department may own many courses.
    std::unordered_set<std::string> courseIds;
};

struct Course {
    std::string id;
    std::string title;
    std::string departmentId;
};

struct Enrollment {
    std::string studentId;
    std::string courseId;
    std::string semester;
    std::optional<char> grade;
};


// ---------------------------------------------------------------------------
// Composite key for the many-to-many relationship
// ---------------------------------------------------------------------------

struct EnrollmentKey {
    std::string studentId;
    std::string courseId;

    bool operator==(const EnrollmentKey& other) const {
        return studentId == other.studentId &&
               courseId == other.courseId;
    }
};

struct EnrollmentKeyHash {
    std::size_t operator()(const EnrollmentKey& key) const noexcept {
        const std::size_t first =
            std::hash<std::string>{}(key.studentId);

        const std::size_t second =
            std::hash<std::string>{}(key.courseId);

        // Combining the two hashes distinguishes the composite key.
        return first ^ (second + 0x9e3779b9 +
                        (first << 6) + (first >> 2));
    }
};


// ---------------------------------------------------------------------------
// Repository
// ---------------------------------------------------------------------------

class UniversityRepository {
private:
    std::unordered_map<std::string, Student> students;
    std::unordered_map<std::string, StudentProfile> profiles;
    std::unordered_map<std::string, Department> departments;
    std::unordered_map<std::string, Course> courses;

    std::unordered_map<
        EnrollmentKey,
        Enrollment,
        EnrollmentKeyHash
    > enrollments;

public:
    void addStudent(Student student) {
        requireNew(students, student.id, "student");
        students.emplace(student.id, std::move(student));
    }

    void addDepartment(Department department) {
        requireNew(
            departments,
            department.id,
            "department"
        );

        departments.emplace(
            department.id,
            std::move(department)
        );
    }

    void addProfile(StudentProfile profile) {
        requireReference(
            students,
            profile.studentId,
            "student"
        );

        requireNew(
            profiles,
            profile.id,
            "profile"
        );

        Student& student = students.at(profile.studentId);

        // The student can own zero or one profile, never two.
        if (student.profileId.has_value()) {
            throw CardinalityError(
                "Student " + student.id +
                " already has profile " +
                student.profileId.value()
            );
        }

        student.profileId = profile.id;

        profiles.emplace(
            profile.id,
            std::move(profile)
        );
    }

    void addCourse(Course course) {
        requireReference(
            departments,
            course.departmentId,
            "department"
        );

        requireNew(
            courses,
            course.id,
            "course"
        );

        const std::string departmentId = course.departmentId;
        const std::string courseId = course.id;

        courses.emplace(
            course.id,
            std::move(course)
        );

        departments.at(departmentId)
            .courseIds
            .insert(courseId);
    }

    void enroll(
        const std::string& studentId,
        const std::string& courseId,
        const std::string& semester,
        std::optional<char> grade = std::nullopt
    ) {
        requireReference(
            students,
            studentId,
            "student"
        );

        requireReference(
            courses,
            courseId,
            "course"
        );

        EnrollmentKey key{
            studentId,
            courseId
        };

        if (enrollments.find(key) != enrollments.end()) {
            throw CardinalityError(
                "Duplicate student-course relationship: " +
                studentId + " / " + courseId
            );
        }

        Enrollment enrollment{
            studentId,
            courseId,
            semester,
            grade
        };

        enrollments.emplace(
            key,
            std::move(enrollment)
        );

        students.at(studentId)
            .courseIds
            .insert(courseId);
    }

    void withdraw(
        const std::string& studentId,
        const std::string& courseId
    ) {
        EnrollmentKey key{
            studentId,
            courseId
        };

        const auto iterator = enrollments.find(key);

        if (iterator == enrollments.end()) {
            throw NotFoundError(
                "Enrollment does not exist: " +
                studentId + " / " + courseId
            );
        }

        enrollments.erase(iterator);

        auto studentIterator = students.find(studentId);

        if (studentIterator != students.end()) {
            studentIterator->second.courseIds.erase(courseId);
        }
    }

    const StudentProfile* getProfile(
        const std::string& studentId
    ) const {
        requireReference(
            students,
            studentId,
            "student"
        );

        const Student& student = students.at(studentId);

        if (!student.profileId.has_value()) {
            return nullptr;
        }

        return &profiles.at(student.profileId.value());
    }

    std::vector<const Course*> getDepartmentCourses(
        const std::string& departmentId
    ) const {
        requireReference(
            departments,
            departmentId,
            "department"
        );

        std::vector<const Course*> result;

        const Department& department =
            departments.at(departmentId);

        for (const std::string& courseId : department.courseIds) {
            result.push_back(&courses.at(courseId));
        }

        std::sort(
            result.begin(),
            result.end(),
            [](const Course* left, const Course* right) {
                return left->id < right->id;
            }
        );

        return result;
    }

    std::vector<const Course*> getStudentCourses(
        const std::string& studentId
    ) const {
        requireReference(
            students,
            studentId,
            "student"
        );

        std::vector<const Course*> result;

        const Student& student = students.at(studentId);

        for (const std::string& courseId : student.courseIds) {
            result.push_back(&courses.at(courseId));
        }

        std::sort(
            result.begin(),
            result.end(),
            [](const Course* left, const Course* right) {
                return left->id < right->id;
            }
        );

        return result;
    }

    std::vector<const Student*> getCourseStudents(
        const std::string& courseId
    ) const {
        requireReference(
            courses,
            courseId,
            "course"
        );

        std::vector<const Student*> result;

        for (const auto& [key, enrollment] : enrollments) {
            if (key.courseId == courseId) {
                result.push_back(
                    &students.at(key.studentId)
                );
            }
        }

        std::sort(
            result.begin(),
            result.end(),
            [](const Student* left, const Student* right) {
                return left->id < right->id;
            }
        );

        return result;
    }

    std::unordered_set<std::string> findSharedCourses(
        const std::string& firstStudentId,
        const std::string& secondStudentId
    ) const {
        requireReference(
            students,
            firstStudentId,
            "student"
        );

        requireReference(
            students,
            secondStudentId,
            "student"
        );

        const auto& firstCourses =
            students.at(firstStudentId).courseIds;

        const auto& secondCourses =
            students.at(secondStudentId).courseIds;

        const auto* smaller = &firstCourses;
        const auto* larger = &secondCourses;

        // Iterate through the smaller set to reduce membership checks.
        if (firstCourses.size() > secondCourses.size()) {
            smaller = &secondCourses;
            larger = &firstCourses;
        }

        std::unordered_set<std::string> shared;

        for (const auto& courseId : *smaller) {
            if (larger->find(courseId) != larger->end()) {
                shared.insert(courseId);
            }
        }

        return shared;
    }

    std::vector<std::string> validateIntegrity() const {
        std::vector<std::string> errors;

        // Validate the one-to-one relationship in both directions.
        for (const auto& [profileId, profile] : profiles) {
            auto studentIterator =
                students.find(profile.studentId);

            if (studentIterator == students.end()) {
                errors.push_back(
                    "Profile " + profileId +
                    " references missing student " +
                    profile.studentId
                );
                continue;
            }

            const Student& student =
                studentIterator->second;

            if (!student.profileId.has_value() ||
                student.profileId.value() != profileId) {
                errors.push_back(
                    "Profile " + profileId +
                    " has an inconsistent reverse reference."
                );
            }
        }

        // Validate one-to-many foreign keys and reverse indexes.
        for (const auto& [courseId, course] : courses) {
            auto departmentIterator =
                departments.find(course.departmentId);

            if (departmentIterator == departments.end()) {
                errors.push_back(
                    "Course " + courseId +
                    " references missing department " +
                    course.departmentId
                );
                continue;
            }

            if (
                departmentIterator->second.courseIds.find(courseId)
                ==
                departmentIterator->second.courseIds.end()
            ) {
                errors.push_back(
                    "Department " +
                    course.departmentId +
                    " is missing reverse reference to " +
                    courseId
                );
            }
        }

        // Validate many-to-many endpoints and duplicate prevention.
        for (const auto& [key, enrollment] : enrollments) {
            if (students.find(key.studentId) == students.end()) {
                errors.push_back(
                    "Enrollment references missing student " +
                    key.studentId
                );
            }

            if (courses.find(key.courseId) == courses.end()) {
                errors.push_back(
                    "Enrollment references missing course " +
                    key.courseId
                );
            }

            if (
                students.find(key.studentId) != students.end() &&
                students.at(key.studentId)
                    .courseIds.find(key.courseId)
                    ==
                    students.at(key.studentId)
                        .courseIds.end()
            ) {
                errors.push_back(
                    "Student reverse index is missing " +
                    key.courseId
                );
            }

            if (
                enrollment.studentId != key.studentId ||
                enrollment.courseId != key.courseId
            ) {
                errors.push_back(
                    "Enrollment data disagrees with its composite key."
                );
            }
        }

        return errors;
    }

    std::size_t enrollmentCount() const {
        return enrollments.size();
    }

private:
    template <typename Map>
    static void requireNew(
        const Map& map,
        const std::string& id,
        const std::string& entityName
    ) {
        if (map.find(id) != map.end()) {
            throw CardinalityError(
                entityName + " " + id + " already exists."
            );
        }
    }

    template <typename Map>
    static void requireReference(
        const Map& map,
        const std::string& id,
        const std::string& entityName
    ) {
        if (map.find(id) == map.end()) {
            throw NotFoundError(
                entityName + " " + id + " does not exist."
            );
        }
    }
};


// ---------------------------------------------------------------------------
// Presentation helpers
// ---------------------------------------------------------------------------

void printStudentCourses(
    const UniversityRepository& repository,
    const std::string& studentId
) {
    const auto courses =
        repository.getStudentCourses(studentId);

    std::cout << studentId << " -> ";

    for (std::size_t index = 0; index < courses.size(); ++index) {
        if (index > 0) {
            std::cout << ", ";
        }

        std::cout << courses[index]->id;
    }

    std::cout << '\n';
}

void printCourseStudents(
    const UniversityRepository& repository,
    const std::string& courseId
) {
    const auto students =
        repository.getCourseStudents(courseId);

    std::cout << courseId << " <- ";

    for (std::size_t index = 0; index < students.size(); ++index) {
        if (index > 0) {
            std::cout << ", ";
        }

        std::cout << students[index]->id;
    }

    std::cout << '\n';
}


// ---------------------------------------------------------------------------
// Test-style verification
// ---------------------------------------------------------------------------

void runAssertions(UniversityRepository& repository) {
    const StudentProfile* profile =
        repository.getProfile("S100");

    assert(profile != nullptr);
    assert(profile->studentId == "S100");

    const auto departmentCourses =
        repository.getDepartmentCourses("D10");

    assert(departmentCourses.size() == 3);

    const auto studentCourses =
        repository.getStudentCourses("S100");

    assert(studentCourses.size() == 2);

    const auto courseStudents =
        repository.getCourseStudents("C101");

    assert(courseStudents.size() == 3);

    const auto shared =
        repository.findSharedCourses("S100", "S101");

    assert(shared.size() == 1);
    assert(shared.find("C101") != shared.end());

    const std::size_t originalCount =
        repository.enrollmentCount();

    repository.withdraw("S100", "C102");

    assert(
        repository.enrollmentCount() ==
        originalCount - 1
    );

    repository.enroll(
        "S100",
        "C102",
        "2026-FALL"
    );

    assert(
        repository.enrollmentCount() ==
        originalCount
    );

    assert(
        repository.validateIntegrity().empty()
    );
}


// ---------------------------------------------------------------------------
// Failure demonstrations
// ---------------------------------------------------------------------------

void demonstrateFailures(
    UniversityRepository& repository
) {
    std::cout << "\nFAILURE HANDLING\n";

    try {
        repository.addProfile(
            StudentProfile{
                "P999",
                "S100",
                "+91-0000000000",
                "Mumbai"
            }
        );
    }
    catch (const CardinalityError& error) {
        std::cout
            << "One-to-one violation caught: "
            << error.what()
            << '\n';
    }

    try {
        repository.addCourse(
            Course{
                "C999",
                "Invalid Course",
                "D404"
            }
        );
    }
    catch (const NotFoundError& error) {
        std::cout
            << "One-to-many reference violation caught: "
            << error.what()
            << '\n';
    }

    try {
        repository.enroll(
            "S100",
            "C101",
            "2026-FALL"
        );
    }
    catch (const CardinalityError& error) {
        std::cout
            << "Many-to-many duplicate caught: "
            << error.what()
            << '\n';
    }

    try {
        repository.enroll(
            "S404",
            "C101",
            "2026-FALL"
        );
    }
    catch (const NotFoundError& error) {
        std::cout
            << "Missing endpoint caught: "
            << error.what()
            << '\n';
    }
}


// ---------------------------------------------------------------------------
// Main case study
// ---------------------------------------------------------------------------

int main() {
    try {
        std::cout
            << "CARDINALITY: UNIVERSITY REGISTRATION ENGINE\n"
            << "============================================\n";

        UniversityRepository repository;

        // One-to-one entities.
        repository.addStudent(
            Student{
                "S100",
                "Atul Pandey",
                "atul@example.edu",
                std::nullopt,
                {}
            }
        );

        repository.addStudent(
            Student{
                "S101",
                "Priya Sharma",
                "priya@example.edu",
                std::nullopt,
                {}
            }
        );

        repository.addStudent(
            Student{
                "S102",
                "Rahul Singh",
                "rahul@example.edu",
                std::nullopt,
                {}
            }
        );

        repository.addProfile(
            StudentProfile{
                "P100",
                "S100",
                "+91-9876543210",
                "Lucknow"
            }
        );

        repository.addProfile(
            StudentProfile{
                "P101",
                "S101",
                "+91-9123456780",
                "Delhi"
            }
        );

        // One-to-many parent entities.
        repository.addDepartment(
            Department{
                "D10",
                "Computer Science",
                {}
            }
        );

        repository.addDepartment(
            Department{
                "D20",
                "Management",
                {}
            }
        );

        repository.addCourse(
            Course{
                "C101",
                "Database Systems",
                "D10"
            }
        );

        repository.addCourse(
            Course{
                "C102",
                "Distributed Systems",
                "D10"
            }
        );

        repository.addCourse(
            Course{
                "C103",
                "Software Engineering",
                "D10"
            }
        );

        repository.addCourse(
            Course{
                "C201",
                "Product Management",
                "D20"
            }
        );

        // Many-to-many association records.
        repository.enroll(
            "S100",
            "C101",
            "2026-FALL"
        );

        repository.enroll(
            "S100",
            "C102",
            "2026-FALL"
        );

        repository.enroll(
            "S101",
            "C101",
            "2026-FALL"
        );

        repository.enroll(
            "S101",
            "C103",
            "2026-FALL"
        );

        repository.enroll(
            "S102",
            "C101",
            "2026-FALL"
        );

        repository.enroll(
            "S102",
            "C201",
            "2026-FALL"
        );

        std::cout << "\nONE-TO-ONE\n";

        const StudentProfile* profile =
            repository.getProfile("S100");

        if (profile != nullptr) {
            std::cout
                << "S100 -> "
                << profile->id
                << " -> "
                << profile->city
                << '\n';
        }

        std::cout << "\nONE-TO-MANY\n";

        const auto courses =
            repository.getDepartmentCourses("D10");

        for (const Course* course : courses) {
            std::cout
                << "D10 -> "
                << course->id
                << " : "
                << course->title
                << '\n';
        }

        std::cout << "\nMANY-TO-MANY\n";

        printStudentCourses(repository, "S100");
        printStudentCourses(repository, "S101");
        printStudentCourses(repository, "S102");

        printCourseStudents(repository, "C101");

        const auto shared =
            repository.findSharedCourses(
                "S100",
                "S101"
            );

        std::cout
            << "Courses shared by S100 and S101: ";

        for (const auto& courseId : shared) {
            std::cout << courseId << ' ';
        }

        std::cout << '\n';

        demonstrateFailures(repository);

        std::cout << "\nINTEGRITY VALIDATION\n";

        const auto errors =
            repository.validateIntegrity();

        if (errors.empty()) {
            std::cout
                << "All relationship constraints are consistent.\n";
        }
        else {
            for (const auto& error : errors) {
                std::cout
                    << "ERROR: "
                    << error
                    << '\n';
            }
        }

        std::cout << "\nMUTATION TESTS\n";

        const std::size_t before =
            repository.enrollmentCount();

        repository.withdraw(
            "S100",
            "C102"
        );

        std::cout
            << "Enrollment count after withdrawal: "
            << repository.enrollmentCount()
            << '\n';

        repository.enroll(
            "S100",
            "C102",
            "2026-FALL"
        );

        std::cout
            << "Enrollment count after re-enrollment: "
            << repository.enrollmentCount()
            << '\n';

        assert(
            repository.enrollmentCount() == before
        );

        runAssertions(repository);

        std::cout << "\nPERFORMANCE CHARACTERISTICS\n";

        std::cout
            << "Student-to-course membership uses "
            << "unordered_set average O(1) lookup.\n";

        std::cout
            << "Department-to-course membership uses "
            << "unordered_set average O(1) lookup.\n";

        std::cout
            << "Many-to-many enrollment lookup by composite key uses "
            << "unordered_map average O(1) lookup.\n";

        std::cout
            << "Course-to-student reverse lookup scans enrollment records "
            << "in this case study; a production schema would index "
            << "course_id in the association table.\n";

        std::cout << "\nCASE STUDY COMPLETED\n";

        return 0;
    }
    catch (const std::exception& error) {
        std::cerr
            << "Fatal error: "
            << error.what()
            << '\n';

        return 1;
    }
}
