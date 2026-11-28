import java.io.BufferedWriter;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.time.Instant;
import java.util.ArrayList;
import java.util.EnumMap;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import java.util.Set;
import java.util.UUID;

/**
 * Distributed Transactions: Two-Phase Commit and Enterprise Coordination.
 *
 * Domain-oriented Java 17 implementation.
 *
 * Includes:
 * - Immutable transaction identifiers and operation records.
 * - Explicit transaction state transitions.
 * - Participant resource management.
 * - Reviewable voting and coordination policies.
 * - Durable decision logging.
 * - Failure handling and recovery.
 * - Idempotent phase-2 operations.
 * - Enterprise-oriented merge eligibility equivalent:
 *   a transaction can complete only when its global decision is
 *   durable and all participant acknowledgements are received.
 */

public class DistributedTransactionSystem {

    enum TransactionState {
        ACTIVE,
        PREPARING,
        PREPARED,
        COMMITTING,
        COMMITTED,
        ABORTING,
        ABORTED,
        IN_DOUBT
    }

    enum ParticipantState {
        ACTIVE,
        PREPARED,
        COMMITTED,
        ABORTED,
        FAILED
    }

    enum Decision {
        COMMIT,
        ABORT
    }

    enum Vote {
        YES,
        NO
    }

    record TransactionId(String value) {
        TransactionId {
            Objects.requireNonNull(value, "Transaction ID is required");

            if (value.isBlank()) {
                throw new IllegalArgumentException(
                    "Transaction ID cannot be blank"
                );
            }
        }

        static TransactionId create() {
            return new TransactionId(UUID.randomUUID().toString());
        }
    }

    record Operation(long debit, long credit) {
        Operation {
            if (debit < 0 || credit < 0) {
                throw new IllegalArgumentException(
                    "Amounts cannot be negative"
                );
            }
        }
    }

    record JournalEvent(
        long sequence,
        Instant timestamp,
        TransactionId transactionId,
        String event,
        String details
    ) {}

    static class TransactionException extends RuntimeException {
        TransactionException(String message) {
            super(message);
        }

        TransactionException(String message, Throwable cause) {
            super(message, cause);
        }
    }

    static class ParticipantUnavailableException
            extends TransactionException {
        ParticipantUnavailableException(String message) {
            super(message);
        }
    }

    static class InvalidTransitionException
            extends TransactionException {
        InvalidTransitionException(String message) {
            super(message);
        }
    }

    interface TransactionParticipant {
        String name();

        Vote prepare(TransactionId id, Operation operation);

        void commit(TransactionId id);

        void abort(TransactionId id);

        long balance();

        ParticipantState state(TransactionId id);
    }

    static final class StateMachine {
        private static final Map<TransactionState, Set<TransactionState>>
            ALLOWED = new EnumMap<>(TransactionState.class);

        static {
            ALLOWED.put(TransactionState.ACTIVE,
                Set.of(
                    TransactionState.PREPARING,
                    TransactionState.ABORTING
                ));

            ALLOWED.put(TransactionState.PREPARING,
                Set.of(
                    TransactionState.PREPARED,
                    TransactionState.ABORTING
                ));

            ALLOWED.put(TransactionState.PREPARED,
                Set.of(
                    TransactionState.COMMITTING,
                    TransactionState.ABORTING
                ));

            ALLOWED.put(TransactionState.COMMITTING,
                Set.of(
                    TransactionState.COMMITTED,
                    TransactionState.IN_DOUBT
                ));

            ALLOWED.put(TransactionState.ABORTING,
                Set.of(
                    TransactionState.ABORTED,
                    TransactionState.IN_DOUBT
                ));

            ALLOWED.put(TransactionState.IN_DOUBT,
                Set.of(
                    TransactionState.COMMITTED,
                    TransactionState.ABORTED
                ));

            ALLOWED.put(TransactionState.COMMITTED, Set.of());
            ALLOWED.put(TransactionState.ABORTED, Set.of());
        }

        private StateMachine() {}

        static void validate(
            TransactionState current,
            TransactionState next
        ) {
            if (!ALLOWED.get(current).contains(next)) {
                throw new InvalidTransitionException(
                    "Illegal transaction transition: " +
                    current + " -> " + next
                );
            }
        }
    }

