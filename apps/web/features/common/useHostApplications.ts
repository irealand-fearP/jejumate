"use client";

import { useCallback, useEffect, useState } from "react";
import {
  approveMeetingApplication,
  getMeetingApplications,
  getMeetingsData,
  rejectMeetingApplication,
  type MeetingApplicationItem,
} from "@/lib/api";
import { listOwnedMeetings } from "@/lib/ownerSecret";

/** 한 모임에 들어온 신청들. 여러 모임에 대기 신청이 있을 수 있어 모임별로 묶는다. */
export type HostMeetingGroup = {
  meetingId: string;
  ownerSecret: string;
  meetingTitle: string;
  applications: MeetingApplicationItem[];
};

export type HostApplicationsState = {
  groups: HostMeetingGroup[];
  /** 이 기기에 관리 코드가 저장된 모임 수(0이면 "만든 파티가 없다"는 뜻). */
  ownedCount: number;
  loading: boolean;
  error: string | null;
  /** 처리 중인 신청 id(버튼 중복 클릭 방지). */
  busyApplicationId: string | null;
  decide: (group: HostMeetingGroup, applicationId: string, action: "approve" | "reject") => Promise<void>;
  reload: () => Promise<void>;
};

function countPending(groups: HostMeetingGroup[]): number {
  return groups.reduce(
    (total, group) => total + group.applications.filter((a) => a.status === "pending").length,
    0,
  );
}

/** 대기 신청 수만 필요할 때(배너 등) 쓰는 헬퍼. */
export function countPendingApplications(groups: HostMeetingGroup[]): number {
  return countPending(groups);
}

/**
 * 무로그인 서비스라 "내가 만든 모임"은 localStorage의 관리 코드(owner_secret)로만 알 수 있다.
 * 그 코드로 신청 목록을 모아 모임별로 묶고, 승인/거절까지 처리한다.
 * admin 페이지와 호스트 승인 시트가 이 훅을 함께 쓴다 — 한 곳만 고치면 양쪽에 반영된다.
 */
export function useHostApplications(onChanged?: () => void): HostApplicationsState {
  const [groups, setGroups] = useState<HostMeetingGroup[]>([]);
  const [ownedCount, setOwnedCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyApplicationId, setBusyApplicationId] = useState<string | null>(null);

  const reload = useCallback(async () => {
    const owned = listOwnedMeetings();
    setOwnedCount(owned.length);
    if (owned.length === 0) {
      setGroups([]);
      setLoading(false);
      return;
    }

    // 모임 제목은 목록 API에서 가져온다(실패해도 id 앞자리로 대체 표시).
    const meetingsData = await getMeetingsData().catch(() => null);
    const titleById = new Map(meetingsData?.meetings.map((meeting) => [meeting.id, meeting.title]) ?? []);

    const nextGroups: HostMeetingGroup[] = [];
    for (const { meetingId, ownerSecret } of owned) {
      try {
        const res = await getMeetingApplications(meetingId, ownerSecret);
        if (!res.authorized || res.applications.length === 0) continue;
        nextGroups.push({
          meetingId,
          ownerSecret,
          meetingTitle: titleById.get(meetingId) ?? `파티 ${meetingId.slice(0, 8)}`,
          // 대기 중인 신청을 위로 올린다.
          applications: [...res.applications].sort(
            (a, b) => Number(a.status !== "pending") - Number(b.status !== "pending"),
          ),
        });
      } catch {
        // 이 기기에 저장된 관리 코드가 더는 유효하지 않을 수 있음 — 조용히 건너뜀
      }
    }

    // 대기 신청이 있는 모임을 먼저 보여준다.
    nextGroups.sort((a, b) => countPending([b]) - countPending([a]));
    setGroups(nextGroups);
    setLoading(false);
  }, []);

  useEffect(() => {
    reload().catch(() => {
      setError("신청 목록을 불러오지 못했습니다.");
      setLoading(false);
    });
  }, [reload]);

  async function decide(group: HostMeetingGroup, applicationId: string, action: "approve" | "reject") {
    setBusyApplicationId(applicationId);
    setError(null);
    try {
      // 기존 API 규약 그대로: owner_secret으로 본인 확인, 403/409/400은 메시지로 표시된다.
      const call = action === "approve" ? approveMeetingApplication : rejectMeetingApplication;
      await call(group.meetingId, applicationId, group.ownerSecret);
      await reload();
      onChanged?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "처리를 완료하지 못했습니다.");
    } finally {
      setBusyApplicationId(null);
    }
  }

  return { groups, ownedCount, loading, error, busyApplicationId, decide, reload };
}
