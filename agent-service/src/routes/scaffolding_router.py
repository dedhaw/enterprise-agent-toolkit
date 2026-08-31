"""
Scaffolding Agent Router — template for a new agent's API routes.

Exposes:
  POST /message          — send a message, get a reply
  GET  /history/{id}     — placeholder (no memory by default)

To use this as a template:
  1. Copy this file to src/routes/<your_agent>_router.py
  2. Replace all references to "scaffolding" / "ScaffoldingAgent" with your agent name
  3. Register the router in src/api/v0/router.py
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.agents.scaffolding.agent import ScaffoldingAgent
from src.db.base import get_db_dep
from src.logger import get_logger

log = get_logger(__name__)
router = APIRouter(tags=["scaffolding"])


# ── Request / Response models ─────────────────────────────────────────────────

class MessageRequest(BaseModel):
    session_id: str
    message: str


class MessageResponse(BaseModel):
    session_id: str
    reply: str
    tools_used: list[str] = []


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/message", response_model=MessageResponse)
async def send_message(
    body: MessageRequest,
    db: Session = Depends(get_db_dep),
) -> MessageResponse:
    try:
        agent = ScaffoldingAgent(db_session=db)
        result = await agent.run(session_id=body.session_id, user_message=body.message)
        return MessageResponse(
            session_id=result.session_id,
            reply=result.reply,
            tools_used=result.tools_used,
        )
    except Exception as exc:
        log.exception("scaffolding.error", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/history/{session_id}")
def get_history(session_id: str):
    # No memory wired up yet — add ConversationMemory here when ready
    return {"session_id": session_id, "messages": []}
