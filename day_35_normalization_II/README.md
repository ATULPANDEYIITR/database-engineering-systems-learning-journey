# Normalization II: 1NF, 2NF, and 3NF

## Scope

This learning artifact studies three stages of relational normalization:

- **First Normal Form (1NF)** addresses repeating groups and non-atomic attribute values.
- **Second Normal Form (2NF)** addresses partial functional dependencies on part of a composite candidate key.
- **Third Normal Form (3NF)** addresses transitive dependencies in which a non-key attribute determines another non-key attribute.

The implementations use one coherent order-management domain, but each language approaches the subject from a different engineering perspective.

The central domain contains customers, orders, products, and order-line quantities.

The final normalized design is:

| Relation | Primary key | Main responsibility |
|---|---|---|
| `Customers` | `customer_id` | Stores facts determined by a customer |
| `Orders` | `order_id` | Stores facts determined by an order |
| `Products` | `product_id` | Stores facts determined by a product |
| `OrderItems` | `(order_id, product_id)` | Stores facts about a particular product within an order |

Normalization is not simply splitting a large table into smaller tables. The important question is **why each fact belongs where it does**. Functional dependencies provide that reasoning.

---

## Functional Dependencies

A functional dependency has the form `X -> Y`.

It means that once the value of `X` is known, the value of `Y` is determined for the relation under consideration.

The order-management example contains dependencies such as:

- `order_id -> order_date`
- `order_id -> customer_id`
- `customer_id -> customer_name, customer_city`
- `product_id -> product_name`
- `(order_id, product_id) -> quantity`

These dependencies explain the normalization decisions.

The dependency `order_id -> order_date` means that the order date belongs to the order identified by `order_id`.

The dependency `product_id -> product_name` means that the product name belongs to the product identified by `product_id`.

The dependency `(order_id, product_id) -> quantity` is different. Quantity describes how many units of a particular product occur in a particular order, so both identifiers are needed.

The dependency `customer_id -> customer_name, customer_city` establishes the ownership of customer attributes. Those attributes should not be repeatedly stored in every order.

---

## 1NF: Atomic Values and Repeating Groups

The starting representation deliberately stores several products inside one order.

A conceptual unnormalized row can look like:

`order_id = 1001`

`product_ids = P101,P102`

`product_names = Keyboard,Mouse`

`quantities = 2,1`

The problem is not merely that the string is inconvenient. A relational attribute is expected to contain one value from its defined domain. Packing several independent product occurrences into one attribute creates a repeating group.

It also introduces practical problems:

- Searching for a particular product requires parsing the packed value.
- A database cannot naturally enforce a foreign key from one comma-separated string to individual product identifiers.
- Indexing individual product occurrences becomes difficult.
- Updating one product occurrence requires manipulating a larger packed value.
- The number of products per order is represented indirectly rather than through rows.

### The 1NF transformation

The Python and JavaScript programs flatten the repeating product collection.

The C++ program turns every raw product entry into a `FirstNFRow`.

The resulting relation contains rows such as:

| order_id | product_id | product_name | quantity |
|---:|---|---|---:|
| 1001 | P101 | Keyboard | 2 |
| 1001 | P102 | Mouse | 1 |
| 1002 | P101 | Keyboard | 1 |

Each row represents one order-product occurrence.

Every value is atomic, and the relation can use `(order_id, product_id)` as its candidate key for the example.

1NF does **not** by itself eliminate all redundancy. The same customer information and product information can still appear on several rows. That is the issue addressed by 2NF.

---

## 2NF: The Composite-Key Problem

The 1NF relation uses the composite key:

`(order_id, product_id)`

Consider the attributes in that relation.

`quantity` depends on the entire key:

`(order_id, product_id) -> quantity`

The quantity cannot generally be identified from `order_id` alone because an order can contain several products.

It also cannot be identified from `product_id` alone because the same product can appear in many orders with different quantities.

The situation is different for order-level attributes.

`order_id -> order_date`

`order_id -> customer_id`

An order's date and customer do not require `product_id`.

Likewise:

`product_id -> product_name`

The product name does not require `order_id`.

These are **partial dependencies** because non-key attributes depend on only part of the composite candidate key.

### Why partial dependencies matter

Suppose order `1001` contains ten products.

If the order date and customer are stored on all ten rows, the same order-level facts are repeated ten times.

If the customer changes an attribute, multiple rows may need updating.

If the same product appears in hundreds of orders, its name is repeated hundreds of times.

The redundancy is a structural consequence of mixing facts with different determinants.

### 2NF decomposition

The implementations separate the relation into:

`Orders(order_id, order_date, customer_id, customer_name, customer_city)`

`Products(product_id, product_name)`

