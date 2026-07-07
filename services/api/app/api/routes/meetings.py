from fastapi import APIRouter, HTTPException

from app.repositories.local_store import (
    AlreadyProcessedError,
    ApplicationNotFoundError,
    CapacityExceededError,
    MeetingNotFoundError,
    OwnerMismatchError,
)
from app.schemas.common import ApiResponse
from app.schemas.interactions import (
    MeetingApplicationDecisionResponse,
    MeetingApplicationListResponse,
    MeetingCreateRequest,
    MeetingCreateResponse,
    MeetingStatusResponse,
)
from app.schemas.resources import MeetingsResponse
from app.services.interaction_service import (
    create_meeting,
    decide_meeting_application,
    get_meeting_status,
    list_meeting_applications,
)
from app.services.resource_service import get_meetings_data

router = APIRouter(tags=["meetings"])


@router.get("/meetings", response_model=ApiResponse[MeetingsResponse])
def meetings() -> ApiResponse[MeetingsResponse]:
    return ApiResponse(request_id="local_service_request", data=get_meetings_data())


@router.post("/meetings", response_model=ApiResponse[MeetingCreateResponse], status_code=201)
def create_meeting_endpoint(payload: MeetingCreateRequest) -> ApiResponse[MeetingCreateResponse]:
    return ApiResponse(
        request_id="local_service_request",
        data=create_meeting(
            category=payload.category,
            title=payload.title,
            description=payload.description,
            place_label=payload.place_label,
            capacity=payload.capacity,
            duration_minutes=payload.duration_minutes,
            nickname=payload.nickname,
            anonymous_id=payload.anonymous_id,
        ),
    )


@router.get("/meetings/{meeting_id}/status", response_model=ApiResponse[MeetingStatusResponse])
def meeting_status(meeting_id: str) -> ApiResponse[MeetingStatusResponse]:
    try:
        return ApiResponse(request_id="local_service_request", data=get_meeting_status(meeting_id))
    except MeetingNotFoundError:
        raise HTTPException(status_code=404, detail="모임을 찾을 수 없어요")


@router.get("/meetings/{meeting_id}/applications", response_model=ApiResponse[MeetingApplicationListResponse])
def meeting_applications(meeting_id: str, owner_secret: str | None = None) -> ApiResponse[MeetingApplicationListResponse]:
    try:
        return ApiResponse(
            request_id="local_service_request",
            data=list_meeting_applications(meeting_id, owner_secret),
        )
    except MeetingNotFoundError:
        raise HTTPException(status_code=404, detail="모임을 찾을 수 없어요")


@router.post(
    "/meetings/{meeting_id}/applications/{application_id}/approve",
    response_model=ApiResponse[MeetingApplicationDecisionResponse],
)
def approve_meeting_application(
    meeting_id: str, application_id: str, owner_secret: str
) -> ApiResponse[MeetingApplicationDecisionResponse]:
    try:
        data = decide_meeting_application(meeting_id, application_id, owner_secret, "approve")
    except MeetingNotFoundError:
        raise HTTPException(status_code=404, detail="모임을 찾을 수 없어요")
    except ApplicationNotFoundError:
        raise HTTPException(status_code=404, detail="신청을 찾을 수 없어요")
    except OwnerMismatchError:
        raise HTTPException(status_code=403, detail="관리 코드가 일치하지 않아요")
    except AlreadyProcessedError:
        raise HTTPException(status_code=400, detail="이미 처리된 신청이에요")
    except CapacityExceededError:
        raise HTTPException(status_code=409, detail="정원이 찼어요")
    return ApiResponse(request_id="local_service_request", data=data)


@router.post(
    "/meetings/{meeting_id}/applications/{application_id}/reject",
    response_model=ApiResponse[MeetingApplicationDecisionResponse],
)
def reject_meeting_application(
    meeting_id: str, application_id: str, owner_secret: str
) -> ApiResponse[MeetingApplicationDecisionResponse]:
    try:
        data = decide_meeting_application(meeting_id, application_id, owner_secret, "reject")
    except MeetingNotFoundError:
        raise HTTPException(status_code=404, detail="모임을 찾을 수 없어요")
    except ApplicationNotFoundError:
        raise HTTPException(status_code=404, detail="신청을 찾을 수 없어요")
    except OwnerMismatchError:
        raise HTTPException(status_code=403, detail="관리 코드가 일치하지 않아요")
    except AlreadyProcessedError:
        raise HTTPException(status_code=400, detail="이미 처리된 신청이에요")
    return ApiResponse(request_id="local_service_request", data=data)
