//! REM Dreaming - Background intelligence layer
//!
//! Uses LLMs to analyze user activity and generate:
//! - Moments: Temporal classifications with emotions, topics, outcomes
//! - Summaries: Period recaps and key insights
//! - Graph edges: Connections between related resources and sessions
//! - Ontological maps: Topic relationships

pub mod types;
pub mod collector;
pub mod generator;
pub mod persister;

pub use types::*;

use std::path::PathBuf;
use anyhow::Result;

/// Run the REM Dreaming process
///
/// # Arguments
///
/// * `db_path` - Path to database
/// * `lookback_hours` - Hours to look back for analysis
/// * `start` - Optional start date (ISO 8601)
/// * `end` - Optional end date (ISO 8601)
/// * `llm` - LLM model to use
/// * `dry_run` - If true, show what would be generated without writing
/// * `summary_only` - Skip moment generation, only create summaries
/// * `min_duration_minutes` - Minimum moment duration filter
/// * `debug` - Show LLM prompts and intermediate steps
///
/// # Returns
///
/// Statistics about the dreaming run
pub fn run_dreaming(
    db_path: &PathBuf,
    lookback_hours: u32,
    start: Option<&str>,
    end: Option<&str>,
    llm: &str,
    dry_run: bool,
    summary_only: bool,
    min_duration_minutes: Option<u32>,
    debug: bool,
) -> Result<DreamingStats> {
    use crate::database::Database;
    use std::time::Instant;

    let start_time = Instant::now();

    if debug {
        println!("[DEBUG] Opening database: {}", db_path.display());
    }

    let db = Database::open(db_path)?;

    // Step 1: Collect data from database
    if debug {
        println!("[DEBUG] Step 1: Collecting data...");
    }

    let input = collector::collect_dreaming_data(
        &db,
        lookback_hours,
        start,
        end,
    )?;

    if debug {
        println!("[DEBUG] Collected:");
        println!("  - {} resources", input.resources.len());
        println!("  - {} sessions", input.sessions.len());
        println!("  - {} messages", input.messages.len());
        println!("  - Time range: {} to {}", input.time_range_start, input.time_range_end);
    }

    // Step 2: Invoke LLM (Moment Generator agent)
    if debug {
        println!("[DEBUG] Step 2: Invoking LLM ({})...", llm);
    }

    let output = generator::invoke_moment_generator(
        &input,
        llm,
        summary_only,
        min_duration_minutes,
        debug,
    )?;

    if debug {
        println!("[DEBUG] Generated:");
        println!("  - {} moments", output.moments.len());
        println!("  - {} graph edges", output.graph_edges.len());
        println!("  - {} summaries", if output.summary_resource.is_some() { 1 } else { 0 });
    }

    // Step 3: Persist results (unless dry run)
    let stats = if dry_run {
        if debug {
            println!("[DEBUG] Step 3: Dry run - skipping persistence");
        }

        println!("Dry run - results not persisted:");
        println!();
        for moment in &output.moments {
            println!("Moment: {}", moment.name);
            println!("  Type: {:?}", moment.moment_type);
            println!("  Time: {} to {}", moment.start_time, moment.end_time);
            println!("  Tags: {:?}", moment.tags);
            if !moment.emotion_tags.is_empty() {
                println!("  Emotions: {:?}", moment.emotion_tags);
            }
            println!("  Summary: {}", moment.summary);
            println!();
        }

        DreamingStats {
            moments_created: output.moments.len(),
            edges_created: output.graph_edges.len(),
            summaries_created: if output.summary_resource.is_some() { 1 } else { 0 },
            duration_seconds: start_time.elapsed().as_secs_f64(),
            llm_tokens_used: output.analysis_metadata.llm_tokens_used.unwrap_or(0),
            estimated_cost: output.analysis_metadata.estimated_cost.unwrap_or(0.0),
        }
    } else {
        if debug {
            println!("[DEBUG] Step 3: Persisting results...");
        }

        let mut stats = persister::persist_dreaming_results(&db, output)?;

        stats.duration_seconds = start_time.elapsed().as_secs_f64();

        stats
    };

    Ok(stats)
}
