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
_DEPARTMENT_ALIAS_OVERRIDES = {
    "생활환경복지학과": (
        "생활환경복지학부",
        "아동·생활복지전공",
        "아동생활복지전공",
        "주거·가족복지전공",
        "주거가족복지전공",
    ),
    "스포츠과학과": ("체육학과", "체육학전공"),
    "전기공학과": ("전기에너지공학과", "전기에너지공학전공"),
    "메카트로닉스공학과": ("기계시스템공학과", "기계시스템공학전공"),
    "문화조형디자인전공": ("융합디자인학과", "융합디자인전공"),
    "자유전공": ("글로벌자율전공", "글로벌자율전공학부"),
}
_DEPARTMENT_LOCATION_OVERRIDES = (
    ("미술학과", "미술관", "지상3층", "미술관 3층 학과사무실"),
    ("의학과", "의과대학 1호관", "층 정보 없음", "의과대학 1호관"),
    ("수의예과", "수의과대학", "층 정보 없음", "수의과대학 수의예과 사무실"),
)


class CampusBuilding(TypedDict):
    source_id: str
    name: str
    lat: float
    lng: float
    description: str
    aliases: tuple[str, ...]
    room_count: int
    floors: tuple[dict[str, Any], ...]


class CampusDepartmentLocation(TypedDict):
    name: str
    aliases: tuple[str, ...]
    building_source_id: str
    building_name: str
    floor: str
    room_label: str


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


def _clean_department_name(value: str) -> str:
    name = re.sub(r"\([^)]*\)", "", value).replace(" ", "").strip("-,")
    while "학과학과" in name or "학학과" in name:
        name = name.replace("학과학과", "학과").replace("학학과", "학과")
    return name


def _department_aliases(name: str) -> set[str]:
    aliases = {name}
    if name.endswith("전공"):
        stem = name.removesuffix("전공")
        aliases.add(stem)
        aliases.add(f"{stem}과" if stem.endswith("학") else f"{stem}학과")
    elif name.endswith("학과"):
        stem = name.removesuffix("학과")
        aliases.update((stem, f"{stem}전공"))
    elif name.endswith("학부"):
        stem = name.removesuffix("학부")
        aliases.update((stem, f"{stem}학과"))
    elif name.endswith("과"):
        aliases.add(name.removesuffix("과"))
    aliases.update(_DEPARTMENT_ALIAS_OVERRIDES.get(name, ()))
    return {alias for alias in aliases if len(_normalize(alias)) >= 2}


def _names_from_office_label(label: str) -> tuple[str, ...]:
    if "사무실" not in label:
        return ()
    prefix = label.split("사무실", 1)[0].strip()
    raw_names = [part.strip() for part in prefix.split(",") if part.strip()]
    if not raw_names:
        return ()

    last_name = _clean_department_name(raw_names[-1])
    suffix = next(
        (candidate for candidate in ("학과", "전공", "학부") if last_name.endswith(candidate)),
        None,
    )
    names: list[str] = []
    for raw_name in raw_names:
        name = _clean_department_name(raw_name)
        if suffix and not name.endswith(("학과", "전공", "학부", "교육과", "의예과")):
            if suffix == "학과" and name.endswith("학"):
                name = f"{name}과"
            else:
                name = f"{name}{suffix}"
        name = _clean_department_name(name)
        if name not in {"학과", "전공", "학부"} and name.endswith(
            ("학과", "전공", "학부", "교육과", "의예과")
        ):
            names.append(name)
    return tuple(dict.fromkeys(names))


def _names_from_department_space(label: str) -> tuple[str, ...]:
    office_names = _names_from_office_label(label)
    if office_names:
        return office_names
    if "전공학과방" in label:
        stem = _clean_department_name(label.split("전공학과방", 1)[0])
        if stem:
            return (f"{stem}전공",)
    if "과방" in label:
        stem = _clean_department_name(label.split("과방", 1)[0])
        if stem and not stem.endswith(("전공", "학부")):
            return (_clean_department_name(f"{stem}과"),)
    if "전공강의실" in label:
        stem = _clean_department_name(label.split("전공강의실", 1)[0])
        if stem:
            if stem.endswith(("학과", "전공", "학부")):
                return (stem,)
            return (_clean_department_name(f"{stem}전공"),)
    return ()


