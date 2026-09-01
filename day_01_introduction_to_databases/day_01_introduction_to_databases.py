# ============================================================
# INTRODUCTION TO DATABASES
# ============================================================
# This script is designed for a complete beginner.
# It explains:
# 1. What databases are
# 2. Why databases exist
# 3. DBMS
# 4. Database users
# 5. Database applications
#
# The script uses simple Python examples and simulations.
# It does NOT require a real database system.
# ============================================================


print("=" * 70)
print("INTRODUCTION TO DATABASES")
print("=" * 70)


# ============================================================
# 1. WHAT IS DATA?
# ============================================================

print("\n1. WHAT IS DATA?")
print("-" * 70)

print("""
Data means recorded facts, values, observations, or information.

Examples:
- A person's name
- A person's age
- A product price
- A customer's phone number
- A student's marks
- A bank transaction
- An employee's salary
- An order date

In Python, data can be represented using variables and data structures.
""")

name = "Atul"
age = 33
city = "Lucknow"
salary = 50000

print("Name:", name)
print("Age:", age)
print("City:", city)
print("Salary:", salary)

print("""
The important idea is:

DATA = individual facts that can be stored, processed, searched,
updated, analyzed, and used for decision-making.
""")


# ============================================================
# 2. WHAT IS A DATABASE?
# ============================================================

print("\n2. WHAT IS A DATABASE?")
print("-" * 70)

print("""
A database is an organized collection of data that can be stored,
managed, searched, updated, and retrieved efficiently.

Imagine a business has thousands of customers.

For every customer, the business may need:
- Customer ID
- Name
- Email
- Phone number
- City
- Date of registration
- Purchase history

Keeping all of this information scattered across random files would
become difficult.

A database provides an organized way to keep this information together.
""")

customers = [
    {
        "customer_id": 101,
        "name": "Rahul",
        "city": "Lucknow",
        "email": "rahul@example.com"
    },
    {
        "customer_id": 102,
        "name": "Priya",
        "city": "Delhi",
        "email": "priya@example.com"
    },
    {
        "customer_id": 103,
        "name": "Amit",
        "city": "Mumbai",
        "email": "amit@example.com"
    }
]

print("Example database-like collection:")
for customer in customers:
    print(customer)

print("""
The Python list above is NOT a full database.

It is only a simple simulation that helps us understand the concept.

A real database provides specialized mechanisms for:
- storing large amounts of data
- searching data
- updating data
- deleting data
- controlling access
- maintaining consistency
- handling many users
- recovering from failures
""")


# ============================================================
# 3. DATABASE AS AN ORGANIZED SYSTEM
# ============================================================

print("\n3. DATABASE AS AN ORGANIZED DATA SYSTEM")
print("-" * 70)

print("""
A database is more than simply a collection of values.

Good database organization gives data structure and relationships.

For example, an online shopping business may have:

CUSTOMERS
    |
    +---- ORDERS
              |
              +---- PRODUCTS

A customer can place many orders.
An order can contain multiple products.

This allows businesses to represent relationships between different
types of information.
""")

customers_table = [
    {"customer_id": 1, "name": "Anil"},
    {"customer_id": 2, "name": "Neha"}
]

orders_table = [
    {"order_id": 1001, "customer_id": 1, "product": "Laptop"},
    {"order_id": 1002, "customer_id": 1, "product": "Mouse"},
    {"order_id": 1003, "customer_id": 2, "product": "Keyboard"}
]

print("CUSTOMERS")
for row in customers_table:
    print(row)

print("\nORDERS")
for row in orders_table:
    print(row)

print("""
Notice that customer_id connects the two collections.

This is an example of a relationship between data.
Relational databases make such relationships a central part of their
design.
""")


# ============================================================
# 4. WHY DO DATABASES EXIST?
# ============================================================

print("\n4. WHY DO DATABASES EXIST?")
print("-" * 70)

print("""
The main reason databases exist is that organizations need to store
and manage increasing amounts of information reliably and efficiently.

Before modern database systems, organizations often depended heavily
on paper records and separate computer files.

As organizations grew, several problems appeared.
""")

