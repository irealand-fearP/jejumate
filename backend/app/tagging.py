"""
2차 태깅: 규칙 필터를 통과한 메시지의 최종 category/post_type/status를 정한다.

- MockLLMTagger: API 키 없이 파이프라인을 검증하기 위한 규칙 기반 대체 구현.
- AnthropicLLMTagger: 실제 서비스용. ANTHROPIC_API_KEY가 있어야 동작한다.
  (이 개발 환경에는 키가 없어 "키가 없으면 명확히 에러를 낸다"만 테스트했고,
  실제 API 호출 자체는 검증하지 못했다 — 완료 보고에 명시)
"""
import json
import os
from dataclasses import dataclass
from typing import Protocol

from app.rule_filter import match_categories

PARTY_CATEGORIES = {"ride", "drink", "run", "walk", "tour"}
INFO_CATEGORIES = {"food", "cafe", "stay", "living", "qna"}
CATEGORY_PRIORITY = ("ride", "drink", "run", "walk", "tour", "food", "cafe", "stay", "living", "qna")

MOBILIZE_KEYWORDS = (
    "구해요", "구합니다", "구합니당", "구해용", "모집",
    "같이 가실", "같이가요", "타실 분", "가실분", "분 구",
)
CLOSED_KEYWORDS = ("마감", "종료", "끝났", "구했어요", "구했습니다")


@dataclass
class TagResult:
    post_type: str
    category: str
    status: str


class LLMTagger(Protocol):
    def tag(self, content: str) -> TagResult: ...


class MockLLMTagger:
    """규칙 필터 후보 + 모집 의도 키워드로 실제 LLM 판단을 흉내낸다."""

    def tag(self, content: str) -> TagResult:
        candidates = match_categories(content) or {"qna"}
        is_mobilizing = any(keyword in content for keyword in MOBILIZE_KEYWORDS)

        party_candidates = candidates & PARTY_CATEGORIES
        info_candidates = candidates & INFO_CATEGORIES

        if is_mobilizing and party_candidates:
            pool = party_candidates
        elif not is_mobilizing and info_candidates:
            pool = info_candidates
        else:
            pool = candidates

        category = next(c for c in CATEGORY_PRIORITY if c in pool)
        post_type = "party" if category in PARTY_CATEGORIES else "info"
        status = "closed" if any(keyword in content for keyword in CLOSED_KEYWORDS) else "active"
        return TagResult(post_type=post_type, category=category, status=status)


_SYSTEM_PROMPT = """너는 제주 런케이션 오픈채팅 메시지를 분류하는 태거다.
아래 카테고리 중 하나(category), post_type(party 또는 info), status(active 또는 closed)를
JSON 하나로만 답해라. 다른 텍스트는 절대 출력하지 마라.

party 카테고리: ride(이동팟), drink(술자리), run(러닝/운동), walk(산책/나들이), tour(맛집/카페 동행)
info 카테고리: food(맛집), cafe(카페/감성장소), stay(숙소), living(생활편의), qna(질문답변)

출력 형식: {"post_type": "...", "category": "...", "status": "..."}
"""


class AnthropicLLMTagger:
    """실제 서비스용 LLM 태거. ANTHROPIC_API_KEY 필요."""

    def __init__(self, api_key: str | None = None, model: str = "claude-sonnet-5"):
        key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY가 설정되지 않았습니다. backend/.env에 키를 추가해야 "
                "실제 LLM 태깅을 실행할 수 있습니다."
            )
        import anthropic  # 키가 없는 경로에서는 import조차 필요 없게 지연 임포트

        self._client = anthropic.Anthropic(api_key=key)
        self._model = model

    def tag(self, content: str) -> TagResult:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=200,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": content}],
        )
        raw_text = response.content[0].text
        parsed = json.loads(raw_text)
        return TagResult(
            post_type=parsed["post_type"],
            category=parsed["category"],
            status=parsed["status"],
        )
