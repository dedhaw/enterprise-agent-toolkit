"""
API v0 — initial release.

Adding a new agent to v0:
  1. Create src/routes/<agent>_router.py
  2. Import and include it here

Breaking changes that affect existing endpoints must go in a new api version (v1, v2, ...).
"""
from fastapi import APIRouter

from src.routes.chat_router import router as chat_router
from src.routes.scaffolding_router import router as scaffolding_router

router = APIRouter(prefix="/v0")

router.include_router(chat_router, prefix="/agents/chat")
router.include_router(scaffolding_router, prefix="/agents/scaffolding")
