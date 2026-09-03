````markdown
# Database Architecture

## Overview

Database architecture describes how different components of a database system work together to store, retrieve, modify, protect, and manage data.

The major components studied are:

- Database Client
- Database Server
- Connection Layer
- Query Engine
- Storage Engine

A modern database system also contains supporting components such as:

- Query Parser
- Query Analyzer
- Query Optimizer
- Query Executor
- Transaction Manager
- Concurrency Control
- Buffer Cache
- Index Manager
- Logging System
- Recovery System
- Replication System
- Partitioning and Sharding
- Authentication and Authorization
- Backup and Disaster Recovery
- Monitoring and Observability

---

## What is a Database?

A database is an organized system for storing, managing, retrieving, and modifying data.

For example, an e-commerce database may contain:

- Customers
- Products
- Orders
- Payments
- Inventory
- Addresses

A Database Management System (DBMS) is the software responsible for managing this data.

Examples include:

- PostgreSQL
- MySQL
- Microsoft SQL Server
- Oracle Database
- SQLite
- MongoDB
- Redis

The database contains the data, while the DBMS provides the mechanisms required to work with that data.

---

## What is Database Architecture?

Database architecture describes the internal organization of a database system and the way its components communicate.

A simplified architecture is:

```text
Application
    |
    v
Database Client
    |
    v
Connection Layer
    |
    v
Database Server
    |
    v
Query Engine
    |
    v
Storage Engine
    |
    v
Physical Storage
````

A more detailed architecture is:

```text
Application
    |
    v
Database Driver / Client
    |
    v
Connection Layer
    |
    v
Database Server
    |
    +----------------------+
    |                      |
    v                      v
Authentication       Session Manager
    |
    v
SQL Processing
    |
    +---- Parser
    |
    +---- Analyzer
    |
    +---- Query Optimizer
    |
    +---- Query Executor
    |
    v
Transaction Manager
    |
    v
Concurrency Control
    |
    v
Buffer / Cache
    |
    v
Storage Engine
    |
    +---- Tables
    +---- Indexes
    +---- Pages
    +---- Logs
    |
    v
Disk / SSD
```

---

# 1. Database Client

A database client is the application or software component that communicates with the database.

Examples include:

* Python applications
* Java applications
* Web applications
* Command-line SQL clients
* Database GUI applications
* Business intelligence tools
* Data pipelines
* Backend services

A Python application can act as a database client.

For example:

```text
Python Application
        |
        v
Database Driver
        |
        v
PostgreSQL Server
```

The database client can:

* Open connections
* Send SQL queries
* Send query parameters
* Receive query results
* Commit transactions
* Roll back transactions
* Handle database errors
* Close connections

The client normally does not directly manipulate the database's physical storage.

---

# 2. Database Server

A database server is the software process that manages database operations for clients.

The server is responsible for coordinating:

* Client connections
* Authentication
* Authorization
* Query execution
* Transactions
* Concurrency
* Locks
* Caching
* Storage access
* Logging
* Recovery
* Replication

Multiple clients can communicate with the same database server:

```text
Client A ----\
Client B -----\
Client C ------> Database Server
Client D -----/
Client E ----/
```

The server coordinates these requests and ensures that database rules are followed.

---

# 3. Connection Layer

The connection layer establishes and maintains communication between a client and a database server.

A simplified process is:

```text
Client
   |
   | Connect
   v
Network
   |
   v
Database Server
   |
   | Authenticate
   v
Database Session
   |
   v
Query Execution
```

A connection can contain information such as:

* Host
* Port
* Username
* Authentication information
* Database name
* Session configuration

Common database ports include:

```text
PostgreSQL -> 5432
MySQL      -> 3306
```

A connection is not the same thing as a query.

A connection means:

> Establish communication with the database.

A query means:

> Ask the database to perform an operation.

---

# 4. Database Session

After a client establishes a connection, the database server may create a session.

A session can maintain:

* Authenticated user information
* Transaction state
* Temporary tables
* Session variables
* Isolation settings
* Connection-specific configuration

Conceptually:

```text
Connection
    |
    v
Session
    |
    +---- Query 1
    +---- Query 2
    +---- Query 3
    +---- Transaction
```

---

# 5. Query Engine

The query engine is responsible for understanding and executing database queries.

Consider:

```sql
SELECT name
FROM employees
WHERE salary > 50000;
```

The database does not simply read this SQL string and immediately access the disk.

It normally processes the query through multiple stages:

```text
SQL Query
    |
    v
Parser
    |
    v
Query Analyzer
    |
    v
Query Optimizer
    |
    v
Execution Plan
    |
    v
Query Executor
    |
    v
Storage Engine
    |
    v
Results
```

The major components of a query engine include:

* Parser
* Analyzer
* Optimizer
* Executor

---

# 6. SQL Parser

The parser checks whether SQL follows the database's syntax.

Valid SQL:

```sql
SELECT name FROM employees;
```

Invalid SQL:

```sql
SELECT FROM employees;
```

The parser converts SQL text into an internal representation that the database can understand.

Conceptually:

```text
SQL Text
   |
   v
Tokens
   |
   v
Syntax Tree
   |
   v
