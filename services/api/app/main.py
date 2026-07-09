import asyncio
import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import board, health, home, ingest, interactions, meetings, profile
from app.core.config import settings
from app.repositories.local_store import cleanup_expired_parties
from app.services.kakao_ingest import ingest_new_messages

logger = logging.getLogger(__name__)
# 루트 로거가 기본 WARNING이라 logger.info()가 조용히 버려진다 — 이 로거만 INFO로 올리고
# 전용 핸들러를 달아 journald(stderr)로 실제로 찍히게 한다. 다른 라이브러리 로그엔 영향 없음.
logger.setLevel(logging.INFO)
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(asctime)s %(name)s %(levelname)s: %(message)s"))
    logger.addHandler(_handler)
    logger.propagate = False

# create_task가 반환한 Task를 아무 데도 저장하지 않으면 가비지 컬렉션 대상이 되어
# 루프가 조용히 죽을 수 있다(asyncio 공식 문서 경고) — 모듈 레벨 set에 참조를 유지한다.
_background_tasks: set[asyncio.Task] = set()


def _spawn_background_task(coro) -> asyncio.Task:
    task = asyncio.create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return task


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


async def _party_cleanup_loop() -> None:
    """마감 2일 지난 사용자 파티를 주기적으로 실제 삭제한다(자체 서버 전용 —
    서버리스는 GET /api/cleanup/expired-parties 트리거로 대신한다)."""
    loop = asyncio.get_running_loop()
    while True:
        try:
            deleted = await loop.run_in_executor(None, cleanup_expired_parties)
            if deleted:
                logger.info("만료 파티 정리: %s건 삭제", deleted)
        except Exception:  # noqa: BLE001 - 정리 루프도 한 번 실패해도 계속 돌아야 한다.
            logger.exception("만료 파티 정리 실패")
        await asyncio.sleep(settings.party_cleanup_interval_seconds)


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
        logger.info("startup: 백그라운드 루프 기동 시작")
        # Vercel 서버리스는 요청이 끝나면 프로세스가 죽어서 상시 폴링이 불가능하다.
        # 배포는 GET /api/ingest/kakao?secret=...로 크론/수동 트리거한다.
        if os.environ.get("VERCEL"):
            logger.info("startup: VERCEL 환경이라 폴링 루프 생략")
            return
        _spawn_background_task(_kakao_polling_loop())
        _spawn_background_task(_party_cleanup_loop())
        logger.info("startup: 카톡 폴링/파티 정리 태스크 생성 완료")

    return app


app = create_app()
