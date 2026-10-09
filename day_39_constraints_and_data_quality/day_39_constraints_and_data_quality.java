import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Collections;
import java.util.EnumSet;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.UUID;
import java.util.regex.Pattern;

/*
 * Enterprise data-quality service for employee onboarding.
 *
 * Compile and run:
 *   javac DataQualityGovernance.java
 *   java DataQualityGovernance
 *
 * Java 17+, standard library only.
 */

public class DataQualityGovernance {

    enum QualityRule {
        REQUIRED_FIELD,
        TEXT_LENGTH,
        EMAIL_FORMAT,
        UNIQUE_EMPLOYEE_CODE,
        UNIQUE_EMAIL,
        AGE_RANGE,
        SALARY_RANGE,
        SALARY_PRECISION,
        DEPARTMENT_REFERENCE,
        INVALID_ACTIVE_STATE,
        EMPLOYEE_NOT_FOUND
    }

    enum Severity {
        WARNING,
        ERROR
    }

    record QualityViolation(
        UUID id,
        Instant detectedAt,
        QualityRule rule,
        Severity severity,
        String field,
        String message,
        String employeeCode
    ) {
        QualityViolation {
            Objects.requireNonNull(id);
            Objects.requireNonNull(detectedAt);
            Objects.requireNonNull(rule);
            Objects.requireNonNull(severity);
            Objects.requireNonNull(field);
            Objects.requireNonNull(message);
        }
    }

    record Department(String name, BigDecimal annualBudget) {
        Department {
            name = requireText(name, "department name", 50);
            Objects.requireNonNull(annualBudget, "annualBudget");

            if (annualBudget.signum() < 0) {
                throw new IllegalArgumentException(
                    "Department budget cannot be negative."
                );
            }

            annualBudget = annualBudget.setScale(2, RoundingMode.UNNECESSARY);
        }
    }

    record EmployeeCommand(
        String employeeCode,
        String email,
        String fullName,
        int age,
        BigDecimal salary,
        String department,
        boolean active
    ) {}

    record Employee(
        UUID id,
        String employeeCode,
        String email,
        String fullName,
        int age,
        BigDecimal salary,
        String department,
        boolean active,
        Instant createdAt
    ) {
        Employee {
            Objects.requireNonNull(id);
            Objects.requireNonNull(createdAt);
            Objects.requireNonNull(salary);
        }
    }

    static class DataQualityException extends RuntimeException {
        private final QualityRule rule;
        private final String field;

        DataQualityException(
            QualityRule rule,
            String field,
            String message
        ) {
            super(message);
            this.rule = rule;
            this.field = field;
        }

        QualityRule rule() {
            return rule;
        }

        String field() {
            return field;
        }
    }

    static String requireText(
        String value,
        String field,
        int maximumLength
    ) {
        if (value == null) {
            throw new DataQualityException(
                QualityRule.REQUIRED_FIELD,
                field,
                field + " cannot be null."
            );
        }

        String normalized = value.strip();

        if (normalized.isEmpty() || normalized.length() > maximumLength) {
            throw new DataQualityException(
                QualityRule.TEXT_LENGTH,
                field,
                field + " must contain between 1 and "
                    + maximumLength + " characters."
            );
        }

        return normalized;
    }

    static String normalizeEmail(String value) {
        String email = requireText(value, "email", 254)
            .toLowerCase(Locale.ROOT);

        // Basic business validation is not a complete RFC email parser.
        if (!Pattern.matches("^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$", email)) {
            throw new DataQualityException(
                QualityRule.EMAIL_FORMAT,
                "email",
                "Email does not match the accepted business format."
            );
        }

        return email;
    }

    static BigDecimal normalizeSalary(BigDecimal salary) {
        if (salary == null) {
            throw new DataQualityException(
                QualityRule.REQUIRED_FIELD,
                "salary",
                "Salary cannot be null."
            );
        }

        if (salary.signum() < 0) {
            throw new DataQualityException(
                QualityRule.SALARY_RANGE,
                "salary",
                "Salary cannot be negative."
            );
        }

        try {
            return salary.setScale(2, RoundingMode.UNNECESSARY);
        } catch (ArithmeticException exception) {
            throw new DataQualityException(
                QualityRule.SALARY_PRECISION,
                "salary",
                "Salary cannot have more than two fractional digits."
            );
        }
    }

