from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.v0.router import router as v0_router
from src.config import get_settings
from src.db.base import init_db
from src.logger import get_logger, setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    setup_logging(settings.log_level, settings.log_service_url)
    log = get_logger("startup")
    log.info("agent_service.starting", mode=settings.app_mode, model=settings.general_model)
    init_db()
    log.info("agent_service.ready")
    yield
    log.info("agent_service.shutdown")


app = FastAPI(
    title="Agent Service",
    version="0.1.0",
    description="FastAPI agent backend — multi-model, multi-agent, versioned API.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(v0_router, prefix="/api")


@app.get("/health", tags=["meta"])
async def health():
    settings = get_settings()
    return {"status": "ok", "mode": settings.app_mode, "model": settings.general_model}
