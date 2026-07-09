"use client";

import { useEffect, useState } from "react";
import { loadKakaoMapsSdk } from "./JejuMapPreview";

/** 장소명으로 좌표를 찾아낸 결과. JejuMapPlace와 같은 형태라 그대로 마커로 쓸 수 있다. */
export type GeocodedPlace = {
  title: string;
  lat: number;
  lng: number;
};

type PlaceSearchState = {
  /** idle: 아직 검색 안 함, loading: 검색 중, done: 검색 끝. */
  status: "idle" | "loading" | "done";
  /** 좌표를 찾은 장소들(지도 마커용). */
  resolved: GeocodedPlace[];
  /** 좌표를 못 찾은 장소명들(텍스트 폴백용). */
  failedTitles: string[];
};

const IDLE_STATE: PlaceSearchState = { status: "idle", resolved: [], failedTitles: [] };

// 같은 장소명이 전국에 여럿 있을 수 있어 '제주'를 붙여 지역을 한정한다.
const REGION_KEYWORD = "제주";

type Coords = { lat: number; lng: number };

// 제주도(본섬 + 추자도·마라도 등 부속 섬)를 넉넉히 감싸는 경계 박스.
// 검색 옵션의 radius는 최대 20km라 동서로 70km가 넘는 섬 전체를 못 덮는다. 그래서 rect를 쓴다.
const JEJU_BOUNDS = { minLng: 125.95, minLat: 33.05, maxLng: 127.0, maxLat: 34.0 };
const JEJU_RECT = `${JEJU_BOUNDS.minLng},${JEJU_BOUNDS.minLat},${JEJU_BOUNDS.maxLng},${JEJU_BOUNDS.maxLat}`;

// '학생회관1호관' → '학생회관'처럼 건물 동/호 접미를 떼어낸 검색어를 만든다.
const BUILDING_SUFFIX_PATTERN = /\s*\d+\s*(호관|호점|호실|호|동|관|층|번지)$/;
const TRAILING_NUMBER_PATTERN = /\s*\d+$/;

// 카카오에 등록 안 된 세부 건물명이면 접미를 뗀 상위 명칭으로라도 찾아본다.
function simplifyPlaceName(title: string): string | null {
  const simplified = title.replace(BUILDING_SUFFIX_PATTERN, "").replace(TRAILING_NUMBER_PATTERN, "").trim();
  return simplified.length >= 2 && simplified !== title ? simplified : null;
}

// 제주 밖 좌표는 동명이인(다른 지역 같은 이름) 오검색이므로 받아들이지 않는다.
function isWithinJeju({ lat, lng }: Coords): boolean {
  return (
    lat >= JEJU_BOUNDS.minLat &&
    lat <= JEJU_BOUNDS.maxLat &&
    lng >= JEJU_BOUNDS.minLng &&
    lng <= JEJU_BOUNDS.maxLng
  );
}

type SearchVariant = { keyword: string; options?: KakaoPlaceSearchOptions };

/**
 * 한 장소명에 대해 순차로 시도할 검색 변형들. 위에서부터 시도하다 처음 성공하면 멈춘다.
 * 제주로 좁힌 검색을 먼저 두고, 전국 검색은 뒤로 미뤄 오검색 확률을 낮춘다.
 */
function buildSearchVariants(title: string): SearchVariant[] {
  const variants: SearchVariant[] = [
    { keyword: `${title} ${REGION_KEYWORD}` }, // ① 지역명을 붙인 검색
    { keyword: title, options: { rect: JEJU_RECT } }, // ② 제주 경계로 한정
    { keyword: title }, // ③ 장소명 그대로(전국) — 결과는 제주 경계 검증으로 거른다
  ];

  const simplified = simplifyPlaceName(title);
  if (simplified) {
    // ④ '학생회관1호관' 같은 세부 건물명은 상위 명칭 + 제주 한정으로 재시도
    variants.push({ keyword: simplified, options: { rect: JEJU_RECT } });
  }

  return variants;
}

// 변형 하나를 검색해 '제주 안에 있는 첫 결과'의 좌표를 돌려준다(없으면 undefined).
function runSearchVariant(variant: SearchVariant): Promise<Coords | undefined> {
  return new Promise((resolve) => {
    const kakao = window.kakao;
    if (!kakao) {
      resolve(undefined);
      return;
    }

    const searcher = new kakao.maps.services.Places();
    searcher.keywordSearch(
      variant.keyword,
      (result, status) => {
        if (status !== kakao.maps.services.Status.OK) {
          resolve(undefined);
          return;
        }
        // 결과는 정확도순이므로, 제주 안에 드는 가장 앞선 결과를 쓴다.
        const match = result
          .map((item) => ({ lat: Number(item.y), lng: Number(item.x) }))
          .find((coords) => isWithinJeju(coords));
        resolve(match);
      },
      variant.options,
    );
  });
}

type OneSearchResult = { title: string; coords?: Coords };

// 장소명 하나를 변형들로 순차 검색한다. 첫 성공에서 중단하고, 전부 실패하면 coords 없이 반환.
async function searchOnePlace(title: string): Promise<OneSearchResult> {
  for (const variant of buildSearchVariants(title)) {
    const coords = await runSearchVariant(variant);
    if (coords) return { title, coords };
  }
  return { title };
}

/**
 * 좌표가 없는 장소명들을 카카오맵 장소 검색으로 좌표로 바꿔주는 훅.
 * enabled가 true가 됐을 때(지도 토글 시)만 검색을 실행해 불필요한 API 호출을 막는다.
 */
export function useKakaoPlaceSearch(titles: string[], enabled: boolean): PlaceSearchState {
  const appKey = process.env.NEXT_PUBLIC_KAKAO_MAP_APP_KEY;
  const [state, setState] = useState<PlaceSearchState>(IDLE_STATE);

  // titles 배열은 매 렌더마다 새로 생기므로, 내용을 문자열 키로 묶어 재검색 조건을 안정화한다.
  const titlesKey = titles.join("||");

  useEffect(() => {
    if (!enabled || !appKey || titles.length === 0) return;

    let cancelled = false;
    setState({ status: "loading", resolved: [], failedTitles: [] });

    loadKakaoMapsSdk(appKey)
      .then(() => {
        if (cancelled || !window.kakao?.maps.services) {
          throw new Error("카카오맵 장소 검색 라이브러리를 쓸 수 없습니다.");
        }
        return Promise.all(titles.map((title) => searchOnePlace(title)));
      })
      .then((results) => {
        if (cancelled) return;
        const resolved: GeocodedPlace[] = [];
        const failedTitles: string[] = [];
        results.forEach((result) => {
          if (result.coords) {
            resolved.push({ title: result.title, lat: result.coords.lat, lng: result.coords.lng });
          } else {
            failedTitles.push(result.title);
          }
        });
        setState({ status: "done", resolved, failedTitles });
      })
      .catch(() => {
        // 검색 자체가 실패하면 모든 장소를 텍스트 폴백으로 돌린다.
        if (!cancelled) setState({ status: "done", resolved: [], failedTitles: titles });
      });

    return () => {
      cancelled = true;
    };
    // titles는 titlesKey로 대표하므로 의존성에서 제외한다.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, appKey, titlesKey]);

  return state;
}
