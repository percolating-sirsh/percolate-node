"""SQL-like predicates for filtering."""

from dataclasses import dataclass
from typing import Any

import numpy as np

from .models import Entity, Order, Resource


@dataclass
class Predicate:
    """Base predicate class."""

    def evaluate(self, obj: Entity | Resource) -> bool:
        """Evaluate predicate against object."""
        raise NotImplementedError


@dataclass
class Eq(Predicate):
    """field == value"""

    field: str
    value: Any

    def evaluate(self, obj: Entity | Resource) -> bool:
        val = self._get_field(obj, self.field)
        return val == self.value

    @staticmethod
    def _get_field(obj: Entity | Resource, field: str) -> Any:
        # Check direct attributes
        if hasattr(obj, field):
            return getattr(obj, field)
        # Check properties/metadata
        if hasattr(obj, "properties") and field in obj.properties:
            return obj.properties[field]
        if hasattr(obj, "metadata") and field in obj.metadata:
            return obj.metadata[field]
        return None


@dataclass
class Ne(Predicate):
    """field != value"""

    field: str
    value: Any

    def evaluate(self, obj: Entity | Resource) -> bool:
        val = Eq._get_field(obj, self.field)
        return val != self.value


@dataclass
class Gt(Predicate):
    """field > value"""

    field: str
    value: Any

    def evaluate(self, obj: Entity | Resource) -> bool:
        val = Eq._get_field(obj, self.field)
        return val is not None and val > self.value


@dataclass
class Gte(Predicate):
    """field >= value"""

    field: str
    value: Any

    def evaluate(self, obj: Entity | Resource) -> bool:
        val = Eq._get_field(obj, self.field)
        return val is not None and val >= self.value


@dataclass
class Lt(Predicate):
    """field < value"""

    field: str
    value: Any

    def evaluate(self, obj: Entity | Resource) -> bool:
        val = Eq._get_field(obj, self.field)
        return val is not None and val < self.value


@dataclass
class Lte(Predicate):
    """field <= value"""

    field: str
    value: Any

    def evaluate(self, obj: Entity | Resource) -> bool:
        val = Eq._get_field(obj, self.field)
        return val is not None and val <= self.value


@dataclass
class In(Predicate):
    """field IN [values]"""

    field: str
    values: list[Any]

    def evaluate(self, obj: Entity | Resource) -> bool:
        val = Eq._get_field(obj, self.field)
        return val in self.values


@dataclass
class NotIn(Predicate):
    """field NOT IN [values]"""

    field: str
    values: list[Any]

    def evaluate(self, obj: Entity | Resource) -> bool:
        val = Eq._get_field(obj, self.field)
        return val not in self.values


@dataclass
class Contains(Predicate):
    """field CONTAINS substring"""

    field: str
    substring: str

    def evaluate(self, obj: Entity | Resource) -> bool:
        val = Eq._get_field(obj, self.field)
        return isinstance(val, str) and self.substring in val


@dataclass
class StartsWith(Predicate):
    """field STARTS WITH prefix"""

    field: str
    prefix: str

    def evaluate(self, obj: Entity | Resource) -> bool:
        val = Eq._get_field(obj, self.field)
        return isinstance(val, str) and val.startswith(self.prefix)


@dataclass
class EndsWith(Predicate):
    """field ENDS WITH suffix"""

    field: str
    suffix: str

    def evaluate(self, obj: Entity | Resource) -> bool:
        val = Eq._get_field(obj, self.field)
        return isinstance(val, str) and val.endswith(self.suffix)


@dataclass
class And(Predicate):
    """pred1 AND pred2 AND ..."""

    predicates: list[Predicate]

    def evaluate(self, obj: Entity | Resource) -> bool:
        return all(p.evaluate(obj) for p in self.predicates)


@dataclass
class Or(Predicate):
    """pred1 OR pred2 OR ..."""

    predicates: list[Predicate]

    def evaluate(self, obj: Entity | Resource) -> bool:
        return any(p.evaluate(obj) for p in self.predicates)


@dataclass
class Not(Predicate):
    """NOT pred"""

    predicate: Predicate

    def evaluate(self, obj: Entity | Resource) -> bool:
        return not self.predicate.evaluate(obj)


@dataclass
class Exists(Predicate):
    """field IS NOT NULL"""

    field: str

    def evaluate(self, obj: Entity | Resource) -> bool:
        return Eq._get_field(obj, self.field) is not None


@dataclass
class NotExists(Predicate):
    """field IS NULL"""

    field: str

    def evaluate(self, obj: Entity | Resource) -> bool:
        return Eq._get_field(obj, self.field) is None


@dataclass
class All(Predicate):
    """Always true"""

    def evaluate(self, obj: Entity | Resource) -> bool:
        return True


@dataclass
class Query:
    """Query builder with predicates."""

    predicate: Predicate = None
    order_by: tuple[str, Order] | None = None
    limit: int | None = None
    offset: int | None = None

    def __post_init__(self):
        if self.predicate is None:
            self.predicate = All()

    def filter(self, predicate: Predicate) -> "Query":
        """Add filter predicate."""
        if isinstance(self.predicate, All):
            self.predicate = predicate
        else:
            self.predicate = And([self.predicate, predicate])
        return self

    def sort(self, field: str, order: Order = Order.ASC) -> "Query":
        """Add sorting."""
        self.order_by = (field, order)
        return self

    def take(self, n: int) -> "Query":
        """Limit results."""
        self.limit = n
        return self

    def skip(self, n: int) -> "Query":
        """Skip results."""
        self.offset = n
        return self
