"""제주대학교 공식 캠퍼스맵 건물 좌표와 검색 별칭을 제공한다."""
from __future__ import annotations

import ast
import json
import math
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, TypedDict


CAMPUS_MAP_SOURCE_URL = "https://www.jejunu.ac.kr/schoolinfo/campinfo/campusmap.htm"
_CAMPUS_MAP_ASSET = (
    Path(__file__).resolve().parents[4]
    / "apps"
    / "web"
    / "public"
    / "campus-map"
    / "vworld_3d_preview.html"
)
_VIZ_DATA_PATTERN = re.compile(
    r'<script id="viz-data" type="application/json">(?P<data>.*?)</script>',
    re.DOTALL,
)
_ALIASES_PATTERN = re.compile(
    r"var buildingSearchAliases\s*=\s*(?P<data>\{.*?\});",
    re.DOTALL,
)
_CAMPUS_BUILDING_ALIAS_OVERRIDES = {
    "생명자원과학대학": (
        "생명과학대",
        "생명과학대학",
        "생명자원과학대",
        "농생대",
        "농생명대",
        "농생명과학대",
    ),
}


class CampusBuilding(TypedDict):
    source_id: str
    name: str
    lat: float
    lng: float
    description: str
    aliases: tuple[str, ...]
    room_count: int
    floors: tuple[dict[str, Any], ...]


def _normalize(value: str) -> str:
    return re.sub(r"[^0-9a-z가-힣]", "", value.lower())


def _source_id(building: dict[str, Any]) -> str:
    romanized = str(building.get("nameRomanized") or building["name"])
    slug = re.sub(r"[^a-z0-9]+", "-", romanized.lower()).strip("-")
    return f"campus-building-{slug}"


def _distance_m(a: dict[str, Any], b: dict[str, Any]) -> float:
    mean_lat = math.radians((float(a["lat"]) + float(b["lat"])) / 2)
    dy = (float(a["lat"]) - float(b["lat"])) * 111_320
    dx = (float(a["lng"]) - float(b["lng"])) * 111_320 * math.cos(mean_lat)
    return math.hypot(dx, dy)


