#include <algorithm>
#include <cstdint>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <map>
#include <optional>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <vector>

/*
 * Distributed Transaction Coordination Engine.
 *
 * Implements:
 * - Two-phase commit.
 * - Participant voting.
 * - Transaction state machines.
 * - Durable decision records.
 * - Protected commit and abort transitions.
 * - Idempotent participant operations.
 * - Failure detection.
 * - In-doubt transaction recovery.
 * - Merge-free resource coordination.
 *
 * Monetary values use integer minor units to avoid floating-point errors.
 */

enum class TxState {
    Active,
    Preparing,
    Prepared,
    Committing,
    Committed,
    Aborting,
    Aborted,
    InDoubt
};

enum class ParticipantState {
    Active,
    Prepared,
    Committed,
    Aborted,
    Failed
};

enum class Decision {
    Commit,
    Abort
};

enum class Vote {
    Yes,
    No
};

std::string toString(TxState state) {
    switch (state) {
        case TxState::Active: return "ACTIVE";
        case TxState::Preparing: return "PREPARING";
        case TxState::Prepared: return "PREPARED";
        case TxState::Committing: return "COMMITTING";
        case TxState::Committed: return "COMMITTED";
        case TxState::Aborting: return "ABORTING";
        case TxState::Aborted: return "ABORTED";
        case TxState::InDoubt: return "IN_DOUBT";
    }
    throw std::logic_error("Unknown transaction state");
}

std::string toString(Decision decision) {
    return decision == Decision::Commit ? "COMMIT" : "ABORT";
}

class TransactionError : public std::runtime_error {
public:
    explicit TransactionError(const std::string& message)
        : std::runtime_error(message) {}
};

struct Operation {
    std::int64_t debit = 0;
    std::int64_t credit = 0;
};

struct Transaction {
    std::string id;
    std::string description;
    TxState state = TxState::Active;

    std::vector<std::string> participants;
    std::map<std::string, Vote> votes;
    std::optional<Decision> decision;
};

class DecisionLog {
private:
    std::string filename;

public:
    explicit DecisionLog(std::string path)
        : filename(std::move(path)) {}

    void append(const std::string& event) {
        std::ofstream file(
            filename,
            std::ios::out | std::ios::app
        );

        if (!file.is_open()) {
            throw TransactionError("Unable to open decision log");
        }

        file << event << '\n';
        file.flush();

        if (!file.good()) {
            throw TransactionError("Unable to persist decision record");
        }
    }

    std::vector<std::string> readAll() const {
        std::ifstream file(filename);

        if (!file.is_open()) {
            return {};
        }

        std::vector<std::string> records;
        std::string line;

        while (std::getline(file, line)) {
            if (!line.empty()) {
                records.push_back(line);
            }
        }

        return records;
    }
};

class Participant {
private:
    struct PendingOperation {
        Operation operation;
    };

    std::string name;
    std::int64_t balance;
    bool available = true;
    bool allowPrepare = true;

    std::map<std::string, ParticipantState> states;
    std::map<std::string, PendingOperation> pending;

public:
    Participant(
        std::string participantName,
        std::int64_t initialBalance,
        bool prepareAllowed = true
    )
        : name(std::move(participantName)),
          balance(initialBalance),
          allowPrepare(prepareAllowed) {

        if (name.empty() || balance < 0) {
            throw std::invalid_argument("Invalid participant");
        }
    }

    const std::string& getName() const {
        return name;
    }

    std::int64_t getBalance() const {
        return balance;
    }

    void setAvailable(bool value) {
        available = value;
    }

    Vote prepare(const std::string& transactionId, Operation operation) {
        if (!available) {
            throw TransactionError(name + " unavailable during prepare");
        }

        if (operation.debit < 0 || operation.credit < 0) {
            throw std::invalid_argument("Negative operation amount");
        }

        auto existing = states.find(transactionId);

        if (existing != states.end()) {
            if (existing->second == ParticipantState::Prepared ||
                existing->second == ParticipantState::Committed) {
                return Vote::Yes;
            }

            if (existing->second == ParticipantState::Aborted) {
                return Vote::No;
            }
        }

        if (!allowPrepare || balance < operation.debit) {
            states[transactionId] = ParticipantState::Failed;
            return Vote::No;
        }

        // Reserve the operation without modifying the committed balance.
        pending[transactionId] = PendingOperation{operation};
        states[transactionId] = ParticipantState::Prepared;

        return Vote::Yes;
    }

