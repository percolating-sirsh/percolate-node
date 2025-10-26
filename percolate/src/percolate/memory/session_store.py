"""Session persistence using REM database.

Sessions and messages are stored as separate tables (parent-child relationship):
- sessions: session metadata (id, tenant, agent, timestamps)
- messages: individual messages linked to session via session_id

Schemas are defined in percolate-rocks (builtin.rs) and auto-registered.
Python code just uses the tables - NO duplicate schema definitions.
"""

from datetime import datetime
from typing import Any
import uuid

from pydantic import BaseModel, Field
from loguru import logger

from percolate.memory.database import get_database

# NOTE: Schemas are now defined in percolate-rocks/src/schema/builtin.rs
# They are automatically registered when the database opens.
# We keep Pydantic models here for type hints and validation only.

# Removed SESSION_SCHEMA, MESSAGE_SCHEMA, FEEDBACK_SCHEMA - now in rocks!


class Message(BaseModel):
    """Individual message in a conversation."""

    message_id: str = Field(description="Unique message identifier")
    session_id: str = Field(description="Parent session identifier")
    tenant_id: str = Field(description="Tenant scope for isolation")
    role: str = Field(description="Message role: user, assistant, or system")
    content: str = Field(description="Message content")
    model: str | None = Field(default=None, description="Model that generated response")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    usage: dict[str, int] | None = Field(default=None, description="Token usage metrics")
    trace_id: str | None = Field(default=None, description="OTEL trace ID")
    span_id: str | None = Field(default=None, description="OTEL span ID")


class Feedback(BaseModel):
    """User feedback on agent interactions."""

    feedback_id: str = Field(description="Unique feedback identifier")
    session_id: str = Field(description="Parent session identifier")
    message_id: str | None = Field(default=None, description="Specific message being rated")
    tenant_id: str = Field(description="Tenant scope for isolation")
    trace_id: str | None = Field(default=None, description="OTEL trace ID")
    span_id: str | None = Field(default=None, description="OTEL span ID")
    label: str | None = Field(default=None, description="Feedback label (any string)")
    score: float | None = Field(default=None, description="Feedback score 0-1")
    feedback_text: str | None = Field(default=None, description="Optional comment")
    user_id: str | None = Field(default=None, description="User providing feedback")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)


