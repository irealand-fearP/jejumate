"""FastAPI 앱: 피드(GET /posts) + RAG 검색(POST /search)."""
from fastapi import Depends, FastAPI
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.embedding import EmbeddingProvider, get_embedding_provider
from app.expiry import is_active_post
from app.models import Post
from app.schemas import EvidenceOut, PostOut, SearchRequest, SearchResponse
from app.search import search_posts

app = FastAPI(title="jejumate")


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
