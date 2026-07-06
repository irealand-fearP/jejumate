import type {
  ApplicationListResponse,
  ApplicationOut,
  PartyPostCreateResponse,
  Post,
  PostStatus,
  SearchResponse,
} from "./types";

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

export interface PartyPostInput {
  category: string;
  content: string;
  capacity: number;
  deadline_minutes: number;
  nickname: string;
}

export async function createPartyPost(
  input: PartyPostInput
): Promise<PartyPostCreateResponse> {
  const res = await fetch(new URL("/posts/party", API_BASE).toString(), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!res.ok) throw new Error("파티 등록에 실패했습니다");
  return res.json();
}

export async function fetchPostStatus(postId: string): Promise<PostStatus> {
  const res = await fetch(new URL(`/posts/${postId}/status`, API_BASE).toString(), {
    cache: "no-store",
  });
  if (!res.ok) throw new Error("모집 현황을 불러오지 못했습니다");
  return res.json();
}

export async function applyToPost(
  postId: string,
  input: { nickname: string; message?: string }
): Promise<ApplicationOut> {
  const res = await fetch(new URL(`/posts/${postId}/applications`, API_BASE).toString(), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail ?? "신청에 실패했습니다");
  }
  return res.json();
}

export async function fetchApplications(
  postId: string,
  ownerSecret?: string
): Promise<ApplicationListResponse> {
  const url = new URL(`/posts/${postId}/applications`, API_BASE);
  if (ownerSecret) url.searchParams.set("owner_secret", ownerSecret);
  const res = await fetch(url.toString(), { cache: "no-store" });
  if (!res.ok) throw new Error("신청 목록을 불러오지 못했습니다");
  return res.json();
}

async function reviewApplication(
  postId: string,
  applicationId: string,
  ownerSecret: string,
  action: "approve" | "reject"
): Promise<ApplicationOut> {
  const url = new URL(`/posts/${postId}/applications/${applicationId}/${action}`, API_BASE);
  url.searchParams.set("owner_secret", ownerSecret);
  const res = await fetch(url.toString(), { method: "POST" });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail ?? "처리에 실패했습니다");
  }
  return res.json();
}

export function approveApplication(postId: string, applicationId: string, ownerSecret: string) {
  return reviewApplication(postId, applicationId, ownerSecret, "approve");
}

export function rejectApplication(postId: string, applicationId: string, ownerSecret: string) {
  return reviewApplication(postId, applicationId, ownerSecret, "reject");
}
