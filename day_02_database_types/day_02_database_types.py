"""
DATABASE TYPES
===============

Topic:
Relational, NoSQL, NewSQL, Graph, Document, Key-Value,
Column-Family, and Time-Series Databases

Purpose:
This script is a structured learning program for understanding
database types from basic concepts to advanced architectural
considerations.

The script intentionally uses standard Python only.
No external packages are required.

Run:
    python database_types.py
"""

from dataclasses import dataclass
from typing import Dict, List, Tuple


# ============================================================
# 1. INTRODUCTION
# ============================================================

def title(text: str) -> None:
    print("\n" + "=" * 78)
    print(text.upper())
    print("=" * 78)


def section(text: str) -> None:
    print("\n" + "-" * 78)
    print(text)
    print("-" * 78)


def explain(text: str) -> None:
    print(text)


def show_example(label: str, example: str) -> None:
    print(f"\n{label}:")
    print(example)


def pause_note() -> None:
    print()


title("DATABASE TYPES: FROM FUNDAMENTALS TO ADVANCED")

explain("""
A database is a system used to store, organize, retrieve, update,
and manage data.

The important point is that "database" does not describe one single
technology.

Different database systems make different assumptions about:

    - how data is structured
    - how data is queried
    - how relationships are represented
    - how transactions work
    - how data is distributed
    - how systems scale
    - how consistency is maintained
    - how much schema flexibility is required
    - what kinds of workloads are efficient

The major database families covered here are:

    1. Relational databases
    2. NoSQL databases
    3. NewSQL databases
    4. Document databases
    5. Key-value databases
    6. Column-family databases
    7. Graph databases
    8. Time-series databases

No database type is universally superior.

Database selection is primarily a question of workload,
data relationships, consistency requirements, scale,
query patterns, operational requirements, and failure tolerance.
""")

pause_note()


# ============================================================
# 2. WHAT A DATABASE ACTUALLY DOES
# ============================================================

title("1. WHAT A DATABASE ACTUALLY DOES")

explain("""
At its simplest level, a database provides persistent storage.

An application generates data:

    User
    Order
    Product
    Payment
    Sensor reading
    Log event
    Social connection
    Financial transaction

The database stores this data so that it can be retrieved later.

A database system normally provides several capabilities:

    CREATE
    READ
    UPDATE
    DELETE

These are commonly referred to as CRUD operations.

Example:

    CREATE:
        Create a customer.

    READ:
        Retrieve customer information.

    UPDATE:
        Change the customer's address.

    DELETE:
        Remove or deactivate a record.

Real database systems provide much more than CRUD.

They can provide:

    - transactions
    - indexes
    - constraints
    - concurrency control
    - replication
    - partitioning
    - backups
    - recovery
    - authentication
    - authorization
    - query optimization
    - caching
    - distributed coordination
    - consistency guarantees
""")

show_example(
    "Simple conceptual flow",
    """
    Application
        |
        v
    Database Driver / Client
        |
        v
    Database Server
        |
        +---- Storage
        |
        +---- Query Engine
        |
        +---- Transaction Manager
        |
        +---- Concurrency Control
        |
        +---- Indexes
        |
        +---- Recovery / Logging
"""
)


# ============================================================
# 3. DATABASE VS DBMS
# ============================================================

title("2. DATABASE VS DBMS")

explain("""
A database is the organized collection of data.

A DBMS, or Database Management System, is the software that manages
that data.

For example, a conceptual database might contain:

    customers
    products
    orders

The DBMS provides mechanisms to create tables or collections,
execute queries, maintain indexes, enforce rules, and recover data.

Examples of relational DBMS products include:

    PostgreSQL
    MySQL
    Microsoft SQL Server
    Oracle Database
    SQLite

Examples from other database families include:

    MongoDB
    Redis
    Cassandra
    Neo4j
    InfluxDB

The distinction is useful because "database type" and "database
product" are not exactly the same thing.

Relational is a data-model family.

PostgreSQL is a particular database system that primarily follows
the relational model.

MongoDB is a document-oriented database system.

Redis is primarily a key-value database.

Cassandra is a distributed wide-column / column-family database.

Neo4j is a graph database.

InfluxDB is a time-series database.
""")


# ============================================================
# 4. DATA MODELS
# ============================================================

title("3. DATA MODELS")

explain("""
A data model describes how information is represented.

Different database families use different abstractions.

Relational model:
    Data is represented using relations, commonly exposed as tables.

Document model:
    Data is represented as documents, often using JSON-like structures.

Key-value model:
    Data is represented as key -> value pairs.

Column-family model:
    Data is organized around rows and dynamically grouped columns,
    often optimized for distributed workloads and particular access
    patterns.

Graph model:
    Data is represented using nodes, relationships, and properties.

Time-series model:
    Data is organized around measurements associated with time,
    commonly involving timestamps, tags, and values.

The physical implementation can differ substantially from the
logical model.

A database may internally use trees, hash tables, logs, SSTables,
LSM trees, B-trees, columnar structures, or other mechanisms.
""")


# ============================================================
# 5. RELATIONAL DATABASES
# ============================================================

title("4. RELATIONAL DATABASES")

explain("""
The relational model represents data using relations.

In practical database systems, these are usually represented
as tables.

A table contains:

    - rows
    - columns

Example:

    CUSTOMERS

    customer_id | name        | email
    ------------+-------------+------------------
    1           | Atul        | atul@example.com
    2           | Rahul       | rahul@example.com
    3           | Priya       | priya@example.com

Each row represents an entity or record.

Each column represents an attribute.

A relational database normally has a defined schema.

For example:

    customer_id -> integer
    name        -> text
    email       -> text

The relational model is strongly associated with SQL.
""")

show_example(
    "Example SQL",
    """
CREATE TABLE customers (
    customer_id INTEGER PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(255) UNIQUE
);

INSERT INTO customers
(customer_id, name, email)
VALUES
(1, 'Atul', 'atul@example.com');

SELECT customer_id, name, email
FROM customers
WHERE customer_id = 1;
"""
)

section("Primary Keys")

explain("""
A primary key uniquely identifies a row.

Example:

    customer_id

A primary key should identify one specific record.

For example:

    customer_id = 101
    customer_id = 102
    customer_id = 103

Two different rows should not normally have the same primary key.

Primary keys are important for:

    - uniqueness
    - relationships
    - indexing
    - data integrity
    - efficient lookup
""")

section("Foreign Keys")

explain("""
A foreign key represents a relationship between tables.

Example:

CUSTOMERS

    customer_id
    -----------
    1
    2

ORDERS

    order_id | customer_id
    ---------+------------
    5001     | 1
    5002     | 1
    5003     | 2

The customer_id in ORDERS can reference customer_id in CUSTOMERS.

This establishes referential integrity.

Conceptually:

    CUSTOMER 1 ---- N ORDER
""")

section("Normalization")

explain("""
Normalization is the process of organizing relational data to reduce
unnecessary duplication and improve consistency.

Important normal forms include:

    1NF
    2NF
    3NF
    BCNF
    4NF
    5NF

A simple example of a poorly designed table:

    order_id
    customer_name
    customer_email
    product_name
    product_price

If the same customer places 100 orders, their name and email may be
repeated many times.

A normalized design might separate:

    customers
    orders
    products
    order_items

The purpose is not simply "make everything into many tables."

Normalization is about functional dependencies, data integrity,
and avoiding inappropriate redundancy.
""")

section("Denormalization")

explain("""
Denormalization intentionally introduces redundancy.

Why?

Because read performance can sometimes be more important than
eliminating every duplicate value.

For example, an analytics table might intentionally contain:

    order_id
    customer_name
    product_name
    product_category
    order_total
    order_date

This may make reporting queries faster and simpler.

Therefore:

    Normalization -> consistency and reduced redundancy

    Denormalization -> potentially faster reads and simpler access

The correct design depends on workload.
""")

section("Joins")

explain("""
One of the strongest features of relational databases is the ability
to combine related data through joins.

Common join types:

    INNER JOIN
    LEFT JOIN
    RIGHT JOIN
    FULL OUTER JOIN
    CROSS JOIN

Example:

SELECT
    customers.name,
    orders.order_id
FROM customers
INNER JOIN orders
    ON customers.customer_id = orders.customer_id;

Joins are powerful because relationships can be represented
independently and assembled at query time.
""")

section("ACID Transactions")

explain("""
Relational systems are strongly associated with ACID transactions.

ACID means:

    A = Atomicity
    C = Consistency
    I = Isolation
    D = Durability

Atomicity:
    A transaction succeeds completely or fails as a unit.

Consistency:
    A committed transaction leaves the database satisfying its
    defined integrity rules.

Isolation:
    Concurrent transactions should behave according to the
    database's isolation guarantees.

Durability:
    Once a transaction is committed, its effects survive
    appropriate failures.

Example:

    Transfer $100 from Account A to Account B.

The operation should not produce:

    A loses $100
    B receives nothing

or:

    B receives $100
    A does not lose $100

The transfer is logically one transaction.
""")

section("Transaction Isolation Levels")

explain("""
Isolation is not a single setting.

Common isolation levels include:

    READ UNCOMMITTED
    READ COMMITTED
    REPEATABLE READ
    SERIALIZABLE

Some systems also provide snapshot-based isolation variants.

Typical concurrency anomalies include:

    Dirty read
    Non-repeatable read
    Phantom read
    Lost update

Higher isolation generally provides stronger guarantees but may
reduce concurrency or increase coordination costs.

This is why transaction isolation is an architectural concern,
not merely a SQL syntax detail.
""")


