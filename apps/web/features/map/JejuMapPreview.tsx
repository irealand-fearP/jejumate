"use client";

import { useEffect, useRef, useState } from "react";
import styles from "./JejuMapPreview.module.css";
// kakao-maps.d.ts는 tsconfig include(**/*.ts)에 잡혀 전역 타입으로 자동 적용된다(별도 import 불필요).

export type JejuMapPlace = {
  title: string;
  lat: number;
  lng: number;
  description?: string;
};

type JejuMapPreviewProps = {
  places: JejuMapPlace[];
  /** 지도 높이(px). 지정하지 않으면 기본값(240px)을 쓴다. */
  height?: number;
};

const KAKAO_MAP_SCRIPT_ID = "kakao-maps-sdk-script";
const DEFAULT_MAP_HEIGHT_PX = 240;
const DEFAULT_MAP_ZOOM_LEVEL = 6;

// 카카오맵 SDK 스크립트를 문서에 한 번만 추가하고, 로드가 끝나면 resolve한다.
// 다른 컴포넌트가 이미 스크립트 태그를 추가해뒀다면(중복 추가 방지) 그 로드를 그대로 기다린다.
// 장소명→좌표 검색 훅(useKakaoPlaceSearch)도 같은 로더를 재사용하므로 export한다.
export function loadKakaoMapsSdk(appKey: string): Promise<void> {
  return new Promise((resolve, reject) => {
    if (window.kakao?.maps) {
      resolve();
      return;
    }

    const existingScript = document.getElementById(KAKAO_MAP_SCRIPT_ID);
    if (existingScript) {
      existingScript.addEventListener("load", () => window.kakao?.maps.load(resolve));
      existingScript.addEventListener("error", () => reject(new Error("카카오맵 SDK 로드 실패")));
      return;
    }

    const script = document.createElement("script");
    script.id = KAKAO_MAP_SCRIPT_ID;
    // autoload=false로 받아서, 로드 완료 후 kakao.maps.load 콜백으로 실제 초기화 시점을 제어한다.
    // libraries=services는 장소명으로 좌표를 찾는 keywordSearch(장소 검색)를 쓰기 위해 필요하다.
    script.src = `https://dapi.kakao.com/v2/maps/sdk.js?appkey=${appKey}&autoload=false&libraries=services`;
    script.async = true;
    script.addEventListener("load", () => window.kakao?.maps.load(resolve));
    script.addEventListener("error", () => reject(new Error("카카오맵 SDK 로드 실패")));
    document.head.appendChild(script);
  });
}

/** 좌표가 있는 장소들을 카카오맵 위에 마커로 표시하는 클라이언트 컴포넌트. */
export function JejuMapPreview({ places, height = DEFAULT_MAP_HEIGHT_PX }: JejuMapPreviewProps) {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const [loadError, setLoadError] = useState(false);

  // 실제 카카오 앱키는 서버 .env에서 주입한다. 코드에 절대 하드코딩하지 않는다.
  const appKey = process.env.NEXT_PUBLIC_KAKAO_MAP_APP_KEY;

  useEffect(() => {
    if (!appKey || !mapContainerRef.current || places.length === 0) return;

    let cancelled = false;

    loadKakaoMapsSdk(appKey)
      .then(() => {
        if (cancelled || !mapContainerRef.current || !window.kakao) return;

        const kakao = window.kakao;
        const center = new kakao.maps.LatLng(places[0].lat, places[0].lng);
        const map = new kakao.maps.Map(mapContainerRef.current, {
          center,
          level: DEFAULT_MAP_ZOOM_LEVEL,
        });

        places.forEach((place) => {
          const marker = new kakao.maps.Marker({
            position: new kakao.maps.LatLng(place.lat, place.lng),
            map,
            title: place.title,
          });

          if (place.description) {
            const infoWindow = new kakao.maps.InfoWindow({
              content: `<div style="padding:6px 8px;font-size:12px;">${place.title}</div>`,
            });
            kakao.maps.event.addListener(marker, "click", () => infoWindow.open(map, marker));
          }
        });
      })
      .catch(() => {
        if (!cancelled) setLoadError(true);
      });

    return () => {
      cancelled = true;
    };
  }, [appKey, places]);

  // 앱키가 없으면(아직 발급 전이거나 환경변수 누락) 조용히 아무것도 렌더링하지 않는다.
  if (!appKey || places.length === 0) return null;

  if (loadError) {
    return <div className={styles.mapError}>지도를 불러오지 못했습니다.</div>;
  }

  return <div className={styles.mapContainer} ref={mapContainerRef} style={{ height }} />;
}
