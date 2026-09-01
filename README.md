# database-engineering-systems-learning-journey
My learning journey through database design, architecture, optimization, transactions, and database systems.

This repository documents my journey of learning **Database Engineering and Database Systems**, from relational database fundamentals to design, optimization, transactions, and modern database technologies.

## 🎯 Goal

To understand how databases are designed, structured, optimized, secured, and operated to store and manage data efficiently.

# 120-Day Database Engineering & Systems Learning Journey
## From Absolute Basics to Extreme Advanced

> A 120-day topic-wise roadmap covering database fundamentals, SQL, relational
> database engineering, PostgreSQL, database internals, NoSQL, distributed
> systems, data engineering, performance engineering, high availability,
> replication, sharding, cloud databases, security, observability, and
> advanced distributed database architecture.

---

## PHASE 01 — DATABASE FOUNDATIONS

| Day | Topic | Core Areas |
|---:|---|---|
| 1 | Introduction to Databases | What databases are, why databases exist, DBMS, database users, database applications |
| 2 | Database Types | Relational, NoSQL, NewSQL, graph, document, key-value, column-family, time-series |
| 3 | Database Architecture | Database server, client, storage engine, query engine, connection layer |
| 4 | Data Modeling Fundamentals | Entities, attributes, relationships, business rules |
| 5 | Relational Model | Tables, rows, columns, domains, tuples, relations |
| 6 | Keys and Constraints | Primary keys, foreign keys, candidate keys, unique keys, constraints |
| 7 | Database Schemas | Schema concepts, namespaces, objects, logical organization |
| 8 | SQL Introduction | SQL purpose, statements, commands, syntax fundamentals |
| 9 | SELECT Fundamentals | SELECT, FROM, WHERE, aliases, expressions |
| 10 | Filtering Data | Comparison operators, logical operators, NULL, BETWEEN, IN, LIKE |
| 11 | Sorting and Limiting | ORDER BY, ASC, DESC, LIMIT, OFFSET |
| 12 | SQL Functions | String, numeric, date, conditional and NULL-handling functions |
| 13 | Aggregations | COUNT, SUM, AVG, MIN, MAX, GROUP BY |
| 14 | HAVING and Aggregated Filtering | HAVING, grouped conditions, aggregation logic |
| 15 | SQL Foundations Project | Build and query a complete small relational database |

---

## PHASE 02 — ADVANCED SQL

| Day | Topic | Core Areas |
|---:|---|---|
| 16 | SQL Joins I | INNER JOIN, LEFT JOIN, RIGHT JOIN |
| 17 | SQL Joins II | FULL JOIN, CROSS JOIN, SELF JOIN |
| 18 | Join Strategy | Join keys, cardinality, duplicate rows, NULL behavior |
| 19 | Subqueries | Scalar, correlated, nested and multi-level subqueries |
| 20 | Common Table Expressions | WITH, reusable query logic, recursive CTE introduction |
| 21 | CASE Expressions | Conditional transformations, business logic in SQL |
| 22 | Set Operations | UNION, UNION ALL, INTERSECT, EXCEPT |
| 23 | Window Functions I | OVER, PARTITION BY, ORDER BY |
| 24 | Window Functions II | ROW_NUMBER, RANK, DENSE_RANK, NTILE |
| 25 | Analytical Windows | LAG, LEAD, FIRST_VALUE, LAST_VALUE |
| 26 | Running and Moving Calculations | Running totals, moving averages, cumulative metrics |
| 27 | Advanced Aggregation | GROUPING SETS, ROLLUP, CUBE |
| 28 | Date and Time Analytics | Intervals, timestamps, time zones, date arithmetic |
| 29 | Advanced SQL Patterns | Top-N, gaps-and-islands, deduplication, pivot-style analysis |
| 30 | Advanced SQL Project | Build an analytical SQL system using complex queries |

---

# PHASE 03 — RELATIONAL DATABASE DESIGN

