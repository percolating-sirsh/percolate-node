# Staged query planning scenarios

## Overview

Natural language questions decompose into **multi-modal query stages** that combine different search modalities:
- **Semantic search** (Resources) - Chunked, embedded data for conceptual matching
- **Entity lookup** (Entities) - Global search by identifier or named thing
- **Graph traversal** (Edges) - Relationship navigation across all entity types
- **Temporal filtering** (Moments) - Narrative construction over time
- **SQL predicates** - Structured field-based filtering

**Key insight**: Complex questions = composition of simple query primitives executed in stages.

## REM model search modalities

### Resources (semantic search)
**What**: Chunked, embedded documents ideal for semantic search
**When**: Conceptual queries, paraphrases, fuzzy matching
**Examples**:
- "Find documents about authentication"
- "Resources related to animal behavior"
- "Files discussing security vulnerabilities"

**Hybrid**: Can combine with temporal filters (e.g., "resources about Python from last month")

### Entities (global lookup)
**What**: Named things with identifiers - global search when table unknown
**When**: User provides identifier but unclear which table
**Examples**:
- "What is Bob?" (could be employee, customer, vendor)
- "Tell me about DHL" (could be carrier, company, partner)
- "Find 12345" (could be issue, PR, order, ticket)

**Why not SQL**: `SELECT * FROM company WHERE name='DHL'` requires knowing the table. Entity lookup searches all tables.

### Moments (temporal narratives)
**What**: Special resources with temporal properties - narrative construction
**When**: Time-based queries, historical tracking, event sequences
**Examples**:
- "What happened last Tuesday?"
- "Show me the timeline of the security incident"
- "Meeting notes from Q4 2024"

**Properties**: Moments are resources with additional temporal metadata and narrative structure.

### Graph edges (relationships)
**What**: Directed relationships between any entities
**When**: "Who", "what", "which" questions about connections
**Examples**:
- "Who worked on this?" → Traverse 'authored' edges
- "What does Alice manage?" → Traverse 'manages' edges
- "Which projects use Python?" → Traverse 'uses' edges

**All entities have edges**: Resources, Entities, and Moments can all have graph relationships.

## Staged query execution strategies

### Strategy 1: Semantic → Graph
**Pattern**: Find entities semantically, then explore relationships

**Example 1**: "Who worked on authentication code?"

**Stages**:
1. **Semantic search** (Resources): `SELECT * FROM resources WHERE embedding.cosine('authentication code') LIMIT 20`
   - Returns: auth.py, login.py, oauth_flow.py (resource IDs)
2. **Graph traversal**: Traverse INCOMING 'authored' edges from resource IDs
   - Returns: Alice, Bob, Charlie (entity IDs)

**LLM-driven approach**: Return resource IDs from stage 1, prompt LLM to construct graph query for stage 2.

**DB-driven approach**: Database executes both stages internally as key filters.

**Example 2**: "What animals are related to mammals?"

**Stages**:
1. **Semantic search**: Find resources matching "mammals"
   - Returns: mammal_overview.md, primate_guide.md (resource IDs)
2. **Graph traversal**: Traverse 'is_related_to' edges to find connected animal resources

---

### Strategy 2: Entity lookup → Graph
**Pattern**: Global search for named thing, then explore connections

**Example 1**: "What companies does Bob work with?"

**Stages**:
1. **Entity lookup**: `lookup_entity("Bob")`
   - Could be in employees, customers, vendors, contacts
   - Returns: Bob (employee ID)
2. **Graph traversal**: Traverse OUTGOING 'works_with' edges
   - Returns: DHL, FedEx, UPS (company entity IDs)

**Why entity lookup**: We don't know if Bob is employee, customer, or vendor upfront.

**Example 2**: "What projects is DHL involved in?"

**Stages**:
1. **Entity lookup**: `lookup_entity("DHL")`
   - Could be in carriers, companies, partners
   - Returns: DHL (company ID)
2. **Graph traversal**: Traverse 'participates_in' edges
   - Returns: Project IDs

---

### Strategy 3: SQL → Graph
**Pattern**: Filter structurally (known table), then explore connections

**Example**: "What do senior engineers work on?"

**Stages**:
1. **SQL filter**: `SELECT * FROM employees WHERE level='senior' AND role='engineer'`
   - Returns: Alice, Bob (entity IDs)
2. **Graph traversal**: Traverse OUTGOING 'works_on' edges
   - Returns: Project IDs

**Why SQL first**: We know the table (employees) and have structured criteria (level, role).

---

### Strategy 4: Semantic → Graph → SQL
**Pattern**: Semantic search → relationship navigation → structured filter

**Example**: "Which senior engineers reviewed security-related code?"

**Stages**:
1. **Semantic search**: `SELECT * FROM resources WHERE embedding.cosine('security code') LIMIT 20`
   - Returns: security.py, auth.py (resource IDs)