# ============================================================
# 6. INDEXES
# ============================================================

title("5. DATABASE INDEXES")

explain("""
An index is an additional data structure that helps the database
find rows efficiently.

Without an appropriate index, the database may need to inspect
many rows.

Conceptually:

    Without index:

    Query
      |
      v
    Scan Row 1
    Scan Row 2
    Scan Row 3
    ...
    Scan Row N

With a suitable index:

    Query
      |
      v
    Index
      |
      v
    Relevant rows

Indexes can dramatically improve read performance.

Common index structures include:

    B-tree
    Hash
    Bitmap
    GiST
    GIN
    R-tree

The exact choices depend on the database.
""")

section("Index Trade-Off")

explain("""
Indexes are not free.

They consume:

    - storage
    - memory
    - CPU
    - write time

When a row changes, related indexes may also need to be updated.

Therefore:

    More indexes != automatically better performance

A database with many unnecessary indexes may have poor write
performance and larger storage requirements.
""")


# ============================================================
# 7. NOSQL
# ============================================================

title("6. NOSQL DATABASES")

explain("""
NoSQL generally refers to database systems that do not primarily
use the traditional relational table-and-join model.

The term is broad.

NoSQL does not mean:

    "No SQL exists anywhere."

It is better understood as a family of alternative data models and
scaling approaches.

Major NoSQL categories include:

    - document
    - key-value
    - column-family / wide-column
    - graph

Common motivations include:

    - flexible schemas
    - horizontal scaling
    - high throughput
    - distributed operation
    - workload-specific data models
    - avoiding expensive relational joins for certain workloads

NoSQL is not a single database architecture.
""")


# ============================================================
# 8. DOCUMENT DATABASES
# ============================================================

title("7. DOCUMENT DATABASES")

explain("""
A document database stores records as documents.

Documents commonly resemble JSON.

Example:

{
    "customer_id": 101,
    "name": "Atul",
    "email": "atul@example.com",
    "address": {
        "city": "Lucknow",
        "country": "India"
    },
    "interests": [
        "Python",
        "Databases",
        "Cybersecurity"
    ]
}

Instead of splitting every attribute into separate relational
tables, related information can be embedded into one document.

This can make application development convenient.

Document databases are especially useful when:

    - records have flexible attributes
    - application objects map naturally to documents
    - nested data is frequently retrieved together
    - schema changes frequently
    - horizontal scaling is important
""")

section("Embedded Data")

show_example(
    "Embedded document",
    """
{
    "order_id": 5001,
    "customer_id": 101,
    "items": [
        {
            "product_id": 10,
            "name": "Keyboard",
            "quantity": 1
        },
        {
            "product_id": 20,
            "name": "Mouse",
            "quantity": 2
        }
    ]
}
"""
)

section("Embedding vs Referencing")

explain("""
A document system can often represent relationships in two major
ways.

Embedding:

    Customer
       |
       +-- address
       +-- preferences
       +-- contact details

Referencing:

    Order
       |
       +-- customer_id

Embedding is useful when related information is usually retrieved
together.

Referencing can be useful when the referenced entity is shared,
large, independently updated, or has its own lifecycle.

This is similar to the broader database design decision between
duplicating data and keeping relationships separate.
""")

section("Document Database Peculiarities")

explain("""
A flexible schema does not mean no structure.

Poorly controlled document structures can lead to:

    - inconsistent field names
    - different data types for the same field
    - duplicated information
    - difficult migrations
    - large documents
    - complicated application-side validation

Schema flexibility is useful when used deliberately.

It should not become an excuse for uncontrolled data design.
""")


# ============================================================
# 9. KEY-VALUE DATABASES
# ============================================================

title("8. KEY-VALUE DATABASES")

explain("""
A key-value database stores data using a key and an associated value.

Conceptually:

    key -> value

Example:

    user:101 -> "Atul"

    session:ABC123 -> "{...session data...}"

    cart:101 -> "{...shopping cart...}"

The key is normally the primary mechanism used to retrieve the
value.

Key-value systems are particularly effective when the application
already knows the key it wants.
""")

show_example(
    "Conceptual key-value operations",
    """
SET user:101 "Atul"

GET user:101

DELETE user:101
"""
)

section("Common Use Cases")

explain("""
Key-value databases are commonly considered for:

    - caching
    - sessions
    - authentication state
    - feature flags
    - counters
    - rate limiting
    - temporary state
    - shopping carts
    - fast lookups

Their strength is often low-latency access by key.
""")

section("Important Limitation")

explain("""
A key-value model is not naturally designed for complex relational
queries such as:

    Find every customer in Lucknow
    who purchased products in category X
    during the previous six months
    and whose total spending exceeds Y.

Such queries can require additional structures, application logic,
secondary indexes, or a different database model.

The key-value model is powerful because it intentionally keeps
the primary access pattern simple.
""")


# ============================================================
# 10. COLUMN-FAMILY DATABASES
# ============================================================

title("9. COLUMN-FAMILY / WIDE-COLUMN DATABASES")

explain("""
Column-family databases are designed around distributed,
large-scale workloads.

They are sometimes called wide-column databases.

The model is different from a traditional relational table even
though the words "row" and "column" may appear in both.

Examples of systems in this family include:

    Apache Cassandra
    Apache HBase

A wide-column system may organize data around:

    partition key
    clustering columns
    columns
    column families / tables

The exact terminology differs between systems.
""")

section("Partition Key")

explain("""
A partition key determines where data belongs in a distributed
system.

Conceptually:

    partition_key -> node / partition

A good partition key distributes data reasonably well.

A poor partition key can create a hot partition.

Example:

    country = "India"

If almost every record uses India as the partition key, too much
traffic may concentrate on one partition.

A better design may use a more appropriate distribution strategy.
""")

section("Query-Driven Design")

explain("""
Wide-column databases often encourage designing tables according
to known access patterns.

Instead of starting with:

    "What entities do I have?"

the design process may ask:

    "What queries must the system answer?"

Suppose an application needs:

    Get all events for user 101
    ordered by time.

A table may be designed specifically around:

    user_id
    event_time
    event_data

This is different from normalized relational modeling.

The access pattern is a major driver of schema design.
""")

section("Advantages")

explain("""
Wide-column systems can be effective for:

    - high write throughput
    - very large datasets
    - distributed workloads
    - predictable access patterns
    - horizontal scaling
    - high availability

They can be less convenient for:

    - arbitrary joins
    - ad-hoc relational queries
    - highly dynamic query patterns
    - workloads requiring many relational constraints
""")


# ============================================================
# 11. GRAPH DATABASES
# ============================================================

title("10. GRAPH DATABASES")

explain("""
Graph databases represent data primarily through:

    Nodes
    Relationships
    Properties

Example:

    (Atul)-[:WORKS_AT]->(Company)

    (Atul)-[:KNOWS]->(Rahul)

    (Rahul)-[:WORKS_AT]->(Company)

The relationship itself is a first-class element of the model.

This is particularly useful when relationships are as important
as the entities themselves.
""")

section("Graph Concepts")

show_example(
    "Conceptual graph",
    """
    [Atul]
       |
       | WORKS_AT
       v
    [Company A]
       ^
       |
       | WORKS_AT
       |
    [Rahul]

    [Atul] ---- KNOWS ----> [Rahul]
"""
)

section("When Graph Databases Are Useful")

explain("""
Common applications include:

    - social networks
    - recommendation systems
    - fraud detection
    - network analysis
    - identity relationships
    - knowledge graphs
    - dependency analysis
    - route and path analysis
    - access-control relationships

A graph database becomes especially interesting when queries involve
multiple levels of relationships.

Example:

    Find people who know someone
    who works at the same company
    as a person connected to the current user.
""")

section("Graph Traversal")

explain("""
A graph query often performs a traversal.

For example:

    User
      |
      | follows
      v
    User
      |
      | purchased
      v
    Product
      |
      | belongs_to
      v
    Category

The query can follow relationships through the graph.

In a relational system, equivalent information may require multiple
joins.

Neither approach is automatically better.

The graph model becomes attractive when relationship traversal is
central to the workload.
""")

section("Graph Peculiarity")

explain("""
A graph database is not merely a relational database with a graph
visualization.

Its storage and query engine are often designed around relationships
and traversals.

The important design question is:

    "What connections exist, and how will those connections be
     traversed?"

rather than only:

    "What columns exist?"
""")


# ============================================================
# 12. TIME-SERIES DATABASES
# ============================================================

title("11. TIME-SERIES DATABASES")

explain("""
Time-series databases are optimized for data where time is a
fundamental dimension.

Examples:

    temperature at 10:01
    temperature at 10:02
    temperature at 10:03

    CPU usage at 10:01
    CPU usage at 10:02

    stock price at a particular timestamp

    website requests per minute

Typical time-series data contains:

    timestamp
    measurement
    tags / dimensions
    value
""")

show_example(
    "Example time-series record",
    """
timestamp: 2026-09-03T10:00:00
measurement: cpu_usage
host: server-01
region: ap-south
value: 72.4
"""
)

section("Why Time-Series Databases Are Specialized")

