'use strict';

/*
 * Query processing pipeline:
 * lexical analysis -> parsing -> semantic analysis -> rewriting
 * -> physical-plan selection -> execution.
 *
 * The implementation uses an event-driven execution layer so that
 * query lifecycle events can be observed without coupling observers
 * to parsing or execution internals.
 */

const EventEmitter = require('node:events');
const { performance } = require('node:perf_hooks');

class QueryError extends Error {}
class LexicalError extends QueryError {}
class ParseError extends QueryError {}
class SemanticError extends QueryError {}

const KEYWORDS = new Set([
  'SELECT', 'FROM', 'WHERE', 'AND', 'OR',
  'ORDER', 'BY', 'ASC', 'DESC', 'LIMIT', 'AS'
]);

const OPERATORS = new Set(['=', '>', '<', '>=', '<=', '!=', '<>']);

function tokenize(sql) {
  const tokens = [];
  let i = 0;

  while (i < sql.length) {
    const ch = sql[i];

    if (/\s/.test(ch)) {
      i++;
      continue;
    }

    if (ch === "'") {
      const start = i++;
      let value = '';

      while (i < sql.length) {
        if (sql[i] === "'" && sql[i + 1] === "'") {
          value += "'";
          i += 2;
        } else if (sql[i] === "'") {
          i++;
          break;
        } else {
          value += sql[i++];
        }
      }

      if (sql[i - 1] !== "'") {
        throw new LexicalError(`Unterminated string at ${start}`);
      }

      tokens.push({ type: 'STRING', value, position: start });
      continue;
    }

    if (/[0-9]/.test(ch)) {
      const start = i;
      while (i < sql.length && /[0-9]/.test(sql[i])) i++;
      tokens.push({
        type: 'NUMBER',
        value: sql.slice(start, i),
        position: start
      });
      continue;
    }

    if (/[A-Za-z_]/.test(ch)) {
      const start = i;
      while (i < sql.length && /[A-Za-z0-9_]/.test(sql[i])) i++;

      const value = sql.slice(start, i);
      const upper = value.toUpperCase();

      tokens.push({
        type: KEYWORDS.has(upper) ? 'KEYWORD' : 'IDENTIFIER',
        value: KEYWORDS.has(upper) ? upper : value,
        position: start
      });
      continue;
    }

    const two = sql.slice(i, i + 2);
    if (OPERATORS.has(two)) {
      tokens.push({ type: 'OPERATOR', value: two, position: i });
      i += 2;
      continue;
    }

    if (OPERATORS.has(ch)) {
      tokens.push({ type: 'OPERATOR', value: ch, position: i });
      i++;
      continue;
    }

    if (',;*()'.includes(ch)) {
      tokens.push({ type: 'SYMBOL', value: ch, position: i });
      i++;
      continue;
    }

    throw new LexicalError(`Unsupported character ${ch} at ${i}`);
  }

  tokens.push({ type: 'EOF', value: '', position: sql.length });
  return tokens;
}

class Parser {
  constructor(tokens) {
    this.tokens = tokens;
    this.index = 0;
  }

  current() {
    return this.tokens[this.index];
  }

  consume() {
    return this.tokens[this.index++];
  }

  expect(value) {
    const token = this.current();
    if (token.value.toUpperCase() !== value.toUpperCase()) {
      throw new ParseError(
        `Expected ${value} at ${token.position}, found ${token.value}`
      );
    }
    return this.consume();
  }

  identifier() {
    const token = this.current();
    if (token.type !== 'IDENTIFIER') {
      throw new ParseError(
        `Expected identifier at ${token.position}`
      );
    }
    return this.consume().value;
  }

