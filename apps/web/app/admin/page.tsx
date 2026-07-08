"use client";

import { useEffect, useState } from "react";
import {
  approveMeetingApplication,
  getMeetingApplications,
  getMeetingsData,
  rejectMeetingApplication,
  type MeetingApplicationItem,
} from "@/lib/api";
import { listOwnedMeetings } from "@/lib/ownerSecret";
import styles from "./admin.module.css";

// 코덱스 원본 admin 페이지(전역 조회, 인증 없음)를 참고했지만, 우리 API 규약대로
// 이 기기에 저장된 관리 코드(owner_secret)를 가진 모임만 조회/승인/거절한다
// (jejumate/backend와 동일하게 로그인 없는 관리 코드 인증 유지).

type Row = {
  meetingId: string;
  ownerSecret: string;
  meetingTitle: string;
  application: MeetingApplicationItem;
};

const statusLabel: Record<string, string> = {
  pending: "대기",
  approved: "승인",
  rejected: "거절",
};

export default function AdminPage() {
  const [rows, setRows] = useState<Row[]>([]);
  const [ownedCount, setOwnedCount] = useState(0);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [filter, setFilter] = useState<"pending" | "all">("pending");
  const [message, setMessage] = useState("");
  const [loaded, setLoaded] = useState(false);

  async function load() {
    const owned = listOwnedMeetings();
    setOwnedCount(owned.length);
    if (owned.length === 0) {
      setRows([]);
      setLoaded(true);
      return;
    }

    const meetingsData = await getMeetingsData().catch(() => null);
    const titleById = new Map(meetingsData?.meetings.map((meeting) => [meeting.id, meeting.title]) ?? []);

    const nextRows: Row[] = [];
    for (const { meetingId, ownerSecret } of owned) {
      try {
        const res = await getMeetingApplications(meetingId, ownerSecret);
        if (!res.authorized) continue;
        for (const application of res.applications) {
          nextRows.push({
            meetingId,
            ownerSecret,
            meetingTitle: titleById.get(meetingId) ?? `파티 ${meetingId.slice(0, 8)}`,
            application,
          });
        }
      } catch {
        // 이 기기에 저장된 관리 코드가 더는 유효하지 않을 수 있음 — 조용히 건너뜀
      }
    }
    nextRows.sort((a, b) => Number(a.application.status !== "pending") - Number(b.application.status !== "pending"));
    setRows(nextRows);
    setLoaded(true);
  }

  useEffect(() => {
    load().catch(() => setMessage("신청 목록을 불러오지 못했습니다."));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const visibleRows = filter === "pending" ? rows.filter((row) => row.application.status === "pending") : rows;

  async function decide(row: Row, action: "approve" | "reject") {
    if (!row.application.application_id) return;
    setBusyId(row.application.application_id);
    setMessage("");
    try {
      const decide = action === "approve" ? approveMeetingApplication : rejectMeetingApplication;
      await decide(row.meetingId, row.application.application_id, row.ownerSecret);
      await load();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "처리를 완료하지 못했습니다.");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <main className={styles.page}>
      <header className={styles.header}>
        <div>
          <p className={styles.eyebrow}>Host Console</p>
          <h1 className={styles.title}>파티 신청함</h1>
        </div>
        <div className={styles.segment}>
          <button
            className={filter === "pending" ? styles.segmentActive : styles.segmentButton}
            onClick={() => setFilter("pending")}
            type="button"
          >
            대기
          </button>
          <button
            className={filter === "all" ? styles.segmentActive : styles.segmentButton}
            onClick={() => setFilter("all")}
            type="button"
          >
            전체
          </button>
        </div>
      </header>

      {message ? <div className={styles.notice}>{message}</div> : null}
      {!message && loaded && ownedCount === 0 ? (
        <div className={styles.notice}>
          이 기기에서 등록한 파티가 없어요. 파티 화면에서 &quot;+ 파티 만들기&quot;로 등록하면 여기서 관리할 수 있어요.
        </div>
      ) : null}

      <section className={styles.list}>
        {visibleRows.length ? (
          visibleRows.map((row) => (
            <article
              className={styles.item}
              key={row.application.application_id ?? `${row.meetingId}-${row.application.nickname}`}
            >
              <div className={styles.itemMain}>
                <div className={styles.itemTitleRow}>
                  <b className={styles.meetingTitle}>{row.meetingTitle}</b>
                  <span className={styles.badge}>
                    {statusLabel[row.application.status ?? "pending"] ?? row.application.status}
                  </span>
                </div>
                <span className={styles.nickname}>{row.application.nickname}</span>
                {row.application.message ? <p className={styles.text}>{row.application.message}</p> : null}
              </div>

              <div className={styles.actions}>
                <button
                  className={styles.primaryButton}
                  disabled={busyId === row.application.application_id || row.application.status !== "pending"}
                  onClick={() => decide(row, "approve")}
                  type="button"
                >
                  승인
                </button>
                <button
                  className={styles.secondaryButton}
                  disabled={busyId === row.application.application_id || row.application.status !== "pending"}
                  onClick={() => decide(row, "reject")}
                  type="button"
                >
                  거절
                </button>
              </div>
            </article>
          ))
        ) : (
          <div className={styles.empty}>표시할 신청이 없습니다.</div>
        )}
      </section>
    </main>
  );
}
