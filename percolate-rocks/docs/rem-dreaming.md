# REM Dreaming - Background intelligence layer

**Status:** Design complete, implementation in progress
**Date:** 2025-10-25

---

## Table of contents

1. [Overview](#overview)
2. [Core concept](#core-concept)
3. [Architecture](#architecture)
4. [Dreaming process](#dreaming-process)
5. [Schema definitions](#schema-definitions)
6. [CLI usage](#cli-usage)
7. [Implementation details](#implementation-details)
8. [Use cases](#use-cases)

---

## Overview

**REM Dreaming** is a background intelligence layer that uses LLMs to continuously analyze, classify, and connect your data. While you sleep (or work), the database "dreams" - creating summaries, ontological maps, temporal moments, and graph edges between entities.

**This is novel:** Most databases are passive storage. REM actively learns from your data in the background, creating semantic structure and temporal narratives.

### What REM Dreaming does

```text
Resources + Sessions → LLM Analysis → Moments + Summaries + Graph Edges

Input:                  Process:              Output:
- Documents             - Semantic analysis   - Temporal moments
- Audio logs            - Pattern detection   - Activity summaries
- Chat sessions         - Emotion detection   - Graph connections
- Code commits          - Topic clustering    - Ontological maps
                        - Entity extraction
```

**Key insight:** Your database doesn't just store data - it understands it.

---

## Core concept

### The REM principle (Resources-Entities-Moments)

| Layer | What it stores | Dreaming generates |
|-------|---------------|-------------------|
| **Resources** | Documents, audio logs, content chunks | Summaries, embeddings, related resources |
| **Entities** | Structured data (people, places, things) | Connections, attributes, ontological links |
| **Moments** | Temporal classifications of activity | Time periods with semantic tags and emotions |

**Dreaming bridges the layers:**
- Analyzes **resources** and **sessions** to generate **moments**
- Creates **graph edges** between related entities
- Generates **summary resources** for time periods
- Builds **ontological maps** of topics and themes

### Why this matters

**Without dreaming:**
```
User: "What was I working on last Tuesday afternoon?"
Database: [returns raw documents and chat logs]
User: [must read and synthesize manually]
```

**With dreaming:**
```
User: "What was I working on last Tuesday afternoon?"
Database: [returns moment]
"Deep work on DiskANN graph construction (2:00-5:30 PM)"
- Topics: vector search, Rust, performance optimization
- Outcome: Implemented Vamana builder, benchmarked vs HNSW
- Emotion: Focused, productive
- Related: 3 documents, 1 conversation, 2 code commits
```

**The database tells a story about your data.**

---

## Architecture

### System diagram

```text
┌─────────────────────────────────────────────────────────┐
│                    User Activity                         │
│  - Create documents    - Chat with agents               │
│  - Record audio logs   - Write code                     │
│  - Save notes          - Browse research                 │
└──────────────┬──────────────────────────────────────────┘
               │
               ↓ (stored in database)
┌──────────────────────────────────────────────────────────┐
│                    Core Tables                           │
│                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │  Resources   │  │   Sessions   │  │   Messages   │  │
│  │              │  │              │  │              │  │
│  │ Documents    │  │ Conversation │  │ User queries │  │
│  │ Audio logs   │  │ threads      │  │ AI responses │  │
│  │ Code files   │  │ Context      │  │ Tool calls   │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
└──────────────┬──────────────────────────────────────────┘
               │
               ↓ (trigger: cron, manual, or threshold)
┌──────────────────────────────────────────────────────────┐
│                 REM Dreaming Process                     │
│                                                          │
│  1. Query recent activity (lookback window)             │
│  2. Pass to Moment Generator agent (LLM)                │
│  3. Agent analyzes patterns, extracts semantics         │
│  4. Agent generates moments, summaries, edges           │
└──────────────┬──────────────────────────────────────────┘
               │
               ↓ (write results back to database)
┌──────────────────────────────────────────────────────────┐
│                  Generated Artifacts                     │
│                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │   Moments    │  │   Summaries  │  │  Graph Edges │  │
│  │              │  │              │  │              │  │
│  │ Time periods │  │ Period recap │  │ Related docs │  │
│  │ Activity tags│  │ Key insights │  │ Topic links  │  │
│  │ Emotions     │  │ Outcomes     │  │ Ontology     │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
└──────────────────────────────────────────────────────────┘
               │
               ↓ (user queries enriched data)
┌──────────────────────────────────────────────────────────┐
│              Enhanced User Experience                    │
│                                                          │
│  "What did I learn this week?" → Moment summaries       │
│  "Show me all Rust work" → Topic-filtered moments       │
│  "When was I most productive?" → Emotion-tagged moments │
│  "What's related to DiskANN?" → Graph traversal         │
└──────────────────────────────────────────────────────────┘
```

### Data flow

**Input collection (24 hours):**
```sql
-- Resources created in last 24 hours
SELECT * FROM resources
WHERE created_at >= NOW() - INTERVAL '24 hours'
ORDER BY created_at

-- Sessions and messages from last 24 hours
SELECT s.*,
       array_agg(m.* ORDER BY m.created_at) as messages
FROM sessions s
JOIN messages m ON m.session_id = s.id
WHERE s.created_at >= NOW() - INTERVAL '24 hours'
GROUP BY s.id
```

**LLM analysis (Moment Generator agent):**
```text
Input: Resources + Sessions + Messages
↓
Agent analyzes:
- Temporal patterns (when did topics change?)
- Semantic clustering (what topics are related?)
- Emotion detection (frustrated debugging? excited prototyping?)
- Entity extraction (people, places, tools mentioned?)
- Outcome identification (what was accomplished?)
↓
Output: Moments + Summaries + Graph Edges
```

**Output storage:**
```rust
// Insert generated moments
for moment in agent_output.moments {
    db.insert("moments", moment)?;
}

// Create graph edges
for edge in agent_output.graph_edges {
    db.add_edge(
        edge.source_id,
        edge.target_id,
        edge.edge_type,
        edge.metadata
    )?;
}

// Create summary resource
db.insert("resources", agent_output.summary_resource)?;
```

---

## Dreaming process

### Trigger modes

| Mode | When | Use case |
|------|------|----------|
| **Cron** | Every 24 hours at 3 AM | Daily recap while you sleep |
| **Manual** | `rem dream --now` | On-demand analysis |
| **Threshold** | After N resources or sessions | Real-time for heavy activity |
| **On-demand** | User query triggers dreaming | "Summarize my week" |

### Process steps

#### 1. Data collection

```rust
pub async fn collect_dreaming_data(
    db: &Database,
    lookback_hours: u32,
) -> Result<DreamingInput> {
    let cutoff = Utc::now() - Duration::hours(lookback_hours as i64);

    // Query recent resources
    let resources = db.query(&format!(
        "SELECT * FROM resources WHERE created_at >= '{}'",
        cutoff.to_rfc3339()
    ))?;

    // Query recent sessions with messages
    let sessions = db.query(&format!(
        "SELECT * FROM sessions WHERE created_at >= '{}'",
        cutoff.to_rfc3339()
    ))?;

    let messages = db.query(&format!(
        "SELECT * FROM messages WHERE created_at >= '{}'",
        cutoff.to_rfc3339()
    ))?;

    Ok(DreamingInput {
        resources,
        sessions,
        messages,
        time_range_start: cutoff,
        time_range_end: Utc::now(),
    })
}
```

#### 2. LLM invocation

```rust
pub async fn invoke_moment_generator(
    input: DreamingInput,
    llm: &LLMProvider,
) -> Result<DreamingOutput> {
    // Load Moment Generator agent schema
    let agent_schema = load_agentlet("moment-generator")?;

    // Prepare prompt with input data
    let prompt = format!(
        "Analyze the following activity and generate moments:\n\n\
         Resources: {} documents\n\
         Sessions: {} conversations\n\
         Messages: {} messages\n\
         Time range: {} to {}\n\n\
         [... full resource and session data ...]",
        input.resources.len(),
        input.sessions.len(),
        input.messages.len(),
        input.time_range_start,
        input.time_range_end
    );

    // Invoke LLM with structured output
    let response = llm.generate_structured(
        &agent_schema,
        &prompt,
        GenerateOptions {
            model: "gpt-4-turbo",
            temperature: 0.3,  // Lower for consistent analysis
            max_tokens: 4096,
        }
    ).await?;

    // Parse response into DreamingOutput
    Ok(serde_json::from_value(response)?)
}
```

#### 3. Result persistence

```rust
pub async fn persist_dreaming_results(
    db: &Database,
    output: DreamingOutput,
) -> Result<DreamingStats> {
    let mut stats = DreamingStats::default();

    // Insert moments
    for moment in output.moments {
        let moment_id = db.insert("moments", &moment)?;
        stats.moments_created += 1;

        // Create edges from moment to related resources
        for resource_id in &moment.resource_ids {
            db.add_edge(
                moment_id,
                resource_id,
                "contains",
                json!({"generated_by": "rem_dreaming"})
            )?;
            stats.edges_created += 1;
        }

        // Create edges from moment to related sessions
        for session_id in &moment.session_ids {
            db.add_edge(
                moment_id,
                session_id,
                "captured_in",
                json!({"generated_by": "rem_dreaming"})
            )?;
            stats.edges_created += 1;
        }
    }

    // Create additional graph edges (resource relationships)
    for edge in output.graph_edges {
        db.add_edge(
            &edge.source_id,
            &edge.target_id,
            &edge.edge_type,
            edge.metadata
        )?;
        stats.edges_created += 1;
    }

    // Insert summary resource if generated
    if let Some(summary) = output.summary_resource {
        db.insert("resources", &summary)?;
        stats.summaries_created += 1;
    }

    Ok(stats)
}
```

### Performance characteristics

| Operation | Time | Cost |
|-----------|------|------|
| Data collection (24h) | <1s | Free |
| LLM invocation (GPT-4) | 10-30s | ~$0.10-0.50 |
| Result persistence | <2s | Free |
| **Total** | **15-35s** | **~$0.15-0.55** |

**Cost projection:**
- Daily dreaming: ~$5-15/month
- Weekly dreaming: ~$1-3/month
- Manual dreaming: Pay per use

---

## Schema definitions

### Core tables

#### 1. Sessions

**Purpose:** Track user conversation sessions for contextual AI interactions.

**Schema:** [`schema/core/sessions.json`](../schema/core/sessions.json)

**Key fields:**
- `id` (UUID) - Session identifier
- `case_id` (UUID) - Optional link to project/case
- `user_id` (string) - User identifier
- `metadata` (object) - Session context

**Used by dreaming:**
- Groups related messages for analysis
- Provides conversational context
- Tracks user focus over time

#### 2. Messages

**Purpose:** Individual messages within sessions (user queries, AI responses, tool calls).

**Schema:** [`schema/core/messages.json`](../schema/core/messages.json)

**Key fields:**
- `session_id` (UUID) - Parent session reference
- `role` (enum) - user | assistant | system | tool
- `content` (string) - Message content (embedded)
- `tool_calls` (array) - Tool invocations
- `trace_id`, `span_id` (string) - Observability

**Used by dreaming:**
- Analyzes conversation flow and topics
- Extracts user intents and questions
- Identifies AI tool usage patterns
- Embeds content for semantic search

#### 3. Moments

**Purpose:** Temporal classifications of user activity generated by dreaming.

**Schema:** [`schema/core/moments.json`](../schema/core/moments.json)

**Key fields:**
- `name` (string) - Moment title
- `summary` (string) - Activity description
- `start_time`, `end_time` (datetime) - Time bounds
- `moment_type` (enum) - Activity type
- `tags` (array[string]) - Topic tags
- `emotion_tags` (array[string]) - Emotion/tone tags
- `people` (array[string]) - People involved
- `resource_ids`, `session_ids` (array[UUID]) - Related entities
- `metadata` (object) - Additional context

**Generated by dreaming:**
- Automatically created from resources and sessions
- Embeds summary for semantic search
- Indexed by time range for temporal queries

#### 4. Resources (existing)

**Purpose:** Document chunks with embeddings for semantic search.

**Schema:** [`schema/core/resources.json`](../schema/core/resources.json)

**Used by dreaming:**
- Source material for moment generation
- Content for summarization
- Entities to link in graph

**Dreaming generates:**
- Summary resources (type: "summary")
- Graph edges to related resources

---

## CLI usage

### Basic commands

```bash
# Run dreaming with default lookback (24 hours)
rem dream

# Custom lookback window
rem dream --lookback-hours 48

# Weekly dreaming
rem dream --lookback-hours 168

# Dry run (show what would be generated)
rem dream --dry-run

# Specify LLM provider
rem dream --llm gpt-4-turbo

# Save results to file
rem dream --output moments.json

# Verbose output
rem dream --verbose
```

### Advanced usage

```bash
# Dream for specific date range
rem dream --start "2025-10-20" --end "2025-10-25"

# Generate summary only (no moments)
rem dream --summary-only

# Custom moment types
rem dream --moment-types "work_session,learning"

# Set minimum moment duration
rem dream --min-duration-minutes 30

# Debug mode (show LLM prompts)
rem dream --debug
```

### Automated dreaming

**Cron job (Unix):**
```bash
# Daily at 3 AM
0 3 * * * cd /path/to/db && rem dream --lookback-hours 24

# Weekly on Sunday at 2 AM
0 2 * * 0 cd /path/to/db && rem dream --lookback-hours 168
```

**Systemd timer (Linux):**
```ini
# /etc/systemd/system/rem-dreaming.timer
[Unit]
Description=REM Dreaming Daily Analysis

[Timer]
OnCalendar=daily
OnCalendar=03:00
Persistent=true

[Install]
WantedBy=timers.target
```

```ini
# /etc/systemd/system/rem-dreaming.service
[Unit]
Description=REM Dreaming Analysis

[Service]
Type=oneshot
ExecStart=/usr/local/bin/rem dream --lookback-hours 24
User=myuser
WorkingDirectory=/home/myuser/.p8
```

---

## Implementation details

### Module structure

```text
src/
├── dreaming/
│   ├── mod.rs              # Public API
│   ├── collector.rs        # Data collection
│   ├── generator.rs        # LLM invocation
│   ├── persister.rs        # Result storage
│   ├── scheduler.rs        # Cron/trigger management
│   └── types.rs            # Data structures
└── bin/
    └── rem.rs              # CLI command: `rem dream`
```

### Key types

```rust
// src/dreaming/types.rs

/// Input data for dreaming process
pub struct DreamingInput {
    pub resources: Vec<Entity>,
    pub sessions: Vec<Entity>,
    pub messages: Vec<Entity>,
    pub time_range_start: DateTime<Utc>,
    pub time_range_end: DateTime<Utc>,
}

/// Output from moment generator agent
pub struct DreamingOutput {
    pub moments: Vec<Moment>,
    pub graph_edges: Vec<GraphEdge>,
    pub summary_resource: Option<Resource>,
    pub analysis_metadata: AnalysisMetadata,
}

/// Moment structure
pub struct Moment {
    pub name: String,
    pub summary: String,
    pub start_time: DateTime<Utc>,
    pub end_time: DateTime<Utc>,
    pub moment_type: MomentType,
    pub tags: Vec<String>,
    pub emotion_tags: Vec<String>,
    pub people: Vec<String>,
    pub resource_ids: Vec<Uuid>,
    pub session_ids: Vec<Uuid>,
    pub metadata: serde_json::Value,
}

/// Graph edge between entities
pub struct GraphEdge {
    pub source_id: Uuid,
    pub target_id: Uuid,
    pub edge_type: EdgeType,
    pub metadata: serde_json::Value,
}

/// Statistics from dreaming run
pub struct DreamingStats {
    pub moments_created: usize,
    pub edges_created: usize,
    pub summaries_created: usize,
    pub duration_seconds: f64,
    pub llm_tokens_used: usize,
    pub estimated_cost: f64,
}
```

### Agent-let schema

**File:** `schema/agentlets/moment-generator.json`

**Key configuration:**
- System prompt with moment generation guidelines
- Structured output schema (moments, edges, summaries)
- No MCP tools required (operates on provided data)
- Embedding enabled for agent discovery

See full schema: [`schema/agentlets/moment-generator.json`](../schema/agentlets/moment-generator.json)

---

## Use cases

### 1. Daily journal

**Problem:** Manually journaling is time-consuming and often skipped.

**Solution:** REM Dreaming generates daily summaries automatically.

```bash
# Run every night at 3 AM
rem dream --lookback-hours 24

# User queries next morning
rem query "SELECT * FROM moments WHERE DATE(start_time) = CURRENT_DATE - 1"
```

**Output:**
```
Moment: Deep work on DiskANN (9:30 AM - 12:45 PM)
- Topics: vector search, Rust, performance
- Outcome: Implemented Vamana builder
- Emotion: Focused, productive

Moment: Documentation writing (2:00 PM - 3:30 PM)
- Topics: API design, architecture docs
- Outcome: Created advanced-search.md
- Emotion: Satisfied

Moment: Team sync (4:00 PM - 4:45 PM)
- Topics: sprint planning, priority decisions
- People: Alice, Bob
- Emotion: Collaborative
```

### 2. Weekly review

**Problem:** Hard to remember what you worked on over the past week.

**Solution:** Aggregate moments for weekly patterns.

```bash
# Generate weekly moments
rem dream --lookback-hours 168

# Query week's work
rem query "SELECT * FROM moments
          WHERE start_time >= CURRENT_DATE - 7
          ORDER BY start_time"
```

**Output:**
```
Week of Oct 20-25:
- 15 hours: Deep work (DiskANN, BM25, documentation)
- 8 hours: Meetings (planning, reviews, 1:1s)
- 5 hours: Learning (read papers on graph algorithms)
- 3 hours: Debugging (performance issues in HNSW)

Key outcomes:
- Completed DiskANN implementation
- Wrote 3 major documentation files
- Resolved 2 critical bugs
```

### 3. Topic tracking

**Problem:** "When did I last work on X? What was the outcome?"

**Solution:** Semantic search over moments.

```bash
# Find all DiskANN-related moments
rem search "DiskANN implementation" --schema moments

# Or with SQL
rem query "SELECT * FROM moments WHERE 'diskann' = ANY(tags)"
```

### 4. Mood patterns

**Problem:** Hard to identify when you're most productive or what causes frustration.

**Solution:** Analyze emotion tags over time.

```bash
# Find most productive periods
rem query "SELECT * FROM moments
          WHERE 'productive' = ANY(emotion_tags)
          ORDER BY (end_time - start_time) DESC
          LIMIT 10"

# Find frustration patterns
rem query "SELECT tags, COUNT(*)
          FROM moments
          WHERE 'frustrated' = ANY(emotion_tags)
          GROUP BY tags
          ORDER BY COUNT(*) DESC"
```

**Insights:**
```
Most frustration during: debugging, infrastructure setup
Most productive during: morning deep work, documentation
Least productive during: afternoon meetings
```

### 5. Ontology building

**Problem:** Want to understand relationships between topics in your knowledge base.

**Solution:** REM Dreaming creates graph edges between related resources.

```bash
# Find all resources related to DiskANN
rem graph traverse --start-entity "diskann" --edge-type "related_to" --depth 2

# Visualize topic ontology
rem graph export --format dot --output ontology.dot
dot -Tpng ontology.dot -o ontology.png
```

**Output:** Graph showing relationships between DiskANN, HNSW, vector search, Rust, performance, etc.

---

## Future enhancements

### 1. Real-time dreaming

**Current:** Batch processing every 24 hours

**Future:** Streaming analysis as data arrives

```rust
// Watch for new resources and sessions
db.watch("resources", |resource| {
    if should_trigger_dreaming(resource) {
        tokio::spawn(async move {
            dream_incremental(resource).await
        });
    }
});
```

### 2. Multi-user collaboration moments

**Current:** Single-user moments

**Future:** Team collaboration detection

```json
{
  "name": "Team brainstorming on architecture",
  "moment_type": "collaboration",
  "people": ["Alice", "Bob", "Charlie"],
  "collaborative_insights": [
    "Converged on event-driven design",
    "Identified 3 integration points",
    "Assigned owners for each component"
  ]
}
```

### 3. Predictive moments

**Current:** Retrospective analysis

**Future:** Predict upcoming focus areas

```json
{
  "name": "Likely next: Performance optimization work",
  "moment_type": "prediction",
  "confidence": 0.75,
  "evidence": [
    "Recent benchmarking activity",
    "Performance discussions in meetings",
    "TODO items mention 'optimization'"
  ]
}
```

### 4. Custom moment types

**Current:** Fixed enum of moment types

**Future:** User-defined moment types

```bash
# Register custom moment type
rem dream register-type "exercise" --description "Physical activity sessions"

# Dreaming will now detect and classify exercise moments
```

---

## Novelty statement

**Why REM Dreaming is novel:**

1. **Active database intelligence** - Most databases are passive storage. REM actively learns and creates structure.

2. **Temporal narrative generation** - Databases don't typically "tell stories" about your data. REM generates human-readable narratives.

3. **Background LLM processing** - Using LLMs as database indexers (not just query interfaces) is a new pattern.

4. **Graph + temporal + semantic fusion** - Combines graph relationships, time-series analysis, and semantic understanding in one system.

5. **Zero-effort journaling** - Personal memory systems require manual input. REM automatically creates memory artifacts.

6. **Ontology emergence** - Knowledge graphs usually require manual curation. REM's graph edges emerge from usage patterns.