    void commit(const std::string& transactionId) {
        if (!available) {
            throw TransactionError(name + " unavailable during commit");
        }

        auto existing = states.find(transactionId);

        if (existing != states.end() &&
            existing->second == ParticipantState::Committed) {
            return;
        }

        if (existing == states.end() ||
            existing->second != ParticipantState::Prepared) {
            throw TransactionError(
                name + " cannot commit without preparation"
            );
        }

        auto operation = pending.find(transactionId);

        if (operation == pending.end()) {
            throw TransactionError("Pending operation not found");
        }

        const auto& op = operation->second.operation;

        if (op.credit > INT64_MAX - (balance - op.debit)) {
            throw TransactionError("Balance overflow");
        }

        balance = balance - op.debit + op.credit;

        pending.erase(operation);
        states[transactionId] = ParticipantState::Committed;
    }

    void abort(const std::string& transactionId) {
        if (!available) {
            throw TransactionError(name + " unavailable during abort");
        }

        auto existing = states.find(transactionId);

        if (existing != states.end()) {
            if (existing->second == ParticipantState::Aborted) {
                return;
            }

            if (existing->second == ParticipantState::Committed) {
                throw TransactionError(
                    "Cannot abort committed participant"
                );
            }
        }

        pending.erase(transactionId);
        states[transactionId] = ParticipantState::Aborted;
    }

    std::string getState(const std::string& transactionId) const {
        auto iterator = states.find(transactionId);

        if (iterator == states.end()) {
            return "NOT_REGISTERED";
        }

        switch (iterator->second) {
            case ParticipantState::Active: return "ACTIVE";
            case ParticipantState::Prepared: return "PREPARED";
            case ParticipantState::Committed: return "COMMITTED";
            case ParticipantState::Aborted: return "ABORTED";
            case ParticipantState::Failed: return "FAILED";
        }

        return "UNKNOWN";
    }
};

class Coordinator {
private:
    std::map<std::string, Participant*> participants;
    std::map<std::string, Transaction> transactions;
    DecisionLog log;
    std::uint64_t nextId = 1;

    Transaction& getTransaction(const std::string& id) {
        auto iterator = transactions.find(id);

        if (iterator == transactions.end()) {
            throw TransactionError("Unknown transaction");
        }

        return iterator->second;
    }

    void transition(
        Transaction& transaction,
        TxState next
    ) {
        static const std::map<TxState, std::set<TxState>> allowed = {
            {TxState::Active, {
                TxState::Preparing,
                TxState::Aborting
            }},
            {TxState::Preparing, {
                TxState::Prepared,
                TxState::Aborting
            }},
            {TxState::Prepared, {
                TxState::Committing,
                TxState::Aborting
            }},
            {TxState::Committing, {
                TxState::Committed,
                TxState::InDoubt
            }},
            {TxState::Aborting, {
                TxState::Aborted,
                TxState::InDoubt
            }},
            {TxState::InDoubt, {
                TxState::Committed,
                TxState::Aborted
            }},
            {TxState::Committed, {}},
            {TxState::Aborted, {}}
        };

        auto iterator = allowed.find(transaction.state);

        if (iterator == allowed.end() ||
            !iterator->second.count(next)) {
            throw TransactionError(
                "Illegal transition: " +
                toString(transaction.state) + " -> " +
                toString(next)
            );
        }

        transaction.state = next;
    }

    void recordDecision(Transaction& transaction, Decision decision) {
        if (transaction.decision.has_value()) {
            if (transaction.decision.value() != decision) {
                throw TransactionError(
                    "Global decision cannot be reversed"
                );
            }
            return;
        }

        // Write-ahead decision: persist before distributing phase 2.
        log.append(
            transaction.id + "|GLOBAL_DECISION|" +
            toString(decision)
        );

        transaction.decision = decision;

        transition(
            transaction,
            decision == Decision::Commit
                ? TxState::Committing
                : TxState::Aborting
        );
    }