explain("""
Time-series workloads often have predictable characteristics:

    - data arrives continuously
    - timestamps are central
    - writes are frequent
    - recent data is queried often
    - historical data may be aggregated
    - old data may expire
    - range queries over time are common

Typical queries include:

    Average CPU usage over the last hour.

    Maximum temperature during the previous day.

    Number of requests per minute.

    95th percentile latency over seven days.
""")

section("Retention")

explain("""
Time-series systems commonly support retention concepts.

For example:

    Raw data:
        keep for 7 days

    Aggregated hourly data:
        keep for 90 days

    Aggregated daily data:
        keep for 2 years

This can dramatically reduce long-term storage requirements.
""")

section("Downsampling")

explain("""
Suppose a monitoring system stores one value every second.

One day contains:

    86,400 seconds

Instead of retaining every raw point forever, historical data
can sometimes be aggregated.

For example:

    1-second data
        |
        v
    1-minute averages
        |
        v
    1-hour averages
        |
        v
    1-day averages

This is called downsampling or aggregation depending on the
implementation and context.
""")

section("Time-Series Peculiarity")

explain("""
Time-series systems are usually optimized for ordered temporal
access.

A general-purpose relational database can absolutely store
time-series data.

The difference is that a specialized time-series system may provide
purpose-built mechanisms for:

    - ingestion
    - timestamp indexing
    - compression
    - retention
    - window queries
    - aggregation
    - monitoring workloads
""")


# ============================================================
# 13. NEWSQL
# ============================================================

title("12. NEWSQL DATABASES")

explain("""
NewSQL refers broadly to relational database systems that aim to
provide SQL and strong transactional semantics while also supporting
modern distributed and horizontally scalable architectures.

The motivation is based on a tension:

Traditional relational databases are excellent at:

    - SQL
    - transactions
    - consistency
    - relational modeling

Distributed NoSQL systems often emphasize:

    - horizontal scalability
    - distribution
    - high availability
    - large-scale workloads

NewSQL attempts to combine important properties from both worlds.
""")

section("Conceptual Position")

show_example(
    "High-level comparison",
    """
    Traditional Relational
            |
            | SQL + ACID
            v
         NewSQL
            |
            | SQL + ACID + distributed architecture
            v
    Horizontally Scalable Relational System
"""
)

section("Distributed Transactions")

explain("""
A distributed NewSQL system may distribute data across multiple
machines while still allowing applications to use transactions.

This is difficult because a transaction may involve data stored
on different nodes.

The system may need:

    - distributed coordination
    - consensus
    - replication
    - transaction ordering
    - conflict handling
    - failure recovery

The benefit is that an application can retain relational semantics
while operating across a distributed infrastructure.
""")

section("NewSQL Trade-Offs")

explain("""
Distributed relational systems introduce additional complexity.

Potential costs include:

    - network latency
    - coordination overhead
    - operational complexity
    - distributed transaction cost
    - more complex failure scenarios

NewSQL is therefore not simply "better SQL."

It is useful when the workload actually benefits from distributed
relational architecture.
""")


# ============================================================
# 14. CAP THEOREM
# ============================================================

title("13. CAP THEOREM")

explain("""
CAP is one of the most frequently discussed concepts in distributed
database architecture.

The three properties are:

    C = Consistency
    A = Availability
    P = Partition tolerance

The key idea is about behavior when a network partition occurs.

A distributed system cannot simultaneously guarantee all three
properties in their strongest interpretations during a partition.

Partition tolerance matters because network partitions can occur
in distributed systems.

Therefore, the practical question often becomes:

    During a partition, should the system favor stronger consistency
    or greater availability?
""")

section("Consistency")

explain("""
Consistency in CAP refers to a specific distributed-systems
meaning.

After a successful operation, clients should observe a single,
up-to-date view according to the system's consistency model.

This should not be confused with the "C" in ACID.

ACID consistency and CAP consistency are related concepts but they
are not interchangeable terms.
""")

section("Availability")

explain("""
CAP availability means that every request to a non-failing node
receives a response.

The response may not necessarily contain the newest data under
weaker consistency models.

This is different from saying:

    "The server is online."

CAP availability is a formal distributed-system property.
""")

section("Partition Tolerance")

explain("""
A partition occurs when nodes cannot reliably communicate.

For example:

    Node A ----X---- Node B

The system must continue operating despite the communication failure
if it is designed to tolerate partitions.

Distributed systems generally must account for this possibility.
""")


# ============================================================
# 15. ACID VS BASE
# ============================================================

title("14. ACID VS BASE")

explain("""
ACID emphasizes strong transactional behavior.

BASE is often associated with distributed NoSQL systems.

BASE is commonly expanded as:

    Basically Available
    Soft state
    Eventual consistency

Eventual consistency means that replicas may temporarily disagree,
but under appropriate conditions they converge toward the same state.

This can be useful when immediate global consistency is not required.
""")

section("Example")

explain("""
Imagine a social media "like" counter.

A system might tolerate:

    User A sees 1,000 likes.
    User B briefly sees 998 likes.

After replication catches up:

    Both eventually see 1,000 likes.

For some applications this is acceptable.

For a banking balance, the same level of temporary inconsistency
may be unacceptable.

The correct consistency model depends on the business operation.
""")


# ============================================================
# 16. CONSISTENCY MODELS
# ============================================================

title("15. CONSISTENCY MODELS")

explain("""
Distributed databases can provide different consistency guarantees.

Important concepts include:

    Strong consistency
    Eventual consistency
    Linearizability
    Sequential consistency
    Causal consistency
    Read-your-writes consistency
    Monotonic reads

Linearizability is particularly strong.

It makes operations appear as though each operation takes effect
atomically at some point between its invocation and completion,
while respecting real-time ordering.

Eventual consistency is weaker.

It permits temporary divergence between replicas.
""")

section("Read-Your-Writes")

explain("""
Suppose a user changes:

    name = "Atul"

Immediately afterward, the same user reads their profile.

A read-your-writes guarantee means they should not unexpectedly
receive the old value.

This illustrates why "consistency" can have several useful levels
rather than being simply on or off.
""")


# ============================================================
# 17. REPLICATION
# ============================================================

title("16. REPLICATION")

explain("""
Replication means maintaining multiple copies of data.

Example:

    Primary
      |
      +------ Replica 1
      |
      +------ Replica 2

Benefits can include:

    - fault tolerance
    - read scaling
    - disaster recovery
    - geographic distribution

But replication introduces questions:

    How quickly do replicas receive updates?

    Can replicas accept writes?

    What happens if replicas disagree?

    What happens when a replica is unavailable?

    How is a failed node recovered?
""")

section("Synchronous vs Asynchronous Replication")

explain("""
Synchronous replication:

    A write may wait until another replica acknowledges it.

Possible benefit:

    stronger durability / consistency guarantees

Possible cost:

    higher write latency

Asynchronous replication:

    The primary may acknowledge the write before replicas have
    received it.

Possible benefit:

    lower write latency

Possible cost:

    replicas can temporarily lag.
""")

section("Leader-Based Replication")

explain("""
A common architecture is:

    Leader / Primary
          |
          +---- Follower / Replica
          |
          +---- Follower / Replica

Writes go to the leader.

Reads may be served by replicas depending on the consistency model.

This model is conceptually simple but introduces leader-failure
and failover considerations.
""")


# ============================================================
# 18. SHARDING
# ============================================================

title("17. SHARDING / PARTITIONING")

explain("""
Sharding means distributing data across multiple machines.

Example:

    Shard 1 -> Users 1 through 1,000,000
    Shard 2 -> Users 1,000,001 through 2,000,000
    Shard 3 -> Users 2,000,001 through 3,000,000

Instead of one server storing everything:

                Application
                     |
          +----------+----------+
          |          |          |
        Shard 1    Shard 2    Shard 3

Sharding allows storage and workload to be distributed.
""")

section("Common Partitioning Strategies")

explain("""
Range partitioning:

    IDs 1-1000
    IDs 1001-2000
    IDs 2001-3000

Hash partitioning:

    hash(key) -> partition

Directory-based partitioning:

    lookup table -> partition

Geographic partitioning:

    India -> shard A
    Europe -> shard B
    America -> shard C
""")

section("Hot Partitions")

explain("""
A hot partition occurs when a disproportionate amount of traffic
goes to one partition.

Example:

    Partition by date

If today's date receives nearly all writes:

    Today -> extremely high traffic
    Yesterday -> low traffic
    Older -> almost no traffic

The partitioning strategy may therefore create a bottleneck.

Good partition-key design attempts to distribute workload.
""")


# ============================================================
# 19. HORIZONTAL VS VERTICAL SCALING
# ============================================================

title("18. SCALING DATABASES")

explain("""
Vertical scaling means increasing the resources of one machine.

For example:

    More CPU
    More RAM
    Faster storage

Horizontal scaling means adding machines.

For example:

    Server 1
    Server 2
    Server 3
    Server 4

Relational databases can scale vertically and can also scale
horizontally through replication, partitioning, sharding, or
distributed architectures.

NoSQL databases are often designed with horizontal distribution
as a central architectural property.

NewSQL systems explicitly target distributed relational workloads.
""")

section("Scaling Dimensions")

explain("""
Database scaling is not only about storage.

There are several dimensions:

    storage capacity
    write throughput
    read throughput
    network bandwidth
    memory capacity
    query complexity
    concurrent connections
    transaction rate
    latency requirements
    geographic distribution
""")


# ============================================================
# 20. OLTP
# ============================================================

