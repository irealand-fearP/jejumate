"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getMeetingApplications } from "@/lib/api";
import { listOwnedMeetings } from "@/lib/ownerSecret";
import styles from "./HostPendingBanner.module.css";

const POLL_INTERVAL_MS = 10000;

/**
 * 호스트용 알림 배너. 무로그인 서비스라 "내가 만든 모임"은 웹 localStorage에 저장된
 * 관리 코드(owner_secret)로만 알 수 있다(listOwnedMeetings) — 기존 승인/거절 API인
 * GET /meetings/{id}/applications?owner_secret=를 그대로 재활용해 대기(pending) 신청
 * 수를 세고, 있으면 배너로 알린다. 누르면 admin 콘솔(내가 만든 모임의 신청함)로 이동.
 */
export function HostPendingBanner({ variant }: { variant: "overlay" | "inline" }) {
  const router = useRouter();
  const [pendingCount, setPendingCount] = useState(0);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      const owned = listOwnedMeetings();
      if (owned.length === 0) {
        if (!cancelled) setPendingCount(0);
        return;
      }
      let total = 0;
      for (const { meetingId, ownerSecret } of owned) {
        try {
          const res = await getMeetingApplications(meetingId, ownerSecret);
          if (res.authorized) {
            total += res.applications.filter((application) => application.status === "pending").length;
          }
        } catch {
          // 이 기기에 저장된 관리 코드가 더는 유효하지 않을 수 있음 — 조용히 건너뜀
        }
      }
      if (!cancelled) setPendingCount(total);
    }

    load();
    const timer = setInterval(load, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, []);

  if (pendingCount === 0) return null;

  return (
    <button
      className={`${styles.banner} ${variant === "overlay" ? styles.overlay : styles.inline}`}
      onClick={() => router.push("/admin")}
      type="button"
    >
      🔔 새 신청 {pendingCount}건 — 승인해 주세요
    </button>
  );
}
