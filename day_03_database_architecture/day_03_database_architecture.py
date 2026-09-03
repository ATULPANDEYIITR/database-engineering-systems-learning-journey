"""
DATABASE ARCHITECTURE
=====================

Topic:
Database Server, Client, Storage Engine, Query Engine, Connection Layer

Purpose:
This script provides a comprehensive, beginner-to-advanced explanation of
database architecture using Python examples and simulations.

IMPORTANT:
The examples are educational simulations. They demonstrate how the major
components of a database system work conceptually.

The script covers:

1. What is a database?
2. What is database architecture?
3. Client
4. Database server
5. Connection layer
6. Query engine
7. Storage engine
8. Data storage
9. Complete query lifecycle
10. SQL example
11. CRUD operations
12. Transactions
13. ACID properties
14. Concurrency
15. Locks
16. Connection pooling
17. Query optimization
18. Indexes
19. Caching
20. Buffer/cache management
21. Write-ahead logging
22. Recovery
23. Replication
24. Partitioning
25. Sharding
26. Distributed databases
27. CAP theorem
28. OLTP vs OLAP
29. Row-oriented vs column-oriented storage
30. Database architecture layers
31. Scaling
32. High availability
33. Fault tolerance
34. Security
35. Advanced database architecture
36. End-to-end architecture simulation
37. Practical Python SQLite examples
38. Interview-level concepts
39. Advanced design considerations
"""


# ============================================================
# 1. WHAT IS A DATABASE?
# ============================================================

"""
A database is an organized system for storing, managing, retrieving,
and modifying data.

For example, an e-commerce application may store:

    Customers
    Products
    Orders
    Payments
    Addresses
    Inventory

Without a database, an application could store information in ordinary
files, but files become difficult to manage when:

    - millions of records exist
    - multiple users access data simultaneously
    - transactions are required
    - data must remain consistent
    - fast searching is required
    - failures must be recovered
    - access control is required

A database management system (DBMS) solves these problems.

Examples:

    PostgreSQL
    MySQL
    Microsoft SQL Server
    Oracle Database
    SQLite
    MongoDB
    Cassandra
    Redis

A database is the stored data.

A DBMS is the software that manages the data.
"""


# ============================================================
# 2. WHAT IS DATABASE ARCHITECTURE?
# ============================================================

"""
Database architecture describes how different components cooperate
to store, retrieve, modify, protect, and manage data.

A simplified architecture is:

    Application
        |
        v
    Client / Driver
        |
        v
    Connection Layer
        |
        v
    Database Server
        |
        +--------------------+
        |                    |
        v                    v
    Query Engine       Transaction Manager
        |
        v
    Storage Engine
        |
        v
    Buffer / Cache
        |
        v
    Physical Storage

The five major concepts in this lesson are:

    1. Database client
    2. Database server
    3. Connection layer
    4. Query engine
    5. Storage engine

These components work together whenever an application executes
a database query.
"""


# ============================================================
# 3. DATABASE CLIENT
# ============================================================

"""
A database client is the software component that communicates with
the database server.

Examples:

    Python application
    Java application
    Web application
    Command-line SQL client
    Database GUI
    BI tool
    Data engineering pipeline

A Python program can act as a database client.

For example:

    Python application
            |
            | SQL
            v
    PostgreSQL server

The client normally uses a database driver.

Examples of Python database libraries:

    sqlite3
    psycopg
    mysql-connector-python
    SQLAlchemy

The client is responsible for things such as:

    - opening connections
    - sending queries
    - sending parameters
    - receiving results
    - handling errors
    - committing transactions
    - rolling back transactions

The client does NOT normally directly manipulate the database's
physical storage files.

Instead:

    Client -> Connection -> Server -> Query Engine -> Storage Engine
"""


# ============================================================
# 4. DATABASE SERVER
# ============================================================

"""
A database server is the software process that manages database
operations for clients.

For example:

    Python Application
            |
            v
    PostgreSQL Server
            |
            v
    PostgreSQL Storage

The database server manages:

    - client connections
    - authentication
    - authorization
    - query execution
    - transactions
    - concurrency
    - caching
    - locking
    - recovery
    - storage access

A server can support many clients simultaneously.

For example:

    Client A ----\
    Client B -----\
    Client C ------> Database Server
    Client D -----/
    Client E ----/

The server coordinates all these requests.
"""


# ============================================================
# 5. CONNECTION LAYER
# ============================================================

"""
The connection layer is responsible for establishing and maintaining
communication between the client and database server.

A simplified process:

    Client
       |
       | 1. Connect
       v
    Network
       |
       v
    Database Server
       |
       | 2. Authenticate
       v
    Session
       |
       | 3. Execute queries
       v
    Database

A connection may contain information such as:

    host
    port
    username
    authentication information
    database name
    session settings

Example:

    PostgreSQL default port = 5432
    MySQL default port      = 3306

A connection is not the same thing as a query.

Connection:

    "I am establishing communication with the database."

Query:

    "Now execute this SQL command."

"""


# ============================================================
# 6. DATABASE SESSION
# ============================================================

"""
Once a client connects to a database server, the server may create
a database session.

A session can maintain:

    - authenticated user
    - transaction state
    - session variables
    - temporary tables
    - isolation settings
    - connection-specific configuration

Conceptually:

    Connection
         |
         v
    Session
         |
         +---- Query 1
         +---- Query 2
         +---- Query 3
         +---- Transaction
"""


# ============================================================
# 7. QUERY ENGINE
# ============================================================

"""
The query engine is responsible for understanding and executing
database queries.

Suppose we execute:

    SELECT name
    FROM employees
    WHERE salary > 50000;

The query engine does not simply read the entire SQL string and
immediately access disk.

It typically performs several stages.

Simplified pipeline:

    SQL
     |
     v
    Parser
     |
     v
    Parsed representation
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
    Executor
     |
     v
    Storage Engine
     |
     v
    Results
"""


# ============================================================
# 8. SQL PARSER
# ============================================================

"""
The parser checks whether SQL follows the database's syntax.

Example:

    SELECT name FROM employees;

Valid SQL.

Invalid example:

    SELECT FROM employees;

The parser may detect:

    syntax error

The parser converts SQL into an internal representation.

Conceptually:

    SQL text
       |
       v
    Tokens
       |
       v
    Syntax tree
       |
       v
    Query representation
"""