print("\nProblem 1: TOO MUCH DATA")
print("""
A small business might have 100 customers.

A large e-commerce company may have millions of customers.

Manually managing millions of records is impractical.

Databases provide systems for organizing and retrieving large volumes
of information.
""")

print("\nProblem 2: DIFFICULT SEARCHING")
print("""
Suppose a company has 10 million customer records.

The company may ask:

- Find customer 50125.
- Find all customers from Lucknow.
- Find customers who placed an order this month.
- Find customers whose spending exceeds 100,000.

A database system can execute structured queries to perform such tasks.
""")

print("\nProblem 3: DATA DUPLICATION")
print("""
Imagine the same customer information is stored in 20 different files.

If the customer's phone number changes, every copy might need to be
updated.

If one copy is updated and another is not, inconsistent information
can appear.

Database design attempts to reduce unnecessary duplication and improve
consistency.
""")

print("\nProblem 4: MULTIPLE USERS")
print("""
Modern systems are usually used by many people simultaneously.

For example:
- customers use an application
- employees use internal systems
- managers view reports
- administrators maintain infrastructure

A database system is designed to support controlled concurrent access.
""")

print("\nProblem 5: SECURITY")
print("""
Not everyone should be allowed to see or modify everything.

For example:
- Customers may see their own orders.
- Sales employees may manage customer information.
- Finance employees may access payment information.
- Database administrators may have much broader privileges.

Database systems provide mechanisms for authentication, authorization,
and access control.
""")

print("\nProblem 6: DATA RECOVERY")
print("""
Hardware can fail.
Software can crash.
Power can be interrupted.
Human mistakes can happen.

Important databases therefore need backup and recovery mechanisms.

The goal is to reduce the chance that valuable information is
permanently lost.
""")


# ============================================================
# 5. FILES VS DATABASES
# ============================================================

print("\n5. FILES VS DATABASES")
print("-" * 70)

print("""
A simple file can store data.

For example, a CSV file might contain:

customer_id,name,city
1,Anil,Lucknow
2,Neha,Delhi

Files are useful and are still widely used.

However, databases provide additional capabilities for structured
data management.

A simplified comparison:
""")

comparison = {
    "Simple file": [
        "Easy to create",
        "Useful for small datasets",
        "Limited concurrent access",
        "Limited querying capabilities",
        "Security and recovery depend heavily on surrounding software"
    ],
    "Database system": [
        "Designed for structured data management",
        "Efficient querying",
        "Supports multiple users",
        "Access control",
        "Transactions and consistency mechanisms",
        "Backup and recovery capabilities",
        "Can handle large and complex applications"
    ]
}

for category, points in comparison.items():
    print("\n" + category)
    for point in points:
        print(" -", point)

print("""
Important:

A database does not mean that files are useless.

Files are excellent for many purposes such as configuration,
data exchange, logs, exports, and temporary processing.

Databases become especially valuable when data must be managed
systematically and reliably by applications and users.
""")


# ============================================================
# 6. WHAT IS A DBMS?
# ============================================================

print("\n6. WHAT IS A DBMS?")
print("-" * 70)

print("""
DBMS stands for:

DATABASE MANAGEMENT SYSTEM

A DBMS is software that allows users and applications to create,
store, organize, retrieve, update, secure, and manage data in databases.

Think of it this way:

DATABASE
    = The organized collection of data

DBMS
    = The software system used to manage that data

APPLICATION
    = The software through which users may interact with the data
""")


# ============================================================
# 7. SIMPLE DBMS ANALOGY
# ============================================================

print("\n7. DBMS ANALOGY")
print("-" * 70)

print("""
Imagine a large library.

BOOKS
    = Data

SHELVES AND ORGANIZATION
    = Database structure

LIBRARIAN / LIBRARY MANAGEMENT SYSTEM
    = DBMS

PEOPLE ASKING FOR BOOKS
    = Users / applications

A person might ask:

'Find me a book about economics.'

The management system helps locate the requested information.

A DBMS performs a similar role for digital data, although real DBMSs
are far more sophisticated than a library.
""")


