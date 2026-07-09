import type { JejuMapPlace } from "./JejuMapPreview";

/**
 * 질문 화면 기본 지도의 중심(제주대학교 아라캠퍼스).
 * 우리 사용자가 제주대 계절학기 학생들이라 캠퍼스를 기본 화면으로 둔다
 * (팀원 프로토타입과 같은 좌표).
 */
export const JEJU_NATIONAL_UNIVERSITY_CENTER = { lat: 33.4558, lng: 126.5624 };

/** 캠퍼스가 화면에 알맞게 들어오는 확대 레벨. */
export const JEJU_NATIONAL_UNIVERSITY_ZOOM_LEVEL = 4;

/**
 * 캠퍼스 주요 건물 마커. 팀원 프로토타입에는 68개 건물의 층·호실 정보까지 있지만,
 * 질문 화면 배경 지도에는 과하다 — 학생이 실제로 찾을 만한 곳만 추렸다.
 */
export const JEJU_NATIONAL_UNIVERSITY_LANDMARKS: JejuMapPlace[] = [
  { title: "정문", lat: 33.4593139, lng: 126.5612901, description: "정문 및 수위실" },
  { title: "대학본부", lat: 33.4559382, lng: 126.5618842, description: "대학본부" },
  { title: "학생회관", lat: 33.4549703, lng: 126.5605324, description: "학생회관" },
  { title: "중앙도서관", lat: 33.4527006, lng: 126.5608489, description: "중앙도서관" },
  { title: "교양강의동", lat: 33.4556618, lng: 126.5644189, description: "교양강의동" },
  { title: "체육관", lat: 33.4561027, lng: 126.5605029, description: "체육관" },
  { title: "대운동장", lat: 33.4554274, lng: 126.5594354, description: "대운동장" },
  { title: "학생생활관 3호관", lat: 33.4515543, lng: 126.5567867, description: "기숙사" },
];
