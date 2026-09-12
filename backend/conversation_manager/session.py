"""
session.py — Session state management.

Each WebSocket connection is associated with a Session.
Sessions track conversation history, detected intent, and
any in-progress entity context (e.g., the last looked-up order ID).
"""

import uuid
import time
from dataclasses import dataclass, field
from typing import Optional

from backend.config import SESSION_TIMEOUT_SECONDS


@dataclass
class Turn:
    """A single conversation turn (one user message + one assistant reply)."""
    role: str        # "user" or "assistant"
    content: str
    timestamp: float = field(default_factory=time.time)


@dataclass
class Session:
    """
    Full state for one user session.

    history      — ordered list of Turn objects (user/assistant alternating)
    active_intent — last detected intent: PRODUCT_QUERY | ORDER_TRACKING |
                    RETURNS_POLICY | OUT_OF_SCOPE | None (not yet determined)
    last_order_id — most recently looked-up order ID (for follow-up turns)
    last_sku      — most recently referenced product SKU (for follow-up turns)
    created_at    — epoch timestamp of session creation
    last_active   — epoch timestamp of most recent activity (for TTL cleanup)
    """
    session_id:    str   = field(default_factory=lambda: str(uuid.uuid4()))
    history:       list  = field(default_factory=list)
    active_intent: Optional[str] = None
    last_order_id: Optional[str] = None
    last_sku:      Optional[str] = None
    created_at:    float = field(default_factory=time.time)
    last_active:   float = field(default_factory=time.time)

    def add_turn(self, role: str, content: str) -> None:
        self.history.append(Turn(role=role, content=content))
        self.last_active = time.time()

    def is_expired(self) -> bool:
        return (time.time() - self.last_active) > SESSION_TIMEOUT_SECONDS

    def reset(self) -> None:
        """Clear history and intent state, keeping session ID."""
        self.history.clear()
        self.active_intent = None
        self.last_order_id = None
        self.last_sku      = None
        self.last_active   = time.time()


class SessionStore:
    """
    In-memory store of active sessions.
    Thread-safety note: FastAPI with a single uvicorn worker is
    single-threaded per event loop, so a plain dict is safe here.
    For multi-worker deployments, replace with Redis or a DB backend.
    """

    def __init__(self):
        self._sessions: dict[str, Session] = {}

    def create(self) -> Session:
        session = Session()
        self._sessions[session.session_id] = session
        return session

    def get(self, session_id: str) -> Optional[Session]:
        session = self._sessions.get(session_id)
        if session and session.is_expired():
            self.delete(session_id)
            return None
        return session

    def get_or_create(self, session_id: str) -> Session:
        """Return existing session or create a new one with the given ID."""
        session = self.get(session_id)
        if session is None:
            session = Session(session_id=session_id)
            self._sessions[session_id] = session
        return session

    def delete(self, session_id: str) -> bool:
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False

    def purge_expired(self) -> int:
        """Remove all expired sessions. Returns count removed."""
        expired = [sid for sid, s in self._sessions.items() if s.is_expired()]
        for sid in expired:
            del self._sessions[sid]
        return len(expired)

    def count(self) -> int:
        return len(self._sessions)
