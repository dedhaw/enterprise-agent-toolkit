"""
Scaffolding Agent — Memory strategies.

Two options shown side by side:

  SlidingWindowMemory — keeps the last N turns, older turns fall out of context.
                        Simple, cheap, predictable token cost.
                        Best for: short-lived tasks, stateless Q&A, support bots.

  CompactingMemory    — when history exceeds a threshold, summarizes old turns
                        with a small LLM call, then keeps summary + recent turns.
                        More expensive (extra LLM call) but the agent never forgets
                        things said early in a long conversation.
                        Best for: long-running sessions, onboarding flows,
                        agents that need to remember context from hours ago.
"""
from sqlalchemy.orm import Session

from src.db.chat.models import ChatMessage, ChatSession
from src.logger import get_logger

log = get_logger(__name__)


# ── Option 1: Sliding Window ──────────────────────────────────────────────────

class SlidingWindowMemory:
    """
    Returns the last `max_turns` turns from the DB.
    Everything older than that is ignored each request — it's still in the DB,
    just not sent to the LLM.

    Token cost: fixed (bounded by max_turns).
    Trade-off: the agent forgets things said before the window.
    """

    def __init__(self, db_session: Session, max_turns: int = 20) -> None:
        self.db = db_session
        self.max_turns = max_turns

    def _get_or_create_session(self, session_id: str) -> ChatSession:
        session = self.db.query(ChatSession).filter_by(id=session_id).first()
        if not session:
            session = ChatSession(id=session_id)
            self.db.add(session)
            self.db.commit()
        return session

    def load(self, session_id: str) -> list[dict]:
        messages = (
            self.db.query(ChatMessage)
            .filter_by(session_id=session_id)
            .order_by(ChatMessage.created_at.desc())
            .limit(self.max_turns * 2)  # user + assistant per turn
            .all()
        )
        messages.reverse()
        return [{"role": m.role, "content": m.content} for m in messages]

    def save(self, session_id: str, user_message: str, assistant_reply: str) -> None:
        self._get_or_create_session(session_id)
        self.db.add_all([
            ChatMessage(session_id=session_id, role="user", content=user_message),
            ChatMessage(session_id=session_id, role="assistant", content=assistant_reply),
        ])
        self.db.commit()


# ── Option 2: Compacting Memory ───────────────────────────────────────────────

class CompactingMemory:
    """
    Keeps up to `recent_turns` turns in full. When total history exceeds
    `compact_after_turns`, older turns are summarized with a small LLM call
    and stored as a single "summary" system message prepended to the context.

    The summary is regenerated on each request where compaction is triggered,
    so it stays current as the conversation grows.

    Token cost: variable — one extra LLM call when compaction fires.
    Trade-off: slightly higher latency on long sessions, but the agent retains
    the gist of the entire conversation regardless of length.

    Example context sent to LLM after compaction:
      [system]     <your agent system prompt>
      [system]     Summary of earlier conversation: Dev mentioned he works in
                   fintech and is building a trading assistant. He prefers
                   concise responses. He asked about market data APIs.
      [user]       What was that API endpoint again?
      [assistant]  The Alpaca Markets endpoint is ...
      [user]       Can you show me the Python code?
    """

    def __init__(
        self,
        db_session: Session,
        llm,                        # any LLMClient — use a fast/cheap model here
        recent_turns: int = 10,     # how many full turns to keep after the summary
        compact_after_turns: int = 30,  # total turns before compaction kicks in
    ) -> None:
        self.db = db_session
        self.llm = llm
        self.recent_turns = recent_turns
        self.compact_after_turns = compact_after_turns

    def _get_or_create_session(self, session_id: str) -> ChatSession:
        session = self.db.query(ChatSession).filter_by(id=session_id).first()
        if not session:
            session = ChatSession(id=session_id)
            self.db.add(session)
            self.db.commit()
        return session

    def _all_messages(self, session_id: str) -> list[ChatMessage]:
        return (
            self.db.query(ChatMessage)
            .filter_by(session_id=session_id)
            .order_by(ChatMessage.created_at.asc())
            .all()
        )

    async def load(self, session_id: str) -> list[dict]:
        all_messages = self._all_messages(session_id)
        total_turns = len(all_messages) // 2  # each turn = 1 user + 1 assistant

        if total_turns <= self.compact_after_turns:
            # Under the threshold — return everything, no compaction needed
            log.debug("memory.no_compaction", session_id=session_id, turns=total_turns)
            return [{"role": m.role, "content": m.content} for m in all_messages]

        # Split: old messages to summarize + recent messages to keep in full
        cutoff = len(all_messages) - (self.recent_turns * 2)
        old_messages = all_messages[:cutoff]
        recent_messages = all_messages[cutoff:]

        log.info(
            "memory.compacting",
            session_id=session_id,
            summarizing=len(old_messages),
            keeping=len(recent_messages),
        )

        summary = await self._summarize(old_messages)

        return [
            # Inject the summary as a system message so the LLM treats it as context
            {"role": "system", "content": f"Summary of earlier conversation:\n{summary}"},
            *[{"role": m.role, "content": m.content} for m in recent_messages],
        ]

    async def _summarize(self, messages: list[ChatMessage]) -> str:
        """Calls the LLM to produce a compact summary of the given message list."""
        history_text = "\n".join(
            f"{m.role.upper()}: {m.content}" for m in messages
        )
        summary_prompt = [
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
        ]
        response = await self.llm.chat(summary_prompt)
        return response.content or ""

    def save(self, session_id: str, user_message: str, assistant_reply: str) -> None:
        self._get_or_create_session(session_id)
        self.db.add_all([
            ChatMessage(session_id=session_id, role="user", content=user_message),
            ChatMessage(session_id=session_id, role="assistant", content=assistant_reply),
        ])
        self.db.commit()
