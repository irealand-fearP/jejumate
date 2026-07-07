from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "local"
    api_cors_origins: str = (
        "http://127.0.0.1:3000,http://localhost:3000,"
        "http://127.0.0.1:3123,http://localhost:3123,"
        "http://127.0.0.1:3124,http://localhost:3124,"
        "http://127.0.0.1:3128,http://localhost:3128,"
        "http://127.0.0.1:5173,http://localhost:5173"
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

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.api_cors_origins.split(",") if origin.strip()]


settings = Settings()