# ============================================================
# 8. EXAMPLES OF DBMS SOFTWARE
# ============================================================

print("\n8. EXAMPLES OF DBMS SOFTWARE")
print("-" * 70)

dbms_examples = [
    "MySQL",
    "PostgreSQL",
    "Oracle Database",
    "Microsoft SQL Server",
    "SQLite",
    "MongoDB"
]

for dbms in dbms_examples:
    print("-", dbms)

print("""
These systems differ in architecture, features, data models, use cases,
and query mechanisms.

MySQL, PostgreSQL, Oracle Database, Microsoft SQL Server, and SQLite
are commonly associated with relational database management.

MongoDB is commonly associated with the document-oriented NoSQL model.

The important beginner concept is not memorizing product names.

The important concept is understanding what a DBMS does.
""")


# ============================================================
# 9. DATABASE VS DBMS
# ============================================================

print("\n9. DATABASE VS DBMS")
print("-" * 70)

print("""
DATABASE:
A structured collection of data.

DBMS:
Software that manages the database.

For example:

Database:
    Customer records
    Product records
    Order records

DBMS:
    Stores the records
    Retrieves the records
    Updates the records
    Controls access
    Helps maintain consistency
    Handles database operations

A DBMS acts as the management layer between applications/users
and the stored data.
""")


# ============================================================
# 10. WHAT DOES A DBMS DO?
# ============================================================

print("\n10. MAJOR FUNCTIONS OF A DBMS")
print("-" * 70)

dbms_functions = [
    "Data storage",
    "Data retrieval",
    "Data insertion",
    "Data updating",
    "Data deletion",
    "Security and access control",
    "Transaction management",
    "Concurrency management",
    "Backup and recovery",
    "Data integrity",
    "Query processing",
    "Database administration"
]

for number, function in enumerate(dbms_functions, start=1):
    print(f"{number}. {function}")


# ============================================================
# 11. CRUD
# ============================================================

print("\n11. CRUD OPERATIONS")
print("-" * 70)

print("""
Many database applications perform four fundamental operations:

C = CREATE
R = READ
U = UPDATE
D = DELETE

These four operations are commonly called CRUD.
""")

products = [
    {"id": 1, "name": "Laptop", "price": 60000},
    {"id": 2, "name": "Mouse", "price": 1000}
]

print("Initial data:")
print(products)

print("\nCREATE - Add a new product")
products.append({"id": 3, "name": "Keyboard", "price": 2000})
print(products)

print("\nREAD - Retrieve products")
for product in products:
    print(product)

print("\nUPDATE - Change a price")
for product in products:
    if product["id"] == 2:
        product["price"] = 1200

print(products)

print("\nDELETE - Remove a product")
products = [product for product in products if product["id"] != 3]
print(products)

print("""
The Python example simulates CRUD.

A real DBMS performs these operations using its own storage engine,
query language, indexing mechanisms, transaction system, and other
internal components.
""")


# ============================================================
# 12. QUERYING DATA
# ============================================================

print("\n12. QUERYING DATA")
print("-" * 70)

employees = [
    {"id": 1, "name": "Amit", "department": "IT", "salary": 70000},
    {"id": 2, "name": "Neha", "department": "HR", "salary": 60000},
    {"id": 3, "name": "Rahul", "department": "IT", "salary": 90000},
    {"id": 4, "name": "Priya", "department": "Finance", "salary": 80000}
]

print("All employees:")
for employee in employees:
    print(employee)

print("\nEmployees from IT:")
for employee in employees:
    if employee["department"] == "IT":
        print(employee)

print("\nEmployees earning more than 75000:")
for employee in employees:
    if employee["salary"] > 75000:
        print(employee)

print("""
A database query allows us to ask questions about stored data.

In relational databases, SQL is commonly used for querying.

For example, conceptually:

SELECT * FROM employees
WHERE department = 'IT';

This asks the database to return employees belonging to the IT
department.
""")


# ============================================================
# 13. DATABASE USERS
# ============================================================

