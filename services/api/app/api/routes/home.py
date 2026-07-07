from fastapi import APIRouter

from app.schemas.common import ApiResponse
from app.schemas.home import HomeResponse
from app.services.home_service import get_home_data

router = APIRouter(tags=["home"])


@router.get("/home", response_model=ApiResponse[HomeResponse])
def home() -> ApiResponse[HomeResponse]:
    return ApiResponse(request_id="local_service_request", data=get_home_data())
