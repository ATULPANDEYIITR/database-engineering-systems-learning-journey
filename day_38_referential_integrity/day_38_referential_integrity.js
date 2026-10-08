"use strict";

/*
 * Referential integrity in JavaScript.
 *
 * This file models a customer -> order -> order-item hierarchy and then
 * demonstrates the same relationship through SQLite-compatible SQL concepts.
 *
 * The in-memory model is intentionally event-driven: every relationship
 * mutation emits an event so an application can observe parent deletion,
 * cascading child deletion, and integrity failures.
 */

class ReferentialIntegrityError extends Error {
    constructor(message) {
        super(message);
        this.name = "ReferentialIntegrityError";
    }
}

const CascadeAction = Object.freeze({
    RESTRICT: "RESTRICT",
    CASCADE: "CASCADE",
    SET_NULL: "SET NULL"
});

class EventBus {
    constructor() {
        this.listeners = new Map();
    }

    on(eventName, listener) {
        if (!this.listeners.has(eventName)) {
            this.listeners.set(eventName, []);
        }
        this.listeners.get(eventName).push(listener);
    }

    emit(eventName, payload) {
        for (const listener of this.listeners.get(eventName) ?? []) {
            listener(payload);
        }
    }
}

class Repository {
    constructor() {
        this.customers = new Map();
        this.orders = new Map();
        this.items = new Map();

        this.relationshipPolicies = {
            customerToOrder: CascadeAction.RESTRICT,
            orderToItem: CascadeAction.CASCADE
        };

        this.events = new EventBus();
    }

    addCustomer(id, name) {
        if (!Number.isInteger(id) || id <= 0) {
            throw new TypeError("Customer ID must be a positive integer.");
        }

        if (this.customers.has(id)) {
            throw new ReferentialIntegrityError(
                `Customer ${id} already exists.`
            );
        }

        if (typeof name !== "string" || name.trim() === "") {
            throw new TypeError("Customer name must not be empty.");
        }

        this.customers.set(id, {
            customerId: id,
            name: name.trim()
        });

        this.events.emit("customer.created", {
            customerId: id
        });
    }

    addOrder(id, customerId, amount) {
        if (this.orders.has(id)) {
            throw new ReferentialIntegrityError(`Order ${id} already exists.`);
        }

        if (!this.customers.has(customerId)) {
            throw new ReferentialIntegrityError(
                `Order ${id} references missing customer ${customerId}.`
            );
        }

        if (!Number.isFinite(amount) || amount < 0) {
            throw new TypeError("Order amount must be a non-negative number.");
        }

        this.orders.set(id, {
            orderId: id,
            customerId,
            amount
        });

        this.events.emit("order.created", {
            orderId: id,
            customerId
        });
    }

    addItem(id, orderId, product, quantity) {
        if (this.items.has(id)) {
            throw new ReferentialIntegrityError(`Item ${id} already exists.`);
        }

        if (!this.orders.has(orderId)) {
            throw new ReferentialIntegrityError(
                `Item ${id} references missing order ${orderId}.`
            );
        }

        if (!Number.isInteger(quantity) || quantity <= 0) {
            throw new TypeError("Quantity must be a positive integer.");
        }

        if (typeof product !== "string" || product.trim() === "") {
            throw new TypeError("Product name must not be empty.");
        }

        this.items.set(id, {
            itemId: id,
            orderId,
            product: product.trim(),
            quantity
        });

        this.events.emit("item.created", {
            itemId: id,
            orderId
        });
    }

    findOrdersByCustomer(customerId) {
        return [...this.orders.values()].filter(
            order => order.customerId === customerId
        );
    }

    findItemsByOrder(orderId) {
        return [...this.items.values()].filter(
            item => item.orderId === orderId
        );
    }

    deleteCustomer(customerId) {
        if (!this.customers.has(customerId)) {
            throw new ReferentialIntegrityError(
                `Customer ${customerId} does not exist.`
            );
        }

        const dependents = this.findOrdersByCustomer(customerId);

        if (this.relationshipPolicies.customerToOrder === CascadeAction.RESTRICT &&
            dependents.length > 0) {
            throw new ReferentialIntegrityError(
                `Cannot delete customer ${customerId}; ` +
                `${dependents.length} dependent order(s) exist.`
            );
        }

        if (this.relationshipPolicies.customerToOrder === CascadeAction.CASCADE) {
            for (const order of dependents) {
                this.deleteOrder(order.orderId);
            }
        }

        this.customers.delete(customerId);

        this.events.emit("customer.deleted", {
            customerId
        });
    }

