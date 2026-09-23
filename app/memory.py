"""In-memory, per-session conversation history.

Deliberately simple: a dict guarded by a lock. Sessions older than the configured
TTL are evicted lazily whenever the store is touched, so nothing runs in the
background. Restarting the server clears everything.
"""

import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, List

from app.config import settings


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Session:
    messages: List[dict] = field(default_factory=list)
    last_used: datetime = field(default_factory=_now)


class SessionStore:
    def __init__(self, max_turns: int, ttl_minutes: int) -> None:
        self._max_messages = max_turns * 2
        self._ttl = timedelta(minutes=ttl_minutes)
        self._sessions: Dict[str, Session] = {}
        self._lock = threading.Lock()

    def _evict_expired(self) -> None:
        cutoff = _now() - self._ttl
        stale = [sid for sid, s in self._sessions.items() if s.last_used < cutoff]
        for sid in stale:
            del self._sessions[sid]

    def get_history(self, session_id: str) -> List[dict]:
        """Return the recent turns for a session, oldest first."""
        with self._lock:
            self._evict_expired()
            session = self._sessions.get(session_id)
            if session is None:
                return []
            session.last_used = _now()
            return list(session.messages)

    def append(self, session_id: str, role: str, text: str) -> None:
        """Record one turn. `role` is "user" or "model"."""
        with self._lock:
            self._evict_expired()
            session = self._sessions.setdefault(session_id, Session())
            session.messages.append({"role": role, "text": text})
            # Keep only the most recent exchanges so prompts stay bounded.
            if len(session.messages) > self._max_messages:
                session.messages = session.messages[-self._max_messages :]
            session.last_used = _now()

    def reset(self, session_id: str) -> bool:
        """Forget a session. Returns True if there was anything to forget."""
        with self._lock:
            return self._sessions.pop(session_id, None) is not None

    def count(self) -> int:
        with self._lock:
            self._evict_expired()
            return len(self._sessions)


store = SessionStore(settings.max_history_turns, settings.session_ttl_minutes)