print("\n13. DATABASE USERS")
print("-" * 70)

print("""
Different people interact with databases for different reasons.

A database environment can include:

1. Database Administrators
2. Database Designers / Architects
3. Application Developers
4. Data Analysts
5. Data Engineers
6. Business Users
7. End Users
8. System / Infrastructure Administrators
""")


# ============================================================
# 14. DATABASE ADMINISTRATOR (DBA)
# ============================================================

print("\n14. DATABASE ADMINISTRATOR (DBA)")
print("-" * 70)

print("""
A Database Administrator, commonly called a DBA, is responsible for
managing and maintaining database systems.

Typical responsibilities may include:

- Database installation and configuration
- User management
- Access control
- Backup and recovery
- Performance monitoring
- Database maintenance
- Security management
- Troubleshooting
- Capacity planning
- High availability

A DBA is concerned with keeping database systems reliable, secure,
available, and performant.
""")


# ============================================================
# 15. DATABASE DESIGNER / ARCHITECT
# ============================================================

print("\n15. DATABASE DESIGNER / ARCHITECT")
print("-" * 70)

print("""
A database designer or architect focuses on how data should be
structured.

They may determine:

- What entities exist
- What attributes each entity has
- How entities relate
- Which fields uniquely identify records
- How tables should be organized
- How redundancy should be controlled
- What constraints should exist

Example:

CUSTOMER
    customer_id
    name
    email

ORDER
    order_id
    customer_id
    order_date

Here customer_id can connect an order to a customer.
""")


# ============================================================
# 16. APPLICATION DEVELOPERS
# ============================================================

print("\n16. APPLICATION DEVELOPERS")
print("-" * 70)

print("""
Application developers build software that interacts with databases.

Examples:

- Banking applications
- E-commerce websites
- Hospital systems
- Government portals
- School management systems
- Mobile applications

A developer may write application code that sends database queries
and processes the returned data.
""")

print("""
Simple conceptual flow:

USER
  |
  v
APPLICATION
  |
  v
DBMS
  |
  v
DATABASE
""")


# ============================================================
# 17. DATA ANALYSTS
# ============================================================

print("\n17. DATA ANALYSTS")
print("-" * 70)

print("""
Data analysts use stored data to answer business questions.

Examples:

- Which product sells the most?
- Which region generates the most revenue?
- What is the monthly sales trend?
- Which customers are most valuable?
- Which branch is underperforming?

Analysts commonly retrieve data from databases using SQL and then
analyze or visualize it using analytical tools.
""")


# ============================================================
# 18. DATA ENGINEERS
# ============================================================

print("\n18. DATA ENGINEERS")
print("-" * 70)

print("""
Data engineers build and maintain systems that move, transform,
store, and prepare data.

They may work with:

- Databases
- Data warehouses
- Data lakes
- ETL / ELT pipelines
- Cloud platforms
- Streaming systems
- Data integration tools

Their work helps make reliable data available for analytics,
reporting, applications, and machine learning.
""")


# ============================================================
# 19. BUSINESS USERS
# ============================================================

print("\n19. BUSINESS USERS")
print("-" * 70)

print("""
Business users may not directly manage the database.

Instead, they use applications, dashboards, reports, or business
intelligence tools that obtain information from databases.

Examples:

A sales manager might view:
    Total sales
    Monthly revenue
    Sales by region

A finance manager might view:
    Expenses
    Revenue
    Profit
    Outstanding payments

A human resources manager might view:
    Employee count
    Hiring trends
    Department distribution
""")


# ============================================================
# 20. END USERS
# ============================================================

print("\n20. END USERS")
print("-" * 70)

print("""
End users are people who interact with a software application
that uses a database.

For example, when a customer logs into an online shopping application:

Customer
   |
   v
Website / Mobile App
   |
   v
Application Server
   |
   v
Database
   |
   v
Customer's information

The customer may never know which database technology is being used.
""")


# ============================================================
# 21. DATABASE APPLICATIONS
# ============================================================

print("\n21. WHAT ARE DATABASE APPLICATIONS?")
print("-" * 70)

