from fastapi import APIRouter, HTTPException

from app.core.config import settings
from app.schemas.common import ApiResponse
from app.schemas.ingest import KakaoIngestResponse
from app.services.kakao_ingest import ingest_new_messages

router = APIRouter(tags=["ingest"])


@router.get("/ingest/kakao", response_model=ApiResponse[KakaoIngestResponse])
def ingest_kakao(secret: str) -> ApiResponse[KakaoIngestResponse]:
    """배포(서버리스)는 상시 폴링이 안 되므로 크론/수동으로 이 엔드포인트를 호출해
    카톡 신규 메시지를 증분 수집한다. INGEST_SECRET 환경변수와 일치해야 동작한다."""
    if not settings.ingest_secret or secret != settings.ingest_secret:
        raise HTTPException(status_code=403, detail="권한이 없어요")

    ingested, cursor = ingest_new_messages()
    return ApiResponse(
        request_id="local_service_request",
        data=KakaoIngestResponse(ingested=ingested, cursor=cursor),
    )
