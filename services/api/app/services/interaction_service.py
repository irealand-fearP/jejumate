from app.repositories import local_store
from app.schemas.home import HomeMeeting
from app.schemas.interactions import (
    ApplicantNotificationsResponse,
    ApplicationDeleteResponse,
    ChatMessagesResponse,
    MeetingApplicationDecisionResponse,
    MeetingApplicationListResponse,
    MeetingApplicationResponse,
    MeetingCreateResponse,
    MeetingStatusResponse,
    NicknameResponse,
    RagAskResponse,
)


def create_nickname_profile(nickname: str, anonymous_id: str | None = None) -> NicknameResponse:
    return local_store.create_or_update_profile(nickname=nickname, anonymous_id=anonymous_id)


def submit_meeting_application(
    meeting_id: str,
    nickname: str,
    message: str | None = None,
    anonymous_id: str | None = None,
) -> MeetingApplicationResponse:
    return local_store.create_or_update_application(
        meeting_id=meeting_id,
        nickname=nickname,
        message=message,
        anonymous_id=anonymous_id,
    )


def list_meeting_chat_messages(
    meeting_id: str, anonymous_id: str | None = None, owner_secret: str | None = None
) -> ChatMessagesResponse:
    return local_store.list_chat_messages(meeting_id=meeting_id, anonymous_id=anonymous_id, owner_secret=owner_secret)


def post_meeting_chat_message(
    meeting_id: str,
    nickname: str,
    content: str,
    anonymous_id: str | None = None,
    owner_secret: str | None = None,
) -> ChatMessagesResponse:
    return local_store.create_chat_message(
        meeting_id=meeting_id,
        nickname=nickname,
        content=content,
        anonymous_id=anonymous_id,
        owner_secret=owner_secret,
    )


def answer_rag_question(question: str, anonymous_id: str | None = None) -> RagAskResponse:
    return local_store.answer_rag_question(question=question, anonymous_id=anonymous_id)


def create_meeting(
    *,
    category: str,
    title: str,
    description: str | None,
    place_label: str,
    capacity: int,
    starts_at: str,
    ends_at: str,
    nickname: str,
    anonymous_id: str | None = None,
) -> MeetingCreateResponse:
    return local_store.create_meeting(
        category=category,
        title=title,
        description=description,
        place_label=place_label,
        capacity=capacity,
        starts_at=starts_at,
        ends_at=ends_at,
        nickname=nickname,
        anonymous_id=anonymous_id,
    )


def get_meeting_status(meeting_id: str) -> MeetingStatusResponse:
    return local_store.get_meeting_status(meeting_id=meeting_id)


def get_meeting_detail(meeting_id: str) -> HomeMeeting:
    return local_store.get_meeting_by_id(meeting_id=meeting_id)


def list_meeting_applications(meeting_id: str, owner_secret: str | None = None) -> MeetingApplicationListResponse:
    return local_store.list_meeting_applications(meeting_id=meeting_id, owner_secret=owner_secret)


def decide_meeting_application(
    meeting_id: str, application_id: str, owner_secret: str, decision: str
) -> MeetingApplicationDecisionResponse:
    return local_store.decide_meeting_application(
        meeting_id=meeting_id,
        application_id=application_id,
        owner_secret=owner_secret,
        decision=decision,
    )


def list_my_application_notifications(anonymous_id: str) -> ApplicantNotificationsResponse:
    return local_store.list_notifications_for_applicant(anonymous_id=anonymous_id)


def delete_my_application(meeting_id: str, application_id: str, anonymous_id: str) -> ApplicationDeleteResponse:
    return local_store.delete_my_application(
        meeting_id=meeting_id, application_id=application_id, anonymous_id=anonymous_id
    )