Internal Query Representation
```

---

# 7. Query Analyzer

After parsing, the database needs to determine whether the query makes semantic sense.

For example:

```sql
SELECT employee_name
FROM employees;
```

If `employee_name` does not exist, the query will fail.

The analyzer may validate:

* Tables
* Columns
* Data types
* Functions
* Relationships
* Permissions
* Database objects

The parser answers:

> Is the SQL syntactically correct?

The analyzer answers:

> Does this SQL make sense for this database?

---

# 8. Query Optimizer

The query optimizer attempts to find an efficient way to execute a query.

Consider:

```sql
SELECT *
FROM employees
WHERE department_id = 10;
```

The database might execute this query using:

```text
Sequential Scan
```

or:

```text
Index Scan
```

The optimizer evaluates possible strategies and estimates their cost.

It can consider:

* Table size
* Indexes
* Selectivity
* Join algorithms
* Available memory
* Sorting requirements
* Filtering cost
* Disk I/O
* Database statistics

The optimizer then selects an execution plan.

This is one of the most important concepts in database performance engineering.

---

# 9. Execution Plan

An execution plan describes how a database intends to execute a query.

Common operations include:

* Sequential Scan
* Index Scan
* Index Seek
* Nested Loop Join
* Hash Join
* Merge Join
* Sort
* Aggregate
* Filter
* Group By

A conceptual execution plan might look like:

```text
Index Scan
    |
    v
Filter
    |
    v
Return Rows
```

A JOIN might look like:

```text
Table A
   |
   v
Hash Join
   ^
   |
Table B
```

Execution plans are extremely important when investigating slow SQL queries.

---

# 10. Query Executor

The query executor performs the operations selected by the optimizer.

The complete query-processing pipeline is:

```text
SQL
 |
 v
Parser
 |
 v
Analyzer
 |
 v
Optimizer
 |
 v
Execution Plan
 |
 v
Executor
 |
 v
Storage Engine
 |
 v
Result
```

---

# 11. Storage Engine

The storage engine manages the physical storage and retrieval of database data.

It deals with concepts such as:

* Tables
* Rows
* Pages
* Indexes
* Buffer management
* Data files
* Logs
* Persistent storage

The query engine asks for logical data.

The storage engine determines how that data is physically stored and retrieved.

```text
Query Engine
     |
     v
Storage Engine
     |
     v
Database Pages
     |
     v
Disk / SSD
```

---

# 12. Database Pages

Databases generally organize physical storage into pages or blocks.

Conceptually:

```text
Database File
---------------------------------
| Page 1 | Page 2 | Page 3 | ... |
---------------------------------
```

A page can contain multiple records.

Databases commonly read and write pages instead of treating every individual row as an independent physical I/O operation.

Efficient page management is important because storage I/O can be significantly more expensive than CPU and memory operations.

---

# 13. Rows and Records

A relational table contains rows and columns.

Example:

```text
id | name    | salary
---------------------
1  | Alice   | 50000
2  | Bob     | 60000
3  | Charlie | 70000
```

A row represents a record.

A column represents an attribute of the record.

The storage engine determines how these records are physically represented.

---

# 14. Indexes

An index is a data structure that helps the database locate records efficiently.

Without an appropriate index, a database may need to inspect many or all rows.

With a suitable index, the database can often locate matching records much faster.

Example:

```sql
CREATE INDEX idx_employee_salary
ON employees(salary);
```

Common index structures include:

* B-tree
* B+ tree
* Hash index
* Bitmap index
* GiST
* GIN
* LSM-tree-based structures

Indexes can improve:

* Filtering
* Searching
* Lookups
* Ordering in appropriate cases

But indexes also have costs:

* Additional storage
* Slower INSERT operations
* Slower UPDATE operations
* Slower DELETE operations
* Maintenance overhead

Therefore:

> More indexes do not automatically mean better database performance.

---

# 15. Complete Query Lifecycle

Consider:

```sql
SELECT name
FROM employees
WHERE salary > 50000;
```

The complete lifecycle can be understood as:

```text
Python Application
       |
       v
Database Driver
       |
       v
Connection Layer
       |
       v
Database Server
       |
       v
SQL Parser
       |
       v
Query Analyzer
       |
       v
Query Optimizer
       |
       v
Execution Plan
       |
       v
Query Executor
       |
       v
Storage Engine
       |
       v
Buffer / Cache
       |
       v
Disk / SSD
       |
       v
Rows Returned
       |
       v
Database Server
       |
       v
Database Client
       |
       v
Python Application
```

This is one of the most important mental models for understanding database architecture.

---

# 16. CRUD Operations

CRUD represents four fundamental database operations:

```text
C = Create
R = Read
U = Update
D = Delete
```

Typical SQL commands are:

```text
Create -> INSERT
Read   -> SELECT
Update -> UPDATE
Delete -> DELETE
```

Example:

```sql
INSERT INTO employees
(id, name, salary)
VALUES
(1, 'Alice', 80000);
```

```sql
SELECT *
FROM employees;
```

```sql
UPDATE employees
SET salary = 85000
WHERE id = 1;
```

```sql
DELETE FROM employees
WHERE id = 1;
```

---

# 17. Python and SQLite

Python provides the built-in `sqlite3` module for working with SQLite.

Example:

```python
import sqlite3

connection = sqlite3.connect(":memory:")

cursor = connection.cursor()

cursor.execute("""
    CREATE TABLE employees (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        department TEXT,
        salary REAL
    )
""")

