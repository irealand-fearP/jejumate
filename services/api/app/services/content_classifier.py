"""카톡 메시지를 콜드스타트 콘텐츠(모임 후보/생활게시판)로 분류한다.

노이즈 필터를 통과한 메시지만 대상으로 하며(비용 절약), OpenAI Chat Completions로
한 번에 [유형, 제목, 모임이면 카테고리]를 뽑는다.
"""
from __future__ import annotations

import json
import os

from app.core.config import settings

CHAT_MODEL = "gpt-5-mini"

# 생활게시판 기존 3카테고리 + 모임 후보(meetup) + 그 외(other, 변환 안 함).
CONTENT_TYPES = ["meetup", "secondhand", "share", "question", "other"]
MEETING_CATEGORIES = ["meal", "work", "move", "coffee", "run"]

_SYSTEM_PROMPT = """너는 제주 대학생 오픈채팅방 메시지를 분류하는 도우미다.
메시지를 다음 중 정확히 하나로 분류해라:
- meetup: 같이 갈 사람/동행을 구하는 글 (예: "내일 1시 애월 가실 분", "택시팟 구해요")
- secondhand: 중고거래 글
- share: 무료 나눔 글
- question: 궁금한 걸 묻는 글
- other: 위에 안 속하는 잡담/일상 대화

meetup이면 함께 갈 장소·활동을 20자 이내로 새로 요약한 title과, 다음 중 가장 가까운
meeting_category를 하나 골라라: meal(식사)/work(작업·공부)/move(이동·택시)/coffee(카페)/
run(운동·산책). meetup이 아니면 title은 20자 이내 요약, meeting_category는 null로 둬라.
other면 title도 빈 문자열로 둬라.

JSON으로만 답해라: {"type": "...", "title": "...", "meeting_category": "..." 또는 null}"""


def classify_message(content: str) -> dict:
    from openai import OpenAI  # 키 없는 경로에서는 import조차 필요 없게 지연 임포트

    api_key = settings.openai_api_key or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return {"type": "other", "title": "", "meeting_category": None}

    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=CHAT_MODEL,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": content},
        ],
        response_format={"type": "json_object"},
        # gpt-5-mini(추론 모델)는 temperature 커스텀 값을 지원하지 않는다(기본값 1만 허용).
        # 대신 reasoning_effort로 비용/속도를 낮춘다 — 이 분류는 단순 태스크라 minimal로 충분.
        reasoning_effort="minimal",
        max_completion_tokens=200,
    )
    try:
        data = json.loads(response.choices[0].message.content or "{}")
    except json.JSONDecodeError:
        return {"type": "other", "title": "", "meeting_category": None}

    content_type = data.get("type")
    if content_type not in CONTENT_TYPES:
        content_type = "other"
    meeting_category = data.get("meeting_category")
    if meeting_category not in MEETING_CATEGORIES:
        meeting_category = None
    title = (data.get("title") or "").strip()[:20]

    return {"type": content_type, "title": title, "meeting_category": meeting_category}
