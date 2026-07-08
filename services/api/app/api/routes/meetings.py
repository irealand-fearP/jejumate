from fastapi import APIRouter, HTTPException

from app.repositories.local_store import (
    AlreadyProcessedError,
    ApplicantMismatchError,
    ApplicationNotFoundError,
    CapacityExceededError,
    MeetingNotFoundError,
    OwnerMismatchError,
)
from app.schemas.common import ApiResponse
from app.schemas.home import HomeMeeting
from app.schemas.interactions import (
    ApplicantNotificationsResponse,
    ApplicationDeleteResponse,
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
    delete_my_application,
    get_meeting_detail,
    get_meeting_status,
    list_meeting_applications,
    list_my_application_notifications,
)
from app.services.resource_service import get_meetings_data

router = APIRouter(tags=["meetings"])


@router.get("/meetings", response_model=ApiResponse[MeetingsResponse])
def meetings() -> ApiResponse[MeetingsResponse]:
    # 카톡 실시간 수집 피기백은 여기서 더 이상 호출하지 않는다 — Vercel 프로덕션 실측
    # (연속 호출 2.5~11초)이 핵심 화면 응답 속도를 갉아먹어 제거했다. 카톡 수집은
    # GitHub Actions 5분 크론(.github/workflows/kakao-ingest.yml)만으로 계속된다.
    return ApiResponse(request_id="local_service_request", data=get_meetings_data())


@router.get("/meetings/applications/notifications", response_model=ApiResponse[ApplicantNotificationsResponse])
def my_application_notifications(anonymous_id: str) -> ApiResponse[ApplicantNotificationsResponse]:
    """내 신청 알림(코덱스 원본 신규 기능 이식). 호스트 액션이 아니므로 owner_secret이
    아니라 신청자 본인의 anonymous_id로 조회한다."""
    return ApiResponse(request_id="local_service_request", data=list_my_application_notifications(anonymous_id))


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
            starts_at=payload.starts_at,
            ends_at=payload.ends_at,
            nickname=payload.nickname,
            anonymous_id=payload.anonymous_id,
        ),
    )


@router.get("/meetings/{meeting_id}", response_model=ApiResponse[HomeMeeting])
def meeting_detail(meeting_id: str) -> ApiResponse[HomeMeeting]:
    """내정보 '내가 만든 모임' 목록 등 상태와 무관하게 모임 상세가 필요할 때 쓴다."""
    try:
        return ApiResponse(request_id="local_service_request", data=get_meeting_detail(meeting_id))
    except MeetingNotFoundError:
        raise HTTPException(status_code=404, detail="파티를 찾을 수 없어요")


@router.get("/meetings/{meeting_id}/status", response_model=ApiResponse[MeetingStatusResponse])
def meeting_status(meeting_id: str) -> ApiResponse[MeetingStatusResponse]:
    try:
        return ApiResponse(request_id="local_service_request", data=get_meeting_status(meeting_id))
    except MeetingNotFoundError:
        raise HTTPException(status_code=404, detail="파티를 찾을 수 없어요")


@router.get("/meetings/{meeting_id}/applications", response_model=ApiResponse[MeetingApplicationListResponse])
def meeting_applications(meeting_id: str, owner_secret: str | None = None) -> ApiResponse[MeetingApplicationListResponse]:
    try:
        return ApiResponse(
            request_id="local_service_request",
            data=list_meeting_applications(meeting_id, owner_secret),
        )
    except MeetingNotFoundError:
        raise HTTPException(status_code=404, detail="파티를 찾을 수 없어요")


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
        raise HTTPException(status_code=404, detail="파티를 찾을 수 없어요")
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
        raise HTTPException(status_code=404, detail="파티를 찾을 수 없어요")
    except ApplicationNotFoundError:
        raise HTTPException(status_code=404, detail="신청을 찾을 수 없어요")
    except OwnerMismatchError:
        raise HTTPException(status_code=403, detail="관리 코드가 일치하지 않아요")
    except AlreadyProcessedError:
        raise HTTPException(status_code=400, detail="이미 처리된 신청이에요")
    return ApiResponse(request_id="local_service_request", data=data)


@router.delete(
    "/meetings/{meeting_id}/applications/{application_id}",
    response_model=ApiResponse[ApplicationDeleteResponse],
)
def delete_meeting_application(
    meeting_id: str, application_id: str, anonymous_id: str
) -> ApiResponse[ApplicationDeleteResponse]:
    """신청 삭제(코덱스 원본 신규 기능 이식). 신청자 본인 액션이므로 owner_secret이
    아니라 신청 생성 시 쓴 anonymous_id로 본인 확인한다(승인/거절과는 다른 권한 모델)."""
    try:
        data = delete_my_application(meeting_id, application_id, anonymous_id)
    except MeetingNotFoundError:
        raise HTTPException(status_code=404, detail="파티를 찾을 수 없어요")
    except ApplicationNotFoundError:
        raise HTTPException(status_code=404, detail="신청을 찾을 수 없어요")
    except ApplicantMismatchError:
        raise HTTPException(status_code=403, detail="본인 신청만 삭제할 수 있어요")
    return ApiResponse(request_id="local_service_request", data=data)
