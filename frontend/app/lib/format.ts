export function formatRelativeTime(iso: string): string {
  const date = new Date(iso);
  const now = new Date();
  const time = date.toLocaleTimeString("ko-KR", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });

  const isSameDay = date.toDateString() === now.toDateString();
  if (isSameDay) return `오늘 ${time}`;

  const yesterday = new Date(now);
  yesterday.setDate(now.getDate() - 1);
  if (date.toDateString() === yesterday.toDateString()) return `어제 ${time}`;

  return `${date.getMonth() + 1}/${date.getDate()} ${time}`;
}

export function formatMinutesUntil(deadlineIso: string): string {
  const diffMs = new Date(deadlineIso).getTime() - Date.now();
  const minutes = Math.round(diffMs / 60000);
  if (minutes <= 0) return "마감";
  if (minutes < 60) return `마감까지 ${minutes}분`;
  return `마감까지 ${Math.round(minutes / 60)}시간`;
}

// 코덱스 제안 반영 결정 ②: "2/4명" 표기 + 잔여 1명일 때 "1명 남음" 강조.
export function formatCapacityStatus(
  approvedCount: number,
  capacity: number | null,
  isClosed: boolean
): { text: string; emphasize: boolean } {
  if (isClosed) return { text: "마감", emphasize: false };
  if (capacity == null) return { text: `${approvedCount}명 참여`, emphasize: false };

  const remaining = capacity - approvedCount;
  if (remaining <= 0) return { text: `${approvedCount}/${capacity}명 · 모집완료`, emphasize: false };
  if (remaining === 1) return { text: `${approvedCount}/${capacity}명 · 1명 남음`, emphasize: true };
  return { text: `${approvedCount}/${capacity}명`, emphasize: false };
}
