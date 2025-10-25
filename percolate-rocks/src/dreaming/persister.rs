//! Result persistence for dreaming

use super::types::{DreamingOutput, DreamingStats};
use crate::database::Database;
use anyhow::Result;

/// Persist dreaming results to database
pub fn persist_dreaming_results(
    db: &Database,
    output: DreamingOutput,
) -> Result<DreamingStats> {
    let mut stats = DreamingStats {
        moments_created: 0,
        edges_created: 0,
        summaries_created: 0,
        duration_seconds: 0.0,
        llm_tokens_used: output.analysis_metadata.llm_tokens_used.unwrap_or(0),
        estimated_cost: output.analysis_metadata.estimated_cost.unwrap_or(0.0),
    };

    // TODO: Insert moments
    // for moment in output.moments {
    //     let moment_json = serde_json::to_value(&moment)?;
    //     let moment_id = db.insert("default", "moments", moment_json)?;
    //     stats.moments_created += 1;
    //
    //     // Create edges from moment to resources
    //     for resource_id in &moment.resource_ids {
    //         db.add_edge(
    //             moment_id,
    //             *resource_id,
    //             "contains",
    //             json!({"generated_by": "rem_dreaming"})
    //         )?;
    //         stats.edges_created += 1;
    //     }
    //
    //     // Create edges from moment to sessions
    //     for session_id in &moment.session_ids {
    //         db.add_edge(
    //             moment_id,
    //             *session_id,
    //             "captured_in",
    //             json!({"generated_by": "rem_dreaming"})
    //         )?;
    //         stats.edges_created += 1;
    //     }
    // }

    // TODO: Create graph edges
    // for edge in output.graph_edges {
    //     db.add_edge(
    //         edge.source_id,
    //         edge.target_id,
    //         &edge.edge_type.to_string(),
    //         edge.metadata
    //     )?;
    //     stats.edges_created += 1;
    // }

    // TODO: Insert summary resource
    // if let Some(summary) = output.summary_resource {
    //     let summary_json = serde_json::to_value(&summary)?;
    //     db.insert("default", "resources", summary_json)?;
    //     stats.summaries_created = 1;
    // }

    Ok(stats)
}