print("""
A database application is a software application that uses a
database to store, retrieve, update, or manage information.

Most modern digital systems depend on databases in some way.
""")


# ============================================================
# 22. E-COMMERCE APPLICATION
# ============================================================

print("\n22. E-COMMERCE")
print("-" * 70)

print("""
An e-commerce platform may store:

CUSTOMERS
PRODUCTS
ORDERS
PAYMENTS
SHIPPING
REVIEWS
INVENTORY

When a customer places an order:

1. The application identifies the customer.
2. Product information is retrieved.
3. Inventory is checked.
4. The order is recorded.
5. Payment information is processed through appropriate systems.
6. Inventory may be updated.
7. The order becomes available for tracking.
""")

print("Example order:")
order = {
    "order_id": 5001,
    "customer_id": 101,
    "product": "Laptop",
    "quantity": 1,
    "status": "Confirmed"
}

for key, value in order.items():
    print(f"{key}: {value}")


# ============================================================
# 23. BANKING APPLICATION
# ============================================================

print("\n23. BANKING SYSTEMS")
print("-" * 70)

print("""
Banks use databases for information such as:

- Customer accounts
- Account balances
- Transactions
- Loans
- Payments
- Branch information
- Customer profiles

Banking systems require particularly strong requirements around
correctness, security, availability, auditing, and transaction
processing.
""")


# ============================================================
# 24. HOSPITAL APPLICATION
# ============================================================

print("\n24. HOSPITAL SYSTEMS")
print("-" * 70)

print("""
A hospital database application may manage:

- Patient registration
- Doctor information
- Appointments
- Billing
- Laboratory records
- Pharmacy information
- Admission and discharge records

Different parts of the hospital may interact with shared information
according to their permissions.
""")


# ============================================================
# 25. EDUCATION APPLICATION
# ============================================================

print("\n25. EDUCATION SYSTEMS")
print("-" * 70)

print("""
A school or university system may store:

- Student profiles
- Courses
- Teachers
- Attendance
- Marks
- Examinations
- Fees
- Timetables

Students, teachers, administrators, and management may have different
levels of access.
""")


# ============================================================
# 26. GOVERNMENT APPLICATIONS
# ============================================================

print("\n26. GOVERNMENT SYSTEMS")
print("-" * 70)

print("""
Government organizations can use databases for:

- Citizen services
- Licenses
- Registrations
- Tax records
- Public administration
- Land records
- Welfare programs
- Case management
- Public infrastructure records

Large government systems may involve many databases and applications
working together.
""")


# ============================================================
# 27. SOCIAL MEDIA APPLICATIONS
# ============================================================

print("\n27. SOCIAL MEDIA")
print("-" * 70)

print("""
Social platforms may store information related to:

- User accounts
- Posts
- Comments
- Likes
- Followers
- Messages
- Notifications
- Media metadata

A social application may generate enormous amounts of data and may
therefore require highly scalable database infrastructure.
""")


# ============================================================
# 28. DATABASE STRUCTURE: TABLES
# ============================================================

print("\n28. TABLES, ROWS, AND COLUMNS")
print("-" * 70)

print("""
In a relational database, data is commonly organized into tables.

A TABLE is similar to a structured grid.

A ROW represents one record.

A COLUMN represents one attribute or field.
""")

students = [
    {"student_id": 1, "name": "Ravi", "age": 20, "course": "Python"},
    {"student_id": 2, "name": "Sneha", "age": 21, "course": "SQL"},
    {"student_id": 3, "name": "Arjun", "age": 22, "course": "Analytics"}
]

print("Student table:")
print("student_id | name  | age | course")
print("-" * 40)

for student in students:
    print(
        f"{student['student_id']:10} | "
        f"{student['name']:5} | "
        f"{student['age']:3} | "
        f"{student['course']}"
    )

print("""
Here:

Table  = students
Row    = one student's record
Column = student_id, name, age, or course
""")


# ============================================================
# 29. PRIMARY KEY
# ============================================================

print("\n29. PRIMARY KEY")
print("-" * 70)