# ============================================================
# 9. QUERY ANALYZER
# ============================================================

"""
After parsing, the database must determine whether the query makes
semantic sense.

For example:

    SELECT employee_name
    FROM employees;

If employee_name does not exist, the database may report an error.

The analyzer checks:

    - tables
    - columns
    - data types
    - functions
    - permissions
    - relationships
"""


# ============================================================
# 10. QUERY OPTIMIZER
# ============================================================

"""
The query optimizer attempts to find an efficient execution strategy.

Consider:

    SELECT *
    FROM employees
    WHERE department_id = 10;

Possible strategies:

    Strategy A:
        Scan every row.

    Strategy B:
        Use an index on department_id.

The optimizer estimates the cost of each strategy.

It may consider:

    - table size
    - indexes
    - selectivity
    - join algorithms
    - available memory
    - statistics
    - sorting cost
    - filtering cost
    - disk I/O

The optimizer then chooses an execution plan.

This is one of the most important concepts in database performance.
"""


# ============================================================
# 11. EXECUTION PLAN
# ============================================================

"""
An execution plan describes how the database intends to execute
a query.

Example conceptual plan:

    Index Scan
        |
        v
    Filter
        |
        v
    Return rows

For a JOIN:

    Table A
       |
       v
    Hash Join
       ^
       |
    Table B

Common operations include:

    Sequential Scan
    Index Scan
    Index Seek
    Nested Loop Join
    Hash Join
    Merge Join
    Sort
    Aggregate
    Filter
    Group By

Database professionals inspect execution plans when optimizing
slow queries.
"""


# ============================================================
# 12. STORAGE ENGINE
# ============================================================

"""
The storage engine is the component responsible for storing and
retrieving database data.

It manages concepts such as:

    - pages
    - records
    - indexes
    - buffers
    - files
    - logs
    - physical layouts

Different databases use different storage architectures.

The storage engine sits below the query engine.

Conceptually:

    SQL
     |
     v
    Query Engine
     |
     v
    Storage Engine
     |
     v
    Disk / SSD


The query engine asks:

    "Give me rows satisfying this condition."

The storage engine determines how those rows are physically
retrieved.
"""


# ============================================================
# 13. DATABASE PAGES
# ============================================================

"""
Databases usually do not read individual rows directly from disk
one at a time.

Instead, storage is commonly organized into pages or blocks.

Conceptually:

    Database File
    --------------------------------
    | Page 1 | Page 2 | Page 3 | ...
    --------------------------------

A page may contain multiple records.

Reading pages efficiently is important because disk I/O can be
expensive compared with CPU and memory operations.
"""


# ============================================================
# 14. ROWS AND RECORDS
# ============================================================

"""
Suppose we have:

    employees

    id | name | salary
    ------------------
    1  | A    | 50000
    2  | B    | 60000
    3  | C    | 70000

A row is one record.

A column represents one attribute.

A database storage engine determines how those records are
physically represented.
"""


# ============================================================
# 15. INDEXES
# ============================================================

"""
An index is a data structure that helps the database locate rows
efficiently.

Without an index:

    Search all rows
        |
        v
    O(n) approximately

With a suitable index:

    Search index
        |
        v
    Locate relevant rows

Indexes can dramatically improve read performance.

Common index structures include:

    B-tree
    B+ tree
    Hash index
    Bitmap index
    GiST
    GIN
    LSM-tree-based structures

Example:

    CREATE INDEX idx_employee_salary
    ON employees(salary);

An index has a cost.

Advantages:

    faster reads
    faster filtering
    faster ordering in suitable cases

Costs:

    additional storage
    slower INSERT
    slower UPDATE
    slower DELETE
    maintenance overhead

Therefore:

    More indexes != always better performance
"""


# ============================================================
# 16. QUERY LIFECYCLE
# ============================================================

"""
Let's understand the complete lifecycle of:

    SELECT name
    FROM employees
    WHERE salary > 50000;

Step 1:
    Application creates query.

Step 2:
    Client driver sends query.

Step 3:
    Connection layer transmits query.

Step 4:
    Database server receives request.

Step 5:
    Parser validates SQL syntax.

Step 6:
    Analyzer validates objects and permissions.

Step 7:
    Optimizer evaluates possible execution plans.

Step 8:
    Optimizer selects a plan.

Step 9:
    Executor starts execution.

Step 10:
    Storage engine retrieves required data.

Step 11:
    Buffer/cache is checked.

Step 12:
    Disk may be accessed if data is not cached.

Step 13:
    Matching records are returned.

Step 14:
    Database server sends result to client.

Step 15:
    Client receives result.

Pipeline:

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
    Parser
          |
          v
    Analyzer
          |
          v
    Optimizer
          |
          v
    Executor
          |
          v
    Storage Engine
          |
          v
    Buffer / Cache
          |
          v
    Disk / SSD
"""


# ============================================================
# 17. DATABASE CRUD
# ============================================================

"""
CRUD means:

    C = Create
    R = Read
    U = Update
    D = Delete

Create:

    INSERT

Read:

    SELECT

Update:

    UPDATE

Delete:

    DELETE
"""


# ============================================================
# 18. PRACTICAL SQLITE EXAMPLE
# ============================================================

"""
SQLite is useful for learning because it is embedded directly
inside an application.

Unlike PostgreSQL or MySQL, SQLite normally does not require a
separate database server process.

This makes SQLite architecturally different from client-server
databases.
"""

import sqlite3


# Create an in-memory SQLite database.
connection = sqlite3.connect(":memory:")

cursor = connection.cursor()


# Create a table.
cursor.execute(
    """
    CREATE TABLE employees (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        department TEXT,
        salary REAL
    )
    """
)


# Insert data.
employees = [
    (1, "Alice", "Engineering", 80000),
    (2, "Bob", "Finance", 70000),
    (3, "Charlie", "Engineering", 90000),
    (4, "Diana", "HR", 60000),
]

cursor.executemany(
    """
    INSERT INTO employees
    (id, name, department, salary)
    VALUES (?, ?, ?, ?)
    """,
    employees
)