  parse() {
    this.expect('SELECT');
    const columns = this.selectList();

    this.expect('FROM');
    const table = this.identifier();

    const where = [];
    if (this.current().value === 'WHERE') {
      this.consume();
      where.push(this.condition());

      while (this.current().value === 'AND') {
        this.consume();
        where.push(this.condition());
      }
    }

    let orderBy = null;
    let direction = 'ASC';

    if (this.current().value === 'ORDER') {
      this.consume();
      this.expect('BY');
      orderBy = this.identifier();

      if (['ASC', 'DESC'].includes(this.current().value)) {
        direction = this.consume().value;
      }
    }

    let limit = null;
    if (this.current().value === 'LIMIT') {
      this.consume();
      if (this.current().type !== 'NUMBER') {
        throw new ParseError('LIMIT requires an integer');
      }
      limit = Number(this.consume().value);
    }

    if (this.current().value === ';') this.consume();

    if (this.current().type !== 'EOF') {
      throw new ParseError(
        `Unexpected token ${this.current().value}`
      );
    }

    return { columns, table, where, orderBy, direction, limit };
  }

  selectList() {
    if (this.current().value === '*') {
      this.consume();
      return [{ expression: '*' }];
    }

    const result = [];

    while (true) {
      const expression = this.identifier();
      let alias = null;

      if (this.current().value === 'AS') {
        this.consume();
        alias = this.identifier();
      }

      result.push({ expression, alias });

      if (this.current().value !== ',') break;
      this.consume();
    }

    return result;
  }

  condition() {
    const column = this.identifier();
    const operator = this.current();

    if (operator.type !== 'OPERATOR') {
      throw new ParseError('Expected comparison operator');
    }
    this.consume();

    const valueToken = this.consume();
    let value;

    if (valueToken.type === 'STRING') {
      value = valueToken.value;
    } else if (valueToken.type === 'NUMBER') {
      value = Number(valueToken.value);
    } else if (valueToken.type === 'IDENTIFIER') {
      value = valueToken.value;
    } else {
      throw new ParseError('Expected comparison value');
    }

    return {
      column,
      operator: operator.value,
      value
    };
  }
}

class Catalog {
  constructor() {
    this.tables = new Map();
  }

  register(table) {
    const name = table.name.toLowerCase();
    if (this.tables.has(name)) {
      throw new SemanticError(`Table ${table.name} already exists`);
    }
    this.tables.set(name, table);
  }

  get(name) {
    const table = this.tables.get(name.toLowerCase());
    if (!table) throw new SemanticError(`Unknown table: ${name}`);
    return table;
  }
}

class QueryEngine extends EventEmitter {
  constructor(catalog) {
    super();
    this.catalog = catalog;
  }

  analyze(query) {
    const table = this.catalog.get(query.table);
    const columns = new Set(table.columns);

    for (const item of query.columns) {
      if (item.expression !== '*' && !columns.has(item.expression)) {
        throw new SemanticError(`Unknown column: ${item.expression}`);
      }
    }

    for (const condition of query.where) {
      if (!columns.has(condition.column)) {
        throw new SemanticError(
          `Unknown WHERE column: ${condition.column}`
        );
      }
    }

    if (query.orderBy && !columns.has(query.orderBy)) {
      throw new SemanticError(`Unknown ORDER BY column: ${query.orderBy}`);
    }

    if (query.limit !== null && query.limit < 0) {
      throw new SemanticError('LIMIT cannot be negative');
    }
  }

  rewrite(query) {
    const predicates = query.where.filter(
      condition => !(condition.operator === '=' &&
        condition.column === 'id' &&
        condition.value === '')
    );

    return { ...query, where: predicates };
  }

  choosePlan(query) {
    const operations = [`SCAN ${query.table}`];

    if (query.where.length) {
      operations.push(
        `FILTER ${query.where.map(c =>
          `${c.column} ${c.operator} ${JSON.stringify(c.value)}`
        ).join(' AND ')}`
      );
    }

    if (query.orderBy) {
      operations.push(`SORT ${query.orderBy} ${query.direction}`);
    }

    if (query.limit !== null) {
      operations.push(`LIMIT ${query.limit}`);
    }

    operations.push(
      `PROJECT ${query.columns.map(c =>
        c.alias ? `${c.expression} AS ${c.alias}` : c.expression
      ).join(', ')}`
    );

    return operations;
  }