print("""
A primary key is a field, or combination of fields, used to uniquely
identify a record in a relational table.

For the student table:

student_id

could serve as a primary key because each student should have a
unique identifier.
""")

student_ids = [student["student_id"] for student in students]

print("Student IDs:", student_ids)
print("Are IDs unique?", len(student_ids) == len(set(student_ids)))

print("""
A good identifier helps the database distinguish one record from
another.
""")


# ============================================================
# 30. RELATIONSHIPS
# ============================================================

print("\n30. RELATIONSHIPS BETWEEN DATA")
print("-" * 70)

print("""
One of the major strengths of relational databases is the ability to
represent relationships.

Example:

CUSTOMER
customer_id
name

ORDER
order_id
customer_id
amount

The customer_id in the order information tells us which customer
placed the order.
""")

customer = {"customer_id": 101, "name": "Rahul"}

order = {
    "order_id": 9001,
    "customer_id": 101,
    "amount": 25000
}

print("Customer:", customer)
print("Order:", order)

if customer["customer_id"] == order["customer_id"]:
    print("Relationship: Order belongs to", customer["name"])


# ============================================================
# 31. DATA INTEGRITY
# ============================================================

print("\n31. DATA INTEGRITY")
print("-" * 70)

print("""
Data integrity means maintaining the correctness, consistency, and
validity of data.

For example:

A customer's age should not normally be stored as:
    'banana'

A product price should not accidentally become:
    -999999999

An order should reference a valid customer when the database design
requires such a relationship.

Database systems provide constraints and other mechanisms to help
protect data integrity.
""")

valid_age = 33
invalid_age = -500

print("Valid age:", valid_age)
print("Invalid example:", invalid_age)

if valid_age >= 0:
    print("The age passes this simple validation.")

if invalid_age < 0:
    print("The second value fails this simple validation.")


# ============================================================
# 32. SECURITY AND ACCESS CONTROL
# ============================================================

print("\n32. DATABASE SECURITY")
print("-" * 70)

print("""
Database security controls who can access which information and
which operations they are allowed to perform.

Imagine:

CUSTOMER
    Can view their own orders.

SALES EMPLOYEE
    Can manage customer and order information.

FINANCE EMPLOYEE
    Can access financial information.

DATABASE ADMINISTRATOR
    Can perform administrative operations.

Different roles can have different permissions.
""")

users = {
    "customer": ["read_own_orders"],
    "sales_employee": ["read_customers", "create_orders", "update_orders"],
    "finance_employee": ["read_payments", "update_payments"],
    "database_admin": ["manage_database"]
}

for role, permissions in users.items():
    print(f"{role}: {permissions}")


# ============================================================
# 33. CONCURRENCY
# ============================================================

print("\n33. MULTIPLE USERS AND CONCURRENCY")
print("-" * 70)

print("""
Suppose two customers try to purchase the last available product
at nearly the same time.

Customer A sees:
    Stock = 1

Customer B sees:
    Stock = 1

If the system is poorly designed, both may successfully purchase the
same last item.

Database systems use transaction and concurrency mechanisms to help
prevent such consistency problems.

Concurrency means dealing with multiple operations occurring at the
same time or overlapping in execution.
""")


# ============================================================
# 34. TRANSACTIONS
# ============================================================

print("\n34. TRANSACTIONS")
print("-" * 70)

print("""
A transaction is a logical unit of database work.

Consider transferring money:

Account A:
    -1000

Account B:
    +1000

Both operations belong to one logical transaction.

We generally do not want the first operation to permanently happen
while the second operation fails without proper handling.

Database transaction mechanisms help maintain reliable state changes.

Transactions are especially important in systems such as:
- Banking
- Payments
- Orders
- Inventory
- Financial systems
""")


# ============================================================
# 35. BACKUP AND RECOVERY
# ============================================================

print("\n35. BACKUP AND RECOVERY")
print("-" * 70)

