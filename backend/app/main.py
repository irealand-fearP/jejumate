"""FastAPI 앱: 피드(GET /posts) + RAG 검색(POST /search) + 파티 등록/신청."""
import random
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.embedding import EmbeddingProvider, get_embedding_provider
from app.expiry import is_active_post
from app.models import Application, Post
from app.schemas import (
    ApplicationCreate,
    ApplicationListItem,
    ApplicationListResponse,
    ApplicationOut,
    EvidenceOut,
    PartyPostCreate,
    PartyPostCreateResponse,
    PostOut,
    PostStatusOut,
    SearchRequest,
    SearchResponse,
)
from app.search import search_posts

app = FastAPI(title="jejumate")

# 해커톤 데모용: 프론트엔드(Next.js, 다른 포트)에서 자유롭게 호출 가능하게 전체 허용.
# 운영 전환 시 실제 프론트 도메인으로 좁혀야 한다.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_embedder() -> EmbeddingProvider:
    return get_embedding_provider()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/posts", response_model=list[PostOut])
def list_posts(category: str | None = None, db: Session = Depends(get_db)):
    """피드: 카테고리 필터, 최신순, closed/만료 글은 제외."""
    query = db.query(Post)
    if category is not None:
        query = query.filter(Post.category == category)
    posts = query.order_by(Post.created_at.desc()).all()
    return [post for post in posts if is_active_post(post)]


@app.post("/search", response_model=SearchResponse)
def search(
    payload: SearchRequest,
    db: Session = Depends(get_db),
    embedder: EmbeddingProvider = Depends(get_embedder),
):
    """RAG 검색: 카테고리 필터 → 벡터 검색(closed/만료 제외) → 근거 포함 응답."""
    query_vector = embedder.embed(payload.query)
    results = search_posts(db, query_vector, category=payload.category)

    if not results:
        return SearchResponse(answer="지금 유효한 정보가 없어요", evidence=[])

    evidence = [
        EvidenceOut(
            id=str(post.id),
            content=post.content,
            author_nickname=post.author_nickname,
            original_timestamp=post.original_timestamp,
            source=post.source,
            category=post.category,
            post_type=post.post_type,
        )
        for post in results
    ]
    answer = f"관련된 정보를 {len(results)}건 찾았어요. 근거를 확인해보세요."
    return SearchResponse(answer=answer, evidence=evidence)


def _generate_owner_secret() -> str:
    """로그인 없이 글쓴이 권한을 증명할 4자리 관리 코드(화면흐름.md 6장)."""
    return f"{random.randint(0, 9999):04d}"


@app.post("/posts/party", response_model=PartyPostCreateResponse, status_code=201)
def create_party_post(
    payload: PartyPostCreate,
    db: Session = Depends(get_db),
    embedder: EmbeddingProvider = Depends(get_embedder),
):
    now = datetime.now(timezone.utc)
    deadline = now + timedelta(minutes=payload.deadline_minutes)
    owner_secret = _generate_owner_secret()

    post = Post(
        source="user_post",
        post_type="party",
        category=payload.category,
        content=payload.content,
        author_nickname=payload.nickname,
        original_timestamp=now,
        capacity=payload.capacity,
        deadline=deadline,
        owner_secret=owner_secret,
        # 등록 즉시 RAG 검색 대상이 되려면 임베딩이 있어야 한다(데모 시나리오 5번).
        embedding=embedder.embed(payload.content),
    )
    db.add(post)
    db.commit()
    db.refresh(post)

    return PartyPostCreateResponse(id=str(post.id), owner_secret=owner_secret, deadline=deadline)


@app.post("/posts/{post_id}/applications", response_model=ApplicationOut, status_code=201)
def create_application(post_id: uuid.UUID, payload: ApplicationCreate, db: Session = Depends(get_db)):
    """참여 신청('같이 갈래요'). 신청/승인 데이터는 RAG 임베딩·검색 대상이 아니다(기획서 3장-11)."""
    post = db.query(Post).filter(Post.id == post_id).first()
    if post is None:
        raise HTTPException(status_code=404, detail="모집 글을 찾을 수 없어요")
    if post.post_type != "party":
        raise HTTPException(status_code=400, detail="정보 글에는 신청할 수 없어요")
    if not is_active_post(post):
        raise HTTPException(status_code=400, detail="마감된 모집이에요")

    application = Application(post_id=post.id, nickname=payload.nickname, message=payload.message)
    db.add(application)
    db.commit()
    db.refresh(application)

    return ApplicationOut(
        id=str(application.id),
        nickname=application.nickname,
        message=application.message,
        status=application.status,
    )


