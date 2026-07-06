"""
mock↔실제 제공자 전환이 환경변수(설정) 하나로 되는지 확인한다.

나중에 LLM은 OpenAI 단일(GPT 태깅 + OpenAI 임베딩)로 통일할 예정이라
"openai"가 실제 제공자의 기본 후보가 된다. 오늘은 API 키가 없어 설정 기본값이
"mock"이고, 실제 호출은 여전히 API 키가 없으면 에러를 낸다.
"""
import pytest

from app.embedding import MockEmbeddingProvider, OpenAIEmbeddingProvider, get_embedding_provider
from app.tagging import AnthropicLLMTagger, MockLLMTagger, OpenAILLMTagger, get_llm_tagger


def test_get_llm_tagger_mock():
    assert isinstance(get_llm_tagger("mock"), MockLLMTagger)


def test_get_llm_tagger_openai_with_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "dummy-key-not-real")
    assert isinstance(get_llm_tagger("openai"), OpenAILLMTagger)


def test_get_llm_tagger_anthropic_with_key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "dummy-key-not-real")
    assert isinstance(get_llm_tagger("anthropic"), AnthropicLLMTagger)


def test_get_llm_tagger_unknown_provider_raises():
    with pytest.raises(ValueError, match="llm_provider"):
        get_llm_tagger("unknown")


def test_get_embedding_provider_mock():
    assert isinstance(get_embedding_provider("mock"), MockEmbeddingProvider)


def test_get_embedding_provider_openai_with_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "dummy-key-not-real")
    assert isinstance(get_embedding_provider("openai"), OpenAIEmbeddingProvider)


def test_openai_tagger_requires_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        OpenAILLMTagger()
