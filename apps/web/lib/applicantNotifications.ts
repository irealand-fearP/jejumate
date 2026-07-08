// 참가자가 마지막으로 '내 신청 알림'을 확인한 시각을 기기 로컬에 저장한다.
// 무로그인 서비스라 서버에 읽음 상태를 못 두므로, ownerSecret.ts와 동일하게
// localStorage 기반 기기별 상태로 관리한다. 이 시각 이후 승인/거절된 알림만
// "새 알림"으로 간주해 배너에 표시한다.
const SEEN_AT_KEY = "jejumate.applicantNotifications.seenAt";

export function getNotificationsSeenAt(): string | null {
  try {
    return localStorage.getItem(SEEN_AT_KEY);
  } catch {
    return null;
  }
}

export function markNotificationsSeenNow(): void {
  try {
    localStorage.setItem(SEEN_AT_KEY, new Date().toISOString());
  } catch {
    // localStorage를 못 쓰는 환경(프라이빗 모드 등)이면 그냥 넘어간다.
  }
}
