#!/usr/bin/env python3
"""PostgreSQL JSON and JSONB modeling, querying, validation, and indexing concepts.

This executable example uses Python's standard library to simulate a document
repository and demonstrates how application-side JSON handling corresponds to
PostgreSQL JSON/JSONB operations.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Iterable


class DocumentError(ValueError):
    """Raised when a document violates the application data contract."""


@dataclass(frozen=True)
class Product:
    product_id: int
    name: str
    category: str
    price: Decimal
    attributes: dict[str, Any] = field(default_factory=dict)
    tags: tuple[str, ...] = ()


class ProductRepository:
    """An in-memory model of JSON document operations."""

    def __init__(self) -> None:
        self._products: dict[int, Product] = {}
        self._next_id = 1
        self._category_index: dict[str, set[int]] = {}
        self._attribute_index: dict[tuple[str, str], set[int]] = {}

    @staticmethod
    def _validate_attributes(attributes: Any) -> dict[str, Any]:
        if not isinstance(attributes, dict):
            raise DocumentError("attributes must be a JSON object")

        encoded = json.dumps(
            attributes,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
        )

        if len(encoded.encode("utf-8")) > 16_384:
            raise DocumentError("attributes exceed 16 KiB")

        def validate(value: Any, depth: int = 0) -> None:
            if depth > 12:
                raise DocumentError("maximum JSON nesting depth exceeded")
            if value is None or isinstance(value, (str, bool, int)):
                return
            if isinstance(value, float):
                if value != value or value in (float("inf"), float("-inf")):
                    raise DocumentError("non-finite JSON numbers are forbidden")
                return
            if isinstance(value, list):
                for item in value:
                    validate(item, depth + 1)
                return
            if isinstance(value, dict):
                for key, item in value.items():
                    if not isinstance(key, str):
                        raise DocumentError("JSON object keys must be strings")
                    validate(item, depth + 1)
                return
            raise DocumentError(f"unsupported JSON value: {type(value).__name__}")

        validate(attributes)

        # Round-trip prevents callers from retaining mutable nested references.
        return json.loads(encoded)

    @staticmethod
    def _canonical_json(value: Any) -> str:
        """Produce deterministic application-level JSON serialization."""
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )

    def add(
        self,
        name: str,
        category: str,
        price: Decimal,
        attributes: dict[str, Any],
        tags: Iterable[str] = (),
    ) -> Product:
        name = name.strip()
        category = category.strip().lower()

        if not name or len(name) > 120:
            raise DocumentError("name must contain 1 to 120 characters")
        if not re.fullmatch(r"[a-z][a-z0-9_-]{0,49}", category):
            raise DocumentError("invalid category")
        if not price.is_finite() or price < 0:
            raise DocumentError("price must be finite and non-negative")
        if price.as_tuple().exponent < -2:
            raise DocumentError("price cannot have more than two decimal places")

        safe_attributes = self._validate_attributes(attributes)
        normalized_tags = tuple(sorted({
            tag.strip().lower()
            for tag in tags
            if isinstance(tag, str) and tag.strip()
        }))

        product = Product(
            product_id=self._next_id,
            name=name,
            category=category,
            price=price,
            attributes=safe_attributes,
            tags=normalized_tags,
        )

        self._products[product.product_id] = product
        self._category_index.setdefault(category, set()).add(product.product_id)

        # This index models equality lookups for selected top-level JSON fields.
        for key, value in safe_attributes.items():
            if isinstance(value, (str, bool, int)):
                index_key = (key, self._canonical_json(value))
                self._attribute_index.setdefault(index_key, set()).add(
                    product.product_id
                )

        self._next_id += 1
        return product

    def get(self, product_id: int) -> Product | None:
        return self._products.get(product_id)

    def query_category(self, category: str) -> list[Product]:
        ids = self._category_index.get(category.strip().lower(), set())
        return [self._products[i] for i in sorted(ids)]

    def query_attribute(self, key: str, expected: Any) -> list[Product]:
        index_key = (key, self._canonical_json(expected))
        ids = self._attribute_index.get(index_key, set())
        return [self._products[i] for i in sorted(ids)]

    def contains_attributes(self, product_id: int, required: dict[str, Any]) -> bool:
        product = self.get(product_id)
        if product is None:
            return False

        # Python's recursive equality models object containment for this example.
        return self._contains(product.attributes, required)

    @classmethod
    def _contains(cls, actual: Any, expected: Any) -> bool:
        if isinstance(expected, dict):
            if not isinstance(actual, dict):
                return False
            return all(
                key in actual and cls._contains(actual[key], value)
                for key, value in expected.items()
            )

        if isinstance(expected, list):
            if not isinstance(actual, list):
                return False
            return all(
                any(cls._contains(item, candidate) for item in actual)
                for candidate in expected
            )

        return type(actual) is type(expected) and actual == expected

    def extract_path(self, product_id: int, *path: str) -> Any:
        product = self.get(product_id)
        if product is None:
            return None

        value: Any = product.attributes
        for segment in path:
            if isinstance(value, dict):
                value = value.get(segment)
            elif isinstance(value, list) and segment.isdigit():
                index = int(segment)
                value = value[index] if index < len(value) else None
            else:
                return None
        return value

    def update_attributes(
        self, product_id: int, changes: dict[str, Any]
    ) -> Product:
        """Replace attributes atomically and rebuild affected indexes."""
        current = self.get(product_id)
        if current is None:
            raise DocumentError("product does not exist")

        merged = dict(current.attributes)
        merged.update(changes)
        validated = self._validate_attributes(merged)

        # Construct the replacement before mutating repository state.
        replacement = Product(
            product_id=current.product_id,
            name=current.name,
            category=current.category,
            price=current.price,
            attributes=validated,
            tags=current.tags,
        )

        for key in current.attributes:
            if key in validated:
                old_value = current.attributes[key]
                if isinstance(old_value, (str, bool, int)):
                    index_key = (key, self._canonical_json(old_value))
                    ids = self._attribute_index.get(index_key)
                    if ids is not None:
                        ids.discard(product_id)
                        if not ids:
                            del self._attribute_index[index_key]

        for key, value in validated.items():
            if isinstance(value, (str, bool, int)):
                index_key = (key, self._canonical_json(value))
                self._attribute_index.setdefault(index_key, set()).add(product_id)

        self._products[product_id] = replacement
        return replacement

    def export_json(self, product_id: int) -> str:
        product = self.get(product_id)
        if product is None:
            raise DocumentError("product does not exist")

        document = {
            "id": product.product_id,
            "name": product.name,
            "category": product.category,
            "price": str(product.price),
            "attributes": product.attributes,
            "tags": list(product.tags),
        }
        return self._canonical_json(document)


def main() -> None:
    repository = ProductRepository()

    laptop = repository.add(
        "Engineering Laptop",
        "electronics",
        Decimal("1299.99"),
        {
            "brand": "Northstar",
            "specs": {
                "ram_gb": 32,
                "storage_gb": 1024,
                "cpu": "x86_64",
            },
            "wireless": True,
            "ports": ["USB-C", "HDMI"],
        },
        ["developer", "portable"],
    )

    monitor = repository.add(
        "Operations Monitor",
        "electronics",
        Decimal("349.50"),
        {
            "brand": "Northstar",
            "specs": {"ram_gb": 0, "storage_gb": 0},
            "wireless": False,
            "ports": ["HDMI", "DisplayPort"],
        },
        ["office"],
    )

    assert repository.extract_path(laptop.product_id, "specs", "ram_gb") == 32
    assert repository.extract_path(laptop.product_id, "missing") is None
    assert repository.contains_attributes(
        laptop.product_id, {"specs": {"ram_gb": 32}}
    )
    assert not repository.contains_attributes(
        laptop.product_id, {"specs": {"ram_gb": 64}}
    )

    print("Electronics:", [p.name for p in repository.query_category("electronics")])
    print("Wireless products:", [
        p.name for p in repository.query_attribute("wireless", True)
    ])
    print("Laptop RAM:", repository.extract_path(laptop.product_id, "specs", "ram_gb"))
    print("Laptop JSON:", repository.export_json(laptop.product_id))

    updated = repository.update_attributes(
        monitor.product_id, {"wireless": True, "warranty_years": 3}
    )
    assert updated.attributes["warranty_years"] == 3
    assert [p.name for p in repository.query_attribute("wireless", True)] == [
        laptop.name,
        monitor.name,
    ]

    try:
        repository.add(
            "Invalid Product",
            "electronics",
            Decimal("-1.00"),
            {"valid": True},
        )
    except DocumentError as error:
        print("Validation rejected invalid product:", error)

    try:
        repository.add(
            "Invalid JSON",
            "electronics",
            Decimal("10.00"),
            {"measurement": float("nan")},
        )
    except (DocumentError, ValueError) as error:
        print("Validation rejected invalid JSON:", error)

    print("All assertions passed.")


if __name__ == "__main__":
    main()
