from fastapi import APIRouter, File, Header, HTTPException, Query, UploadFile

from app.core.config import settings
from app.repositories.local_store import cleanup_expired_parties
from app.repositories.local_store import count_pending_kakao_upload_messages
from app.schemas.common import ApiResponse
from app.schemas.ingest import (
    KakaoIngestResponse,
    KakaoProcessResponse,
    KakaoUploadFileResponse,
    KakaoUploadRequest,
    KakaoUploadResponse,
    PartyCleanupResponse,
)
from app.services.kakao_export import parse_kakao_export_text
from app.services.kakao_ingest import (
    enqueue_uploaded_messages,
    ingest_uploaded_messages,
)

router = APIRouter(tags=["ingest"])


def _is_authorized(secret: str | None, authorization: str | None) -> bool:
    allowed_query_tokens = {token for token in [settings.ingest_secret] if token}
    allowed_bearer_tokens = {token for token in [settings.ingest_secret, settings.cron_secret] if token}

    if secret in allowed_query_tokens:
        return True
    if not authorization:
        return False
    return any(authorization == f"Bearer {token}" for token in allowed_bearer_tokens)


def _is_kakao_upload_authorized(authorization: str | None) -> bool:
    token = settings.kakao_upload_secret
    return bool(token and authorization == f"Bearer {token}")


@router.post(
    "/ingest/kakao/messages",
    response_model=ApiResponse[KakaoUploadResponse],
)
def upload_kakao_messages(
    payload: KakaoUploadRequest,
    authorization: str | None = Header(default=None),
) -> ApiResponse[KakaoUploadResponse]:
    """Windows 카카오톡 내보내기 수집기가 보내는 메시지를 멱등 저장·처리한다."""
    if not settings.kakao_upload_secret:
        raise HTTPException(status_code=503, detail="카카오 업로드가 설정되지 않았어요")
    if not _is_kakao_upload_authorized(authorization):
        raise HTTPException(status_code=403, detail="권한이 없어요")

    messages = [message.model_dump() for message in payload.messages]
    accepted = enqueue_uploaded_messages(messages)
    received = len(messages)
    return ApiResponse(
        request_id="kakao_upload_request",
        data=KakaoUploadResponse(
            received=received,
            accepted=accepted,
            duplicates=received - accepted,
            pending=count_pending_kakao_upload_messages(),
        ),
    )


@router.post(
    "/ingest/kakao/upload-file",
    response_model=ApiResponse[KakaoUploadFileResponse],
)
async def upload_kakao_export_file(
    file: UploadFile = File(...),
    authorization: str | None = Header(default=None),
) -> ApiResponse[KakaoUploadFileResponse]:
    """사장님이 카톡 PC 대화 내보내기 .txt를 직접 올리면 파싱부터 RAG 색인까지 한
    번에 처리한다. 자동 스케줄러 없이 원할 때만 반영하는 수동 업로드 경로다."""
    if not settings.kakao_upload_secret:
        raise HTTPException(status_code=503, detail="카카오 업로드가 설정되지 않았어요")
    if not _is_kakao_upload_authorized(authorization):
        raise HTTPException(status_code=403, detail="권한이 없어요")

    raw_bytes = await file.read()
    try:
        text = raw_bytes.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(
            status_code=400, detail="UTF-8로 인코딩된 텍스트 파일만 올릴 수 있어요"
        ) from exc

    try:
        exported = parse_kakao_export_text(text)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    messages = [message.to_api_payload() for message in exported.messages]
    parsed = len(messages)
    accepted = enqueue_uploaded_messages(messages) if messages else 0

    # 새로 쌓인 만큼만 즉시 처리해 업로드하자마자 RAG에 반영한다.
    indexed = 0
    if accepted:
        indexed, _filtered, _pending = ingest_uploaded_messages(max_items=accepted)

    return ApiResponse(
        request_id="kakao_upload_file_request",
        data=KakaoUploadFileResponse(
            parsed=parsed,
            accepted=accepted,
            duplicates=parsed - accepted,
            indexed=indexed,
        ),
    )


@router.post(
    "/ingest/kakao/process",
    response_model=ApiResponse[KakaoProcessResponse],
)
def process_uploaded_kakao_messages(
    max_items: int = Query(default=1, ge=1, le=10),
    authorization: str | None = Header(default=None),
) -> ApiResponse[KakaoProcessResponse]:
    """저장된 Windows 수집기 큐를 소량 처리한다. 느린 AI 호출과 업로드를 분리한다."""
    if not settings.kakao_upload_secret:
        raise HTTPException(status_code=503, detail="카카오 업로드가 설정되지 않았어요")
    if not _is_kakao_upload_authorized(authorization):
        raise HTTPException(status_code=403, detail="권한이 없어요")

    ingested, filtered, pending = ingest_uploaded_messages(max_items=max_items)
    return ApiResponse(
        request_id="kakao_process_request",
        data=KakaoProcessResponse(
            ingested=ingested,
            filtered=filtered,
            pending=pending,
        ),
    )


@router.get("/ingest/kakao", response_model=ApiResponse[KakaoIngestResponse])
def ingest_kakao(
    secret: str | None = Query(default=None),
    authorization: str | None = Header(default=None),
) -> ApiResponse[KakaoIngestResponse]:
    """카톡 신규 메시지를 증분 수집한다.

    수동 호출은 ?secret=..., Vercel Cron은 Authorization: Bearer <INGEST_SECRET>로
    인증한다. 시크릿 값은 로그나 응답에 포함하지 않는다.
    """
    if not _is_authorized(secret, authorization):
        raise HTTPException(status_code=403, detail="권한이 없어요")

    # 기존 dm.kggstudio.com 폴링 대신 Windows 내보내기 업로드 큐를 처리한다.
    # cursor 필드는 기존 크론 응답 호환을 위해 남은 큐 건수를 담는다.
    ingested, _filtered, pending = ingest_uploaded_messages(
        max_items=settings.kakao_ingest_max_items_per_run
    )
    return ApiResponse(
        request_id="local_service_request",
        data=KakaoIngestResponse(ingested=ingested, cursor=pending),
    )


@router.get("/cleanup/expired-parties", response_model=ApiResponse[PartyCleanupResponse])
def cleanup_parties(
    secret: str | None = Query(default=None),
    authorization: str | None = Header(default=None),
) -> ApiResponse[PartyCleanupResponse]:
    """마감 2일 지난 사용자 파티를 실제 삭제한다(신청·채팅 cascade).

    서버리스(Vercel) 배포용 트리거 — 자체 서버는 백그라운드 루프가 같은 함수를
    주기 실행하므로 이 엔드포인트가 없어도 정리가 돌아간다. 인증은 ingest와 동일.
    """
    if not _is_authorized(secret, authorization):
        raise HTTPException(status_code=403, detail="권한이 없어요")

    deleted = cleanup_expired_parties()
    return ApiResponse(
        request_id="local_service_request",
        data=PartyCleanupResponse(deleted=deleted),
    )
