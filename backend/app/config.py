"""환경변수 설정. Supabase(운영) 또는 로컬 postgres(docker) 접속 정보를 읽는다."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/jejumate"


settings = Settings()
