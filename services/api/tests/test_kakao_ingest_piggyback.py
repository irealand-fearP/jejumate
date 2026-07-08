"""카톡 실시간 수집 '피기백'(서버리스 경로) 동시성·예외 안전성 테스트.

Vercel 서버리스는 백그라운드 루프를 못 돌려서, /api/home·/api/meetings·/api/board
같은 조회 요청이 들어올 때 카톡 수집을 얹어서 실행한다(maybe_ingest_kakao_now).
이 테스트는 (1) 동시 요청이 겹쳐도 실제 수집(ingest_new_messages)이 한 번만
"선점"되는지, (2) 커서가 실수로 되돌아가지 않는지, (3) 카톡 API/DB 오류가 나도
호출자(조회 API)에 예외가 전파되지 않는지를 실제 로컬 SQLite DB로 검증한다.
격리된 source 이름을 써서 실제 'kakao_live' 커서와 섞이지 않게 하고, 끝나면 정리한다.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import pytest

from app.repositories.local_store import (
    _connect,
    get_ingest_cursor,
    set_ingest_cursor,
    try_claim_kakao_ingest_attempt,
)
from app.services.kakao_ingest import maybe_ingest_kakao_now


def _cleanup(source: str) -> None:
    with _connect() as connection:
        connection.execute("DELETE FROM ingest_cursors WHERE source = ?", (source,))


@pytest.fixture
def probe_source():
    source = "test_claim_probe"
    _cleanup(source)
    yield source
    _cleanup(source)


def test_first_claim_succeeds_for_new_source(probe_source):
    assert try_claim_kakao_ingest_attempt(probe_source, min_interval_seconds=60) is True


def test_second_claim_within_interval_fails(probe_source):
    assert try_claim_kakao_ingest_attempt(probe_source, min_interval_seconds=3600) is True
    assert try_claim_kakao_ingest_attempt(probe_source, min_interval_seconds=3600) is False


def test_claim_succeeds_again_when_interval_is_zero(probe_source):
    assert try_claim_kakao_ingest_attempt(probe_source, min_interval_seconds=0) is True
    assert try_claim_kakao_ingest_attempt(probe_source, min_interval_seconds=0) is True


def test_concurrent_claims_only_one_wins(probe_source):
    # 10개 스레드가 동시에 같은 source로 선점을 시도해도 정확히 하나만 True여야 한다
    # (원자적 UPDATE ... WHERE ...가 락 없이도 이걸 보장하는지 확인).
    with ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(lambda _: try_claim_kakao_ingest_attempt(probe_source, 3600), range(10)))
    assert results.count(True) == 1


def test_set_ingest_cursor_is_monotonic(probe_source):
    set_ingest_cursor(probe_source, 100)
    set_ingest_cursor(probe_source, 50)  # 더 작은 값으로 되돌리려는 시도 — 무시돼야 함
    assert get_ingest_cursor(probe_source) == 100
    set_ingest_cursor(probe_source, 150)
    assert get_ingest_cursor(probe_source) == 150


@patch("app.services.kakao_ingest.try_claim_kakao_ingest_attempt", return_value=True)
def test_maybe_ingest_kakao_now_swallows_exceptions(mock_claim):
    with patch("app.services.kakao_ingest.ingest_new_messages") as mock_ingest:
        mock_ingest.side_effect = RuntimeError("카톡 API 다운")
        maybe_ingest_kakao_now()  # 여기서 예외가 밖으로 안 나가야 통과(호출자 응답을 실패시키면 안 됨)


@patch("app.services.kakao_ingest.try_claim_kakao_ingest_attempt", return_value=False)
def test_maybe_ingest_kakao_now_skips_when_not_claimed(mock_claim):
    with patch("app.services.kakao_ingest.ingest_new_messages") as mock_ingest:
        maybe_ingest_kakao_now()
        mock_ingest.assert_not_called()
