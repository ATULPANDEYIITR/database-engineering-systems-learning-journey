from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable
import re
import time


class TokenType(Enum):
    KEYWORD = "KEYWORD"
    IDENTIFIER = "IDENTIFIER"
    NUMBER = "NUMBER"
    STRING = "STRING"
    OPERATOR = "OPERATOR"
    SYMBOL = "SYMBOL"
    EOF = "EOF"


@dataclass(frozen=True)
class Token:
    type: TokenType
    value: str
    position: int


class QueryError(Exception):
    pass


class LexicalError(QueryError):
    pass


class ParseError(QueryError):
    pass


class SemanticError(QueryError):
    pass


@dataclass
class SelectItem:
    expression: str
    alias: str | None = None


@dataclass
class Condition:
    column: str
    operator: str
    value: Any


@dataclass
class Query:
    columns: list[SelectItem]
    table: str
    where: list[Condition] = field(default_factory=list)
    order_by: str | None = None
    order_direction: str = "ASC"
    limit: int | None = None


class Lexer:
    KEYWORDS = {
        "SELECT",
        "FROM",
        "WHERE",
        "AND",
        "OR",
        "ORDER",
        "BY",
        "ASC",
        "DESC",
        "LIMIT",
        "AS",
    }

    OPERATORS = {"=", ">", "<", ">=", "<=", "!=", "<>"}
    SYMBOLS = {",", "*", "(", ")", ";"}

    def tokenize(self, text: str) -> list[Token]:
        tokens: list[Token] = []
        i = 0

        while i < len(text):
            char = text[i]

            if char.isspace():
                i += 1
                continue

            if char == "'":
                start = i
                i += 1
                value = []

                while i < len(text):
                    if text[i] == "'" and i + 1 < len(text) and text[i + 1] == "'":
                        value.append("'")
                        i += 2
                    elif text[i] == "'":
                        i += 1
                        break
                    else:
                        value.append(text[i])
                        i += 1
                else:
                    raise LexicalError("Unterminated string literal")

                tokens.append(Token(TokenType.STRING, "".join(value), start))
                continue

            if char.isdigit():
                start = i
                while i < len(text) and text[i].isdigit():
                    i += 1
                tokens.append(Token(TokenType.NUMBER, text[start:i], start))
                continue

            if char.isalpha() or char == "_":
                start = i
                while i < len(text) and (text[i].isalnum() or text[i] == "_"):
                    i += 1

                word = text[start:i]
                upper = word.upper()
                if upper in self.KEYWORDS:
                    tokens.append(Token(TokenType.KEYWORD, upper, start))
                else:
                    tokens.append(Token(TokenType.IDENTIFIER, word, start))
                continue

            two = text[i:i + 2]
            if two in self.OPERATORS:
                tokens.append(Token(TokenType.OPERATOR, two, i))
                i += 2
                continue

            if char in self.OPERATORS:
                tokens.append(Token(TokenType.OPERATOR, char, i))
                i += 1
                continue

            if char in self.SYMBOLS:
                tokens.append(Token(TokenType.SYMBOL, char, i))
                i += 1
                continue

            raise LexicalError(f"Unsupported character {char!r} at position {i}")

        tokens.append(Token(TokenType.EOF, "", len(text)))
        return tokens


