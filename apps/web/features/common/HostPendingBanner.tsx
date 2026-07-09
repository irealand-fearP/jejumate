"use client";

import { useCallback, useEffect, useState } from "react";
import { getMeetingApplications } from "@/lib/api";
import { listOwnedMeetings } from "@/lib/ownerSecret";
import { HostApprovalSheet } from "./HostApprovalSheet";
import styles from "./HostPendingBanner.module.css";

const POLL_INTERVAL_MS = 10000;

/**
 * 호스트용 알림 배너. 무로그인 서비스라 "내가 만든 모임"은 웹 localStorage에 저장된
 * 관리 코드(owner_secret)로만 알 수 있다(listOwnedMeetings) — 기존 승인/거절 API인
 * GET /meetings/{id}/applications?owner_secret=를 그대로 재활용해 대기(pending) 신청
 * 수를 세고, 있으면 배너로 알린다. 누르면 페이지 이동 없이 승인 시트를 연다.
 */
export function HostPendingBanner({ variant }: { variant: "overlay" | "inline" }) {
  const [pendingCount, setPendingCount] = useState(0);
  const [sheetOpen, setSheetOpen] = useState(false);

  const loadPendingCount = useCallback(async () => {
    const owned = listOwnedMeetings();
    if (owned.length === 0) {
      setPendingCount(0);
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
    setPendingCount(total);
  }, []);

  useEffect(() => {
    let cancelled = false;
    const run = () => {
      if (!cancelled) loadPendingCount();
    };
    run();
    const timer = setInterval(run, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [loadPendingCount]);

  // 시트는 배너와 별도로 렌더링한다 — 마지막 신청을 처리해 대기 건수가 0이 되어도
  // 시트가 갑자기 사라지지 않고 "모든 신청을 처리했어요"를 보여준 뒤 사용자가 닫는다.
  return (
    <>
      {pendingCount > 0 ? (
        <button
          className={`${styles.banner} ${variant === "overlay" ? styles.overlay : styles.inline}`}
          onClick={() => setSheetOpen(true)}
          type="button"
        >
          🔔 새 신청 {pendingCount}건 — 승인해 주세요
        </button>
      ) : null}

      {sheetOpen ? (
        <HostApprovalSheet onChanged={loadPendingCount} onClose={() => setSheetOpen(false)} />
      ) : null}
    </>
  );
}