title("19. OLTP")

explain("""
OLTP means Online Transaction Processing.

OLTP systems process many relatively small transactions.

Examples:

    banking
    order processing
    payments
    inventory
    account management

Typical characteristics:

    - frequent writes
    - frequent reads
    - low latency
    - concurrent users
    - transactional correctness

Relational databases are traditionally strong in OLTP.
""")

show_example(
    "Typical OLTP operation",
    """
BEGIN;

UPDATE accounts
SET balance = balance - 100
WHERE account_id = 1;

UPDATE accounts
SET balance = balance + 100
WHERE account_id = 2;

COMMIT;
"""
)


# ============================================================
# 21. OLAP
# ============================================================

title("20. OLAP")

explain("""
OLAP means Online Analytical Processing.

OLAP systems focus on analytical queries over large datasets.

Examples:

    total revenue by year
    customer segmentation
    average order value
    sales by region
    monthly growth

Analytical queries may scan millions or billions of records.

Typical OLAP systems often use:

    - columnar storage
    - data warehouses
    - analytical engines
    - distributed query processing
""")

section("OLTP vs OLAP")

show_example(
    "Conceptual comparison",
    """
    OLTP
    ----
    "Process this payment."

    OLAP
    ----
    "Calculate revenue by region for the previous
     three years and compare quarterly growth."
"""
)


# ============================================================
# 22. ROW STORAGE VS COLUMN STORAGE
# ============================================================

title("21. ROW-ORIENTED VS COLUMN-ORIENTED STORAGE")

explain("""
Row-oriented storage stores the fields of a record together.

Conceptually:

    Row 1:
        ID | Name | Age | City

    Row 2:
        ID | Name | Age | City

This is often useful when retrieving complete records.

Column-oriented storage groups values by column.

Conceptually:

    ID:
        1, 2, 3, 4

    Name:
        A, B, C, D

    Age:
        20, 30, 40, 50

This can be highly effective for analytical queries that read only
a subset of columns across many rows.

Example:

    SELECT AVG(age)
    FROM customers;

A columnar engine may avoid reading unrelated columns such as
address, phone number, and biography.
""")


# ============================================================
# 23. STORAGE ENGINES
# ============================================================

title("22. STORAGE ENGINES AND INTERNAL STRUCTURES")

explain("""
The logical database model does not tell the whole story.

Database engines use internal structures to make operations fast.

Common structures include:

    B-trees
    B+ trees
    Hash tables
    LSM trees
    SSTables
    Write-ahead logs
    Memtables
    Bloom filters

B-tree family indexes are common in relational systems.

LSM-tree-style architectures are common in many systems optimized
for heavy writes and distributed storage.

The distinction is:

    Data model:
        How users logically represent data.

    Storage engine:
        How the database physically manages data.
""")

section("Write-Ahead Logging")

explain("""
Write-ahead logging, or WAL, is a technique where changes are
recorded in a log before the corresponding data pages are considered
durably updated.

Conceptually:

    Application
        |
        v
    Transaction
        |
        v
    WAL
        |
        v
    Data pages

If a failure occurs, the log can help recover changes.

WAL is an important component of durability and crash recovery
in many database systems.
""")

section("LSM Trees")

explain("""
Log-structured merge-tree designs typically optimize write-heavy
workloads.

A simplified conceptual flow is:

    Incoming writes
          |
          v
      Memtable
          |
          v
       SSTable
          |
          v
    Background compaction

Compaction combines and reorganizes immutable files.

Benefits can include efficient sequential writes.

Costs can include:

    - write amplification
    - read amplification
    - compaction overhead
    - temporary storage requirements

This is one reason database performance cannot be judged only
from the logical data model.
""")


# ============================================================
# 24. DATABASE TRANSACTIONS
# ============================================================

title("23. TRANSACTIONS")

explain("""
A transaction is a logical unit of work.

Example:

    Create order
    Reduce inventory
    Record payment

If these operations belong to one business transaction, the
application may need guarantees about what happens when one
operation fails.

Conceptually:

    BEGIN

        operation 1
        operation 2
        operation 3

    COMMIT

or:

    ROLLBACK
""")

section("Optimistic vs Pessimistic Concurrency")

explain("""
Pessimistic concurrency assumes conflicts may occur and uses
locking or related mechanisms to prevent unsafe concurrent changes.

Optimistic concurrency assumes conflicts are relatively uncommon
and checks whether a conflict occurred before committing.

Optimistic approach:

    Read version 10
    Make changes
    Write only if version is still 10

If another transaction changed the row to version 11,
the update fails and may need to be retried.
""")


# ============================================================
# 25. CONSISTENCY AND DATABASE TYPE
# ============================================================

title("24. DATABASE TYPE DOES NOT DETERMINE ONE CONSISTENCY LEVEL")

explain("""
It is a mistake to assume:

    Relational = always strongly consistent

or:

    NoSQL = always eventually consistent

Modern database systems are more nuanced.

Relational databases can participate in distributed architectures.

NoSQL systems can provide strong consistency for particular
operations or configurations.

Some systems offer tunable consistency.

Therefore, consistency should be evaluated from the actual
database's guarantees, configuration, and operation being performed.
""")


# ============================================================
# 26. DATABASE SELECTION BY WORKLOAD
# ============================================================

title("25. CHOOSING A DATABASE BY WORKLOAD")

explain("""
The correct question is not:

    "Which database is the best?"

The better question is:

    "Which database model fits this workload?"

Consider the following patterns.
""")

section("Banking Transactions")

explain("""
Requirements:

    - strong transactional semantics
    - correctness
    - constraints
    - predictable consistency
    - complex relationships

A relational database or distributed relational/NewSQL system
is often a strong candidate.
""")

section("Session Storage")

explain("""
Requirements:

    - extremely fast key lookup
    - short-lived data
    - simple access pattern

A key-value database is often a natural fit.
""")

section("Product Catalog")

explain("""
Requirements may include:

    - flexible attributes
    - different product categories
    - nested information
    - frequent reads

A document model can be attractive.
""")

section("Social Network Relationships")

explain("""
Requirements:

    - friends
    - followers
    - recommendations
    - paths
    - relationship traversal

A graph model can be attractive.
""")

section("IoT Monitoring")

explain("""
Requirements:

    - huge volume of timestamped measurements
    - recent-data queries
    - aggregations
    - retention
    - downsampling

A time-series database can be a strong fit.
""")

section("Massive Distributed Event Workload")

explain("""
Requirements may include:

    - high write volume
    - distributed storage
    - predictable query patterns
    - horizontal scalability

A wide-column system may be appropriate.
""")


# ============================================================
# 27. POLYGLOT PERSISTENCE
# ============================================================

title("26. POLYGLOT PERSISTENCE")

explain("""
Polyglot persistence means using different data storage technologies
for different workloads within the same larger system.

For example:

    PostgreSQL
        -> financial transactions

    Redis
        -> caching and sessions

    MongoDB
        -> flexible product documents

    Neo4j
        -> relationship analysis

    InfluxDB
        -> metrics

This approach recognizes that one data model may not be optimal
for every problem.
""")

section("Cost of Polyglot Persistence")

explain("""
Using multiple databases creates additional operational complexity.

The organization may need to manage:

    - multiple backup systems
    - multiple monitoring systems
    - multiple security models
    - multiple client libraries
    - multiple deployment systems
    - data synchronization
    - consistency between systems
    - different failure modes

Polyglot persistence is therefore an architectural decision,
not simply a list of technologies.
""")


# ============================================================
# 28. CACHE VS DATABASE
# ============================================================

title("27. CACHE VS DATABASE")

explain("""
A cache stores data primarily to make repeated access faster.

A database is generally responsible for durable persistence.

Example:

    Database:
        PostgreSQL

    Cache:
        Redis

Flow:

    Application
        |
        v
      Cache
       / \
    hit   miss
     |      |
     |      v
     |    Database
     |      |
     +------+

Caching introduces important concerns:

    - stale data
    - invalidation
    - expiration
    - memory limits
    - cache stampedes
    - consistency

A cache should not automatically be treated as a replacement
for durable storage.
""")


# ============================================================
# 29. DATABASE NORMALIZATION VS DENORMALIZATION
# ============================================================

title("28. NORMALIZATION VS DENORMALIZATION IN PRACTICE")

explain("""
Suppose we have:

    customers
    orders
    products

A normalized relational design may separate these entities.

This reduces duplication.

A denormalized design may store frequently accessed information
together.

For example:

    order_id
    customer_name
    customer_city
    product_name
    product_price
    quantity

Denormalization can reduce joins.

But it creates duplication.

If customer_city changes, multiple records may need updating.

This produces a fundamental trade-off:

    Less duplication
        vs
    Faster or simpler reads

The correct choice depends on workload and correctness requirements.
""")


# ============================================================
# 30. SCHEMA-ON-WRITE VS SCHEMA-ON-READ
# ============================================================

title("29. SCHEMA-ON-WRITE VS SCHEMA-ON-READ")

explain("""
Schema-on-write means data is expected to conform to a schema
before or during storage.

Traditional relational systems strongly emphasize this approach.

Example:

    age INTEGER

Trying to store:

    age = "unknown"

may violate the schema.

Schema-on-read means raw or flexible data can be stored and
interpreted when it is read.

This is common in flexible data systems and data lakes.

Neither approach is universally superior.

Schema-on-write can improve:

    - integrity
    - predictability
    - query consistency

Schema-on-read can improve:

    - flexibility
    - ingestion speed
    - accommodation of changing data
""")