connection.commit()


# Read data.
cursor.execute(
    """
    SELECT id, name, department, salary
    FROM employees
    """
)

rows = cursor.fetchall()

print("\nALL EMPLOYEES")
for row in rows:
    print(row)


# Filter data.
cursor.execute(
    """
    SELECT name, salary
    FROM employees
    WHERE salary > ?
    """,
    (75000,)
)

print("\nEMPLOYEES WITH SALARY > 75000")

for row in cursor.fetchall():
    print(row)


# Update data.
cursor.execute(
    """
    UPDATE employees
    SET salary = salary + ?
    WHERE department = ?
    """,
    (5000, "Engineering")
)

connection.commit()


# Delete data.
cursor.execute(
    """
    DELETE FROM employees
    WHERE name = ?
    """,
    ("Diana",)
)

connection.commit()


# ============================================================
# 19. PARAMETERIZED QUERIES
# ============================================================

"""
Never construct SQL using unsafe string concatenation when external
input is involved.

BAD:

    username = input("Username: ")

    query = "SELECT * FROM users WHERE name = '" + username + "'"

This can lead to SQL injection.

GOOD:

    cursor.execute(
        "SELECT * FROM users WHERE name = ?",
        (username,)
    )

Parameterized queries separate:

    SQL code

from:

    user data
"""

username = "Alice"

cursor.execute(
    "SELECT * FROM employees WHERE name = ?",
    (username,)
)

print("\nPARAMETERIZED QUERY")
print(cursor.fetchall())


# ============================================================
# 20. TRANSACTIONS
# ============================================================

"""
A transaction is a logical unit of database work.

Example:

    Transfer ₹1000 from Account A to Account B.

Required operations:

    1. Subtract ₹1000 from A.
    2. Add ₹1000 to B.

Both operations should succeed together.

If step 1 succeeds but step 2 fails, the database should be able
to undo the transaction.

Conceptually:

    BEGIN
       |
       v
    UPDATE A
       |
       v
    UPDATE B
       |
       v
    COMMIT

If something fails:

    BEGIN
       |
       v
    UPDATE A
       |
       v
    UPDATE B
       |
       X
    ROLLBACK
"""


# ============================================================
# 21. ACID
# ============================================================

"""
ACID describes important transaction properties.

A = Atomicity
C = Consistency
I = Isolation
D = Durability


ATOMICITY

A transaction is treated as one unit.

Either:

    all operations succeed

or:

    all operations are rolled back.


CONSISTENCY

A transaction should move the database from one valid state
to another valid state.

Database constraints help maintain consistency.


ISOLATION

Concurrent transactions should not interfere in unacceptable ways.

Different isolation levels provide different guarantees.


DURABILITY

Once a transaction is committed, its effects should survive
system failures.

Logging and persistent storage help provide durability.
"""


# ============================================================
# 22. CONCURRENCY
# ============================================================

"""
A database may have many clients simultaneously.

Example:

    User A -> UPDATE account
    User B -> UPDATE account
    User C -> SELECT account
    User D -> INSERT transaction

The database must coordinate these operations.

This is called concurrency control.
"""


# ============================================================
# 23. LOCKING
# ============================================================

"""
Databases may use locks to control concurrent access.

Common conceptual lock types:

    Shared lock
    Exclusive lock

Shared lock:

    Multiple readers may access data.

Exclusive lock:

    A transaction needs exclusive access for modification.

Example:

    Transaction A
        |
        | UPDATE account
        v
    Exclusive Lock
        |
        v
    Modify data
        |
        v
    COMMIT
        |
        v
    Release lock
"""


# ============================================================
# 24. DEADLOCK
# ============================================================

"""
A deadlock occurs when transactions wait for one another indefinitely.

Example:

    Transaction A locks Row 1.
    Transaction B locks Row 2.

    A waits for Row 2.
    B waits for Row 1.

Result:

    A -> waiting for B
    B -> waiting for A

The database must detect or prevent such situations.

Common strategies include:

    - deadlock detection
    - timeout
    - consistent lock ordering
    - transaction rollback
"""


# ============================================================
# 25. ISOLATION LEVELS
# ============================================================

"""
Common SQL transaction isolation levels:

    READ UNCOMMITTED
    READ COMMITTED
    REPEATABLE READ
    SERIALIZABLE

Higher isolation generally provides stronger consistency but may
reduce concurrency.

Common anomalies include:

    Dirty Read
    Non-repeatable Read
    Phantom Read

Dirty Read:

    Transaction A reads data that Transaction B has not committed.

Non-repeatable Read:

    Transaction A reads a row twice and gets different results
    because another transaction modified it.

Phantom Read:

    A repeated query returns additional or missing rows because
    another transaction inserted or deleted matching records.
"""


# ============================================================
# 26. CONNECTION POOLING
# ============================================================

"""
Creating a database connection can be relatively expensive.

Instead of repeatedly doing:

    connect
    query
    disconnect

applications often use connection pooling.

Conceptually:

        Connection Pool
       /      |       \
      C1     C2       C3
       \      |       /
        Application

When a request needs a database connection:

    1. Borrow connection.
    2. Execute query.
    3. Return connection to pool.

Benefits:

    - lower connection overhead
    - better performance
    - controlled concurrency
    - reduced database connection pressure
"""


class SimpleConnectionPool:
    """
    Educational simulation of a connection pool.
    """

    def __init__(self, size):
        self.connections = [
            f"Connection-{i}"
            for i in range(1, size + 1)
        ]
        self.available = self.connections.copy()

    def acquire(self):
        if not self.available:
            raise RuntimeError("No database connections available.")

        return self.available.pop()

    def release(self, connection):
        self.available.append(connection)


pool = SimpleConnectionPool(3)

conn1 = pool.acquire()
conn2 = pool.acquire()

print("\nCONNECTION POOL")
print("Acquired:", conn1)
print("Acquired:", conn2)

pool.release(conn1)

print("Released:", conn1)


# ============================================================
# 27. BUFFER CACHE
# ============================================================

