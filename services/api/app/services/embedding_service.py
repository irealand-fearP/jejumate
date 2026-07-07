"""
RAG 임베딩 유틸리티. jejumate/backend(app/embedding.py, app/search.py)의
OpenAI 임베딩(text-embedding-3-small) + 코사인 유사도 계산 방식을 그대로 이식한다.
"""
from __future__ import annotations

import math
import os

EMBEDDING_MODEL = "text-embedding-3-small"


def embed_text(text: str) -> list[float]:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY가 설정되지 않았습니다. services/api/.env에 키를 추가해야 "
            "실제 임베딩을 생성할 수 있습니다."
        )
    import openai  # 키 없는 경로에서는 import조차 필요 없게 지연 임포트

    client = openai.OpenAI(api_key=api_key)
    response = client.embeddings.create(model=EMBEDDING_MODEL, input=text)
    return response.data[0].embedding


def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
