"use client";

import { useState } from "react";
import { searchPosts } from "../lib/api";
import { getCategoryMeta } from "../lib/categories";
import { formatRelativeTime } from "../lib/format";
import type { SearchResponse } from "../lib/types";

const EXAMPLE_QUESTIONS = [
  "지금 함덕 가는 택시팟 있어?",
  "성산일출봉 근처 맛집 추천해줘",
  "제주 공항 근처 숙소 있을까?",
];

export function SearchBox() {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<SearchResponse | null>(null);
  const [showEvidence, setShowEvidence] = useState(false);

  async function runSearch(question: string) {
    if (!question.trim()) return;
    setQuery(question);
    setLoading(true);
    setShowEvidence(false);
    try {
      const response = await searchPosts(question);
      setResult(response);
    } catch {
      setResult({ answer: "검색 중 문제가 발생했어요. 잠시 후 다시 시도해주세요.", evidence: [] });
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="border-b border-zinc-200 bg-white px-4 py-4">
      <h2 className="text-sm font-semibold text-zinc-700">💬 지금 궁금한 거 물어보세요</h2>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          runSearch(query);
        }}
        className="mt-2 flex gap-2"
      >
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="지금 함덕 가는 택시팟 있어?"
          className="flex-1 rounded-lg border border-zinc-300 px-3 py-2 text-sm focus:border-zinc-500 focus:outline-none"
        />
        <button
          type="submit"
          disabled={loading}
          className="rounded-lg bg-zinc-800 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
        >
          {loading ? "찾는 중..." : "질문하기"}
        </button>
      </form>

      {!result && (
        <div className="mt-3 flex flex-wrap gap-2">
          {EXAMPLE_QUESTIONS.map((q) => (
            <button
              key={q}
              onClick={() => runSearch(q)}
              className="rounded-full border border-zinc-200 bg-zinc-50 px-3 py-1 text-xs text-zinc-600 hover:bg-zinc-100"
            >
              {q}
            </button>
          ))}
        </div>
      )}

      {result && (
        <div className="mt-3 rounded-xl border border-zinc-200 bg-zinc-50 p-4">
          <p className="text-sm text-zinc-800">🤖 {result.answer}</p>

          {result.evidence.length > 0 && (
            <>
              <button
                onClick={() => setShowEvidence((v) => !v)}
                className="mt-2 text-xs font-medium text-zinc-500"
              >
                근거 보기 {showEvidence ? "▴" : "▾"}
              </button>

              {showEvidence && (
                <div className="mt-2 flex flex-col gap-2">
                  {result.evidence.map((ev) => {
                    const meta = getCategoryMeta(ev.category);
                    return (
                      <div
                        key={ev.id}
                        className="rounded-lg border border-zinc-200 bg-white p-3 text-xs"
                      >
                        <div className="text-zinc-400">
                          {ev.source === "kakao" ? "💬 카톡수집" : "✍️ 직접작성"} ·{" "}
                          {formatRelativeTime(ev.original_timestamp)} · {ev.author_nickname}
                          {meta && ` · ${meta.icon} ${meta.label}`}
                        </div>
                        <div className="mt-1 text-zinc-700">&quot;{ev.content}&quot;</div>
                      </div>
                    );
                  })}
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
