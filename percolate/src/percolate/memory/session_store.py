"""Session persistence using REM database.

Sessions and messages are stored as separate tables (parent-child relationship):
- sessions: session metadata (id, tenant, agent, timestamps)
- messages: individual messages linked to session via session_id

Schemas are defined in percolate-rocks (builtin.rs) and auto-registered.
Models are imported from percolate-rocks - NO duplicate definitions.
"""

from typing import Any
import uuid

from loguru import logger
from rem_db.models import ChatSession, ChatMessage, ChatFeedback

from percolate.memory.constants import TABLE_SESSIONS, TABLE_MESSAGES, TABLE_FEEDBACK
from percolate.memory.database import get_database
from percolate.memory.utils import utc_timestamp

# NOTE: Models imported from percolate-rocks/python/rem_db/models.py
# Schemas defined in percolate-rocks/src/schema/builtin.rs
# Both are kept in sync and auto-registered when database opens.

# Re-export models for backward compatibility
Session = ChatSession
Message = ChatMessage
Feedback = ChatFeedback


class SessionStore:
    """Manage conversation sessions and messages with REM database persistence.

    Sessions and messages are stored in separate tables:
    - sessions: Parent table with session metadata
    - messages: Child table with individual messages (foreign key: session_id)

    Uses percolate-rocks insert() as upsert via key_field.
    """

    def __init__(self, db_path: str | None = None):
        """Initialize session store.

        Args:
            db_path: Optional database path override
        """
        self.db = get_database(db_path)
        if not self.db:
            logger.warning("REM database unavailable - sessions will not persist")

    def _build_session_data(
        self,
        session_id: str,
        tenant_id: str,
        agent_uri: str | None,
        metadata: dict[str, Any] | None,
        existing_session: ChatSession | None,
        timestamp: str,
    ) -> dict[str, Any]:
        """Build session data dict for upsert.

        Args:
            session_id: Session identifier
            tenant_id: Tenant scope
            agent_uri: Optional agent identifier
            metadata: Optional session metadata
            existing_session: Existing session if updating
            timestamp: ISO 8601 timestamp

        Returns:
            Session data dictionary for database insert
        """
        if existing_session:
            return {
                "session_id": session_id,
                "tenant_id": tenant_id,
                "agent_uri": agent_uri or existing_session.agent_uri,
                "message_count": existing_session.message_count + 1,
                "metadata": metadata or existing_session.metadata,
                "created_at": existing_session.created_at.replace(tzinfo=None).isoformat() + "Z",
                "updated_at": timestamp,
            }
        else:
            return {
                "session_id": session_id,
                "tenant_id": tenant_id,
                "agent_uri": agent_uri,
                "message_count": 1,
                "metadata": metadata or {},
                "created_at": timestamp,
                "updated_at": timestamp,
            }

    def _upsert_session(self, session_data: dict[str, Any]) -> str:
        """Upsert session to database.

        Args:
            session_data: Session data dictionary

        Returns:
            Entity ID from database
        """
        entity_id = self.db.insert(TABLE_SESSIONS, session_data)
        logger.debug(f"Upserted session {session_data['session_id']} (entity: {entity_id})")
        return entity_id

    def _insert_message(
        self,
        session_id: str,
        tenant_id: str,
        role: str,
        content: str,
        timestamp: str,
        model: str | None = None,
        usage: dict[str, int] | None = None,
        trace_id: str | None = None,
        span_id: str | None = None,
    ) -> str:
        """Insert message to database.

        Args:
            session_id: Parent session identifier
            tenant_id: Tenant scope
            role: Message role
            content: Message content
            timestamp: ISO 8601 timestamp
            model: Optional model identifier
            usage: Optional token usage metrics
            trace_id: Optional OTEL trace ID
            span_id: Optional OTEL span ID

        Returns:
            Message ID (UUID)
        """
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

        entity_id = self.db.insert(TABLE_MESSAGES, message_data)
        logger.debug(f"Inserted message {message_id} to session {session_id} (entity: {entity_id})")
        return message_id

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

        Args:
            session_id: Session identifier
            tenant_id: Tenant scope for isolation
            role: Message role (user, assistant, system)
            content: Message content
            agent_uri: Optional agent identifier
            model: Model that generated response
            usage: Token usage metrics
            trace_id: OTEL trace ID
            span_id: OTEL span ID
            metadata: Additional session metadata

        Returns:
            Message ID if successful, None otherwise
        """
        if not self.db:
            logger.debug(f"Skipping session save (db unavailable): {session_id}")
            return None

        try:
            timestamp = utc_timestamp()
            existing_session = self.get_session(session_id, tenant_id)

            session_data = self._build_session_data(
                session_id, tenant_id, agent_uri, metadata, existing_session, timestamp
            )
            self._upsert_session(session_data)

            message_id = self._insert_message(
                session_id, tenant_id, role, content, timestamp,
                model, usage, trace_id, span_id
            )

            return message_id

        except Exception as e:
            logger.error(f"Failed to save message: {e}")
            return None

    def get_session(self, session_id: str, tenant_id: str) -> ChatSession | None:
        """Retrieve session metadata by ID.

        Args:
            session_id: Session identifier
            tenant_id: Tenant scope for isolation

        Returns:
            Session metadata if found, None otherwise
        """
        if not self.db:
            return None

        try:
            results = self.db.lookup(TABLE_SESSIONS, session_id)
            if not results:
                return None

            session_dict = results[0]

            # Verify tenant_id matches (security check)
            if session_dict.get("tenant_id") != tenant_id:
                logger.warning(
                    f"Session {session_id} belongs to different tenant "
                    f"(requested: {tenant_id}, actual: {session_dict.get('tenant_id')})"
                )
                return None

            return ChatSession(**session_dict)

        except Exception as e:
            logger.error(f"Failed to retrieve session {session_id}: {e}")
            return None

    def get_messages(self, session_id: str, tenant_id: str, limit: int = 100) -> list[ChatMessage]:
        """Retrieve all messages for a session.

        Args:
            session_id: Session identifier
            tenant_id: Tenant scope for isolation
            limit: Maximum number of messages to return

        Returns:
            List of messages ordered by timestamp
        """
        if not self.db:
            return []

        try:
            # TODO: Replace with proper query when percolate-rocks supports SQL queries
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
            label: Optional feedback label
            message_id: Optional specific message being rated
            score: Optional feedback score 0-1
            feedback_text: Optional comment text
            trace_id: Optional OTEL trace ID
            span_id: Optional OTEL span ID
            user_id: Optional user providing feedback
            metadata: Additional metadata

        Returns:
            Feedback ID if successful, None otherwise
        """
        if not self.db:
            logger.debug(f"Skipping feedback save (db unavailable): {session_id}")
            return None

        try:
            timestamp = utc_timestamp()
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

            entity_id = self.db.insert(TABLE_FEEDBACK, feedback_data)
            logger.debug(f"Saved feedback {feedback_id} for session {session_id} (entity: {entity_id})")

            return feedback_id

        except Exception as e:
            logger.error(f"Failed to save feedback: {e}")
            return None

    def list_sessions(self, tenant_id: str, limit: int = 100) -> list[ChatSession]:
        """List sessions for a tenant.

        Args:
            tenant_id: Tenant identifier
            limit: Maximum number of sessions to return

        Returns:
            List of sessions ordered by updated_at descending
        """
        if not self.db:
            return []

        try:
            # TODO: Replace with proper query when percolate-rocks supports SQL queries
            logger.debug("Session listing not yet implemented (rem query TODO)")
            return []

        except Exception as e:
            logger.error(f"Failed to list sessions for {tenant_id}: {e}")
            return []