    deleteOrder(orderId) {
        if (!this.orders.has(orderId)) {
            throw new ReferentialIntegrityError(
                `Order ${orderId} does not exist.`
            );
        }

        const dependents = this.findItemsByOrder(orderId);

        if (this.relationshipPolicies.orderToItem === CascadeAction.CASCADE) {
            for (const item of dependents) {
                this.items.delete(item.itemId);

                this.events.emit("item.deleted", {
                    itemId: item.itemId,
                    reason: "cascade"
                });
            }
        } else if (
            this.relationshipPolicies.orderToItem === CascadeAction.RESTRICT &&
            dependents.length > 0
        ) {
            throw new ReferentialIntegrityError(
                `Cannot delete order ${orderId}; dependent items exist.`
            );
        } else if (
            this.relationshipPolicies.orderToItem === CascadeAction.SET_NULL
        ) {
            for (const item of dependents) {
                item.orderId = null;
            }
        }

        const order = this.orders.get(orderId);
        this.orders.delete(orderId);

        this.events.emit("order.deleted", {
            orderId,
            customerId: order.customerId,
            cascadeCount: dependents.length
        });
    }

    reassignOrder(orderId, newCustomerId) {
        const order = this.orders.get(orderId);

        if (!order) {
            throw new ReferentialIntegrityError(
                `Order ${orderId} does not exist.`
            );
        }

        if (!this.customers.has(newCustomerId)) {
            throw new ReferentialIntegrityError(
                `Customer ${newCustomerId} does not exist.`
            );
        }

        const oldCustomerId = order.customerId;
        order.customerId = newCustomerId;

        this.events.emit("order.reassigned", {
            orderId,
            oldCustomerId,
            newCustomerId
        });
    }

    validateIntegrity() {
        const violations = [];

        for (const order of this.orders.values()) {
            if (!this.customers.has(order.customerId)) {
                violations.push(
                    `Order ${order.orderId} references missing customer ` +
                    `${order.customerId}.`
                );
            }
        }

        for (const item of this.items.values()) {
            if (item.orderId !== null && !this.orders.has(item.orderId)) {
                violations.push(
                    `Item ${item.itemId} references missing order ` +
                    `${item.orderId}.`
                );
            }
        }

        return violations;
    }

    snapshot() {
        return {
            customers: this.customers.size,
            orders: this.orders.size,
            items: this.items.size
        };
    }
}

function printEvent(title, payload) {
    console.log(`[EVENT] ${title}`, payload);
}

function demonstrateRestrict() {
    console.log("\n=== RESTRICT ===");

    const repository = new Repository();

    repository.events.on("customer.deleted", payload =>
        printEvent("customer.deleted", payload)
    );

    repository.addCustomer(1, "Atlas Manufacturing");
    repository.addOrder(101, 1, 12000);

    try {
        repository.deleteCustomer(1);
    } catch (error) {
        console.log(error.name + ":", error.message);
    }

    console.log("State:", repository.snapshot());
}

function demonstrateCascade() {
    console.log("\n=== CASCADE ===");

    const repository = new Repository();

    repository.events.on("item.deleted", payload =>
        printEvent("item.deleted", payload)
    );

    repository.events.on("order.deleted", payload =>
        printEvent("order.deleted", payload)
    );

    repository.addCustomer(2, "Northwind Engineering");
    repository.addOrder(201, 2, 35000);
    repository.addItem(2001, 201, "Sensor", 10);
    repository.addItem(2002, 201, "Gateway", 2);

    console.log("Before order deletion:", repository.snapshot());

    repository.deleteOrder(201);

    console.log("After order deletion:", repository.snapshot());
    console.log("Integrity violations:", repository.validateIntegrity());
}

function demonstrateTransitiveCascade() {
    console.log("\n=== TRANSITIVE CASCADE ===");

    const repository = new Repository();

    repository.relationshipPolicies.customerToOrder = CascadeAction.CASCADE;

    repository.addCustomer(3, "Cascade Industries");
    repository.addOrder(301, 3, 1000);
    repository.addOrder(302, 3, 2000);
    repository.addItem(3001, 301, "Component A", 4);
    repository.addItem(3002, 302, "Component B", 5);

    console.log("Before customer deletion:", repository.snapshot());

    repository.deleteCustomer(3);

    console.log("After customer -> order -> item cascade:",
        repository.snapshot());
}

