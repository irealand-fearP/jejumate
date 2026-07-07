from fastapi import APIRouter

from app.schemas.common import ApiResponse
from app.schemas.resources import PoliciesResponse
from app.services.resource_service import get_policies_data

router = APIRouter(tags=["policies"])


@router.get("/policies", response_model=ApiResponse[PoliciesResponse])
def policies() -> ApiResponse[PoliciesResponse]:
    return ApiResponse(request_id="local_service_request", data=get_policies_data())
