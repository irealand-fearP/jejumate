"""FastAPI 앱: 피드(GET /posts) + RAG 검색(POST /search) + 파티 등록(POST /posts/party)."""
import random
from datetime import datetime, timedelta, timezone

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.embedding import EmbeddingProvider, get_embedding_provider
from app.expiry import is_active_post
from app.models import Post
from app.schemas import (
    EvidenceOut,
    PartyPostCreate,
    PartyPostCreateResponse,
    PostOut,
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
