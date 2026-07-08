from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "local"
    api_cors_origins: str = (
        "http://127.0.0.1:3000,http://localhost:3000,"
        "http://127.0.0.1:3123,http://localhost:3123,"
        "http://127.0.0.1:3124,http://localhost:3124,"
        "http://127.0.0.1:3128,http://localhost:3128,"
        "http://127.0.0.1:5173,http://localhost:5173,"
        "https://jejumate-web.vercel.app"
    )
    api_cors_origin_regex: str | None = None
    database_url: str = "postgresql+psycopg://jejumate:jejumate_local@127.0.0.1:5432/jejumate"
    redis_url: str = "redis://127.0.0.1:6379/0"
    embedding_provider: str = "local"
    llm_provider: str = "local"
    openai_api_key: str | None = None

    # RAG 근거 코사인 유사도 하한선. jejumate/backend(app/config.py)와 동일 기준(0.5)을
    # 그대로 이식 — 관련 없는 문서가 근거로 끼어드는 것을 막는다.
    rag_similarity_threshold: float = 0.5

    # 카톡 실시간 수집 파이프라인. 로컬은 FastAPI startup에서 띄우는 백그라운드
    # asyncio 루프가 이 간격으로 반복 폴링한다. 배포(서버리스)는 상시 루프를 못 돌리는
    # 대신, 자주 호출되는 GET /api/home·/api/meetings·/api/board가 호출될 때마다
    # "마지막 시도로부터 이 간격이 지났으면 그 요청 처리에 얹어서 한 번 수집"하는
    # 방식으로 사실상 상시 수집을 흉내낸다(maybe_ingest_kakao_now). 그 외
    # GET /api/ingest/kakao?secret=...로 수동/크론 트리거도 여전히 가능하다.
    kakao_poll_interval_seconds: int = 20
    # 크론(GET /api/ingest/kakao)·로컬 백그라운드 루프 전용 상한. 이쪽은 실사용
    # 요청을 막지 않으므로 넉넉하게 잡아도 된다(밀렸을 때 한 번에 많이 처리).
    kakao_ingest_max_items_per_run: int = 50
    # 피기백(GET /api/home·/api/meetings·/api/board에 얹혀 실행) 전용 상한.
    # BackgroundTasks로 응답 이후에 실행되게 해봤지만(커밋 2f8f0a6), Vercel Python
    # 런타임이 백그라운드 작업이 끝날 때까지 응답을 마무리하지 않아(실측: 배포판에서
    # 2.1~12초, 사실상 동기와 동일) 되돌렸다 — 그래서 동기 호출을 유지한 채 처리
    # 건수 자체를 최대한 줄여서 지연을 낮춘다(임베딩 호출 1건당 0.5~1초 직결).
    # 대량 적체는 크론(GET /api/ingest/kakao, 5분 주기)이 마저 처리한다.
    kakao_ingest_piggyback_max_items: int = 1
    ingest_secret: str | None = None
    cron_secret: str | None = None

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.api_cors_origins.split(",") if origin.strip()]


settings = Settings()
