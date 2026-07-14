"""제주대 통합검색 API 결과의 공식 RAG 변환을 검증한다."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.services import jejunu_portal_search


def _response(payload: dict) -> MagicMock:
    response = MagicMock()
    response.json.return_value = payload
    return response


def test_build_official_search_query_rewrites_parking_question():
    assert (
        jejunu_portal_search.build_official_search_query("주차등록은 어디서 해?")
        == "자동차 정기이용"
    )


def test_choose_menu_prefers_writers_notice_page():
    menu = jejunu_portal_search._choose_menu(
        [
            {
                "CS_URL": "/lifescience",
                "URLS": "index/laboratory",
                "CM_NAME": "실험실 소개",
                "CS_TITLE": "제주대학교 생물학과",
            },
            {
                "CS_URL": "/lifescience",
                "URLS": "index/community/notice",
                "CM_NAME": "공지사항",
                "CS_TITLE": "제주대학교 생물학과",
            },
        ],
        "생물학과",
    )

    assert menu is not None
    assert menu["URLS"] == "index/community/notice"
    assert (
        jejunu_portal_search.build_official_search_query("제주대 교환학생 신청 알려줘")
        == "교환학생 신청"
    )


@patch("app.services.jejunu_portal_search.httpx.get")
def test_fetches_article_body_attachments_and_original_url(mock_get):
    mock_get.side_effect = [
        _response(
            {
                "error": False,
                "article": {
                    "items": [
                        {
                            "BA_SEQ": 270790,
                            "BA_TITLE": "2026년 1학기 자동차 정기이용 등록 절차 안내",
                            "BA_WRITE_TIME": "2026-03-04",
                            "BA_WRITER": "대학본부",
                        }
                    ]
                },
            }
        ),
        _response(
            {
                "error": False,
                "article": {
                    "seq": 270790,
                    "stat": "OK",
                    "title": "2026년 1학기 자동차 정기이용 등록 절차 안내",
                    "writer": "대학본부",
                    "boardName": "공지사항",
                    "contents": "<p>신청방법: <strong>교통상황실 방문 신청</strong></p><table><tr><td>위치</td><td>산학협력관 1층 북동측</td></tr></table>",
                },
                "menus": [
                    {
                        "CS_URL": "/",
                        "URLS": "ara/noticesurvey/outEvent",
                        "CS_TITLE": "제주대학교",
                    }
                ],
                "files": [{"no": 1, "name": "자동차 정기이용 등록 신청서.hwp"}],
            }
        ),
    ]

    documents = jejunu_portal_search.fetch_jejunu_official_documents("자동차 정기이용")

    assert len(documents) == 1
    assert documents[0]["source_id"] == "portal-article-270790"
    assert "교통상황실 방문 신청" in documents[0]["body"]
    assert "산학협력관 1층 북동측" in documents[0]["body"]
    assert "자동차 정기이용 등록 신청서.hwp" in documents[0]["body"]
    assert documents[0]["url"] == (
        "https://www.jejunu.ac.kr/ara/noticesurvey/outEvent.htm?act=view&seq=270790"
    )


@patch("app.services.jejunu_portal_search.seed_jejunu_official_documents", return_value=1)
@patch("app.services.jejunu_portal_search.fetch_jejunu_official_documents")
def test_search_result_ingest_is_cached_per_process(mock_fetch, mock_seed):
    mock_fetch.return_value = (
        {
            "source_id": "portal-article-270790",
            "title": "주차 등록 안내",
            "body": "교통상황실 방문 신청",
            "url": "https://www.jejunu.ac.kr/notice",
        },
    )
    jejunu_portal_search.search_and_ingest_jejunu_official.cache_clear()

    assert jejunu_portal_search.search_and_ingest_jejunu_official("자동차 정기이용") == 1
    assert jejunu_portal_search.search_and_ingest_jejunu_official("자동차 정기이용") == 1

    mock_fetch.assert_called_once_with("자동차 정기이용")
    mock_seed.assert_called_once()
    jejunu_portal_search.search_and_ingest_jejunu_official.cache_clear()