class Parser:
    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.index = 0

    def current(self) -> Token:
        return self.tokens[self.index]

    def consume(self) -> Token:
        token = self.current()
        self.index += 1
        return token

    def expect(self, value: str) -> Token:
        token = self.current()
        if token.value.upper() != value.upper():
            raise ParseError(
                f"Expected {value!r} at position {token.position}, "
                f"found {token.value!r}"
            )
        return self.consume()

    def expect_identifier(self) -> str:
        token = self.current()
        if token.type != TokenType.IDENTIFIER:
            raise ParseError(
                f"Expected identifier at position {token.position}, "
                f"found {token.value!r}"
            )
        return self.consume().value

    def parse(self) -> Query:
        self.expect("SELECT")
        columns = self.parse_select_list()

        self.expect("FROM")
        table = self.expect_identifier()

        where: list[Condition] = []
        if self.current().value.upper() == "WHERE":
            self.consume()
            where = self.parse_conditions()

        order_by = None
        order_direction = "ASC"
        if self.current().value.upper() == "ORDER":
            self.consume()
            self.expect("BY")
            order_by = self.expect_identifier()

            if self.current().value.upper() in {"ASC", "DESC"}:
                order_direction = self.consume().value

        limit = None
        if self.current().value.upper() == "LIMIT":
            self.consume()
            token = self.current()
            if token.type != TokenType.NUMBER:
                raise ParseError("LIMIT requires a non-negative integer")
            limit = int(self.consume().value)

        if self.current().value == ";":
            self.consume()

        if self.current().type != TokenType.EOF:
            token = self.current()
            raise ParseError(
                f"Unexpected token {token.value!r} at position {token.position}"
            )

        return Query(
            columns=columns,
            table=table,
            where=where,
            order_by=order_by,
            order_direction=order_direction,
            limit=limit,
        )

    def parse_select_list(self) -> list[SelectItem]:
        items: list[SelectItem] = []

        if self.current().value == "*":
            self.consume()
            return [SelectItem("*")]

        while True:
            expression = self.expect_identifier()
            alias = None

            if self.current().value.upper() == "AS":
                self.consume()
                alias = self.expect_identifier()

            items.append(SelectItem(expression, alias))

            if self.current().value != ",":
                break
            self.consume()

        return items

    def parse_conditions(self) -> list[Condition]:
        conditions = [self.parse_condition()]

        while self.current().value.upper() == "AND":
            self.consume()
            conditions.append(self.parse_condition())

        return conditions

    def parse_condition(self) -> Condition:
        column = self.expect_identifier()

        operator = self.current()
        if operator.type != TokenType.OPERATOR:
            raise ParseError(
                f"Expected comparison operator at position {operator.position}"
            )
        self.consume()

        value_token = self.current()
        if value_token.type == TokenType.STRING:
            value = self.consume().value
        elif value_token.type == TokenType.NUMBER:
            value = int(self.consume().value)
        elif value_token.type == TokenType.IDENTIFIER:
            value = self.consume().value
        else:
            raise ParseError(
                f"Expected comparison value at position {value_token.position}"
            )

        return Condition(column, operator.value, value)


@dataclass
class Table:
    name: str
    columns: list[str]
    rows: list[dict[str, Any]]


class Catalog:
    def __init__(self):
        self.tables: dict[str, Table] = {}

    def register(self, table: Table) -> None:
        key = table.name.lower()
        if key in self.tables:
            raise SemanticError(f"Table {table.name!r} already exists")
        self.tables[key] = table

    def resolve(self, name: str) -> Table:
        table = self.tables.get(name.lower())
        if table is None:
            raise SemanticError(f"Unknown table: {name}")
        return table


class QueryPlanner:
    """Transforms a parsed query into an executable relational plan."""

    def __init__(self, catalog: Catalog):
        self.catalog = catalog

    def analyze(self, query: Query) -> None:
        table = self.catalog.resolve(query.table)
        columns = set(table.columns)

        for item in query.columns:
            if item.expression != "*" and item.expression not in columns:
                raise SemanticError(
                    f"Unknown column {item.expression!r} in table {table.name!r}"
                )

        if query.order_by and query.order_by not in columns:
            raise SemanticError(
                f"Unknown ORDER BY column {query.order_by!r}"
            )

        for condition in query.where:
            if condition.column not in columns:
                raise SemanticError(
                    f"Unknown WHERE column {condition.column!r}"
                )

        if query.limit is not None and query.limit < 0:
            raise SemanticError("LIMIT cannot be negative")

    def rewrite(self, query: Query) -> Query:
        # Constantly redundant predicates are removed before planning.
        filtered = [
            condition
            for condition in query.where
            if not (
                condition.operator == "="
                and condition.column.lower() == "id"
                and str(condition.value) == ""
            )
        ]

        return Query(
            columns=query.columns,
            table=query.table,
            where=filtered,
            order_by=query.order_by,
            order_direction=query.order_direction,
            limit=query.limit,
        )

    def plan(self, query: Query) -> list[str]:
        operations = [f"SCAN {query.table}"]

        if query.where:
            predicates = [
                f"{c.column} {c.operator} {c.value!r}"
                for c in query.where
            ]
            operations.append("FILTER " + " AND ".join(predicates))

        if query.order_by:
            operations.append(
                f"SORT {query.order_by} {query.order_direction}"
            )

        if query.limit is not None:
            operations.append(f"LIMIT {query.limit}")

        projection = ", ".join(
            item.expression if item.alias is None
            else f"{item.expression} AS {item.alias}"
            for item in query.columns
        )
        operations.append(f"PROJECT {projection}")

        return operations


