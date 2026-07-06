"use client";

import { useEffect, useState } from "react";
import {
  applyToPost,
  approveApplication,
  fetchApplications,
  fetchPostStatus,
  rejectApplication,
} from "../lib/api";
import { formatCapacityStatus, formatMinutesUntil } from "../lib/format";
import { getOwnerSecret } from "../lib/ownerSecret";
import type { ApplicationItem, PostStatus } from "../lib/types";

const POLL_INTERVAL_MS = 8000;

export function PartyAccordion({ postId, deadline }: { postId: string; deadline: string | null }) {
  const [status, setStatus] = useState<PostStatus | null>(null);

  const [nickname, setNickname] = useState("");
  const [message, setMessage] = useState("");
  const [applySubmitting, setApplySubmitting] = useState(false);
  const [applyError, setApplyError] = useState<string | null>(null);
  const [applied, setApplied] = useState(false);

  const [ownerCode, setOwnerCode] = useState("");
  const [applications, setApplications] = useState<ApplicationItem[] | null>(null);
  const [authorized, setAuthorized] = useState(false);
  const [codeChecked, setCodeChecked] = useState(false);

  useEffect(() => {
    setOwnerCode(getOwnerSecret(postId) ?? "");
  }, [postId]);

  useEffect(() => {
    let cancelled = false;
    function load() {
      fetchPostStatus(postId).then((data) => {
        if (!cancelled) setStatus(data);
      });
    }
    load();
    const timer = setInterval(load, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [postId]);

  async function refreshApplications(code: string) {
    const res = await fetchApplications(postId, code || undefined);
    setApplications(res.applications);
    setAuthorized(res.authorized);
    setCodeChecked(true);
  }

  async function handleApply(e: React.FormEvent) {
    e.preventDefault();
    if (!nickname.trim()) {
      setApplyError("닉네임을 입력해주세요");
      return;
    }
    setApplySubmitting(true);
    setApplyError(null);
    try {
      await applyToPost(postId, { nickname, message: message || undefined });
      setApplied(true);
    } catch (err) {
      setApplyError(err instanceof Error ? err.message : "신청에 실패했어요");
    } finally {
      setApplySubmitting(false);
    }
  }

  async function handleReview(applicationId: string, action: "approve" | "reject") {
    const fn = action === "approve" ? approveApplication : rejectApplication;
    try {
      await fn(postId, applicationId, ownerCode);
      await refreshApplications(ownerCode);
      fetchPostStatus(postId).then(setStatus);
    } catch {
      // 정원 초과·이미 처리됨 등은 목록 새로고침으로 자연스럽게 드러난다.
      await refreshApplications(ownerCode);
    }
  }

  const capacityInfo = status
    ? formatCapacityStatus(status.approved_count, status.capacity, status.is_closed)
    : null;

  return (
    <div className="mt-3 border-t border-zinc-100 pt-3 text-sm">
      {capacityInfo && (
        <p className={capacityInfo.emphasize ? "font-bold text-orange-600" : "text-zinc-600"}>
          모집 정보: {capacityInfo.text}
          {deadline && ` · ${formatMinutesUntil(deadline)}`}
        </p>
      )}

      {!applied ? (
        <form onSubmit={handleApply} className="mt-2 flex flex-col gap-2">
          <p className="text-xs text-zinc-400">호스트가 승인해야 약속이 확정돼요</p>
          <div className="flex gap-2">
            <input
              value={nickname}
              onChange={(e) => setNickname(e.target.value)}
              placeholder="닉네임"
              className="w-24 rounded-lg border border-zinc-300 p-1.5 text-xs"
            />
            <input
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              placeholder="메시지(선택)"
              className="flex-1 rounded-lg border border-zinc-300 p-1.5 text-xs"
            />
            <button
              type="submit"
              disabled={applySubmitting}
              className="rounded-lg bg-orange-500 px-3 py-1.5 text-xs font-medium text-white disabled:opacity-50"
            >
              같이 갈래요
            </button>
          </div>
          {applyError && <p className="text-xs text-red-500">{applyError}</p>}
        </form>
      ) : (
        <p className="mt-2 text-xs text-emerald-600">
          신청했어요! 호스트가 승인해야 약속이 확정돼요.
        </p>
      )}

      <div className="mt-3 border-t border-zinc-100 pt-3">
        <p className="text-xs font-medium text-zinc-500">내 글 관리 (글쓴이만)</p>
        <div className="mt-1 flex gap-2">
          <input
            value={ownerCode}
            onChange={(e) => setOwnerCode(e.target.value)}
            placeholder="관리 코드"
            className="w-24 rounded-lg border border-zinc-300 p-1.5 text-xs"
          />
          <button
            onClick={() => refreshApplications(ownerCode)}
            className="rounded-lg border border-zinc-300 px-3 py-1.5 text-xs"
          >
            확인
          </button>
        </div>

        {codeChecked && !authorized && (
          <p className="mt-1 text-xs text-red-500">코드가 맞지 않아요</p>
        )}

        {applications && applications.length > 0 && (
          <ul className="mt-2 flex flex-col gap-1.5">
            {applications.map((a, i) => (
              <li
                key={a.id ?? i}
                className="flex items-center justify-between rounded-lg bg-zinc-50 px-2 py-1.5 text-xs"
              >
                <span>
                  {a.nickname}
                  {authorized && a.message && <span className="text-zinc-400"> · {a.message}</span>}
                </span>
                {authorized && a.id && a.status === "pending" && (
                  <span className="flex gap-1">
                    <button
                      onClick={() => handleReview(a.id!, "approve")}
                      className="rounded-full bg-orange-500 px-2 py-0.5 text-white"
                    >
                      같이 가기로 하기
                    </button>
                    <button
                      onClick={() => handleReview(a.id!, "reject")}
                      className="rounded-full border border-zinc-300 px-2 py-0.5"
                    >
                      거절
                    </button>
                  </span>
                )}
                {authorized && a.status === "approved" && (
                  <span className="text-emerald-600">확정됨</span>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
