"use client";

import { useEffect, useState } from "react";
import { CategoryFilter } from "./components/CategoryFilter";
import { PartyRegisterModal } from "./components/PartyRegisterModal";
import { PostCard } from "./components/PostCard";
import { SearchBox } from "./components/SearchBox";
import { WeatherCard } from "./components/WeatherCard";
import { fetchPosts } from "./lib/api";
import type { Post } from "./lib/types";

// "실시간으로 갱신된다"는 데모 포인트를 위한 피드 자동 폴링 주기.
// 파티 현황(PartyAccordion)의 8초 폴링과 별개로 피드 전체를 갱신한다.
const FEED_POLL_INTERVAL_MS = 12000;

export default function Home() {
  const [category, setCategory] = useState<string | null>(null);
  const [posts, setPosts] = useState<Post[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showRegisterModal, setShowRegisterModal] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    let cancelled = false;

    function load(showLoading: boolean) {
      if (showLoading) {
        setLoading(true);
        setError(null);
      }
      fetchPosts(category)
        .then((data) => {
          if (!cancelled) {
            setPosts(data);
            if (showLoading) setError(null);
          }
        })
        .catch(() => {
          // 폴링 중 실패는 화면을 비우지 않고 조용히 넘어간다(다음 폴링에서 복구 시도).
          if (!cancelled && showLoading) setError("피드를 불러오지 못했어요");
        })
        .finally(() => {
          if (!cancelled && showLoading) setLoading(false);
        });
    }

    load(true);
    const timer = setInterval(() => load(false), FEED_POLL_INTERVAL_MS);

    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [category, refreshKey]);

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-1 flex-col bg-zinc-50">
      <header className="border-b border-zinc-200 bg-white px-4 py-3">
        <h1 className="text-lg font-bold text-zinc-900">🌴 제주메이트(가칭)</h1>
        <p className="text-xs text-zinc-500">혼자 가긴 아쉬울 때, 같이 갈 사람 찾기</p>
      </header>

      <SearchBox />

      <div className="border-b border-zinc-200 bg-white">
        <CategoryFilter selected={category} onSelect={setCategory} />
      </div>

      <div className="px-4 py-3">
        <button
          onClick={() => setShowRegisterModal(true)}
          className="w-full rounded-lg border border-orange-300 bg-orange-50 py-2 text-sm font-medium text-orange-700"
        >
          + 파티 등록하기
        </button>
      </div>

      {showRegisterModal && (
        <PartyRegisterModal
          onClose={() => setShowRegisterModal(false)}
          onCreated={() => setRefreshKey((k) => k + 1)}
        />
      )}

      <main className="flex flex-1 flex-col gap-3 px-4 py-4">
        <WeatherCard />
        {loading && <p className="text-sm text-zinc-400">불러오는 중...</p>}
        {error && <p className="text-sm text-red-500">{error}</p>}
        {!loading && !error && posts.length === 0 && (
          <p className="text-sm text-zinc-400">아직 등록된 글이 없어요.</p>
        )}
        {posts.map((post) => (
          <PostCard key={post.id} post={post} />
        ))}
      </main>
    </div>
  );
}