cursor.execute("""
    INSERT INTO employees
    (id, name, department, salary)
    VALUES (?, ?, ?, ?)
""", (1, "Alice", "Engineering", 80000))

connection.commit()

cursor.execute("""
    SELECT *
    FROM employees
""")

rows = cursor.fetchall()

for row in rows:
    print(row)

connection.close()
```

SQLite is useful for learning because it is generally embedded into the application rather than requiring a separate database server process.

---

# 18. Parameterized Queries

Parameterized queries are essential for protecting applications against SQL injection.

Unsafe approach:

```python
query = "SELECT * FROM users WHERE name = '" + username + "'"
```

Safer approach:

```python
cursor.execute(
    "SELECT * FROM users WHERE name = ?",
    (username,)
)
```

The important principle is:

```text
SQL Code
   +
User Data
```

should remain logically separate.

---

# 19. Transactions

A transaction is a logical unit of database work.

Consider a bank transfer:

```text
Account A
    |
    | Subtract ₹1000
    v
Account B
    |
    | Add ₹1000
    v
Commit
```

Both operations should succeed together.

A transaction may look like:

```text
BEGIN
  |
  v
UPDATE Account A
  |
  v
UPDATE Account B
  |
  v
COMMIT
```

If an error occurs:

```text
BEGIN
  |
  v
UPDATE Account A
  |
  v
UPDATE Account B
  |
  X
ROLLBACK
```

---

# 20. ACID Properties

ACID represents four important transaction properties.

## Atomicity

A transaction is treated as one logical unit.

Either all required operations succeed or the transaction is rolled back.

## Consistency

A transaction should move the database from one valid state to another valid state.

Database constraints and application rules help maintain consistency.

## Isolation

Concurrent transactions should not interfere with one another in unacceptable ways.

Different isolation levels provide different guarantees.

## Durability

Once a transaction is committed, its effects should survive system failures according to the database's durability guarantees.

Logging and persistent storage mechanisms help provide durability.

---

# 21. Concurrency

A database may serve many users at the same time.

For example:

```text
User A -> UPDATE account
User B -> UPDATE account
User C -> SELECT account
User D -> INSERT transaction
```

The database must coordinate these operations.

This is called concurrency control.

---

# 22. Locks

Database systems may use locks to coordinate concurrent operations.

Two important conceptual lock types are:

* Shared Lock
* Exclusive Lock

A shared lock generally allows multiple readers.

An exclusive lock is typically required for modifications that need exclusive access to affected data.

Conceptually:

```text
Transaction
     |
     v
Acquire Lock
     |
     v
Perform Operation
     |
     v
Commit
     |
     v
Release Lock
```

---

# 23. Deadlocks

A deadlock occurs when transactions wait for each other indefinitely.

Example:

```text
Transaction A locks Row 1
Transaction B locks Row 2

A waits for Row 2
B waits for Row 1
```

This produces:

```text
A -> waiting for B
B -> waiting for A
```

Database systems may use:

* Deadlock detection
* Timeouts
* Consistent lock ordering
* Transaction rollback

---

# 24. Isolation Levels

Common SQL isolation levels include:

* READ UNCOMMITTED
* READ COMMITTED
* REPEATABLE READ
* SERIALIZABLE

Common transaction anomalies include:

### Dirty Read

A transaction reads data that another transaction has not committed.

### Non-repeatable Read

A transaction reads the same row twice and obtains different values because another transaction modified it.

### Phantom Read

A repeated query returns a different set of matching rows because another transaction inserted or deleted records.

Higher isolation generally provides stronger consistency guarantees but may reduce concurrency or increase contention.

---

# 25. Connection Pooling

Creating a database connection can involve overhead.

Instead of repeatedly doing:

```text
Connect
Query
Disconnect
```

applications can use connection pooling.

Architecture:

```text
              Connection Pool
             /       |       \
            C1      C2       C3
             \       |       /
              Application
```

The application:

1. Acquires a connection.
2. Executes database operations.
3. Returns the connection to the pool.

Benefits include:

* Lower connection overhead
* Better performance
* Controlled concurrency
* Reduced connection pressure on the database

---

# 26. Buffer Cache

Memory is generally much faster than persistent storage.

Database systems therefore use memory to cache frequently accessed pages.

```text
Query
  |
  v
Buffer Cache
  |
  +---- Cache Hit ----> Return Data
  |
  +---- Cache Miss ---> Read From Disk
```

A cache hit means required data is already available in memory.

A cache miss means the database must load the required page from storage.

---

# 27. Write-Ahead Logging

Write-Ahead Logging, commonly known as WAL, is an important technique used by many database systems.

The basic principle is:

```text
Write Log Record
       |
       v
Durable Storage
       |
       v
Write / Update Data Page
```

The database records a change in a durable log before the corresponding data page is persisted according to the system's logging rules.

WAL can support:

* Durability
* Crash recovery
* Replication
* Point-in-time recovery in systems that support it

---

# 28. Crash Recovery

Databases can crash because of:

* Hardware failure
* Power failure
* Operating system failure
* Software bugs
* Storage failure

Recovery mechanisms use logs and other metadata to restore the database to a consistent state.

Conceptually:

```text
Database Crash
      |
      v
Database Restart
      |
      v
Read Recovery Information
      |
      v
Redo / Undo Operations
      |
      v
