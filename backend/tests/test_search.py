"""
태스크6: RAG 검색 — 카테고리 필터 → 벡터 유사도 → closed/만료 제외.

mock 임베딩이라 검색 '품질'(의미적 유사도)은 의미가 없으므로, 여기서는
파이프라인이 끝까지 돌면서 (1) closed/만료 글이 제외되고 (2) 카테고리 필터가
먹히고 (3) 코사인 유사도로 정렬되는 '메커니즘'만 검증한다.
"""
import math
from datetime import datetime, timedelta, timezone

from app.models import Post
from app.search import search_posts

NOW = datetime(2026, 7, 6, 15, 0, tzinfo=timezone.utc)


def _make_post(session, **overrides):
    defaults = dict(
        source="kakao",
        post_type="party",
        category="ride",
        content="함덕 택시팟 구해요",
        author_nickname="누군가",
        original_timestamp=NOW,
        embedding=[0.0] * 1536,
    )
    defaults.update(overrides)
    post = Post(**defaults)
    session.add(post)
    session.commit()
    return post


# 아래 4개 테스트는 정렬/카테고리 필터/만료 제외 등 '메커니즘'만 검증하므로
# 관련도 threshold는 0으로 꺼서(similarity_threshold=0.0) 새로 추가한 필터에 영향받지
# 않게 한다(제로 벡터 위주라 threshold 기본값 적용 시 결과가 전부 걸러짐).


def test_excludes_closed_and_expired_posts(db_session):
    active = _make_post(db_session, content="유효한 글")
    closed = _make_post(db_session, content="수동 마감된 글", status="closed")
    expired = _make_post(
        db_session, content="마감시간 지난 글", deadline=NOW - timedelta(minutes=1)
    )

    results = search_posts(
        db_session, query_embedding=[0.0] * 1536, now=NOW, similarity_threshold=0.0
    )

    ids = {p.id for p in results}
    assert active.id in ids
    assert closed.id not in ids
    assert expired.id not in ids


def test_category_filter_applied(db_session):
    ride = _make_post(db_session, category="ride", content="택시팟")
    food = _make_post(db_session, category="food", post_type="info", content="맛집")

    results = search_posts(
        db_session, query_embedding=[0.0] * 1536, category="food", now=NOW, similarity_threshold=0.0
    )

    ids = {p.id for p in results}
    assert food.id in ids
    assert ride.id not in ids


def test_orders_by_cosine_similarity_descending(db_session):
    close_vector = [1.0] + [0.0] * 1535
    far_vector = [0.0, 1.0] + [0.0] * 1534

    near = _make_post(db_session, content="가까운 글", embedding=close_vector)
    far = _make_post(db_session, content="먼 글", embedding=far_vector)

    results = search_posts(
        db_session, query_embedding=close_vector, now=NOW, similarity_threshold=0.0
    )

    assert results[0].id == near.id
    assert results[-1].id == far.id


def test_respects_top_k_limit(db_session):
    for i in range(5):
        _make_post(db_session, content=f"글{i}")

    # 이 테스트들은 정렬/필터/limit 등 '메커니즘'만 보므로 관련도 threshold는 0으로 꺼서
    # (제로 벡터라 코사인 유사도가 늘 0으로 계산됨) 새로 추가한 필터에 영향받지 않게 한다.
    results = search_posts(
        db_session, query_embedding=[0.0] * 1536, top_k=2, now=NOW, similarity_threshold=0.0
    )
    assert len(results) == 2


def _unit_vector_with_similarity(cos_sim: float) -> list[float]:
    """query_vector=[1,0,0,...]과의 코사인 유사도가 정확히 cos_sim이 되는 단위벡터를 만든다."""
    remainder = math.sqrt(max(0.0, 1 - cos_sim**2))
    return [cos_sim, remainder] + [0.0] * 1534


def test_filters_evidence_below_similarity_threshold(db_session):
    query_vector = [1.0] + [0.0] * 1535

    relevant = _make_post(
        db_session, content="관련 근거", embedding=_unit_vector_with_similarity(0.7)
    )
    irrelevant = _make_post(
        db_session, content="무관 근거", embedding=_unit_vector_with_similarity(0.3)
    )

    results = search_posts(
        db_session, query_embedding=query_vector, now=NOW, similarity_threshold=0.5
    )

    ids = {p.id for p in results}
    assert relevant.id in ids
    assert irrelevant.id not in ids


def test_returns_empty_list_when_all_evidence_below_threshold(db_session):
    query_vector = [1.0] + [0.0] * 1535
    _make_post(db_session, content="무관 근거", embedding=_unit_vector_with_similarity(0.3))

    results = search_posts(
        db_session, query_embedding=query_vector, now=NOW, similarity_threshold=0.5
    )

    assert results == []
