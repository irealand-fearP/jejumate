"use client";

import { useState } from "react";
import { createPartyPost } from "../lib/api";
import { CATEGORIES } from "../lib/categories";
import { saveOwnerSecret } from "../lib/ownerSecret";

const PARTY_CATEGORIES = CATEGORIES.filter((c) => c.group === "party");
const DEADLINE_OPTIONS = [
  { label: "30분", minutes: 30 },
  { label: "1시간", minutes: 60 },
  { label: "2시간", minutes: 120 },
];

interface Props {
  onClose: () => void;
  onCreated: () => void;
}

export function PartyRegisterModal({ onClose, onCreated }: Props) {
  const [category, setCategory] = useState(PARTY_CATEGORIES[0].value);
  const [content, setContent] = useState("");
  const [capacity, setCapacity] = useState(2);
  const [deadlineMinutes, setDeadlineMinutes] = useState(30);
  const [customMinutes, setCustomMinutes] = useState("");
  const [nickname, setNickname] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<{ id: string; ownerSecret: string } | null>(null);
  const [copied, setCopied] = useState(false);

  const effectiveDeadline = deadlineMinutes === -1 ? Number(customMinutes) : deadlineMinutes;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!content.trim() || !nickname.trim() || !effectiveDeadline || effectiveDeadline <= 0) {
      setError("내용, 닉네임, 마감시간을 모두 입력해주세요");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const res = await createPartyPost({
        category,
        content,
        capacity,
        deadline_minutes: effectiveDeadline,
        nickname,
      });
      saveOwnerSecret(res.id, res.owner_secret);
      setResult({ id: res.id, ownerSecret: res.owner_secret });
      onCreated();
    } catch {
      setError("등록에 실패했어요. 잠시 후 다시 시도해주세요.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4">
      <div className="w-full max-w-md rounded-2xl bg-white p-5 shadow-lg">
        {result ? (
          <div className="text-center">
            <p className="text-sm text-zinc-600">파티 등록 완료!</p>
            <p className="mt-3 text-2xl font-bold tracking-widest text-orange-600">
              관리 코드: {result.ownerSecret}
            </p>
            <p className="mt-1 text-xs text-zinc-400">
              나중에 신청 승인/마감할 때 필요해요. 이 기기엔 자동 저장했어요.
            </p>
            <button
              onClick={() => {
                navigator.clipboard?.writeText(result.ownerSecret);
                setCopied(true);
              }}
              className="mt-3 rounded-lg border border-zinc-300 px-3 py-1.5 text-sm"
            >
              {copied ? "복사됨" : "코드 복사"}
            </button>
            <button
              onClick={onClose}
              className="mt-4 block w-full rounded-lg bg-zinc-800 py-2 text-sm font-medium text-white"
            >
              확인
            </button>
          </div>
        ) : (
          <form onSubmit={handleSubmit}>
            <h2 className="text-base font-semibold text-zinc-900">🎉 파티 모집 등록</h2>

            <div className="mt-3 flex flex-wrap gap-2">
              {PARTY_CATEGORIES.map((c) => (
                <button
                  key={c.value}
                  type="button"
                  onClick={() => setCategory(c.value)}
                  className={`rounded-full border px-3 py-1 text-sm ${
                    category === c.value
                      ? "border-orange-500 bg-orange-500 text-white"
                      : "border-orange-200 bg-orange-50 text-orange-700"
                  }`}
                >
                  {c.icon} {c.label}
                </button>
              ))}
            </div>

            <textarea
              value={content}
              onChange={(e) => setContent(e.target.value)}
              placeholder="내용(장소·시간 등)"
              rows={3}
              className="mt-3 w-full rounded-lg border border-zinc-300 p-2 text-sm"
            />

            <div className="mt-3 flex gap-3">
              <label className="flex-1 text-xs text-zinc-500">
                정원
                <input
                  type="number"
                  min={1}
                  value={capacity}
                  onChange={(e) => setCapacity(Number(e.target.value))}
                  className="mt-1 w-full rounded-lg border border-zinc-300 p-2 text-sm"
                />
              </label>
              <label className="flex-1 text-xs text-zinc-500">
                닉네임
                <input
                  value={nickname}
                  onChange={(e) => setNickname(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-zinc-300 p-2 text-sm"
                />
              </label>
            </div>

            <div className="mt-3">
              <span className="text-xs text-zinc-500">마감시간</span>
              <div className="mt-1 flex flex-wrap gap-2">
                {DEADLINE_OPTIONS.map((opt) => (
                  <button
                    key={opt.minutes}
                    type="button"
                    onClick={() => setDeadlineMinutes(opt.minutes)}
                    className={`rounded-full border px-3 py-1 text-sm ${
                      deadlineMinutes === opt.minutes
                        ? "border-zinc-800 bg-zinc-800 text-white"
                        : "border-zinc-300 text-zinc-600"
                    }`}
                  >
                    {opt.label}
                  </button>
                ))}
                <button
                  type="button"
                  onClick={() => setDeadlineMinutes(-1)}
                  className={`rounded-full border px-3 py-1 text-sm ${
                    deadlineMinutes === -1
                      ? "border-zinc-800 bg-zinc-800 text-white"
                      : "border-zinc-300 text-zinc-600"
                  }`}
                >
                  직접입력
                </button>
                {deadlineMinutes === -1 && (
                  <input
                    type="number"
                    min={1}
                    placeholder="분"
                    value={customMinutes}
                    onChange={(e) => setCustomMinutes(e.target.value)}
                    className="w-20 rounded-lg border border-zinc-300 p-1 text-sm"
                  />
                )}
              </div>
            </div>

            {error && <p className="mt-2 text-xs text-red-500">{error}</p>}

            <div className="mt-4 flex gap-2">
              <button
                type="button"
                onClick={onClose}
                className="flex-1 rounded-lg border border-zinc-300 py-2 text-sm"
              >
                취소
              </button>
              <button
                type="submit"
                disabled={submitting}
                className="flex-1 rounded-lg bg-orange-500 py-2 text-sm font-medium text-white disabled:opacity-50"
              >
                {submitting ? "등록 중..." : "등록하기"}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
