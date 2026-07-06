export type CategoryGroup = "party" | "info";

export interface CategoryMeta {
  value: string;
  label: string;
  icon: string;
  group: CategoryGroup;
}

// 기획서 6장 카테고리 체계: party 5종 + info 5종
export const CATEGORIES: CategoryMeta[] = [
  { value: "ride", label: "이동팟", icon: "🚕", group: "party" },
  { value: "drink", label: "술자리", icon: "🍻", group: "party" },
  { value: "run", label: "러닝", icon: "🏃", group: "party" },
  { value: "walk", label: "산책", icon: "🚶", group: "party" },
  { value: "tour", label: "맛집동행", icon: "🍽", group: "party" },
  { value: "food", label: "맛집", icon: "🍜", group: "info" },
  { value: "cafe", label: "카페", icon: "☕", group: "info" },
  { value: "stay", label: "숙소", icon: "🏠", group: "info" },
  { value: "living", label: "생활", icon: "🧴", group: "info" },
  { value: "qna", label: "질문답변", icon: "❓", group: "info" },
];

const CATEGORY_MAP = new Map(CATEGORIES.map((c) => [c.value, c]));

export function getCategoryMeta(value: string): CategoryMeta | undefined {
  return CATEGORY_MAP.get(value);
}