# ============================================================
# 31. DATABASE CONSTRAINTS
# ============================================================

title("30. DATABASE CONSTRAINTS")

explain("""
Relational systems commonly support constraints such as:

    PRIMARY KEY
    FOREIGN KEY
    UNIQUE
    NOT NULL
    CHECK

Example:

CREATE TABLE accounts (
    account_id INTEGER PRIMARY KEY,
    balance DECIMAL(15, 2) CHECK (balance >= 0)
);

Constraints move some business rules into the database.

This is valuable because multiple applications or services may
otherwise implement the same rule differently.

Not every database model provides the same constraint mechanisms.
""")


# ============================================================
# 32. QUERY LANGUAGE DIFFERENCES
# ============================================================

title("31. QUERY LANGUAGES")

explain("""
Relational systems commonly use SQL.

Example:

SELECT *
FROM customers
WHERE city = 'Lucknow';

Document systems may use document-oriented query APIs.

Graph systems may use languages such as Cypher or Gremlin depending
on the product and ecosystem.

Key-value systems commonly expose operations such as:

    GET
    SET
    DELETE

Wide-column systems often use query languages or APIs designed
around partitioning and access patterns.

Time-series systems may provide specialized query languages,
SQL-like interfaces, or domain-specific query APIs.

The query language reflects the data model.
""")

section("Why This Matters")

explain("""
A query language is not merely syntax.

It reflects what the database considers a natural operation.

Relational:

    joins and set operations

Graph:

    traversal

Key-value:

    direct key lookup

Document:

    document filtering

Time-series:

    temporal filtering and aggregation

Wide-column:

    partition-oriented access
""")


# ============================================================
# 33. DATABASE LATENCY
# ============================================================

title("32. LATENCY")

explain("""
Latency is the time required to complete an operation.

Common measurements include:

    p50
    p90
    p95
    p99
    p99.9

p50 means median latency.

p99 means 99% of requests are at or below that latency,
while the slowest 1% are above it.

Tail latency matters significantly in distributed systems.

A database may have:

    p50 = 5 ms
    p99 = 80 ms

Averages alone may hide this behavior.
""")

section("Latency Sources")

explain("""
Database latency can come from:

    - network communication
    - disk I/O
    - cache misses
    - locks
    - transaction coordination
    - replication
    - query execution
    - index access
    - CPU contention
    - garbage collection
    - compaction
    - distributed consensus
""")


# ============================================================
# 34. THROUGHPUT
# ============================================================

title("33. THROUGHPUT")

explain("""
Throughput measures how much work a system can process in a period.

Examples:

    10,000 reads per second

    5,000 writes per second

    100,000 events per second

Latency and throughput are different.

A system can have:

    high throughput
    but high latency

or:

    low latency
    but limited throughput

Database architecture must consider both.
""")


# ============================================================
# 35. AVAILABILITY
# ============================================================

title("34. AVAILABILITY")

explain("""
Availability describes whether a service remains operational
and able to serve requests.

A common expression is:

    availability = successful service time / total expected service time

Availability targets are sometimes expressed as percentages.

For example:

    99%
    99.9%
    99.99%
    99.999%

The number of "nines" represents increasingly strict uptime
requirements.

High availability commonly requires:

    - replication
    - failover
    - redundancy
    - health checks
    - monitoring
    - automated recovery
""")


# ============================================================
# 36. DURABILITY
# ============================================================

title("35. DURABILITY")

explain("""
Durability concerns whether committed data survives failures.

Possible failure scenarios include:

    - process crash
    - machine failure
    - storage failure
    - power failure
    - network failure
    - data-center failure

Mechanisms supporting durability can include:

    - write-ahead logs
    - replicated storage
    - synchronous replication
    - backups
    - snapshots
    - point-in-time recovery
    - geographically distributed copies
""")

section("Backup Is Not Replication")

explain("""
Replication and backup solve different problems.

Replication provides additional copies for availability and
operational continuity.

Backups provide historical recovery points.

If corrupted data is replicated immediately, replicas may also
contain the corruption.

A backup can allow recovery to an earlier state.
""")


# ============================================================
# 37. DATABASE FAILURE MODES
# ============================================================

title("36. DATABASE FAILURE MODES")

explain("""
Database failures can happen at several levels.

Application level:

    incorrect queries
    incorrect updates
    logical bugs

Database level:

    deadlocks
    constraint violations
    corruption
    overloaded queries

Infrastructure level:

    disk failure
    CPU exhaustion
    memory exhaustion
    network failure

Distributed level:

    network partitions
    replica lag
    leader failure
    split-brain scenarios
    clock-related problems
    consensus failures

A good database architecture is designed around failure assumptions,
not only normal operation.
""")


# ============================================================
# 38. DEADLOCKS
# ============================================================

title("37. DEADLOCKS")

explain("""
A deadlock occurs when transactions wait for one another in a cycle.

Example:

    Transaction A locks Resource 1
    Transaction B locks Resource 2

    A waits for Resource 2
    B waits for Resource 1

Result:

    A waits for B
    B waits for A

Neither can proceed.

Database systems may detect deadlocks and abort one transaction.

Applications should often be prepared to retry safe transactions.
""")


# ============================================================
# 39. READ / WRITE PATTERNS
# ============================================================

title("38. READ PATTERNS AND WRITE PATTERNS")

explain("""
Database design should begin with understanding access patterns.

Questions include:

    How much data is written?

    How much data is read?

    Are reads by primary key?

    Are reads by range?

    Are joins required?

    Are graph traversals required?

    Are queries mostly historical?

    Is the data immutable?

    Are records frequently updated?

    Are updates concurrent?

    Is ordering important?

    Is aggregation common?

    Is global consistency required?

These questions often tell us more about the appropriate database
than the raw number of records.
""")


# ============================================================
# 40. IMMUTABLE DATA
# ============================================================

title("39. IMMUTABLE VS MUTABLE DATA")

explain("""
Mutable data changes in place.

Example:

    customer.email

may change from:

    old@example.com

to:

    new@example.com

Immutable event data is normally appended rather than changed.

Example:

    PaymentCreated
    PaymentAuthorized
    PaymentCompleted

Event-oriented workloads can benefit from append-heavy storage
designs.

Time-series and wide-column systems often work well with high-volume
append-oriented workloads.
""")


# ============================================================
# 41. EVENT SOURCING
# ============================================================

title("40. EVENT SOURCING")

explain("""
Event sourcing stores state changes as events.

Instead of storing only:

    account_balance = 5000

the system might store:

    AccountCreated
    MoneyDeposited(3000)
    MoneyDeposited(3000)
    MoneyWithdrawn(1000)

The current state can be derived by replaying events.

Benefits can include:

    - complete history
    - auditability
    - temporal reconstruction

Costs can include:

    - more complex reads
    - event schema evolution
    - replay cost
    - projection management

Event sourcing is an architectural pattern, not a database type.
""")


# ============================================================
# 42. POLYGLOT EXAMPLE
# ============================================================

title("41. COMPLETE MULTI-DATABASE EXAMPLE")

show_example(
    "E-commerce architecture",
    """
                         E-COMMERCE PLATFORM
                                  |
             +--------------------+--------------------+
             |                    |                    |
             v                    v                    v
       PostgreSQL              Redis              MongoDB
       -----------              -----              -------
       Orders                   Cache              Product
       Payments                 Sessions           Catalog
       Customers                Rate limits        Flexible fields
             |
             |
             v
       Transactional
           data

             +--------------------+
             |
             v
          Cassandra
          ----------
          Large-scale
          event/activity
          workloads

             +--------------------+
             |
             v
          Neo4j
          -----
          Recommendations
          relationship
          analysis

             +--------------------+
             |
             v
          Time-Series DB
          --------------
          Infrastructure
          metrics
          latency
          CPU
          memory
"""
)

explain("""
This architecture illustrates that database choice can be based
on bounded responsibilities.

The same organization can legitimately use several database models.
""")


# ============================================================
# 43. RELATIONAL VS DOCUMENT
# ============================================================

title("42. RELATIONAL VS DOCUMENT")

explain("""
Relational:

    Strong schema
    Tables
    Relationships
    SQL
    Joins
    Constraints
    Mature transactions

Document:

    Flexible document structure
    Nested data
    Document-oriented queries
    Convenient object-like representation
    Often easier horizontal distribution

Relational is often preferable when:

    relationships and transactions are central.

Document is often preferable when:

    records are naturally self-contained documents and schema
    flexibility is important.
""")


# ============================================================
# 44. RELATIONAL VS KEY-VALUE
# ============================================================

title("43. RELATIONAL VS KEY-VALUE")

explain("""
Relational:

    Complex queries
    joins
    transactions
    constraints
    rich schema

Key-value:

    direct lookup
    very simple access pattern
    high-speed retrieval
    distributed caching
    simple state

If the core operation is:

    GET user:101

key-value is natural.

If the core operation is:

    Find customers who purchased product X,
    group them by region,
    calculate total spending,
    and join customer records with orders,

a relational model is much more natural.
""")


# ============================================================
# 45. RELATIONAL VS GRAPH
# ============================================================

title("44. RELATIONAL VS GRAPH")

