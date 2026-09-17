"""사장님이 카톡 PC 대화 .txt 파일을 직접 올려 RAG에 즉시 반영하는 기능 테스트.

자동 스케줄러 없이 원할 때 파일을 올리면 파싱→멱등 적재→RAG 색인까지 한 번에
끝나야 한다. 실제 OpenAI 호출(embed_text/classify_message)은 목으로 대체한다.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import create_app
from app.repositories import local_store
from app.services import kakao_ingest


SAMPLE_TXT = """제주 생활 정보방 님과 카카오톡 대화
저장한 날짜 : 2026-07-17 10:00:08

--------------- 2026년 7월 17일 금요일 ---------------
채팅방 안내 문구는 메시지가 아닙니다.
[여행자] [오전 9:16] 공항으로 같이 이동하실 분 계신가요 택시팟 구합니다.
[도우미] [오후 1:05] 중고 자전거 나눔합니다 필요하신 분 연락주세요.
"""

BROKEN_TXT = "이건 카카오톡 내보내기 헤더가 아닌 그냥 텍스트입니다.\n아무 내용도 없어요.\n"


@pytest.fixture(autouse=True)
def isolated_sqlite_db(tmp_path, monkeypatch):
    db_path = tmp_path / "test.sqlite3"
    monkeypatch.setattr(local_store, "DB_PATH", db_path)
    monkeypatch.setattr(local_store, "USE_POSTGRES", False)
    local_store.ensure_database()
    yield


@pytest.fixture(autouse=True)
def stub_openai_calls(monkeypatch):
    # 실제 임베딩·분류 API를 부르지 않도록 목으로 대체한다(네트워크·비용 없이 검증).
    monkeypatch.setattr(kakao_ingest, "embed_text", lambda text: [0.1, 0.2])
    monkeypatch.setattr(
        kakao_ingest,
        "classify_message",
        lambda content: {"type": "other", "title": "", "meeting_category": None},
    )


@pytest.fixture
def client():
    return TestClient(create_app())


@pytest.fixture(autouse=True)
def configured_secret(monkeypatch):
    monkeypatch.setattr(settings, "kakao_upload_secret", "test-upload-secret")
    yield


def _upload(client, *, text: str, authorization: str | None):
    headers = {"Authorization": authorization} if authorization else {}
    return client.post(
        "/api/ingest/kakao/upload-file",
        files={"file": ("chat.txt", text.encode("utf-8"), "text/plain")},
        headers=headers,
    )


def test_upload_file_parses_and_indexes_immediately(client):
    response = _upload(client, text=SAMPLE_TXT, authorization="Bearer test-upload-secret")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["parsed"] == 2
    assert data["accepted"] == 2
    assert data["duplicates"] == 0
    assert data["indexed"] == 2


def test_upload_file_second_upload_of_same_file_is_all_duplicates(client):
    _upload(client, text=SAMPLE_TXT, authorization="Bearer test-upload-secret")

    response = _upload(client, text=SAMPLE_TXT, authorization="Bearer test-upload-secret")

    data = response.json()["data"]
    assert data["parsed"] == 2
    assert data["accepted"] == 0
    assert data["duplicates"] == 2
    assert data["indexed"] == 0


def test_upload_file_rejects_wrong_secret(client):
    response = _upload(client, text=SAMPLE_TXT, authorization="Bearer wrong-secret")

    assert response.status_code == 403


def test_upload_file_rejects_missing_authorization_header(client):
    response = _upload(client, text=SAMPLE_TXT, authorization=None)

    assert response.status_code == 403


def test_upload_file_rejects_broken_txt_with_400(client):
    response = _upload(client, text=BROKEN_TXT, authorization="Bearer test-upload-secret")

    assert response.status_code == 400
    assert "헤더" in response.json()["detail"]
