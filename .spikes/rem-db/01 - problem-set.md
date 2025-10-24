# Query Type Evaluation Problem Set

10 carefully designed questions to test the LLM query builder's ability to choose the correct query strategy.

## Query Type Definitions

### 1. entity_lookup
**When to use:** Global search when table/schema is unknown

**Indicators:**
- User provides identifier without table context (IDs, codes, names)
- Numeric IDs: "12345", "550e8400-..."
- Code patterns: "ABC-123", "TAP-1234", "SHIP-5678"
- Entity names: "DHL", "FedEx", "nShift", "Alice"
- No table specified and identifier is specific (not conceptual)

**Strategy:** Search across all entities by name, aliases, or ID fields

### 2. sql
**When to use:** Structured query with known table and field filters

**Indicators:**
- User specifies or implies table ("resources with...", "agents that...")
- Field-based filtering (equality, comparison, IN operator)
- Structured criteria (status, role, category)

**Strategy:** SQL SELECT with WHERE predicates

### 3. vector
**When to use:** Conceptual or meaning-based queries

**Indicators:**
- Semantic concepts ("about programming", "related to authentication")
- No specific field names mentioned
- Paraphrase/synonym queries
- Topic-based search

**Strategy:** Vector similarity search (cosine or inner_product)

### 4. hybrid
**When to use:** Combination of semantic search + metadata filters

**Indicators:**
- Semantic query + temporal filter ("from last week")
- Semantic query + category filter ("Python resources in tutorials category")
- Semantic query + status/state ("active agents about coding")

**Strategy:** Vector search + SQL WHERE on metadata fields

### 5. graph
**When to use:** Relationship exploration (typically multi-stage)

**Indicators:**
- Questions about relationships ("who worked on...", "what is connected to...")
- Staged queries (find X, then explore relationships)
- Traversal language ("related", "connected", "associated")

**Strategy:** Graph traversal (BFS/DFS) after initial entity identification

---

## Problem Set

### Question 1: Entity Lookup - Numeric ID

**Question:** "What is 12345?"

**Expected Type:** `entity_lookup`

**Rationale:**
- Numeric identifier without table context
- Could be issue ID, PR number, user ID, or any entity
- No way to know which table to query
- Must search globally across entities

**Expected Strategy:**
```
Search all entities where:
  - id matches or name matches "12345"
  - aliases contains "12345"
  - properties contain identifier fields matching "12345"
```

**Confidence:** 0.95-1.0 (clear identifier, uncertain table)

**Expected Results:**
- If Issue #12345 exists → return Issue entity
- If no match → return empty with suggestion to be more specific

**Test Data Needed:**
- Issue with id or properties.issue_number = "12345"
- Alternative: User with employee_id = "12345"

---

### Question 2: Entity Lookup - Code Pattern

**Question:** "Find TAP-1234"

**Expected Type:** `entity_lookup`

**Rationale:**
- Code pattern (PREFIX-NUMBER) suggests identifier
- Common in ticketing systems (Jira, support tickets)
- No table specified
- Specific identifier, not conceptual search

**Expected Strategy:**
```
Search all entities where:
  - name = "TAP-1234"
  - aliases contains "TAP-1234"
  - properties contain ticket/issue ID = "TAP-1234"
```

**Confidence:** 0.9-1.0 (clear code pattern)

**Expected Results:**
- Return ticket/issue entity with code TAP-1234

**Test Data Needed:**
- Issue entity with name="TAP-1234" or properties.ticket_id="TAP-1234"

---

### Question 3: Entity Lookup - Brand/Entity Name

**Question:** "Tell me about DHL"

**Expected Type:** `entity_lookup`

**Rationale:**
- Entity name (shipping carrier)
- No table context provided
- Could be in multiple tables (carriers, companies, resources)
- Global search needed

**Expected Strategy:**
```
Search all entities where:
  - name = "DHL" (case-insensitive)
  - aliases contains "DHL"
  - type = "carrier" (if carrier entities exist)
```

**Confidence:** 0.85-0.95 (entity name clear, but could also be semantic search)

**Expected Results:**
- Return carrier entity for DHL
- Or resources about DHL if no entity exists

**Fallback:** If no entity found, try semantic search: `WHERE embedding.cosine("DHL") LIMIT 5`

**Test Data Needed:**
- Entity with type="carrier", name="DHL"
- Or Resource with content about DHL

