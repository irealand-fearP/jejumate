from fastapi import APIRouter

from app.schemas.common import ApiResponse
from app.schemas.resources import ProfilePreviewResponse
from app.services.resource_service import get_profile_preview_data

router = APIRouter(tags=["profile"])


@router.get("/profile/preview", response_model=ApiResponse[ProfilePreviewResponse])
def profile_preview() -> ApiResponse[ProfilePreviewResponse]:
    return ApiResponse(request_id="local_service_request", data=get_profile_preview_data())
