"""
카톡 txt → posts 적재 배치 파이프라인 (태스크4).

흐름: 파싱(app.parser) → 대화 단위 청킹 → 규칙 필터(app.rule_filter)로
후보 카테고리가 없는 잡담은 LLM 호출 없이 버림 → LLM 태깅(app.tagging) →
임베딩(app.embedding) → posts 테이블 적재.
"""
from sqlalchemy.orm import Session

from app.embedding import EmbeddingProvider
from app.models import Post
from app.parser import chunk_messages, parse_kakao_txt
from app.rule_filter import match_categories
from app.tagging import LLMTagger


def ingest_kakao_txt(
    txt_path: str,
    session: Session,
    tagger: LLMTagger,
    embedder: EmbeddingProvider,
    chat_room_name: str | None = None,
) -> list[Post]:
    with open(txt_path, encoding="utf-8") as f:
        text = f.read()

    chunks = chunk_messages(parse_kakao_txt(text))

    created_posts: list[Post] = []
    for chunk in chunks:
        if not match_categories(chunk.content):
            continue  # 규칙 필터 탈락(잡담) → LLM 호출 없이 버림

        tag = tagger.tag(chunk.content)
        post = Post(
            source="kakao",
            post_type=tag.post_type,
            category=tag.category,
            status=tag.status,
            content=chunk.content,
            author_nickname=chunk.nickname,
            original_timestamp=chunk.start_timestamp,
            chat_room_name=chat_room_name,
            embedding=embedder.embed(chunk.content),
        )
        session.add(post)
        created_posts.append(post)

    session.commit()
    return created_posts
