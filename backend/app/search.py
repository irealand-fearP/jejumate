"""
태스크6: RAG 검색. 카테고리 메타데이터 필터 → 벡터 유사도 검색(threshold 미만 제외) →
closed/만료 제외.

코사인 유사도는 애플리케이션(Python) 레벨에서 계산한다. pgvector의 DB단
`<=>` 연산자를 쓰면 더 빠르지만, mock 임베딩 단계에선 정확도가 의미 없고
SQLite(테스트)·Postgres(운영) 양쪽에서 동일 코드로 동작하게 하는 이식성이
지금 단계에선 더 중요하다고 판단했다. 데이터량이 커지면 DB단 인덱스 검색으로
바꿔야 한다.

similarity_threshold 미만인 근거는 결과에서 제외한다(관련 글이 부족한 카테고리에서
무관한 근거가 상위 3건을 채우는 문제 대응, app/config.py 참고). 전부 걸러지면 빈
리스트를 반환하고, 호출부(main.py)가 기존 "지금 유효한 정보가 없어요" 흐름으로 처리한다.
"""
import math
from datetime import datetime

from sqlalchemy.orm import Session

from app.expiry import is_active_post
from app.models import Post


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def search_posts(
    session: Session,
    query_embedding: list[float],
    category: str | None = None,
    top_k: int = 3,
    now: datetime | None = None,
    similarity_threshold: float | None = None,
) -> list[Post]:
    from app.config import settings

    threshold = settings.search_similarity_threshold if similarity_threshold is None else similarity_threshold

    query = session.query(Post)
    if category is not None:
        query = query.filter(Post.category == category)

    candidates = [
        post for post in query.all() if post.embedding is not None and is_active_post(post, now)
    ]
    scored = [(post, _cosine_similarity(query_embedding, post.embedding)) for post in candidates]
    scored = [(post, sim) for post, sim in scored if sim >= threshold]
    scored.sort(key=lambda item: item[1], reverse=True)
    return [post for post, _ in scored[:top_k]]
