# Distributed Transactions: Two-Phase Commit and Coordination

## 1. Distributed Transaction Fundamentals

A distributed transaction is a logical unit of work involving multiple independent resource managers, databases, or services.

Each participant controls its own resources and maintains its own local transaction state. A coordinator manages the global transaction and determines whether all participants can commit.

The central correctness requirement is atomicity:

- Every participant must commit the transaction.
- Every participant must abort the transaction.
- A partially completed transaction must not be treated as successfully committed.

A distributed transaction differs from an ordinary database transaction because its operations cross independent transactional boundaries.

### 1.1 Example: Distributed banking transfer

Consider a transfer of 1,000 monetary units from BANK_A to BANK_B.

| Participant | Operation | Initial balance |
|---|---|---:|
| BANK_A | Debit 1,000 | 10,000 |
| BANK_B | Credit 1,000 | 5,000 |

Expected result:

| Participant | Final balance |
|---|---:|
| BANK_A | 9,000 |
| BANK_B | 6,000 |

If BANK_A commits its debit but BANK_B cannot complete its credit, the system cannot report a successful atomic transfer.

Two-phase commit coordinates the participants so that they agree on one global outcome.

## 2. Two-Phase Commit Architecture

Two-phase commit, commonly abbreviated as 2PC, is a distributed atomic commitment protocol.

It contains two principal roles:

- Coordinator: manages the transaction and collects participant votes.
- Participants: independently manage their local transactional resources.

### 2.1 Architecture

    Application
        |
        v
    Transaction Coordinator
        |
        +-------------------+
        |                   |
        v                   v
    Participant A      Participant B
        |                   |
        v                   v
    Resource A          Resource B

The coordinator does not directly replace the local transaction manager of each participant.

Each participant remains responsible for preparing and applying its own resource changes.

### 2.2 Transaction lifecycle

    ACTIVE
       |
       v
    PREPARING
       |
       +-----------------------------+
       |                             |
       v                             v
    All YES                       Any NO
       |                             |
       v                             v
    PREPARED                     ABORTING
       |                             |
       v                             v
    COMMITTING                    ABORTED
       |
       v
    COMMITTED

A participant communication failure can leave the transaction in `IN_DOUBT`.

This state indicates that the coordinator has not completed delivery or acknowledgement of the global decision.

## 3. Phase 1: Prepare and Voting

The prepare phase establishes whether all participants can commit.

### 3.1 Coordinator responsibilities

The coordinator:

1. Creates a transaction identifier.
2. Registers participating resource managers.
3. Records the proposed operations.
4. Sends PREPARE requests.
5. Collects participant votes.
6. Determines whether unanimous approval is available.

### 3.2 Participant responsibilities

Each participant evaluates its local operation.

A participant voting YES must:

- Validate the requested operation.
- Check resource availability and constraints.
- Acquire or retain the necessary locks.
- Record sufficient recovery information.
- Persist its prepared state.
- Promise not to independently commit or abort before learning the global outcome.

A YES vote is not the same as a final commit.

A participant voting NO indicates that it cannot guarantee successful commitment.

### 3.3 Voting outcomes

| Vote | Meaning | Global implication |
|---|---|---|
| YES | Participant successfully prepared | Continue collecting votes |
| NO | Participant cannot prepare | Global abort |
| Timeout | Participant response unavailable | Cannot establish unanimous YES |

The coordinator may choose COMMIT only after receiving YES from every enlisted participant.

A missing vote must never be interpreted as YES.

## 4. Phase 2: Global Decision and Execution

The second phase distributes the coordinator's final decision.

There are two possible decisions.

### 4.1 COMMIT

When all participants vote YES:

1. The coordinator records the global COMMIT decision durably.
2. The coordinator sends COMMIT messages.
3. Each participant commits its prepared local transaction.
4. Participants acknowledge completion.
5. The coordinator records the global transaction as COMMITTED.

### 4.2 ABORT

When any participant votes NO:

1. The coordinator records the global ABORT decision.
2. The coordinator sends ABORT messages.
3. Participants release prepared resources.
4. Participants acknowledge the abort.
5. The coordinator records the transaction as ABORTED.

### 4.3 Decision durability

The ordering of operations is critical.

    Participant preparation
             |
             v
    Unanimous YES
             |
             v
    Persist global decision
             |
             v
    Distribute phase-2 messages
             |
             v
    Collect acknowledgements
             |
             v
    Record completion