explain("""
Relational databases can represent graphs using foreign keys.

For example:

    users
    friendships

But repeated relationship traversal may require multiple joins.

Graph databases represent relationships directly.

A graph model can be particularly attractive for:

    path queries
    neighborhood queries
    recommendation relationships
    fraud rings
    dependency graphs

The key distinction is not that relational systems cannot represent
relationships.

They can.

The distinction is how central relationships are to the workload
and how the database executes those relationships.
""")


# ============================================================
# 46. DOCUMENT VS KEY-VALUE
# ============================================================

title("45. DOCUMENT VS KEY-VALUE")

explain("""
Both models can appear simple, but their query capabilities differ.

Key-value:

    key -> opaque or relatively simple value

Document:

    key -> structured document

A document system can usually inspect fields inside the document.

For example:

    Find documents where:

        city = "Lucknow"

A pure key-value model may not naturally support this unless an
additional indexing mechanism exists.
""")


# ============================================================
# 47. COLUMN-FAMILY VS RELATIONAL
# ============================================================

title("46. COLUMN-FAMILY VS RELATIONAL")

explain("""
Relational systems commonly support flexible ad-hoc querying
through SQL and joins.

Wide-column systems often expect known query patterns and design
partitions around those patterns.

Relational:

    Model relationships first.
    Query many combinations later.

Wide-column:

    Understand important queries first.
    Design data layout around those queries.

This difference is fundamental.
""")


# ============================================================
# 48. TIME-SERIES VS RELATIONAL
# ============================================================

title("47. TIME-SERIES VS RELATIONAL")

explain("""
A relational database can absolutely store timestamps.

The distinction is workload specialization.

A relational system can store:

    timestamp
    device_id
    value

A time-series system may optimize this workload with:

    compression
    retention
    downsampling
    time-based partitioning
    specialized aggregation
    high ingestion throughput

For moderate workloads, relational storage may be entirely adequate.

Specialization becomes valuable when the workload characteristics
justify it.
""")


# ============================================================
# 49. DATABASE TYPE DECISION MATRIX
# ============================================================

title("48. DATABASE TYPE DECISION MATRIX")

@dataclass
class DatabaseType:
    name: str
    model: str
    strong_area: str
    common_use: str
    major_tradeoff: str


database_types = [
    DatabaseType(
        "Relational",
        "Tables / relations",
        "Transactions, joins, integrity",
        "OLTP, financial systems, business applications",
        "Horizontal distribution can be complex"
    ),
    DatabaseType(
        "Document",
        "Documents",
        "Flexible nested records",
        "Catalogs, content, application objects",
        "Relationships can become duplicated or application-managed"
    ),
    DatabaseType(
        "Key-Value",
        "Key -> value",
        "Fast direct lookup",
        "Caching, sessions, counters",
        "Limited complex querying"
    ),
    DatabaseType(
        "Column-Family",
        "Wide rows / column families",
        "Distributed high-throughput workloads",
        "Large event and activity datasets",
        "Schema is strongly query-pattern dependent"
    ),
    DatabaseType(
        "Graph",
        "Nodes + relationships",
        "Relationship traversal",
        "Fraud, social networks, recommendations",
        "Not always ideal for conventional tabular workloads"
    ),
    DatabaseType(
        "Time-Series",
        "Timestamped measurements",
        "Temporal ingestion and queries",
        "Metrics, IoT, monitoring",
        "Specialized for temporal workloads"
    ),
    DatabaseType(
        "NewSQL",
        "Relational + distributed",
        "SQL + transactions + horizontal scaling",
        "Distributed transactional applications",
        "Distributed coordination adds complexity"
    ),
]


for db in database_types:
    print(f"\n{db.name}")
    print(f"  Model:            {db.model}")
    print(f"  Strong area:      {db.strong_area}")
    print(f"  Common use:       {db.common_use}")
    print(f"  Major trade-off:  {db.major_tradeoff}")


# ============================================================
# 50. DECISION QUESTIONS
# ============================================================

title("49. DATABASE SELECTION QUESTIONS")

questions = [
    "Do I need complex relationships and joins?",
    "Do I need strong multi-record transactions?",
    "Is my data naturally represented as documents?",
    "Is most access based on a known key?",
    "Do I have extremely high distributed write throughput?",
    "Are relationships and graph traversal central to the application?",
    "Is time the dominant dimension of my data?",
    "Do I need horizontal scaling across many machines?",
    "Are queries predictable or highly ad-hoc?",
    "Do I need strict schema enforcement?",
    "How much data duplication is acceptable?",
    "What consistency guarantees are required?",
    "What is the acceptable write latency?",
    "What is the acceptable read latency?",
    "What happens if a network partition occurs?",
    "How much operational complexity can the system support?",
]

for number, question in enumerate(questions, start=1):
    print(f"{number:2}. {question}")


# ============================================================
# 51. COMMON MISCONCEPTIONS
# ============================================================

title("50. COMMON DATABASE MISCONCEPTIONS")

misconceptions = {
    "NoSQL means no SQL":
        "NoSQL is a broad category of non-relational data models and systems.",

    "NoSQL is always faster":
        "Performance depends on workload, query pattern, indexes, hardware, "
        "distribution, and implementation.",

    "Relational databases cannot scale":
        "Relational systems can scale vertically and horizontally through "
        "replication, partitioning, sharding, clustering, and distributed designs.",

    "More indexes always improve performance":
        "Indexes improve some reads but increase storage and write overhead.",

    "MongoDB means no schema":
        "Flexible document schemas still require application and data-design discipline.",

    "Graph databases are only for social networks":
        "Graphs are useful for any workload where relationship traversal is important.",

    "Time-series databases are required for every timestamped table":
        "Relational databases can handle many time-series workloads.",

    "CAP means choose any two at all times":
        "CAP concerns guarantees during network partitions in distributed systems.",

    "Replication is the same as backup":
        "Replication supports availability; backups provide historical recovery.",

    "Database type alone determines consistency":
        "Consistency depends on the actual system, configuration, operation, and architecture.",
}

for misconception, correction in misconceptions.items():
    print(f"\nMisconception:")
    print(f"    {misconception}")
    print(f"Correction:")
    print(f"    {correction}")


# ============================================================
# 52. DATABASE ARCHITECTURE LAYERS
# ============================================================

title("51. DATABASE ARCHITECTURE LAYERS")

show_example(
    "Conceptual database stack",
    """
    Application
        |
        v
    Database Client / Driver
        |
        v
    Query Interface
        |
        v
    Query Parser / Planner
        |
        v
    Execution Engine
        |
        +-----------------------+
        |                       |
        v                       v
    Transaction Manager      Cache / Buffer
        |
        v
    Storage Engine
        |
        +-----------------------+
        |
        v
    Files / SSD / Distributed Storage
        |
        v
    Replication / Recovery / Backup
"""
)

explain("""
This layered view helps separate logical database behavior from
physical implementation.

For example:

SQL syntax belongs primarily to the query interface.

Join optimization belongs to query planning and execution.

Locks and transaction isolation belong to concurrency and
transaction management.

B-trees and LSM structures belong to storage implementation.

Replication belongs to distributed architecture.

These layers interact, but they are conceptually different.
""")


# ============================================================
# 53. DATABASE SECURITY
# ============================================================

title("52. DATABASE SECURITY")

explain("""
Database security includes:

    authentication
    authorization
    encryption
    auditing
    network controls
    secrets management
    access policies
    backup protection
    data masking
    logging

Authentication answers:

    "Who are you?"

Authorization answers:

    "What are you allowed to do?"
""")

section("Least Privilege")

explain("""
Applications should generally receive only the permissions required
for their responsibilities.

For example:

    reporting_user:
        SELECT only

    application_user:
        SELECT / INSERT / UPDATE

    administrative_user:
        schema and operational permissions

Excessive database permissions increase the impact of application
compromise or credential leakage.
""")


# ============================================================
# 54. DATABASE MIGRATIONS
# ============================================================

title("53. DATABASE MIGRATIONS")

explain("""
A migration changes database structure in a controlled manner.

Examples:

    add a column
    create an index
    create a table
    rename a field
    modify constraints

A migration should be treated as part of software evolution.

A dangerous migration can cause:

    downtime
    table locks
    excessive replication lag
    application incompatibility
    data loss

Large systems often use backward-compatible migration strategies.
""")


# ============================================================
# 55. SCHEMA EVOLUTION
# ============================================================

title("54. SCHEMA EVOLUTION")

explain("""
Schema evolution means changing the structure of data over time.

Relational example:

    version 1:
        name

    version 2:
        first_name
        last_name

Document systems face similar issues:

    old documents
    new documents
    mixed versions

A robust application may need to understand more than one document
version during migration.

Schema evolution is therefore a data-lifecycle problem, not merely
a database syntax problem.
""")


# ============================================================
# 56. DATA INTEGRITY
# ============================================================

title("55. DATA INTEGRITY")

explain("""
Data integrity means maintaining correctness and validity of data.

Types include:

    Entity integrity
    Referential integrity
    Domain integrity

Entity integrity:

    Each entity can be uniquely identified.

Referential integrity:

    Relationships between entities remain valid.

Domain integrity:

    Values follow allowed rules.

Examples:

    age must be non-negative

    email must follow expected constraints

    order.customer_id must refer to a valid customer
""")


# ============================================================
# 57. QUERY OPTIMIZATION
# ============================================================

title("56. QUERY OPTIMIZATION")

