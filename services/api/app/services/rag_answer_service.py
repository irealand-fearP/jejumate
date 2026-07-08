"""RAG 근거 기반 답변 생성 + 신뢰도 검증.

gpt-5-mini를 한 번만 호출해 (1) 주어진 근거만으로 답변을 만들고 (2) 그 답변이
각 근거 문서와 실제로 부합하는지 스스로 표시하게 한다. 호출을 나누지 않는 이유는
비용 절약(팀 예산이 크지 않음) — 근거가 없을 때는 아예 호출하지 않는 것과 같은 맥락.
"""
from __future__ import annotations

import json
import os

from app.core.config import settings

ANSWER_MODEL = "gpt-5-mini"
MAX_COMPLETION_TOKENS = 700

_SYSTEM_PROMPT = """너는 제주 대학생 커뮤니티 정보를 안내하는 도우미다.
아래 [근거 문서]는 실제 카톡 오픈채팅에서 학생들이 남긴 글이다. 대부분 "OO 구해요!",
"OO 하실 분 계신가요?"처럼 특정 시점의 개별 모집·질문 글이지만, 질문과 주제가 실제로
일치한다면 그 자체가 충분히 좋은 근거다. 예를 들어 "함덕 해수욕장 택시팟 있나요?"라는
질문에 "지금 함덕 해수욕장에서 택시팟 구해요!" 같은 근거가 있다면, 이는 학생들이
실제로 이렇게 택시팟을 구한다는 확실한 증거이므로 "네, 학생들이 이런 식으로 택시팟을
구하고 있어요"처럼 근거 내용을 바탕으로 자신 있게 답하라. 개별 모집 글이라는 이유만
으로, 또는 "지금 이 순간에도 유효한지 모른다"는 이유만으로 회피하지 마라.

"근거에 없는 내용을 추측하지 말라"는 것은 근거에 전혀 등장하지 않는 새로운 사실
(예: 근거에 없는 장소·서비스·요금·운영시간)을 지어내지 말라는 뜻이다. 근거에 있는
내용을 그대로 요약하거나, 여러 근거에 걸쳐 공통되는 패턴을 설명하는 것은 추측이
아니라 근거를 정확히 활용하는 것이니 적극적으로 해라.

answer에 "제공된 정보로는 답변하기 어렵습니다"라고 쓰는 건 근거 문서들이 질문
주제와 실제로 무관할 때만이다. 근거 중 하나라도 질문 주제와 실제로 관련 있다면
반드시 그 내용을 바탕으로 답하고, 회피 답변을 선택하지 마라.

답변을 만든 뒤, [근거 문서] 각각이 방금 만든 답변 내용을 실제로 뒷받침하는지
스스로 다시 확인해서 citations 배열에 근거 개수만큼 하나씩 표시해라(과장하지 말고
정직하게 판단할 것). 만약 회피 답변을 선택했다면, 그건 근거들이 주제와 무관했기
때문이므로 그 근거들은 모두 supports: false로 표시해라 — 회피 답변 자체를 근거가
"뒷받침"한다고 표시하면 안 된다(신뢰도 점수가 실제와 반대로 나오게 된다).

JSON으로만 답해라:
{"answer": "...", "citations": [{"index": 0, "supports": true}, ...]}"""


class RagAnswerResult:
    def __init__(self, answer: str, supports: list[bool]):
        self.answer = answer
        self.supports = supports


def _build_user_content(question: str, documents: list[dict]) -> str:
    evidence_text = "\n\n".join(
        f"[근거 {doc['index']}] {doc['title']}\n{doc['body']}" for doc in documents
    )
    return f"[근거 문서]\n{evidence_text}\n\n[질문]\n{question}"


def generate_verified_answer(*, question: str, documents: list[dict]) -> RagAnswerResult:
    """documents: [{"index": int, "title": str, "body": str}, ...] (threshold 통과분만 전달).

    반환하는 supports는 documents와 같은 순서·길이의 bool 리스트다.
    """
    api_key = settings.openai_api_key or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY가 설정되지 않았습니다. services/api/.env에 키를 추가해야 "
            "RAG 답변을 생성할 수 있습니다."
        )

    import openai  # 키 없는 경로에서는 import조차 필요 없게 지연 임포트

    client = openai.OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=ANSWER_MODEL,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": _build_user_content(question, documents)},
        ],
        response_format={"type": "json_object"},
        reasoning_effort="minimal",
        max_completion_tokens=MAX_COMPLETION_TOKENS,
    )

    try:
        data = json.loads(response.choices[0].message.content or "{}")
    except json.JSONDecodeError:
        data = {}

    answer = (data.get("answer") or "").strip()
    if not answer:
        answer = "제공된 정보로는 답변하기 어렵습니다."

    citations = data.get("citations")
    if not isinstance(citations, list):
        citations = []
    support_by_index: dict[int, bool] = {}
    for item in citations:
        if isinstance(item, dict) and isinstance(item.get("index"), int):
            support_by_index[item["index"]] = bool(item.get("supports"))

    supports = [support_by_index.get(doc["index"], False) for doc in documents]
    return RagAnswerResult(answer=answer, supports=supports)


def confidence_grade(supports: list[bool]) -> str:
    """근거 개수 대비 실제로 부합한 근거 비율로 등급을 매긴다.

    - none: 근거가 아예 없었던 경우(LLM 호출도 안 함)
    - high: 근거 전부가 답변을 뒷받침
    - medium: 일부만 뒷받침
    - low: 근거가 있었지만 하나도 뒷받침하지 못함(환각 의심)
    """
    total = len(supports)
    if total == 0:
        return "none"
    matched = sum(1 for supported in supports if supported)
    if matched == total:
        return "high"
    if matched > 0:
        return "medium"
    return "low"
