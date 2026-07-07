import logging

from app.repositories import local_store
from app.schemas.interactions import (
    ChatMessagesResponse,
    MeetingApplicationResponse,
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
