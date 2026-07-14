"""제주대학교 공식 학과·학사 자료를 운영 RAG에 색인한다.

실행:
    cd services/api
    python3 scripts/seed_jejunu_official.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.jejunu_official_ingest import seed_jejunu_official_documents  # noqa: E402


if __name__ == "__main__":
    count = seed_jejunu_official_documents()
    print(f"제주대학교 공식 RAG 문서 색인 완료: {count}건")
