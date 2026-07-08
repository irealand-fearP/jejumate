from fastapi import APIRouter, BackgroundTasks

from app.schemas.common import ApiResponse
from app.schemas.home import HomeResponse
from app.services.home_service import get_home_data
from app.services.kakao_ingest import maybe_ingest_kakao_now

router = APIRouter(tags=["home"])


@router.get("/home", response_model=ApiResponse[HomeResponse])
def home(background_tasks: BackgroundTasks) -> ApiResponse[HomeResponse]:
    # 카톡 실시간 수집 피기백. 응답을 클라이언트에 먼저 보낸 뒤 실행되도록
    # BackgroundTasks로 등록한다(서버리스는 백그라운드 루프가 없어 조회 요청에
    # 얹는 방식 자체는 유지하되, 응답 지연에는 더 이상 영향을 주지 않는다).
    background_tasks.add_task(maybe_ingest_kakao_now)
    return ApiResponse(request_id="local_service_request", data=get_home_data())
