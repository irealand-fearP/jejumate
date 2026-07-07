// 홈/모임 화면 필터 칩(한글 라벨)과 백엔드 category 값(영문)을 서로 변환한다.
// 두 화면(MeetingTimeline, MeetingsScreen)이 같은 매핑을 써야 쿼리 파라미터
// 왕복(라벨 → 쿼리 → 라벨)이 어긋나지 않는다.
export const FILTER_TO_CATEGORY: Record<string, string> = {
  밥친구: "meal",
  작업: "work",
  이동: "move",
  커피챗: "coffee",
  러닝: "run",
};

export const CATEGORY_TO_FILTER: Record<string, string> = Object.fromEntries(
  Object.entries(FILTER_TO_CATEGORY).map(([filter, category]) => [category, filter])
);