| Day | Topic | Core Areas |
|---:|---|---|
| 31 | Database Design Principles | Logical vs physical design, design objectives |
| 32 | Entity Relationship Modeling | ER diagrams, entities, attributes and relationships |
| 33 | Cardinality | One-to-one, one-to-many, many-to-many |
| 34 | Normalization I | Functional dependencies and anomalies |
| 35 | Normalization II | 1NF, 2NF, 3NF |
| 36 | Advanced Normalization | BCNF, 4NF, 5NF |
| 37 | Denormalization | Why and when to denormalize |
| 38 | Referential Integrity | Foreign-key relationships and cascading actions |
| 39 | Constraints and Data Quality | CHECK, NOT NULL, UNIQUE and business rules |
| 40 | Schema Evolution | Changing schemas safely over time |
| 41 | Surrogate vs Natural Keys | ID strategies and design trade-offs |
| 42 | Temporal Data Modeling | Historical records, effective dates, event time |
| 43 | Multi-Tenant Database Design | Shared schema, separate schema, separate database |
| 44 | Database Design Patterns | Audit tables, soft deletes, status models |
| 45 | Database Modeling Project | Design a production-grade relational schema |

---

# PHASE 04 — POSTGRESQL DATABASE ENGINEERING

| Day | Topic | Core Areas |
|---:|---|---|
| 46 | PostgreSQL Fundamentals | Installation, architecture, psql, databases and schemas |
| 47 | PostgreSQL Data Types | Numeric, text, Boolean, UUID, JSON, arrays |
| 48 | PostgreSQL Table Engineering | CREATE TABLE, ALTER TABLE, constraints |
| 49 | PostgreSQL Indexes | B-tree, hash, GIN, GiST, BRIN |
| 50 | PostgreSQL Views | Views, materialized views and use cases |
| 51 | PostgreSQL Functions | SQL functions, procedural functions |
| 52 | PL/pgSQL | Variables, control flow, functions |
| 53 | Stored Procedures and Triggers | Procedures, triggers and automated database logic |
| 54 | Transactions in PostgreSQL | BEGIN, COMMIT, ROLLBACK, savepoints |
| 55 | PostgreSQL JSON | JSON/JSONB, querying and indexing JSON |
| 56 | PostgreSQL Arrays | Array operations and practical use cases |
| 57 | PostgreSQL Extensions | Extensions, PostGIS introduction and ecosystem |
| 58 | PostgreSQL Configuration | Configuration files, memory and connection settings |
| 59 | PostgreSQL Administration | Users, roles, permissions and database management |
| 60 | PostgreSQL Engineering Project | Build and administer a production-style PostgreSQL system |

---

# PHASE 05 — DATABASE INTERNALS

| Day | Topic | Core Areas |
|---:|---|---|
| 61 | Database Internals Overview | Query engine, storage engine, buffer manager |
| 62 | Query Processing | Parsing, analysis, rewriting and planning |
| 63 | Query Execution | Operators, execution plans and result generation |
| 64 | Storage Fundamentals | Pages, blocks, records and physical storage |
| 65 | Buffer Management | Buffer pools, cache hits, cache misses |
| 66 | Disk and SSD Behavior | I/O latency, sequential vs random I/O |
| 67 | Index Internals | B-trees, tree traversal, index pages |
| 68 | Hash Indexing | Hash tables and hash-based access |
| 69 | LSM Trees | Log-structured merge trees and write optimization |
| 70 | Write-Ahead Logging | WAL, durability and crash recovery |
| 71 | Database Checkpoints | Checkpoints, dirty pages and recovery |
| 72 | MVCC | Multi-version concurrency control |
| 73 | Vacuum and Garbage Collection | Dead tuples, vacuuming and storage reclamation |
| 74 | Query Optimizer | Cost estimation, statistics and plan selection |
| 75 | Database Internals Project | Analyze database behavior from storage to query execution |

---

# PHASE 06 — TRANSACTIONS AND CONCURRENCY

| Day | Topic | Core Areas |
|---:|---|---|
| 76 | ACID Fundamentals | Atomicity, consistency, isolation and durability |
| 77 | Transaction Lifecycle | Transaction states and commit/rollback |
| 78 | Isolation Levels | Read Uncommitted, Read Committed, Repeatable Read, Serializable |
| 79 | Dirty Reads | Causes, examples and prevention |
| 80 | Non-Repeatable Reads | Concurrency behavior and isolation |
| 81 | Phantom Reads | Range queries and transaction isolation |
| 82 | Lost Updates | Concurrent write problems |
| 83 | Locks | Shared locks, exclusive locks and lock compatibility |
| 84 | Deadlocks | Detection, prevention and recovery |
| 85 | Optimistic Concurrency | Versioning and conflict detection |
| 86 | Pessimistic Concurrency | Lock-based approaches |
| 87 | MVCC vs Locking | Architectural trade-offs |
| 88 | Serializable Systems | Serializable execution and practical costs |
| 89 | Distributed Transactions | Two-phase commit and coordination |
| 90 | Transaction Engineering Project | Design and test concurrent transaction workloads |