2. **Graph traversal**: Traverse INCOMING 'reviewed' edges
   - Returns: All reviewer IDs
3. **SQL filter**: `SELECT * FROM employees WHERE id IN (...) AND level='senior'`
   - Returns: Alice, Charlie (senior engineers who reviewed)

---

### Strategy 5: Temporal (Moments) → Graph
**Pattern**: Time-based search, then explore connections

**Example**: "Who participated in meetings last week?"

**Stages**:
1. **Temporal search**: `SELECT * FROM moments WHERE type='meeting' AND created_at >= '2024-10-17'`
   - Moments are special resources with temporal props
   - Returns: Meeting moment IDs
2. **Graph traversal**: Traverse 'participated_in' edges
   - Returns: Participant entity IDs

---

### Strategy 6: Hybrid semantic + temporal
**Pattern**: Semantic search with temporal constraints

**Example**: "Python resources from the last month"

**Stages**:
1. **Hybrid query**:
   ```sql
   SELECT * FROM resources
   WHERE embedding.cosine('Python')
   AND created_at >= '2024-09-24'
   LIMIT 10
   ```
   - Single stage combining semantic and temporal

**Alternative 2-stage**:
1. Semantic search for "Python"
2. SQL filter by date

---

## Composition patterns by modality

### Resources (semantic) + Graph
**Questions**:
- "Who wrote about X?"
- "What's related to Y topic?"
- "Which teams work on Z?"

**Pattern**: Semantic → Graph traversal

### Entities (lookup) + Graph
**Questions**:
- "What does Bob manage?"
- "Who works with DHL?"
- "What projects involve Alice?"

**Pattern**: Entity lookup → Graph traversal

### Moments (temporal) + Graph
**Questions**:
- "Who attended meetings last week?"
- "What was discussed in Q4?"
- "Timeline of the incident"

**Pattern**: Temporal filter → Graph traversal (or pure Moment query for narratives)

### SQL (structured) + Graph
**Questions**:
- "What do senior engineers work on?"
- "Which active projects have Python files?"
- "Who manages teams in Engineering?"

**Pattern**: SQL filter → Graph traversal

---

## Decision tree: Which strategy?

### Question type: "What is X?" (identifier without context)
**Use**: Entity lookup
**Example**: "What is 12345?" → `lookup_entity("12345")`

### Question type: "Find things about X" (conceptual)
**Use**: Semantic search (Resources)
**Example**: "Find resources about authentication" → Semantic search

### Question type: "Who/What/Which [relationship]?"
**Use**: Graph traversal (often multi-stage)
**Example**: "Who worked on auth?" → Semantic + Graph

### Question type: "[Structured criteria]"
**Use**: SQL (if table known)
**Example**: "Employees where level=senior" → SQL filter

### Question type: "What happened [time]?"
**Use**: Temporal (Moments)
**Example**: "What happened last Tuesday?" → Moment query

### Question type: Complex composition
**Use**: Multi-stage (2-4 stages)
**Example**: "Senior engineers who reviewed API code last month" → Semantic + Graph + SQL + Temporal

---

## Example scenarios

### Scenario 1: Software development

**Entities**: Users, Repositories, Issues, PRs, Files, Commits
**Resources**: Code files (chunked), documentation, meeting notes
**Moments**: Deployments, incidents, release events
**Edges**: authored, reviewed, fixes, modifies, participated_in

**Question 1**: "Who worked on authentication code?"
- Stage 1: Semantic search for "authentication code" → file IDs
- Stage 2: Graph traversal via 'authored' edges → user IDs
- **Modalities**: Resources (semantic) + Graph

**Question 2**: "What is TAP-1234?"
- Stage 1: Entity lookup("TAP-1234") → issue ID
- **Modalities**: Entities (lookup)

**Question 3**: "Which senior engineers reviewed security PRs last month?"
- Stage 1: Semantic search for "security" → file IDs
- Stage 2: Graph traversal via 'modifies' edges (INCOMING) → PR IDs
- Stage 3: Graph traversal via 'reviewed' edges (INCOMING) → reviewer IDs
- Stage 4: SQL filter for level='senior' AND created_at >= last month
- **Modalities**: Resources (semantic) + Graph + Graph + SQL + Temporal

**Question 4**: "What happened during the security incident?"
- Stage 1: Moment query for incident timeline
- Optional Stage 2: Graph traversal for related entities
- **Modalities**: Moments (temporal narrative)

---

### Scenario 2: Company organization

**Entities**: Companies, Departments, Teams, People, Projects, Skills
**Resources**: Documents, policies, meeting notes (chunked)
**Moments**: Org changes, promotions, project milestones
**Edges**: has_department, has_member, has_skill, works_on, reports_to

**Question 1**: "What does Bob work on?"
- Stage 1: Entity lookup("Bob") → person ID (could be employee, contractor, vendor)
- Stage 2: Graph traversal via 'works_on' edges → project IDs
- **Modalities**: Entities (lookup) + Graph