---

### Question 4: SQL Query - Field Equality

**Question:** "Show me resources with category tutorial"

**Expected Type:** `sql`

**Rationale:**
- Table specified (resources)
- Field-based filter (category = tutorial)
- Structured query with known schema
- Not semantic - exact field match

**Expected SQL:**
```sql
SELECT * FROM resources WHERE category = 'tutorial'
```

**Confidence:** 0.9-1.0 (clear field-based query)

**Expected Results:**
- All resources where category field = "tutorial"

**Test Data Needed:**
- Resources with category="tutorial"
- Resources with category="guide" (to show filtering works)

---

### Question 5: SQL Query - Range Filter

**Question:** "Find agents created in the last 7 days"

**Expected Type:** `sql`

**Rationale:**
- Table specified (agents)
- Temporal range query (last 7 days)
- Structured predicate on created_at field
- Not semantic

**Expected SQL:**
```sql
SELECT * FROM agents
WHERE created_at >= '2025-10-17T00:00:00Z'
ORDER BY created_at DESC
```

**Confidence:** 0.85-0.95 (clear temporal query, date calculation needed)

**Expected Results:**
- Agents created in last 7 days, newest first

**Test Data Needed:**
- Agents with various created_at timestamps
- At least 2 agents within last 7 days
- At least 2 agents older than 7 days

---

### Question 6: SQL Query - IN Operator

**Question:** "Resources where status is active or published"

**Expected Type:** `sql`

**Rationale:**
- Table implied (resources)
- Multiple values for status field
- OR condition maps to IN operator
- Structured field-based query

**Expected SQL:**
```sql
SELECT * FROM resources WHERE status IN ('active', 'published')
```

**Confidence:** 0.9-1.0 (clear multi-value field query)

**Expected Results:**
- Resources with status = 'active' OR status = 'published'

**Test Data Needed:**
- Resources with status="active"
- Resources with status="published"
- Resources with status="draft" (excluded)

---

### Question 7: Vector Search - Pure Semantic

**Question:** "Find resources about authentication and security"

**Expected Type:** `vector`

**Rationale:**
- Conceptual/topic-based query
- Multiple related concepts (authentication, security)
- No specific field names
- Meaning-based, not exact match

**Expected SQL:**
```sql
SELECT * FROM resources
WHERE embedding.cosine('authentication and security')
LIMIT 10
```

**Confidence:** 0.8-0.9 (semantic query, vector search appropriate)

**Expected Results:**
- Resources with content about auth, security, login, OAuth, etc.
- Sorted by similarity score

**Fallback:** If no results, broaden to: `WHERE embedding.cosine('security') LIMIT 10`

**Test Data Needed:**
- Resources with content about authentication (OAuth, login, passwords)
- Resources with content about security (encryption, HTTPS)
- Resources about unrelated topics (to show filtering)

---

### Question 8: Vector Search - Paraphrase

**Question:** "Show me tutorials for beginners learning to code"

**Expected Type:** `vector`

**Rationale:**
- Conceptual query with synonyms
- "tutorials" = "guides", "learning" = "teaching"
- "beginners" + "learning to code" = introductory programming
- Semantic understanding needed

**Expected SQL:**
```sql
SELECT * FROM resources
WHERE embedding.cosine('tutorials for beginners learning to code')
LIMIT 10
```

**Confidence:** 0.75-0.85 (semantic query, but could filter on category too)

**Expected Results:**
- Beginner-friendly programming tutorials
- Intro guides to coding

**Test Data Needed:**
- Resources titled "Python for Beginners", "Learn to Code"
- Resources with category="tutorial" and beginner-focused content

---

### Question 9: Hybrid Query - Semantic + Temporal

**Question:** "Find resources about Python created in the last month"

**Expected Type:** `hybrid`

**Rationale:**
- Semantic component ("about Python")
- Temporal filter ("last month")
- Combines vector search + metadata filter
- Two distinct criteria types

**Expected Strategy:**
```sql
-- Stage 1: Semantic search
SELECT * FROM resources
WHERE embedding.cosine('Python')
AND created_at >= '2025-09-24T00:00:00Z'
LIMIT 10
```

Or:

```
-- Stage 1: Vector search
results = vector_search("Python", top_k=50)

-- Stage 2: Filter by date
filtered = [r for r in results if r.created_at >= last_month]
```