Consistent Database
```

---

# 29. Caching

Caching reduces repeated expensive database operations.

A common architecture is:

```text
Application
    |
    v
  Cache
   /  \
 Hit  Miss
 |      |
 |      v
 |    Database
 |      |
 |      v
 \----> Cache
    |
    v
 Result
```

Caching can be useful for:

* Frequently accessed data
* Sessions
* Configuration
* Computed results
* Rate limiting

Common external caching systems include:

* Redis
* Memcached

Caching introduces challenges such as:

* Stale data
* Cache invalidation
* Consistency
* Memory limitations

---

# 30. Cache-Aside Pattern

A common caching strategy is cache-aside.

The process is:

1. Application checks the cache.
2. If the data exists, return it.
3. If the data does not exist, query the database.
4. Store the database result in the cache.
5. Return the result.

Conceptually:

```text
Application
     |
     v
Check Cache
   /     \
 Hit     Miss
 |         |
 v         v
Return   Database
           |
           v
         Cache
```

---

# 31. Query Optimization

Database performance depends heavily on query design.

Instead of:

```sql
SELECT *
FROM employees;
```

when only a few columns are required, use:

```sql
SELECT name, salary
FROM employees
WHERE department = 'Engineering';
```

Useful optimization practices include:

* Select only required columns
* Filter data appropriately
* Use suitable indexes
* Avoid unnecessary joins
* Inspect execution plans
* Avoid unnecessary sorting
* Use pagination
* Use appropriate data types
* Maintain database statistics
* Avoid N+1 queries

---

# 32. N+1 Query Problem

The N+1 problem occurs when an application performs:

```text
1 query to retrieve N records
+
1 query for each individual record
```

For 100 customers:

```text
1 query for customers
+
100 queries for orders

=
101 queries
```

This can often be improved through:

* JOINs
* Batch queries
* Eager loading
* Appropriate ORM strategies

---

# 33. Database Normalization

Normalization organizes relational data to reduce unnecessary redundancy and improve consistency.

Common normal forms include:

* First Normal Form (1NF)
* Second Normal Form (2NF)
* Third Normal Form (3NF)
* Boyce-Codd Normal Form (BCNF)
* Fourth Normal Form (4NF)
* Fifth Normal Form (5NF)

Poor design:

```text
customer_id
customer_name
product_1
product_2
product_3
```

A relational design could instead use:

```text
Customers
Products
Orders
OrderItems
```

Normalization reduces redundancy, although highly normalized schemas may require more joins.

Production systems sometimes use controlled denormalization for performance.

---

# 34. OLTP

OLTP stands for Online Transaction Processing.

Typical OLTP systems include:

* Banking
* E-commerce
* Payments
* Inventory
* Booking
* Order management

Characteristics include:

* Many concurrent users
* Short transactions
* Frequent INSERT operations
* Frequent UPDATE operations
* Frequent DELETE operations
* Strong consistency requirements
* Low latency requirements

---

# 35. OLAP

OLAP stands for Online Analytical Processing.

Typical OLAP workloads include:

* Business intelligence
* Reporting
* Dashboards
* Data warehouses
* Analytical systems

Characteristics include:

* Large data scans
* Aggregations
* Historical data
* Complex queries
* Large datasets

Example:

```sql
SELECT
    department,
    AVG(salary)
FROM employees
GROUP BY department;
```

---

# 36. Row-Oriented Storage

Row-oriented storage keeps the fields belonging to a record together.

Example:

```text
Row 1:
id | name | department | salary

Row 2:
id | name | department | salary
```

Row-oriented storage is often useful for transactional workloads where complete records are frequently accessed or modified.

---

# 37. Column-Oriented Storage

Column-oriented storage organizes data by columns.

Conceptually:

```text
ID:
1, 2, 3, 4

Salary:
50000, 60000, 70000, 80000
```

Columnar storage can be highly efficient for analytical workloads where queries scan a small number of columns across many records.

Columnar systems can benefit from:

* Compression
* Vectorized execution
* Analytical scans

---

# 38. Replication

Replication means maintaining copies of database data across multiple nodes.

Example:

```text
              Primary
                 |
        +--------+--------+
        |                 |
        v                 v
     Replica 1         Replica 2
```

Replication can improve:

* Availability
* Read scalability
* Disaster recovery
* Geographic distribution

Common models include:

* Primary-replica
* Multi-primary
* Synchronous replication
* Asynchronous replication

---

# 39. Synchronous Replication

With synchronous replication, a write may wait for required replicas to acknowledge the operation before the transaction is considered committed according to the system's configuration.

Advantages:

* Stronger consistency guarantees

Potential disadvantages:

* Higher latency
* Dependence on replica availability

---

# 40. Asynchronous Replication

With asynchronous replication:

```text
Primary
   |
   v
Commit
   |
   v
Client receives result
   |
   v
Replica receives changes later
```

Advantages:

* Lower write latency
* Easier geographic replication

Disadvantage:

* Replication lag

A replica may temporarily contain older data than the primary.

---

# 41. Partitioning

Partitioning divides a large logical table into smaller physical partitions.

Example:

```text
Orders