    static final class Transaction {
        private final TransactionId id;
        private final String description;
        private final Instant createdAt;
        private final List<String> participantNames;
        private final Map<String, Vote> votes = new HashMap<>();

        private TransactionState state = TransactionState.ACTIVE;
        private Decision decision;

        Transaction(String description, List<String> participants) {
            if (description == null || description.isBlank()) {
                throw new IllegalArgumentException(
                    "Description is required"
                );
            }

            if (participants.isEmpty()) {
                throw new IllegalArgumentException(
                    "At least one participant is required"
                );
            }

            if (new HashSet<>(participants).size() != participants.size()) {
                throw new IllegalArgumentException(
                    "Duplicate participant"
                );
            }

            this.id = TransactionId.create();
            this.description = description;
            this.createdAt = Instant.now();
            this.participantNames = List.copyOf(participants);
        }

        TransactionId id() {
            return id;
        }

        TransactionState state() {
            return state;
        }

        Decision decision() {
            return decision;
        }

        List<String> participantNames() {
            return participantNames;
        }

        Map<String, Vote> votes() {
            return Map.copyOf(votes);
        }

        Instant createdAt() {
            return createdAt;
        }

        void transition(TransactionState next) {
            StateMachine.validate(state, next);
            state = next;
        }

        void recordVote(String participant, Vote vote) {
            if (!participantNames.contains(participant)) {
                throw new TransactionException(
                    "Vote from non-enlisted participant"
                );
            }

            Vote existing = votes.putIfAbsent(participant, vote);

            if (existing != null && existing != vote) {
                throw new TransactionException(
                    "Conflicting participant vote"
                );
            }
        }

        void setDecision(Decision newDecision) {
            if (decision != null && decision != newDecision) {
                throw new InvalidTransitionException(
                    "Global decision cannot be reversed"
                );
            }

            decision = newDecision;
        }
    }

    static final class AccountParticipant
            implements TransactionParticipant {

        private final String name;
        private long balance;
        private boolean available = true;
        private boolean acceptPreparation = true;

        private final Map<TransactionId, ParticipantState> states =
            new HashMap<>();

        private final Map<TransactionId, Operation> pending =
            new HashMap<>();

        AccountParticipant(String name, long initialBalance) {
            if (name == null || name.isBlank() || initialBalance < 0) {
                throw new IllegalArgumentException(
                    "Invalid participant configuration"
                );
            }

            this.name = name;
            this.balance = initialBalance;
        }

        @Override
        public String name() {
            return name;
        }

        void setAvailable(boolean available) {
            this.available = available;
        }

        void setAcceptPreparation(boolean value) {
            this.acceptPreparation = value;
        }

        private void ensureAvailable() {
            if (!available) {
                throw new ParticipantUnavailableException(
                    name + " is unavailable"
                );
            }
        }

        @Override
        public synchronized Vote prepare(
            TransactionId id,
            Operation operation
        ) {
            ensureAvailable();

            ParticipantState existing = states.get(id);

            if (existing == ParticipantState.PREPARED ||
                existing == ParticipantState.COMMITTED) {
                return Vote.YES;
            }

            if (existing == ParticipantState.ABORTED) {
                return Vote.NO;
            }

            if (!acceptPreparation || balance < operation.debit()) {
                states.put(id, ParticipantState.FAILED);
                return Vote.NO;
            }

            pending.put(id, operation);
            states.put(id, ParticipantState.PREPARED);

            return Vote.YES;
        }

        @Override
        public synchronized void commit(TransactionId id) {
            ensureAvailable();

            ParticipantState current = states.get(id);

            if (current == ParticipantState.COMMITTED) {
                return;
            }

            if (current != ParticipantState.PREPARED) {
                throw new InvalidTransitionException(
                    name + " cannot commit from " + current
                );
            }

            Operation operation = pending.get(id);

            if (operation == null) {
                throw new TransactionException(
                    "Prepared operation missing"
                );
            }

            long remaining = balance - operation.debit();

            try {
                balance = Math.addExact(
                    remaining,
                    operation.credit()
                );
            } catch (ArithmeticException exception) {
                throw new TransactionException(
                    "Account balance overflow",
                    exception
                );
            }

            pending.remove(id);
            states.put(id, ParticipantState.COMMITTED);
        }

        @Override
        public synchronized void abort(TransactionId id) {
            ensureAvailable();

            ParticipantState current = states.get(id);

            if (current == ParticipantState.ABORTED) {
                return;
            }

            if (current == ParticipantState.COMMITTED) {
                throw new InvalidTransitionException(
                    "Cannot abort committed participant"
                );
            }

            pending.remove(id);
            states.put(id, ParticipantState.ABORTED);
        }

        @Override
        public synchronized long balance() {
            return balance;
        }

        @Override
        public synchronized ParticipantState state(TransactionId id) {
            return states.getOrDefault(id, ParticipantState.ACTIVE);
        }
    }

