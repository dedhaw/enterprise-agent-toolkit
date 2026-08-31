from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.agents.chat.chat import ChatAgent
from src.db.base import get_db_dep
from src.logger import get_logger

log = get_logger(__name__)
router = APIRouter(tags=["chat"])


# ── Request / Response models ────────────────────────────────────────────────

class ChatRequest(BaseModel):
    session_id: str
    message: str


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    tools_used: list[str] = []


class HistoryMessage(BaseModel):
    role: str
    content: str


class HistoryResponse(BaseModel):
    session_id: str
    messages: list[HistoryMessage]


# ── Routes ───────────────────────────────────────────────────────────────────

@router.post("/message", response_model=ChatResponse)
async def send_message(
    body: ChatRequest,
    db: Session = Depends(get_db_dep),
) -> ChatResponse:
    try:
        agent = ChatAgent(db_session=db)
        result = await agent.run(session_id=body.session_id, user_message=body.message)
        return ChatResponse(
            session_id=result.session_id,
            reply=result.reply,
            tools_used=result.tools_used,
        )
    except Exception as exc:
        log.exception("chat.error", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/history/{session_id}", response_model=HistoryResponse)
def get_history(
    session_id: str,
    db: Session = Depends(get_db_dep),
) -> HistoryResponse:
    from src.agents.chat.memory.conversation import ConversationMemory
    memory = ConversationMemory(db)
    messages = memory.load_history(session_id)
    return HistoryResponse(
        session_id=session_id,
        messages=[HistoryMessage(**m) for m in messages],
    )
