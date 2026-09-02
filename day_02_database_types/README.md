# Database Types

## Relational, NoSQL, NewSQL, Graph, Document, Key-Value, Column-Family, and Time-Series Databases

This Python program explains the major database types and the architectural ideas that distinguish them. The main purpose is to understand why different databases exist, what kind of data model they use, what workloads they handle well, and what trade-offs appear when a system grows.

## 1. What a Database Is

A database is a system for storing, organizing, retrieving, updating, and managing data.

A database is not just a collection of records. A modern database system can provide:

* Persistent storage
* Data retrieval
* Data modification
* Transactions
* Concurrency control
* Indexes
* Constraints
* Replication
* Partitioning
* Recovery
* Backup
* Query optimization
* Authentication and authorization

The database management system is the software responsible for managing the stored data and providing these capabilities.

## 2. Database Models

A data model describes how data is logically represented.

The main models covered are:

* Relational
* Document
* Key-value
* Column-family
* Graph
* Time-series

NewSQL is slightly different because it is generally associated with relational data and SQL while using distributed architectures to provide horizontal scalability.

NoSQL is also a broad category rather than one specific data model. Document, key-value, column-family, and graph databases are commonly discussed as NoSQL families.

## 3. Relational Databases

A relational database represents data using relations, normally exposed as tables.

A table contains rows and columns.

A row represents a record, while a column represents an attribute.

Relational databases usually have a defined schema. They are strongly associated with SQL and are particularly useful when data has relationships that need to be queried through joins.

Important relational concepts include:

* Tables
* Rows
* Columns
* Primary keys
* Foreign keys
* Constraints
* Joins
* Indexes
* Transactions
* Normalization
* Denormalization

Relational databases are particularly strong for transactional systems such as banking, payments, order processing, inventory, customer management, and other business applications.

## 4. Primary Keys

A primary key uniquely identifies a record.

For example, a customer table may use `customer_id` as its primary key.

A primary key is important for uniqueness, efficient lookup, and relationships between tables.

## 5. Foreign Keys

A foreign key represents a relationship between tables.

An order can contain a `customer_id` that refers to a customer record.

This allows relational databases to represent relationships without storing the entire customer record inside every order.

Foreign keys can also enforce referential integrity.

## 6. Normalization

Normalization is the process of organizing relational data to reduce inappropriate duplication and improve integrity.

Important normal forms include:

* First Normal Form
* Second Normal Form
* Third Normal Form
* Boyce-Codd Normal Form
* Fourth Normal Form
* Fifth Normal Form

The purpose of normalization is not simply to create as many tables as possible. It is based on functional dependencies, data integrity, and appropriate representation of relationships.

A normalized design might separate:

* Customers
* Orders
* Products
* Order items

This avoids repeatedly storing the same customer or product information in every order record.

## 7. Denormalization

Denormalization intentionally introduces redundancy.

It can be useful when frequently accessed information should be stored together to reduce joins or improve read performance.

The trade-off is that duplicated data can require additional updates and can create consistency problems if the copies are not maintained correctly.

Therefore, normalization and denormalization represent different design choices rather than one being universally correct.

## 8. ACID Transactions

ACID represents:

* Atomicity
* Consistency
* Isolation
* Durability

Atomicity means that a transaction is treated as a logical unit.

Consistency means that a successful transaction leaves the database satisfying its defined integrity rules.

Isolation concerns how concurrent transactions interact.

Durability means committed data survives appropriate failures.

A bank transfer is a useful example. If money is removed from one account, the corresponding addition to the other account should be handled as one logical transaction.

## 9. Transaction Isolation

Database systems provide different isolation levels.

Common levels include:

* Read Uncommitted
* Read Committed
* Repeatable Read
* Serializable

Concurrency anomalies include:

* Dirty reads
* Non-repeatable reads
* Phantom reads
* Lost updates

Higher isolation generally provides stronger guarantees but can introduce additional coordination or reduce concurrency.

## 10. Indexes

An index is an additional data structure used to make data retrieval faster.

Common index structures include:

* B-trees
* Hash indexes
* Bitmap indexes
* GIN
* GiST
* R-tree structures

