"""
Conversation memory — loads and saves message history for a session.
Backed by the SQLite ORM models in src/db/chat/.
"""
from sqlalchemy.orm import Session

from src.db.chat.models import ChatMessage, ChatSession
from src.logger import get_logger

log = get_logger(__name__)


class ConversationMemory:
    def __init__(self, db_session: Session) -> None:
        self.db = db_session

    def get_or_create_session(self, session_id: str) -> ChatSession:
        session = self.db.query(ChatSession).filter_by(id=session_id).first()
        if not session:
            session = ChatSession(id=session_id)
            self.db.add(session)
            self.db.commit()
        return session

    def load_history(self, session_id: str, max_turns: int = 20) -> list[dict]:
        """Returns the last N turns as a list of {role, content} dicts."""
        messages = (
            self.db.query(ChatMessage)
            .filter_by(session_id=session_id)
            .order_by(ChatMessage.created_at.desc())
            .limit(max_turns * 2)  # user + assistant per turn
            .all()
        )
        messages.reverse()
        return [{"role": m.role, "content": m.content} for m in messages]

    def save_turn(self, session_id: str, user_content: str, assistant_content: str) -> None:
        self.get_or_create_session(session_id)
        self.db.add_all([
            ChatMessage(session_id=session_id, role="user", content=user_content),
            ChatMessage(session_id=session_id, role="assistant", content=assistant_content),
        ])
        self.db.commit()
        log.debug("memory.saved_turn", session_id=session_id)
