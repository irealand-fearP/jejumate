from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import board, health, home, interactions, meetings, policies, profile
from app.core.config import settings


def create_app() -> FastAPI:
    app = FastAPI(
        title="Jejumate API",
        version="0.1.0",
        description="MVP API for Jejumate, a RAG-based local social web app.",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_origin_regex=settings.api_cors_origin_regex,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(board.router, prefix="/api")
    app.include_router(home.router, prefix="/api")
    app.include_router(interactions.router, prefix="/api")
    app.include_router(meetings.router, prefix="/api")
    app.include_router(policies.router, prefix="/api")
    app.include_router(profile.router, prefix="/api")
    return app


app = create_app()
