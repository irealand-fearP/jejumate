"""
태스크4 전체 배치 파이프라인 테스트: 파싱→청킹→규칙필터→태깅→임베딩→posts 적재.

MockLLMTagger + MockEmbeddingProvider로 실제 API 키 없이 파이프라인 자체가
end-to-end로 동작하는지 검증한다(DB는 SQLite 인메모리, conftest.py 참고).
"""
from app.embedding import MockEmbeddingProvider
from app.models import Post
from app.pipeline import ingest_kakao_txt
from app.tagging import MockLLMTagger

SAMPLE_PATH = "/home/ai/agent-company/data/sample_kakao_chat.txt"


def test_ingest_creates_posts_from_sample_file(db_session):
    created = ingest_kakao_txt(
        SAMPLE_PATH,
        session=db_session,
        tagger=MockLLMTagger(),
        embedder=MockEmbeddingProvider(),
        chat_room_name="2026 제주대학교 하기 계절학기 학점교류방",
    )

    assert len(created) > 0
    # 규칙 필터에서 걸러지는 잡담이 있어야 하므로, 대화 단위 총량(112개)보다는 적어야 한다.
    assert len(created) < 112

    stored = db_session.query(Post).all()
    assert len(stored) == len(created)
    for post in stored:
        assert post.source == "kakao"
        assert post.chat_room_name == "2026 제주대학교 하기 계절학기 학점교류방"
        assert post.post_type in ("party", "info")
        assert len(post.embedding) == 1536


def test_ingest_tags_known_taxi_message_as_ride_party(db_session):
    """'함덕해수욕장 택시팟 구해요' 류 메시지가 ride/party로 태깅되는지 확인한다."""
    created = ingest_kakao_txt(
        SAMPLE_PATH,
        session=db_session,
        tagger=MockLLMTagger(),
        embedder=MockEmbeddingProvider(),
    )
    ride_posts = [p for p in created if p.category == "ride"]
    assert any("택시팟" in p.content for p in ride_posts)
    assert all(p.post_type == "party" for p in ride_posts)
