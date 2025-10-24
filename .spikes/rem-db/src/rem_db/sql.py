"""SQL-like query interface for REM database."""

import re
from dataclasses import dataclass
from typing import Any, Optional

from .predicates import And, Eq, Gt, Gte, In, Lt, Lte, Ne, Or, Predicate


@dataclass
class SelectQuery:
    """Parsed SQL SELECT query."""

    table: str
    fields: list[str] | None = None  # None = SELECT *
    where: Optional[Predicate] = None
    order_by: Optional[tuple[str, str]] = None  # (field, "ASC" | "DESC")
    limit: Optional[int] = None
    offset: Optional[int] = None
    cosine_query: Optional[tuple[str, str, str]] = None  # (field, query_text, similarity_type) for semantic search


class SQLParser:
    """Simple SQL parser for SELECT queries.

    Supports:
    - SELECT field1, field2 FROM table
    - SELECT * FROM table
    - WHERE field = value
    - WHERE field IN (value1, value2)
    - WHERE field > value AND field2 = value2
    - ORDER BY field ASC/DESC
    - LIMIT n
    - OFFSET n
    """

    @staticmethod
    def parse(sql: str) -> SelectQuery:
        """Parse SQL SELECT query.

        Args:
            sql: SQL query string

        Returns:
            Parsed SelectQuery

        Raises:
            ValueError: If query is invalid
        """
        sql = sql.strip()

        # Extract SELECT clause (DOTALL makes . match newlines)
        select_match = re.match(r"SELECT\s+(.*?)\s+FROM\s+(\w+)", sql, re.IGNORECASE | re.DOTALL)
        if not select_match:
            raise ValueError("Invalid SELECT query - must have 'SELECT ... FROM table'")

        fields_str = select_match.group(1).strip()
        table = select_match.group(2).strip()

        # Parse fields
        if fields_str == "*":
            fields = None
        else:
            fields = [f.strip() for f in fields_str.split(",")]

        # Extract WHERE clause - check for cosine similarity first
        where_predicate = None
        cosine_query = None
        where_match = re.search(r"\bWHERE\s+(.*?)(?:\s+ORDER\s+BY|\s+LIMIT|\s+OFFSET|$)", sql, re.IGNORECASE)
        if where_match:
            where_clause = where_match.group(1).strip()

            # Check for embedding.cosine("text") or embedding.inner_product("text")
            similarity_match = re.match(
                r'(\w+)\.(cosine|inner_product)\(["\'](.+?)["\']\)', where_clause, re.IGNORECASE
            )
            if similarity_match:
                field = similarity_match.group(1)
                similarity_type = similarity_match.group(2).lower()
                query_text = similarity_match.group(3)
                cosine_query = (field, query_text, similarity_type)
            else:
                where_predicate = SQLParser._parse_where(where_clause)

        # Extract ORDER BY
        order_by = None
        order_match = re.search(r"\bORDER\s+BY\s+(\w+)(?:\s+(ASC|DESC))?", sql, re.IGNORECASE)
        if order_match:
            field = order_match.group(1)
            direction = (order_match.group(2) or "ASC").upper()
            order_by = (field, direction)

        # Extract LIMIT
        limit = None
        limit_match = re.search(r"\bLIMIT\s+(\d+)", sql, re.IGNORECASE)
        if limit_match:
            limit = int(limit_match.group(1))

        # Extract OFFSET
        offset = None
        offset_match = re.search(r"\bOFFSET\s+(\d+)", sql, re.IGNORECASE)
        if offset_match:
            offset = int(offset_match.group(1))

        return SelectQuery(
            table=table,
            fields=fields,
            where=where_predicate,
            order_by=order_by,
            limit=limit,
            offset=offset,
            cosine_query=cosine_query,
        )

    @staticmethod
    def _parse_where(clause: str) -> Predicate:
        """Parse WHERE clause into Predicate.

        Supports:
        - field = value
        - field != value
        - field > value
        - field >= value
        - field < value
        - field <= value
        - field IN (val1, val2, ...)
        - cond1 AND cond2
        - cond1 OR cond2
        - (nested conditions)
        """
        clause = clause.strip()

        # Handle parentheses first (highest precedence)
        if clause.startswith("(") and clause.endswith(")"):
            # Check if outer parens are balanced
            depth = 0
            for i, char in enumerate(clause):
                if char == "(":
                    depth += 1
                elif char == ")":
                    depth -= 1
                if depth == 0 and i < len(clause) - 1:
                    # Parens close before end, not outer parens
                    break
            else:
                # Outer parens, remove them
                return SQLParser._parse_where(clause[1:-1])

        # Split on OR/AND while respecting parentheses
        def split_respecting_parens(text: str, separator: str) -> list[str]:
            """Split text on separator, but not inside parentheses."""
            parts = []
            current = []
            depth = 0
            i = 0

            while i < len(text):
                if text[i] == "(":
                    depth += 1
                    current.append(text[i])
                    i += 1
                elif text[i] == ")":
                    depth -= 1
                    current.append(text[i])
                    i += 1
                elif depth == 0 and text[i:i+len(separator)].upper() == separator.upper():
                    # Found separator at depth 0
                    parts.append("".join(current))
                    current = []
                    i += len(separator)
                else:
                    current.append(text[i])
                    i += 1

            if current:
                parts.append("".join(current))

            return [p.strip() for p in parts if p.strip()]

        # Handle OR (lowest precedence)
        or_parts = split_respecting_parens(clause, " OR ")
        if len(or_parts) > 1:
            predicates = [SQLParser._parse_where(p) for p in or_parts]
            return Or(predicates)

        # Handle AND (higher precedence)
        and_parts = split_respecting_parens(clause, " AND ")
        if len(and_parts) > 1:
            predicates = [SQLParser._parse_where(p) for p in and_parts]
            return And(predicates)

        # Handle IN operator
        in_match = re.match(r"(\w+)\s+IN\s+\((.*?)\)", clause, re.IGNORECASE)
        if in_match:
            field = in_match.group(1)
            values_str = in_match.group(2)
            values = [SQLParser._parse_value(v.strip()) for v in values_str.split(",")]
            return In(field, values)

        # Handle comparison operators
        for op, predicate_cls in [
            (">=", Gte),
            ("<=", Lte),
            ("!=", Ne),
            ("=", Eq),
            (">", Gt),
            ("<", Lt),
        ]:
            pattern = rf"(\w+)\s*{re.escape(op)}\s*(.+)"
            match = re.match(pattern, clause)
            if match:
                field = match.group(1)
                value_str = match.group(2).strip()
                value = SQLParser._parse_value(value_str)
                return predicate_cls(field, value)

        raise ValueError(f"Unable to parse WHERE clause: {clause}")

    @staticmethod
    def _parse_value(value_str: str) -> Any:
        """Parse value from string."""
        value_str = value_str.strip()

        # String literals (single or double quotes)
        if (value_str.startswith("'") and value_str.endswith("'")) or (
            value_str.startswith('"') and value_str.endswith('"')
        ):
            return value_str[1:-1]

        # Boolean
        if value_str.upper() == "TRUE":
            return True
        if value_str.upper() == "FALSE":
            return False

        # NULL
        if value_str.upper() == "NULL":
            return None

        # Number
        try:
            if "." in value_str:
                return float(value_str)
            return int(value_str)
        except ValueError:
            pass

        # Default: treat as string
        return value_str