Indexes can dramatically improve read performance, but they are not free.

They consume storage and memory and may increase write cost because indexes can also need to be updated when underlying data changes.

Having more indexes does not automatically mean better performance.

## 11. NoSQL Databases

NoSQL is a broad category of database systems that do not primarily use the traditional relational table-and-join model.

NoSQL does not simply mean that SQL cannot exist anywhere in the system.

NoSQL systems are commonly associated with:

* Flexible schemas
* Horizontal scaling
* Distributed architectures
* High throughput
* Workload-specific data models
* Alternative approaches to relationships and querying

The major families covered are document, key-value, column-family, and graph databases.

## 12. Document Databases

A document database stores structured documents.

Documents commonly resemble JSON.

A document can contain:

* Scalar values
* Nested objects
* Arrays
* Embedded structures

This makes the document model useful when application objects naturally form self-contained documents.

Document databases are often useful for:

* Product catalogs
* Content management
* User profiles
* Application objects
* Flexible records
* Systems with evolving attributes

A document database can use embedding or references.

Embedding is useful when related data is usually retrieved together.

References are useful when the related entity has an independent lifecycle, is shared across many records, or should not be duplicated extensively.

Flexible schemas still require discipline. Without proper data design, document databases can develop inconsistent field names, different data types, duplicated information, and difficult migrations.

## 13. Key-Value Databases

A key-value database represents information primarily as:

`key -> value`

The application normally knows the key it wants and uses it to retrieve the associated value.

Typical examples of key-value use cases include:

* Caching
* Sessions
* Counters
* Rate limiting
* Feature flags
* Temporary state
* Shopping carts
* Fast lookups

The model is powerful because it makes direct lookup simple.

The limitation is that complicated queries involving many relationships or arbitrary filtering are not the natural strength of a key-value database.

## 14. Column-Family Databases

Column-family databases, also called wide-column databases, are designed for large distributed workloads.

Examples include systems such as Cassandra and HBase.

They are commonly designed around concepts such as:

* Partition keys
* Clustering columns
* Wide rows
* Distributed storage
* Query-specific data layouts

A major characteristic of column-family databases is query-driven design.

Instead of designing the database only around entities, the designer considers the queries the system must execute and structures partitions accordingly.

A good partition key distributes data and traffic.

A poor partition key can create a hot partition where one node receives a disproportionate amount of traffic.

Column-family databases can be particularly useful for high write throughput, very large datasets, distributed workloads, and predictable access patterns.

## 15. Graph Databases

Graph databases represent data using:

* Nodes
* Relationships
* Properties

For example:

`Atul -> WORKS_AT -> Company`

and:

`Atul -> KNOWS -> Rahul`

The important characteristic is that relationships are first-class elements of the model.

Graph databases are useful when relationship traversal is central to the workload.

Typical applications include:

* Social networks
* Recommendation systems
* Fraud detection
* Knowledge graphs
* Network analysis
* Dependency analysis
* Identity relationships
* Path and route analysis

A graph database is not simply a relational database with a graph visualization. Its data model and query engine are designed around relationships and traversal.

## 16. Time-Series Databases

Time-series databases are optimized for data in which time is a fundamental dimension.

Examples include:

* CPU metrics
* Memory usage
* IoT measurements
* Temperature readings
* Stock prices
* Application latency
* Request counts
* Infrastructure monitoring data

A typical time-series record contains:

* Timestamp
* Measurement
* Tags or dimensions
* Value

Time-series workloads often have frequent writes, temporal range queries, aggregation, retention requirements, and large historical datasets.

Specialized time-series systems can provide features such as:

* Time-based indexing
* Compression
* Retention policies
* Downsampling
* Temporal aggregation
* Efficient ingestion

A relational database can still store time-series data. A specialized system becomes useful when the characteristics of the workload justify it.

## 17. Downsampling

Downsampling means reducing the resolution of historical data by aggregating measurements.

For example:

* Raw measurements every second
* One-minute averages
* One-hour averages
* Daily averages

This reduces storage requirements while retaining useful historical information.

## 18. NewSQL