    static EmployeeCommand validateCommand(EmployeeCommand command) {
        Objects.requireNonNull(command, "Employee command cannot be null.");

        String code = requireText(
            command.employeeCode(), "employeeCode", 20
        ).toUpperCase(Locale.ROOT);

        String email = normalizeEmail(command.email());
        String name = requireText(command.fullName(), "fullName", 100);
        String department = requireText(
            command.department(), "department", 50
        );

        if (command.age() < 18 || command.age() > 100) {
            throw new DataQualityException(
                QualityRule.AGE_RANGE,
                "age",
                "Age must be between 18 and 100."
            );
        }

        return new EmployeeCommand(
            code,
            email,
            name,
            command.age(),
            normalizeSalary(command.salary()),
            department,
            command.active()
        );
    }

    static final class EmployeeRepository {
        private final Map<UUID, Employee> byId = new HashMap<>();
        private final Map<String, UUID> idByCode = new HashMap<>();
        private final Map<String, UUID> idByEmail = new HashMap<>();
        private final Map<String, Department> departments = new HashMap<>();
        private final List<QualityViolation> violations = new ArrayList<>();

        void addDepartment(Department department) {
            Objects.requireNonNull(department);

            Department existing = departments.putIfAbsent(
                department.name(), department
            );

            if (existing != null) {
                throw new IllegalArgumentException(
                    "Department already exists: " + department.name()
                );
            }
        }

        Employee create(EmployeeCommand rawCommand) {
            EmployeeCommand command = validateCommand(rawCommand);

            if (idByCode.containsKey(command.employeeCode())) {
                reject(
                    QualityRule.UNIQUE_EMPLOYEE_CODE,
                    "employeeCode",
                    "Employee code already exists.",
                    command.employeeCode()
                );
            }

            if (idByEmail.containsKey(command.email())) {
                reject(
                    QualityRule.UNIQUE_EMAIL,
                    "email",
                    "Email already exists.",
                    command.employeeCode()
                );
            }

            if (!departments.containsKey(command.department())) {
                reject(
                    QualityRule.DEPARTMENT_REFERENCE,
                    "department",
                    "Department is not registered.",
                    command.employeeCode()
                );
            }

            Employee employee = new Employee(
                UUID.randomUUID(),
                command.employeeCode(),
                command.email(),
                command.fullName(),
                command.age(),
                command.salary(),
                command.department(),
                command.active(),
                Instant.now()
            );

            // The uniqueness checks precede all index mutations. Persistent
            // implementations still need database UNIQUE constraints because
            // concurrent requests can race between checking and insertion.
            byId.put(employee.id(), employee);
            idByCode.put(employee.employeeCode(), employee.id());
            idByEmail.put(employee.email(), employee.id());

            return employee;
        }

        private void reject(
            QualityRule rule,
            String field,
            String message,
            String employeeCode
        ) {
            violations.add(new QualityViolation(
                UUID.randomUUID(),
                Instant.now(),
                rule,
                Severity.ERROR,
                field,
                message,
                employeeCode
            ));

            throw new DataQualityException(rule, field, message);
        }

        Employee updateSalary(String employeeCode, BigDecimal rawSalary) {
            String code = requireText(
                employeeCode, "employeeCode", 20
            ).toUpperCase(Locale.ROOT);

            UUID id = idByCode.get(code);

            if (id == null) {
                reject(
                    QualityRule.EMPLOYEE_NOT_FOUND,
                    "employeeCode",
                    "Cannot update a missing employee.",
                    code
                );
            }

            Employee current = byId.get(id);
            BigDecimal salary = normalizeSalary(rawSalary);

            Employee updated = new Employee(
                current.id(),
                current.employeeCode(),
                current.email(),
                current.fullName(),
                current.age(),
                salary,
                current.department(),
                current.active(),
                current.createdAt()
            );

            byId.put(id, updated);
            return updated;
        }

        List<Employee> findByDepartment(
            String departmentName,
            boolean activeOnly
        ) {
            List<Employee> result = new ArrayList<>();

            for (Employee employee : byId.values()) {
                if (employee.department().equals(departmentName)
                    && (!activeOnly || employee.active())) {
                    result.add(employee);
                }
            }

            result.sort(
                java.util.Comparator.comparing(Employee::employeeCode)
            );

            return Collections.unmodifiableList(result);
        }

        List<QualityViolation> violations() {
            return Collections.unmodifiableList(violations);
        }