    void deliverDecision(Transaction& transaction) {
        if (!transaction.decision.has_value()) {
            throw TransactionError("Global decision is missing");
        }

        std::vector<std::string> failures;

        for (const auto& name : transaction.participants) {
            try {
                Participant* participant = participants.at(name);

                if (transaction.decision.value() == Decision::Commit) {
                    participant->commit(transaction.id);
                } else {
                    participant->abort(transaction.id);
                }
            } catch (const std::exception& error) {
                failures.push_back(name + ": " + error.what());
            }
        }

        if (!failures.empty()) {
            transition(transaction, TxState::InDoubt);

            log.append(
                transaction.id + "|DELIVERY_INCOMPLETE|" +
                std::to_string(failures.size())
            );

            for (const auto& failure : failures) {
                std::cerr << "Recovery required: " << failure << '\n';
            }

            return;
        }

        transition(
            transaction,
            transaction.decision.value() == Decision::Commit
                ? TxState::Committed
                : TxState::Aborted
        );

        log.append(
            transaction.id + "|COMPLETED|" +
            toString(transaction.state)
        );
    }

public:
    explicit Coordinator(const std::string& logPath)
        : log(logPath) {}

    void registerParticipant(Participant& participant) {
        if (participants.count(participant.getName())) {
            throw TransactionError("Duplicate participant");
        }

        participants[participant.getName()] = &participant;
    }

    Transaction& begin(const std::string& description) {
        if (description.empty()) {
            throw std::invalid_argument("Description is required");
        }

        std::ostringstream id;
        id << "TX-" << std::setw(6) << std::setfill('0') << nextId++;

        Transaction transaction;
        transaction.id = id.str();
        transaction.description = description;

        log.append(transaction.id + "|BEGIN|" + description);

        auto result = transactions.emplace(
            transaction.id,
            std::move(transaction)
        );

        return result.first->second;
    }

    void enlist(Transaction& transaction, const std::string& name) {
        if (transaction.state != TxState::Active) {
            throw TransactionError("Cannot enlist after preparation");
        }

        if (!participants.count(name)) {
            throw TransactionError("Unknown participant");
        }

        if (std::find(
            transaction.participants.begin(),
            transaction.participants.end(),
            name
        ) != transaction.participants.end()) {
            throw TransactionError("Participant already enlisted");
        }

        transaction.participants.push_back(name);
    }

    bool prepare(
        Transaction& transaction,
        const std::map<std::string, Operation>& operations
    ) {
        if (transaction.state == TxState::Prepared) {
            return true;
        }

        if (transaction.state != TxState::Active) {
            throw TransactionError("Transaction cannot be prepared");
        }

        if (transaction.participants.empty()) {
            throw TransactionError("No participants enlisted");
        }

        if (operations.size() != transaction.participants.size()) {
            throw TransactionError("Operation count mismatch");
        }

        for (const auto& name : transaction.participants) {
            if (!operations.count(name)) {
                throw TransactionError("Missing participant operation");
            }
        }

        transition(transaction, TxState::Preparing);

        log.append(transaction.id + "|PREPARE_REQUESTED");

        bool unanimous = true;

        for (const auto& name : transaction.participants) {
            Vote vote = Vote::No;

            try {
                vote = participants.at(name)->prepare(
                    transaction.id,
                    operations.at(name)
                );
            } catch (const std::exception& error) {
                std::cerr << name << ": " << error.what() << '\n';
            }

            transaction.votes[name] = vote;

            log.append(
                transaction.id + "|VOTE|" + name + "|" +
                (vote == Vote::Yes ? "YES" : "NO")
            );

            if (vote != Vote::Yes) {
                unanimous = false;
            }
        }

        if (!unanimous) {
            recordDecision(transaction, Decision::Abort);
            deliverDecision(transaction);
            return false;
        }

        transition(transaction, TxState::Prepared);
        log.append(transaction.id + "|ALL_PREPARED");

        return true;
    }

    void commit(Transaction& transaction) {
        if (transaction.state == TxState::Committed) {
            return;
        }

        if (transaction.state != TxState::Prepared) {
            throw TransactionError("Transaction is not prepared");
        }

        recordDecision(transaction, Decision::Commit);
        deliverDecision(transaction);
    }

    void abort(Transaction& transaction) {
        if (transaction.state == TxState::Aborted) {
            return;
        }

        if (transaction.decision == Decision::Commit) {
            throw TransactionError("Cannot reverse COMMIT decision");
        }

        if (transaction.state == TxState::Committed ||
            transaction.state == TxState::Committing) {
            throw TransactionError("Transaction cannot be aborted");
        }

        recordDecision(transaction, Decision::Abort);
        deliverDecision(transaction);
    }

