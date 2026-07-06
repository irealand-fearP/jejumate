import type { Post, SearchResponse } from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function fetchPosts(category: string | null): Promise<Post[]> {
  const url = new URL("/posts", API_BASE);
  if (category) url.searchParams.set("category", category);

  const res = await fetch(url.toString(), { cache: "no-store" });
  if (!res.ok) throw new Error("피드를 불러오지 못했습니다");
  return res.json();
}

/**
 * 질문창은 항상 전체 데이터 대상 검색이다(카테고리 필터는 피드에만 적용,
 * 화면흐름.md 4장). 그래서 category 파라미터를 받지 않는다.
 */
export async function searchPosts(query: string): Promise<SearchResponse> {
  const res = await fetch(new URL("/search", API_BASE).toString(), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query }),
  });
  if (!res.ok) throw new Error("검색에 실패했습니다");
  return res.json();
}