NewSQL refers broadly to relational database systems designed to retain SQL and strong transactional semantics while supporting distributed and horizontally scalable architectures.

The idea combines important characteristics of traditional relational systems with modern distributed infrastructure.

NewSQL systems may provide:

* SQL
* Relational data models
* Transactions
* Strong consistency
* Distributed storage
* Horizontal scaling

Distributed transactions are more difficult because a single logical operation may involve data stored on multiple machines.

This can require replication, consensus, transaction coordination, conflict handling, and distributed recovery.

## 19. CAP Theorem

CAP refers to:

* Consistency
* Availability
* Partition tolerance

CAP is specifically concerned with distributed systems and what happens during network partitions.

A partition occurs when distributed nodes cannot reliably communicate.

During a partition, a system must make trade-offs between consistency and availability under the formal CAP model.

CAP consistency should not be confused directly with the consistency component of ACID.

These are related concepts, but they address different aspects of database behavior.

## 20. Eventual Consistency

Eventual consistency allows replicas to temporarily contain different values.

For example:

A primary node may contain value `110` while replicas still contain `100`.

After replication catches up, the replicas may all contain `110`.

This can be acceptable for workloads such as some social-media counters, recommendation data, or monitoring systems.

It may be inappropriate for operations where immediate consistency is essential, such as some financial transactions.

## 21. Consistency Models

Database consistency can be more nuanced than simply strong or weak.

Important concepts include:

* Strong consistency
* Eventual consistency
* Linearizability
* Sequential consistency
* Causal consistency
* Read-your-writes consistency
* Monotonic reads

Read-your-writes consistency is particularly useful for user-facing applications. If a user changes something, they should not unexpectedly see an older value immediately afterward.

## 22. Replication

Replication means maintaining multiple copies of data.

Replication can provide:

* Fault tolerance
* Higher availability
* Read scaling
* Geographic distribution
* Disaster recovery capabilities

Replication can be synchronous or asynchronous.

Synchronous replication may wait for replica acknowledgement, which can provide stronger guarantees at the cost of additional latency.

Asynchronous replication can reduce write latency but can create replica lag.

Replication and backup are not the same thing.

Replication is primarily about maintaining additional copies for availability and continuity.

Backups provide historical recovery points.

## 23. Sharding

Sharding distributes data across multiple machines or partitions.

For example:

* Shard 1 stores one range of users.
* Shard 2 stores another range.
* Shard 3 stores another range.

Sharding can increase storage and processing capacity.

Common partitioning strategies include:

* Range partitioning
* Hash partitioning
* Directory-based partitioning
* Geographic partitioning

Partition-key design is critical.

A poor key can produce hot partitions, where one partition receives much more traffic than others.

## 24. Horizontal and Vertical Scaling

Vertical scaling means adding resources to an existing machine:

* CPU
* RAM
* Faster storage

Horizontal scaling means adding more machines.

Database scaling can involve:

* Storage capacity
* Read throughput
* Write throughput
* Network capacity
* Memory
* Concurrent connections
* Query complexity
* Transaction rate
* Geographic distribution

No single scaling strategy works for every workload.

## 25. OLTP

OLTP stands for Online Transaction Processing.

OLTP systems process many relatively small transactions.

Examples include:

* Banking
* Payments
* Order processing
* Inventory
* Customer accounts

Typical OLTP characteristics include:

* Frequent reads
* Frequent writes
* Low latency
* Concurrent users
* Transactional correctness

Relational databases have traditionally been strong in OLTP workloads.

## 26. OLAP

OLAP stands for Online Analytical Processing.

OLAP focuses on analytical queries over large amounts of data.

Examples include:

* Revenue by region
* Customer segmentation
* Monthly growth
* Average order value
* Sales analysis

Analytical workloads may scan millions or billions of records.

Column-oriented storage is often useful because analytical queries may only need a few columns from a large number of records.

## 27. Row-Oriented and Column-Oriented Storage

Row-oriented storage keeps the fields of a record together.

This can be useful when an application frequently retrieves complete records.

Column-oriented storage groups values by column.

This can be very effective for analytical queries that scan many rows but only need a few columns.

