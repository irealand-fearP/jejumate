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

type OneSearchResult = { title: string; coords?: { lat: number; lng: number } };

// 장소명 하나를 keywordSearch로 검색해 첫 결과의 좌표를 돌려준다(실패 시 coords 없음).
function searchOnePlace(title: string): Promise<OneSearchResult> {
  return new Promise((resolve) => {
    const kakao = window.kakao;
    if (!kakao) {
      resolve({ title });
      return;
    }
    const searcher = new kakao.maps.services.Places();
    searcher.keywordSearch(`${title} ${REGION_KEYWORD}`, (result, status) => {
      if (status === kakao.maps.services.Status.OK && result.length > 0) {
        const first = result[0];
        resolve({ title, coords: { lat: Number(first.y), lng: Number(first.x) } });
      } else {
        resolve({ title });
      }
    });
  });
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
