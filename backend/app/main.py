from datetime import datetime
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .routers import (
    dashboard,
    matches,
    leagues,
    teams,
    players,
    managers,
    model,
    data_status,
    data_sources,
)

app = FastAPI(title="Euro Football Predictor API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
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


@app.get("/health")
def health():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


@app.get("/")
def root():
    return {
        "name": "Euro Football Predictor API",
        "docs": "/docs",
        "health": "/health",
    }
