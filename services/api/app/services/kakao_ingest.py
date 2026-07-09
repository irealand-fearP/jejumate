"""카톡 오픈채팅 실시간 수집 → RAG 증분 적재 + 콜드스타트 콘텐츠 변환 파이프라인.

팀원이 운영하는 dm.kggstudio.com/chats에서 새 메시지를 after_id 커서로 증분
조회하고, 노이즈(이모지만/10자 미만/단순 반응)를 걸러낸 뒤:
1) 임베딩해서 rag_documents에 쌓고(threshold 0.5는 answer_rag_question 쪽 기준을
   그대로 씀 — 여기서는 안 건드림),
2) OpenAI로 분류해서 동행 구인은 모임 후보로, 중고·나눔·질문은 생활게시판으로
   자동 변환한다(콜드스타트 피드).
"""
from __future__ import annotations

import logging
import re

import httpx

from app.core.config import settings
from app.repositories.local_store import (
    add_kakao_rag_document,
    create_coldstart_board_post,
    create_coldstart_meeting,
    get_coldstart_count_today,
    get_ingest_cursor,
    has_coldstart_content,
    set_ingest_cursor,
    try_claim_kakao_ingest_attempt,
)
from app.services.content_classifier import classify_message
from app.services.embedding_service import embed_text

logger = logging.getLogger(__name__)

KAKAO_CHATS_URL = "https://dm.kggstudio.com/chats"
INGEST_SOURCE = "kakao_live"
MIN_CONTENT_LENGTH = 10
# 하루 자동 변환 상한. 초기값 30은 이틀 연속 정오 전에 소진돼 오후 메시지가 서비스에
# 등록되지 않는 병목이 됐다(2026-07-09 사용자 리포트). 스팸 폭주 방어선 역할만 하도록
# 실제 채팅량(하루 수백 건, 필터 통과분은 그 일부)을 넉넉히 웃도는 값으로 상향.
COLDSTART_DAILY_LIMIT = 300

_EMOJI_PATTERN = re.compile(
    "[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF\U00002190-\U000021FF\U00002B00-\U00002BFF]+"
)
# ㅋㅋㅋ/ㅇㅇ/ㅎㅎ/물음표 반복처럼 반응만 있고 내용이 없는 메시지는 근거로 못 쓴다.
_REACTION_ONLY_PATTERN = re.compile(r"^[ㅋㅎㅇㄴㄷㄱㅜㅠ~!?.,\s]+$")

# 카카오톡 자체 시스템 알림(입장/퇴장, 삭제된 메시지 표시)이 실제 대화 내용에 그대로
# 붙어 들어오는 경우가 있다(실데이터 점검 결과 1,971건 중 223건, 11.3%). 닉네임 구간을
# 물음표/느낌표/마침표가 없는 짧은 문자열로 제한해, 앞에 붙은 실제 문장까지 같이
# 지워지지 않게 한다.
_SYSTEM_NOTICE_PATTERN = re.compile(
    r"[^\n?!.~,]{1,20}님이 (들어왔습니다|나갔습니다)\.?|메시지가 삭제되었습니다\.?"
)

_PHONE_PATTERN = re.compile(r"01[016789][-.\s]?\d{3,4}[-.\s]?\d{4}")
# 지역번호 유선전화(02, 031~064 등). 상업 광고·기관 안내에서 종종 등장(예: 064-xxx-xxxx).
_LANDLINE_PATTERN = re.compile(r"0(2|[3-6][1-4])[-.\s]?\d{3,4}[-.\s]?\d{4}")
_URL_PATTERN = re.compile(r"https?://\S+")
_INSTAGRAM_HANDLE_PATTERN = re.compile(r"@[A-Za-z0-9_.]{2,30}")


def _strip_system_notices(content: str) -> str:
    """카카오톡 자체 시스템 알림(입장/퇴장, 삭제된 메시지 표시)만 제거하고 나머지
    실제 대화 내용은 그대로 살린다."""
    cleaned = _SYSTEM_NOTICE_PATTERN.sub("", content)
    return re.sub(r"[ \t]{2,}", " ", cleaned).strip()


_TYPE_TO_BOARD_CATEGORY = {
    "secondhand": "중고거래",
    "share": "나눔",
    "question": "질문게시판",
}


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


def mask_personal_info(text: str) -> str:
    """전화번호(휴대폰·유선)·URL·인스타그램 핸들을 지워서 원문을 서비스 콘텐츠
    (모임/게시판/RAG 근거)로 옮길 때 개인정보·연락처가 그대로 노출되지 않게 한다."""
    text = _URL_PATTERN.sub("[링크 비공개]", text)
    text = _PHONE_PATTERN.sub("[연락처 비공개]", text)
    text = _LANDLINE_PATTERN.sub("[연락처 비공개]", text)
    text = _INSTAGRAM_HANDLE_PATTERN.sub("[SNS 계정 비공개]", text)
    return text


def fetch_new_chats(after_id: int) -> list[dict]:
    response = httpx.get(KAKAO_CHATS_URL, params={"after_id": after_id}, timeout=15)
    response.raise_for_status()
    return response.json().get("items", [])