Partition 2024
Partition 2025
Partition 2026
```

Common approaches include:

* Range partitioning
* List partitioning
* Hash partitioning

Partitioning can help with:

* Query performance
* Maintenance
* Data lifecycle management
* Partition pruning

---

# 42. Sharding

Sharding distributes data across multiple database nodes.

Example:

```text
Shard 1 -> Customers A-F
Shard 2 -> Customers G-M
Shard 3 -> Customers N-S
Shard 4 -> Customers T-Z
```

Benefits include:

* Horizontal scaling
* Larger total storage capacity
* Distributed workloads

Challenges include:

* Cross-shard queries
* Distributed transactions
* Rebalancing
* Shard key selection
* Operational complexity

---

# 43. Shard Key

A shard key determines where data is stored.

A good shard key should ideally:

* Distribute data evenly
* Distribute traffic evenly
* Support common queries
* Avoid hotspots

A poor shard key can cause:

* Hot shards
* Uneven storage
* Uneven traffic
* Poor scalability

Shard-key selection is one of the most important decisions in a sharded architecture.

---

# 44. Consistent Hashing

Consistent hashing is a technique used in distributed systems to distribute keys among nodes while minimizing data movement when nodes are added or removed.

It is commonly discussed in relation to:

* Distributed caches
* Partitioning
* Distributed databases

Conceptually:

```text
            Node A
              |
       +------+------+
       |             |
     Node D         Node B
       |             |
       +-----Node C--+
```

Keys are mapped to positions on the hashing ring.

---

# 45. CAP Theorem

CAP represents:

* Consistency
* Availability
* Partition Tolerance

The important CAP scenario is a network partition.

When a distributed system experiences a partition, it must make a trade-off between consistency and availability.

CAP should not be simplified into the statement:

> A system permanently chooses only two of three properties.

The more useful understanding is that network partitions force distributed systems to make consistency and availability trade-offs.

---

# 46. Consistency Models

Distributed databases can provide different consistency models.

Examples include:

* Strong consistency
* Eventual consistency
* Causal consistency

Strong consistency provides stronger guarantees about what values reads can observe.

Eventual consistency allows temporary differences between replicas with the expectation that replicas converge when updates stop.

---

# 47. Eventual Consistency

A simplified example:

```text
User writes data
      |
      v
Replica A updated
      |
      v
Replication
      |
      v
Replica B updated
```

During replication delay, Replica B may return older data.

After replication completes:

```text
Replica A == Replica B
```

Eventual consistency can be useful in highly distributed systems where temporary inconsistency is acceptable.

---

# 48. Database Security

Database architecture must include security.

Important mechanisms include:

* Authentication
* Authorization
* Encryption
* Auditing
* Network security
* Secrets management
* Least privilege
* Backup security
* Row-level security where supported

Authentication asks:

> Who are you?

Authorization asks:

> What are you allowed to do?

---

# 49. SQL Injection

SQL injection occurs when untrusted input is interpreted as SQL code.

Unsafe:

```python
query = "SELECT * FROM users WHERE name = '" + user_input + "'"
```

Safer:

```python
cursor.execute(
    "SELECT * FROM users WHERE name = ?",
    (user_input,)
)
```

Parameterized queries are a fundamental defense against SQL injection.

---

# 50. Database Connection Failures

Production applications must assume that database connections can fail.

Possible causes include:

* Database restart
* Network failure
* Timeout
* Overloaded database server
* Connection exhaustion
* Firewall problems
* DNS problems

Applications may use:

* Timeouts
* Connection pooling
* Controlled retries
* Exponential backoff
* Jitter
* Circuit breakers
* Health checks
* Monitoring

---

# 51. Retry Strategies

Retries should be carefully designed.

A poor strategy is:

```text
Retry forever immediately
```

A better strategy may use:

```text
Limited retries
+
Exponential backoff
+
Jitter
+
Idempotency awareness
```

Example:

```text
Attempt 1 -> wait 0.5 seconds
Attempt 2 -> wait 1 second
Attempt 3 -> wait 2 seconds
```

Retries can be dangerous for non-idempotent operations.

---

# 52. Idempotency

An operation is idempotent when repeating it produces the same intended final effect.

Example:

```text
SET account_status = 'ACTIVE'
```

Repeated execution results in the same intended state.

Compare this with:

```text
balance = balance + 100
```

Repeating this operation changes the result each time.

Idempotency is important in:

* APIs
* Distributed systems
* Payment systems
* Message processing
* Retry mechanisms

---

# 53. High Availability

High availability aims to keep services operational despite component failures.

A simplified architecture is:

```text
                Load Balancer
                      |
             +--------+--------+
             |                 |
             v                 v
        Application 1     Application 2
             |                 |
             +--------+--------+
                      |
                 Database Cluster
                 /              \
             Primary          Replica
```

The goal is to avoid a single component failure causing complete service outage.

---

# 54. Disaster Recovery

Disaster recovery deals with major failures such as:

* Data center outages
* Hardware failures
* Accidental deletion
* Data corruption
* Ransomware
* Regional outages

Two important concepts are:

## RPO

Recovery Point Objective defines how much data loss can be tolerated.

Example:

```text
RPO = 5 minutes
```

This indicates that the recovery strategy targets approximately five minutes or less of potential data loss, depending on the exact system design.

## RTO

Recovery Time Objective defines how quickly service should be restored.

Example:

```text
RTO = 30 minutes
```

This means the recovery target is approximately thirty minutes.

---

# 55. Database Backups

Important backup strategies include:

* Full backup
* Incremental backup
* Differential backup
* Snapshot
* Logical backup
* Physical backup

A backup strategy should include restoration testing.

A backup that has never been successfully restored should not be treated as proof of recoverability.

---

# 56. Observability

Production databases should be observable.

Important metrics include:

* Query latency
* Query throughput
* CPU utilization
* Memory utilization
* Disk I/O
* Cache hit ratio
* Connection count
* Lock waits
* Replication lag
* Transaction rate
* Error rate
* Deadlocks

Logs provide detailed event information.

Metrics reveal trends.

Distributed tracing helps identify where time is being spent across application and database components.

---

# 57. Vertical Scaling

Vertical scaling means increasing the resources of one machine.

Example:

```text
8 CPU cores -> 32 CPU cores

