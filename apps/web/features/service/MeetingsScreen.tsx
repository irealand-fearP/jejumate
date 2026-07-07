"use client";

import { useMemo, useState } from "react";
import {
  CalendarClock,
  Car,
  CheckCircle2,
  Coffee,
  Dumbbell,
  Laptop,
  LockKeyhole,
  MapPin,
  Utensils,
  UsersRound,
  X,
} from "lucide-react";
import { createNickname, submitMeetingApplication, type HomeMeeting, type MeetingsData } from "@/lib/api";
import { MobileShell } from "@/features/common/MobileShell";
import styles from "./ServicePages.module.css";

type LocalProfile = {
  profileId: string;
  nickname: string;
  anonymousId: string;
};

const PROFILE_STORAGE_KEY = "jejumate.localProfile";

function formatTime(value: string): string {
  return new Intl.DateTimeFormat("ko-KR", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone: "Asia/Seoul",
  }).format(new Date(value));
}

function readProfile(): LocalProfile | null {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(PROFILE_STORAGE_KEY);
  if (!raw) return null;

  try {
    return JSON.parse(raw) as LocalProfile;
  } catch {
    window.localStorage.removeItem(PROFILE_STORAGE_KEY);
    return null;
  }
}

const categoryIcon: Record<string, typeof UsersRound> = {
  meal: Utensils,
  work: Laptop,
  move: Car,
  coffee: Coffee,
  run: Dumbbell,
};

function getMeetingIcon(category: string) {
  return categoryIcon[category] ?? UsersRound;
}

export function MeetingsScreen({ data }: { data: MeetingsData }) {
  const [activeFilter, setActiveFilter] = useState(data.filters[0] ?? "전체");
  const [selected, setSelected] = useState<HomeMeeting | null>(null);
  const [profile, setProfile] = useState<LocalProfile | null>(() => readProfile());
  const [nickname, setNickname] = useState(profile?.nickname ?? "");
  const [message, setMessage] = useState("");
  const [privacyChecked, setPrivacyChecked] = useState(false);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<string | null>(null);

  const meetings = useMemo(() => {
    if (activeFilter === "전체") return data.meetings;
    const categoryByFilter: Record<string, string> = {
      밥친구: "meal",
      작업: "work",
      이동: "move",
      커피챗: "coffee",
      러닝: "run",
    };
    return data.meetings.filter((meeting) => meeting.category === categoryByFilter[activeFilter]);
  }, [activeFilter, data.meetings]);

  async function apply() {
    if (!selected || nickname.trim().length < 2 || !privacyChecked) return;

    setBusy(true);
    setResult(null);

    try {
      let currentProfile = profile;
      if (!currentProfile) {
        const created = await createNickname(nickname.trim());
        currentProfile = {
          profileId: created.profile_id,
          nickname: created.nickname,
          anonymousId: created.anonymous_id,
        };
        window.localStorage.setItem(PROFILE_STORAGE_KEY, JSON.stringify(currentProfile));
        setProfile(currentProfile);
      }

      const application = await submitMeetingApplication(selected.id, {
        nickname: currentProfile.nickname,
        message: message.trim() || undefined,
        anonymous_id: currentProfile.anonymousId,
      });
      setResult(`${application.public_alias} 님의 신청이 접수됐습니다. ${application.next_step}`);
    } catch {
      setResult("신청을 처리하지 못했습니다. 잠시 후 다시 시도해 주세요.");
    } finally {
      setBusy(false);
    }
  }

  function openMeeting(meeting: HomeMeeting) {
    setSelected(meeting);
    setMessage("");
    setResult(null);
    setPrivacyChecked(false);
    setNickname(profile?.nickname ?? nickname);
  }

  return (
    <MobileShell active="meetings" title="모임" subtitle="닉네임만 공개하고 가볍게 합류해요">
      <div className={styles.toolbar}>
        {data.filters.map((filter) => (
          <button
            className={`${styles.chip} ${activeFilter === filter ? styles.chipActive : ""}`}
            key={filter}
            onClick={() => setActiveFilter(filter)}
            type="button"
          >
            {filter}
          </button>
        ))}
      </div>

      <div className={styles.notice}>{data.privacy_note}</div>

      <section className={styles.meetingList}>
        {meetings.map((meeting) => {
          const Icon = getMeetingIcon(meeting.category);
          return (
            <article className={styles.card} key={meeting.id}>
              <div className={styles.time}>
                <CalendarClock size={18} />
                <strong>{formatTime(meeting.starts_at)}</strong>
                <span>~ {formatTime(meeting.ends_at)}</span>
              </div>
              <div className={styles.timelineDot} aria-hidden="true">
                <span />
              </div>
              <div className={styles.categoryBubble}>
                <Icon size={25} strokeWidth={2.2} />
              </div>
              <div className={styles.body}>
                <h2>{meeting.title}</h2>
                <p className={styles.meta}>
                  <MapPin size={14} /> {meeting.place_label}
                </p>
                <p className={styles.host}>호스트 {meeting.host.nickname}</p>
              </div>
              <div className={styles.joinPanel}>
                <b>
                  {meeting.approved_count}/{meeting.capacity}
                </b>
                <span>지금 합류 가능</span>
                <button className={styles.button} onClick={() => openMeeting(meeting)} type="button">
                  신청
                </button>
              </div>
            </article>
          );
        })}
      </section>

      {selected ? (
        <div className={styles.sheetBackdrop} onClick={() => setSelected(null)}>
          <section className={styles.sheet} onClick={(event) => event.stopPropagation()}>
            <button className={styles.sheetClose} onClick={() => setSelected(null)} type="button" aria-label="닫기">
              <X size={20} />
            </button>
            <div className={styles.sheetGrip} />
            <div className={styles.sheetHero}>
              <span>
                <LockKeyhole size={14} /> 닉네임만 공개
              </span>
              <h2>{selected.title}</h2>
              <p>
                {selected.place_label} · {selected.approved_count}/{selected.capacity}명 참여 중
              </p>
            </div>
            <div className={styles.form}>
              <label className={styles.label} htmlFor="meeting-nickname">
                공개 닉네임
              </label>
              <input
                className={styles.input}
                id="meeting-nickname"
                maxLength={20}
                onChange={(event) => setNickname(event.target.value)}
                placeholder="예: 바당이"
                value={nickname}
              />
              <label className={styles.label} htmlFor="meeting-message">
                호스트에게 남길 말
              </label>
              <textarea
                className={styles.textarea}
                id="meeting-message"
                maxLength={160}
                onChange={(event) => setMessage(event.target.value)}
                placeholder="선택 입력. 실명이나 연락처는 쓰지 마세요."
                value={message}
              />
              <button
                className={styles.checkRow}
                onClick={() => setPrivacyChecked((checked) => !checked)}
                type="button"
              >
                <span className={privacyChecked ? styles.checkActive : ""}>
                  {privacyChecked ? <CheckCircle2 size={16} /> : null}
                </span>
                실명과 연락처를 메시지에 적지 않았습니다.
              </button>
              {result ? <div className={styles.result}>{result}</div> : null}
            </div>
            <div className={styles.sheetActions}>
              <button className={styles.secondaryButton} onClick={() => setSelected(null)} type="button">
                닫기
              </button>
              <button
                className={styles.primaryButton}
                disabled={busy || nickname.trim().length < 2 || !privacyChecked}
                onClick={apply}
                type="button"
              >
                {busy ? "처리 중" : "신청 제출"}
              </button>
            </div>
          </section>
        </div>
      ) : null}
    </MobileShell>
  );
}