explain("""
A database usually does not simply execute a SQL statement literally.

It may:

    parse the query
    transform it
    estimate costs
    choose indexes
    reorder joins
    choose join algorithms
    choose scan methods
    produce an execution plan

Common join algorithms include:

    nested loop join
    hash join
    merge join

Possible access methods include:

    sequential scan
    index scan
    index-only scan

The optimizer attempts to find an efficient execution strategy.
""")

section("Statistics")

explain("""
Query optimizers commonly rely on statistics about the data.

Examples:

    number of rows
    value distribution
    selectivity
    distinct values

If statistics are inaccurate, the optimizer may choose a poor plan.

This is why database performance involves both schema design and
query-planning behavior.
""")


# ============================================================
# 58. SELECTIVITY
# ============================================================

title("57. SELECTIVITY")

explain("""
Selectivity describes how much a condition narrows a dataset.

Example:

    WHERE customer_id = 101

If only one row matches, the condition is highly selective.

Example:

    WHERE country = 'India'

If 30% of the database is from India, it is less selective.

Highly selective predicates are often good candidates for index
access, though the actual decision depends on the optimizer and
data distribution.
""")


# ============================================================
# 59. DISTRIBUTED CONSENSUS
# ============================================================

title("58. DISTRIBUTED CONSENSUS")

explain("""
Distributed databases may need multiple nodes to agree on decisions.

Consensus algorithms such as:

    Raft
    Paxos

are associated with distributed agreement.

Consensus can be used for things such as:

    leader election
    replicated state
    cluster coordination

Consensus is difficult because nodes can fail and networks can
delay or lose messages.

This is one reason distributed database architecture is more complex
than simply placing data on several servers.
""")


# ============================================================
# 60. QUORUM
# ============================================================

title("59. QUORUM")

explain("""
Some distributed systems use quorum-style replication.

Suppose data is replicated to:

    N = 3 nodes

A write may require:

    W = 2 acknowledgements

A read may require:

    R = 2 responses

Then:

    W + R > N

because:

    2 + 2 > 3

This overlap can help ensure that reads and writes share at least
one replica.

The exact semantics depend on the database and consistency model.
""")


# ============================================================
# 61. EVENTUAL CONSISTENCY EXAMPLE
# ============================================================

title("60. EVENTUAL CONSISTENCY EXAMPLE")

show_example(
    "Replica propagation",
    """
    Time 0:

        Primary: 100
        Replica A: 100
        Replica B: 100

    Write +10:

        Primary: 110
        Replica A: 100
        Replica B: 100

    Replication occurs:

        Primary: 110
        Replica A: 110
        Replica B: 110
"""
)

explain("""
During the intermediate period, replicas may disagree.

Eventually they converge.

This behavior can be acceptable for some workloads and unacceptable
for others.
""")


# ============================================================
# 62. HOT KEYS
# ============================================================

title("61. HOT KEYS")

explain("""
A hot key is a key that receives unusually high traffic.

Example:

    trending:homepage

If millions of users request the same key simultaneously, the
database or cache infrastructure can become overloaded.

Key-value systems are extremely efficient for direct lookup,
but an extremely popular key can still become a bottleneck.

Possible architectural responses include:

    replication
    request coalescing
    local caching
    key spreading
    partitioning
""")


# ============================================================
# 63. HOT ROWS
# ============================================================

title("62. HOT ROWS")

explain("""
A similar issue can occur in relational databases.

Suppose millions of requests repeatedly update:

    total_count

If every request modifies the same row, contention can develop.

The problem is not necessarily that relational databases are slow.

The problem is that many concurrent operations are competing for
the same piece of mutable state.
""")


# ============================================================
# 64. DATABASE CONNECTIONS
# ============================================================

title("63. CONNECTION MANAGEMENT")

explain("""
Applications communicate with databases through connections.

Creating a new connection for every request can be expensive.

Connection pools maintain reusable database connections.

Conceptually:

    Application
       |
       v
    Connection Pool
       |
       +---- Connection 1
       +---- Connection 2
       +---- Connection 3
       +---- Connection 4
       |
       v
    Database

Too few connections can limit throughput.

Too many connections can overload the database.

Connection management is therefore part of database architecture.
""")


# ============================================================
# 65. DATABASE OBSERVABILITY
# ============================================================

title("64. DATABASE OBSERVABILITY")

explain("""
Important database metrics include:

    query latency
    query throughput
    CPU usage
    memory usage
    disk utilization
    cache hit ratio
    connection count
    lock waits
    deadlocks
    replication lag
    transaction rate
    storage growth
    compaction activity
    error rate

Observability helps identify whether a problem originates from:

    application code
    query design
    database configuration
    hardware
    network
    distributed coordination
""")


# ============================================================
# 66. BACKUP AND RECOVERY
# ============================================================

title("65. BACKUP AND RECOVERY")

explain("""
Backup strategies may include:

    full backups
    incremental backups
    differential backups
    snapshots
    continuous archiving
    point-in-time recovery

Recovery planning should consider:

    RPO
    RTO

RPO = Recovery Point Objective

How much data loss is acceptable?

RTO = Recovery Time Objective

How quickly must service be restored?

These are architectural requirements, not merely operational details.
""")


# ============================================================
# 67. DATABASE CONSISTENCY SCENARIOS
# ============================================================

title("66. CONSISTENCY BY BUSINESS REQUIREMENT")

scenarios = {
    "Bank balance":
        "Usually requires strong correctness and carefully controlled transactions.",

    "Social media like count":
        "May tolerate temporary divergence depending on product requirements.",

    "Shopping cart":
        "Requires careful handling of concurrent updates; exact guarantees "
        "depend on business semantics.",

    "Monitoring metric":
        "Small delays or temporary aggregation differences may be acceptable.",

    "Fraud detection":
        "May require strong consistency for some decisions while allowing "
        "asynchronous processing for others.",

    "Product recommendation":
        "Often tolerates eventually consistent relationship and ranking data.",
}

for scenario, explanation in scenarios.items():
    print(f"\n{scenario}:")
    print(f"    {explanation}")


# ============================================================
# 68. DATABASE TYPE BY DATA RELATIONSHIP
# ============================================================

title("67. DATABASE TYPE BY DATA RELATIONSHIP")

explain("""
If the dominant relationship is:

    Entity <-> Entity
        -> relational

    Key <-> Value
        -> key-value

    Document <-> Nested data
        -> document

    Node <-> Relationship
        -> graph

    Time <-> Measurement
        -> time-series

    Partition <-> Wide row
        -> column-family

    Relational model + distributed architecture
        -> NewSQL

These are conceptual tendencies, not absolute rules.
""")


# ============================================================
# 69. DATABASE TYPE BY ACCESS PATTERN
# ============================================================

title("68. DATABASE TYPE BY ACCESS PATTERN")

patterns = [
    ("Known key lookup",
     "Key-value"),
    ("Complex joins",
     "Relational"),
    ("Nested object retrieval",
     "Document"),
    ("Relationship traversal",
     "Graph"),
    ("Timestamp range aggregation",
     "Time-series"),
    ("Huge distributed write workload",
     "Column-family"),
    ("SQL + distributed transactions",
     "NewSQL"),
]

for pattern, candidate in patterns:
    print(f"{pattern:<38} -> {candidate}")


# ============================================================
# 70. DATABASE TYPE BY SCHEMA
# ============================================================

title("69. DATABASE TYPE BY SCHEMA CHARACTERISTICS")

explain("""
Relational:

    schema-first

Document:

    flexible / evolving document structure

Key-value:

    minimal structural assumptions

Column-family:

    schema and partition design tied closely to query patterns

Graph:

    nodes and relationships with properties

Time-series:

    measurements, timestamps, tags, dimensions

NewSQL:

    relational schema with distributed execution and storage
""")


# ============================================================
# 71. DATABASE TYPE BY SCALE
# ============================================================

title("70. DATABASE TYPE BY SCALE CONSIDERATIONS")

explain("""
Scale should be considered in multiple dimensions.

A database may be large because of:

    millions of users
    billions of events
    enormous storage volume
    high request rates
    geographic distribution
    large analytical scans

A small database with difficult transaction requirements may need
a relational system.

A huge event stream may favor a distributed wide-column system.

A moderate graph workload may favor a graph database because the
relationships are the dominant problem.

Scale alone does not determine database type.
""")


# ============================================================
# 72. DATA LIFECYCLE
# ============================================================

title("71. DATA LIFECYCLE")

explain("""
Data typically passes through stages:

    ingestion
        |
        v
    active
        |
        v
    historical
        |
        v
    archived
        |
        v
    deleted

Different databases may be involved at different stages.

For example:

    operational database
        ->
    analytical store
        ->
    archive

Data lifecycle decisions affect:

    storage cost
    query performance
    retention
    compliance
    recovery
""")


# ============================================================
# 73. DATABASE AND MICROSERVICES
# ============================================================

title("72. DATABASES IN MICROSERVICES")

explain("""
A microservice architecture often gives each service ownership
over its data.

Example:

    Order Service
        -> Order database

    Payment Service
        -> Payment database

    Catalog Service
        -> Catalog database

This can improve service autonomy.

But it introduces distributed-data problems.

A transaction across:

    Order Service
    Payment Service
    Inventory Service

may no longer be a simple local database transaction.

This can lead to patterns such as:

    Saga
    Outbox pattern
    Event-driven integration
    Idempotent processing

Database architecture is therefore closely connected to application
architecture.
""")


