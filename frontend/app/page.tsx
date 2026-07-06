"use client";

import { useEffect, useState } from "react";
import { CategoryFilter } from "./components/CategoryFilter";
import { PostCard } from "./components/PostCard";
import { SearchBox } from "./components/SearchBox";
import { fetchPosts } from "./lib/api";
import type { Post } from "./lib/types";

export default function Home() {
  const [category, setCategory] = useState<string | null>(null);
  const [posts, setPosts] = useState<Post[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    fetchPosts(category)
      .then((data) => {
        if (!cancelled) setPosts(data);
      })
      .catch(() => {
        if (!cancelled) setError("피드를 불러오지 못했어요");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [category]);

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-1 flex-col bg-zinc-50">
      <header className="border-b border-zinc-200 bg-white px-4 py-3">
        <h1 className="text-lg font-bold text-zinc-900">🌴 제주메이트(가칭)</h1>
      </header>

      <SearchBox />

      <div className="border-b border-zinc-200 bg-white">
        <CategoryFilter selected={category} onSelect={setCategory} />
      </div>

      <main className="flex flex-1 flex-col gap-3 px-4 py-4">
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
