# Percolate Spikes

This directory contains **experimental prototypes and proof-of-concept code** for testing architectural decisions before integrating into the main codebase.

## What is a Spike?

A spike is a time-boxed research or prototype project to:
- Answer a specific technical question
- Test an architectural approach
- Prove a concept works before full implementation
- Find the cleanest solution through iteration

**Spikes are NOT production code.** They can be messy, contain dead ends, and incomplete features. The goal is learning and validation, not shipping.

## Active Spikes

### 1. rem-db - REM Database Implementation

**Goal:** Build a fast, usable RocksDB-based REM (Resources-Entities-Moments) database with:
- Vector search support (HNSW)
- SQL-like predicate queries
- Tenant isolation
- Hybrid search (semantic + metadata)

**Approach:** Python prototype first for speed of iteration, then port proven concepts to Rust.

**Status:** Active - Testing REM concepts and API ergonomics

**Location:** `.spikes/rem-db/`

### 2. platform - Multi-Tenant Platform Layer

**Goal:** Design and prototype the cloud platform infrastructure:
- Argo-based Kubernetes deployments
- Tiered tenant management (A/B/C)
- Gateway with tier-aware routing
- Management database for tenants, payments, billing
- Archival and backup services

**Approach:** K8s manifests + Python management services

**Status:** Active - Designing multi-tenant architecture

**Location:** `.spikes/platform/`

## Spike Workflow

### 1. Create a Spike

```bash
# Create spike directory
mkdir -p .spikes/my-spike
cd .spikes/my-spike

# Create README documenting the question/goal
cat > README.md << EOF
# Spike: [Name]

## Goal
What are we trying to learn or prove?

## Approach
How will we test this?

## Success Criteria
What would make this spike successful?

## Learnings
Document as you go
EOF

# Create project structure (Python, Rust, or hybrid)
uv init  # For Python spikes
# OR
cargo init  # For Rust spikes
```

### 2. Iterate and Document

- Write messy, experimental code
- Try different approaches
- Document findings in README:
  - What worked well
  - What didn't work
  - Performance observations
  - API ergonomics
  - Edge cases discovered

### 3. Extract Clean Solution

Once you've found the right approach:

1. **Document the learnings** in spike README
2. **Create design doc** in `docs/components/` with clean API
3. **Implement in main codebase** using learnings from spike
4. **Write tests** based on edge cases found in spike
5. **Archive or delete spike** (learnings captured in docs)

### 4. Archive Completed Spikes

```bash
# Move to archived-spikes/
mkdir -p .spikes/archived/
mv .spikes/my-spike .spikes/archived/my-spike-YYYYMMDD
```

## Guidelines

### DO:
- ✅ Experiment freely - try multiple approaches
- ✅ Document learnings as you go
- ✅ Write minimal tests to validate concepts
- ✅ Keep spike focused on specific question
- ✅ Time-box spike work (1-3 days typical)

### DON'T:
- ❌ Import spike code into main codebase
- ❌ Build production features in spikes
- ❌ Let spikes grow indefinitely
- ❌ Skip documentation of learnings
- ❌ Commit without clear README

## Spike Template

```markdown
# Spike: [Descriptive Name]

## Goal

[1-2 sentence description of what we're trying to learn or prove]

## Questions to Answer

- [ ] Question 1
- [ ] Question 2
- [ ] Question 3

## Approach

[How will we test this? What will we build?]

## Success Criteria

[What would make this spike successful?]

## Implementation Notes

### Attempt 1: [Description]

[What did we try?]

**Result:** [What happened?]

**Learnings:**
- Learning 1
- Learning 2

### Attempt 2: [Description]

...

## Final Recommendation

[What approach should we use in main codebase?]

## Open Questions

[What still needs investigation?]

## References

- Link to docs
- Related code
- Relevant research
```

## Current Focus

### rem-db Spike

Priority questions:
1. Can we achieve <10ms p50 for simple predicate queries?
2. How does vector search performance scale with tenant size?
3. What's the ergonomic Python API for REM operations?
4. How complex is tenant isolation at RocksDB level?
5. Can we support concurrent writes safely?

### platform Spike

Priority questions:
1. How do we route requests to tenant tiers efficiently?
2. What's the minimal management database schema?
3. How do we handle tenant migrations (tier upgrades)?
4. What metrics matter for HPA decisions?
5. How do we archive cold tenant data?

## Tips for Productive Spikes

1. **Start with the API** - Design the interface you want before implementation
2. **Use real data** - Test with realistic dataset sizes
3. **Benchmark early** - Performance surprises are better found early
4. **Document failures** - Failed approaches teach us what to avoid
5. **Keep it small** - If spike grows beyond 1000 LOC, it's not a spike anymore
6. **Share learnings** - Update team on findings, don't work in isolation

## When to Graduate a Spike

Graduate to main codebase when:
- ✅ Core questions answered
- ✅ Approach validated with working prototype
- ✅ Performance acceptable
- ✅ API ergonomics proven
- ✅ Edge cases documented
- ✅ Clear path to production implementation

## Archived Spikes

See `.spikes/archived/` for historical spikes and their learnings.
