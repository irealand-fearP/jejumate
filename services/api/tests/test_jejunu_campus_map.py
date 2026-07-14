"""제주대학교 캠퍼스맵 건물 데이터와 별칭 매칭을 검증한다."""
from __future__ import annotations

from app.data.jejunu_campus_map import (
    CAMPUS_MAP_SOURCE_URL,
    campus_building_documents,
    campus_buildings,
    match_campus_building,
)


def test_loads_all_campus_map_buildings_with_unique_source_ids():
    buildings = campus_buildings()

    assert len(buildings) == 68
    assert len({building["source_id"] for building in buildings}) == 68


def test_matches_golf_practice_range_alias():
    building = match_campus_building("골프연습장은 어디에 있어?")

    assert building is not None
    assert building["name"] == "골프아카데미"
    assert building["lat"] == 33.4516068
    assert building["lng"] == 126.5630135


def test_matches_engineering_building_three_alias_without_spaces():
    building = match_campus_building("공대3호관 어디에있어?")

    assert building is not None
    assert building["name"] == "공과대학3호관"
    assert building["lat"] == 33.45651
    assert building["lng"] == 126.5655039


def test_does_not_guess_ambiguous_engineering_college_alias():
    assert match_campus_building("공대 어디야?") is None


def test_building_documents_include_coordinates_and_official_source():
    documents = campus_building_documents()
    engineering_three = next(
        document
        for document in documents
        if document["source_id"] == "campus-building-gonggwadaehak3hogwan"
    )

    assert len(documents) == 68
    assert "위도 33.45651, 경도 126.5655039" in engineering_three["body"]
    assert "주변 기준" in engineering_three["body"]
    assert engineering_three["url"] == CAMPUS_MAP_SOURCE_URL
