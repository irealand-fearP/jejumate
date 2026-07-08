"use client";

import Link from "next/link";
import { ChevronRight } from "lucide-react";
import type { HomeMeeting } from "@/lib/api";
import { FILTER_TO_CATEGORY } from "@/lib/meetingCategories";
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
  return (
    <section className={styles.meetingsSection}>
      <div className={styles.sectionTitleRow}>
        <h2>
          오늘 열려 있는 모임 <span>{openCount}개</span>
        </h2>
        <Link href="/meetings">
          전체 보기 <ChevronRight size={18} />
        </Link>
      </div>

      <div className={styles.filterRow}>
        {filters.map((filter) => {
          const category = FILTER_TO_CATEGORY[filter];
          const href = category ? `/meetings?category=${category}` : "/meetings";
          return (
            <Link
              className={filter === "전체" ? styles.filterActive : styles.filterChip}
              href={href}
              key={filter}
            >
              {filter}
            </Link>
          );
        })}
      </div>

      <div className={styles.timelineList}>
        {/* 백엔드가 이미 홈 미리보기 6개를 확정해서 내려준다(_home_meeting_rows,
            콜드스타트 콘텐츠 2자리 예약 포함) — 여기서 다시 4개로 자르면 뒤쪽에
            정렬되는 콜드스타트 항목이 화면에서 통째로 잘려나간다. */}
        {meetings.map((meeting, index) => (
          <MeetingCard key={meeting.id} meeting={meeting} index={index} onApply={onApply} />
        ))}
      </div>
    </section>
  );
}
