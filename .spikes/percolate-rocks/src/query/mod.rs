//! SQL query parsing and execution.
//!
//! Provides native SQL execution 5-10x faster than Python.

pub mod parser;
pub mod executor;
pub mod predicates;
pub mod planner;

pub use parser::QueryParser;
pub use executor::QueryExecutor;
pub use predicates::PredicateEvaluator;
pub use planner::QueryPlanner;