    static final class DurableJournal implements AutoCloseable {
        private final Path path;
        private BufferedWriter writer;
        private long sequence;

        DurableJournal(String filename) {
            path = Path.of(filename);

            try {
                writer = Files.newBufferedWriter(
                    path,
                    StandardCharsets.UTF_8,
                    StandardOpenOption.CREATE,
                    StandardOpenOption.APPEND
                );
            } catch (IOException exception) {
                throw new TransactionException(
                    "Cannot initialize transaction journal",
                    exception
                );
            }
        }

        synchronized void append(
            TransactionId id,
            String event,
            String details
        ) {
            try {
                String safeDetails = details
                    .replace("\\", "\\\\")
                    .replace("\n", "\\n")
                    .replace("|", "\\|");

                String record =
                    (++sequence) + "|" +
                    Instant.now() + "|" +
                    id.value() + "|" +
                    event + "|" +
                    safeDetails;

                writer.write(record);
                writer.newLine();
                writer.flush();

            } catch (IOException exception) {
                throw new TransactionException(
                    "Failed to persist transaction event",
                    exception
                );
            }
        }

        List<String> readAll() {
            try {
                if (!Files.exists(path)) {
                    return List.of();
                }

                return Files.readAllLines(path, StandardCharsets.UTF_8);

            } catch (IOException exception) {
                throw new TransactionException(
                    "Unable to read transaction journal",
                    exception
                );
            }
        }

        @Override
        public synchronized void close() {
            try {
                writer.close();
            } catch (IOException exception) {
                throw new TransactionException(
                    "Unable to close transaction journal",
                    exception
                );
            }
        }
    }

    static final class TransactionReport {
        private final Transaction transaction;
        private final Map<String, TransactionParticipant> participants;

        TransactionReport(
            Transaction transaction,
            Map<String, TransactionParticipant> participants
        ) {
            this.transaction = transaction;
            this.participants = participants;
        }

        void print() {
            System.out.println("\nTransaction ID: " +
                transaction.id().value());

            System.out.println("Description: " +
                transaction.description);

            System.out.println("Created: " +
                transaction.createdAt());

            System.out.println("State: " +
                transaction.state());

            System.out.println("Decision: " +
                Optional.ofNullable(transaction.decision())
                    .map(Enum::name)
                    .orElse("NONE"));

            System.out.println("Votes: " + transaction.votes());

            for (String name : transaction.participantNames()) {
                TransactionParticipant participant =
                    participants.get(name);

                System.out.println(
                    name +
                    " | Balance: " + participant.balance() +
                    " | State: " + participant.state(transaction.id())
                );
            }
        }
    }

    static final class Coordinator {
        private final Map<String, TransactionParticipant> participants =
            new HashMap<>();

        private final Map<TransactionId, Transaction> transactions =
            new HashMap<>();

        private final Map<TransactionId, Map<String, Operation>> operations =
            new HashMap<>();

        private final DurableJournal journal;

        Coordinator(DurableJournal journal) {
            this.journal = journal;
        }

        void register(TransactionParticipant participant) {
            if (participants.putIfAbsent(
                participant.name(),
                participant
            ) != null) {
                throw new TransactionException(
                    "Duplicate participant: " + participant.name()
                );
            }
        }

