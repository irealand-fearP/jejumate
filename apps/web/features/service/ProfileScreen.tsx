"use client";

import { useEffect, useState } from "react";
import {
  CalendarClock,
  Eye,
  EyeOff,
  MapPin,
  MessageCircle,
  ShieldCheck,
  UserRound,
  X,
} from "lucide-react";
import {
  createNickname,
  getMeetingChatMessages,
  getMeetingDetail,
  getMyApplicationNotifications,
  sendMeetingChatMessage,
  type ApplicantNotification,
  type ChatMessage,
  type HomeMeeting,
  type ProfilePreviewData,
} from "@/lib/api";
import { listOwnedMeetings } from "@/lib/ownerSecret";
import { MobileShell } from "@/features/common/MobileShell";
import styles from "./ServicePages.module.css";

type LocalProfile = {
  profileId: string;
  nickname: string;
  anonymousId: string;
};

type OwnedMeetingItem = {
  meetingId: string;
  ownerSecret: string;
  meeting: HomeMeeting | null;
};

type ChatTarget = {
  meetingId: string;
  title: string;
  anonymousId?: string;
  ownerSecret?: string;
};

// '참여중인 파티' 통합 목록 한 줄. 호스트/참가자 두 데이터 소스를 같은 모양으로 맞춰서 함께 정렬·렌더링한다.
type PartyListItem = {
  key: string;
  role: "host" | "participant";
  title: string;
  placeLabel: string | null;
  startsAt: string | null;
  detailLabel: string | null;
  chatTarget: ChatTarget | null;
};

const PROFILE_STORAGE_KEY = "jejumate.localProfile";

function formatDateTime(value: string): string {
  return new Intl.DateTimeFormat("ko-KR", {
    month: "long",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone: "Asia/Seoul",
  }).format(new Date(value));
}

