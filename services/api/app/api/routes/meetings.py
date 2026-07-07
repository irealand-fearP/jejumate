from fastapi import APIRouter

from app.schemas.common import ApiResponse
from app.schemas.resources import MeetingsResponse
from app.services.resource_service import get_meetings_data

router = APIRouter(tags=["meetings"])


@router.get("/meetings", response_model=ApiResponse[MeetingsResponse])
def meetings() -> ApiResponse[MeetingsResponse]:
    return ApiResponse(request_id="local_service_request", data=get_meetings_data())
