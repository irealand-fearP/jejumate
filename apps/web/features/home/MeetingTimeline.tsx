"use client";

import { useRouter } from "next/navigation";
import { ChevronRight } from "lucide-react";
import type { HomeMeeting } from "@/lib/api";
import { MeetingCard } from "./MeetingCard";
import styles from "./HomeScreen.module.css";

export function MeetingTimeline({
  meetings,
  filters,
  openCount,
  onApply,
}: {
  meetings: HomeMeeting[];
  filters: string[];
  openCount: number;
  onApply: (meeting: HomeMeeting) => void;
}) {
  const router = useRouter();

  return (
    <section className={styles.meetingsSection}>
      <div className={styles.sectionTitleRow}>
        <h2>
          오늘 열려 있는 모임 <span>{openCount}개</span>
        </h2>
        <button onClick={() => router.push("/meetings")} type="button">
          전체 보기 <ChevronRight size={18} />
        </button>
      </div>

      <div className={styles.filterRow}>
        {filters.map((filter) => (
          <button
            className={filter === "전체" ? styles.filterActive : styles.filterChip}
            key={filter}
            onClick={() => router.push("/meetings")}
            type="button"
          >
            {filter}
          </button>
        ))}
      </div>

      <div className={styles.timelineList}>
        {meetings.slice(0, 4).map((meeting, index) => (
          <MeetingCard key={meeting.id} meeting={meeting} index={index} onApply={onApply} />
        ))}
      </div>
    </section>
  );
}