def _direction_from(origin: dict[str, Any], target: dict[str, Any]) -> str:
    mean_lat = math.radians((float(origin["lat"]) + float(target["lat"])) / 2)
    north = (float(target["lat"]) - float(origin["lat"])) * 111_320
    east = (float(target["lng"]) - float(origin["lng"])) * 111_320 * math.cos(mean_lat)
    angle = (math.degrees(math.atan2(east, north)) + 360) % 360
    directions = ("북쪽", "북동쪽", "동쪽", "남동쪽", "남쪽", "남서쪽", "서쪽", "북서쪽")
    return directions[int((angle + 22.5) // 45) % 8]


def _generated_aliases(name: str) -> set[str]:
    aliases = {name}
    replacements = (
        ("공과대학", "공대"),
        ("해양과학대학", "해대"),
        ("자연과학대학", "자과대"),
        ("인문대학", "인문대"),
        ("사범대학", "사대"),
        ("의과대학", "의대"),
        ("학생생활관", "생활관"),
    )
    for original, abbreviation in replacements:
        if original in name:
            aliases.add(name.replace(original, abbreviation))
    if name.startswith("학생생활관"):
        aliases.add(name.replace("학생생활관", "기숙사"))
    if name == "골프아카데미":
        aliases.update(("골프연습장", "교내 골프연습장", "골프장"))
    return aliases


@lru_cache(maxsize=1)
def campus_buildings() -> tuple[CampusBuilding, ...]:
    html = _CAMPUS_MAP_ASSET.read_text(encoding="utf-8")
    viz_match = _VIZ_DATA_PATTERN.search(html)
    if not viz_match:
        raise RuntimeError("캠퍼스맵 건물 데이터를 찾지 못했습니다.")
    payload = json.loads(viz_match.group("data"))
    raw_buildings = payload.get("buildings") or []

    alias_match = _ALIASES_PATTERN.search(html)
    configured_aliases: dict[str, list[str]] = {}
    if alias_match:
        parsed_aliases = ast.literal_eval(alias_match.group("data"))
        if isinstance(parsed_aliases, dict):
            configured_aliases = parsed_aliases

    buildings: list[CampusBuilding] = []
    for raw in raw_buildings:
        if not isinstance(raw, dict) or not raw.get("name"):
            continue
        name = str(raw["name"])
        aliases = _generated_aliases(name)
        aliases.update(str(alias) for alias in configured_aliases.get(name, []))
        aliases.update(_CAMPUS_BUILDING_ALIAS_OVERRIDES.get(name, ()))
        buildings.append(
            {
                "source_id": _source_id(raw),
                "name": name,
                "lat": float(raw["lat"]),
                "lng": float(raw["lng"]),
                "description": "",
                "aliases": tuple(sorted(aliases, key=lambda value: (-len(_normalize(value)), value))),
                "room_count": int(raw.get("roomCount") or 0),
                "floors": tuple(raw.get("floors") or ()),
            }
        )

    for building in buildings:
        nearest = min(
            (candidate for candidate in buildings if candidate["source_id"] != building["source_id"]),
            key=lambda candidate: _distance_m(building, candidate),
        )
        building["description"] = (
            f"{nearest['name']}에서 {_direction_from(nearest, building)} "
            f"약 {round(_distance_m(building, nearest))}m"
        )
    return tuple(buildings)


@lru_cache(maxsize=1)
def _aliases_by_normalized_name() -> dict[str, tuple[CampusBuilding, ...]]:
    matches: dict[str, list[CampusBuilding]] = {}
    for building in campus_buildings():
        for alias in building["aliases"]:
            normalized = _normalize(alias)
            if len(normalized) < 2:
                continue
            candidates = matches.setdefault(normalized, [])
            if building not in candidates:
                candidates.append(building)
    return {key: tuple(value) for key, value in matches.items()}


def match_campus_building(question: str) -> CampusBuilding | None:
    normalized_question = _normalize(question)
    matching_aliases = sorted(
        (
            alias
            for alias in _aliases_by_normalized_name()
            if alias and alias in normalized_question
        ),
        key=len,
        reverse=True,
    )
    for alias in matching_aliases:
        candidates = _aliases_by_normalized_name()[alias]
        if len(candidates) == 1:
            return candidates[0]
        # 더 짧은 공통 별칭(예: 공대)으로 임의의 건물을 고르지 않는다.
        if len(alias) == len(matching_aliases[0]):
            return None
    return None


@lru_cache(maxsize=1)
def campus_buildings_by_source_id() -> dict[str, CampusBuilding]:
    return {building["source_id"]: building for building in campus_buildings()}


def campus_building_documents() -> tuple[dict[str, str], ...]:
    documents: list[dict[str, str]] = []
    buildings = campus_buildings()
    for building in buildings:
        nearby = sorted(
            (candidate for candidate in buildings if candidate["source_id"] != building["source_id"]),
            key=lambda candidate: _distance_m(building, candidate),
        )[:3]
        nearby_text = ", ".join(
            f"{candidate['name']}에서 {_direction_from(candidate, building)} 약 {round(_distance_m(building, candidate))}m"
            for candidate in nearby
        )
        floor_names = [str(floor.get("floor")) for floor in building["floors"] if floor.get("floor")]
        body_parts = [
            f"제주대학교 공식 아라캠퍼스맵의 {building['name']} 위치 안내.",
            f"{building['name']}의 지도 좌표는 위도 {building['lat']}, 경도 {building['lng']}이다.",
            f"주변 기준: {nearby_text}.",
        ]
        if floor_names:
            body_parts.append(f"캠퍼스맵에 표시된 층: {', '.join(floor_names)}.")
        if building["room_count"]:
            body_parts.append(f"캠퍼스맵에 등록된 공간은 {building['room_count']}개다.")
        documents.append(
            {
                "source_id": building["source_id"],
                "title": f"제주대학교 캠퍼스맵 {building['name']} 위치",
                "body": " ".join(body_parts),
                "url": CAMPUS_MAP_SOURCE_URL,
            }
        )
    return tuple(documents)