class Session(BaseModel):
    """Conversation session metadata."""

    session_id: str = Field(description="Unique session identifier")
    tenant_id: str = Field(description="Tenant scope for isolation")
    agent_uri: str | None = Field(default=None, description="Agent used in session")
    message_count: int = Field(default=0, description="Number of messages")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class SessionStore:
    """Manage conversation sessions and messages with REM database persistence.

    Sessions and messages are stored in separate tables:
    - sessions: Parent table with session metadata
    - messages: Child table with individual messages (foreign key: session_id)

    Uses percolate-rocks insert() as upsert via key_field.
    """

    def __init__(self, db_path: str | None = None):
        """Initialize session store and register schemas.

        Args:
            db_path: Optional database path override
        """
        self.db = get_database(db_path)
        if not self.db:
            logger.warning("REM database unavailable - sessions will not persist")
            return

        # Schemas are auto-registered from percolate-rocks builtin schemas
        # No need to register them here!
        logger.debug("Using sessions, messages, and feedback schemas from percolate-rocks")

    def save_message(
        self,
        session_id: str,
        tenant_id: str,
        role: str,
        content: str,
        agent_uri: str | None = None,
        model: str | None = None,
        usage: dict[str, int] | None = None,
        trace_id: str | None = None,
        span_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str | None:
        """Save a message to session.

        Creates/updates session and inserts new message.

        Tables:
        1. Upserts session (via key_field=session_id)
        2. Inserts message (new row, links to session)

        Args:
            session_id: Session identifier
            tenant_id: Tenant scope for isolation
            role: Message role (user, assistant, system)
            content: Message content (string only)
            agent_uri: Optional agent identifier
            model: Model that generated response
            usage: Token usage metrics
            metadata: Additional session metadata

        Returns:
            Message ID if successful, None otherwise

        Example:
            >>> store = SessionStore()
            >>> msg_id = store.save_message(
            ...     session_id="sess-123",
            ...     tenant_id="tenant-abc",
            ...     role="user",
            ...     content="What is percolate?"
            ... )
        """
        if not self.db:
            logger.debug(f"Skipping session save (db unavailable): {session_id}")
            return None

        try:
            now = datetime.utcnow()
            timestamp = now.isoformat() + "Z"

            # 1. Upsert session (increment message_count, update timestamp)
            existing_session = self.get_session(session_id, tenant_id)

            if existing_session:
                # Update existing session
                session_data = {
                    "session_id": session_id,
                    "tenant_id": tenant_id,
                    "agent_uri": agent_uri or existing_session.agent_uri,
                    "message_count": existing_session.message_count + 1,
                    "metadata": metadata or existing_session.metadata,
                    "created_at": existing_session.created_at.replace(tzinfo=None).isoformat() + "Z",
                    "updated_at": timestamp,
                }
            else:
                # Create new session
                session_data = {
                    "session_id": session_id,
                    "tenant_id": tenant_id,
                    "agent_uri": agent_uri,
                    "message_count": 1,
                    "metadata": metadata or {},
                    "created_at": timestamp,
                    "updated_at": timestamp,
                }

            session_entity_id = self.db.insert("sessions", session_data)
            logger.debug(f"Upserted session {session_id} (entity: {session_entity_id})")

            # 2. Insert message (new row)
            message_id = str(uuid.uuid4())
            message_data = {
                "message_id": message_id,
                "session_id": session_id,
                "tenant_id": tenant_id,
                "role": role,
                "content": content,
                "model": model,
                "timestamp": timestamp,
                "usage": usage,
                "trace_id": trace_id,
                "span_id": span_id,
            }

            message_entity_id = self.db.insert("messages", message_data)
            logger.debug(f"Inserted message {message_id} to session {session_id} (entity: {message_entity_id})")

            return message_id

        except Exception as e:
            logger.error(f"Failed to save message: {e}")
            return None

    def get_session(self, session_id: str, tenant_id: str) -> Session | None:
        """Retrieve session metadata by ID.

        Args:
            session_id: Session identifier (key field)
            tenant_id: Tenant scope for isolation

        Returns:
            Session metadata if found, None otherwise

        Note:
            This only returns session metadata. Use get_messages() to get messages.

        Example:
            >>> store = SessionStore()
            >>> session = store.get_session("sess-123", "tenant-abc")
            >>> if session:
            ...     print(f"Session has {session.message_count} messages")
        """
        if not self.db:
            return None

        try:
            # Lookup by key field (session_id)
            results = self.db.lookup("sessions", session_id)

            if not results:
                return None

            # Get first result (should only be one due to unique key)
            session_dict = results[0]

            # Verify tenant_id matches (security check)
            if session_dict.get("tenant_id") != tenant_id:
                logger.warning(
                    f"Session {session_id} belongs to different tenant "
                    f"(requested: {tenant_id}, actual: {session_dict.get('tenant_id')})"
                )
                return None

            # Convert to Session model
            return Session(**session_dict)

        except Exception as e:
            logger.error(f"Failed to retrieve session {session_id}: {e}")
            return None

    def get_messages(self, session_id: str, tenant_id: str, limit: int = 100) -> list[Message]:
        """Retrieve all messages for a session.

        Args:
            session_id: Session identifier
            tenant_id: Tenant scope for isolation
            limit: Maximum number of messages to return (default: 100)

        Returns:
            List of messages ordered by timestamp

        Example:
            >>> store = SessionStore()
            >>> messages = store.get_messages("sess-123", "tenant-abc")
            >>> for msg in messages:
            ...     print(f"[{msg.role}] {msg.content}")
        """
        if not self.db:
            return []

        try:
            # Query messages table for all messages with this session_id
            # TODO: Replace with proper query when percolate-rocks supports SQL queries
            # For now, we'll need to iterate through messages (not efficient)
            logger.warning("get_messages not yet implemented - requires SQL query support")
            return []

        except Exception as e:
            logger.error(f"Failed to retrieve messages for {session_id}: {e}")
            return []

    def save_feedback(
        self,
        session_id: str,
        tenant_id: str,
        label: str | None = None,
        message_id: str | None = None,
        score: float | None = None,
        feedback_text: str | None = None,
        trace_id: str | None = None,
        span_id: str | None = None,
        user_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str | None:
        """Save user feedback on an interaction.

        Args:
            session_id: Session identifier
            tenant_id: Tenant scope
            label: Optional feedback label (any string, e.g., 'thumbs_up', 'helpful')
            message_id: Optional specific message being rated
            score: Optional feedback score 0-1 (0=thumbs_down, 1=thumbs_up)
            feedback_text: Optional comment text
            trace_id: Optional OTEL trace ID for linking
            span_id: Optional OTEL span ID for linking
            user_id: Optional user providing feedback
            metadata: Additional metadata

        Returns:
            Feedback ID if successful, None otherwise

        Example:
            >>> store = SessionStore()
            >>> feedback_id = store.save_feedback(
            ...     session_id="sess-123",
            ...     tenant_id="tenant-abc",
            ...     label="thumbs_up",
            ...     score=1.0,
            ...     message_id="msg-456"
            ... )
        """
        if not self.db:
            logger.debug(f"Skipping feedback save (db unavailable): {session_id}")
            return None

        try:
            now = datetime.utcnow()
            timestamp = now.isoformat() + "Z"

            feedback_id = str(uuid.uuid4())
            feedback_data = {
                "feedback_id": feedback_id,
                "session_id": session_id,
                "message_id": message_id,
                "tenant_id": tenant_id,
                "trace_id": trace_id,
                "span_id": span_id,
                "label": label,
                "score": score,
                "feedback_text": feedback_text,
                "user_id": user_id,
                "timestamp": timestamp,
                "metadata": metadata or {},
            }

            feedback_entity_id = self.db.insert("feedback", feedback_data)
            logger.debug(f"Saved feedback {feedback_id} for session {session_id} (entity: {feedback_entity_id})")

            return feedback_id

        except Exception as e:
            logger.error(f"Failed to save feedback: {e}")
            return None

    def list_sessions(self, tenant_id: str, limit: int = 100) -> list[Session]:
        """List sessions for a tenant.

        Args:
            tenant_id: Tenant identifier
            limit: Maximum number of sessions to return

        Returns:
            List of sessions ordered by updated_at descending

        Example:
            >>> store = SessionStore()
            >>> sessions = store.list_sessions("tenant-abc", limit=10)
            >>> for session in sessions:
            ...     print(session.session_id, len(session.messages))
        """
        if not self.db:
            return []

        try:
            # Note: This requires rem query which is not implemented yet
            # sql = f"SELECT * FROM sessions WHERE tenant_id = '{tenant_id}' ORDER BY updated_at DESC LIMIT {limit}"
            # results = self.db.query(sql)
            # return [Session(**r) for r in results]
            logger.debug(f"Session listing not yet implemented (rem query TODO)")
            return []

        except Exception as e:
            logger.error(f"Failed to list sessions for {tenant_id}: {e}")
            return []
