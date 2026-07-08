from fastapi import APIRouter

from app.schemas.common import ApiResponse
from app.schemas.home import HomeResponse
from app.services.home_service import get_home_data
from app.services.kakao_ingest import maybe_ingest_kakao_now

router = APIRouter(tags=["home"])


@router.get("/home", response_model=ApiResponse[HomeResponse])
def home() -> ApiResponse[HomeResponse]:
    # 카톡 실시간 수집 피기백(서버리스는 백그라운드 루프가 없어 조회 요청에 얹는다).
    maybe_ingest_kakao_now()
    return ApiResponse(request_id="local_service_request", data=get_home_data())
