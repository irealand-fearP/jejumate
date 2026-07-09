"use client";

import { useState } from "react";
import { ExternalLink, MapPin } from "lucide-react";
import { JejuMapPreview, type JejuMapPlace } from "./JejuMapPreview";
import { useKakaoPlaceSearch } from "./useKakaoPlaceSearch";
import styles from "./PlaceMapSection.module.css";

export type PlaceMapPlace = {
  title: string;
  /** 좌표를 미리 확보한 장소는 검색 없이 바로 지도에 찍는다(선택값). */
  lat?: number;
  lng?: number;
  description?: string;
  /** 좌표를 못 찾은 장소를 텍스트로 보여줄 때 참고 링크(예: 오픈채팅방)로 쓴다. */
  url?: string;
};

type PlaceMapSectionProps = {
  places: PlaceMapPlace[] | undefined;
};

function hasCoordinates(place: PlaceMapPlace): place is PlaceMapPlace & { lat: number; lng: number } {
  return typeof place.lat === "number" && typeof place.lng === "number";
}

/**
 * '지도에서 보기' 토글을 누르면, 좌표가 없는 장소는 카카오맵 장소 검색으로 좌표를 찾아
 * 실제 지도에 마커로 표시한다. 검색에 실패한 장소만 텍스트 목록으로 폴백한다.
 * 검색은 지도를 열 때만 실행해 불필요한 API 호출을 막는다.
 */
export function PlaceMapSection({ places }: PlaceMapSectionProps) {
  const [showMap, setShowMap] = useState(false);

  const safePlaces = places ?? [];
  const placesWithCoords = safePlaces.filter(hasCoordinates);
  const placesNeedingSearch = safePlaces.filter((place) => !hasCoordinates(place));
  const titlesToSearch = placesNeedingSearch.map((place) => place.title);

  // 지도를 연 상태(showMap)일 때만 좌표 검색을 실행한다.
  const { status, resolved, failedTitles } = useKakaoPlaceSearch(titlesToSearch, showMap);

  // 훅 규칙상 훅 호출 뒤에 빈 목록을 걸러낸다.
  if (safePlaces.length === 0) return null;

  // 미리 받은 좌표 + 검색으로 찾은 좌표를 합쳐 지도에 표시한다.
  const mapPlaces: JejuMapPlace[] = [
    ...placesWithCoords.map((place) => ({
      title: place.title,
      lat: place.lat,
      lng: place.lng,
      description: place.description,
    })),
    ...resolved,
  ];

  // 검색에 실패한 장소만 텍스트로 폴백한다(원본에서 url 등을 다시 찾아 붙인다).
  const failedPlaces = placesNeedingSearch.filter((place) => failedTitles.includes(place.title));

  return (
    <section className={styles.placeMapSection}>
      <button className={styles.toggleButton} onClick={() => setShowMap((prev) => !prev)} type="button">
        <MapPin size={14} />
        <span>{showMap ? "지도 닫기" : "지도에서 보기"}</span>
      </button>

      {showMap ? (
        status === "loading" ? (
          <div className={styles.mapLoading}>지도를 준비하는 중…</div>
        ) : mapPlaces.length > 0 ? (
          <JejuMapPreview places={mapPlaces} />
        ) : null
      ) : null}

      {failedPlaces.length > 0 ? (
        <ul className={styles.placeList}>
          {failedPlaces.map((place, index) => (
            <li className={styles.placeItem} key={`${place.title}-${index}`}>
              <span>{place.title}</span>
              {place.url ? (
                <a href={place.url} rel="noreferrer" target="_blank">
                  <ExternalLink size={12} />
                  오픈채팅방 참고
                </a>
              ) : null}
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}
