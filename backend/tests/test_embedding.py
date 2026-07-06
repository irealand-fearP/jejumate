"""
임베딩 인터페이스 테스트 (태스크4).

MockEmbeddingProvider로 API 키 없이 파이프라인의 벡터 저장 경로를 검증한다.
OpenAIEmbeddingProvider는 키가 없으면 명확히 에러만 낸다는 것만 확인한다
(실제 API 호출 자체는 이 환경에서 검증 불가).
"""
import pytest

from app.embedding import MockEmbeddingProvider, OpenAIEmbeddingProvider


def test_mock_embedding_returns_1536_dim_vector():
    provider = MockEmbeddingProvider()
    vector = provider.embed("함덕 택시팟 구해요")
    assert len(vector) == 1536
    assert all(isinstance(v, float) for v in vector)


def test_mock_embedding_is_deterministic_for_same_text():
    provider = MockEmbeddingProvider()
    assert provider.embed("같은 문장") == provider.embed("같은 문장")


def test_mock_embedding_differs_for_different_text():
    provider = MockEmbeddingProvider()
    assert provider.embed("문장 A") != provider.embed("문장 B")


def test_openai_embedding_requires_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        OpenAIEmbeddingProvider()
