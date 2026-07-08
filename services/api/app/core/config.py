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
    # asyncio 루프가 이 간격으로 반복 폴링한다(로컬 전용, 무해함). 배포는
    # GET /api/ingest/kakao?secret=...를 GitHub Actions 5분 크론이 호출하는 방식만
    # 쓴다 — 한때 /api/home·/api/meetings·/api/board 조회 요청에 얹어(피기백,
    # maybe_ingest_kakao_now) 사실상 상시 수집을 흉내내봤지만(BackgroundTasks까지
    # 시도), Vercel 프로덕션 실측(연속 호출 2.5~11초)이 핵심 화면(모임생성→신청→
    # 승인→채팅) 응답 속도를 갉아먹어 그 세 라우트에서는 호출을 뺐다. 함수 자체는
    # kakao_ingest.py에 남아 있다(플랫폼이 바뀌면 재사용 가능).
    kakao_poll_interval_seconds: int = 20
    # 크론(GET /api/ingest/kakao)·로컬 백그라운드 루프 전용 상한. 이쪽은 실사용
    # 요청을 막지 않으므로 넉넉하게 잡아도 된다(밀렸을 때 한 번에 많이 처리).
    kakao_ingest_max_items_per_run: int = 50
    # (미사용) 피기백 전용 상한 — 라우트에서 더 이상 호출 안 하지만 maybe_ingest_kakao_now
    # 자체는 남겨뒀으니 값도 같이 남겨둔다.
    kakao_ingest_piggyback_max_items: int = 1
    ingest_secret: str | None = None
    cron_secret: str | None = None

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.api_cors_origins.split(",") if origin.strip()]


settings = Settings()
