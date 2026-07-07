import asyncio
import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import board, health, home, ingest, interactions, meetings, profile
from app.core.config import settings
from app.services.kakao_ingest import ingest_new_messages

logger = logging.getLogger(__name__)


async def _kakao_polling_loop() -> None:
    loop = asyncio.get_running_loop()
    while True:
        try:
            # ingest_new_messages는 동기(requests류) I/O라 이벤트 루프에서 바로 돌리면
            # OpenAI 임베딩 호출이 끝날 때까지 서버 전체가 응답을 못 한다 — 스레드로 뺀다.
            count, cursor = await loop.run_in_executor(None, ingest_new_messages)
            if count:
                logger.info("카톡 수집: %s건 적재, 커서 %s", count, cursor)
        except Exception:  # noqa: BLE001 - 폴링 루프는 한 번 실패해도 계속 돌아야 한다.
            logger.exception("카톡 수집 실패")
        await asyncio.sleep(settings.kakao_poll_interval_seconds)


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
    app.include_router(ingest.router, prefix="/api")
    app.include_router(interactions.router, prefix="/api")
    app.include_router(meetings.router, prefix="/api")
    app.include_router(profile.router, prefix="/api")

    @app.on_event("startup")
    async def _start_kakao_polling() -> None:
        # Vercel 서버리스는 요청이 끝나면 프로세스가 죽어서 상시 폴링이 불가능하다.
        # 배포는 GET /api/ingest/kakao?secret=...로 크론/수동 트리거한다.
        if os.environ.get("VERCEL"):
            return
        asyncio.create_task(_kakao_polling_loop())

    return app


app = create_app()