**Question 2**: "Who has Kubernetes skills in Engineering?"
- Stage 1: SQL filter for department='Engineering' → person IDs
- Stage 2: Graph traversal via 'has_skill' edges filtered by skill='Kubernetes'
- **Modalities**: SQL + Graph

**Question 3**: "Find documents about data privacy policies"
- Stage 1: Semantic search for "data privacy policies" → resource IDs
- **Modalities**: Resources (semantic only)

**Question 4**: "What organizational changes happened in Q4?"
- Stage 1: Moment query for type='org_change' AND quarter='Q4'
- **Modalities**: Moments (temporal)

---

### Scenario 3: E-commerce

**Entities**: Products, Customers, Orders, Reviews, Categories, Brands
**Resources**: Product descriptions (chunked), reviews (chunked), FAQs
**Moments**: Purchase events, returns, support interactions
**Edges**: purchased, reviewed, belongs_to_category, manufactured_by

**Question 1**: "What is order 87654?"
- Stage 1: Entity lookup("87654") → order ID (could be order, product, customer)
- **Modalities**: Entities (lookup)

**Question 2**: "Find products similar to 'wireless headphones'"
- Stage 1: Semantic search for "wireless headphones" → product resource IDs
- **Modalities**: Resources (semantic)

**Question 3**: "What did customer Alice buy last month?"
- Stage 1: Entity lookup("Alice") → customer ID
- Stage 2: Graph traversal via 'purchased' edges with temporal filter
- **Modalities**: Entities (lookup) + Graph + Temporal

**Question 4**: "Which premium customers reviewed electronics negatively?"
- Stage 1: SQL filter for tier='premium' → customer IDs
- Stage 2: Graph traversal via 'reviewed' edges → review IDs
- Stage 3: Semantic search for negative sentiment in review resources
- Stage 4: Graph traversal via 'reviewed' (INCOMING) → product IDs
- Stage 5: SQL filter for category='electronics'
- **Modalities**: SQL + Graph + Resources (semantic) + Graph + SQL

---

## LLM vs database execution

### LLM-driven staged execution
**Approach**:
1. Execute stage 1, return keys/IDs
2. Prompt LLM with results: "These are the file IDs from semantic search. Construct the next graph query."
3. LLM generates stage 2 query
4. Execute stage 2

**Pros**: Flexible, can adjust strategy mid-flight
**Cons**: Latency (LLM calls), cost

### Database-driven staged execution
**Approach**:
1. Query builder analyzes question, generates full multi-stage plan upfront
2. Database executes all stages internally as key filter sequences
3. Returns final results

**Pros**: Fast, no mid-stage LLM calls
**Cons**: Less flexible, strategy fixed upfront

### Hybrid approach
**Approach**:
1. LLM generates initial multi-stage plan
2. Database executes stages
3. If zero results, LLM generates fallback plan
4. Database executes fallback

**Pros**: Best of both worlds
**Cons**: Complexity

---

## Performance characteristics

### Single-stage queries
- **Semantic search**: 10-50ms (HNSW lookup)
- **Entity lookup**: 1-10ms (key scan)
- **SQL filter**: 5-100ms (depends on indexes)
- **Moment query**: 5-50ms (temporal index)

### Multi-stage queries
- **2 stages**: 20-150ms
- **3 stages**: 50-300ms
- **4+ stages**: 100ms-1s

### Bottlenecks
- **Graph fan-out**: Star topology = exponential growth
- **Large result sets**: 1000s of entities slow
- **Deep traversal**: 3+ hops expensive
- **LLM calls**: 500-2000ms per call

### Optimizations
- **Stage ordering**: Most selective first
- **Early filtering**: Reduce intermediate sets
- **Depth limits**: Max 3-4 hops
- **Batching**: Batch graph operations
- **Caching**: Cache intermediate results

---

## Summary

### REM search modalities
1. **Resources**: Semantic search on chunked, embedded data
2. **Entities**: Global lookup by identifier (table unknown)
3. **Moments**: Temporal narratives (special resources with time props)
4. **Graph**: Relationship traversal across all entity types
5. **SQL**: Structured filtering (table known)

### Composition principles
- Complex questions = 2-4 simple stages
- Each stage uses ONE modality
- Stages pass entity IDs as keys
- LLM or database drives stage planning
- Fallback strategies for zero results

### Strategy selection
- **"What is X?"** → Entity lookup
- **"Find about X"** → Semantic search
- **"Who/What [relationship]"** → Multi-stage (semantic/SQL + graph)
- **"[Structured]"** → SQL
- **"What happened [time]"** → Moments

### Key insight
Natural language naturally decomposes into multi-modal queries. Understanding which modality to use (Resources vs Entities vs Moments vs Graph vs SQL) is critical for correct results.
