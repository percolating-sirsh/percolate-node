# Research Plan: Scenario-Based Query Strategy Testing

## Research Hypothesis

**Natural language questions can be effectively decomposed into multi-stage query strategies using three primitives (semantic search, SQL, graph traversal), and these strategies can be validated through domain-specific scenarios.**

## Research Questions

1. **Pattern Discovery**: What are the most common query patterns across different domains?
2. **Complexity Mapping**: How does natural language question complexity map to strategy complexity?
3. **Performance Characteristics**: What are the performance characteristics of different query patterns?
4. **Optimization Potential**: Can query strategies be optimized automatically based on patterns?
5. **Correctness Validation**: Do multi-stage strategies produce correct results for real-world questions?

## Methodology

### 1. Scenario Generation
- Define 5-10 domain-specific scenarios (Software, Research, E-commerce, etc.)
- Each scenario includes:
  - Entity types and relationships
  - Data generation function
  - 10-20 natural language questions
  - Expected query strategies

### 2. Strategy Mapping
- For each question, define multi-stage strategy:
  - Stage type (SEMANTIC, SQL, GRAPH, HYBRID)
  - Query specification
  - Filters and constraints
  - Expected result type

### 3. Execution Framework
- Implement query executor that:
  - Executes each stage sequentially
  - Passes results between stages
  - Validates correctness
  - Measures performance

### 4. Pattern Analysis
- Identify common patterns across scenarios
- Measure pattern frequency
- Analyze complexity factors
- Document optimization opportunities

### 5. Performance Benchmarking
- Measure latency per pattern
- Identify bottlenecks
- Test optimization strategies
- Compare against baselines

## Step-by-Step Experiments

### Experiment 1: End-to-End Software Project Scenario
**Goal**: Validate that the full scenario framework works end-to-end

**Tasks**:
1. ✅ Create scenario data generator (already defined in scenarios.py)
2. ✅ Define natural language questions (4 questions defined)
3. ✅ Map questions to strategies (done)
4. ✅ Implement query executor (examples/experiment_1_software.py)
5. ✅ Generate test data
6. ✅ Execute Question 1 end-to-end
7. ✅ Validate results match expected answers
8. ⏳ Measure performance
9. ⏳ Execute remaining 3 questions

**Success Criteria**:
- ✅ Question 1 executed without errors
- ✅ Results match expected answer
- ⏳ Performance is reasonable (<2s per question)
- ⏳ All 4 questions executed

**Current Status**: ✅ **QUESTION 1 COMPLETE**

**Results** (2025-10-23):
```
Question: "Who has worked on authentication-related code?"
Strategy: Semantic Search → Graph Traversal (2 stages)

Stage 1: Semantic Search
  - Query: "authentication login OAuth security"
  - Method: Text-based filtering (Contains predicate on content)
  - Results: 4 resources found
    - Issue #1: Authentication bug in login
    - Issue #2: Add OAuth support
    - PR #1: Fix auth bug
    - PR #2: Add OAuth integration

Stage 2: Graph Traversal
  - Method: BFS reverse traversal via 'created' and 'authored' edges
  - Results: 4 contributors identified
    - Alice (created Issue #1)
    - Bob (created Issue #2)
    - Charlie (authored PR #1)
    - Eve (authored PR #2)

Final Answer: Alice, Bob, Charlie, Eve worked on authentication code

✅ Correct results
✅ Multi-stage execution successful
✅ Semantic → Graph pattern validated
```

**Key Learnings**:
1. **Resource-Entity Linking**: Storing entity_id in resource metadata works well for linking
2. **Graph Traversal API**: Must use GraphEdge objects with from_id/to_id/relationship
3. **Direction**: Reverse traversal (INCOMING edges) effective for finding contributors
4. **Text vs Vector Search**: Text-based filtering (Contains) works as semantic search proxy
5. **Stage Composition**: Two-stage strategy cleanly separates concerns

**Implementation Notes**:
- Created `examples/experiment_1_software.py` with full working implementation
- Generated 20 entities, 35 edges, 4 resources
- Used Direction.INCOMING for reverse graph traversal
- Simulated semantic search with Contains predicate (real implementation would use embeddings)

**Next**: Execute Questions 2-4 for complete scenario validation

---

### Experiment 2: Company Organization Scenario
**Goal**: Validate patterns generalize across domains

**Tasks**:
1. ✅ Define company org scenario (done)
2. ✅ Define 2 natural language questions (done)
3. ⏳ Execute questions
4. ⏳ Compare patterns to Software Project scenario
5. ⏳ Validate cross-domain pattern consistency

**Success Criteria**:
- Questions execute correctly
- Patterns match predictions (Semantic→Graph, SQL→Graph)
- Performance similar to Software Project

**Current Status**: Scenario defined, need to execute

---

### Experiment 3: Research Papers Scenario (NEW)
**Goal**: Add third scenario to strengthen pattern analysis

