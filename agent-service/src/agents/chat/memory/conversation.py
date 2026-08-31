"""
Conversation memory — loads and saves message history for a session.
Backed by the ORM models in src/db/chat/.

Two load strategies:
  load_history()   — sliding window, returns last N turns (simple, fixed token cost)
  load_compacted() — summarizes old turns with an LLM when session exceeds threshold
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

    # ── Sliding window ────────────────────────────────────────────────────────

    def load_history(self, session_id: str, max_turns: int = 20) -> list[dict]:
        """Returns the last N turns as {role, content} dicts. Older turns are dropped."""
        messages = (
            self.db.query(ChatMessage)
            .filter_by(session_id=session_id)
            .order_by(ChatMessage.created_at.desc())
            .limit(max_turns * 2)  # user + assistant per turn
            .all()
        )
        messages.reverse()
        return [{"role": m.role, "content": m.content} for m in messages]

    # ── Compacting ────────────────────────────────────────────────────────────

    async def load_compacted(
        self,
        session_id: str,
        llm,
        recent_turns: int = 10,
        compact_after_turns: int = 30,
    ) -> list[dict]:
        """
        Returns history for the session. When total turns exceed `compact_after_turns`,
        old turns are summarized by `llm` and injected as a single system message,
        followed by the last `recent_turns` turns in full.

        Args:
            llm:                 Any LLMClient. Use a fast/cheap model (e.g. intent_model).
            recent_turns:        Full turns to keep after the summary.
            compact_after_turns: Total turns before compaction fires.
        """
        all_messages = (
            self.db.query(ChatMessage)
            .filter_by(session_id=session_id)
            .order_by(ChatMessage.created_at.asc())
            .all()
        )

        total_turns = len(all_messages) // 2

        if total_turns <= compact_after_turns:
            log.debug("memory.no_compaction", session_id=session_id, turns=total_turns)
            return [{"role": m.role, "content": m.content} for m in all_messages]

        cutoff = len(all_messages) - (recent_turns * 2)
        old_messages = all_messages[:cutoff]
        recent_messages = all_messages[cutoff:]

        log.info(
            "memory.compacting",
            session_id=session_id,
            summarizing=len(old_messages),
            keeping=len(recent_messages),
        )

        summary = await self._summarize(llm, old_messages)

        return [
            {"role": "system", "content": f"Summary of earlier conversation:\n{summary}"},
            *[{"role": m.role, "content": m.content} for m in recent_messages],
        ]

    async def _summarize(self, llm, messages: list[ChatMessage]) -> str:
        history_text = "\n".join(f"{m.role.upper()}: {m.content}" for m in messages)
        response = await llm.chat([
            {
                "role": "system",
                "content": (
                    "You are a conversation summarizer. "
                    "Produce a concise summary (3-5 sentences) of the conversation below. "
                    "Capture: who the user is, what they're trying to do, key facts mentioned, "
                    "and any decisions or conclusions reached. "
                    "Write in third person past tense. Return only the summary, no preamble."
                ),
            },
            {"role": "user", "content": history_text},
        ])
        return response.content or ""

    # ── Persist ───────────────────────────────────────────────────────────────

    def save_turn(self, session_id: str, user_content: str, assistant_content: str) -> None:
        self.get_or_create_session(session_id)
        self.db.add_all([
            ChatMessage(session_id=session_id, role="user", content=user_content),
            ChatMessage(session_id=session_id, role="assistant", content=assistant_content),
        ])
        self.db.commit()
        log.debug("memory.saved_turn", session_id=session_id)