def convert_to_coldstart_content(*, item_id: int, content: str, created_at: str) -> str | None:
    """분류 후 모임/게시판으로 변환한다. 실제로 뭔가 만들었으면 콘텐츠 타입 문자열을,
    아니면(기타/이미 변환됨/일일 상한 도달) None을 반환한다."""
    if has_coldstart_content(item_id):
        return None
    if get_coldstart_count_today() >= COLDSTART_DAILY_LIMIT:
        return None

    result = classify_message(content)
    content_type = result["type"]
    title = result["title"] or content[:20]

    if content_type == "meetup":
        create_coldstart_meeting(
            item_id=item_id,
            title=title,
            meeting_category=result["meeting_category"] or "move",
            description=content,
            created_at=created_at,
        )
        return content_type

    board_category = _TYPE_TO_BOARD_CATEGORY.get(content_type)
    if board_category:
        create_coldstart_board_post(item_id=item_id, category=board_category, title=title, body=content)
        return content_type

    return None


def ingest_new_messages(*, max_items: int | None = None) -> tuple[int, int]:
    """새 메시지를 커서 이후로 가져와 노이즈를 거르고 임베딩·적재 + 콜드스타트 변환한다.
    (적재 건수, 갱신된 커서)를 반환. 항목 하나 처리할 때마다 커서를 전진시켜서,
    중간에 실패해도 이미 처리한 범위는 다음 실행에서 다시 안 건드린다.

    max_items를 안 넘기면 크론/수동 트리거·로컬 백그라운드 루프용 기본 상한
    (kakao_ingest_max_items_per_run, 넉넉함)을 쓴다. 피기백 경로(maybe_ingest_kakao_now)는
    실사용 요청을 막지 않도록 훨씬 작은 상한을 명시적으로 넘긴다."""
    cursor = get_ingest_cursor(INGEST_SOURCE)
    items = fetch_new_chats(cursor)
    items.sort(key=lambda item: item["id"])
    effective_max_items = max_items if max_items is not None else settings.kakao_ingest_max_items_per_run
    effective_max_items = max(effective_max_items, 1)
    items = items[:effective_max_items]

    ingested = 0
    max_id = cursor
    for item in items:
        item_id = item["id"]
        content = mask_personal_info((item.get("content") or "").strip())
        content = _strip_system_notices(content)
        if not _is_noise(content):
            embedding = embed_text(content)
            add_kakao_rag_document(item_id=item_id, content=content, embedding=embedding)
            convert_to_coldstart_content(item_id=item_id, content=content, created_at=item.get("created_at", ""))
            ingested += 1
        max_id = max(max_id, item_id)
        set_ingest_cursor(INGEST_SOURCE, max_id)

    return ingested, max_id


def maybe_ingest_kakao_now() -> None:
    """자주 호출되는 조회 엔드포인트(모임/게시판/홈)에 얹혀 카톡 수집을 사실상
    상시로 만든다. Vercel 서버리스는 요청이 끝나면 프로세스가 죽어 백그라운드
    루프를 못 돌리므로, 조회 요청을 처리하는 김에 짬을 내 실행한다 — 마지막
    시도로부터 kakao_poll_interval_seconds(기본 10~30초대)가 지났을 때만.

    동시 요청 대비: try_claim_kakao_ingest_attempt()가 원자적 UPDATE로 한 번에
    하나만 통과시킨다. 카톡 API가 응답 없거나 에러여도, 혹은 그 외 어떤 예외가
    나도 절대 이 함수 밖(본 요청의 모임/게시판/홈 응답)으로 전파시키지 않는다 —
    조용히 넘어가고 다음 요청에서 다시 시도한다.

    이 함수는 동기(블로킹)로 실행되고 응답 완성 전에 끝나야 한다 — BackgroundTasks로
    응답 이후에 돌려봤지만(커밋 2f8f0a6), Vercel Python 런타임이 백그라운드 작업
    완료까지 응답을 안 끝내는 걸 실측으로 확인해(배포판에서 2.1~12초, 사실상 동기와
    동일) 되돌렸다. 그래서 한 번에 kakao_ingest_piggyback_max_items(기본 1)건만
    처리한다 — 실사용 요청에 그대로 얹히는 경로라 임베딩 호출이 쌓이면(1건당
    0.5~1초) 그대로 응답 지연이 되기 때문이다. 대량으로 밀려 있으면 나머지는
    크론(GET /api/ingest/kakao, 5분 주기)이 kakao_ingest_max_items_per_run(기본
    50)로 마저 처리한다."""
    try:
        if not try_claim_kakao_ingest_attempt(INGEST_SOURCE, settings.kakao_poll_interval_seconds):
            return
        count, cursor = ingest_new_messages(max_items=settings.kakao_ingest_piggyback_max_items)
        if count:
            logger.info("피기백 카톡 수집: %s건 적재, 커서 %s", count, cursor)
    except Exception:  # noqa: BLE001 - 본 요청(조회 API)은 절대 실패시키면 안 된다.
        logger.exception("피기백 카톡 수집 실패 — 본 요청에는 영향 없음")
