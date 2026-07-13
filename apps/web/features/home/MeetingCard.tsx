"use client";

import { CarFront, Coffee, Dumbbell, Laptop, MapPin, Soup, UsersRound } from "lucide-react";
import type { HomeMeeting } from "@/lib/api";
import { describeApplicationStatus } from "@/lib/applicationStatus";
import { formatCapacityStatus } from "@/lib/format";
import styles from "./HomeScreen.module.css";

const categoryIconMap = {
  meal: Soup,
  work: Laptop,
  move: CarFront,
  coffee: Coffee,
  run: Dumbbell,
};

const categoryClassMap: Record<string, string> = {
  meal: "categoryMeal",
  work: "categoryWork",
  move: "categoryMove",
  coffee: "categoryCoffee",
  run: "categoryRun",
};

function formatTime(value: string): string {
  return new Intl.DateTimeFormat("ko-KR", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone: "Asia/Seoul",
  }).format(new Date(value));
}

export function MeetingCard({
  meeting,
  index,
  onApply,
  applicationStatus,
  isOwned,
}: {
  meeting: HomeMeeting;
  index: number;
  onApply: (meeting: HomeMeeting) => void;
  /** 이 모임에 대한 내 신청 상태(pending/approved/rejected). 신청 안 했으면 undefined. */
  applicationStatus?: string;
  /** 이 기기에서 내가 만든 파티인지(owner_secret 보유). true면 신청 버튼을 안 보여준다
   * (2026-07-10 셀프 신청 버그 수정 — disabled가 아니라 아예 미표시). */
  isOwned?: boolean;
}) {
  const capacity = formatCapacityStatus(meeting.approved_count, meeting.capacity, meeting.status === "closed");
  const Icon = categoryIconMap[meeting.category as keyof typeof categoryIconMap] ?? UsersRound;
  const categoryClass = categoryClassMap[meeting.category] ?? "categoryDefault";
  const isExternal = meeting.source === "kakao_chat";
  const applyState = describeApplicationStatus(applicationStatus);

  return (
    <article className={styles.timelineItem}>
      <div className={styles.timeColumn}>
        <strong>{formatTime(meeting.starts_at)}</strong>
        <span>{isExternal ? "오픈채팅 작성" : `${index < 3 ? "☀" : "🌙"} ~ ${formatTime(meeting.ends_at)}`}</span>
      </div>
      <div className={styles.timelineRail}>
        <span />
      </div>
      <div className={`${styles.categoryBubble} ${styles[categoryClass]}`}>
        <Icon size={18} strokeWidth={2.2} />
      </div>
      <button className={styles.meetingBody} onClick={() => onApply(meeting)} type="button">
        {isExternal || meeting.is_popular || meeting.is_new ? (
          <span className={styles.meetingBadgeRow}>
            {isExternal ? <em className={styles.externalBadge}>오픈채팅에서 온 글</em> : null}
            {meeting.is_popular ? <em>인기</em> : null}
            {meeting.is_new && !isExternal ? <em>NEW</em> : null}
          </span>
        ) : null}
        <span className={styles.meetingTitleLine}>
          <strong>{meeting.title}</strong>
        </span>
        <small>
          <MapPin size={15} /> {meeting.place_label}
        </small>
        {isExternal ? null : (
          <small>
            👑 호스트 <b>{meeting.host.nickname}</b>
          </small>
        )}
      </button>
      <div className={styles.joinColumn}>
        {isExternal ? (
          <button onClick={() => onApply(meeting)} type="button">
            자세히
          </button>
        ) : (
          <>
            <b>
              {meeting.approved_count}/{meeting.capacity}
            </b>
            {isOwned ? (
              <span className={styles.applyStatusBadge}>내가 만든 파티</span>
            ) : (
              <>
                <span className={capacity.emphasize ? styles.capacityHot : undefined}>지금 합류 가능 ⚡</span>
                <button
                  className={applyState.disabled ? styles.applyStatusBadge : undefined}
                  disabled={applyState.disabled}
                  onClick={() => onApply(meeting)}
                  type="button"
                >
                  {applyState.label}
                </button>
              </>
            )}
          </>
        )}
      </div>
    </article>
  );
}
