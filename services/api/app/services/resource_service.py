from app.repositories.local_store import (
    create_board_comment,
    create_board_post,
    delete_board_post,
    get_board_post,
    list_board_posts,
    list_open_meetings,
    report_board_target,
)
from app.schemas.resources import (
    BoardDeleteResponse,
    BoardPost,
    BoardReportResponse,
    BoardResponse,
    MeetingsResponse,
    ProfilePreviewResponse,
)
from app.services.home_service import get_home_data

BOARD_CATEGORIES = ["질문게시판", "중고거래", "나눔"]


def get_meetings_data() -> MeetingsResponse:
    # 홈 미리보기(get_home_data)는 LIMIT 6이 걸려 있어, 모임 목록 페이지가 이걸 그대로
    # 재사용하면 열린 모임이 6개를 넘는 순간부터 새로 만든 모임이 목록에서 사라지는
    # 버그가 있었다. 목록 페이지는 열린 모임 전체(list_open_meetings)를 쓴다.
    home = get_home_data()
    return MeetingsResponse(
        filters=home.meeting_filters,
        meetings=list_open_meetings(),
        privacy_note="파티 신청 시 공개되는 정보는 닉네임과 신청 상태입니다.",
    )


def get_board_data() -> BoardResponse:
    return BoardResponse(
        categories=BOARD_CATEGORIES,
        posts=list_board_posts(),
        notice="생활게시판 글은 닉네임으로만 공개됩니다.",
    )


def get_board_post_data(post_id: str, anonymous_id: str | None = None) -> BoardPost:
    return get_board_post(post_id, anonymous_id=anonymous_id)


def create_board_post_data(
    *,
    category: str,
    title: str,
    body: str,
    author_nickname: str,
    anonymous_id: str | None,
) -> BoardPost:
    if category not in BOARD_CATEGORIES:
        raise ValueError("Unknown board category")
    return create_board_post(
        category=category,
        title=title,
        body=body,
        author_nickname=author_nickname,
        anonymous_id=anonymous_id,
    )


def delete_board_post_data(post_id: str, anonymous_id: str) -> BoardDeleteResponse:
    return delete_board_post(post_id=post_id, anonymous_id=anonymous_id)


def create_board_comment_data(
    *,
    post_id: str,
    body: str,
    author_nickname: str,
    anonymous_id: str | None,
) -> BoardPost:
    return create_board_comment(
        post_id=post_id,
        body=body,
        author_nickname=author_nickname,
        anonymous_id=anonymous_id,
    )


def report_board_post_data(*, post_id: str, reason: str, anonymous_id: str | None) -> BoardReportResponse:
    return report_board_target(
        target_type="post",
        target_id=post_id,
        reason=reason,
        anonymous_id=anonymous_id,
    )


def get_profile_preview_data() -> ProfilePreviewResponse:
    return ProfilePreviewResponse(
        public_fields=["닉네임", "관심사", "참여 신청 상태"],
        hidden_fields=["실명", "전화번호", "생년월일", "인증 원본"],
        default_interests=["밥친구", "작업", "러닝"],
        safety_notes=[
            "공개 프로필은 닉네임 중심으로 노출됩니다.",
            "실명 인증 정보는 안전 확인과 운영자 검토에만 사용됩니다.",
            "신고/차단 정보는 상대 사용자에게 공개하지 않습니다.",
        ],
    )
