"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getMyApplicationNotifications } from "@/lib/api";
import { getNotificationsSeenAt, markNotificationsSeenNow } from "@/lib/applicantNotifications";
import styles from "./ApplicantNotificationBanner.module.css";

const POLL_INTERVAL_MS = 10000;
const PROFILE_STORAGE_KEY = "jejumate.localProfile";

type LocalProfile = {
  profileId: string;
  nickname: string;
  anonymousId: string;
};

function readProfile(): LocalProfile | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(PROFILE_STORAGE_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as LocalProfile;
  } catch {
    return null;
  }
}

/**
 * 참가자용 알림 배너. HostPendingBanner(호스트용 — 새 신청 대기 알림)와 대칭이다.
 * 호스트가 승인/거절해도 참가자 쪽엔 자동으로 알려주는 폴링이 전혀 없어서, 사용자가
 * '내 신청 알림'을 직접 눌러보기 전엔 승인된 걸 몰랐던 버그가 있었다 — 이 배너가
 * 그 자동 폴링 역할을 한다. 10초마다 내 신청 알림을 조회해 마지막으로 확인한
 * 시각(기기 로컬 저장) 이후 승인/거절된 게 있으면 배너로 알린다.
 */
export function ApplicantNotificationBanner({ variant }: { variant: "overlay" | "inline" }) {
  const router = useRouter();
  const [newCount, setNewCount] = useState(0);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      const profile = readProfile();
      if (!profile?.anonymousId) {
        if (!cancelled) setNewCount(0);
        return;
      }
      try {
        const res = await getMyApplicationNotifications(profile.anonymousId);
        const seenAt = getNotificationsSeenAt();
        const seenAtMs = seenAt ? new Date(seenAt).getTime() : 0;
        const fresh = res.notifications.filter(
          (notification) =>
            (notification.status === "approved" || notification.status === "rejected") &&
            new Date(notification.updated_at).getTime() > seenAtMs
        );
        if (!cancelled) setNewCount(fresh.length);
      } catch {
        // 조회 실패는 조용히 넘어가고 다음 주기에 다시 시도한다.
      }
    }

    load();
    const timer = setInterval(load, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, []);

  if (newCount === 0) return null;

  return (
    <button
      className={`${styles.banner} ${variant === "overlay" ? styles.overlay : styles.inline}`}
      onClick={() => {
        markNotificationsSeenNow();
        setNewCount(0);
        router.push("/meetings?notifications=1");
      }}
      type="button"
    >
      🔔 신청 결과 {newCount}건 도착 — 확인해 주세요
    </button>
  );
}
