from fastapi import APIRouter

from app.schemas.common import ApiResponse
from app.schemas.home import HomeResponse
from app.services.home_service import get_home_data
from app.services.kakao_ingest import maybe_ingest_kakao_now

router = APIRouter(tags=["home"])


@router.get("/home", response_model=ApiResponse[HomeResponse])
def home() -> ApiResponse[HomeResponse]:
    # 카톡 실시간 수집 피기백(서버리스는 백그라운드 루프가 없어 조회 요청에 얹는다).
    # BackgroundTasks로 응답 이후 실행되게 해봤지만(2f8f0a6), 실측 결과 Vercel Python
    # 런타임이 백그라운드 작업 완료까지 응답을 안 끝내(사실상 동기와 동일하면서
    # 코드만 복잡해짐) 되돌렸다 — 그래서 그냥 동기 호출 + 처리 건수를 아주 작게
    # 캡(kakao_ingest_piggyback_max_items)하는 쪽으로 지연을 줄인다.
    maybe_ingest_kakao_now()
    return ApiResponse(request_id="local_service_request", data=get_home_data())