---

# PHASE 07 — DATABASE PERFORMANCE ENGINEERING

| Day | Topic | Core Areas |
|---:|---|---|
| 91 | Query Performance | Identifying slow queries and bottlenecks |
| 92 | EXPLAIN | Reading query execution plans |
| 93 | EXPLAIN ANALYZE | Measuring actual query execution |
| 94 | Index Optimization | Selectivity, composite indexes and covering indexes |
| 95 | Query Optimization | Joins, predicates, subqueries and rewrites |
| 96 | Statistics | Histograms, cardinality estimation and planner statistics |
| 97 | Partitioning | Range, list and hash partitioning |
| 98 | Table Partition Strategy | Partition pruning and maintenance |
| 99 | Connection Management | Connection pools and connection limits |
| 100 | Caching | Database cache, application cache and Redis concepts |
| 101 | Read/Write Optimization | Workload separation and read replicas |
| 102 | Performance Testing | Benchmarking and workload generation |
| 103 | Load Testing | Throughput, latency and concurrency |
| 104 | Capacity Planning | CPU, memory, storage, IOPS and growth |
| 105 | Performance Engineering Project | Tune a deliberately slow database workload |

---

# PHASE 08 — NoSQL DATABASE SYSTEMS

| Day | Topic | Core Areas |
|---:|---|---|
| 106 | NoSQL Fundamentals | Why NoSQL exists and relational limitations |
| 107 | Key-Value Databases | Key-value architecture and access patterns |
| 108 | Document Databases | JSON documents, collections and document modeling |
| 109 | MongoDB Fundamentals | Documents, collections, CRUD and queries |
| 110 | MongoDB Indexing | Indexes, compound indexes and query optimization |
| 111 | Wide-Column Databases | Cassandra-style architecture |
| 112 | Graph Databases | Nodes, edges, relationships and graph queries |
| 113 | Time-Series Databases | Time-series workloads and data modeling |
| 114 | NoSQL Data Modeling | Access-pattern-driven modeling |
| 115 | CAP Theorem | Consistency, availability and partition tolerance |

---

# PHASE 09 — DISTRIBUTED DATABASE SYSTEMS

| Day | Topic | Core Areas |
|---:|---|---|
| 116 | Distributed Databases | Architecture and distributed data management |
| 117 | Replication | Leader-follower, multi-leader and leaderless models |
| 118 | Sharding | Horizontal partitioning, shard keys and rebalancing |
| 119 | Distributed Systems Fundamentals | Consensus, quorum, clocks, failures and coordination |
| 120 | Extreme Advanced Capstone | Design a globally distributed, highly available database platform |

---

# 120-DAY CAPSTONE TARGET

By the end of the program, the learner should be capable of designing and
reasoning about a database platform containing:

```text
                    APPLICATIONS
                         |
                         v
                 API / APPLICATION
                         |
                         v
                CONNECTION POOL
                         |
          +--------------+--------------+
          |                             |
          v                             v
      READ PATH                    WRITE PATH
          |                             |
          v                             v
     READ REPLICAS                 PRIMARY DB
          |                             |
          |                         WAL / LOG
          |                             |
          +-------------+---------------+
                        |
                        v
                  STORAGE ENGINE
                        |
             +----------+----------+
             |                     |
             v                     v
          INDEXES                DATA
             |
             v
       QUERY OPTIMIZER
             |
             v
       QUERY EXECUTION

Additional layers:

    CACHE
    MESSAGE QUEUES
    OBJECT STORAGE
    ANALYTICS SYSTEMS
    MONITORING
    LOGGING
    BACKUPS
    DISASTER RECOVERY
    SECURITY
    IAM
    ENCRYPTION
    REPLICATION
    SHARDING
    LOAD BALANCING
