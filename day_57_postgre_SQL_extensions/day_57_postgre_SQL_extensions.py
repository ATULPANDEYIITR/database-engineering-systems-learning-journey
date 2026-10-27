#!/usr/bin/env python3
"""
PostgreSQL Extensions and PostGIS Ecosystem
A self-contained learning model for extension discovery, PostGIS-style
spatial workflows, validation, indexing decisions, and operational governance.

The program does not require PostgreSQL or third-party Python packages.
It models representative extension metadata and performs real geospatial
calculations using the standard library.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from math import atan2, cos, radians, sin, sqrt
from typing import Iterable


class ExtensionStatus(Enum):
    AVAILABLE = "available"
    INSTALLED = "installed"
    DISABLED = "disabled"


class GeometryType(Enum):
    POINT = "Point"
    LINESTRING = "LineString"
    POLYGON = "Polygon"


@dataclass(frozen=True)
class Extension:
    name: str
    version: str
    description: str
    category: str
    requires: tuple[str, ...] = ()
    trusted: bool = True


@dataclass(frozen=True)
class Coordinate:
    longitude: float
    latitude: float

    def validate(self) -> None:
        if not -180 <= self.longitude <= 180:
            raise ValueError(f"Invalid longitude: {self.longitude}")
        if not -90 <= self.latitude <= 90:
            raise ValueError(f"Invalid latitude: {self.latitude}")


@dataclass
class SpatialFeature:
    feature_id: int
    name: str
    geometry_type: GeometryType
    coordinates: list[Coordinate]
    properties: dict[str, str] = field(default_factory=dict)

    def validate(self) -> None:
        if not self.coordinates:
            raise ValueError("A spatial feature requires coordinates")

        for coordinate in self.coordinates:
            coordinate.validate()

        if self.geometry_type is GeometryType.POINT and len(self.coordinates) != 1:
            raise ValueError("A Point requires exactly one coordinate")

        if self.geometry_type is GeometryType.LINESTRING and len(self.coordinates) < 2:
            raise ValueError("A LineString requires at least two coordinates")

        if self.geometry_type is GeometryType.POLYGON:
            if len(self.coordinates) < 4:
                raise ValueError("A Polygon requires at least four coordinates")
            if self.coordinates[0] != self.coordinates[-1]:
                raise ValueError("A Polygon ring must be closed")


class ExtensionRegistry:
    """Small in-memory analogue of PostgreSQL extension catalog operations."""

    def __init__(self) -> None:
        self._extensions: dict[str, Extension] = {}
        self._installed: set[str] = set()

    def register(self, extension: Extension) -> None:
        if extension.name in self._extensions:
            raise ValueError(f"Extension already registered: {extension.name}")
        self._extensions[extension.name] = extension

    def install(self, name: str) -> None:
        extension = self._extensions.get(name)
        if extension is None:
            raise KeyError(f"Extension is not available: {name}")

        missing = [
            dependency
            for dependency in extension.requires
            if dependency not in self._installed
        ]
        if missing:
            raise RuntimeError(
                f"Cannot install {name}; missing dependencies: {', '.join(missing)}"
            )

        self._installed.add(name)

    def is_installed(self, name: str) -> bool:
        return name in self._installed

    def list_extensions(self) -> list[Extension]:
        return sorted(self._extensions.values(), key=lambda item: item.name)

    def installed_extensions(self) -> list[str]:
        return sorted(self._installed)


def haversine_km(a: Coordinate, b: Coordinate) -> float:
    """Calculate great-circle distance using the WGS84 mean Earth radius."""
    a.validate()
    b.validate()

    earth_radius_km = 6371.0088
    lat1 = radians(a.latitude)
    lat2 = radians(b.latitude)
    d_lat = lat2 - lat1
    d_lon = radians(b.longitude - a.longitude)

    value = (
        sin(d_lat / 2) ** 2
        + cos(lat1) * cos(lat2) * sin(d_lon / 2) ** 2
    )

    value = min(1.0, max(0.0, value))
    return 2 * earth_radius_km * atan2(sqrt(value), sqrt(1 - value))


def polygon_area_sq_km(polygon: SpatialFeature) -> float:
    """
    Approximate polygon area using an equirectangular projection.
    For production GIS work, use PostGIS ST_Area with an appropriate
    geography or projected geometry representation.
    """
    polygon.validate()

    if polygon.geometry_type is not GeometryType.POLYGON:
        raise ValueError("Area requires a polygon")

    lat0 = radians(
        sum(point.latitude for point in polygon.coordinates)
        / len(polygon.coordinates)
    )
    earth_radius_km = 6371.0088

    projected: list[tuple[float, float]] = []
    for point in polygon.coordinates:
        x = earth_radius_km * radians(point.longitude) * cos(lat0)
        y = earth_radius_km * radians(point.latitude)
        projected.append((x, y))

    area = 0.0
    for first, second in zip(projected, projected[1:]):
        area += first[0] * second[1] - second[0] * first[1]

    return abs(area) / 2


def bounding_box(features: Iterable[SpatialFeature]) -> tuple[float, float, float, float]:
    points = [
        coordinate
        for feature in features
        for coordinate in feature.coordinates
    ]

    if not points:
        raise ValueError("Cannot calculate a bounding box for no features")

    for point in points:
        point.validate()

    return (
        min(point.longitude for point in points),
        min(point.latitude for point in points),
        max(point.longitude for point in points),
        max(point.latitude for point in points),
    )


def nearest_feature(
    origin: Coordinate,
    features: Iterable[SpatialFeature],
) -> tuple[SpatialFeature, float]:
    origin.validate()

    candidates = []
    for feature in features:
        feature.validate()

        if feature.geometry_type is not GeometryType.POINT:
            raise ValueError("Nearest-point example requires Point features")

        distance = haversine_km(origin, feature.coordinates[0])
        candidates.append((distance, feature))

    if not candidates:
        raise ValueError("No candidate features supplied")

    distance, feature = min(candidates, key=lambda item: item[0])
    return feature, distance


def main() -> None:
    registry = ExtensionRegistry()

    registry.register(
        Extension(
            "uuid-ossp",
            "1.1",
            "UUID generation functions",
            "utility",
        )
    )
    registry.register(
        Extension(
            "pgcrypto",
            "1.3",
            "Cryptographic and digest functions",
            "security",
        )
    )
    registry.register(
        Extension(
            "postgis",
            "3.x",
            "Geospatial types, functions, operators, and indexes",
            "spatial",
        )
    )
    registry.register(
        Extension(
            "postgis_raster",
            "3.x",
            "Raster data support associated with PostGIS",
            "spatial",
            ("postgis",),
        )
    )
    registry.register(
        Extension(
            "postgis_topology",
            "3.x",
            "Topology-aware spatial data model",
            "spatial",
            ("postgis",),
        )
    )

    for name in ("uuid-ossp", "pgcrypto", "postgis", "postgis_raster"):
        registry.install(name)

    print("=== Extension Registry ===")
    for extension in registry.list_extensions():
        state = "installed" if registry.is_installed(extension.name) else "available"
        print(f"{extension.name:20} {extension.version:6} {state:10} {extension.category}")

    print("\n=== Spatial Features ===")

    locations = [
        SpatialFeature(
            1,
            "Lucknow Office",
            GeometryType.POINT,
            [Coordinate(80.9462, 26.8467)],
            {"type": "office"},
        ),
        SpatialFeature(
            2,
            "Kanpur Depot",
            GeometryType.POINT,
            [Coordinate(80.3319, 26.4499)],
            {"type": "depot"},
        ),
        SpatialFeature(
            3,
            "Prayagraj Depot",
            GeometryType.POINT,
            [Coordinate(81.8463, 25.4358)],
            {"type": "depot"},
        ),
    ]

    for feature in locations:
        feature.validate()
        coordinate = feature.coordinates[0]
        print(
            f"{feature.feature_id}: {feature.name} "
            f"({coordinate.longitude}, {coordinate.latitude})"
        )

    origin = Coordinate(80.9462, 26.8467)
    nearest, distance = nearest_feature(origin, locations[1:])
    print(
        f"\nNearest depot to Lucknow Office: "
        f"{nearest.name} ({distance:.2f} km)"
    )

    service_area = SpatialFeature(
        10,
        "Service Area",
        GeometryType.POLYGON,
        [
            Coordinate(80.80, 26.70),
            Coordinate(81.10, 26.70),
            Coordinate(81.10, 26.95),
            Coordinate(80.80, 26.95),
            Coordinate(80.80, 26.70),
        ],
    )
    print(f"Approximate service-area size: {polygon_area_sq_km(service_area):.2f} km²")

    print(f"Bounding box: {bounding_box(locations)}")

    print("\n=== Failure Handling ===")
    invalid = Coordinate(220, 95)
    try:
        invalid.validate()
    except ValueError as exc:
        print(f"Validation rejected invalid coordinate: {exc}")

    try:
        registry.install("postgis_topology")
    except RuntimeError as exc:
        print(f"Dependency check: {exc}")

    print("\n=== Operational Notes ===")
    print("PostGIS provides database-native spatial types, predicates, transformations,")
    print("distance calculations, spatial indexes, and topology/raster capabilities.")
    print("For large datasets, database-side spatial indexes are preferable to scanning")
    print("every feature in application memory.")


if __name__ == "__main__":
    main()
