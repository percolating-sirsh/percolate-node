"""REM Database - RocksDB + Vectors + Predicates + SQL."""

from .database import REMDatabase
from .models import Agent, Direction, Edge, Entity, Message, Moment, Order, Resource, Session, SystemFields
from .predicates import (
    All,
    And,
    Contains,
    EndsWith,
    Eq,
    Exists,
    Gt,
    Gte,
    In,
    Lt,
    Lte,
    Ne,
    Not,
    NotExists,
    NotIn,
    Or,
    Predicate,
    Query,
    StartsWith,
)
from .schema import MCPTool, Schema
from .sql import SQLParser, SelectQuery
from .graph import GraphEdge, GraphTraversal, TraversalPath, TraversalStrategy

__all__ = [
    # Database
    "REMDatabase",
    # Models
    "SystemFields",
    "Resource",
    "Entity",
    "Agent",
    "Session",
    "Message",
    "Edge",
    "Moment",
    "Direction",
    "Order",
    # Query
    "Query",
    "Predicate",
    "Eq",
    "Ne",
    "Gt",
    "Gte",
    "Lt",
    "Lte",
    "In",
    "NotIn",
    "Contains",
    "StartsWith",
    "EndsWith",
    "And",
    "Or",
    "Not",
    "Exists",
    "NotExists",
    "All",
    # Schema
    "Schema",
    "MCPTool",
    # SQL
    "SQLParser",
    "SelectQuery",
    # Graph
    "GraphTraversal",
    "GraphEdge",
    "TraversalPath",
    "TraversalStrategy",
]
