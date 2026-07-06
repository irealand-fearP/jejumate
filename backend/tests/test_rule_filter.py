"""
1차 규칙 필터 테스트 (태스크4).

키워드가 하나도 안 걸리는 잡담은 후보 카테고리가 비어있어야 하고(=LLM 호출 없이
버림), 키워드가 걸리면 6장 10종 카테고리 중 후보 집합을 반환해야 한다.
"""
from app.rule_filter import match_categories


def test_no_keyword_match_returns_empty_set():
    assert match_categories("ㅋㅋㅋㅋㅋ 넵") == set()
    assert match_categories("저요!") == set()


def test_ride_keyword_matches():
    assert "ride" in match_categories("2시반 함덕해수욕장 택시 같이 타실 분 있나용")


def test_food_keyword_matches():
    assert "food" in match_categories("흑돼지 맛집 추천해주세요")


def test_stay_keyword_matches():
    assert "stay" in match_categories("제주 공항 근처 싼 숙소 추천해주세요")


def test_qna_keyword_matches():
    assert "qna" in match_categories("혹시 첫째주에 수강취소하면 수강료환불 언제쯤 들어오나용?")


def test_multiple_keyword_categories_can_match_together():
    candidates = match_categories("카페 동행 같이 갈 맛집 추천해주세요")
    assert "food" in candidates
    assert "tour" in candidates