**Tasks**:
1. ⏳ Define Research Papers scenario
   - Entities: Papers, Authors, Institutions, Citations, Topics
   - Relationships: authored, cites, affiliated_with, tagged_with
2. ⏳ Define 10 natural language questions
   - Mix of simple (2 stage) and complex (4 stage)
   - Cover all common patterns
3. ⏳ Map questions to strategies
4. ⏳ Execute and validate

**Example Questions**:
- "Who are the most cited authors in machine learning?" (SQL + Graph)
- "What papers cite work on transformers from Stanford?" (Semantic + Graph + SQL)
- "Find recent papers by authors who collaborate with Yoshua Bengio" (SQL + Graph + Graph)

**Success Criteria**:
- 10 questions defined and executed
- Pattern distribution matches predictions
- New patterns discovered (if any)

**Current Status**: Not started

---

### Experiment 4: Performance Benchmarking
**Goal**: Measure actual performance characteristics of query patterns

**Tasks**:
1. ⏳ Implement performance measurement
   - Per-stage timing
   - Total query latency
   - Memory usage
   - Result set sizes
2. ⏳ Run benchmarks on all scenarios
3. ⏳ Analyze results by pattern type
4. ⏳ Compare to predictions in SCENARIOS.md
5. ⏳ Identify optimization opportunities

**Metrics to Collect**:
- Latency (p50, p95, p99)
- Result set size at each stage
- Memory usage
- Cache hit rates (if applicable)

**Success Criteria**:
- Performance data collected for all patterns
- Bottlenecks identified
- Optimization strategies prioritized

**Current Status**: Not started

---

### Experiment 5: Query Optimization
**Goal**: Validate that query strategies can be optimized

**Tasks**:
1. ⏳ Implement optimization strategies:
   - Stage reordering (filter early)
   - Depth limiting for graph traversal
   - Result caching between stages
   - Batch operations
2. ⏳ Measure improvement vs baseline
3. ⏳ Document optimization patterns

**Success Criteria**:
- 2-5x speedup from optimizations
- Optimization rules generalize across scenarios
- No correctness regressions

**Current Status**: Not started

---

### Experiment 6: Adaptive Query Planning
**Goal**: Explore LLM-driven dynamic query planning (carrier-inspired)

**Tasks**:
1. ⏳ Design query planner interface
2. ⏳ Implement LLM-based planner
   - Takes natural language question
   - Generates multi-stage strategy
   - Uses few-shot examples from scenarios
3. ⏳ Compare LLM-generated strategies to hand-crafted ones
4. ⏳ Measure success rate

**Success Criteria**:
- LLM generates valid strategies >80% of time
- Generated strategies match hand-crafted quality
- Can handle novel questions not in training scenarios

**Current Status**: Not started

---

## Current Focus: Experiment 1

### Implementation Plan

**Step 1**: Implement `execute_query_strategy` function in `examples/scenario_queries.py`
- Take QueryStrategy, REMDatabase, entity mapping
- Execute each stage sequentially
- Pass results between stages
- Return final results

**Step 2**: Fix entity creation API in scenario data generators
- Use correct `Entity` object format
- Ensure all edges are created properly

**Step 3**: Run Software Project scenario end-to-end
- Generate data
- Execute all 4 questions
- Print results
- Validate correctness

**Step 4**: Measure and document performance
- Add timing to each stage
- Document bottlenecks
- Update CHANGELOG.md

---

## Success Metrics

### Short Term (Experiment 1-2)
- [ ] 6 questions execute successfully (4 Software + 2 Company)
- [ ] Results match expected answers
- [ ] Pattern distribution matches predictions
- [ ] Performance <2s per question

### Medium Term (Experiment 3-4)
- [ ] 3 scenarios implemented and validated
- [ ] 20+ questions tested
- [ ] Performance characteristics documented
- [ ] Optimization opportunities identified

### Long Term (Experiment 5-6)
- [ ] 2-5x speedup from optimizations
- [ ] LLM-based query planner working
- [ ] 5+ scenarios covering diverse domains
- [ ] Comprehensive pattern library

---

## Next Steps

1. **Immediate**: Implement `execute_query_strategy` with real semantic search, SQL, and graph traversal
2. **Today**: Complete Experiment 1 (Software Project end-to-end)
3. **This Week**: Complete Experiment 2 (Company Org) and Experiment 3 (Research Papers)
4. **Next Week**: Performance benchmarking and optimization

---

## Open Questions

1. Should we implement scenario execution in Python or port to Rust for performance?
2. How do we handle semantic search without embeddings? (Mock for now, real later?)
3. Should we add temporal queries (moments) to scenarios?
4. What's the right balance between scenario diversity and depth?

---

## References

- **SCENARIOS.md**: Framework documentation
- **CHANGELOG.md**: Implementation history
- **src/rem_db/scenarios.py**: Scenario definitions
- **examples/query_strategies_demo.py**: Conceptual demonstration
- **Carrier's N-hop Planner**: Inspiration for multi-stage queries