The physical storage organization is separate from the logical database model.

## 28. Storage Engines

A database's logical model does not describe how data is physically stored.

Database systems can use structures such as:

* B-trees
* B+ trees
* Hash tables
* LSM trees
* SSTables
* Memtables
* Bloom filters
* Write-ahead logs

B-tree-based structures are common in relational systems.

LSM-tree-style architectures are common in systems designed around heavy writes and distributed storage.

## 29. Write-Ahead Logging

Write-ahead logging, or WAL, records changes in a log before the corresponding data pages are considered durably updated.

The log can then help the database recover from crashes.

WAL is an important mechanism for durability and crash recovery in many database systems.

## 30. LSM Trees

LSM-tree architectures are commonly associated with write-heavy workloads.

A simplified process is:

* Incoming writes
* Memtable
* SSTables
* Background compaction

LSM-based systems can provide efficient write behavior but may introduce:

* Write amplification
* Read amplification
* Compaction overhead
* Additional temporary storage requirements

This demonstrates why physical storage architecture matters as much as the logical database model when evaluating performance.

## 31. Concurrency

Multiple users can access the same database at the same time.

Database systems therefore require concurrency-control mechanisms.

Two broad approaches are:

### Pessimistic concurrency

The system assumes conflicts may happen and uses locking or similar mechanisms.

### Optimistic concurrency

The system assumes conflicts are less common and checks whether a conflict occurred before committing.

Optimistic concurrency can use version numbers.

For example:

* Read version 10
* Make changes
* Update only if version is still 10

If another transaction changed the record to version 11, the update can fail and be retried.

## 32. Deadlocks

A deadlock occurs when transactions wait for one another in a cycle.

For example:

Transaction A holds resource 1 and waits for resource 2.

Transaction B holds resource 2 and waits for resource 1.

Neither can continue.

Database systems can detect deadlocks and abort one transaction.

Applications may need to retry safe transactions after a deadlock.

## 33. Latency

Latency is the time required to complete an operation.

Useful latency measurements include:

* p50
* p90
* p95
* p99
* p99.9

The p50 is the median.

The p99 represents the point below which 99% of requests complete.

Tail latency is important in distributed systems because averages can hide a small but significant group of very slow operations.

Latency can be caused by:

* Network communication
* Disk I/O
* Cache misses
* Lock contention
* Query execution
* Replication
* Distributed coordination
* CPU contention
* Memory pressure
* Compaction

## 34. Throughput

Throughput measures how much work a database can process during a period.

Examples include:

* Reads per second
* Writes per second
* Transactions per second
* Events per second

Latency and throughput are different properties.

A system can process a high volume of operations but still have high individual request latency.

## 35. Availability

Availability describes whether a service can continue responding to requests.

High availability commonly involves:

* Replication
* Failover
* Redundancy
* Health checks
* Monitoring
* Automated recovery

Availability requirements are often expressed using percentages such as 99%, 99.9%, 99.99%, or 99.999%.

## 36. Durability

Durability concerns whether committed data survives failures.

Potential failures include:

* Process crashes
* Machine failures
* Disk failures
* Network failures
* Power failures
* Data-center failures

Mechanisms that can contribute to durability include:

* Write-ahead logs
* Replicated storage
* Synchronous replication
* Backups
* Snapshots
* Point-in-time recovery
* Geographic copies

## 37. Backup and Recovery

Common backup approaches include:

* Full backups
* Incremental backups
* Differential backups
* Snapshots
* Continuous archiving
* Point-in-time recovery

Two important recovery concepts are:

### RPO

Recovery Point Objective describes how much data loss is acceptable.

### RTO

Recovery Time Objective describes how quickly the service must be restored.

Replication does not replace backup because replication can also reproduce corrupted or incorrectly modified data.

## 38. Query Optimization

A database does not necessarily execute a query exactly in the order in which it is written.

A query engine may:

* Parse the query
* Transform it
* Estimate costs
* Select indexes
* Reorder joins
* Choose join algorithms
* Select access paths
* Produce an execution plan

Common join algorithms include:

* Nested loop join
* Hash join
* Merge join