function demonstrateSetNull() {
    console.log("\n=== SET NULL ===");

    const repository = new Repository();

    repository.relationshipPolicies.orderToItem = CascadeAction.SET_NULL;

    repository.addCustomer(4, "Nullable Relationship Corp");
    repository.addOrder(401, 4, 750);
    repository.addItem(4001, 401, "Retained Item", 1);

    repository.deleteOrder(401);

    const retainedItem = repository.items.get(4001);

    console.log("Retained item:", retainedItem);
    console.log(
        "The child survives because its foreign-key value becomes null."
    );
}

function demonstrateUpdateReference() {
    console.log("\n=== REFERENTIAL UPDATE ===");

    const repository = new Repository();

    repository.addCustomer(10, "Original Key");
    repository.addOrder(1001, 10, 5000);

    const customer = repository.customers.get(10);
    repository.customers.delete(10);
    repository.customers.set(11, {
        customerId: 11,
        name: customer.name
    });

    for (const order of repository.orders.values()) {
        if (order.customerId === 10) {
            order.customerId = 11;
        }
    }

    console.log("Updated order:", repository.orders.get(1001));
    console.log("Integrity violations:", repository.validateIntegrity());
}

function demonstrateAtomicApplicationOperation() {
    console.log("\n=== APPLICATION-LEVEL ATOMIC OPERATION ===");

    const repository = new Repository();

    repository.addCustomer(20, "Atomicity Test");
    repository.addOrder(2001, 20, 900);
    repository.addItem(20001, 2001, "Component", 2);

    /*
     * Database transactions are the authoritative mechanism for atomicity.
     * This snapshot is only an application-level illustration and is not a
     * substitute for a real database transaction.
     */
    const before = {
        customers: new Map(repository.customers),
        orders: new Map(repository.orders),
        items: new Map(repository.items)
    };

    try {
        repository.deleteOrder(2001);
        repository.deleteCustomer(20);

        if (repository.validateIntegrity().length !== 0) {
            throw new ReferentialIntegrityError(
                "Integrity validation failed."
            );
        }

        console.log("Atomic workflow completed:", repository.snapshot());
    } catch (error) {
        repository.customers = before.customers;
        repository.orders = before.orders;
        repository.items = before.items;

        console.log("Rolled back application state:", error.message);
    }
}

function demonstrateInvalidReferences() {
    console.log("\n=== INVALID REFERENCES ===");

    const repository = new Repository();

    try {
        repository.addOrder(5001, 9999, 100);
    } catch (error) {
        console.log("Rejected orphan order:", error.message);
    }

    repository.addCustomer(50, "Validation Customer");

    try {
        repository.addItem(50001, 8888, "Orphan Item", 1);
    } catch (error) {
        console.log("Rejected orphan item:", error.message);
    }

    repository.addOrder(5002, 50, 100);

    try {
        repository.reassignOrder(5002, 7777);
    } catch (error) {
        console.log("Rejected invalid reassignment:", error.message);
    }
}

function generatePostgreSQLDefinition() {
    console.log("\n=== POSTGRESQL RELATIONSHIP DEFINITION ===");

    const sql = `
CREATE TABLE customer (
    customer_id BIGINT PRIMARY KEY,
    name TEXT NOT NULL
);

CREATE TABLE customer_order (
    order_id BIGINT PRIMARY KEY,
    customer_id BIGINT NOT NULL,
    amount NUMERIC(12,2) NOT NULL CHECK (amount >= 0),
    CONSTRAINT fk_order_customer
        FOREIGN KEY (customer_id)
        REFERENCES customer(customer_id)
        ON DELETE RESTRICT
        ON UPDATE CASCADE
);

CREATE TABLE order_item (
    item_id BIGINT PRIMARY KEY,
    order_id BIGINT NOT NULL,
    product TEXT NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    CONSTRAINT fk_item_order
        FOREIGN KEY (order_id)
        REFERENCES customer_order(order_id)
        ON DELETE CASCADE
);
`;

    console.log(sql);
}

function main() {
    console.log("REFERENTIAL INTEGRITY WORKFLOW");

    demonstrateRestrict();
    demonstrateCascade();
    demonstrateTransitiveCascade();
    demonstrateSetNull();
    demonstrateUpdateReference();
    demonstrateAtomicApplicationOperation();
    demonstrateInvalidReferences();
    generatePostgreSQLDefinition();

    console.log("\nKey design rule:");
    console.log(
        "A foreign key protects the existence of the referenced parent row; " +
        "a cascading action defines what happens to dependent rows when " +
        "the relationship changes."
    );
}

main();
