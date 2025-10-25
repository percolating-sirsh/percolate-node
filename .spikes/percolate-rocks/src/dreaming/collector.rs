//! Data collection for dreaming

use super::types::DreamingInput;
use crate::database::Database;
use anyhow::Result;
use chrono::{DateTime, Duration, Utc};

/// Collect data from database for dreaming analysis
pub fn collect_dreaming_data(
    db: &Database,
    lookback_hours: u32,
    start: Option<&str>,
    end: Option<&str>,
) -> Result<DreamingInput> {
    // Calculate time range
    let time_range_end = if let Some(end_str) = end {
        DateTime::parse_from_rfc3339(end_str)?.with_timezone(&Utc)
    } else {
        Utc::now()
    };

    let time_range_start = if let Some(start_str) = start {
        DateTime::parse_from_rfc3339(start_str)?.with_timezone(&Utc)
    } else {
        time_range_end - Duration::hours(lookback_hours as i64)
    };

    // TODO: Query resources created in time range
    // let resources = db.query(&format!(
    //     "SELECT * FROM resources WHERE created_at >= '{}' AND created_at <= '{}'",
    //     time_range_start.to_rfc3339(),
    //     time_range_end.to_rfc3339()
    // ))?;

    // TODO: Query sessions and messages in time range
    // let sessions = db.query(&format!(
    //     "SELECT * FROM sessions WHERE created_at >= '{}' AND created_at <= '{}'",
    //     time_range_start.to_rfc3339(),
    //     time_range_end.to_rfc3339()
    // ))?;

    // let messages = db.query(&format!(
    //     "SELECT * FROM messages WHERE created_at >= '{}' AND created_at <= '{}'",
    //     time_range_start.to_rfc3339(),
    //     time_range_end.to_rfc3339()
    // ))?;

    // Stub: Return empty data for now
    Ok(DreamingInput {
        resources: vec![],
        sessions: vec![],
        messages: vec![],
        time_range_start,
        time_range_end,
    })
}