The coordinator must persist its global decision before distributing the final decision.

If a coordinator crashes after sending COMMIT but before recording the decision, recovery may become ambiguous.

A durable transaction log prevents this specific failure when correctly implemented.

## 5. Transaction State Management

A distributed transaction requires explicit state management.

| State | Meaning |
|---|---|
| ACTIVE | Transaction is being constructed |
| PREPARING | Prepare requests are being processed |
| PREPARED | All participants voted YES |
| COMMITTING | Global COMMIT has been recorded |
| COMMITTED | Every participant acknowledged COMMIT |
| ABORTING | Global ABORT has been recorded |
| ABORTED | Every participant acknowledged ABORT |
| IN_DOUBT | Decision delivery or recovery is incomplete |

Terminal states must be protected from invalid transitions.

For example:

- COMMITTED cannot become ABORTED.
- ABORTED cannot become COMMITTED.
- COMMIT cannot be reversed to ABORT.
- A participant cannot commit without successfully preparing.

The Python, JavaScript, C++17 and Java 17 implementations use explicit transition validation.

The PostgreSQL implementation reinforces decision consistency through constraints and triggers.

## 6. Coordinator and Participant Responsibilities

### 6.1 Coordinator

The coordinator owns global coordination.

Its responsibilities include:

- Creating global transaction identifiers.
- Enlisting participants.
- Sending prepare requests.
- Collecting votes.
- Recording the global decision.
- Distributing phase-2 instructions.
- Tracking acknowledgements.
- Detecting incomplete transactions.
- Initiating recovery.

The coordinator does not independently determine that an unavailable participant has committed.

### 6.2 Participant

A participant owns its local resource state.

Its responsibilities include:

- Validating local operations.
- Managing local transactional resources.
- Acquiring necessary locks.
- Recording prepared state.
- Preserving recovery information.
- Applying COMMIT or ABORT.
- Responding to repeated messages safely.

The participant must preserve sufficient information to recover after a process failure.

### 6.3 Distinction between voting and acknowledgement

Voting and acknowledgement represent different protocol events.

| Mechanism | Stage | Meaning |
|---|---|---|
| YES vote | Phase 1 | Participant promises it can commit |
| NO vote | Phase 1 | Participant cannot prepare |
| COMMIT acknowledgement | Phase 2 | Participant completed commitment |
| ABORT acknowledgement | Phase 2 | Participant completed abortion |

A participant that voted YES has not necessarily committed.

This distinction is essential when diagnosing partially completed distributed transactions.

## 7. Durable Logging and Recovery

Distributed transaction coordination requires persistent information.

Important events include:

- BEGIN
- ENLIST
- PREPARE_REQUESTED
- VOTE
- ALL_PREPARED
- GLOBAL_DECISION
- DELIVERY_ATTEMPT
- DELIVERY_ACKNOWLEDGED
- DELIVERY_FAILED
- COMPLETED
- RECOVERY_REQUESTED

### 7.1 Write-ahead decision logging

The coordinator must persist its final decision before sending phase-2 messages.

This establishes a recoverable source of truth.

For example:

    GLOBAL_DECISION: COMMIT
             |
             v
    BANK_A receives COMMIT
             |
             v
    BANK_B becomes unavailable
             |
             v
    Coordinator records IN_DOUBT
             |
             v
    BANK_B becomes available
             |
             v
    Coordinator retries COMMIT
             |
             v
    Transaction becomes COMMITTED

The coordinator must retry the recorded decision rather than create a contradictory decision.

### 7.2 Idempotency

An operation is idempotent when repeating it does not produce an additional effect after its first successful application.

Consider a participant receiving the same COMMIT message twice.

The participant must not debit an account twice.

Each participant therefore associates transaction identifiers with durable processing states.

A repeated COMMIT for an already committed transaction returns the existing result without applying the operation again.

A repeated ABORT for an already aborted transaction behaves similarly.

### 7.3 Recovery without a global decision

An important distinction exists between two recovery situations.

**Situation A: Decision already persisted**

The coordinator knows whether the transaction must commit or abort.

Recovery can safely retry delivery of that decision.

**Situation B: No decision persisted**

The coordinator cannot automatically assume that commitment is valid.

