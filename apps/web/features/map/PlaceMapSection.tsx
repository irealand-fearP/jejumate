"use client";

import { useState } from "react";
import { ExternalLink, MapPin } from "lucide-react";
import { JejuMapPreview, type JejuMapPlace } from "./JejuMapPreview";
import styles from "./PlaceMapSection.module.css";

export type PlaceMapPlace = {
  title: string;
  /** 좌표는 아직 확보 못한 장소도 있을 수 있어(예: RAG 답변 출처) 선택값이다. */
  lat?: number;
  lng?: number;
  description?: string;
  /** 좌표가 없는 장소를 텍스트로 보여줄 때 참고 링크(예: 오픈채팅방)로 쓴다. */
  url?: string;
};

type PlaceMapSectionProps = {
  places: PlaceMapPlace[] | undefined;
};

function hasCoordinates(place: PlaceMapPlace): place is PlaceMapPlace & { lat: number; lng: number } {
  return typeof place.lat === "number" && typeof place.lng === "number";
}

/**
 * 좌표가 있는 장소는 '지도에서 보기' 토글로 실제 카카오맵을 보여주고,
 * 좌표가 없는 장소는 텍스트 목록(장소명 + 참고 링크)으로만 보여준다.
 * 좌표 유무가 섞여 있으면 두 표시 방식을 함께 쓴다.
 */
export function PlaceMapSection({ places }: PlaceMapSectionProps) {
  const [showMap, setShowMap] = useState(false);

  if (!places || places.length === 0) return null;

  const placesWithCoords = places.filter(hasCoordinates);
  const placesWithoutCoords = places.filter((place) => !hasCoordinates(place));

  const mapPlaces: JejuMapPlace[] = placesWithCoords.map((place) => ({
    title: place.title,
    lat: place.lat,
    lng: place.lng,
    description: place.description,
  }));

  return (
    <section className={styles.placeMapSection}>
      {placesWithCoords.length > 0 ? (
        <>
          <button className={styles.toggleButton} onClick={() => setShowMap((prev) => !prev)} type="button">
            <MapPin size={14} />
            <span>{showMap ? "지도 닫기" : "지도에서 보기"}</span>
          </button>
          {showMap ? <JejuMapPreview places={mapPlaces} /> : null}
        </>
      ) : null}
      {placesWithoutCoords.length > 0 ? (
        <ul className={styles.placeList}>
          {placesWithoutCoords.map((place, index) => (
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