"""
Disk access is much slower than memory access.

Database systems therefore use memory aggressively.

A buffer cache stores frequently accessed database pages in memory.

Conceptually:

    Query
      |
      v
    Buffer Cache
      |
      +---- Page found -> use memory
      |
      +---- Page missing -> read from disk

This is called a cache hit or cache miss.

Cache hit:

    Data found in memory.

Cache miss:

    Data must be loaded from storage.
"""


# ============================================================
# 28. WRITE-AHEAD LOGGING
# ============================================================

"""
Many database systems use Write-Ahead Logging (WAL).

The basic principle is:

    Write the change to a durable log
    before writing the corresponding data page.

Conceptually:

    Transaction
         |
         v
    WAL record
         |
         v
    Durable storage
         |
         v
    Data page update

Why?

If the database crashes, the log can be used during recovery.

This helps support:

    - durability
    - crash recovery
    - replication
    - point-in-time recovery in systems that support it
"""


# ============================================================
# 29. CRASH RECOVERY
# ============================================================

"""
Suppose a database crashes during a transaction.

Without recovery mechanisms, partially completed operations could
leave the database in an inconsistent state.

A recovery system can use transaction logs to determine:

    Which operations were committed?
    Which operations were incomplete?
    Which changes must be replayed?
    Which changes must be undone?

Conceptually:

    Database Crash
          |
          v
       Restart
          |
          v
    Read recovery log
          |
          v
    Redo / Undo
          |
          v
    Consistent database
"""


# ============================================================
# 30. CACHING
# ============================================================

"""
Caching reduces repeated expensive database operations.

Architecture:

    Application
        |
        v
      Cache
      /   \
    Hit   Miss
    |       |
    v       v
 Return   Database
           |
           v
         Cache

Examples of caching systems include:

    Redis
    Memcached

Caching is useful for:

    - frequently requested data
    - sessions
    - configuration
    - computed results
    - rate limiting

But caching creates challenges:

    - stale data
    - invalidation
    - consistency
    - memory limits
"""


# ============================================================
# 31. CACHE-ASIDE PATTERN
# ============================================================

"""
A common pattern is cache-aside.

Process:

    1. Application checks cache.
    2. If found, return cached value.
    3. If not found, query database.
    4. Store result in cache.
    5. Return result.

Conceptually:

    Application
        |
        v
      Cache?
       /  \
     Hit  Miss
      |     |
      |     v
      |   Database
      |     |
      |     v
      |   Cache
      |     |
      \-----/
        |
        v
      Result
"""


# ============================================================
# 32. QUERY OPTIMIZATION
# ============================================================

"""
Database performance depends heavily on query design.

Example of potentially expensive query:

    SELECT *
    FROM employees;

If a table has 100 million rows, this can return an enormous amount
of data.

Better:

    SELECT name, salary
    FROM employees
    WHERE department = 'Engineering';

Good optimization practices include:

    - select only required columns
    - filter early
    - use appropriate indexes
    - avoid unnecessary joins
    - inspect execution plans
    - avoid unnecessary sorting
    - use pagination
    - use appropriate data types
    - maintain statistics
    - avoid N+1 queries
"""


# ============================================================
# 33. N+1 QUERY PROBLEM
# ============================================================

"""
The N+1 problem occurs when an application executes:

    1 query to retrieve N records

and then:

    1 additional query for each record.

Example:

    SELECT * FROM customers;

Then for 100 customers:

    SELECT * FROM orders WHERE customer_id = 1;
    SELECT * FROM orders WHERE customer_id = 2;
    ...
    SELECT * FROM orders WHERE customer_id = 100;

Total:

    101 queries

A JOIN or batch query may reduce this significantly.
"""


# ============================================================
# 34. DATABASE NORMALIZATION
# ============================================================

"""
Normalization organizes relational data to reduce redundancy.

Common normal forms:

    1NF
    2NF
    3NF
    BCNF
    4NF
    5NF

Example of poor design:

    customer_id
    customer_name
    product_1
    product_2
    product_3

Better relational design:

    Customers
    Products
    Orders
    OrderItems

Normalization can improve consistency.

But highly normalized schemas may require more joins.

Therefore production systems sometimes use controlled denormalization
for performance.
"""


# ============================================================
# 35. OLTP
# ============================================================

"""
OLTP = Online Transaction Processing

Typical OLTP workloads:

    banking
    e-commerce
    payments
    inventory
    booking systems

Characteristics:

    - many concurrent users
    - short transactions
    - frequent INSERT/UPDATE/DELETE
    - strong consistency requirements
    - low latency
"""


# ============================================================
# 36. OLAP
# ============================================================

"""
OLAP = Online Analytical Processing

Typical OLAP workloads:

    business intelligence
    dashboards
    reporting
    data warehouses
    analytics

Characteristics:

    - large scans
    - aggregations
    - historical data
    - complex queries
    - fewer writes compared with OLTP

Example:

    SELECT
        department,
        AVG(salary)
    FROM employees
    GROUP BY department;
"""


# ============================================================
# 37. ROW-ORIENTED STORAGE
# ============================================================

"""
Row-oriented databases store related fields of a record together.

Conceptually:

    Row 1:
        id | name | department | salary

    Row 2:
        id | name | department | salary

This is often useful for transactional workloads where complete
records are frequently accessed or modified.
"""


# ============================================================
# 38. COLUMN-ORIENTED STORAGE
# ============================================================

"""
Column-oriented systems organize data by columns.

Conceptually:

    ID:
        1, 2, 3, 4

    Salary:
        50000, 60000, 70000, 80000

This can be highly efficient for analytical workloads where queries
scan only a subset of columns across many rows.

Columnar storage can also benefit from:

    - compression
    - vectorized execution
    - analytical scans
"""


# ============================================================
# 39. REPLICATION
# ============================================================

"""
Replication means maintaining copies of data across multiple
database nodes.

Example:

                 Primary
                   |
          +--------+--------+
          |                 |
          v                 v
       Replica 1         Replica 2

Advantages:

    - high availability
    - read scaling
    - disaster recovery
    - geographic distribution

Common models include:

    primary-replica
    multi-primary
    synchronous replication
    asynchronous replication
"""


# ============================================================
# 40. SYNCHRONOUS REPLICATION
# ============================================================

"""
With synchronous replication, a write may not be considered fully
committed until required replicas acknowledge it.

Advantage:

    stronger consistency

Potential disadvantage:

    higher latency
    dependency on replica availability
"""