# ============================================================
# 74. OUTBOX PATTERN
# ============================================================

title("73. OUTBOX PATTERN")

explain("""
Suppose an application needs to:

    update a database
    and publish an event

A failure between the two operations can create inconsistency.

The outbox pattern stores the business change and the event
record in the same local transaction.

Conceptually:

    Transaction
       |
       +--> Business data
       |
       +--> Outbox event

A separate process publishes the outbox event.

This creates a bridge between transactional storage and
asynchronous event processing.
""")


# ============================================================
# 75. SAGA PATTERN
# ============================================================

title("74. SAGA PATTERN")

explain("""
A saga coordinates a business process across multiple services.

Example:

    Order
      |
      v
    Payment
      |
      v
    Inventory
      |
      v
    Shipment

If a later step fails, compensating actions may be required.

For example:

    Payment succeeded
    Inventory failed

The system may need:

    Refund payment

This is different from a single ACID transaction spanning every
service.
""")


# ============================================================
# 76. DATABASE ANTI-PATTERNS
# ============================================================

title("75. DATABASE ANTI-PATTERNS")

anti_patterns = [
    "Using a database without understanding the access pattern.",
    "Creating indexes for every column.",
    "Using a relational database as a cache.",
    "Using a key-value database for complex relational analytics.",
    "Using a graph database simply because relationships exist.",
    "Treating document schema flexibility as permission for inconsistent data.",
    "Using one giant table for unrelated workloads.",
    "Ignoring transaction boundaries.",
    "Ignoring replication lag.",
    "Assuming a successful write is automatically durable under every configuration.",
    "Ignoring backup restoration testing.",
    "Allowing unlimited database connections.",
    "Running unbounded queries on very large datasets.",
    "Partitioning without considering hot partitions.",
    "Assuming averages represent tail latency.",
]

for item in anti_patterns:
    print(f"\n- {item}")


# ============================================================
# 77. FINAL TECHNICAL COMPARISON
# ============================================================

title("76. TECHNICAL COMPARISON")

comparison = [
    ("Relational",
     "Tables",
     "SQL",
     "Strong transactions",
     "Joins",
     "OLTP / business systems"),

    ("Document",
     "Documents",
     "Document query APIs",
     "Varies by system",
     "Embedded/reference relationships",
     "Flexible application data"),

    ("Key-Value",
     "Key-value",
     "GET/SET-like operations",
     "Varies",
     "Minimal",
     "Caching / sessions"),

    ("Column-Family",
     "Wide rows",
     "Query/API varies",
     "Often tunable",
     "Partition-oriented",
     "Large distributed workloads"),

    ("Graph",
     "Nodes + edges",
     "Graph query language",
     "Varies",
     "Native relationships",
     "Relationship-heavy workloads"),

    ("Time-Series",
     "Timestamped measurements",
     "Specialized / SQL-like",
     "Varies",
     "Temporal dimensions",
     "Metrics / IoT / monitoring"),

    ("NewSQL",
     "Relational",
     "SQL",
     "Strong transactional focus",
     "Distributed relational",
     "Distributed OLTP"),
]

headers = (
    "Type",
    "Model",
    "Query",
    "Transactions",
    "Relationship style",
    "Typical workload"
)

print(
    f"{headers[0]:<16}"
    f"{headers[1]:<24}"
    f"{headers[2]:<24}"
    f"{headers[3]:<28}"
    f"{headers[4]:<28}"
    f"{headers[5]}"
)

print("-" * 145)

for row in comparison:
    print(
        f"{row[0]:<16}"
        f"{row[1]:<24}"
        f"{row[2]:<24}"
        f"{row[3]:<28}"
        f"{row[4]:<28}"
        f"{row[5]}"
    )


# ============================================================
# 78. PRACTICAL DECISION TREE
# ============================================================

title("77. PRACTICAL DATABASE DECISION TREE")

show_example(
    "Decision tree",
    """
    START
      |
      +-- Are complex transactions and relationships central?
      |        |
      |       YES
      |        |
      |        +-- Need distributed horizontal relational scaling?
      |                 |
      |                YES -> NewSQL / distributed relational
      |
      +-- Is the data naturally a document?
      |        |
      |       YES -> Document database
      |
      +-- Is access primarily by a known key?
      |        |
      |       YES -> Key-value database
      |
      +-- Are relationships/traversals the central problem?
      |        |
      |       YES -> Graph database
      |
      +-- Is timestamped data the dominant workload?
      |        |
      |       YES -> Time-series database
      |
      +-- Is the workload massive, distributed, write-heavy,
      |    and driven by predictable access patterns?
      |        |
      |       YES -> Column-family database
      |
      +-- Otherwise:
               Evaluate relational database first,
               then compare alternatives against the
               actual workload.
"""
)


# ============================================================
# 79. CORE VOCABULARY
# ============================================================

title("78. CORE DATABASE VOCABULARY")

terms = {
    "Schema":
        "The structural definition of data.",
    "Table":
        "A relational structure containing rows and columns.",
    "Row":
        "A record or tuple in a relational table.",
    "Column":
        "An attribute or field in a relational table.",
    "Primary key":
        "A unique identifier for a record.",
    "Foreign key":
        "A reference to a key in another table.",
    "Index":
        "A structure used to accelerate data retrieval.",
    "Transaction":
        "A logical unit of database work.",
    "Replication":
        "Maintaining multiple copies of data.",
    "Sharding":
        "Distributing data across partitions or machines.",
    "Partition key":
        "A key used to determine data distribution.",
    "Consistency":
        "A guarantee about what values clients can observe.",
    "Availability":
        "The ability of a system to respond to requests.",
    "Durability":
        "Persistence of committed data across failures.",
    "Latency":
        "Time required to complete an operation.",
    "Throughput":
        "Amount of work processed over a period.",
    "OLTP":
        "Online transaction processing.",
    "OLAP":
        "Online analytical processing.",
    "Normalization":
        "Organizing data to reduce inappropriate redundancy.",
    "Denormalization":
        "Intentionally introducing redundancy for workload reasons.",
    "Index selectivity":
        "How effectively a condition narrows the dataset.",
    "Deadlock":
        "A cycle of transactions waiting for each other.",
    "Replication lag":
        "Delay between a source update and replica application.",
    "Quorum":
        "A required number of participating replicas for an operation.",
    "Consensus":
        "Agreement among distributed nodes about system state.",
}

for term, meaning in terms.items():
    print(f"\n{term}:")
    print(f"    {meaning}")


# ============================================================
# 80. KNOWLEDGE CHECK
# ============================================================

title("79. KNOWLEDGE CHECK")

questions_and_answers = [
    (
        "What is the primary abstraction of a relational database?",
        "Relations, usually represented as tables."
    ),
    (
        "What does SQL provide?",
        "A language for defining, querying, and manipulating relational data."
    ),
    (
        "What does NoSQL describe?",
        "A broad family of non-relational database models and systems."
    ),
    (
        "What is the fundamental abstraction of a key-value database?",
        "A key associated with a value."
    ),
    (
        "What is the fundamental abstraction of a document database?",
        "A structured document."
    ),
    (
        "What is central to a graph database?",
        "Nodes, relationships, and graph traversal."
    ),
    (
        "What is central to a time-series database?",
        "Timestamped measurements and temporal access patterns."
    ),
    (
        "What is a column-family database designed to handle well?",
        "Large-scale distributed workloads with predictable access patterns."
    ),
    (
        "What is NewSQL trying to combine?",
        "Relational SQL and transactional semantics with distributed scalability."
    ),
    (
        "What does ACID stand for?",
        "Atomicity, Consistency, Isolation, Durability."
    ),
    (
        "What does CAP discuss?",
        "Consistency, availability, and partition tolerance in distributed systems."
    ),
    (
        "What is replication?",
        "Maintaining multiple copies of data."
    ),
    (
        "What is sharding?",
        "Distributing data across partitions or machines."
    ),
    (
        "Why can indexes hurt write performance?",
        "Writes may need to update the indexes as well as the underlying data."
    ),
    (
        "Why can denormalization improve performance?",
        "It can reduce joins and make frequently accessed data available together."
    ),
]

for number, (question, answer) in enumerate(questions_and_answers, start=1):
    print(f"\n{number}. {question}")
    print(f"   Answer: {answer}")


# ============================================================
# 81. END
# ============================================================

title("DATABASE TYPES LEARNING PROGRAM COMPLETE")

explain("""
The program has covered the database types:

    Relational
    NoSQL
    NewSQL
    Document
    Key-value
    Column-family
    Graph
    Time-series

It has also covered the architectural concepts that distinguish
these systems:

    data models
    schemas
    normalization
    denormalization
    SQL
    transactions
    ACID
    BASE
    consistency
    CAP
    replication
    sharding
    partitioning
    indexes
    storage engines
    OLTP
    OLAP
    scaling
    latency
    throughput
    availability
    durability
    distributed consensus
    quorum
    query optimization
    database security
    migrations
    observability
    backup and recovery
    polyglot persistence
    microservice data ownership
    event sourcing
    outbox
    saga
    database anti-patterns

The central principle is that a database should be understood
through both its data model and its workload.

A database is not selected merely because it is popular.
Its suitability comes from how well its model, consistency,
query capabilities, storage architecture, scaling behavior,
and operational characteristics match the problem being solved.
""")
