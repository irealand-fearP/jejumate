from fastapi import APIRouter, HTTPException

from app.repositories.local_store import ChatAccessDeniedError, MeetingNotFoundError
from app.schemas.common import ApiResponse
from app.schemas.interactions import (
    ChatMessageRequest,
    ChatMessagesResponse,
    MeetingApplicationRequest,
    MeetingApplicationResponse,
    NicknameRequest,
    NicknameResponse,
    RagAskRequest,
    RagAskResponse,
)
from app.services.interaction_service import (
    answer_rag_question,
    create_nickname_profile,
    list_meeting_chat_messages,
    post_meeting_chat_message,
    submit_meeting_application,
)

router = APIRouter(tags=["interactions"])


@router.post("/onboarding/nickname", response_model=ApiResponse[NicknameResponse])
def onboarding_nickname(payload: NicknameRequest) -> ApiResponse[NicknameResponse]:
    return ApiResponse(
        request_id="local_service_request",
        data=create_nickname_profile(payload.nickname, anonymous_id=payload.anonymous_id),
    )


@router.post("/meetings/{meeting_id}/applications", response_model=ApiResponse[MeetingApplicationResponse])
def meeting_application(
    meeting_id: str,
    payload: MeetingApplicationRequest,
) -> ApiResponse[MeetingApplicationResponse]:
    return ApiResponse(
        request_id="local_service_request",
        data=submit_meeting_application(
            meeting_id=meeting_id,
            nickname=payload.nickname,
            message=payload.message,
            anonymous_id=payload.anonymous_id,
        ),
    )


@router.get("/meetings/{meeting_id}/chat/messages", response_model=ApiResponse[ChatMessagesResponse])
def meeting_chat_messages(
    meeting_id: str, anonymous_id: str | None = None, owner_secret: str | None = None
) -> ApiResponse[ChatMessagesResponse]:
    """모임 채팅은 승인된 신청자(anonymous_id)와 호스트(owner_secret)만 볼 수 있다."""
    try:
        data = list_meeting_chat_messages(meeting_id, anonymous_id=anonymous_id, owner_secret=owner_secret)
    except MeetingNotFoundError:
        raise HTTPException(status_code=404, detail="파티를 찾을 수 없어요")
    except ChatAccessDeniedError:
        raise HTTPException(status_code=403, detail="승인된 참가자와 호스트만 볼 수 있어요")
    return ApiResponse(request_id="local_service_request", data=data)


@router.post("/meetings/{meeting_id}/chat/messages", response_model=ApiResponse[ChatMessagesResponse])
def meeting_chat_message(
    meeting_id: str,
    payload: ChatMessageRequest,
) -> ApiResponse[ChatMessagesResponse]:
    try:
        data = post_meeting_chat_message(
            meeting_id=meeting_id,
            nickname=payload.nickname,
            content=payload.content,
            anonymous_id=payload.anonymous_id,
            owner_secret=payload.owner_secret,
        )
    except MeetingNotFoundError:
        raise HTTPException(status_code=404, detail="파티를 찾을 수 없어요")
    except ChatAccessDeniedError:
        raise HTTPException(status_code=403, detail="승인된 참가자와 호스트만 보낼 수 있어요")
    return ApiResponse(request_id="local_service_request", data=data)


@router.post("/rag/ask", response_model=ApiResponse[RagAskResponse])
def rag_ask(payload: RagAskRequest) -> ApiResponse[RagAskResponse]:
    return ApiResponse(
        request_id="local_service_request",
        data=answer_rag_question(payload.question, anonymous_id=payload.anonymous_id),
    )