# ============================================================
# 41. ASYNCHRONOUS REPLICATION
# ============================================================

"""
With asynchronous replication:

    Primary commits
        |
        v
    Client receives result

Replica receives changes afterward.

Advantages:

    - lower write latency
    - easier geographic replication

Risk:

    replicas may temporarily lag behind the primary.
"""


# ============================================================
# 42. PARTITIONING
# ============================================================

"""
Partitioning divides a large logical table into smaller physical
partitions.

Example:

    Orders

    Partition 2024
    Partition 2025
    Partition 2026

Common strategies:

    Range partitioning
    List partitioning
    Hash partitioning

Partitioning can improve:

    - query performance
    - maintenance
    - data lifecycle management
    - partition pruning
"""


# ============================================================
# 43. SHARDING
# ============================================================

"""
Sharding distributes data across multiple database servers.

Example:

    Database Cluster

    Shard 1 -> Customers A-F
    Shard 2 -> Customers G-M
    Shard 3 -> Customers N-S
    Shard 4 -> Customers T-Z

Unlike partitioning within one database system, sharding usually
means distributing data across independent nodes.

Benefits:

    - horizontal scaling
    - larger total capacity
    - distributed workload

Challenges:

    - cross-shard queries
    - distributed transactions
    - rebalancing
    - shard key design
    - operational complexity
"""


# ============================================================
# 44. SHARD KEY
# ============================================================

"""
A shard key determines where data is stored.

A good shard key should ideally:

    - distribute data evenly
    - distribute workload evenly
    - support common queries
    - avoid hotspots

A poor shard key can create:

    hotspot shards
    uneven storage
    uneven traffic
    scaling problems
"""


# ============================================================
# 45. CONSISTENT HASHING
# ============================================================

"""
Consistent hashing is often discussed in distributed systems for
assigning keys to nodes while minimizing data movement when nodes
are added or removed.

Conceptual ring:

             Node A
               |
        +------+------+
        |             |
      Node D         Node B
        |             |
        +------Node C-+

Keys are mapped onto the ring.

Consistent hashing is useful in:

    distributed caches
    partitioning systems
    distributed databases

The exact implementation differs between systems.
"""


# ============================================================
# 46. CAP THEOREM
# ============================================================

"""
CAP theorem describes trade-offs in distributed systems.

C = Consistency
A = Availability
P = Partition tolerance

When a network partition occurs, a distributed system must make
a trade-off between strong consistency and availability.

Important:

    CAP does NOT simply mean:

        "You can only ever choose two of three."

The more useful interpretation is:

    In the presence of a network partition, the system must choose
    how to balance consistency and availability.
"""


# ============================================================
# 47. DATABASE SECURITY
# ============================================================

"""
Database architecture must include security.

Important controls include:

    Authentication
    Authorization
    Encryption
    Auditing
    Network security
    Secrets management
    Least privilege
    Backup security
    Row-level security where supported

Authentication asks:

    "Who are you?"

Authorization asks:

    "What are you allowed to do?"
"""


# ============================================================
# 48. SQL INJECTION
# ============================================================

"""
SQL injection occurs when untrusted input is interpreted as SQL code.

Unsafe pattern:

    query = "SELECT * FROM users WHERE name = '" + user_input + "'"

Safer pattern:

    cursor.execute(
        "SELECT * FROM users WHERE name = ?",
        (user_input,)
    )

Parameterized queries are a fundamental defense.
"""


# ============================================================
# 49. DATABASE CONNECTION FAILURE
# ============================================================

"""
Production applications must assume connections can fail.

Possible causes:

    - database restart
    - network failure
    - timeout
    - overloaded server
    - connection exhaustion
    - firewall issues
    - DNS failure

Applications should use:

    - timeouts
    - controlled retries
    - connection pooling
    - circuit breakers where appropriate
    - health checks
    - observability
"""


# ============================================================
# 50. RETRY STRATEGIES
# ============================================================

"""
Retries must be designed carefully.

Bad strategy:

    retry forever immediately

Better:

    limited retries
    exponential backoff
    jitter
    idempotency awareness

Example:

    Attempt 1 -> wait 0.5 seconds
    Attempt 2 -> wait 1 second
    Attempt 3 -> wait 2 seconds

Retries can be dangerous for non-idempotent operations.

Example:

    CREATE PAYMENT

If the client does not know whether the first attempt succeeded,
blindly retrying may create duplicate effects.

Idempotency keys can help in appropriate application designs.
"""


# ============================================================
# 51. HIGH AVAILABILITY
# ============================================================

"""
High availability means designing the system so that service remains
available despite failures.

Possible architecture:

              Load Balancer
                    |
          +---------+---------+
          |                   |
          v                   v
      App Server 1        App Server 2
          |                   |
          +---------+---------+
                    |
               DB Cluster
              /          \
         Primary        Replica

Failure of one component should not necessarily bring down the
entire application.
"""


# ============================================================
# 52. DISASTER RECOVERY
# ============================================================

"""
Disaster recovery deals with major failures.

Examples:

    data center outage
    hardware failure
    accidental deletion
    corruption
    ransomware
    regional outage

Important concepts:

    RPO = Recovery Point Objective

    RTO = Recovery Time Objective

RPO answers:

    "How much data loss can we tolerate?"

RTO answers:

    "How quickly must service be restored?"
"""


# ============================================================
# 53. BACKUPS
# ============================================================

"""
Backups are a critical part of database architecture.

Possible backup approaches:

    Full backup
    Incremental backup
    Differential backup
    Snapshot
    Logical backup
    Physical backup

A backup strategy should also include restoration testing.

A backup that has never been tested is not sufficient evidence
of recoverability.
"""


# ============================================================
# 54. OBSERVABILITY
# ============================================================

"""
Production databases should be observable.

Important metrics include:

    query latency
    throughput
    CPU usage
    memory usage
    disk I/O
    cache hit ratio
    connection count
    lock waits
    replication lag
    transaction rate
    errors
    deadlocks

Logs help explain what happened.

Metrics show trends.

Tracing helps understand request flow across services.
"""


