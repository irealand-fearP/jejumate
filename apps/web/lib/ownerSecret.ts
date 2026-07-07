// 호스트 관리 코드를 localStorage에 저장(같은 기기 재방문 시 자동 인식용).
// jejumate/frontend(app/lib/ownerSecret.ts)와 동일 패턴 — 다른 기기에서는 코드 직접
// 입력으로 대체 가능해야 하므로 이건 어디까지나 편의 기능이다.
const STORAGE_PREFIX = "jejumate.ownerSecret.";

export function saveOwnerSecret(meetingId: string, secret: string) {
  try {
    localStorage.setItem(STORAGE_PREFIX + meetingId, secret);
  } catch {
    // localStorage를 못 쓰는 환경(프라이빗 모드 등)이면 그냥 넘어간다.
  }
}

export function getOwnerSecret(meetingId: string): string | null {
  try {
    return localStorage.getItem(STORAGE_PREFIX + meetingId);
  } catch {
    return null;
  }
}