Participants may already be prepared and waiting.

Recovery must inspect the coordinator's durable log and participant records, reconcile protocol state, and follow the protocol's recovery rules.

A system must not invent a COMMIT decision merely because all participants appear temporarily unavailable.

## 8. The Blocking Problem in Two-Phase Commit

Classical 2PC is a blocking protocol.

A participant that has voted YES may need to retain locks and other resources until it learns the final global decision.

Consider the following failure:

1. BANK_A votes YES.
2. BANK_B votes YES.
3. Both participants enter PREPARED.
4. The coordinator fails before distributing the final decision.
5. Both participants wait for recovery information.

Neither participant can safely assume that the other participant has committed.

This creates a blocking situation.

### 8.1 Consequences

| Resource | Potential effect |
|---|---|
| Database locks | Remain held |
| Connections | May remain occupied |
| Memory | Prepared transaction state retained |
| Throughput | Reduced |
| Waiting transactions | May accumulate |
| Recovery operations | Become more expensive |

The duration of this condition depends on failure detection, coordinator recovery, network availability, and participant recovery behavior.

### 8.2 Important limitation

Timeouts do not automatically solve the fundamental blocking problem.

A timeout can indicate that communication has failed, but it cannot establish whether the coordinator recorded COMMIT or ABORT.

A participant must not unilaterally abort a prepared transaction merely because a response is delayed.

## 9. Python Implementation

The Python implementation models transaction coordination through classes, dictionaries, enumerations, dataclasses, and exceptions.

### 9.1 Main components

| Component | Responsibility |
|---|---|
| `Transaction` | Stores global transaction state |
| `Participant` | Manages local resource operations |
| `Coordinator` | Executes the 2PC protocol |
| `DurableLog` | Persists transaction events |
| `Decision` | Represents COMMIT or ABORT |
| `Vote` | Represents YES or NO |

### 9.2 Important implementation mechanisms

**Dataclasses**

The transaction model uses a dataclass to group identifiers, descriptions, votes, timestamps, and transaction state.

**Enumerations**

Enumerations prevent arbitrary transaction-state strings from spreading throughout the implementation.

**Participant reservation**

The prepare method records a pending operation without immediately modifying the committed balance.

**Durable logging**

The JSONL journal records transaction events and uses file flushing and `fsync` to request persistence.

**Recovery**

The coordinator uses the recorded global decision to retry incomplete phase-2 delivery.

**Assertions**

The demonstration checks:

- Successful transfer.
- Insufficient funds.
- Participant unavailability.
- Recovery.
- Repeated recovery.
- Final account balances.

The implementation is an in-process simulation. Its local file journal is not a replicated consensus log and does not provide production-grade coordinator failover.

## 10. JavaScript Implementation

The JavaScript implementation emphasizes asynchronous coordination and event-driven processing.

### 10.1 Main components

| Component | Responsibility |
|---|---|
| `EventJournal` | Records asynchronous transaction events |
| `Participant` | Simulates independent resource managers |
| `Transaction` | Maintains transaction state |
| `Coordinator` | Coordinates participants |
| `EventEmitter` | Publishes lifecycle events |

### 10.2 Asynchronous prepare phase

The coordinator uses `Promise.all()` to collect participant votes concurrently.

This differs from sequential communication because independent participants can process prepare requests at the same time.

The coordinator still waits for every result before making its global decision.

### 10.3 Timeout management

The implementation uses `Promise.race()` to enforce a participant response deadline.

A timeout is treated as an unsuccessful vote during preparation.

During phase 2, a timeout produces an incomplete delivery result and preserves the previously recorded global decision.

The timeout does not imply that the participant operation itself has stopped. A real implementation requires cancellation, request identifiers, durable deduplication, and reconciliation because a remote operation may complete after the caller times out.

### 10.4 Event-driven monitoring

The journal publishes events through Node.js `EventEmitter`.

Applications can observe:

- Transaction initiation.
- Preparation completion.
- Global decisions.
- In-doubt transactions.
- Final completion.

This separates transaction processing from monitoring and event consumers.

The journal serializes writes through a promise queue to preserve event ordering.

## 11. C++17 Implementation

The C++17 implementation provides a repository-independent transaction governance engine using explicit domain structures and standard-library containers.

### 11.1 Design components