# ============================================================
# 55. DATABASE ARCHITECTURE LAYERS
# ============================================================

"""
A useful conceptual layered architecture is:

    +------------------------------------+
    | Application / Client               |
    +------------------------------------+
                    |
                    v
    +------------------------------------+
    | Connection Layer                   |
    +------------------------------------+
                    |
                    v
    +------------------------------------+
    | Authentication / Session Manager   |
    +------------------------------------+
                    |
                    v
    +------------------------------------+
    | SQL Parser / Analyzer              |
    +------------------------------------+
                    |
                    v
    +------------------------------------+
    | Query Optimizer                    |
    +------------------------------------+
                    |
                    v
    +------------------------------------+
    | Query Executor                     |
    +------------------------------------+
                    |
                    v
    +------------------------------------+
    | Transaction / Concurrency Manager  |
    +------------------------------------+
                    |
                    v
    +------------------------------------+
    | Buffer / Cache Manager              |
    +------------------------------------+
                    |
                    v
    +------------------------------------+
    | Storage Engine                     |
    +------------------------------------+
                    |
                    v
    +------------------------------------+
    | Files / SSD / Persistent Storage   |
    +------------------------------------+
"""


# ============================================================
# 56. CLIENT-SERVER ARCHITECTURE
# ============================================================

"""
In a traditional client-server database:

    Client
      |
      | SQL request
      v
    Database Server
      |
      v
    Storage

Advantages:

    centralized management
    concurrent access
    authentication
    transactions
    query optimization
    shared data

This is common in:

    PostgreSQL
    MySQL
    SQL Server
    Oracle
"""


# ============================================================
# 57. EMBEDDED DATABASE ARCHITECTURE
# ============================================================

"""
SQLite is different.

Typical architecture:

    Application
        |
        v
    SQLite Library
        |
        v
    Database File

There may be no independent database server process.

This makes SQLite particularly useful for:

    desktop applications
    mobile applications
    testing
    prototypes
    embedded systems
    small local applications
"""


# ============================================================
# 58. DATABASE DRIVER
# ============================================================

"""
A database driver translates application-level requests into a
protocol the database understands.

Example:

    Python
      |
      v
    psycopg
      |
      v
    PostgreSQL protocol
      |
      v
    PostgreSQL server

The driver provides APIs for:

    connect()
    execute()
    fetchone()
    fetchall()
    commit()
    rollback()
    close()
"""


# ============================================================
# 59. ORM
# ============================================================

"""
ORM = Object-Relational Mapping.

An ORM maps programming-language objects to relational database
tables.

For example:

    Python object

        Employee(
            id=1,
            name="Alice",
            salary=80000
        )

may correspond to:

    employees table

ORMs can simplify application development.

Examples:

    SQLAlchemy
    Django ORM
    SQLModel

But understanding SQL remains important because ORMs still generate
database queries and poorly designed ORM usage can produce inefficient
SQL.
"""


# ============================================================
# 60. TRANSACTION MANAGER
# ============================================================

"""
The transaction manager coordinates transactions.

Responsibilities may include:

    - begin transaction
    - commit
    - rollback
    - isolation
    - concurrency coordination
    - interaction with logging
    - recovery

Conceptually:

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
"""


# ============================================================
# 61. CONCURRENCY CONTROL MODELS
# ============================================================

"""
Common approaches include:

    Lock-based concurrency control

    MVCC
    Multi-Version Concurrency Control

MVCC allows multiple versions of records to exist so readers and
writers can often operate with less blocking.

Conceptually:

    Row Version 1
    Row Version 2
    Row Version 3

Different transactions may observe different versions depending
on their isolation and snapshot rules.

MVCC is widely used in modern relational databases.
"""


# ============================================================
# 62. MVCC
# ============================================================

"""
MVCC can provide efficient concurrent reads.

Conceptual example:

    Transaction A starts
        |
        v
    Reads version 1

    Transaction B updates row
        |
        v
    Creates version 2

Transaction A may continue seeing version 1 according to the
database's isolation model.

Transaction B sees its updated state.

The exact MVCC implementation differs between databases.
"""


# ============================================================
# 63. QUERY EXECUTION STRATEGIES
# ============================================================

"""
JOIN algorithms are especially important.

Nested Loop Join:

    For each row in A:
        search matching rows in B

Hash Join:

    Build hash structure from one input
    Probe it using the other input

Merge Join:

    Sort inputs
    Walk through sorted inputs

The optimizer chooses based on:

    data size
    indexes
    statistics
    estimated selectivity
    memory
    ordering
"""


# ============================================================
# 64. DATABASE STATISTICS
# ============================================================

"""
Query optimizers depend heavily on statistics.

Statistics may describe:

    - number of rows
    - value distributions
    - distinct values
    - data density
    - index characteristics

If statistics are inaccurate, the optimizer may choose a poor plan.

Therefore database maintenance may include refreshing statistics.
"""


# ============================================================
# 65. CARDINALITY ESTIMATION
# ============================================================

"""
Cardinality refers to the number of rows produced by an operation.

Example:

    Table contains 1,000,000 rows.

Predicate:

    WHERE country = 'India'

If approximately 100,000 rows match:

    estimated cardinality = 100,000

Accurate cardinality estimates help query optimizers choose better
plans.
"""


# ============================================================
# 66. DATABASE LATENCY
# ============================================================

"""
Database latency is the time required to complete a database
operation.

A simplified latency model:

    Total Latency
        =
    Network latency
    +
    Connection overhead
    +
    Query planning
    +
    CPU processing
    +
    Memory access
    +
    Disk I/O
    +
    Lock waiting
    +
    Result transmission

Optimization requires identifying the actual bottleneck.
"""


# ============================================================
# 67. THROUGHPUT
# ============================================================

"""
Throughput measures how much work the database completes per unit
of time.

Examples:

    queries per second
    transactions per second
    rows processed per second

A system may have:

    low latency but low throughput

or:

    high throughput but high latency

Database architecture must consider both.
"""


# ============================================================
# 68. HORIZONTAL SCALING
# ============================================================

"""
Horizontal scaling means adding more machines.

Example:

    1 database server

becomes:

    3 database servers

Horizontal scaling can involve:

    replication
    sharding
    distributed SQL
    partitioning
    load distribution
"""