def _extract_department_locations(
    buildings: list[CampusBuilding],
) -> tuple[CampusDepartmentLocation, ...]:
    locations: list[CampusDepartmentLocation] = []
    seen: set[tuple[str, str, str]] = set()
    rooms: list[tuple[CampusBuilding, str, str]] = []
    for building in buildings:
        for floor in building["floors"]:
            floor_name = str(floor.get("floor") or "층 정보 없음")
            for room_label in floor.get("spaces") or ():
                rooms.append((building, floor_name, str(room_label)))

    office_aliases: set[str] = set()
    for building, floor_name, room_label in rooms:
        for name in _names_from_office_label(room_label):
            office_aliases.update(_normalize(alias) for alias in _department_aliases(name))
            key = (name, building["source_id"], floor_name)
            if key in seen:
                continue
            seen.add(key)
            locations.append(
                {
                    "name": name,
                    "aliases": tuple(
                        sorted(
                            _department_aliases(name),
                            key=lambda value: (-len(_normalize(value)), value),
                        )
                    ),
                    "building_source_id": building["source_id"],
                    "building_name": building["name"],
                    "floor": floor_name,
                    "room_label": room_label,
                }
            )

    for building, floor_name, room_label in rooms:
        if "사무실" in room_label:
            continue
        for name in _names_from_department_space(room_label):
            aliases = _department_aliases(name)
            if any(_normalize(alias) in office_aliases for alias in aliases):
                continue
            key = (name, building["source_id"], floor_name)
            if key in seen:
                continue
            seen.add(key)
            locations.append(
                {
                    "name": name,
                    "aliases": tuple(
                        sorted(
                            _department_aliases(name),
                            key=lambda value: (-len(_normalize(value)), value),
                        )
                    ),
                    "building_source_id": building["source_id"],
                    "building_name": building["name"],
                    "floor": floor_name,
                    "room_label": room_label,
                }
            )

    buildings_by_name = {building["name"]: building for building in buildings}
    for name, building_name, floor_name, room_label in _DEPARTMENT_LOCATION_OVERRIDES:
        building = buildings_by_name[building_name]
        key = (name, building["source_id"], floor_name)
        if key in seen:
            continue
        seen.add(key)
        locations.append(
            {
                "name": name,
                "aliases": tuple(
                    sorted(
                        _department_aliases(name),
                        key=lambda value: (-len(_normalize(value)), value),
                    )
                ),
                "building_source_id": building["source_id"],
                "building_name": building_name,
                "floor": floor_name,
                "room_label": room_label,
            }
        )
    return tuple(locations)


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

    department_locations = _extract_department_locations(buildings)
    department_aliases_by_building: dict[str, set[str]] = {}
    for location in department_locations:
        department_aliases_by_building.setdefault(location["building_source_id"], set()).update(
            location["aliases"]
        )

    for building in buildings:
        aliases = set(building["aliases"])
        aliases.update(department_aliases_by_building.get(building["source_id"], ()))
        building["aliases"] = tuple(
            sorted(aliases, key=lambda value: (-len(_normalize(value)), value))
        )
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
def campus_department_locations() -> tuple[CampusDepartmentLocation, ...]:
    return _extract_department_locations(list(campus_buildings()))


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
    department_locations_by_building: dict[str, list[CampusDepartmentLocation]] = {}
    for location in campus_department_locations():
        department_locations_by_building.setdefault(location["building_source_id"], []).append(
            location
        )
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
        department_locations = department_locations_by_building.get(building["source_id"], [])
        if department_locations:
            location_text = ", ".join(
                f"{location['name']} {location['floor']} {location['room_label']}"
                for location in department_locations
            )
            body_parts.append(f"학과·전공 위치: {location_text}.")
        documents.append(
            {
                "source_id": building["source_id"],
                "title": f"제주대학교 캠퍼스맵 {building['name']} 위치",
                "body": " ".join(body_parts),
                "url": CAMPUS_MAP_SOURCE_URL,
            }
        )
    return tuple(documents)
