"""/api/home·/api/meetings·/api/board가 카톡 피기백을 BackgroundTasks로 등록하는지
회귀 테스트.

실제 "응답이 먼저 오고 나중에 백그라운드 작업이 끝난다"는 타이밍은 실제 uvicorn
서버 + 별도 HTTP 클라이언트로만 확인 가능하다(TestClient는 ASGI 호출 전체가 끝날
때까지 기다리므로 이 테스트로는 그 부분을 증명할 수 없다 — 로컬에서 uvicorn으로
직접 확인함, 응답 6.8ms 즉시 도착 후 몇 초 뒤 커서 전진 확인). 여기서는 최소한
"라우트가 maybe_ingest_kakao_now를 background_tasks.add_task로 등록해 호출한다"는
배선(wiring) 자체만 회귀 검증한다.
"""
from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


@patch("app.api.routes.home.maybe_ingest_kakao_now")
def test_home_route_schedules_piggyback(mock_ingest):
    response = client.get("/api/home")
    assert response.status_code == 200
    mock_ingest.assert_called_once_with()


@patch("app.api.routes.meetings.maybe_ingest_kakao_now")
def test_meetings_route_schedules_piggyback(mock_ingest):
    response = client.get("/api/meetings")
    assert response.status_code == 200
    mock_ingest.assert_called_once_with()


@patch("app.api.routes.board.maybe_ingest_kakao_now")
def test_board_route_schedules_piggyback(mock_ingest):
    response = client.get("/api/board")
    assert response.status_code == 200
    mock_ingest.assert_called_once_with()
