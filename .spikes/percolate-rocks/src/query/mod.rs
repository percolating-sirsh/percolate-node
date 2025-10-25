//! SQL query parsing and execution.
//!
//! Provides native SQL execution 5-10x faster than Python.

pub mod parser;
pub mod executor;
pub mod predicates;
pub mod planner;
