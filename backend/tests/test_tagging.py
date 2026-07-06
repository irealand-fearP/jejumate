"""
LLM 태깅 인터페이스 테스트 (태스크4).

MockLLMTagger로 실제 API 키 없이 파이프라인 로직(모집 의도 → party,
질문/추천 의도 → info, 마감 키워드 → closed)을 검증한다.
AnthropicLLMTagger는 실제 호출 코드는 있으나 API 키가 없어 이 환경에서는
"키가 없으면 명확히 에러"만 검증한다(실제 호출 자체는 미검증, 완료 보고에 명시).
"""
import pytest

from app.tagging import AnthropicLLMTagger, MockLLMTagger


@pytest.fixture()
def tagger():
    return MockLLMTagger()


def test_party_ride_intent_tagged_as_party(tagger):
    result = tagger.tag("지금 함덕해수욕장 택시팟 구해요!")
    assert result.post_type == "party"
    assert result.category == "ride"
    assert result.status == "active"


def test_info_food_question_tagged_as_info(tagger):
    result = tagger.tag("흑돼지 맛집 추천해주세요")
    assert result.post_type == "info"
    assert result.category == "food"


def test_closed_keyword_sets_status_closed(tagger):
    result = tagger.tag("함덕 택시팟 구해요 -> 마감되었습니다")
    assert result.status == "closed"


def test_overlap_category_prefers_party_category_when_mobilizing(tagger):
    # "카페 동행"(tour, party성) vs "카페"(cafe, info성) 둘 다 걸리는 문장.
    # "같이 가실 분" 모집 의도가 있으므로 party 카테고리(tour)를 우선한다.
    result = tagger.tag("카페 동행 같이 가실 분 구해요")
    assert result.post_type == "party"
    assert result.category == "tour"


def test_anthropic_tagger_requires_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        AnthropicLLMTagger()
