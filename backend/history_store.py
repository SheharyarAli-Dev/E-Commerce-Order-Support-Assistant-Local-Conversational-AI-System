"""
history_store.py — Durable JSON-file persistence for past conversations.

SessionStore (session.py) remains the in-memory source of truth for a
*live* conversation's working state (active_intent, last_order_id, etc.).
This module mirrors each session's turns to disk so the frontend can show
a "conversation history" sidebar that survives page reloads and server
restarts — deliberately simple (a single JSON file) to match the rest of
this project's file-based data layer, with no new dependency.
"""

import json
import threading
from typing import Optional

from backend.config import HISTORY_FILE

_lock = threading.Lock()


def _read_all() -> dict:
    if not HISTORY_FILE.exists():
        return {}
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _write_all(data: dict) -> None:
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp_file = HISTORY_FILE.with_suffix(".tmp")
    with open(tmp_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    tmp_file.replace(HISTORY_FILE)


def _make_title(history: list) -> str:
    for turn in history:
        if turn.role == "user":
            text = turn.content.strip()
            return (text[:60] + "…") if len(text) > 60 else text
    return "New conversation"


def save_session(session) -> None:
    """Persist (upsert) a session's turns to the history file."""
    with _lock:
        data = _read_all()
        data[session.session_id] = {
            "session_id": session.session_id,
            "title": _make_title(session.history),
            "created_at": session.created_at,
            "last_active": session.last_active,
            "messages": [
                {"role": t.role, "content": t.content, "timestamp": t.timestamp}
                for t in session.history
            ],
        }
        _write_all(data)


def list_sessions() -> list:
    """Return session summaries (no message bodies) sorted newest-active-first."""
    data = _read_all()
    summaries = [
        {
            "session_id": s["session_id"],
            "title": s["title"],
            "created_at": s["created_at"],
            "last_active": s["last_active"],
            "message_count": len(s["messages"]),
        }
        for s in data.values()
        if s["messages"]
    ]
    summaries.sort(key=lambda s: s["last_active"], reverse=True)
    return summaries


def get_session_messages(session_id: str) -> Optional[list]:
    """Return the full turn list for one session, or None if never persisted."""
    data = _read_all()
    entry = data.get(session_id)
    return entry["messages"] if entry else None


def delete_session(session_id: str) -> bool:
    with _lock:
        data = _read_all()
        if session_id in data:
            del data[session_id]
            _write_all(data)
            return True
        return False