Common access methods include:

* Sequential scan
* Index scan
* Index-only scan

Database statistics help the optimizer estimate the cost of different strategies.

## 39. Selectivity

Selectivity describes how effectively a condition narrows a dataset.

A condition such as:

`customer_id = 101`

may be highly selective if it identifies one record.

A condition such as:

`country = 'India'`

may be much less selective if a large percentage of the database contains Indian customers.

Selectivity can influence whether an index is useful.

## 40. Distributed Consensus

Distributed database systems may require nodes to agree on important decisions.

Consensus algorithms such as Raft and Paxos are associated with distributed agreement.

Consensus can support:

* Leader election
* Replicated state
* Cluster coordination

Consensus is difficult because machines can fail and networks can delay or lose messages.

This is one reason distributed database systems are substantially more complex than simply storing copies of data on multiple servers.

## 41. Quorum

Some distributed databases use quorum-based approaches.

If data is replicated across three nodes:

`N = 3`

A write may require two acknowledgements:

`W = 2`

A read may require two responses:

`R = 2`

Since:

`W + R > N`

the read and write sets overlap.

The exact behavior depends on the database and its consistency configuration.

## 42. Hot Partitions and Hot Keys

A hot partition occurs when too much traffic is concentrated on one partition.

A hot key is a particular key that receives unusually high traffic.

For example, if millions of users repeatedly request one cache key, that key can become a bottleneck even though key-value databases are extremely fast for normal direct lookups.

Partitioning and key design therefore need to consider traffic distribution, not only data distribution.

## 43. Connection Management

Applications communicate with databases through connections.

Creating a new connection for every request can be expensive.

Connection pools maintain reusable database connections.

Too few connections can limit throughput.

Too many connections can overload the database.

Connection management is therefore part of database performance and capacity planning.

## 44. Database Observability

Important database metrics include:

* Query latency
* Query throughput
* CPU usage
* Memory usage
* Disk usage
* Cache hit ratio
* Connection count
* Lock waits
* Deadlocks
* Replication lag
* Transaction rate
* Storage growth
* Compaction activity
* Error rate

These measurements help identify whether a problem originates from the application, database queries, configuration, infrastructure, or distributed coordination.

## 45. Schema-on-Write and Schema-on-Read

Schema-on-write means data is expected to conform to a defined schema during storage.

Traditional relational databases strongly emphasize this approach.

Schema-on-read allows data to be stored with more flexibility and interpreted when it is read.

Schema-on-write provides stronger structure and predictability.

Schema-on-read provides greater flexibility.

Neither is universally superior.

## 46. Data Integrity

Data integrity means maintaining correct and valid data.

Important forms include:

* Entity integrity
* Referential integrity
* Domain integrity

Primary keys help with entity integrity.

Foreign keys help with referential integrity.

Data types, checks, and constraints help maintain domain integrity.

## 47. Polyglot Persistence

Polyglot persistence means using multiple storage technologies for different workloads within one larger system.

A system could use:

* A relational database for transactions
* A key-value database for caching
* A document database for flexible product information
* A graph database for relationship analysis
* A time-series database for infrastructure metrics
* A column-family database for large distributed event data

This can be effective because different workloads have different requirements.

The trade-off is increased operational complexity.

Multiple databases mean multiple backup mechanisms, monitoring systems, security models, client libraries, deployment processes, and failure modes.

## 48. Cache vs Database

A cache is primarily used to make repeated access faster.

A database is generally responsible for durable persistence.

A typical architecture can use:

`Application -> Cache -> Database`

A cache hit returns data directly.

A cache miss retrieves data from the database and may populate the cache.

Caching introduces its own problems:

* Stale data
* Cache invalidation
* Expiration
* Cache stampedes
* Memory limitations
* Consistency issues

A cache should not automatically be treated as a replacement for durable storage.

## 49. Data Lifecycle

Data can move through stages such as:

* Ingestion
* Active use
* Historical storage
* Archive
* Deletion

Data lifecycle decisions affect:

* Storage cost
* Performance
* Retention
* Recovery
* Compliance
* Availability

