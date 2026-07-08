from fastapi import APIRouter, BackgroundTasks, HTTPException

from app.repositories.local_store import BoardOwnerMismatchError, BoardPostNotFoundError
from app.schemas.common import ApiResponse
from app.schemas.resources import (
    BoardCommentCreateRequest,
    BoardDeleteResponse,
    BoardPost,
    BoardPostCreateRequest,
    BoardReportRequest,
    BoardReportResponse,
    BoardResponse,
)
from app.services.kakao_ingest import maybe_ingest_kakao_now
from app.services.resource_service import (
    create_board_comment_data,
    create_board_post_data,
    delete_board_post_data,
    get_board_data,
    get_board_post_data,
    report_board_post_data,
)

router = APIRouter(tags=["board"])


@router.get("/board", response_model=ApiResponse[BoardResponse])
def board(background_tasks: BackgroundTasks) -> ApiResponse[BoardResponse]:
    # 카톡 실시간 수집 피기백. 응답 지연에 영향 없도록 BackgroundTasks로 등록.
    background_tasks.add_task(maybe_ingest_kakao_now)
    return ApiResponse(request_id="local_service_request", data=get_board_data())


@router.get("/board/posts/{post_id}", response_model=ApiResponse[BoardPost])
def board_post(post_id: str, anonymous_id: str | None = None) -> ApiResponse[BoardPost]:
    try:
        return ApiResponse(request_id="local_service_request", data=get_board_post_data(post_id, anonymous_id))
    except BoardPostNotFoundError:
        raise HTTPException(status_code=404, detail="게시글을 찾을 수 없어요")


@router.post("/board/posts", response_model=ApiResponse[BoardPost], status_code=201)
def create_board_post(payload: BoardPostCreateRequest) -> ApiResponse[BoardPost]:
    try:
        data = create_board_post_data(
            category=payload.category,
            title=payload.title,
            body=payload.body,
            author_nickname=payload.author_nickname,
            anonymous_id=payload.anonymous_id,
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="지원하지 않는 게시판 카테고리예요")
    return ApiResponse(request_id="local_service_request", data=data)


@router.delete("/board/posts/{post_id}", response_model=ApiResponse[BoardDeleteResponse])
def delete_board_post(post_id: str, anonymous_id: str) -> ApiResponse[BoardDeleteResponse]:
    try:
        return ApiResponse(request_id="local_service_request", data=delete_board_post_data(post_id, anonymous_id))
    except BoardPostNotFoundError:
        raise HTTPException(status_code=404, detail="게시글을 찾을 수 없어요")
    except BoardOwnerMismatchError:
        raise HTTPException(status_code=403, detail="본인 글만 삭제할 수 있어요")


@router.post("/board/posts/{post_id}/comments", response_model=ApiResponse[BoardPost], status_code=201)
def create_board_comment(post_id: str, payload: BoardCommentCreateRequest) -> ApiResponse[BoardPost]:
    try:
        data = create_board_comment_data(
            post_id=post_id,
            body=payload.body,
            author_nickname=payload.author_nickname,
            anonymous_id=payload.anonymous_id,
        )
    except BoardPostNotFoundError:
        raise HTTPException(status_code=404, detail="게시글을 찾을 수 없어요")
    return ApiResponse(request_id="local_service_request", data=data)


@router.post("/board/posts/{post_id}/reports", response_model=ApiResponse[BoardReportResponse], status_code=201)
def report_board_post(post_id: str, payload: BoardReportRequest) -> ApiResponse[BoardReportResponse]:
    try:
        data = report_board_post_data(post_id=post_id, reason=payload.reason, anonymous_id=payload.anonymous_id)
    except BoardPostNotFoundError:
        raise HTTPException(status_code=404, detail="게시글을 찾을 수 없어요")
    return ApiResponse(request_id="local_service_request", data=data)
