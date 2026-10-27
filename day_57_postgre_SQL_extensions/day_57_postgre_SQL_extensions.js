'use strict';

/*
 * PostgreSQL Extensions and PostGIS Ecosystem
 *
 * Event-driven policy and spatial workflow model using Node.js standard
 * library features only. The program models extension installation events,
 * validates spatial records, performs great-circle calculations, and
 * evaluates operational policies.
 */

const EventEmitter = require('node:events');
const crypto = require('node:crypto');

const ExtensionState = Object.freeze({
    AVAILABLE: 'available',
    INSTALLED: 'installed',
    FAILED: 'failed'
});

class ExtensionManager extends EventEmitter {
    #catalog = new Map();
    #installed = new Set();

    register(extension) {
        if (!extension.name || !extension.version) {
            throw new TypeError('Extension requires a name and version');
        }

        if (this.#catalog.has(extension.name)) {
            throw new Error(`Extension already registered: ${extension.name}`);
        }

        this.#catalog.set(extension.name, {
            ...extension,
            dependencies: [...(extension.dependencies ?? [])]
        });

        this.emit('registered', extension.name);
    }

    async install(name) {
        const extension = this.#catalog.get(name);

        if (!extension) {
            throw new Error(`Unknown extension: ${name}`);
        }

        if (this.#installed.has(name)) {
            return ExtensionState.INSTALLED;
        }

        for (const dependency of extension.dependencies) {
            if (!this.#installed.has(dependency)) {
                throw new Error(
                    `Cannot install ${name}; dependency ${dependency} is not installed`
                );
            }
        }

        await new Promise(resolve => setImmediate(resolve));
        this.#installed.add(name);
        this.emit('installed', name);

        return ExtensionState.INSTALLED;
    }

    isInstalled(name) {
        return this.#installed.has(name);
    }

    list() {
        return [...this.#catalog.values()]
            .sort((a, b) => a.name.localeCompare(b.name))
            .map(extension => ({
                ...extension,
                state: this.#installed.has(extension.name)
                    ? ExtensionState.INSTALLED
                    : ExtensionState.AVAILABLE
            }));
    }
}

class GeoPoint {
    constructor(longitude, latitude) {
        if (!Number.isFinite(longitude) || !Number.isFinite(latitude)) {
            throw new TypeError('Coordinates must be finite numbers');
        }

        if (longitude < -180 || longitude > 180) {
            throw new RangeError('Longitude must be between -180 and 180');
        }

        if (latitude < -90 || latitude > 90) {
            throw new RangeError('Latitude must be between -90 and 90');
        }

        this.longitude = longitude;
        this.latitude = latitude;
        Object.freeze(this);
    }
}

class SpatialRecord {
    constructor({ id, name, type, geometry, properties = {} }) {
        if (!Number.isInteger(id) || id <= 0) {
            throw new TypeError('Spatial record id must be a positive integer');
        }

        if (!name || typeof name !== 'string') {
            throw new TypeError('Spatial record requires a name');
        }

        if (!['Point', 'LineString', 'Polygon'].includes(type)) {
            throw new TypeError(`Unsupported geometry type: ${type}`);
        }

        if (!Array.isArray(geometry) || geometry.length === 0) {
            throw new TypeError('Geometry must contain coordinates');
        }

        if (type === 'Point' && geometry.length !== 1) {
            throw new TypeError('Point requires one coordinate');
        }

        if (type === 'LineString' && geometry.length < 2) {
            throw new TypeError('LineString requires at least two coordinates');
        }

        if (type === 'Polygon') {
            if (geometry.length < 4) {
                throw new TypeError('Polygon requires at least four coordinates');
            }

            const first = geometry[0];
            const last = geometry[geometry.length - 1];

            if (
                first.longitude !== last.longitude ||
                first.latitude !== last.latitude
            ) {
                throw new TypeError('Polygon ring must be closed');
            }
        }

        this.id = id;
        this.name = name;
        this.type = type;
        this.geometry = Object.freeze([...geometry]);
        this.properties = Object.freeze({ ...properties });
        Object.freeze(this);
    }
}

