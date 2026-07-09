"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { ChevronRight, Radio } from "lucide-react";
import type { HomeMeeting } from "@/lib/api";
import { FILTER_TO_CATEGORIES } from "@/lib/meetingCategories";
import { MeetingCard } from "./MeetingCard";
import styles from "./HomeScreen.module.css";

// 필터별 이동 링크. '전체'/'오픈채팅'은 category가 아니라 각각 무필터/source로
// 구분되는 별도 축이라 FILTER_TO_CATEGORIES에 없다.
function filterHref(filter: string): string {
  if (filter === "전체") return "/meetings";
  if (filter === "오픈채팅") return "/meetings?source=kakao_chat";
  const categories = FILTER_TO_CATEGORIES[filter];
  return categories?.length ? `/meetings?category=${categories[0]}` : "/meetings";
}

export function MeetingTimeline({
  meetings,
  filters,
  openCount,
  onApply,
  applicationStatusByMeetingId,
  ownedMeetingIds,
}: {
  meetings: HomeMeeting[];
  filters: string[];
  openCount: number;
  onApply: (meeting: HomeMeeting) => void;
  /** meeting_id -> 내 신청 상태. 프로필이 없거나 조회 전이면 빈 맵. */
  applicationStatusByMeetingId?: Map<string, string>;
  /** 이 기기에서 내가 만든(owner_secret을 가진) 모임 id 집합. */
  ownedMeetingIds?: Set<string>;
}) {
  const quickMatches = useMemo(
    () => meetings.filter((meeting) => meeting.category === "quick" && meeting.source === "service"),
    [meetings],
  );
  const regularMeetings = useMemo(() => meetings.filter((meeting) => meeting.category !== "quick"), [meetings]);
  const [quickMatchIndex, setQuickMatchIndex] = useState(0);

  useEffect(() => {
    if (quickMatches.length < 2) return;
    const timer = window.setInterval(() => {
      setQuickMatchIndex((current) => (current + 1) % quickMatches.length);
    }, 5000);
    return () => window.clearInterval(timer);
  }, [quickMatches.length]);

  useEffect(() => {
    setQuickMatchIndex((current) => Math.min(current, Math.max(quickMatches.length - 1, 0)));
  }, [quickMatches.length]);

  const quickMatch = quickMatches[quickMatchIndex];

  return (
    <section className={styles.meetingsSection}>
      <div className={styles.sectionTitleRow}>
        <h2>
          오늘 열려 있는 파티 <span>{openCount}개</span>
        </h2>
        <Link href="/meetings">
          전체 보기 <ChevronRight size={18} />
        </Link>
      </div>

      <div className={styles.filterRow}>
        {filters.map((filter) => (
          <Link
            className={filter === "전체" ? styles.filterActive : styles.filterChip}
            href={filterHref(filter)}
            key={filter}
          >
            {filter}
          </Link>
        ))}
      </div>

      {quickMatch ? (
        <button className={styles.quickMatchTicker} onClick={() => onApply(quickMatch)} type="button">
          <span className={styles.quickMatchLabel}>
            <Radio size={14} /> 퀵매치
          </span>
          <span className={styles.quickMatchContent}>
            <strong>{quickMatch.title}</strong>
            <small>{quickMatch.place_label} · {quickMatch.approved_count}/{quickMatch.capacity}명</small>
          </span>
          <ChevronRight className={styles.quickMatchArrow} size={18} />
          {quickMatches.length > 1 ? (
            <span className={styles.quickMatchDots} aria-label={`퀵매치 ${quickMatchIndex + 1} / ${quickMatches.length}`}>
              {quickMatches.map((match, index) => <i className={index === quickMatchIndex ? styles.quickMatchDotActive : undefined} key={match.id} />)}
            </span>
          ) : null}
        </button>
      ) : (
        <div className={styles.quickMatchEmpty}>
          <span className={styles.quickMatchLabel}>
            <Radio size={14} /> 퀵매치
          </span>
          <span>
            <strong>현재 매칭 중인 퀵매치가 없어요</strong>
            <small>새로운 퀵매치가 등록되면 이곳에서 바로 확인할 수 있어요.</small>
          </span>
        </div>
      )}

      <div className={styles.timelineList}>
        {/* 백엔드가 이미 홈 미리보기 6개를 확정해서 내려준다(_home_meeting_rows,
            콜드스타트 콘텐츠 2자리 예약 포함) — 여기서 다시 4개로 자르면 뒤쪽에
            정렬되는 콜드스타트 항목이 화면에서 통째로 잘려나간다. */}
        {regularMeetings.map((meeting, index) => (
          <MeetingCard
            applicationStatus={applicationStatusByMeetingId?.get(meeting.id)}
            isOwned={ownedMeetingIds?.has(meeting.id) ?? false}
            key={meeting.id}
            meeting={meeting}
            index={index}
            onApply={onApply}
          />
        ))}
      </div>
    </section>
  );
}
