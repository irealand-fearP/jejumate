import type { ApplicantNotification } from "./api";

/** meeting_id -> 내 신청 상태(pending/approved/rejected). 신청 안 한 모임은 키가 없다. */
export function buildApplicationStatusMap(notifications: ApplicantNotification[]): Map<string, string> {
  const map = new Map<string, string>();
  for (const notification of notifications) {
    map.set(notification.meeting_id, notification.status);
  }
  return map;
}

/** 신청 버튼에 표시할 라벨과, 다시 눌러도 의미가 없는 상태인지(중복 신청 방지)를 알려준다.
 * rejected도 disabled로 둔다 — 백엔드가 재신청 시 상태를 pending으로 되돌리지 않아서
 * (create_or_update_application은 message/profile만 갱신), 다시 시도해도 실제로는
 * 아무 효과가 없다. 잘못된 기대를 주지 않는 게 더 정직하다. */
export function describeApplicationStatus(status: string | undefined): {
  label: string;
  disabled: boolean;
} {
  switch (status) {
    case "pending":
      return { label: "대기중", disabled: true };
    case "approved":
      return { label: "확정", disabled: true };
    case "rejected":
      return { label: "거절됨", disabled: true };
    default:
      return { label: "신청", disabled: false };
  }
}