print("""
Backup means creating additional copies of data so it can potentially
be restored after loss or corruption.

Recovery is the process of restoring the database or returning it to
a usable and consistent state after a failure.

Possible failures include:
- Hardware failure
- Software failure
- Human error
- Accidental deletion
- System crash
- Infrastructure problems

A professional database environment should have a carefully designed
backup and recovery strategy.
""")


# ============================================================
# 36. DATABASE PERFORMANCE
# ============================================================

print("\n36. DATABASE PERFORMANCE")
print("-" * 70)

print("""
As databases become large, simply storing data is not enough.

Applications need fast access.

For example:

Find customer with ID 5000000.

If the database must examine every single record, the operation may
be inefficient.

Database systems can use structures such as indexes to accelerate
certain types of searches.
""")

numbers = list(range(1, 11))

target = 7

print("Data:", numbers)
print("Searching for:", target)

for number in numbers:
    if number == target:
        print("Found:", number)
        break

print("""
This Python example is only a simple illustration.

Real database indexing techniques are much more sophisticated.
""")


# ============================================================
# 37. DATABASE APPLICATION ARCHITECTURE
# ============================================================

print("\n37. DATABASE APPLICATION ARCHITECTURE")
print("-" * 70)

print("""
A common application architecture looks conceptually like this:

USER
  |
  v
FRONTEND
  |
  v
APPLICATION / BACKEND
  |
  v
DBMS
  |
  v
DATABASE

Example:

A customer clicks 'My Orders'.

1. The frontend sends a request.
2. The backend processes the request.
3. The backend sends a query to the DBMS.
4. The DBMS retrieves the appropriate data.
5. The result returns to the application.
6. The frontend displays the orders.
""")


# ============================================================
# 38. REAL-WORLD EXAMPLE
# ============================================================

print("\n38. COMPLETE REAL-WORLD EXAMPLE: ONLINE SHOPPING")
print("-" * 70)

print("""
Imagine an online shopping application.

DATABASE MAY CONTAIN:

Customers
Products
Orders
Order Items
Payments
Addresses
Inventory
Reviews

When a customer searches for a product:

USER
  |
  v
SHOPPING WEBSITE
  |
  v
APPLICATION SERVER
  |
  v
DBMS
  |
  v
PRODUCT DATA

When the customer purchases it:

Customer
   |
   v
Create Order
   |
   +----> Update Inventory
   |
   +----> Record Payment
   |
   +----> Store Shipping Information
   |
   +----> Generate Order Status

This demonstrates why databases are foundational to modern
applications.
""")


# ============================================================
# 39. DATABASE ECOSYSTEM
# ============================================================

print("\n39. DATABASE ECOSYSTEM")
print("-" * 70)

print("""
A real organization may have many different data technologies.

Examples:

APPLICATION DATABASES
    Store operational application data.

DATA WAREHOUSES
    Store and organize data for analytics and reporting.

DATA LAKES
    Can store large amounts of raw or semi-structured data.

CACHE SYSTEMS
    Keep frequently needed information available for faster access.

DATABASE ADMINISTRATION TOOLS
    Help monitor and manage database environments.

ANALYTICS TOOLS
    Use stored data to produce reports and insights.
""")


# ============================================================
# 40. RELATIONAL VS NON-RELATIONAL DATABASES
# ============================================================

print("\n40. RELATIONAL AND NON-RELATIONAL DATABASES")
print("-" * 70)

print("""
Relational databases commonly organize data into tables and use
relationships between tables.

Examples:
- PostgreSQL
- MySQL
- Oracle Database
- Microsoft SQL Server
- SQLite

Non-relational databases, often called NoSQL databases, can use other
data models.

Examples include:
- Document databases
- Key-value databases
- Wide-column databases
- Graph databases

The choice depends on the application's requirements.
""")


# ============================================================
# 41. WHY BUSINESSES CARE ABOUT DATABASES
# ============================================================

print("\n41. WHY BUSINESSES CARE ABOUT DATABASES")
print("-" * 70)

