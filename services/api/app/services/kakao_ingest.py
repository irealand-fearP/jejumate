"""카톡 오픈채팅 실시간 수집 → RAG 증분 적재 파이프라인.

팀원이 운영하는 dm.kggstudio.com/chats에서 새 메시지를 after_id 커서로 증분
조회하고, 노이즈(이모지만/10자 미만/단순 반응)를 걸러낸 뒤 임베딩해서
rag_documents에 쌓는다. threshold(0.5)는 answer_rag_question 쪽 기준을
그대로 쓰므로 여기서는 건드리지 않는다.
"""
from __future__ import annotations

import re

import httpx

from app.core.config import settings
from app.repositories.local_store import add_kakao_rag_document, get_ingest_cursor, set_ingest_cursor
from app.services.embedding_service import embed_text

KAKAO_CHATS_URL = "https://dm.kggstudio.com/chats"
INGEST_SOURCE = "kakao_live"
MIN_CONTENT_LENGTH = 10

_EMOJI_PATTERN = re.compile(
    "[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF\U00002190-\U000021FF\U00002B00-\U00002BFF]+"
)
# ㅋㅋㅋ/ㅇㅇ/ㅎㅎ/물음표 반복처럼 반응만 있고 내용이 없는 메시지는 근거로 못 쓴다.
_REACTION_ONLY_PATTERN = re.compile(r"^[ㅋㅎㅇㄴㄷㄱㅜㅠ~!?.,\s]+$")


def _is_noise(content: str) -> bool:
    stripped = content.strip()
    if len(stripped) < MIN_CONTENT_LENGTH:
        return True
    without_emoji = _EMOJI_PATTERN.sub("", stripped).strip()
    if not without_emoji:
        return True
    if _REACTION_ONLY_PATTERN.fullmatch(stripped):
        return True
    return False


def fetch_new_chats(after_id: int) -> list[dict]:
    response = httpx.get(KAKAO_CHATS_URL, params={"after_id": after_id}, timeout=15)
    response.raise_for_status()
    return response.json().get("items", [])


def ingest_new_messages() -> tuple[int, int]:
    """새 메시지를 커서 이후로 가져와 노이즈를 거르고 임베딩·적재한다.
    (적재 건수, 갱신된 커서)를 반환. 항목 하나 처리할 때마다 커서를 전진시켜서,
    중간에 실패해도 이미 처리한 범위는 다음 실행에서 다시 안 건드린다."""
    cursor = get_ingest_cursor(INGEST_SOURCE)
    items = fetch_new_chats(cursor)
    items.sort(key=lambda item: item["id"])
    max_items = max(settings.kakao_ingest_max_items_per_run, 1)
    items = items[:max_items]

    ingested = 0
    max_id = cursor
    for item in items:
        item_id = item["id"]
        content = (item.get("content") or "").strip()
        if not _is_noise(content):
            embedding = embed_text(content)
            add_kakao_rag_document(item_id=item_id, content=content, embedding=embedding)
            ingested += 1
        max_id = max(max_id, item_id)
        set_ingest_cursor(INGEST_SOURCE, max_id)

    return ingested, max_id