**Confidence:** 0.7-0.85 (hybrid complexity, multiple approaches)

**Expected Results:**
- Resources about Python created in last 30 days
- Combines semantic relevance + recency

**Test Data Needed:**
- Recent resources (< 30 days) about Python
- Older resources (> 30 days) about Python
- Recent resources about other topics

---

### Question 10: Graph Traversal - Relationship Exploration

**Question:** "Who has worked on authentication-related code?"

**Expected Type:** `graph` (multi-stage)

**Rationale:**
- Requires finding entities (code files) first
- Then traversing relationships (authorship, contributions)
- Two-stage query: semantic → graph
- Cannot be answered with single SQL query

**Expected Strategy:**
```
Stage 1: Semantic Search (vector)
  Query: "authentication code login OAuth"
  Target: resources or files
  Output: [auth.py, login_handler.py, oauth_flow.py]

Stage 2: Graph Traversal (graph)
  Start: Entity IDs from Stage 1
  Traverse: INCOMING edges with relationship IN ['created', 'authored', 'modified']
  Output: [Alice, Bob, Charlie]
```

**Confidence:** 0.6-0.8 (multi-stage complexity, requires graph understanding)

**Expected Results:**
- Users who created/authored/modified authentication-related files
- E.g., Alice, Bob, Charlie

**Fallback:** If graph not available, return files and suggest manual exploration

**Test Data Needed:**
- Resources/Files with authentication content
- Users who created those files
- Edges: (user) -[created]-> (file), (user) -[authored]-> (file)

---

## Evaluation Criteria

Each question is evaluated on:

### 1. Query Type Accuracy
- Did LLM choose correct query type?
- Score: 1.0 if correct, 0.0 if wrong

### 2. Confidence Calibration
- Is confidence score in expected range?
- Score: 1.0 if within range, 0.5 if close, 0.0 if far

### 3. Query Correctness
- Does generated SQL/strategy produce correct results?
- Score: 1.0 if correct, 0.5 if partial, 0.0 if wrong

### 4. Fallback Quality
- If no results, is fallback query appropriate?
- Score: 1.0 if good fallback, 0.5 if okay, 0.0 if none/bad

### 5. Explanation Quality
- If confidence < 0.8, is explanation clear?
- Score: 1.0 if clear, 0.5 if vague, 0.0 if missing/wrong

## Overall Score

**Per Question:** Average of 5 criteria (max 5.0)

**Total Score:** Sum across 10 questions (max 50.0)

**Passing Threshold:** 40.0/50.0 (80% accuracy)

## Summary Statistics

| Query Type | Count | Expected Accuracy |
|------------|-------|-------------------|
| entity_lookup | 3 | 85-95% |
| sql | 3 | 90-100% |
| vector | 2 | 80-90% |
| hybrid | 1 | 70-85% |
| graph | 1 | 60-80% |

**Key Challenges:**
1. **entity_lookup vs sql** - Distinguishing when table is unknown
2. **vector vs sql** - Semantic vs structured queries
3. **hybrid** - Combining multiple query types
4. **graph** - Multi-stage reasoning

**Success Metrics:**
- ✅ 9/10 correct query type (90%)
- ✅ 8/10 confidence within expected range (80%)
- ✅ 8/10 queries produce correct results (80%)
- ✅ 7/10 fallbacks are appropriate (70%)

## Test Data Requirements

### Entities Needed
- Users: Alice, Bob, Charlie, Diana, Eve, Frank
- Issues: #12345, TAP-1234 (with properties)
- Carriers: DHL, FedEx (with type="carrier")
- Files: auth.py, login.py, oauth.py

### Resources Needed
- Category="tutorial" resources
- Status="active" and "published" resources
- Authentication/security content
- Python beginner tutorials
- Recent (< 30 days) and older resources

### Relationships Needed
- (User) -[created]-> (File)
- (User) -[authored]-> (Issue)
- (User) -[modified]-> (File)

### Temporal Data
- Mix of created_at dates (last 7 days, last month, older)
- Test temporal filtering accuracy

## Usage

```bash
# Run evaluation
python examples/test_problem_set.py

# Expected output:
# Question 1: ✅ entity_lookup (confidence: 0.98)
# Question 2: ✅ entity_lookup (confidence: 0.92)
# ...
# Total Score: 43.5/50.0 (87%)
```