| Component | Responsibility |
|---|---|
| `Transaction` | Global transaction data |
| `Participant` | Local resource state |
| `Coordinator` | Protocol execution |
| `DecisionLog` | Append-only decision records |
| `Operation` | Debit and credit amounts |
| `TxState` | Global transaction lifecycle |
| `ParticipantState` | Participant lifecycle |

### 11.2 Data structures

The implementation uses:

- `std::map` for ordered participant and transaction registries.
- `std::set` for allowed state transitions.
- `std::vector` for participant membership and recovery failures.
- `std::optional` for decisions that have not yet been recorded.
- `std::int64_t` for integer monetary values.

Integer monetary values avoid floating-point precision problems.

The implementation also validates potential balance overflow.

### 11.3 State-machine validation

The coordinator uses a transition table to reject invalid state changes.

This makes the permitted protocol lifecycle explicit.

An attempt to change a COMMITTED transaction into ABORTED produces an exception.

### 11.4 Performance characteristics

Let:

- \(n\) represent the number of participants.
- \(m\) represent the number of transaction events.

In the in-memory simulation:

| Operation | Approximate complexity |
|---|---|
| Participant lookup | \(O(\log n)\) |
| Transaction lookup | \(O(\log m)\) |
| Prepare voting | \(O(n \log n)\) |
| Decision delivery | \(O(n \log n)\) |
| Transaction report | \(O(n \log n)\) |

The file journal introduces additional I/O overhead.

A production system would normally use a durable transactional storage engine and network-based participant communication.

## 12. Java 17 Implementation

The Java implementation models an enterprise-oriented transaction coordination service.

Its design emphasizes domain separation, explicit policies, immutable records, service boundaries, and synchronized participant operations.

### 12.1 Domain model

| Type | Purpose |
|---|---|
| `TransactionId` | Immutable transaction identifier |
| `Operation` | Validated debit and credit amounts |
| `Transaction` | Global transaction aggregate |
| `TransactionParticipant` | Participant contract |
| `AccountParticipant` | Account resource manager |
| `StateMachine` | Transition validation |
| `DurableJournal` | Persistent event recording |
| `Coordinator` | Transaction orchestration |
| `TransactionReport` | Operational reporting |

### 12.2 Interfaces and domain separation

`TransactionParticipant` defines the participant contract.

The coordinator depends on the interface rather than the concrete account implementation.

This supports alternative resource managers without changing the core coordination logic.

### 12.3 Immutable records

Java records provide compact immutable representations for:

- Transaction identifiers.
- Operations.
- Journal events.

The transaction itself remains mutable because its state evolves during protocol execution.

### 12.4 Synchronization

The account participant synchronizes its critical methods.

This prevents concurrent operations from modifying the same participant's in-memory state without mutual exclusion.

The journal also synchronizes writes.

These mechanisms protect the local simulation but do not provide distributed locking or cross-process coordination.

### 12.5 Enterprise considerations

A production implementation would separate:

- Transaction application services.
- Coordinator persistence.
- Participant adapters.
- Remote communication.
- Retry scheduling.
- Observability.
- Authentication and authorization.
- Recovery administration.

The Java program combines these mechanisms into one executable learning model while preserving their domain boundaries.

## 13. PostgreSQL Implementation

The PostgreSQL implementation models the relational structure of a distributed transaction coordination system.

It separates transaction records, participant records, resource accounts, decisions, and event history.

### 13.1 Relational architecture

    PARTICIPANTS
         |
         v
    RESOURCE_ACCOUNTS

    DISTRIBUTED_TRANSACTIONS
         |
         v
    TRANSACTION_PARTICIPANTS
         |
         +----------------------+
         |                      |
         v                      v
    PARTICIPANTS          TRANSACTION_EVENTS

The main relationships are:

| Table | Purpose |
|---|---|
| `participants` | Registered resource managers |
| `resource_accounts` | Example participant-owned resources |
| `distributed_transactions` | Global transaction records |
| `transaction_participants` | Participant membership and votes |
| `transaction_events` | Coordinator event journal |

### 13.2 Constraints

The schema uses:

- Primary keys for entity identification.
- Foreign keys for referential integrity.
- Unique constraints for participant and account identifiers.
- Check constraints for monetary values and state consistency.
- Enum types for transaction and participant states.
- Triggers to prevent decision reversal.