# ============================================================
# 69. VERTICAL SCALING
# ============================================================

"""
Vertical scaling means increasing the resources of one machine.

For example:

    8 CPU -> 32 CPU

    32 GB RAM -> 128 GB RAM

    slower SSD -> faster SSD

Advantages:

    simpler architecture
    fewer distributed-system problems

Limitations:

    hardware limits
    increasing cost
    single-node constraints
"""


# ============================================================
# 70. DISTRIBUTED DATABASE
# ============================================================

"""
A distributed database stores or processes data across multiple
machines.

Example:

             Application
                  |
                  v
            Query Router
          /      |       \
         v       v        v
      Node A   Node B   Node C

Challenges include:

    network failures
    consistency
    replication
    distributed transactions
    clock differences
    leader election
    data placement
    rebalancing
"""


# ============================================================
# 71. CONSISTENCY MODELS
# ============================================================

"""
Distributed databases can provide different consistency models.

Examples:

    Strong consistency
    Eventual consistency
    Causal consistency

Strong consistency generally aims to make reads observe the latest
committed state according to the system's defined semantics.

Eventual consistency allows temporary differences between replicas,
with the expectation that replicas converge if updates stop.
"""


# ============================================================
# 72. EVENTUAL CONSISTENCY
# ============================================================

"""
Example:

    User writes data to Replica A.

    Replica A -> updated

    Replica B -> temporarily old

    Replication occurs.

    Replica B -> updated

Eventually:

    A == B

This can improve availability and scalability but applications must
be designed to tolerate temporary inconsistency where appropriate.
"""


# ============================================================
# 73. DATABASE PROXY / ROUTER
# ============================================================

"""
A proxy or database router can sit between applications and
database servers.

Architecture:

    Applications
          |
          v
    Database Proxy
       /      \
      v        v
  Primary    Replicas

The proxy may help with:

    connection management
    routing
    failover
    read/write separation
    observability
"""


# ============================================================
# 74. READ/WRITE SPLITTING
# ============================================================

"""
Some architectures send:

    Writes -> Primary

    Reads -> Replicas

Example:

          Application
           /       \
        Writes     Reads
          |          |
          v          v
       Primary    Replicas

This can scale read-heavy workloads.

But replication lag must be considered.
"""


# ============================================================
# 75. DATABASE MIGRATIONS
# ============================================================

"""
A migration changes database schema in a controlled way.

Example:

Version 1:

    users(id, name)

Version 2:

    users(id, name, email)

Migration:

    ALTER TABLE users
    ADD COLUMN email TEXT;

Migration systems help teams track schema versions.

Good migrations consider:

    backward compatibility
    locking
    deployment order
    large-table changes
    rollback strategy
    data migration
"""


# ============================================================
# 76. SCHEMA EVOLUTION
# ============================================================

"""
Schema evolution is the process of changing data structures as
applications evolve.

Examples:

    adding columns
    removing columns
    changing indexes
    creating tables
    changing constraints

Large production databases require careful migration planning
because schema changes can affect:

    queries
    application code
    replication
    locks
    performance
"""


# ============================================================
# 77. IDEMPOTENCY
# ============================================================

"""
An operation is idempotent if repeating it produces the same intended
final effect.

Example:

    SET account_status = 'ACTIVE'

Repeated execution has the same intended final state.

Compare with:

    balance = balance + 100

Repeating it twice adds 200.

Idempotency is particularly important in:

    distributed systems
    retries
    payment systems
    message processing
    APIs
"""


# ============================================================
# 78. DATABASE QUEUES AND ASYNCHRONOUS WORK
# ============================================================

"""
Applications may avoid performing every database-heavy operation
synchronously.

Example:

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

This architecture can improve:

    responsiveness
    throughput
    workload isolation

But introduces distributed-system complexity.
"""


# ============================================================
# 79. DATABASE AND MICROSERVICES
# ============================================================

"""
In microservice architectures, each service may own its database.

Example:

    User Service -> User DB

    Order Service -> Order DB

    Payment Service -> Payment DB

This is often called database-per-service.

Benefits:

    service autonomy
    independent scaling
    isolated schemas

Challenges:

    distributed transactions
    data duplication
    cross-service queries
    eventual consistency
    synchronization
"""


# ============================================================
# 80. DATABASE DESIGN DECISION TREE
# ============================================================

"""
When designing a database architecture, ask:

1. What type of workload?
       OLTP or OLAP?

2. How much data?
       GB, TB, PB?

3. How many users?
       Hundreds, thousands, millions?

4. Read/write ratio?
       Read-heavy or write-heavy?

5. Consistency requirement?
       Strong or eventual?

6. Availability requirement?
       Standard or mission-critical?

7. Geographic distribution?
       One region or multiple regions?

8. Latency requirement?
       Milliseconds or seconds?

9. Scaling model?
       Vertical or horizontal?

10. Recovery requirement?
       What are RPO and RTO?

11. Security requirement?
       Authentication, authorization, encryption?

12. Operational complexity?
       Can the team operate the architecture?

The best architecture is not necessarily the most complicated one.
"""


# ============================================================
# 81. SIMPLE END-TO-END SIMULATION
# ============================================================

class QueryEngine:
    """
    Educational simulation of a query engine.
    """

    def parse(self, query):
        print("[Query Engine] Parsing query...")
        return {"query": query}

    def optimize(self, parsed_query):
        print("[Query Engine] Optimizing query...")
        return {
            "plan": "Sequential Scan",
            "query": parsed_query["query"]
        }

    def execute(self, plan, storage_engine):
        print("[Query Engine] Executing plan...")
        return storage_engine.read(plan["query"])


class StorageEngine:
    """
    Educational storage engine simulation.
    """

    def __init__(self):
        self.data = [
            {"id": 1, "name": "Alice", "salary": 80000},
            {"id": 2, "name": "Bob", "salary": 60000},
            {"id": 3, "name": "Charlie", "salary": 90000},
        ]

    def read(self, query):
        print("[Storage Engine] Reading data...")
        return self.data