print("""
Databases are not only a technical concept.

They directly support business operations.

A business needs data to answer questions such as:

- Who are our customers?
- What are we selling?
- How much are we selling?
- Which products are profitable?
- Where are our customers located?
- What inventory is available?
- Which employees are assigned to which operations?
- What payments are pending?
- What trends are developing?

Reliable data supports:

OPERATIONS
    Running day-to-day activities.

ANALYTICS
    Understanding what happened and why.

DECISION-MAKING
    Choosing what to do next.

AUTOMATION
    Allowing software to perform tasks based on stored information.

COMPLIANCE
    Maintaining required records and controls.
""")


# ============================================================
# 42. IMPORTANT VOCABULARY
# ============================================================

print("\n42. IMPORTANT DATABASE VOCABULARY")
print("-" * 70)

terms = {
    "Data": "Individual facts or values.",
    "Database": "Organized collection of data.",
    "DBMS": "Software used to manage databases.",
    "Table": "Structured collection of rows and columns in a relational database.",
    "Row": "One record in a table.",
    "Column": "An attribute or field in a table.",
    "Primary Key": "Field or fields that uniquely identify a record.",
    "Query": "Request for information or an operation on data.",
    "CRUD": "Create, Read, Update, Delete.",
    "Transaction": "Logical unit of database operations.",
    "Integrity": "Correctness and consistency of data.",
    "Concurrency": "Handling multiple operations/users.",
    "Backup": "Copy of data used for protection and restoration.",
    "Recovery": "Returning data/system to a usable state after failure."
}

for term, definition in terms.items():
    print(f"{term}: {definition}")


# ============================================================
# 43. MINI DATABASE SIMULATION
# ============================================================

print("\n43. MINI DATABASE SIMULATION")
print("-" * 70)

database = {
    "customers": [],
    "products": [],
    "orders": []
}

print("Empty database:")
print(database)

print("\nAdding customer...")
database["customers"].append({
    "customer_id": 1,
    "name": "Atul",
    "city": "Lucknow"
})

print("\nAdding product...")
database["products"].append({
    "product_id": 101,
    "name": "Laptop",
    "price": 65000
})

print("\nCreating order...")
database["orders"].append({
    "order_id": 1001,
    "customer_id": 1,
    "product_id": 101,
    "quantity": 1
})

print("\nCurrent database-like structure:")
for table_name, records in database.items():
    print(f"\n{table_name.upper()}")
    for record in records:
        print(record)

print("""
This dictionary is only a learning simulation.

A production database provides sophisticated storage, querying,
transactions, security, concurrency, recovery, indexing, and
administration capabilities that a Python dictionary does not provide.
""")


# ============================================================
# 44. BIG PICTURE
# ============================================================

print("\n44. THE BIG PICTURE")
print("-" * 70)

print("""
The complete idea can be remembered as:

DATA
  |
  v
DATABASE
  |
  v
DBMS
  |
  v
APPLICATION
  |
  v
USERS

DATA
    Facts and information.

DATABASE
    Organized collection of data.

DBMS
    Software that manages the database.

APPLICATION
    Software that uses the database to perform useful tasks.

USERS
    People or systems that interact with the application/database.
""")


# ============================================================
# 45. FINAL SUMMARY
# ============================================================

print("\n45. FINAL SUMMARY")
print("-" * 70)

print("""
1. Data consists of facts and values.

2. A database is an organized collection of data.

3. Databases exist because organizations need to store, retrieve,
   update, secure, and manage growing amounts of information.

4. A DBMS is software that manages databases.

5. DBMSs provide capabilities such as querying, security, transactions,
   concurrency management, integrity, backup, and recovery.

6. Database users include DBAs, database designers, developers,
   analysts, engineers, business users, and end users.

7. Database applications are found in e-commerce, banking, healthcare,
   education, government, social media, logistics, finance, and almost
   every modern digital industry.

8. Relational databases commonly organize information into tables,
   rows, and columns.

9. Relationships allow related data to be connected.

10. CRUD stands for Create, Read, Update, and Delete.

11. Databases are a foundation of modern software and business
    information systems.
""")


print("=" * 70)
print("END OF INTRODUCTION TO DATABASES")
print("=" * 70)

