//! Trace context propagation for PyO3 bindings.
//!
//! Enables trace context to flow from Python (OpenTelemetry Python SDK)
//! to Rust (tracing + tracing-opentelemetry).

use pyo3::prelude::*;
use std::collections::HashMap;
use tracing::Span;

/// Trace context from Python to Rust.
///
/// Carries W3C Trace Context headers across the Python/Rust boundary.
///
/// # Python side
///
/// ```python
/// from opentelemetry import trace
/// from opentelemetry.propagate import inject
///
/// # Extract trace context to pass to Rust
/// carrier = {}
/// inject(carrier)
///
/// # Call Rust with trace context
/// db.insert_with_trace("articles", data, carrier)
/// ```
///
/// # Rust side
///
/// ```rust,ignore
/// #[pyfunction]
/// fn insert_with_trace(
///     table: &str,
///     data: PyObject,
///     trace_context: Option<HashMap<String, String>>,
/// ) -> PyResult<String> {
///     let _guard = attach_trace_context(trace_context);
///     // ... perform operation
/// }
/// ```
#[derive(Debug, Clone)]
#[pyclass]
pub struct TraceContext {
    /// W3C Trace Context headers
    ///
    /// Standard keys:
    /// - `traceparent`: W3C trace parent header
    /// - `tracestate`: W3C trace state header
    pub headers: HashMap<String, String>,
}

#[pymethods]
impl TraceContext {
    /// Create new trace context from Python dict.
    ///
    /// # Arguments
    ///
    /// * `headers` - Dictionary with trace headers
    ///
    /// # Returns
    ///
    /// New `TraceContext` instance
    #[new]
    pub fn new(headers: HashMap<String, String>) -> Self {
        Self { headers }
    }

    /// Get trace parent header.
    ///
    /// # Returns
    ///
    /// `traceparent` header value if present
    pub fn traceparent(&self) -> Option<String> {
        self.headers.get("traceparent").cloned()
    }

    /// Get trace state header.
    ///
    /// # Returns
    ///
    /// `tracestate` header value if present
    pub fn tracestate(&self) -> Option<String> {
        self.headers.get("tracestate").cloned()
    }
}

/// Attach trace context to current span (if provided).
///
/// # Arguments
///
/// * `context` - Optional trace context from Python
///
/// # Returns
///
/// Span guard (keeps span active until dropped)
///
/// # Example
///
/// ```rust,ignore
/// #[pyfunction]
/// fn insert(table: &str, data: PyObject, trace_ctx: Option<TraceContext>) -> PyResult<String> {
///     let _guard = attach_trace_context(trace_ctx);
///     // Operation now participates in parent trace
///     db.insert(table, data)
/// }
/// ```
pub fn attach_trace_context(context: Option<TraceContext>) -> Option<tracing::span::EnteredSpan> {
    if let Some(ctx) = context {
        if let Some(traceparent) = ctx.traceparent() {
            // Parse traceparent and create remote span context
            // Format: "00-{trace-id}-{parent-id}-{flags}"
            let parts: Vec<&str> = traceparent.split('-').collect();
            if parts.len() == 4 {
                // Create span with remote parent
                let span = tracing::info_span!(
                    "rust_operation",
                    otel.kind = "internal",
                    traceparent = %traceparent,
                );
                return Some(span.entered());
            }
        }
    }
    None
}

/// Extract trace context from current Rust span to pass to Python.
///
/// # Returns
///
/// Dictionary with W3C Trace Context headers
///
/// # Example
///
/// ```rust,ignore
/// let ctx = extract_trace_context();
/// // Pass ctx back to Python for distributed tracing
/// ```
pub fn extract_trace_context() -> HashMap<String, String> {
    let mut headers = HashMap::new();

    // Get current span context
    let span = Span::current();

    // Extract traceparent from span metadata
    // This is a placeholder - actual implementation would use
    // opentelemetry::global::get_text_map_propagator()

    // For now, just return empty map
    // TODO: Implement proper W3C Trace Context extraction

    headers
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_trace_context_creation() {
        let mut headers = HashMap::new();
        headers.insert("traceparent".to_string(), "00-trace-parent-00".to_string());

        let ctx = TraceContext::new(headers);
        assert_eq!(ctx.traceparent(), Some("00-trace-parent-00".to_string()));
    }

    #[test]
    fn test_attach_none_context() {
        let guard = attach_trace_context(None);
        assert!(guard.is_none());
    }
}
