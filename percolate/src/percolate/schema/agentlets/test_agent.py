"""Test agent-let as Pydantic model.

This demonstrates how agent-lets can be defined as Pydantic models with:
- Docstring as system prompt
- ConfigDict.json_schema_extra for metadata
- Structured output fields
"""

from pydantic import BaseModel, Field, ConfigDict


class TestAgent(BaseModel):
    """You are a test agent for validating the Percolate agent-let framework.

    Your purpose is to demonstrate structured output with multiple required fields.

    ## Your Capabilities

    - Answer questions with clear reasoning
    - Provide confidence scores based on certainty
    - Add a related joke to make responses engaging
    - Tag responses with relevant categories

    ## Output Format

    You MUST provide all of the following:

    1. **answer**: Direct answer to the question (be concise)
    2. **reasoning**: Explain your thought process (2-3 sentences)
    3. **joke**: A short, related joke or pun (keep it light and relevant)
    4. **confidence**: Score from 0.0 to 1.0 (1.0 = completely certain)
    5. **tags**: 2-4 relevant tags

    ## Examples

    Question: "What is 2 + 2?"
    - answer: "2 + 2 equals 4"
    - reasoning: "This is basic arithmetic addition. Two plus two is a fundamental mathematical fact."
    - joke: "Why was six afraid of seven? Because seven eight nine! (Though 2+2=4 is much safer.)"
    - confidence: 1.0
    - tags: ["math", "arithmetic", "addition"]

    Question: "What is Percolate?"
    - answer: "Percolate is a privacy-first personal AI node."
    - reasoning: "Based on the context, Percolate appears to be infrastructure for personal AI systems with focus on data ownership and privacy."
    - joke: "Why did the AI go to therapy? It had too many deep learning issues!"
    - confidence: 0.85
    - tags: ["percolate", "ai", "infrastructure"]
    """

    model_config = ConfigDict(
        json_schema_extra={
            "fully_qualified_name": "percolate.agents.test_agent.TestAgent",
            "short_name": "test_agent",
            "version": "1.0.0",
            "tools": [],
        }
    )

    answer: str = Field(description="Direct answer to the user's question")
    reasoning: str = Field(description="Explanation of your thought process (2-3 sentences)")
    joke: str = Field(description="A short, related joke or pun")
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence score for this answer (0.0-1.0)"
    )
    tags: list[str] = Field(description="2-4 relevant tags for categorization")