        Transaction begin(
            String description,
            List<String> participantNames,
            Map<String, Operation> transactionOperations
        ) {
            if (participantNames.isEmpty()) {
                throw new TransactionException(
                    "Transaction requires participants"
                );
            }

            if (transactionOperations.size() != participantNames.size()) {
                throw new TransactionException(
                    "Operation count does not match participant count"
                );
            }

            for (String name : participantNames) {
                if (!participants.containsKey(name)) {
                    throw new TransactionException(
                        "Unknown participant: " + name
                    );
                }

                if (!transactionOperations.containsKey(name)) {
                    throw new TransactionException(
                        "Missing operation for " + name
                    );
                }
            }

            Transaction transaction = new Transaction(
                description,
                participantNames
            );

            transactions.put(transaction.id(), transaction);

            operations.put(
                transaction.id(),
                Map.copyOf(transactionOperations)
            );

            journal.append(
                transaction.id(),
                "BEGIN",
                description
            );

            return transaction;
        }

        boolean prepare(Transaction transaction) {
            if (transaction.state() == TransactionState.PREPARED) {
                return true;
            }

            if (transaction.state() != TransactionState.ACTIVE) {
                throw new InvalidTransitionException(
                    "Transaction cannot enter preparation"
                );
            }

            transaction.transition(TransactionState.PREPARING);

            journal.append(
                transaction.id(),
                "PREPARE_REQUESTED",
                "Phase 1 started"
            );

            boolean allYes = true;

            Map<String, Operation> transactionOperations =
                operations.get(transaction.id());

            for (String name : transaction.participantNames()) {
                TransactionParticipant participant =
                    participants.get(name);

                Vote vote;

                try {
                    vote = participant.prepare(
                        transaction.id(),
                        transactionOperations.get(name)
                    );
                } catch (ParticipantUnavailableException exception) {
                    vote = Vote.NO;

                    System.err.println(
                        "Participant failure: " + exception.getMessage()
                    );
                }

                transaction.recordVote(name, vote);

                journal.append(
                    transaction.id(),
                    "VOTE",
                    name + ":" + vote
                );

                if (vote != Vote.YES) {
                    allYes = false;
                }
            }

            if (!allYes) {
                recordDecision(transaction, Decision.ABORT);
                deliverDecision(transaction);
                return false;
            }

            transaction.transition(TransactionState.PREPARED);

            journal.append(
                transaction.id(),
                "ALL_PREPARED",
                "Unanimous YES"
            );

            return true;
        }

        private void recordDecision(
            Transaction transaction,
            Decision decision
        ) {
            if (transaction.decision() != null) {
                if (transaction.decision() != decision) {
                    throw new InvalidTransitionException(
                        "Cannot reverse global decision"
                    );
                }

                return;
            }

            // Persist before any participant receives the decision.
            journal.append(
                transaction.id(),
                "GLOBAL_DECISION",
                decision.name()
            );

            transaction.setDecision(decision);

            transaction.transition(
                decision == Decision.COMMIT
                    ? TransactionState.COMMITTING
                    : TransactionState.ABORTING
            );
        }

        void commit(Transaction transaction) {
            if (transaction.state() == TransactionState.COMMITTED) {
                return;
            }

            if (transaction.state() != TransactionState.PREPARED) {
                throw new InvalidTransitionException(
                    "Commit requires PREPARED state"
                );
            }

            recordDecision(transaction, Decision.COMMIT);
            deliverDecision(transaction);
        }

        void abort(Transaction transaction) {
            if (transaction.state() == TransactionState.ABORTED) {
                return;
            }

            if (transaction.decision() == Decision.COMMIT) {
                throw new InvalidTransitionException(
                    "Commit decision already persisted"
                );
            }

            if (transaction.state() == TransactionState.COMMITTED ||
                transaction.state() == TransactionState.COMMITTING) {
                throw new InvalidTransitionException(
                    "Cannot abort transaction"
                );
            }

            recordDecision(transaction, Decision.ABORT);
            deliverDecision(transaction);
        }

        private void deliverDecision(Transaction transaction) {
            if (transaction.decision() == null) {
                throw new TransactionException(
                    "Missing global decision"
                );
            }

            List<String> failures = new ArrayList<>();

            for (String name : transaction.participantNames()) {
                try {
                    TransactionParticipant participant =
                        participants.get(name);

                    if (transaction.decision() == Decision.COMMIT) {
                        participant.commit(transaction.id());
                    } else {
                        participant.abort(transaction.id());
                    }

                } catch (TransactionException exception) {
                    failures.add(name + ": " + exception.getMessage());
                }
            }

            if (!failures.isEmpty()) {
                transaction.transition(TransactionState.IN_DOUBT);

                journal.append(
                    transaction.id(),
                    "DELIVERY_INCOMPLETE",
                    String.join("; ", failures)
                );

                return;
            }

            transaction.transition(
                transaction.decision() == Decision.COMMIT
                    ? TransactionState.COMMITTED
                    : TransactionState.ABORTED
            );

            journal.append(
                transaction.id(),
                "COMPLETED",
                transaction.state().name()
            );
        }

