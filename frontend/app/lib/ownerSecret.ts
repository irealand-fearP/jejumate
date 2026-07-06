// 글쓴이 관리 코드를 localStorage에 저장(같은 기기 재방문 시 자동 인식용).
// 다른 기기에서는 코드 직접 입력으로 대체 가능해야 하므로(화면흐름.md 5-5),
// 이건 어디까지나 편의 기능이다.
const STORAGE_PREFIX = "jejumate:owner_secret:";

export function saveOwnerSecret(postId: string, secret: string) {
  try {
    localStorage.setItem(STORAGE_PREFIX + postId, secret);
  } catch {
    // localStorage를 못 쓰는 환경(프라이빗 모드 등)이면 그냥 넘어간다.
  }
}

export function getOwnerSecret(postId: string): string | null {
  try {
    return localStorage.getItem(STORAGE_PREFIX + postId);
  } catch {
    return null;
  }
}
