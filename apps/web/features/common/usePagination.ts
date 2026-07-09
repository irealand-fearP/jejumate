"use client";

import { useEffect, useMemo, useRef, useState, type RefObject } from "react";

/** 한 페이지에 보여줄 항목 수(사용자 지정). */
export const DEFAULT_PAGE_SIZE = 15;

type UsePaginationResult<T> = {
  page: number;
  totalPages: number;
  /** 현재 페이지에 해당하는 항목들. */
  pageItems: T[];
  /** 페이지 이동 + 목록 상단으로 스크롤. */
  goToPage: (nextPage: number) => void;
  /** 목록 바로 위에 붙여두면 페이지 전환 시 이 지점으로 스크롤한다. */
  listTopRef: RefObject<HTMLDivElement | null>;
};

/**
 * 클라이언트 사이드 페이징. 목록 전체를 이미 받아오므로 slice로 충분하다(새 API 불필요).
 *
 * - resetKey(카테고리 필터·검색어 등)가 바뀌면 1페이지로 되돌린다.
 * - 폴링 등으로 항목 수가 줄어 현재 페이지가 범위를 벗어나면 마지막 페이지로 보정한다.
 *   (페이지 자체는 유지되므로 갱신 때문에 보던 페이지가 튀지 않는다)
 */
export function usePagination<T>(
  items: T[],
  resetKey: string,
  pageSize: number = DEFAULT_PAGE_SIZE,
): UsePaginationResult<T> {
  const [page, setPage] = useState(1);
  const listTopRef = useRef<HTMLDivElement | null>(null);

  // 항목이 없어도 1페이지로 친다(페이지네이션은 어차피 숨겨진다).
  const totalPages = Math.max(1, Math.ceil(items.length / pageSize));

  // 필터·검색어가 바뀌면 보던 페이지 번호가 의미를 잃으므로 처음으로 되돌린다.
  useEffect(() => {
    setPage(1);
  }, [resetKey]);

  // 목록이 갱신돼 항목이 줄면 현재 페이지가 빈 페이지가 될 수 있다 — 마지막 페이지로 당긴다.
  useEffect(() => {
    setPage((current) => (current > totalPages ? totalPages : current));
  }, [totalPages]);

  const pageItems = useMemo(() => {
    // 보정 effect가 돌기 전 렌더에서도 빈 화면이 안 나오도록 여기서도 범위를 클램프한다.
    const safePage = Math.min(page, totalPages);
    const start = (safePage - 1) * pageSize;
    return items.slice(start, start + pageSize);
  }, [items, page, totalPages, pageSize]);

  function goToPage(nextPage: number) {
    const clamped = Math.min(Math.max(nextPage, 1), totalPages);
    setPage(clamped);
    listTopRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  return { page, totalPages, pageItems, goToPage, listTopRef };
}