def _get_post_or_404(db: Session, post_id: uuid.UUID) -> Post:
    post = db.query(Post).filter(Post.id == post_id).first()
    if post is None:
        raise HTTPException(status_code=404, detail="모집 글을 찾을 수 없어요")
    return post


def _require_owner(post: Post, owner_secret: str | None) -> None:
    if owner_secret is None or post.owner_secret != owner_secret:
        raise HTTPException(status_code=403, detail="관리 코드가 일치하지 않아요")


@app.get("/posts/{post_id}/status", response_model=PostStatusOut)
def get_post_status(post_id: uuid.UUID, db: Session = Depends(get_db)):
    """모집 현황 폴링용: 승인 count vs 정원, 마감 여부."""
    post = _get_post_or_404(db, post_id)
    approved_count = (
        db.query(Application)
        .filter(Application.post_id == post.id, Application.status == "approved")
        .count()
    )
    return PostStatusOut(
        capacity=post.capacity,
        approved_count=approved_count,
        deadline=post.deadline,
        is_closed=not is_active_post(post),
    )


@app.get("/posts/{post_id}/applications", response_model=ApplicationListResponse)
def list_applications(post_id: uuid.UUID, owner_secret: str | None = None, db: Session = Depends(get_db)):
    """관리 코드가 맞으면 전체 상세, 아니면 닉네임만(화면흐름.md 5-5). 거절된 신청은 목록에서 제외."""
    post = _get_post_or_404(db, post_id)
    applications = (
        db.query(Application)
        .filter(Application.post_id == post.id, Application.status != "rejected")
        .order_by(Application.created_at)
        .all()
    )
    authorized = owner_secret is not None and post.owner_secret == owner_secret

    if authorized:
        items = [
            ApplicationListItem(id=str(a.id), nickname=a.nickname, message=a.message, status=a.status)
            for a in applications
        ]
    else:
        items = [ApplicationListItem(id=None, nickname=a.nickname) for a in applications]

    return ApplicationListResponse(authorized=authorized, applications=items)


def _get_application_or_404(db: Session, post: Post, application_id: uuid.UUID) -> Application:
    application = (
        db.query(Application)
        .filter(Application.id == application_id, Application.post_id == post.id)
        .first()
    )
    if application is None:
        raise HTTPException(status_code=404, detail="신청을 찾을 수 없어요")
    return application


@app.post("/posts/{post_id}/applications/{application_id}/approve", response_model=ApplicationOut)
def approve_application(
    post_id: uuid.UUID, application_id: uuid.UUID, owner_secret: str, db: Session = Depends(get_db)
):
    """'같이 가기로 하기'. 정원 초과면 서버에서 승인을 막는다(정원 체크는 승인 시점 1회)."""
    post = _get_post_or_404(db, post_id)
    _require_owner(post, owner_secret)
    application = _get_application_or_404(db, post, application_id)

    if application.status != "pending":
        raise HTTPException(status_code=400, detail="이미 처리된 신청이에요")

    if post.capacity is not None:
        approved_count = (
            db.query(Application)
            .filter(Application.post_id == post.id, Application.status == "approved")
            .count()
        )
        if approved_count >= post.capacity:
            raise HTTPException(status_code=409, detail="정원이 찼어요")

    application.status = "approved"
    db.commit()
    db.refresh(application)

    return ApplicationOut(
        id=str(application.id), nickname=application.nickname, message=application.message, status=application.status
    )


@app.post("/posts/{post_id}/applications/{application_id}/reject", response_model=ApplicationOut)
def reject_application(
    post_id: uuid.UUID, application_id: uuid.UUID, owner_secret: str, db: Session = Depends(get_db)
):
    """거절은 알림 없이 목록에서 빠지기만 하면 된다(화면흐름.md 5-5)."""
    post = _get_post_or_404(db, post_id)
    _require_owner(post, owner_secret)
    application = _get_application_or_404(db, post, application_id)

    application.status = "rejected"
    db.commit()
    db.refresh(application)

    return ApplicationOut(
        id=str(application.id), nickname=application.nickname, message=application.message, status=application.status
    )
