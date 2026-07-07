// jejumate/frontend(app/lib/format.ts)의 formatCapacityStatus를 그대로 이식.
// "n/정원명" 표기 + 잔여 1명일 때 "1명 남음" 강조.
export function formatCapacityStatus(
  approvedCount: number,
  capacity: number,
  isClosed: boolean
): { text: string; emphasize: boolean } {
  if (isClosed) return { text: "마감", emphasize: false };

  const remaining = capacity - approvedCount;
  if (remaining <= 0) return { text: `${approvedCount}/${capacity}명 · 모집완료`, emphasize: false };
  if (remaining === 1) return { text: `${approvedCount}/${capacity}명 · 1명 남음`, emphasize: true };
  return { text: `${approvedCount}/${capacity}명`, emphasize: false };
}
