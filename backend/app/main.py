from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .routers import (
    dashboard,
    data_sources,
    data_status,
    leagues,
    managers,
    matches,
    model,
    players,
    teams,
)

app = FastAPI(
    title="Euro Football Predictor API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["*"],
)

for router in (
    dashboard.router,
    matches.router,
    leagues.router,
    teams.router,
    players.router,
    managers.router,
    model.router,
    data_status.router,
    data_sources.router,
):
    app.include_router(router)


@app.get("/health", tags=["system"])
def health():
    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/", tags=["system"])
def root():
    return {
        "name": "Euro Football Predictor API",
        "docs": "/docs",
        "health": "/health",
    }