        List<Employee> allEmployees() {
            return Collections.unmodifiableList(
                new ArrayList<>(byId.values())
            );
        }
    }

    static final class OnboardingService {
        private final EmployeeRepository repository;

        OnboardingService(EmployeeRepository repository) {
            this.repository = Objects.requireNonNull(repository);
        }

        List<Employee> importBatch(List<EmployeeCommand> commands) {
            List<Employee> accepted = new ArrayList<>();

            for (EmployeeCommand command : commands) {
                try {
                    accepted.add(repository.create(command));
                } catch (DataQualityException exception) {
                    System.out.printf(
                        "Rejected %s [%s]: %s%n",
                        command.employeeCode(),
                        exception.rule(),
                        exception.getMessage()
                    );
                }
            }

            return Collections.unmodifiableList(accepted);
        }
    }

    public static void main(String[] args) {
        EmployeeRepository repository = new EmployeeRepository();

        repository.addDepartment(new Department(
            "Engineering", new BigDecimal("250000.00")
        ));
        repository.addDepartment(new Department(
            "Finance", new BigDecimal("150000.00")
        ));
        repository.addDepartment(new Department(
            "Operations", new BigDecimal("200000.00")
        ));

        OnboardingService service = new OnboardingService(repository);

        List<EmployeeCommand> batch = List.of(
            new EmployeeCommand(
                "E-401", "ALICE@example.com", "Alice Sharma", 32,
                new BigDecimal("65000.00"), "Engineering", true
            ),
            new EmployeeCommand(
                "E-402", "rahul@example.com", "Rahul Verma", 41,
                new BigDecimal("82000.00"), "Finance", true
            ),
            new EmployeeCommand(
                "E-403", "meera@example.com", "Meera Singh", 27,
                new BigDecimal("54000.00"), "Operations", false
            ),
            new EmployeeCommand(
                "E-401", "another@example.com", "Duplicate Code", 30,
                new BigDecimal("45000.00"), "Finance", true
            ),
            new EmployeeCommand(
                "E-404", "alice@EXAMPLE.com", "Duplicate Email", 30,
                new BigDecimal("45000.00"), "Engineering", true
            ),
            new EmployeeCommand(
                "E-405", "underage@example.com", "Underage Applicant", 17,
                new BigDecimal("30000.00"), "Finance", true
            ),
            new EmployeeCommand(
                "E-406", "unknown@example.com", "Unknown Department", 29,
                new BigDecimal("45000.00"), "Legal", true
            )
        );

        List<Employee> accepted = service.importBatch(batch);

        System.out.println("\nAccepted employee records");
        for (Employee employee : accepted) {
            System.out.printf(
                "%s | %s | %s | salary=%s%n",
                employee.employeeCode(),
                employee.fullName(),
                employee.department(),
                employee.salary()
            );
        }

        System.out.println("\nActive Engineering employees");
        for (Employee employee :
            repository.findByDepartment("Engineering", true)) {
            System.out.println(employee.employeeCode() + " " + employee.fullName());
        }

        System.out.println("\nSalary correction");
        try {
            Employee updated = repository.updateSalary(
                "E-401", new BigDecimal("68000.00")
            );
            System.out.println(
                updated.employeeCode() + " salary=" + updated.salary()
            );
        } catch (DataQualityException exception) {
            System.out.println(exception.getMessage());
        }

        try {
            repository.updateSalary("E-401", new BigDecimal("-1.00"));
        } catch (DataQualityException exception) {
            System.out.println(
                "Rejected salary correction: " + exception.getMessage()
            );
        }

        System.out.println("\nQuality metrics");
        System.out.println("Accepted records: " + repository.allEmployees().size());
        System.out.println("Recorded violations: " + repository.violations().size());

        Map<String, BigDecimal> salaryTotals = new HashMap<>();
        Map<String, Integer> counts = new HashMap<>();

        for (Employee employee : repository.allEmployees()) {
            salaryTotals.merge(
                employee.department(), employee.salary(), BigDecimal::add
            );
            counts.merge(employee.department(), 1, Integer::sum);
        }

        for (String department : new java.util.TreeSet<>(counts.keySet())) {
            BigDecimal average = salaryTotals.get(department).divide(
                BigDecimal.valueOf(counts.get(department)),
                2,
                RoundingMode.HALF_UP
            );

            System.out.printf(
                "%s: count=%d, averageSalary=%s%n",
                department,
                counts.get(department),
                average
            );
        }
    }
}
