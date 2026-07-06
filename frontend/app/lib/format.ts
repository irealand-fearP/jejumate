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
