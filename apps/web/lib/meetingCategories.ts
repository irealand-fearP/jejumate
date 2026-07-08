// 홈/모임 화면 필터 칩(한글 라벨)과 백엔드 category 값(영문)을 서로 변환한다.
// 필터 체계(전체/이동/밥친구/러닝/기타/오픈채팅)와 백엔드 저장값(category 컬럼)을
// 일부러 분리했다 — '기타' 필터는 여러 category(work/coffee/other)를 하나로 묶어
// 보여주고, 백엔드 값 자체는 바꾸지 않는다.
// '오픈채팅'은 category가 아니라 source==='kakao_chat'인 모임 전체를 보여주는
// 별도 축이라 이 맵에 넣지 않는다(추후 오픈채팅 의존도를 낮출 계획이라 지금부터 분리).
export const FILTER_TO_CATEGORIES: Record<string, string[]> = {
  이동: ["move"],
  밥친구: ["meal"],
  러닝: ["run"],
  기타: ["work", "coffee", "other"],
};

// category(백엔드 값) → 필터 라벨. 여러 category가 같은 필터로 묶이므로 역방향은
// 대표 라벨 하나로만 되돌아간다(쿼리 파라미터 왕복·칩 하이라이트용).
export const CATEGORY_TO_FILTER: Record<string, string> = Object.fromEntries(
  Object.entries(FILTER_TO_CATEGORIES).flatMap(([filter, categories]) =>
    categories.map((category) => [category, filter])
  )
);