A system may use different storage systems at different stages.

## 50. Event Sourcing

Event sourcing stores changes as events rather than storing only the current state.

For example, instead of storing only:

`balance = 5000`

the system could store:

* Account created
* Money deposited
* Money deposited
* Money withdrawn

The current state can be reconstructed from those events.

Event sourcing can provide a detailed history and audit trail, but it also introduces additional complexity around event schemas, replay, projections, and read models.

Event sourcing is an architectural pattern rather than a database type.

## 51. Microservices and Databases

In a microservice architecture, individual services may own their own data.

For example:

* Order Service -> Order database
* Payment Service -> Payment database
* Catalog Service -> Catalog database

This can improve service independence.

It also means a business operation may cross multiple databases.

A transaction involving orders, payments, and inventory is no longer necessarily a single local ACID transaction.

Patterns such as Saga, Outbox, and event-driven processing can be used to manage these distributed workflows.

## 52. Outbox Pattern

The outbox pattern is useful when an application needs to update database state and publish an event reliably.

The business change and an outbox record can be written within the same local transaction.

A separate process can then publish the outbox event.

This reduces the risk of updating the database successfully while failing to publish the corresponding event.

## 53. Saga Pattern

A saga represents a business process composed of multiple local transactions.

For example:

* Create order
* Process payment
* Reserve inventory
* Arrange shipment

If a later step fails, the system can perform compensating actions.

For example, if payment succeeds but inventory reservation fails, the payment may need to be refunded.

A saga is different from a single distributed ACID transaction.

## 54. Database Security

Database security includes:

* Authentication
* Authorization
* Encryption
* Auditing
* Network controls
* Secrets management
* Access policies
* Backup protection
* Logging

Authentication determines who the user is.

Authorization determines what that user is allowed to do.

The principle of least privilege means database accounts should receive only the permissions required for their responsibilities.

## 55. Database Migrations

A migration changes database structure in a controlled way.

Examples include:

* Adding a column
* Creating an index
* Creating a table
* Changing a constraint
* Renaming a field

Large migrations can cause:

* Locking
* Downtime
* Replication lag
* Application incompatibility
* Data loss

Schema changes therefore need to be treated as part of software evolution.

## 56. Schema Evolution

Data structures change as applications evolve.

A database may need to support older and newer versions of records during a migration.

This is particularly important in document databases where old documents may remain in storage while new documents use a newer structure.

Schema evolution is therefore both a database and application design problem.

## 57. Database Selection

Database selection should begin with workload requirements rather than popularity.

Important questions include:

* Are complex joins required?
* Are strong transactions required?
* Is the data naturally represented as documents?
* Is access primarily by key?
* Is write throughput extremely high?
* Are graph relationships central?
* Is time the dominant dimension?
* Are queries predictable?
* Are queries highly ad-hoc?
* Is horizontal scaling required?
* What consistency guarantees are required?
* What latency is acceptable?
* What happens during network partitions?
* How much operational complexity is acceptable?

## 58. Database Type by Workload

### Relational

Best aligned with:

* Complex transactions
* Joins
* Strong integrity
* Structured business data
* Traditional OLTP

### Document

Best aligned with:

* Nested records
* Flexible attributes
* Application objects
* Content and catalog data

### Key-Value

Best aligned with:

* Direct key lookup
* Caching
* Sessions
* Counters
* Temporary state

### Column-Family

Best aligned with:

* Large distributed workloads
* High write throughput
* Predictable access patterns
* Large event datasets

### Graph

Best aligned with:

* Relationship traversal
* Fraud detection
* Recommendations
* Social networks
* Knowledge graphs

### Time-Series

Best aligned with:

* Timestamped measurements
* Monitoring
* IoT
* Metrics
* Temporal aggregation

### NewSQL

Best aligned with:

* Relational data
* SQL
* Transactions
* Distributed storage
* Horizontally scalable transactional workloads

## 59. Relational vs Document

Relational databases emphasize tables, schemas, joins, constraints, and transactional operations.

Document databases emphasize documents, nested structures, flexible schemas, and document-oriented access.

Relational databases are often a better fit when relationships and transactional integrity are central.