32 GB RAM -> 128 GB RAM

Slower SSD -> Faster SSD
```

Advantages:

* Simpler architecture
* Fewer distributed-system problems
* Easier operational model

Limitations:

* Hardware limits
* Increasing cost
* Single-node constraints

---

# 58. Horizontal Scaling

Horizontal scaling means adding additional machines.

Example:

```text
1 Database Server
       |
       v
3 Database Servers
```

Horizontal scaling can involve:

* Replication
* Sharding
* Distributed SQL
* Partitioning
* Load distribution

---

# 59. Distributed Databases

A distributed database stores or processes data across multiple machines.

Example:

```text
                Application
                     |
                     v
                Query Router
              /      |       \
             v       v        v
          Node A   Node B   Node C
```

Distributed databases introduce challenges such as:

* Network failures
* Consistency
* Replication
* Distributed transactions
* Data placement
* Rebalancing
* Leader election
* Clock differences

---

# 60. Database Proxy and Router

A database proxy or router can sit between applications and database nodes.

Example:

```text
Applications
      |
      v
Database Proxy
    /       \
   v         v
Primary    Replicas
```

A proxy may assist with:

* Connection management
* Traffic routing
* Failover
* Read/write splitting
* Monitoring
* Load distribution

---

# 61. Read/Write Splitting

A common architecture routes:

```text
Writes -> Primary

Reads -> Replicas
```

Architecture:

```text
                Application
                 /       \
              Writes     Reads
                |          |
                v          v
             Primary    Replicas
```

This can help scale read-heavy workloads.

Replication lag must be considered because replicas may temporarily contain older data.

---

# 62. Database Migrations

A migration changes database schema in a controlled way.

Initial schema:

```text
users(id, name)
```

Later schema:

```text
users(id, name, email)
```

Example migration:

```sql
ALTER TABLE users
ADD COLUMN email TEXT;
```

Migration systems help teams track schema versions.

Important migration considerations include:

* Backward compatibility
* Locking
* Deployment order
* Large-table changes
* Rollback strategy
* Data migration
* Performance impact

---

# 63. Schema Evolution

Schema evolution means changing database structures as applications evolve.

Examples:

* Adding columns
* Removing columns
* Adding tables
* Removing tables
* Creating indexes
* Changing constraints
* Modifying data structures

Large production databases require careful planning because schema changes can affect:

* Queries
* Application code
* Replication
* Locks
* Performance

---

# 64. ORM

ORM means Object-Relational Mapping.

An ORM maps programming-language objects to relational database structures.

Conceptually:

```python
Employee(
    id=1,
    name="Alice",
    salary=80000
)
```

can correspond to a row in:

```text
employees
```

Popular Python ORM technologies include:

* SQLAlchemy
* Django ORM
* SQLModel

ORMs can simplify application development.

But understanding SQL remains important because ORMs generate SQL, and inefficient ORM usage can result in inefficient database queries.

---

# 65. Transaction Manager

The transaction manager coordinates database transactions.

Responsibilities may include:

* Beginning transactions
* Committing transactions
* Rolling back transactions
* Managing isolation
* Coordinating concurrency
* Working with logging
* Supporting recovery

Conceptually:

```text
Application
    |
    v
Transaction Manager
    |
    +---- Query
    +---- Query
    +---- Query
    |
    v
Commit
```

---

# 66. MVCC

MVCC means Multi-Version Concurrency Control.

MVCC allows multiple versions of records to exist so that readers and writers can often operate concurrently with less blocking.

Conceptually:

```text
Row Version 1
Row Version 2
Row Version 3
```

Different transactions may observe different versions depending on the database's isolation and snapshot rules.

MVCC is an important technique used by modern relational database systems.

---

# 67. JOIN Algorithms

Important JOIN algorithms include:

## Nested Loop Join

```text
For each row in A:
    search for matching rows in B
```

## Hash Join

```text
Build hash structure from one input
            |
            v
Probe using the other input
```

## Merge Join

```text
Sort input A
Sort input B
     |
     v
