"use client";

import { CarFront, Coffee, Dumbbell, Laptop, MapPin, Soup, UsersRound } from "lucide-react";
import type { HomeMeeting } from "@/lib/api";
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
}: {
  meeting: HomeMeeting;
  index: number;
  onApply: (meeting: HomeMeeting) => void;
}) {
  const capacity = formatCapacityStatus(meeting.approved_count, meeting.capacity, meeting.status === "closed");
  const Icon = categoryIconMap[meeting.category as keyof typeof categoryIconMap] ?? UsersRound;
  const categoryClass = categoryClassMap[meeting.category] ?? "categoryDefault";
  const isExternal = meeting.source === "kakao_chat";

  return (
    <article className={styles.timelineItem}>
      <div className={styles.timeColumn}>
        <strong>{formatTime(meeting.starts_at)}</strong>
        <span>
          {index < 3 ? "☀" : "🌙"} ~ {formatTime(meeting.ends_at)}
        </span>
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
            {meeting.is_new ? <em>NEW</em> : null}
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
            <span className={capacity.emphasize ? styles.capacityHot : undefined}>지금 합류 가능 ⚡</span>
            <button onClick={() => onApply(meeting)} type="button">
              신청
            </button>
          </>
        )}
      </div>
    </article>
  );
}
