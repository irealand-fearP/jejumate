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

// 파티를 해산했으면 남은 관리 코드도 지운다(없는 모임을 계속 조회하지 않도록).
export function removeOwnerSecret(meetingId: string) {
  try {
    localStorage.removeItem(STORAGE_PREFIX + meetingId);
  } catch {
    // localStorage를 못 쓰는 환경이면 그냥 넘어간다.
  }
}

// admin 콘솔용: 이 기기에서 등록한(관리 코드를 저장해둔) 모든 모임을 나열한다.
export function listOwnedMeetings(): Array<{ meetingId: string; ownerSecret: string }> {
  try {
    const owned: Array<{ meetingId: string; ownerSecret: string }> = [];
    for (let i = 0; i < localStorage.length; i += 1) {
      const key = localStorage.key(i);
      if (!key || !key.startsWith(STORAGE_PREFIX)) continue;
      const ownerSecret = localStorage.getItem(key);
      if (!ownerSecret) continue;
      owned.push({ meetingId: key.slice(STORAGE_PREFIX.length), ownerSecret });
    }
    return owned;
  } catch {
    return [];
  }
}
