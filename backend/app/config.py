"""환경변수 설정. Supabase(운영) 또는 로컬 postgres(docker) 접속 정보를 읽는다."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/jejumate"

    # "mock" 또는 "openai"(추후 실제 키 연동 시). 나중엔 OpenAI 단일로 통일할 예정이라
    # 실제 제공자 기본값은 openai로 두되, 오늘은 API 키가 없어 mock으로 운용한다.
    llm_provider: str = "mock"
    embedding_provider: str = "mock"


settings = Settings()
