from fastapi import APIRouter

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
def meeting_chat_messages(meeting_id: str) -> ApiResponse[ChatMessagesResponse]:
    return ApiResponse(
        request_id="local_service_request",
        data=list_meeting_chat_messages(meeting_id),
    )


@router.post("/meetings/{meeting_id}/chat/messages", response_model=ApiResponse[ChatMessagesResponse])
def meeting_chat_message(
    meeting_id: str,
    payload: ChatMessageRequest,
) -> ApiResponse[ChatMessagesResponse]:
    return ApiResponse(
        request_id="local_service_request",
        data=post_meeting_chat_message(
            meeting_id=meeting_id,
            nickname=payload.nickname,
            content=payload.content,
            anonymous_id=payload.anonymous_id,
        ),
    )


@router.post("/rag/ask", response_model=ApiResponse[RagAskResponse])
def rag_ask(payload: RagAskRequest) -> ApiResponse[RagAskResponse]:
    return ApiResponse(
        request_id="local_service_request",
        data=answer_rag_question(payload.question, anonymous_id=payload.anonymous_id),
    )
