"""생활게시판 카테고리 개편 테스트.

'중고거래'와 '나눔'을 '중고거래/나눔' 하나로 합치고 '꿀팁'·'기타'를 추가했다.
기존 DB에 옛 값으로 저장된 글이 새 필터에서 사라지면 안 되므로,
ensure_database가 멱등 UPDATE로 값을 통일한다.
"""
from __future__ import annotations

import pytest

from app.repositories import local_store
from app.services import resource_service
from app.services.kakao_ingest import _TYPE_TO_BOARD_CATEGORY


@pytest.fixture(autouse=True)
def isolated_sqlite_db(tmp_path, monkeypatch):
    db_path = tmp_path / "test.sqlite3"
    monkeypatch.setattr(local_store, "DB_PATH", db_path)
    monkeypatch.setattr(local_store, "USE_POSTGRES", False)
    local_store.ensure_database()
    yield


def _insert_post(post_id: str, category: str) -> None:
    with local_store._connect() as connection:
        connection.execute(
            """
            INSERT INTO board_posts (id, category, title, body, author_nickname, source, created_at)
            VALUES (?, ?, '옛 글', '본문', '이전유저', 'service', ?)
            """,
            (post_id, category, local_store._now()),
        )


def _category_of(post_id: str) -> str:
    with local_store._connect() as connection:
        return connection.execute("SELECT category FROM board_posts WHERE id = ?", (post_id,)).fetchone()[
            "category"
        ]


def test_board_categories_are_the_new_four():
    assert resource_service.BOARD_CATEGORIES == ["질문게시판", "중고거래/나눔", "꿀팁", "기타"]


def test_legacy_categories_are_merged_on_startup():
    """'중고거래'/'나눔'으로 저장된 옛 글은 '중고거래/나눔'으로 통일된다."""
    _insert_post("legacy-secondhand", "중고거래")
    _insert_post("legacy-share", "나눔")
    _insert_post("keep-question", "질문게시판")

    local_store.ensure_database()  # 재기동 시 마이그레이션이 다시 돈다

    assert _category_of("legacy-secondhand") == "중고거래/나눔"
    assert _category_of("legacy-share") == "중고거래/나눔"
    # 다른 카테고리는 건드리지 않는다.
    assert _category_of("keep-question") == "질문게시판"


def test_migration_is_idempotent():
    _insert_post("legacy-secondhand", "중고거래")
    local_store.ensure_database()
    local_store.ensure_database()
    assert _category_of("legacy-secondhand") == "중고거래/나눔"


def test_merged_posts_are_visible_in_board_list():
    """합쳐진 글이 목록 API에 새 카테고리로 나온다(새 필터에서 안 보이는 일이 없어야 한다)."""
    _insert_post("legacy-share", "나눔")
    local_store.ensure_database()

    posts = local_store.list_board_posts()
    categories = {post.id: post.category for post in posts}
    assert categories["legacy-share"] == "중고거래/나눔"
    assert set(categories.values()) <= set(resource_service.BOARD_CATEGORIES)


def test_kakao_ingest_maps_secondhand_and_share_to_one_category():
    assert _TYPE_TO_BOARD_CATEGORY["secondhand"] == "중고거래/나눔"
    assert _TYPE_TO_BOARD_CATEGORY["share"] == "중고거래/나눔"
    assert _TYPE_TO_BOARD_CATEGORY["tip"] == "꿀팁"
    # 잡담(other)은 게시판으로 변환하지 않는다 — '기타'는 사용자가 직접 쓸 때만 고른다.
    assert "other" not in _TYPE_TO_BOARD_CATEGORY


def test_create_board_post_accepts_new_categories_and_rejects_old():
    for category in ("꿀팁", "기타", "중고거래/나눔"):
        post = resource_service.create_board_post_data(
            category=category, title=f"{category} 글", body="본문",
            author_nickname="작성자", anonymous_id=None,
        )
        assert post.category == category

    with pytest.raises(ValueError):
        resource_service.create_board_post_data(
            category="나눔", title="옛 카테고리", body="본문",
            author_nickname="작성자", anonymous_id=None,
        )
