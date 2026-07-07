"use client";

import { useMemo, useState } from "react";
import { MobileShell } from "@/features/common/MobileShell";
import type { BoardData } from "@/lib/api";
import styles from "./ServicePages.module.css";

export function BoardScreen({ data }: { data: BoardData }) {
  const filters = useMemo(() => ["전체", ...data.categories], [data.categories]);
  const [activeFilter, setActiveFilter] = useState(filters[0] ?? "전체");
  const posts = activeFilter === "전체" ? data.posts : data.posts.filter((post) => post.category === activeFilter);

  return (
    <MobileShell active="board" title="생활게시판" subtitle="이웃과 가볍게 묻고 나눠요">
      <div className={styles.notice}>{data.notice}</div>
      <div className={styles.toolbar}>
        {filters.map((filter) => (
          <button
            className={`${styles.chip} ${activeFilter === filter ? styles.chipActive : ""}`}
            key={filter}
            onClick={() => setActiveFilter(filter)}
            type="button"
          >
            {filter}
          </button>
        ))}
      </div>
      <section className={styles.boardList}>
        {posts.map((post) => (
          <article className={styles.boardCard} key={post.id}>
            <span className={styles.boardCategoryTag}>{post.category}</span>
            <h2>{post.title}</h2>
            <p>{post.body}</p>
            <span className={styles.boardMeta}>{post.author_nickname}</span>
          </article>
        ))}
      </section>
    </MobileShell>
  );
}
