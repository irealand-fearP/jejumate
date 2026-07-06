"use client";

import { useState } from "react";
import { getCategoryMeta } from "../lib/categories";
import { formatMinutesUntil, formatRelativeTime } from "../lib/format";
import type { Post } from "../lib/types";
import { PartyAccordion } from "./PartyAccordion";

function SourceBadge({ source }: { source: Post["source"] }) {
  if (source === "kakao") {
    return (
      <span className="rounded-full bg-zinc-100 px-2 py-0.5 text-xs text-zinc-600">
        💬 카톡수집
      </span>
    );
  }
  return (
    <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-700">
      ✍️ 직접작성
    </span>
  );
}

function CategoryBadge({ category }: { category: string }) {
  const meta = getCategoryMeta(category);
  if (!meta) return null;
  const color =
    meta.group === "party"
      ? "bg-orange-100 text-orange-700"
      : "bg-blue-100 text-blue-700";
  return (
    <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${color}`}>
      {meta.icon} {meta.label}
    </span>
  );
}

export function PostCard({ post }: { post: Post }) {
  const [expanded, setExpanded] = useState(false);
  const isKakaoParty = post.post_type === "party" && post.source === "kakao";
  const isOwnedParty = post.post_type === "party" && post.source === "user_post";

  return (
    <div className="rounded-xl border border-zinc-200 bg-white p-4 shadow-sm">
      <div className="flex items-center gap-2">
        <SourceBadge source={post.source} />
        <CategoryBadge category={post.category} />
        {isKakaoParty && (
          <span className="ml-auto rounded-full bg-zinc-200 px-2 py-0.5 text-xs text-zinc-600">
            읽기전용 · 지난글
          </span>
        )}
      </div>

      <p className={`mt-2 text-sm text-zinc-800 ${expanded ? "" : "line-clamp-2"}`}>
        {post.content}
      </p>

      <div className="mt-2 flex items-center justify-between text-xs text-zinc-400">
        <span>{formatRelativeTime(post.original_timestamp)}</span>

        {isOwnedParty && post.capacity != null && (
          <span className="font-medium text-orange-600">
            정원 {post.capacity}명 ·{" "}
            {post.deadline ? formatMinutesUntil(post.deadline) : "마감 미정"}
          </span>
        )}

        <button
          onClick={() => setExpanded((v) => !v)}
          className="text-zinc-500 underline underline-offset-2"
        >
          {expanded ? "접기" : isOwnedParty ? "▾ 펼치기" : "원문 보기"}
        </button>
      </div>

      {expanded && isOwnedParty && <PartyAccordion postId={post.id} deadline={post.deadline} />}
    </div>
  );
}
