"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";
import styles from "./Pagination.module.css";

/** 한 번에 보여줄 페이지 번호 개수(묶음 크기). */
const PAGE_WINDOW_SIZE = 5;

type PaginationProps = {
  page: number;
  totalPages: number;
  onChange: (nextPage: number) => void;
};

/**
 * '< 1 2 3 4 5 >' 형태의 페이지네이션.
 *
 * 번호는 5개씩 고정 묶음으로 보여준다 — 6페이지로 넘어가면 묶음도 '6 7 8 9 10'으로 바뀐다.
 * 화살표는 묶음이 아니라 '한 페이지'를 이동하므로, 6페이지에서 '<'를 누르면 5페이지(이전
 * 묶음의 마지막)로 자연스럽게 돌아간다.
 */
export function Pagination({ page, totalPages, onChange }: PaginationProps) {
  // 페이지가 하나뿐이면 보여줄 이유가 없다.
  if (totalPages <= 1) return null;

  const windowStart = Math.floor((page - 1) / PAGE_WINDOW_SIZE) * PAGE_WINDOW_SIZE + 1;
  const windowEnd = Math.min(windowStart + PAGE_WINDOW_SIZE - 1, totalPages);
  const pageNumbers = Array.from({ length: windowEnd - windowStart + 1 }, (_, index) => windowStart + index);

  return (
    <nav aria-label="페이지" className={styles.pagination}>
      <button
        aria-label="이전 페이지"
        className={styles.arrow}
        disabled={page === 1}
        onClick={() => onChange(page - 1)}
        type="button"
      >
        <ChevronLeft size={16} />
      </button>

      {pageNumbers.map((pageNumber) => (
        <button
          aria-current={pageNumber === page ? "page" : undefined}
          className={`${styles.pageButton} ${pageNumber === page ? styles.pageButtonActive : ""}`}
          key={pageNumber}
          onClick={() => onChange(pageNumber)}
          type="button"
        >
          {pageNumber}
        </button>
      ))}

      <button
        aria-label="다음 페이지"
        className={styles.arrow}
        disabled={page === totalPages}
        onClick={() => onChange(page + 1)}
        type="button"
      >
        <ChevronRight size={16} />
      </button>
    </nav>
  );
}