`OrderItems(order_id, product_id, quantity)`

The `OrderItems` relation retains the composite key because quantity genuinely belongs to the relationship between an order and a product.

The order attributes move to `Orders`.

The product attributes move to `Products`.

At this point the partial dependencies caused by the composite key have been removed.

2NF does not necessarily mean that the design is already in 3NF. The `Orders` relation still contains a dependency involving customer attributes.

---

## 3NF: Transitive Dependencies

After the 2NF decomposition, the `Orders` relation contains:

`order_id`

`order_date`

`customer_id`

`customer_name`

`customer_city`

There are two dependency levels:

`order_id -> customer_id`

and:

`customer_id -> customer_name, customer_city`

Therefore customer information is transitively dependent on `order_id`.

The order identifies the customer, and the customer identifies the customer's descriptive attributes.

The important distinction is that `customer_name` and `customer_city` are not facts determined directly by the order itself. They are facts about the customer.

### The 3NF decomposition

The final design separates the customer relation:

`Customers(customer_id, customer_name, customer_city)`

and reduces `Orders` to:

`Orders(order_id, order_date, customer_id)`

The resulting dependency structure is clearer:

`order_id -> order_date, customer_id`

`customer_id -> customer_name, customer_city`

`product_id -> product_name`

`(order_id, product_id) -> quantity`

Each relation has a clear determinant for its non-key facts.

---

## Distinguishing the Three Normal Forms

The three normal forms address different structural problems.

| Normal form | Primary question | Problem addressed in this example |
|---|---|---|
| 1NF | Does each attribute contain an atomic value rather than a repeating group? | Products and quantities were packed into repeating product groups |
| 2NF | Does every non-key attribute depend on the whole candidate key? | Order facts depended only on `order_id`; product facts depended only on `product_id` |
| 3NF | Does a non-key attribute determine another non-key attribute? | `customer_id` determined customer details inside the Orders relation |

The distinctions matter.

1NF is about the structure and atomicity of attribute values.

2NF is about dependencies on portions of a composite key.

3NF is about transitive dependencies through non-key determinants.

A design should not describe every redundancy problem as "a 3NF problem." The appropriate diagnosis depends on the functional dependency causing the redundancy.

---

## Python Implementation

The Python program is an executable normalization model rather than a collection of isolated syntax examples.

It begins with dictionaries containing a nested product collection. `check_atomic_values()` detects list, tuple, set, and dictionary values that violate the intended atomic representation.

`convert_to_1nf()` creates one row per order-product combination.

The program then tests the composite key with `assert_unique()` and uses `functional_dependency_holds()` to inspect whether a determinant consistently determines an attribute.

The 2NF transformation creates separate order, product, and order-item collections. The `deduplicate()` function is deliberately strict. It does not silently discard contradictory values for the same determinant. If two rows claim different customer information for the same `customer_id`, the program raises an exception instead of hiding the dependency violation.

The 3NF stage extracts customers into their own relation and removes customer descriptive attributes from orders.

The final Python validation checks:

- primary-key uniqueness,
- foreign-key relationships,
- positive order quantities,
- order-to-customer dependencies,
- customer-to-customer-attribute dependencies,
- product-to-product-name dependencies.

The final join reconstruction demonstrates that normalization changes storage structure without preventing the application from producing the combined business view.

---

## JavaScript Implementation

The JavaScript implementation uses a different perspective: data transformation and repository-style validation.

The initial model uses JavaScript objects containing a `products` array. This makes the repeating-group problem visible in a way that is natural for JavaScript data structures.

`findNonAtomicValues()` detects nested values.

`convertTo1NF()` turns the nested representation into atomic order-line records.

The 2NF stage uses `projectDistinct()` to project order and product facts into separate collections. The function checks that a projection does not hide contradictory values. This is important because simply using a `Map` to keep the last value could silently mask a functional-dependency violation.

`RepositoryStyleRelation` represents a relation with an explicit key and validation operation.

The final repository maintains separate maps for:

- customers,
- orders,
- products,
- order items.

`enforceForeignKeys()` verifies relationships between those maps.

`buildBusinessView()` performs the equivalent of relational joins using JavaScript `Map` objects. This demonstrates the practical difference between normalized storage and the combined view consumed by an application.

The implementation also shows how JavaScript's dynamic object model can be paired with explicit validation when the application must enforce relational assumptions outside a database.

---

## C++ Case Study

The C++ implementation models normalization as an integrity-oriented data transformation.

The raw domain uses `RawOrder`, which contains a `std::vector<RawProduct>`. This deliberately represents a repeating group.

The 1NF transformation creates `FirstNFRow` objects.

The 1NF candidate key is represented with:

`std::pair<int, std::string>`

corresponding to `(orderId, productId)`.

A `std::set` validates uniqueness of that composite key.

The 2NF transformation separates:

- `Order`
- `Product`
- `OrderItem`

The implementation uses `std::map` to detect contradictory dependencies. For example, if the same `productId` appears with two different product names, the transformation throws instead of arbitrarily selecting one.

The 3NF transformation creates `Customer` objects and removes customer descriptive fields from the normalized `Order` representation.

### Repository architecture

`NormalizedRepository` provides an in-memory representation of the final schema.

It maintains:

- `std::map<int, Order>` for orders,
- `std::map<std::string, Customer>` for customers,
- `std::map<std::string, Product>` for products,
- `std::map<CompositeKey, OrderItem>` for order items.

The repository explicitly validates primary-key uniqueness and foreign-key existence.

The composite order-item key prevents two records for the same order/product pair.

The repository also demonstrates an update operation against customer data. Because customer information has one authoritative owner, a city change updates one customer record rather than duplicated order rows.

The design therefore connects normalization to a concrete data-integrity architecture.

---

## Java Implementation

The Java implementation uses explicit domain types and validation abstractions.

Java records model immutable domain values:

- `Customer`
- `Product`
- `Order`
- `OrderItem`
- `RawOrder`
- `RawProduct`

The use of records is useful here because these objects represent relation tuples with value-based equality.

`NormalForm` provides an explicit domain representation of the normalization stages.

Validation is represented through the generic `RelationValidator<T>` interface. Customer, product, and order-item validation rules are therefore expressed as domain-specific components rather than being scattered through unrelated code.

The `Repository` class represents the normalized persistence boundary.

Its maps correspond to relational primary-key indexes:

- customer ID to customer,
- product ID to product,
- order ID to order,
- composite order/product identity to order item.

`addOrder()` checks the customer foreign key before inserting the order.

`addOrderItem()` checks both the order and product foreign keys and enforces a positive quantity.

The customer city update replaces one immutable customer record. This reflects the 3NF ownership boundary: customer facts belong to the customer identified by `customerId`.

The business view reconstructs the combined result by navigating relationships between the domain maps.

---

## SQL Data Model

The SQL implementation is PostgreSQL-compatible and demonstrates the normalization process inside a relational database.

The `unnormalized_orders` table deliberately stores product identifiers, names, and quantities as comma-separated text. It exists only as a teaching-stage representation.

PostgreSQL's `string_to_array()` and `unnest()` transform the packed values into atomic rows for `first_nf_order_lines`.

The 1NF relation has:

`PRIMARY KEY (order_id, product_id)`

The 2NF stage creates:

- `second_nf_orders`
- `second_nf_products`
- `second_nf_order_items`

Foreign keys connect order items to orders and products.

The final 3NF model creates:

- `customers`
- `products`
- `orders`
- `order_items`

The `orders.customer_id` foreign key identifies the customer without duplicating customer descriptive attributes.

### Database constraints

The database is not relying only on application code.

Primary keys enforce identity.

Foreign keys enforce valid relationships.

`CHECK (quantity > 0)` prevents invalid order quantities.

Additional checks prevent blank customer and product names.

This is important because normalization and integrity are closely related but not identical concepts. Normalization determines appropriate fact ownership and dependency structure, while constraints enforce many of the resulting rules at runtime.

### Indexing

Primary keys automatically provide indexes in PostgreSQL.

An explicit index on `orders(customer_id)` supports queries that locate orders belonging to a particular customer.

Indexes are not normalization rules. They are physical access structures that support efficient execution of queries against the normalized logical model.

---

## Anomalies

### Update anomaly

In an unnormalized or poorly decomposed design, customer information may appear on many order rows.

Changing a customer's city then requires every occurrence to be changed consistently.

In the 3NF design, the city is stored in `customers`.

An update targets one customer row.

### Insertion anomaly

If product information is stored only as part of order rows, a new product may be difficult to store before its first order.

The normalized `products` relation allows the product to exist independently.

The database therefore does not require an artificial order merely to create product master data.

### Deletion anomaly

If the only occurrence of a product description exists inside an order row, deleting the last order containing that product could unintentionally remove the product information.

Separating `products` prevents an order deletion from automatically deleting unrelated product master data.

The SQL implementation uses a foreign key from `order_items` to `products` without `ON DELETE CASCADE`, so PostgreSQL will reject deletion of a referenced product rather than silently removing product information.

---

## Lossless Reconstruction

Normalization should preserve the information represented by the original design.

The final business view joins:

`orders -> customers`

and:

`orders -> order_items -> products`