export function ProfileScreen({ data }: { data: ProfilePreviewData }) {
  const [profile, setProfile] = useState<LocalProfile | null>(null);
  const [nickname, setNickname] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<string | null>(null);

  const [approvedMeetings, setApprovedMeetings] = useState<ApplicantNotification[]>([]);
  const [ownedMeetings, setOwnedMeetings] = useState<OwnedMeetingItem[]>([]);
  const [ownedLoading, setOwnedLoading] = useState(false);

  const [chatTarget, setChatTarget] = useState<ChatTarget | null>(null);
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [chatNotice, setChatNotice] = useState("");
  const [chatInput, setChatInput] = useState("");
  const [chatNickname, setChatNickname] = useState("");
  const [chatBusy, setChatBusy] = useState(false);
  const [chatError, setChatError] = useState<string | null>(null);

  useEffect(() => {
    const raw = window.localStorage.getItem(PROFILE_STORAGE_KEY);
    if (!raw) return;

    try {
      const parsed = JSON.parse(raw) as LocalProfile;
      setProfile(parsed);
      setNickname(parsed.nickname);
    } catch {
      window.localStorage.removeItem(PROFILE_STORAGE_KEY);
    }
  }, []);

  // ① 내가 신청해서 승인된 모임: 신청 알림 중 상태가 approved인 것만 추린다.
  useEffect(() => {
    if (!profile?.anonymousId) {
      setApprovedMeetings([]);
      return;
    }
    getMyApplicationNotifications(profile.anonymousId)
      .then((res) => setApprovedMeetings(res.notifications.filter((n) => n.status === "approved")))
      .catch(() => {
        // 조회 실패는 조용히 넘어간다 — 이 기기에서 승인된 모임이 안 보이는 것 이상의 영향은 없다.
      });
  }, [profile?.anonymousId]);

  // ② 내가 만든 모임: 이 기기에 저장된 관리 코드 전부를 상세 정보와 함께 불러온다.
  useEffect(() => {
    const owned = listOwnedMeetings();
    if (owned.length === 0) {
      setOwnedMeetings([]);
      return;
    }
    setOwnedLoading(true);
    Promise.all(
      owned.map(async ({ meetingId, ownerSecret }) => {
        try {
          const meeting = await getMeetingDetail(meetingId);
          return { meetingId, ownerSecret, meeting };
        } catch {
          return { meetingId, ownerSecret, meeting: null };
        }
      })
    ).then((results) => {
      setOwnedMeetings(results);
      setOwnedLoading(false);
    });
  }, []);

  async function save() {
    if (nickname.trim().length < 2) return;
    setBusy(true);
    setResult(null);

    try {
      const created = await createNickname(nickname.trim(), profile?.anonymousId);
      const nextProfile = {
        profileId: created.profile_id,
        nickname: created.nickname,
        anonymousId: created.anonymous_id,
      };
      window.localStorage.setItem(PROFILE_STORAGE_KEY, JSON.stringify(nextProfile));
      setProfile(nextProfile);
      setResult("닉네임이 저장됐습니다. 공개 프로필에는 닉네임만 표시됩니다.");
    } catch {
      setResult("닉네임을 저장하지 못했습니다. 잠시 후 다시 시도해 주세요.");
    } finally {
      setBusy(false);
    }
  }

  async function openChat(target: ChatTarget) {
    setChatTarget(target);
    setChatError(null);
    setChatInput("");
    setChatNickname(profile?.nickname ?? nickname);
    setChatBusy(true);

    try {
      const chat = await getMeetingChatMessages(target.meetingId, {
        anonymousId: target.anonymousId,
        ownerSecret: target.ownerSecret,
      });
      setChatMessages(chat.messages);
      setChatNotice(chat.notice);
    } catch (error) {
      setChatError(error instanceof Error ? error.message : "채팅을 불러오지 못했어요.");
    } finally {
      setChatBusy(false);
    }
  }

  function closeChat() {
    setChatTarget(null);
  }

  async function sendChat() {
    if (!chatTarget || chatNickname.trim().length < 2 || chatInput.trim().length < 1) return;
    setChatBusy(true);
    setChatError(null);

    try {
      const chat = await sendMeetingChatMessage(chatTarget.meetingId, {
        nickname: chatNickname.trim(),
        content: chatInput.trim(),
        anonymous_id: chatTarget.anonymousId,
        owner_secret: chatTarget.ownerSecret,
      });
      setChatMessages(chat.messages);
      setChatNotice(chat.notice);
      setChatInput("");
    } catch (error) {
      setChatError(error instanceof Error ? error.message : "메시지를 보내지 못했어요.");
    } finally {
      setChatBusy(false);
    }
  }

  // 호스트 목록 + 승인된 참가 목록을 '참여중인 파티' 하나로 합치고 날짜순으로 정렬한다.
  const participantParties: PartyListItem[] = approvedMeetings.map((meeting) => ({
    key: `participant-${meeting.application_id}`,
    role: "participant",
    title: meeting.meeting_title,
    placeLabel: meeting.place_label,
    startsAt: meeting.starts_at,
    detailLabel: `호스트 ${meeting.host_nickname}`,
    chatTarget: {
      meetingId: meeting.meeting_id,
      title: meeting.meeting_title,
      anonymousId: profile?.anonymousId,
    },
  }));

  const hostParties: PartyListItem[] = ownedMeetings.map((owned) => ({
    key: `host-${owned.meetingId}`,
    role: "host",
    title: owned.meeting?.title ?? "삭제되었거나 찾을 수 없는 파티",
    placeLabel: owned.meeting?.place_label ?? null,
    startsAt: owned.meeting?.starts_at ?? null,
    detailLabel: owned.meeting ? `${owned.meeting.approved_count}/${owned.meeting.capacity}명` : null,
    chatTarget: owned.meeting
      ? { meetingId: owned.meetingId, title: owned.meeting.title, ownerSecret: owned.ownerSecret }
      : null,
  }));

  const myParties = [...participantParties, ...hostParties].sort((a, b) => {
    // 날짜 정보가 없는 항목(삭제된 모임 등)은 맨 뒤로 보낸다.
    if (!a.startsAt) return 1;
    if (!b.startsAt) return -1;
    return new Date(a.startsAt).getTime() - new Date(b.startsAt).getTime();
  });

  return (
    <MobileShell active="profile" title="내정보" subtitle="공개 정보와 비공개 정보를 분리해 관리해요">
      <section className={styles.profileCard}>
        <div className={styles.profileHero}>
          <div className={styles.avatar}>
            <UserRound size={24} />
          </div>
          <div>
            <h2>{profile ? profile.nickname : "닉네임 없음"}</h2>
            <p className={styles.meta}>{profile ? profile.anonymousId : "실명 없이 닉네임부터 만들 수 있습니다."}</p>
          </div>
        </div>
        <label className={styles.label} htmlFor="profile-nickname">
          공개 닉네임
        </label>
        <input
          className={styles.input}
          id="profile-nickname"
          maxLength={20}
          onChange={(event) => setNickname(event.target.value)}
          placeholder="예: 바당이"
          value={nickname}
        />
        <button className={styles.primaryButton} disabled={busy || nickname.trim().length < 2} onClick={save} type="button">
          {busy ? "저장 중" : "닉네임 저장"}
        </button>
        {result ? <div className={styles.result}>{result}</div> : null}
      </section>

      <section className={styles.profileCard}>
        <h2>
          <CalendarClock size={17} /> 참여중인 파티
        </h2>
        {ownedLoading ? (
          <p className={styles.meta}>불러오는 중...</p>
        ) : myParties.length === 0 ? (
          <p className={styles.meta}>아직 참여중인 파티가 없어요. 파티에 신청하거나 새로 만들어보세요.</p>
        ) : (
          <ul className={styles.applicantList}>
            {myParties.map((party) => (
              <li className={styles.notificationRow} key={party.key}>
                <div>
                  <p className={styles.notificationTitle}>
                    {party.title}{" "}
                    <span className={party.role === "host" ? styles.roleBadgeHost : styles.roleBadgeParticipant}>
                      {party.role === "host" ? "호스트" : "참가자"}
                    </span>
                  </p>
                  {party.placeLabel ? (
                    <p className={styles.meta}>
                      <MapPin size={13} /> {party.placeLabel}
                      {party.detailLabel ? ` · ${party.detailLabel}` : ""}
                    </p>
                  ) : null}
                  {party.startsAt ? <p className={styles.meta}>{formatDateTime(party.startsAt)}</p> : null}
                </div>
                {party.chatTarget ? (
                  <button className={styles.secondaryButton} onClick={() => openChat(party.chatTarget as ChatTarget)} type="button">
                    <MessageCircle size={14} /> 채팅
                  </button>
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className={styles.profileGrid}>
        <div className={styles.profileCard}>
          <h2>
            <Eye size={17} /> 공개되는 정보
          </h2>
          <ul>
            {data.public_fields.map((field) => (
              <li key={field}>{field}</li>
            ))}
          </ul>
        </div>
        <div className={styles.profileCard}>
          <h2>
            <EyeOff size={17} /> 공개되지 않는 정보
          </h2>
          <ul>
            {data.hidden_fields.map((field) => (
              <li key={field}>{field}</li>
            ))}
          </ul>
        </div>
        <div className={styles.profileCard}>
          <h2>
            <ShieldCheck size={17} /> 안전 기준
          </h2>
          <ul>
            {data.safety_notes.map((note) => (
              <li key={note}>{note}</li>
            ))}
          </ul>
        </div>
      </section>

      {chatTarget ? (
        <div className={styles.sheetBackdrop} onClick={closeChat}>
          <section className={styles.sheet} onClick={(event) => event.stopPropagation()}>
            <button className={styles.sheetClose} onClick={closeChat} type="button" aria-label="닫기">
              <X size={20} />
            </button>
            <div className={styles.sheetGrip} />
            <div className={styles.sheetHero}>
              <span>
                <MessageCircle size={14} /> 파티 채팅
              </span>
              <h2>{chatTarget.title}</h2>
            </div>

            <div className={styles.form}>
              {chatNotice ? <p className={styles.meta}>{chatNotice}</p> : null}
              {chatBusy && chatMessages.length === 0 ? (
                <p className={styles.meta}>불러오는 중...</p>
              ) : chatMessages.length === 0 ? (
                <p className={styles.meta}>아직 메시지가 없어요. 첫 인사를 남겨보세요.</p>
              ) : (
                <ul className={styles.applicantList}>
                  {chatMessages.map((message) => (
                    <li className={styles.notificationRow} key={message.id}>
                      <div>
                        <p className={styles.notificationTitle}>{message.sender_nickname}</p>
                        <p className={styles.meta}>{message.content}</p>
                      </div>
                    </li>
                  ))}
                </ul>
              )}

              {chatError ? <div className={styles.result}>{chatError}</div> : null}

              <label className={styles.label} htmlFor="profile-chat-nickname">
                닉네임
              </label>
              <input
                className={styles.input}
                id="profile-chat-nickname"
                maxLength={20}
                onChange={(event) => setChatNickname(event.target.value)}
                value={chatNickname}
              />
              <label className={styles.label} htmlFor="profile-chat-message">
                메시지
              </label>
              <textarea
                className={styles.textarea}
                id="profile-chat-message"
                maxLength={500}
                onChange={(event) => setChatInput(event.target.value)}
                placeholder="약속 장소나 준비물을 편하게 이야기해보세요."
                value={chatInput}
              />
            </div>

            <div className={styles.sheetActions}>
              <button className={styles.secondaryButton} onClick={closeChat} type="button">
                닫기
              </button>
              <button
                className={styles.primaryButton}
                disabled={chatBusy || chatNickname.trim().length < 2 || chatInput.trim().length < 1}
                onClick={sendChat}
                type="button"
              >
                {chatBusy ? "보내는 중" : "메시지 보내기"}
              </button>
            </div>
          </section>
        </div>
      ) : null}
    </MobileShell>
  );
}