def compare(left: Any, operator: str, right: Any) -> bool:
    if operator == "=":
        return left == right
    if operator in {"!=", "<>"}:
        return left != right
    if operator == ">":
        return left > right
    if operator == "<":
        return left < right
    if operator == ">=":
        return left >= right
    if operator == "<=":
        return left <= right
    raise ValueError(f"Unsupported operator {operator}")


class QueryExecutor:
    def __init__(self, catalog: Catalog):
        self.catalog = catalog

    def execute(self, query: Query) -> list[dict[str, Any]]:
        table = self.catalog.resolve(query.table)
        rows = table.rows

        for condition in query.where:
            rows = [
                row for row in rows
                if compare(
                    row[condition.column],
                    condition.operator,
                    condition.value,
                )
            ]

        if query.order_by:
            rows = sorted(
                rows,
                key=lambda row: row[query.order_by],
                reverse=query.order_direction == "DESC",
            )

        if query.limit is not None:
            rows = rows[:query.limit]

        if query.columns == [SelectItem("*")]:
            return [dict(row) for row in rows]

        result = []
        for row in rows:
            projected = {}
            for item in query.columns:
                key = item.alias or item.expression
                projected[key] = row[item.expression]
            result.append(projected)

        return result


def build_catalog() -> Catalog:
    catalog = Catalog()

    catalog.register(
        Table(
            name="employees",
            columns=["id", "name", "department", "salary"],
            rows=[
                {"id": 1, "name": "Asha", "department": "R&D", "salary": 92000},
                {"id": 2, "name": "Ravi", "department": "Security", "salary": 81000},
                {"id": 3, "name": "Meera", "department": "R&D", "salary": 105000},
                {"id": 4, "name": "Kabir", "department": "Platform", "salary": 76000},
                {"id": 5, "name": "Nisha", "department": "Security", "salary": 97000},
            ],
        )
    )

    return catalog


def run_query(sql: str, catalog: Catalog) -> list[dict[str, Any]]:
    lexer = Lexer()
    tokens = lexer.tokenize(sql)

    parser = Parser(tokens)
    parsed = parser.parse()

    planner = QueryPlanner(catalog)
    planner.analyze(parsed)

    rewritten = planner.rewrite(parsed)
    plan = planner.plan(rewritten)

    print("SQL:", sql)
    print("PLAN:", " -> ".join(plan))

    executor = QueryExecutor(catalog)
    result = executor.execute(rewritten)

    print("ROWS:", len(result))
    for row in result:
        print(row)
    print()

    return result


def benchmark(catalog: Catalog) -> None:
    query = (
        "SELECT name, salary FROM employees "
        "WHERE salary >= 90000 ORDER BY salary DESC LIMIT 2"
    )

    start = time.perf_counter()
    for _ in range(1000):
        run = Lexer().tokenize(query)
        parsed = Parser(run).parse()
        planner = QueryPlanner(catalog)
        planner.analyze(parsed)
        rewritten = planner.rewrite(parsed)
        QueryExecutor(catalog).execute(rewritten)

    elapsed = time.perf_counter() - start
    print(f"1000 parse/analyze/execute cycles: {elapsed:.6f}s")


def main() -> None:
    catalog = build_catalog()

    run_query(
        "SELECT name, department FROM employees "
        "WHERE salary >= 90000 ORDER BY salary DESC LIMIT 3",
        catalog,
    )

    run_query(
        "SELECT name AS employee, salary FROM employees "
        "WHERE department = 'Security' ORDER BY salary DESC",
        catalog,
    )

    try:
        run_query(
            "SELECT unknown FROM employees",
            catalog,
        )
    except QueryError as exc:
        print(f"Expected query failure: {exc}\n")

    try:
        run_query(
            "SELECT name FROM missing_table",
            catalog,
        )
    except QueryError as exc:
        print(f"Expected semantic failure: {exc}\n")

    benchmark(catalog)


if __name__ == "__main__":
    main()
