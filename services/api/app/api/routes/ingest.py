from fastapi import APIRouter, Header, HTTPException, Query

from app.core.config import settings
from app.schemas.common import ApiResponse
from app.schemas.ingest import KakaoIngestResponse
from app.services.kakao_ingest import ingest_new_messages

router = APIRouter(tags=["ingest"])


def _is_authorized(secret: str | None, authorization: str | None) -> bool:
    allowed_query_tokens = {token for token in [settings.ingest_secret] if token}
    allowed_bearer_tokens = {token for token in [settings.ingest_secret, settings.cron_secret] if token}

    if secret in allowed_query_tokens:
        return True
    if not authorization:
        return False
    return any(authorization == f"Bearer {token}" for token in allowed_bearer_tokens)


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

    ingested, cursor = ingest_new_messages()
    return ApiResponse(
        request_id="local_service_request",
        data=KakaoIngestResponse(ingested=ingested, cursor=cursor),
    )