class ConnectionLayer:
    """
    Educational connection layer.
    """

    def connect(self):
        print("[Connection Layer] Connection established.")

    def send(self, query, query_engine, storage_engine):
        parsed = query_engine.parse(query)
        plan = query_engine.optimize(parsed)
        return query_engine.execute(plan, storage_engine)


class DatabaseServer:
    """
    Educational database server.
    """

    def __init__(self):
        self.query_engine = QueryEngine()
        self.storage_engine = StorageEngine()

    def execute_query(self, query):
        return self.query_engine.execute(
            self.query_engine.optimize(
                self.query_engine.parse(query)
            ),
            self.storage_engine
        )


class DatabaseClient:
    """
    Educational database client.
    """

    def __init__(self, connection_layer):
        self.connection_layer = connection_layer

    def connect(self):
        self.connection_layer.connect()

    def execute(self, query, server):
        return self.connection_layer.send(
            query,
            server.query_engine,
            server.storage_engine
        )


print("\nEND-TO-END DATABASE ARCHITECTURE SIMULATION")

server = DatabaseServer()

connection_layer = ConnectionLayer()

client = DatabaseClient(connection_layer)

client.connect()

result = client.execute(
    "SELECT name FROM employees WHERE salary > 75000",
    server
)

print("[Client] Received result:")
print(result)


# ============================================================
# 82. DATABASE ARCHITECTURE IN ONE DIAGRAM
# ============================================================

"""
                    USER
                     |
                     v
              APPLICATION
                     |
                     v
            DATABASE CLIENT
          /       |        \
       Driver   ORM      SQL Library
                     |
                     v
             CONNECTION LAYER
                     |
                     v
             DATABASE SERVER
                     |
          +----------+----------+
          |                     |
          v                     v
    Authentication       Session Manager
          |
          v
       SQL ENGINE
          |
     +----+----+
     |         |
     v         v
   Parser   Optimizer
               |
               v
            Executor
               |
               v
       Transaction Manager
               |
               v
        Buffer / Cache
               |
               v
         STORAGE ENGINE
               |
       +-------+-------+
       |       |       |
       v       v       v
     Tables  Indexes  WAL
               |
               v
          SSD / Disk
"""


# ============================================================
# 83. IMPORTANT DISTINCTION
# ============================================================

"""
Remember the distinction:

DATABASE CLIENT
    Sends requests to the database.

DATABASE SERVER
    Receives requests and coordinates database operations.

CONNECTION LAYER
    Establishes and manages communication.

QUERY ENGINE
    Understands, optimizes, and executes queries.

STORAGE ENGINE
    Manages physical storage and retrieval.

BUFFER CACHE
    Keeps frequently used pages in memory.

TRANSACTION MANAGER
    Coordinates transactional behavior.

LOGGING / WAL
    Supports durability and recovery.

REPLICATION
    Maintains copies across nodes.

SHARDING
    Distributes data across nodes.

CACHE
    Reduces repeated database access.

PROXY / ROUTER
    Can route database traffic.

APPLICATION
    Uses all these components through database clients/drivers.
"""


# ============================================================
# 84. DATABASE ARCHITECTURE PERFORMANCE MODEL
# ============================================================

"""
A slow database operation can originate from many layers.

Application problem:
    inefficient application logic

Connection problem:
    connection creation overhead

Network problem:
    high latency

Query problem:
    inefficient SQL

Optimizer problem:
    poor execution plan

Index problem:
    missing or inappropriate index

Lock problem:
    contention

Memory problem:
    insufficient cache

Storage problem:
    slow I/O

Replication problem:
    replica lag

Architecture problem:
    incorrect scaling strategy

Therefore:

    "Database is slow"

is not a diagnosis.

It is only a symptom.

Performance engineering requires finding the actual bottleneck.
"""


# ============================================================
# 85. ADVANCED ARCHITECTURAL PRINCIPLE
# ============================================================

"""
A database is not simply:

    "a file containing tables."

A modern database system can be understood as a coordinated
collection of subsystems:

    Client Interface
          |
    Connection Management
          |
    Authentication
          |
    SQL Processing
          |
    Query Optimization
          |
    Query Execution
          |
    Transaction Management
          |
    Concurrency Control
          |
    Buffer Management
          |
    Storage Management
          |
    Logging
          |
    Recovery
          |
    Replication
          |
    Distributed Coordination
          |
    Physical Storage

Understanding this layered architecture makes it much easier to
understand:

    SQL performance
    database scaling
    transaction behavior
    distributed databases
    high availability
    database failures
    data engineering
    backend engineering
    system design
"""


# ============================================================
# 86. PRACTICAL LEARNING EXERCISES
# ============================================================

"""
Exercise 1:
Create a SQLite database with:

    customers
    products
    orders

Exercise 2:
Add indexes and compare query behavior.

Exercise 3:
Use EXPLAIN QUERY PLAN in SQLite.

Example:

    EXPLAIN QUERY PLAN
    SELECT *
    FROM employees
    WHERE salary > 75000;

Exercise 4:
Create a transaction that intentionally fails and perform rollback.

Exercise 5:
Measure the effect of repeated queries using Python.

Exercise 6:
Build a simple connection pool simulation.

Exercise 7:
Implement an in-memory cache.

Exercise 8:
Simulate primary-replica replication.

Exercise 9:
Simulate hash-based sharding.

Exercise 10:
Design a database architecture for an e-commerce application.
"""


# ============================================================
# 87. FINAL CONCEPTUAL MODEL
# ============================================================

"""
The entire topic can be remembered through this sequence:

    CLIENT
       |
       v
    CONNECTION
       |
       v
    SERVER
       |
       v
    QUERY ENGINE
       |
       +---- Parser
       |
       +---- Analyzer
       |
       +---- Optimizer
       |
       +---- Executor
       |
       v
    TRANSACTION MANAGER
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

For larger systems:

    Primary
      |
      +---- Replica
      |
      +---- Replica

For horizontally scaled systems:

    Router
      |
      +---- Shard 1
      +---- Shard 2
      +---- Shard 3
      +---- Shard 4

For high-scale applications:

    Users
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
      +---- Sharded Database
      |
      v
    Backup / Disaster Recovery
"""


# ============================================================
# 88. CLEANUP
# ============================================================

connection.close()

print("\nDatabase connection closed.")
print("Database architecture lesson completed.")