  compare(left, operator, right) {
    switch (operator) {
      case '=': return left === right;
      case '!=':
      case '<>': return left !== right;
      case '>': return left > right;
      case '<': return left < right;
      case '>=': return left >= right;
      case '<=': return left <= right;
      default: throw new QueryError(`Unsupported operator ${operator}`);
    }
  }

  async execute(query) {
    this.emit('executionStarted', query);

    let rows = [...this.catalog.get(query.table).rows];

    for (const condition of query.where) {
      rows = rows.filter(row =>
        this.compare(
          row[condition.column],
          condition.operator,
          condition.value
        )
      );
    }

    if (query.orderBy) {
      const factor = query.direction === 'DESC' ? -1 : 1;
      rows.sort((a, b) => {
        if (a[query.orderBy] < b[query.orderBy]) return -1 * factor;
        if (a[query.orderBy] > b[query.orderBy]) return 1 * factor;
        return 0;
      });
    }

    if (query.limit !== null) {
      rows = rows.slice(0, query.limit);
    }

    if (query.columns.length === 1 &&
        query.columns[0].expression === '*') {
      this.emit('executionCompleted', rows);
      return rows;
    }

    const projected = rows.map(row => {
      const result = {};
      for (const column of query.columns) {
        result[column.alias || column.expression] =
          row[column.expression];
      }
      return result;
    });

    this.emit('executionCompleted', projected);
    return projected;
  }

  async process(sql) {
    this.emit('queryReceived', sql);

    const tokens = tokenize(sql);
    const parsed = new Parser(tokens).parse();

    this.emit('parsed', parsed);
    this.analyze(parsed);

    const rewritten = this.rewrite(parsed);
    this.emit('rewritten', rewritten);

    const plan = this.choosePlan(rewritten);
    this.emit('planned', plan);

    return this.execute(rewritten);
  }
}

function buildCatalog() {
  const catalog = new Catalog();

  catalog.register({
    name: 'orders',
    columns: ['id', 'customer', 'region', 'amount', 'status'],
    rows: [
      { id: 1, customer: 'Asha', region: 'North', amount: 7400, status: 'PAID' },
      { id: 2, customer: 'Ravi', region: 'South', amount: 2800, status: 'PENDING' },
      { id: 3, customer: 'Meera', region: 'North', amount: 9100, status: 'PAID' },
      { id: 4, customer: 'Kabir', region: 'West', amount: 6500, status: 'CANCELLED' },
      { id: 5, customer: 'Nisha', region: 'North', amount: 11200, status: 'PAID' }
    ]
  });

  return catalog;
}

async function main() {
  const engine = new QueryEngine(buildCatalog());

  engine.on('queryReceived', sql => console.log(`QUERY: ${sql}`));
  engine.on('planned', plan =>
    console.log(`PLAN: ${plan.join(' -> ')}`)
  );
  engine.on('executionCompleted', rows =>
    console.log(`ROWS: ${rows.length}`)
  );

  const queries = [
    "SELECT customer, amount FROM orders WHERE region = 'North' ORDER BY amount DESC LIMIT 2",
    "SELECT customer AS buyer, status FROM orders WHERE amount >= 7000",
  ];

  for (const sql of queries) {
    try {
      const result = await engine.process(sql);
      console.table(result);
    } catch (error) {
      console.error(`Query failed: ${error.message}`);
    }
  }

  try {
    await engine.process('SELECT unknown FROM orders');
  } catch (error) {
    console.error(`Expected semantic failure: ${error.message}`);
  }

  const benchmarkQuery =
    "SELECT customer, amount FROM orders WHERE amount >= 7000";

  const start = performance.now();
  for (let i = 0; i < 1000; i++) {
    await engine.process(benchmarkQuery);
  }
  const elapsed = performance.now() - start;

  console.log(`1000 processing cycles: ${elapsed.toFixed(3)} ms`);
}

main().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
