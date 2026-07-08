from fastapi import APIRouter

from app.schemas.common import ApiResponse
from app.schemas.home import HomeResponse
from app.services.home_service import get_home_data

router = APIRouter(tags=["home"])


@router.get("/home", response_model=ApiResponse[HomeResponse])
def home() -> ApiResponse[HomeResponse]:
    # 카톡 실시간 수집 피기백은 여기서 더 이상 호출하지 않는다. 캡 1건 + BackgroundTasks까지
    # 다 시도해봤지만 Vercel 프로덕션 실측(연속 호출 2.5~11초)이 핵심 화면(모임생성→
    # 신청→승인→채팅) 응답 속도를 여전히 갉아먹어, 실시간성보다 핵심 기능 속도를
    # 우선했다(maybe_ingest_kakao_now 함수 자체는 남겨둠 — 플랫폼이 바뀌면 재사용 가능).
    # 카톡 수집은 GitHub Actions 5분 크론(.github/workflows/kakao-ingest.yml)만으로 계속된다.
    return ApiResponse(request_id="local_service_request", data=get_home_data())