Walk through both sorted inputs
```

The optimizer chooses a JOIN strategy based on factors such as:

* Data size
* Indexes
* Statistics
* Estimated cardinality
* Available memory
* Ordering

---

# 68. Database Statistics

Query optimizers rely heavily on database statistics.

Statistics can describe:

* Number of rows
* Distribution of values
* Number of distinct values
* Data density
* Index characteristics

If statistics are inaccurate, the optimizer may choose an inefficient execution plan.

Maintaining accurate statistics is therefore important for query performance.

---

# 69. Cardinality Estimation

Cardinality refers to the number of rows produced by an operation.

Suppose a table contains:

```text
1,000,000 rows
```

and a predicate matches approximately:

```text
100,000 rows
```

The estimated cardinality is approximately:

```text
100,000
```

Accurate cardinality estimation helps the optimizer choose efficient query plans.

---

# 70. Database Latency

Database latency is the time required to complete a database operation.

A simplified latency model is:

```text
Total Latency
=
Network Latency
+
Connection Overhead
+
Query Planning
+
CPU Processing
+
Memory Access
+
Disk I/O
+
Lock Waiting
+
Result Transmission
```

A database can therefore be slow for many different reasons.

---

# 71. Database Throughput

Throughput measures how much work the database completes within a given period.

Examples include:

* Queries per second
* Transactions per second
* Rows processed per second

A system can have:

```text
Low Latency + Low Throughput
```

or:

```text
High Throughput + High Latency
```

Database architecture must consider both latency and throughput.

---

# 72. Database Architecture Performance Model

A slow database operation can originate from many layers.

```text
Application
    |
    +---- Inefficient application logic

Connection
    |
    +---- Connection overhead

Network
    |
    +---- High latency

Query
    |
    +---- Inefficient SQL

Optimizer
    |
    +---- Poor execution plan

Indexes
    |
    +---- Missing or inappropriate indexes

Concurrency
    |
    +---- Lock contention

Memory
    |
    +---- Insufficient cache

Storage
    |
    +---- Slow I/O

Replication
    |
    +---- Replica lag

Architecture
    |
    +---- Incorrect scaling strategy
```

Therefore:

> "The database is slow" is not a diagnosis.

It is only a symptom.

The actual bottleneck must be identified.

---

# 73. Database Architecture for Microservices

In a microservice architecture, individual services may own their own databases.

Example:

```text
User Service
     |
     v
User Database

Order Service
     |
     v
Order Database

Payment Service
     |
     v
Payment Database
```

This is often called database-per-service.

Benefits include:

* Service autonomy
* Independent scaling
* Isolated schemas

Challenges include:

* Distributed transactions
* Data duplication
* Cross-service queries
* Eventual consistency
* Data synchronization

---

# 74. Database Queues and Asynchronous Processing

Applications may move database-heavy work to asynchronous workers.

Example:

```text
Web Request
    |
    v
Application
    |
    v
Message Queue
    |
    v
Worker
    |
    v
Database
```

This can improve:

* Responsiveness
* Throughput
* Workload isolation

But it also introduces distributed-system complexity.

---

# 75. Idempotency in Distributed Systems

Idempotency is particularly important when retrying operations.

For example:

```text
CREATE PAYMENT
```

may not be safe to blindly retry if the first request succeeded but the response was lost.

The client may not know whether the operation succeeded.

Idempotency keys can be used in appropriate application architectures to prevent duplicate effects.

---

# 76. Database Architecture Decision Framework

When designing a database architecture, ask:

### 1. What type of workload?

* OLTP?
* OLAP?
* Mixed?

### 2. How much data?

* GB?
* TB?
* PB?

### 3. How many users?

* Hundreds?
* Thousands?
* Millions?

### 4. What is the read/write ratio?

* Read-heavy?
* Write-heavy?
* Balanced?

### 5. What consistency is required?

* Strong consistency?
* Eventual consistency?

### 6. What availability is required?

* Standard?
* Mission-critical?

### 7. What is the geographic distribution?

* Single region?
* Multiple regions?
* Global?

### 8. What latency is required?

* Milliseconds?
* Seconds?

### 9. What scaling model is appropriate?

* Vertical scaling?
* Horizontal scaling?

### 10. What are the recovery requirements?

* RPO?
* RTO?

### 11. What security requirements exist?

* Authentication?
* Authorization?
* Encryption?
* Auditing?

### 12. What operational complexity can the team support?

The most complicated architecture is not necessarily the best architecture.

The best architecture is the one that satisfies the system's requirements while keeping complexity manageable.

---

# 77. SQLite vs Client-Server Databases

SQLite:

```text
Application
    |
    v
SQLite Library
    |
    v
Database File
```

Traditional client-server architecture:

```text
Application
    |
    v
Database Driver
    |
    v
Network
    |
    v
Database Server
    |
    v
Storage
```

SQLite is generally embedded within the application.

PostgreSQL, MySQL, SQL Server, and Oracle commonly operate using a separate database server architecture.

---

# 78. End-to-End Database Architecture

A complete conceptual architecture is:

```text
                         USERS
                           |
                           v
                     APPLICATION
                           |
                           v
                    LOAD BALANCER
                           |
                           v
                  APPLICATION SERVERS
                           |
                           v
                     DATABASE CLIENT
                           |
                           v
                    CONNECTION LAYER
                           |
                           v
                    DATABASE SERVER
                           |
              +------------+------------+
              |                         |
              v                         v
       Authentication             Session Manager
              |
              v
           SQL ENGINE
              |
       +------+------+
       |             |
       v             v
     Parser      Optimizer
                     |
                     v
                  Executor
                     |
                     v
             Transaction Manager
                     |
                     v
             Concurrency Control
                     |
                     v
                Buffer Cache
                     |
                     v
               Storage Engine
                     |
          +----------+----------+
          |          |          |
          v          v          v
       Tables      Indexes      WAL
                     |
                     v
                Disk / SSD
```

At large scale:

```text
                         APPLICATIONS
                              |
                              v
                       DATABASE ROUTER
                              |
              +---------------+---------------+
              |               |               |
              v               v               v
           Primary         Replica 1       Replica 2
              |
              v
          WAL / Logs
              |
              v
       Backup / Recovery
