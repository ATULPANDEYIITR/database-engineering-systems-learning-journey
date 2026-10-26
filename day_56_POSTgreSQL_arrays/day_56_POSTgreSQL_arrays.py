from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable, Sequence


class ArrayOperationError(ValueError):
    """Raised when an array operation violates domain rules."""


class Priority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class Product:
    product_id: int
    name: str
    tags: list[str] = field(default_factory=list)
    quantities: list[int] = field(default_factory=list)
    priorities: list[Priority] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.product_id <= 0:
            raise ArrayOperationError("product_id must be positive")
        if not self.name.strip():
            raise ArrayOperationError("product name cannot be empty")
        if len(self.quantities) != len(self.priorities):
            raise ArrayOperationError(
                "quantities and priorities must have equal lengths"
            )
        if any(quantity < 0 for quantity in self.quantities):
            raise ArrayOperationError("quantities cannot be negative")

        self.tags = normalize_array(self.tags)

    @property
    def total_quantity(self) -> int:
        return sum(self.quantities)

    @property
    def max_quantity(self) -> int:
        return max(self.quantities, default=0)


def normalize_array(values: Iterable[str]) -> list[str]:
    """Remove empty values and duplicates while preserving first-seen order."""
    result: list[str] = []
    seen: set[str] = set()

    for value in values:
        normalized = value.strip().lower()
        if not normalized:
            continue
        if normalized not in seen:
            seen.add(normalized)
            result.append(normalized)

    return result


def append_unique(values: Sequence[str], value: str) -> list[str]:
    result = list(values)
    normalized = value.strip().lower()

    if not normalized:
        raise ArrayOperationError("cannot append an empty array element")

    if normalized not in result:
        result.append(normalized)

    return result


def prepend(values: Sequence[str], value: str) -> list[str]:
    normalized = value.strip().lower()

    if not normalized:
        raise ArrayOperationError("cannot prepend an empty array element")

    return [normalized, *values]


def concatenate(left: Sequence[str], right: Sequence[str]) -> list[str]:
    return [*left, *right]


def array_difference(left: Sequence[str], right: Sequence[str]) -> list[str]:
    right_set = set(right)
    return [value for value in left if value not in right_set]


def intersection(left: Sequence[str], right: Sequence[str]) -> list[str]:
    right_set = set(right)
    return list(dict.fromkeys(value for value in left if value in right_set))


def contains_all(values: Sequence[str], required: Sequence[str]) -> bool:
    available = set(values)
    return all(value in available for value in required)


def contains_any(values: Sequence[str], candidates: Sequence[str]) -> bool:
    available = set(values)
    return any(value in available for value in candidates)


def positions(values: Sequence[str], target: str) -> list[int]:
    """Return PostgreSQL-style conceptual 1-based positions."""
    return [index + 1 for index, value in enumerate(values) if value == target]


def slice_array(values: Sequence[str], start: int, end: int) -> list[str]:
    """
    Use 1-based inclusive indexes to resemble PostgreSQL array slicing.
    """
    if start < 1 or end < start:
        raise ArrayOperationError("invalid 1-based slice")
    return list(values[start - 1:end])


def zip_arrays(left: Sequence[str], right: Sequence[int]) -> list[tuple[str, int]]:
    if len(left) != len(right):
        raise ArrayOperationError("arrays must have equal dimensions")
    return list(zip(left, right))


def flatten(matrix: Sequence[Sequence[int]]) -> list[int]:
    return [item for row in matrix for item in row]


def build_inventory_report(products: Sequence[Product]) -> list[dict[str, object]]:
    report: list[dict[str, object]] = []

    for product in products:
        report.append(
            {
                "product_id": product.product_id,
                "name": product.name,
                "tags": product.tags,
                "total_quantity": product.total_quantity,
                "max_quantity": product.max_quantity,
                "high_priority_count": sum(
                    priority is Priority.HIGH for priority in product.priorities
                ),
            }
        )

    return report


def main() -> None:
    product = Product(
        product_id=101,
        name="Database Server",
        tags=[" PostgreSQL ", "database", "SQL", "database", ""],
        quantities=[12, 4, 9],
        priorities=[Priority.MEDIUM, Priority.HIGH, Priority.HIGH],
    )

    print("Normalized tags:", product.tags)
    print("Append unique:", append_unique(product.tags, "array"))
    print("Prepend:", prepend(product.tags, "production"))
    print("Concatenate:", concatenate(product.tags, ["backend", "database"]))
    print("Difference:", array_difference(product.tags, ["sql", "database"]))
    print("Intersection:", intersection(product.tags, ["database", "cloud"]))
    print(
        "Contains all:",
        contains_all(product.tags, ["postgresql", "database"]),
    )
    print("Contains any:", contains_any(product.tags, ["nosql", "database"]))
    print("Positions of database:", positions(product.tags, "database"))
    print("Slice:", slice_array(product.tags, 1, 2))
    print("Zipped:", zip_arrays(product.tags[:3], product.quantities))

    matrix = [[1, 2], [3, 4], [5, 6]]
    print("Flattened:", flatten(matrix))

    products = [
        product,
        Product(
            product_id=102,
            name="API Gateway",
            tags=["network", "security", "api"],
            quantities=[20, 7],
            priorities=[Priority.LOW, Priority.HIGH],
        ),
    ]

    for row in build_inventory_report(products):
        print(row)

    # Edge cases and validation.
    try:
        Product(
            product_id=103,
            name="Invalid",
            quantities=[1],
            priorities=[],
        )
    except ArrayOperationError as exc:
        print("Validation failure:", exc)

    try:
        slice_array(["a", "b"], 0, 1)
    except ArrayOperationError as exc:
        print("Slice failure:", exc)

    # Approximate performance:
    # membership tests use a set and are O(n) to build, then O(1) average lookup.
    # Array concatenation and slicing are O(n) because a new list is created.


if __name__ == "__main__":
    main()