        void recover(Transaction transaction) {
            if (transaction.decision() == null) {
                throw new TransactionException(
                    "Missing durable decision; recovery cannot guess"
                );
            }

            if (transaction.state() == TransactionState.COMMITTED ||
                transaction.state() == TransactionState.ABORTED) {
                return;
            }

            deliverDecision(transaction);
        }

        TransactionReport report(Transaction transaction) {
            return new TransactionReport(transaction, participants);
        }

        int eventCount() {
            return journal.readAll().size();
        }
    }

    public static void main(String[] args) {
        try (DurableJournal journal =
                 new DurableJournal("2pc_java_events.log")) {

            Coordinator coordinator = new Coordinator(journal);

            AccountParticipant bankA =
                new AccountParticipant("BANK_A", 10000);

            AccountParticipant bankB =
                new AccountParticipant("BANK_B", 5000);

            AccountParticipant bankC =
                new AccountParticipant("BANK_C", 7000);

            coordinator.register(bankA);
            coordinator.register(bankB);
            coordinator.register(bankC);

            System.out.println("CASE 1: Successful distributed transfer");

            Transaction tx1 = coordinator.begin(
                "Transfer 1000 from BANK_A to BANK_B",
                List.of("BANK_A", "BANK_B"),
                Map.of(
                    "BANK_A", new Operation(1000, 0),
                    "BANK_B", new Operation(0, 1000)
                )
            );

            if (coordinator.prepare(tx1)) {
                coordinator.commit(tx1);
            }

            coordinator.report(tx1).print();

            if (tx1.state() != TransactionState.COMMITTED ||
                bankA.balance() != 9000 ||
                bankB.balance() != 6000) {
                throw new TransactionException(
                    "Successful transfer verification failed"
                );
            }

            System.out.println("\nCASE 2: Insufficient funds");

            Transaction tx2 = coordinator.begin(
                "Rejected transfer",
                List.of("BANK_A", "BANK_C"),
                Map.of(
                    "BANK_A", new Operation(500, 0),
                    "BANK_C", new Operation(100000, 0)
                )
            );

            if (coordinator.prepare(tx2) ||
                tx2.state() != TransactionState.ABORTED) {
                throw new TransactionException(
                    "Expected ABORTED transaction"
                );
            }

            coordinator.report(tx2).print();

            System.out.println("\nCASE 3: Participant failure during commit");

            Transaction tx3 = coordinator.begin(
                "Delayed commit delivery",
                List.of("BANK_A", "BANK_B"),
                Map.of(
                    "BANK_A", new Operation(200, 0),
                    "BANK_B", new Operation(0, 200)
                )
            );

            if (!coordinator.prepare(tx3)) {
                throw new TransactionException(
                    "Unexpected preparation failure"
                );
            }

            bankB.setAvailable(false);
            coordinator.commit(tx3);

            if (tx3.state() != TransactionState.IN_DOUBT) {
                throw new TransactionException(
                    "Expected IN_DOUBT state"
                );
            }

            coordinator.report(tx3).print();

            bankB.setAvailable(true);

            coordinator.recover(tx3);
            coordinator.recover(tx3);

            if (tx3.state() != TransactionState.COMMITTED ||
                bankB.balance() != 6200) {
                throw new TransactionException(
                    "Recovery verification failed"
                );
            }

            System.out.println("\nCASE 4: Idempotent recovery");

            System.out.println(
                "Repeated recovery did not duplicate committed operations."
            );

            System.out.println("\nCASE 5: Journal verification");

            System.out.println(
                "Persisted journal records: " + coordinator.eventCount()
            );

            System.out.println("\nAll Java 17 tests passed.");

        } catch (Exception exception) {
            System.err.println(
                "Transaction system failure: " + exception.getMessage()
            );

            exception.printStackTrace();
            System.exit(1);
        }
    }
}