function haversineKm(a, b) {
    const earthRadiusKm = 6371.0088;
    const lat1 = a.latitude * Math.PI / 180;
    const lat2 = b.latitude * Math.PI / 180;
    const deltaLat = lat2 - lat1;
    const deltaLon = (b.longitude - a.longitude) * Math.PI / 180;

    const h =
        Math.sin(deltaLat / 2) ** 2 +
        Math.cos(lat1) *
        Math.cos(lat2) *
        Math.sin(deltaLon / 2) ** 2;

    return 2 * earthRadiusKm * Math.atan2(
        Math.sqrt(Math.min(1, h)),
        Math.sqrt(Math.max(0, 1 - h))
    );
}

function nearestPoint(origin, records) {
    const candidates = records.filter(record => record.type === 'Point');

    if (candidates.length === 0) {
        throw new Error('No Point records available');
    }

    return candidates
        .map(record => ({
            record,
            distanceKm: haversineKm(origin, record.geometry[0])
        }))
        .sort((a, b) => a.distanceKm - b.distanceKm)[0];
}

function createAuditId() {
    return crypto.randomUUID();
}

async function main() {
    const manager = new ExtensionManager();

    manager.on('registered', name => {
        console.log(`registered: ${name}`);
    });

    manager.on('installed', name => {
        console.log(`installed: ${name}`);
    });

    manager.register({
        name: 'pgcrypto',
        version: '1.3',
        category: 'security'
    });

    manager.register({
        name: 'postgis',
        version: '3.x',
        category: 'spatial'
    });

    manager.register({
        name: 'postgis_raster',
        version: '3.x',
        category: 'spatial',
        dependencies: ['postgis']
    });

    manager.register({
        name: 'postgis_topology',
        version: '3.x',
        category: 'spatial',
        dependencies: ['postgis']
    });

    await manager.install('pgcrypto');
    await manager.install('postgis');

    try {
        await manager.install('postgis_raster');
        await manager.install('postgis_topology');
    } catch (error) {
        console.error(`installation failure: ${error.message}`);
    }

    console.log('\nExtension catalog:');
    console.table(manager.list());

    const facilities = [
        new SpatialRecord({
            id: 1,
            name: 'Lucknow',
            type: 'Point',
            geometry: [new GeoPoint(80.9462, 26.8467)],
            properties: { category: 'office' }
        }),
        new SpatialRecord({
            id: 2,
            name: 'Kanpur',
            type: 'Point',
            geometry: [new GeoPoint(80.3319, 26.4499)],
            properties: { category: 'depot' }
        }),
        new SpatialRecord({
            id: 3,
            name: 'Prayagraj',
            type: 'Point',
            geometry: [new GeoPoint(81.8463, 25.4358)],
            properties: { category: 'depot' }
        })
    ];

    const origin = facilities[0].geometry[0];
    const nearest = nearestPoint(origin, facilities.slice(1));

    console.log('\nSpatial query:');
    console.log({
        source: facilities[0].name,
        nearest: nearest.record.name,
        distanceKm: Number(nearest.distanceKm.toFixed(2)),
        auditId: createAuditId()
    });

    const restrictedOperations = new Set([
        'DROP EXTENSION',
        'ALTER EXTENSION',
        'CREATE EXTENSION'
    ]);

    function evaluateSqlPolicy(statement, isAdministrator) {
        const normalized = statement.trim().toUpperCase();

        for (const operation of restrictedOperations) {
            if (normalized.startsWith(operation) && !isAdministrator) {
                return {
                    allowed: false,
                    reason: `${operation} requires administrative privilege`
                };
            }
        }

        return { allowed: true, reason: 'policy accepted' };
    }

    console.log('\nSecurity policy:');
    console.table([
        evaluateSqlPolicy('CREATE EXTENSION postgis', false),
        evaluateSqlPolicy('SELECT ST_AsText(geom) FROM locations', false),
        evaluateSqlPolicy('CREATE EXTENSION postgis', true)
    ]);
}

main().catch(error => {
    console.error(`fatal error: ${error.message}`);
    process.exitCode = 1;
});
