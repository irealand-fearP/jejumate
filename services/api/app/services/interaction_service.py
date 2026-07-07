import logging

from app.repositories import local_store
from app.schemas.interactions import (
    ChatMessagesResponse,
    MeetingApplicationDecisionResponse,
    MeetingApplicationListResponse,
    MeetingApplicationResponse,
    MeetingCreateResponse,
    MeetingStatusResponse,
    NicknameResponse,
    RagAskResponse,
)


logger = logging.getLogger(__name__)


def create_nickname_profile(nickname: str, anonymous_id: str | None = None) -> NicknameResponse:
    try:
        from app.repositories.interactions_repository import (
            create_or_update_profile as create_or_update_postgres_profile,
        )

        return create_or_update_postgres_profile(nickname=nickname, anonymous_id=anonymous_id)
    except Exception:
        logger.info("Postgres profile persistence unavailable; using local service database.")
        return local_store.create_or_update_profile(nickname=nickname, anonymous_id=anonymous_id)


def submit_meeting_application(
    meeting_id: str,
    nickname: str,
    message: str | None = None,
    anonymous_id: str | None = None,
) -> MeetingApplicationResponse:
    try:
        from app.repositories.interactions_repository import (
            create_or_update_application as create_or_update_postgres_application,
        )

        return create_or_update_postgres_application(
            meeting_source_id=meeting_id,
            nickname=nickname,
            message=message,
            anonymous_id=anonymous_id,
        )
    except Exception:
        logger.info("Postgres application persistence unavailable; using local service database.")
        return local_store.create_or_update_application(
            meeting_id=meeting_id,
            nickname=nickname,
            message=message,
            anonymous_id=anonymous_id,
        )


def list_meeting_chat_messages(meeting_id: str) -> ChatMessagesResponse:
    return local_store.list_chat_messages(meeting_id=meeting_id)


def post_meeting_chat_message(
    meeting_id: str,
    nickname: str,
    content: str,
    anonymous_id: str | None = None,
) -> ChatMessagesResponse:
    return local_store.create_chat_message(
        meeting_id=meeting_id,
        nickname=nickname,
        content=content,
        anonymous_id=anonymous_id,
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
    duration_minutes: int,
    nickname: str,
    anonymous_id: str | None = None,
) -> MeetingCreateResponse:
    return local_store.create_meeting(
        category=category,
        title=title,
        description=description,
        place_label=place_label,
        capacity=capacity,
        duration_minutes=duration_minutes,
        nickname=nickname,
        anonymous_id=anonymous_id,
    )


def get_meeting_status(meeting_id: str) -> MeetingStatusResponse:
    return local_store.get_meeting_status(meeting_id=meeting_id)


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
