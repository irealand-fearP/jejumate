"""
1차 규칙 필터: 키워드 매칭으로 명백히 무관한 잡담을 걸러낸다.

키워드가 하나도 안 걸리면 후보 카테고리가 비어있는 채로 반환되고, 파이프라인은
이 경우 LLM을 호출하지 않고 그대로 버린다(비용·시간 절약). 여기서 반환하는
후보는 "가능성 있는 카테고리 집합"이며, 최종 카테고리·post_type 확정은
LLM 태깅(app/tagging.py) 단계에서 한다.
"""
from app.models import CATEGORY_VALUES

# 6장 카테고리 체계(10종) 기준 키워드. 겹치는 키워드가 있으면 후보를 여러 개
# 반환하고, 최종 판단은 LLM 태깅 단계에서 문맥(모집 의도 vs 질문/추천)으로 정한다.
CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "ride": ("택시팟", "택시 같이", "택시타", "카풀", "렌터카", "동승", "같이 타"),
    "drink": ("술자리", "한잔", "맥주", "소주", "술 드실", "간술", "같이 마실"),
    "run": ("러닝", "등산", "운동장", "조깅", "축구", "농구", "볼링", "패들보드", "수영"),
    "walk": ("산책", "오름", "나들이"),
    "tour": ("카페 동행", "맛집 동행", "같이 갈 맛집", "독립서점"),
    "food": ("맛집", "흑돼지", "고기국수"),
    "cafe": ("카페", "노을 명소"),
    "stay": ("숙소", "게하", "게스트하우스", "민박"),
    "living": ("병원", "약국", "세탁", "마트", "편의점"),
    "qna": ("궁금", "환불", "수강", "시험", "알려주세요"),
}

assert set(CATEGORY_KEYWORDS) == set(CATEGORY_VALUES), "카테고리 키워드는 6장 10종과 항상 일치해야 한다"


def match_categories(content: str) -> set[str]:
    """content에 등장하는 키워드로 후보 카테고리 집합을 반환한다. 없으면 빈 집합(=버림)."""
    return {
        category
        for category, keywords in CATEGORY_KEYWORDS.items()
        if any(keyword in content for keyword in keywords)
    }
