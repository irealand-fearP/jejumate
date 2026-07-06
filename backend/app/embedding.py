"""
임베딩 생성 인터페이스.

- MockEmbeddingProvider: API 키 없이 파이프라인을 검증하기 위한 결정적(같은 입력 →
  같은 벡터) 가짜 임베딩. 실제 유사도 의미는 없다.
- OpenAIEmbeddingProvider: 실제 서비스용(text-embedding-3-small, 1536차원).
  OPENAI_API_KEY 필요. 이 환경에는 키가 없어 "키 없으면 에러"만 검증했고,
  실제 API 호출 자체는 검증하지 못했다 — 완료 보고에 명시.
"""
import hashlib
import os
import random
from typing import Protocol

EMBEDDING_DIM = 1536


class EmbeddingProvider(Protocol):
    def embed(self, text: str) -> list[float]: ...


class MockEmbeddingProvider:
    def embed(self, text: str) -> list[float]:
        seed = int(hashlib.sha256(text.encode("utf-8")).hexdigest(), 16)
        rng = random.Random(seed)
        return [rng.uniform(-1.0, 1.0) for _ in range(EMBEDDING_DIM)]


class OpenAIEmbeddingProvider:
    def __init__(self, api_key: str | None = None, model: str = "text-embedding-3-small"):
        key = api_key or os.environ.get("OPENAI_API_KEY")
        if not key:
            raise RuntimeError(
                "OPENAI_API_KEY가 설정되지 않았습니다. backend/.env에 키를 추가해야 "
                "실제 임베딩을 생성할 수 있습니다."
            )
        import openai  # 키가 없는 경로에서는 import조차 필요 없게 지연 임포트

        self._client = openai.OpenAI(api_key=key)
        self._model = model

    def embed(self, text: str) -> list[float]:
        response = self._client.embeddings.create(model=self._model, input=text)
        return response.data[0].embedding


def get_embedding_provider(provider: str | None = None) -> "MockEmbeddingProvider | OpenAIEmbeddingProvider":
    """설정값(app.config.settings.embedding_provider) 하나로 mock↔실제 임베딩을 전환한다."""
    from app.config import settings

    provider = provider or settings.embedding_provider
    if provider == "mock":
        return MockEmbeddingProvider()
    if provider == "openai":
        return OpenAIEmbeddingProvider()
    raise ValueError(f"알 수 없는 embedding_provider: {provider!r} (mock/openai 중 하나여야 함)")