The SQL `order_business_view`, the Python dictionary-based reconstruction, the JavaScript map-based reconstruction, and the C++ repository view all demonstrate this principle.

The storage representation is decomposed, but applications can still obtain:

- order identifier,
- order date,
- customer,
- city,
- product,
- quantity.

The normalized structure stores each fact in an appropriate relation while relationships allow the original business perspective to be reconstructed.

---

## Edge Cases

### Duplicate order/product pair

Two `OrderItems` records with the same `(order_id, product_id)` would make the composite key ambiguous.

The final schema rejects this through the composite primary key.

### Conflicting customer facts

If two rows claim:

`C001 -> Lucknow`

and:

`C001 -> Kanpur`

the functional dependency `customer_id -> customer_city` does not hold for that dataset.

The Python, C++, and Java implementations explicitly detect this situation rather than silently selecting one value.

### Missing foreign key

An order referencing a nonexistent customer is structurally invalid.

The SQL schema rejects it through the foreign key.

The application implementations perform equivalent validation.

### Invalid quantity

A quantity of zero or a negative quantity has no valid meaning for the modeled order-line domain.

The SQL schema rejects it through a `CHECK` constraint, while the application implementations validate it before persistence.

### Empty identifiers

The Java implementation rejects blank customer and product identifiers.

The SQL model uses primary-key and non-null constraints plus checks for descriptive attributes where appropriate.

---

## Common Design Errors

A common mistake is to assume that any table with many columns is automatically insufficiently normalized. Column count is not the defining criterion. Functional dependencies determine the relevant decomposition.

Another mistake is to believe that 1NF means simply "do not use comma-separated strings." That is a useful practical warning, but the deeper requirement is atomic attribute values and elimination of repeating groups.

A third mistake is to claim that 2NF requires every table to have a single-column primary key. That is incorrect. A relation can be in 2NF while having a composite candidate key, provided no non-key attribute depends on only part of that key.

A fourth mistake is to confuse 3NF with eliminating every relationship between attributes. Functional dependencies are expected. The purpose of 3NF is to prevent inappropriate transitive dependency of non-key attributes within the same relation.

Another mistake is to normalize without preserving constraints. A decomposition that loses important relationships or permits invalid foreign-key references is not a sound production design merely because the tables look smaller.

---

## Performance Considerations

Normalization reduces redundancy but can increase the number of joins required for read-heavy queries.

The normalized order view requires joins among customers, orders, order items, and products.

Indexes can reduce the cost of these joins and lookups.

The primary key on `order_items(order_id, product_id)` supports efficient access using the composite identity.

The index on `orders(customer_id)` supports customer-to-order queries.

Normalization should therefore be considered together with workload characteristics. A logically sound 3NF design may later require carefully justified denormalization for a particular performance requirement, but denormalization should be an intentional trade-off rather than a consequence of unclear dependencies.

---

## Security and Integrity Considerations

Normalization itself is not a security mechanism, but clear data ownership can support better security boundaries.

Customer attributes are centralized in `customers`, making access-control decisions around customer information easier to reason about.

Foreign keys prevent references to nonexistent entities.

Database constraints provide protection against invalid states even when an application contains a bug.

Transactions are important when multiple related changes must succeed together. The SQL demonstration updates customer data inside a transaction and uses transactional handling around intentionally invalid operations.

A production implementation should also consider authorization separately from structural integrity. A normalized schema does not automatically determine which users are allowed to modify customer, product, or order data.

---

## Debugging and Dependency Reasoning

When a normalized design appears to contain duplicated facts, identify the determinant first.

For example, if the same customer city appears in many order rows, ask:

`What determines customer_city?`

If the answer is `customer_id`, the city is a customer fact.

If the same product name appears in many order lines, ask:

`What determines product_name?`

If the answer is `product_id`, the product name belongs to the product relation.

If quantity changes from order to order for the same product, the determinant must include the order as well:

`(order_id, product_id) -> quantity`

This determinant-first approach is more reliable than deciding table boundaries based only on visual repetition.

---

## Final Normalized Structure

The final design is:

`Customers(customer_id, customer_name, customer_city)`

`Orders(order_id, order_date, customer_id)`

`Products(product_id, product_name)`

`OrderItems(order_id, product_id, quantity)`

The key relationships are:

`Orders.customer_id -> Customers.customer_id`

`OrderItems.order_id -> Orders.order_id`

`OrderItems.product_id -> Products.product_id`

The functional dependencies are distributed so that each relation stores facts associated with an appropriate determinant.

The progression is therefore:

**Repeating groups → 1NF → partial dependencies removed → 2NF → transitive dependencies removed → 3NF**

The three stages are related, but they solve different dependency problems. Understanding that distinction is the central technical objective of this normalization model.