```

For sharded systems:

```text
                        DATABASE ROUTER
                              |
          +-------------------+-------------------+
          |                   |                   |
          v                   v                   v
       Shard 1             Shard 2             Shard 3
          |                   |                   |
       Replica              Replica              Replica
```

---

# 79. Most Important Conceptual Distinctions

## Database Client

Sends requests to the database.

## Connection Layer

Establishes and manages communication.

## Database Server

Receives requests and coordinates database operations.

## Query Engine

Parses, analyzes, optimizes, and executes queries.

## Storage Engine

Manages physical storage and retrieval.

## Buffer Cache

Keeps frequently accessed database pages in memory.

## Transaction Manager

Coordinates transaction operations.

## Logging System

Records changes and supports durability and recovery.

## Replication

Maintains copies of data across multiple nodes.

## Partitioning

Divides a logical dataset into smaller physical partitions.

## Sharding

Distributes data across multiple database nodes.

## Cache

Stores frequently accessed data to reduce repeated database work.

## Proxy / Router

Routes database traffic to appropriate nodes.

---

# 80. Complete Mental Model

The complete database architecture can be remembered as:

```text
CLIENT
   |
   v
CONNECTION
   |
   v
DATABASE SERVER
   |
   v
QUERY ENGINE
   |
   +---- Parser
   +---- Analyzer
   +---- Optimizer
   +---- Executor
   |
   v
TRANSACTION MANAGER
   |
   v
CONCURRENCY CONTROL
   |
   v
BUFFER / CACHE
   |
   v
STORAGE ENGINE
   |
   +---- Tables
   +---- Indexes
   +---- Pages
   +---- Logs
   |
   v
PHYSICAL STORAGE
```

For large-scale systems:

```text
Application
    |
    v
Load Balancer
    |
    v
Application Cluster
    |
    v
Cache
    |
    v
Database Router
    |
    +---- Primary
    +---- Replicas
    |
    +---- Shards
    |
    v
Backup / Disaster Recovery
```

---

# 81. What I Learned

After studying database architecture, I learned that a database system is not simply a collection of tables stored on a disk.

It is a collection of specialized components that work together.

I learned that the **database client** is responsible for communicating with the database, while the **connection layer** establishes and manages the communication channel.

I learned that the **database server** coordinates client requests and manages sessions, authentication, transactions, concurrency, queries, and storage.

I learned that the **query engine** processes SQL through several stages:

```text
Parser
   |
Analyzer
   |
Optimizer
   |
Execution Plan
   |
Executor
```

I learned that the **storage engine** is responsible for managing the physical representation and retrieval of database data.

I learned about:

* Database pages
* Rows and records
* Indexes
* Buffer caches
* Transactions
* ACID properties
* Concurrency control
* Locks
* Deadlocks
* Isolation levels
* MVCC
* Write-Ahead Logging
* Crash recovery
* Query optimization
* Execution plans
* Database statistics
* Cardinality estimation
* Connection pooling
* Caching
* N+1 queries
* Normalization
* Denormalization
* OLTP
* OLAP
* Row-oriented storage
* Column-oriented storage
* Replication
* Partitioning
* Sharding
* Shard keys
* Consistent hashing
* CAP theorem
* Strong consistency
* Eventual consistency
* Database security
* SQL injection
* Idempotency
* High availability
* Disaster recovery
* RPO
* RTO
* Database backups
* Observability
* Vertical scaling
* Horizontal scaling
* Distributed databases
* Database proxies
* Read/write splitting
* Database migrations
* Schema evolution
* Microservice database architecture

Most importantly, I learned how a database query travels through the system:

```text
Application
    |
    v
Database Client
    |
    v
Connection Layer
    |
    v
Database Server
    |
    v
Parser
    |
    v
Analyzer
    |
    v
Query Optimizer
    |
    v
Execution Plan
    |
    v
Query Executor
    |
    v
Transaction / Concurrency Management
    |
    v
Buffer Cache
    |
    v
Storage Engine
    |
    v
Disk / SSD
    |
    v
Result
```

This understanding provides a strong foundation for learning:

* SQL
* Database Administration
* Backend Engineering
* Data Engineering
* Data Analytics
* System Design
* Distributed Systems
* Cloud Architecture
* High-Scale Application Design

---

# 82. Key Takeaway

The most important idea from this topic is:

> A database is a complete software system consisting of multiple coordinated layers, not merely a collection of tables.

The fundamental architecture is:

```text
Client
  ↓
Connection Layer
  ↓
Database Server
  ↓
Query Engine
  ↓
Transaction & Concurrency Management
  ↓
Buffer / Cache
  ↓
Storage Engine
  ↓
Persistent Storage
```

For large-scale systems, this architecture expands to include:

```text
Load Balancing
      ↓
Application Cluster
      ↓
Caching
      ↓
Database Routing
      ↓
Primary + Replicas
      ↓
Partitioning / Sharding
      ↓
Backups + Disaster Recovery
```

Understanding these layers makes it possible to reason about database performance, scalability, reliability, security, consistency, availability, and fault tolerance at an advanced system-design level.

```

This version is intentionally **one single Markdown unit** with no fragmented Markdown sections, so you can copy the entire block directly into `README.md`.
```

