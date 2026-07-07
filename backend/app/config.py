"""환경변수 설정. Supabase(운영) 또는 로컬 postgres(docker) 접속 정보를 읽는다."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/jejumate"

    # "mock" 또는 "openai". OPENAI_API_KEY 확보돼 openai로 전환.
    llm_provider: str = "openai"
    embedding_provider: str = "openai"

    # RAG 근거 코사인 유사도 하한선. QA-REPORT.md "Day3 P0 재확인"(2026-07-07) 실측값으로
    # 보정: "택시팟" 계열 질문(관련 근거) 상위 결과 유사도 0.5752~0.6222, "카페 추천" 질문의
    # "제주 공항 근처 싼 숙소"(무관 근거) 유사도 0.4952. 두 값 사이인 0.5로 두면 관련 근거는
    # 통과하고 해당 무관 근거는 걸러진다.
    search_similarity_threshold: float = 0.5


settings = Settings()