Document databases are often attractive when application records are naturally self-contained and have flexible structures.

## 60. Relational vs Key-Value

A key-value database is optimized around direct lookup.

A relational database is designed for richer querying and relationships.

A request such as:

`GET user:101`

is naturally suited to a key-value model.

A query involving customers, orders, products, grouping, filtering, and aggregation is naturally suited to a relational model.

## 61. Relational vs Graph

Relational databases can represent graphs using tables and foreign keys.

Graph databases make relationships a primary part of the model.

The important question is not whether a relational database can represent relationships. It can.

The question is whether relationship traversal is central enough to the workload that a graph-oriented model provides a better fit.

## 62. Document vs Key-Value

A document database stores structured documents that can usually be queried by fields inside the document.

A basic key-value database is primarily focused on retrieving a value from a known key.

Therefore, document systems generally provide more structure and query capability than a simple key-value model.

## 63. Column-Family vs Relational

Relational systems are generally designed for flexible SQL queries and relationships.

Column-family systems are commonly designed around known query patterns and partition layouts.

Relational modeling often starts from entities and relationships.

Wide-column design often starts from the access patterns the application must serve.

## 64. Time-Series vs Relational

A relational database can store timestamps and measurements.

A time-series database is specialized for workloads in which timestamps dominate the access pattern.

Specialized features can include retention, compression, downsampling, temporal aggregation, and high ingestion performance.

The presence of a timestamp alone does not mean that a time-series database is required.

## 65. Common Misconceptions

Several common assumptions are incorrect.

"NoSQL means no SQL."

NoSQL is a broad family of non-relational database systems and data models.

"NoSQL is always faster."

Performance depends on workload, access patterns, implementation, hardware, indexes, and distribution.

"Relational databases cannot scale."

Relational databases can scale vertically and can also scale horizontally through replication, partitioning, sharding, and distributed architectures.

"More indexes always improve performance."

Indexes can improve reads while increasing write overhead and storage requirements.

"Document databases have no schema."

Flexible schemas still require data discipline and application-level validation.

"Graph databases are only for social networks."

Graphs are useful whenever relationships and traversal are central to the problem.

"Time-series databases are required for every timestamped dataset."

Relational databases can handle many time-series workloads effectively.

"Replication is the same as backup."

Replication and backup solve different problems.

"CAP means choose any two properties at all times."

CAP concerns distributed systems during network partitions.

## 66. Core Comparison

| Database Type | Main Model               | Strong Area                           | Typical Workload                        |
| ------------- | ------------------------ | ------------------------------------- | --------------------------------------- |
| Relational    | Tables and relations     | Transactions, joins, integrity        | OLTP and business systems               |
| Document      | Documents                | Flexible nested records               | Catalogs, content, application data     |
| Key-Value     | Key and value            | Direct lookup                         | Caching, sessions, counters             |
| Column-Family | Wide rows                | Distributed high-throughput workloads | Large event and activity datasets       |
| Graph         | Nodes and relationships  | Relationship traversal                | Fraud, recommendations, social networks |
| Time-Series   | Timestamped measurements | Temporal ingestion and analysis       | Metrics, IoT, monitoring                |
| NewSQL        | Distributed relational   | SQL, transactions, horizontal scaling | Distributed OLTP                        |

## 67. The Main Principle

Database type should be understood through both the data model and the workload.

The most important questions are not simply:

"Which database is most popular?"

or:

"Which database is fastest?"

The meaningful questions are:

* How is the data naturally structured?
* How is the data accessed?
* What relationships exist?
* What transactions are required?
* What consistency guarantees are required?
* How much data is stored?
* How quickly does data arrive?
* What read and write throughput is required?
* What latency is acceptable?
* How will the system scale?
* What happens when machines or networks fail?
* How much operational complexity can be supported?

A relational database, document database, key-value database, column-family database, graph database, time-series database, or NewSQL system becomes appropriate when its underlying model and architecture match the requirements of the workload.

The important distinction between database types is therefore not simply the syntax used to access them. It is the way each model represents information, relationships, queries, transactions, consistency, distribution, and storage.

