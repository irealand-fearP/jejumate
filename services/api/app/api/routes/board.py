from fastapi import APIRouter

from app.schemas.common import ApiResponse
from app.schemas.resources import BoardResponse
from app.services.resource_service import get_board_data

router = APIRouter(tags=["board"])


@router.get("/board", response_model=ApiResponse[BoardResponse])
def board() -> ApiResponse[BoardResponse]:
    return ApiResponse(request_id="local_service_request", data=get_board_data())