The database rejects negative debit and credit amounts.

A committed transaction must have a COMMIT decision and a completion timestamp.

An aborted transaction must have an ABORT decision and a completion timestamp.

### 13.3 Functions and procedures

| Database object | Purpose |
|---|---|
| `begin_transaction()` | Creates a global transaction |
| `enlist_participant()` | Registers a participant operation |
| `start_prepare()` | Initiates phase 1 |
| `record_vote()` | Records YES or NO |
| `all_participants_prepared()` | Checks unanimous preparation |
| `decide_transaction()` | Persists the global decision |
| `acknowledge_participant()` | Records phase-2 completion |
| `record_delivery_failure()` | Records failed message delivery |
| `complete_transaction()` | Verifies global completion |

### 13.4 Reporting views

**transaction_eligibility**

Determines whether all participants have acknowledged the global decision.

**recovery_queue**

Identifies transactions requiring phase-2 recovery.

**participant_performance**

Aggregates committed transactions, aborted transactions, failures, and delivery attempts.

### 13.5 Database transaction boundaries

The sample workflow uses PostgreSQL transactions to protect modifications to the coordination records.

These local SQL transactions are distinct from distributed 2PC.

The sample does not independently commit remote resource databases.

A real deployment must execute participant operations in their own transactional environments and connect those operations to a durable coordinator.

## 14. Failure Scenarios and Recovery Policies

Distributed transactions must handle failures at different protocol stages.

| Failure scenario | Risk | Required response |
|---|---|---|
| Participant unavailable during prepare | Missing YES vote | Abort |
| Participant votes NO | Unanimous preparation impossible | Abort |
| Coordinator fails before decision | Global outcome unknown | Recover coordinator and participant state |
| Coordinator fails after durable COMMIT | Participants may remain prepared | Retry COMMIT |
| Participant fails during COMMIT delivery | Partial completion | Preserve COMMIT and retry |
| Participant receives duplicate COMMIT | Duplicate resource modification | Idempotent processing |
| Participant fails during ABORT delivery | Prepared resources remain held | Preserve ABORT and retry |
| Journal persistence fails | Decision may not be durable | Do not distribute an unpersisted decision |
| Network timeout | Message outcome uncertain | Reconcile using transaction identity and participant state |

### 14.1 Failure detection versus failure resolution

Failure detection identifies that an expected response has not arrived.

Failure resolution determines what action is safe.

These are different responsibilities.

For example, a timeout during COMMIT delivery does not justify switching to ABORT.

The global decision remains COMMIT.

## 15. Security and Operational Controls

Distributed transaction coordinators and participants exchange sensitive operational instructions.

Important controls include:

### Authentication

Each participant should authenticate the coordinator and reject unauthorized transaction requests.

### Authorization

Only authorized coordinators should initiate transactions or distribute final decisions.

### Transaction identity

Globally unique transaction identifiers should be used to correlate requests, votes, acknowledgements, and recovery events.

### Message integrity

Participant messages should be protected against unauthorized modification and replay.

### Idempotency

Participants should persist transaction identifiers and processing states to prevent duplicate resource modifications.

### Auditability

Transaction events should retain:

- Transaction identifier.
- Participant identifier.
- Event type.
- Timestamp.
- Decision.
- Error information.
- Recovery attempts.

### Secret management

Database passwords, API credentials, certificates, and signing keys should not be stored directly in source code or transaction logs.

### Resource monitoring

Operational monitoring should identify:

- Long-running prepared transactions.
- Transactions in IN_DOUBT.
- Failed participant communications.
- Repeated recovery attempts.
- Unusually high participant lock durations.
- Coordinator journal failures.

## 16. Performance and Scalability

The principal performance cost of classical 2PC comes from coordination, communication, durable logging, and resource retention.

### 16.1 Network communication

The protocol normally requires two coordination phases:

1. Prepare request and vote collection.
2. Final decision distribution and acknowledgement.

The number of participant messages grows linearly with the number of participants.

For \(n\) participants, the coordinator typically handles approximately \(2n\) outbound messages and \(2n\) responses, excluding retries and additional recovery traffic.

### 16.2 Latency

The overall latency depends on the slowest required participant in each coordination phase.

Concurrent participant processing can reduce preparation latency compared with sequential requests.

It does not eliminate network latency or the requirement to wait for all votes.