    void recover(Transaction& transaction) {
        if (!transaction.decision.has_value()) {
            transition(transaction, TxState::InDoubt);
            throw TransactionError(
                "No durable decision; participant reconciliation required"
            );
        }

        if (transaction.state == TxState::Committed ||
            transaction.state == TxState::Aborted) {
            return;
        }

        deliverDecision(transaction);
    }

    void report(const Transaction& transaction) const {
        std::cout << "\nTransaction: " << transaction.id
                  << "\nDescription: " << transaction.description
                  << "\nState: " << toString(transaction.state)
                  << "\nDecision: ";

        if (transaction.decision.has_value()) {
            std::cout << toString(transaction.decision.value());
        } else {
            std::cout << "NONE";
        }

        std::cout << "\nParticipants:\n";

        for (const auto& name : transaction.participants) {
            const auto* participant = participants.at(name);

            std::cout << "  " << name
                      << " | Balance: " << participant->getBalance()
                      << " | State: "
                      << participant->getState(transaction.id)
                      << '\n';
        }
    }

    std::size_t eventCount() const {
        return log.readAll().size();
    }
};

int main() {
    try {
        Participant bankA("BANK_A", 10000);
        Participant bankB("BANK_B", 5000);
        Participant bankC("BANK_C", 7000);

        Coordinator coordinator("2pc_cpp.log");

        coordinator.registerParticipant(bankA);
        coordinator.registerParticipant(bankB);
        coordinator.registerParticipant(bankC);

        std::cout << "CASE 1: Successful transaction\n";

        Transaction& tx1 = coordinator.begin(
            "Transfer 1000 from BANK_A to BANK_B"
        );

        coordinator.enlist(tx1, "BANK_A");
        coordinator.enlist(tx1, "BANK_B");

        std::map<std::string, Operation> operations1 = {
            {"BANK_A", {1000, 0}},
            {"BANK_B", {0, 1000}}
        };

        if (coordinator.prepare(tx1, operations1)) {
            coordinator.commit(tx1);
        }

        coordinator.report(tx1);

        if (tx1.state != TxState::Committed ||
            bankA.getBalance() != 9000 ||
            bankB.getBalance() != 6000) {
            throw TransactionError("Successful transaction validation failed");
        }

        std::cout << "\nCASE 2: Insufficient funds\n";

        Transaction& tx2 = coordinator.begin(
            "Rejected transfer"
        );

        coordinator.enlist(tx2, "BANK_A");
        coordinator.enlist(tx2, "BANK_C");

        std::map<std::string, Operation> operations2 = {
            {"BANK_A", {500, 0}},
            {"BANK_C", {100000, 0}}
        };

        bool prepared = coordinator.prepare(tx2, operations2);

        if (prepared || tx2.state != TxState::Aborted) {
            throw TransactionError("Expected transaction abort");
        }

        coordinator.report(tx2);

        std::cout << "\nCASE 3: Participant unavailable in phase 2\n";

        Transaction& tx3 = coordinator.begin(
            "Delayed commit delivery"
        );

        coordinator.enlist(tx3, "BANK_A");
        coordinator.enlist(tx3, "BANK_B");

        std::map<std::string, Operation> operations3 = {
            {"BANK_A", {200, 0}},
            {"BANK_B", {0, 200}}
        };

        if (!coordinator.prepare(tx3, operations3)) {
            throw TransactionError("Unexpected prepare failure");
        }

        bankB.setAvailable(false);
        coordinator.commit(tx3);

        if (tx3.state != TxState::InDoubt) {
            throw TransactionError("Expected IN_DOUBT");
        }

        coordinator.report(tx3);

        bankB.setAvailable(true);
        coordinator.recover(tx3);
        coordinator.recover(tx3);

        if (tx3.state != TxState::Committed ||
            bankB.getBalance() != 6200) {
            throw TransactionError("Recovery verification failed");
        }

        std::cout << "\nCASE 4: Durable event log\n";
        std::cout << "Recorded events: "
                  << coordinator.eventCount() << '\n';

        std::cout << "\nAll C++17 transaction tests passed.\n";
        return 0;

    } catch (const std::exception& error) {
        std::cerr << "Transaction engine failure: "
                  << error.what() << '\n';
        return 1;
    }
}
