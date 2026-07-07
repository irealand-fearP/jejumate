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
        <Icon size={28} strokeWidth={2.2} />
      </div>
      <button className={styles.meetingBody} onClick={() => onApply(meeting)} type="button">
        <span className={styles.meetingTitleLine}>
          <strong>{meeting.title}</strong>
          {index === 0 ? <em>인기</em> : null}
          {meeting.category === "run" ? <em>NEW</em> : null}
        </span>
        <small>
          <MapPin size={15} /> {meeting.place_label}
        </small>
        <small>
          👑 호스트 <b>{meeting.host.nickname}</b>
        </small>
      </button>
      <div className={styles.joinColumn}>
        <b>
          {meeting.approved_count}/{meeting.capacity}
        </b>
        <span className={capacity.emphasize ? styles.capacityHot : undefined}>지금 합류 가능 ⚡</span>
        <button onClick={() => onApply(meeting)} type="button">
          신청
        </button>
      </div>
    </article>
  );
}