### 16.3 Lock duration

Prepared participants may retain locks until the global decision is received.

Long coordination delays therefore reduce concurrency and increase contention.

### 16.4 Logging

Transaction logs must preserve ordering and durability.

High-volume systems should consider:

- Group commit.
- Batched event persistence.
- Indexed recovery records.
- Journal retention policies.
- Log replication.
- Recovery checkpoints.

Any optimization must preserve the required durability guarantees.

## 17. Two-Phase Commit and Alternative Coordination Approaches

Two-phase commit is not interchangeable with every distributed workflow mechanism.

| Mechanism | Main purpose | Atomicity model |
|---|---|---|
| Two-phase commit | Coordinate atomic commitment across participants | Distributed atomic commitment |
| Three-phase commit | Introduce an additional protocol phase to reduce certain blocking conditions under its assumptions | Distributed atomic commitment |
| Saga | Coordinate long-running business transactions through local transactions and compensations | Eventual business consistency |
| Outbox pattern | Reliably publish events associated with local database changes | Local atomic persistence plus asynchronous delivery |
| Consensus protocol | Establish agreement among distributed replicas | Replicated agreement |

### 17.1 Two-phase commit versus Saga

A Saga does not normally hold all participants in a prepared state until a global commit decision.

Instead, it executes local transactions and uses compensating operations when a later step fails.

For example:

1. Reserve inventory.
2. Charge a payment method.
3. Schedule delivery.
4. Compensate earlier operations if a subsequent step cannot complete.

A compensation is a new business operation, not necessarily a reversal of the original database transaction.

### 17.2 Two-phase commit versus consensus

2PC coordinates commitment among transaction participants.

Consensus protocols establish agreement among distributed nodes despite specified failure conditions.

They solve different problems, although production transaction managers may use consensus-based replication to make coordinator decisions durable and available.

## 18. Testing and Execution

### 18.1 Python

- Runtime: Python 3.10 or later.
- Dependencies: Python standard library.
- Execution: `python distributed_transactions.py`

The demonstration creates a JSONL event journal.

### 18.2 JavaScript

- Runtime: Node.js 18 or later.
- Dependencies: Node.js standard library.
- Execution: `node distributed_transactions.js`

The demonstration creates an asynchronous event journal.

### 18.3 C++17

- Standard: C++17.
- Dependencies: Standard C++ library.
- Compilation: `g++ -std=c++17 -O2 -Wall -Wextra -pedantic distributed_transactions.cpp -o distributed_transactions`
- Execution: `./distributed_transactions`

On Windows, the executable can be launched as `.\distributed_transactions.exe`.

### 18.4 Java 17

- Runtime: Java 17.
- Dependencies: Java standard library.
- Compilation: `javac --release 17 DistributedTransactionSystem.java`
- Execution: `java DistributedTransactionSystem`

### 18.5 PostgreSQL

- Database: PostgreSQL 17 or later.
- Execution: Run the complete SQL script in a dedicated development database.

The script recreates the `distributed_tx` schema and inserts sample transactions.

The execution account requires permission to create schemas, tables, functions, procedures, triggers, and extensions' built-in UUID functionality through `gen_random_uuid()`.

The script should be executed in an isolated environment because it drops the existing `distributed_tx` schema.

## 19. Implementation Limitations

The five implementations demonstrate the protocol and its engineering requirements. They are not production-ready distributed transaction managers.

| Implementation | Important limitation |
|---|---|
| Python | In-memory participant state; local file journal |
| JavaScript | Asynchronous in-process participants; local event journal |
| C++17 | In-memory resource managers; local append-only file |
| Java 17 | In-memory participant state; local journal |
| PostgreSQL | Relational coordination model without actual remote participant execution |

A production implementation requires additional capabilities:

- Durable participant-side prepared transactions.
- Replicated coordinator decision storage.
- Distributed failure detection.
- Fencing against stale coordinators.
- Authenticated communication.
- Transaction recovery after process and machine failures.
- Persistent idempotency records.
- Lock monitoring and prepared-transaction cleanup.
- Controlled retry and backoff.
- Operational alerting.
- Consistent transaction identifiers across services.

The central engineering distinction remains that preparation, voting, global decision persistence, decision delivery, participant acknowledgement, and final transaction completion are separate protocol events.
