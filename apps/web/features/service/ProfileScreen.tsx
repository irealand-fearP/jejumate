"use client";

import { useEffect, useState } from "react";
import {
  CalendarClock,
  LogOut,
  MapPin,
  MessageCircle,
  ShieldCheck,
  Trash2,
  UserRound,
} from "lucide-react";
import {
  createNickname,
  deleteMeeting,
  deleteMyApplication,
  getMeetingDetail,
  getMyApplicationNotifications,
  type ApplicantNotification,
  type HomeMeeting,
  type ProfilePreviewData,
} from "@/lib/api";
import { listOwnedMeetings, removeOwnerSecret } from "@/lib/ownerSecret";
import { CenterModal } from "@/features/common/CenterModal";
import { ChatSheet } from "@/features/common/ChatSheet";
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

// 공용 ChatSheet에 넘길 최소 정보. 접근 권한(호스트 관리 코드/익명 ID)은 ChatSheet가
// localStorage와 profile에서 알아서 읽는다.
type ChatTarget = {
  meetingId: string;
  title: string;
  placeLabel: string;
};

// '참여중인 파티' 통합 목록 한 줄. 호스트/참가자 두 데이터 소스를 같은 모양으로 맞춰서 함께 정렬·렌더링한다.
type PartyListItem = {
  key: string;
  role: "host" | "participant";
  meetingId: string;
  title: string;
  placeLabel: string | null;
  startsAt: string | null;
  detailLabel: string | null;
  chatTarget: ChatTarget | null;
  /** 참가자 항목의 '파티 탈퇴'용(내 신청 id). */
  applicationId?: string;
  /** 호스트 항목의 '파티 해산'용(관리 코드). */
  ownerSecret?: string;
};

// 확인 다이얼로그로 물어볼 파티 관리 동작.
type PartyAction = {
  kind: "leave" | "disband";
  party: PartyListItem;
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

  // 확인 다이얼로그로 물어보는 중인 파티 관리 동작(탈퇴/해산).
  const [pendingAction, setPendingAction] = useState<PartyAction | null>(null);
  const [actionBusy, setActionBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const [chatTarget, setChatTarget] = useState<ChatTarget | null>(null);

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

  /** 확인 다이얼로그에서 '확인'을 눌렀을 때 실제로 탈퇴/해산을 수행한다. */
  async function runPendingAction() {
    if (!pendingAction) return;
    const { kind, party } = pendingAction;
    setActionBusy(true);
    setActionError(null);

    try {
      if (kind === "leave") {
        if (!party.applicationId || !profile?.anonymousId) return;
        await deleteMyApplication(party.meetingId, party.applicationId, profile.anonymousId);
        // 목록에서 즉시 제거한다(서버 재조회를 기다리지 않는다).
        setApprovedMeetings((current) => current.filter((m) => m.application_id !== party.applicationId));
      } else {
        if (!party.ownerSecret) return;
        await deleteMeeting(party.meetingId, party.ownerSecret);
        setOwnedMeetings((current) => current.filter((owned) => owned.meetingId !== party.meetingId));
        // 해산했으면 이 기기에 남은 관리 코드도 지운다.
        removeOwnerSecret(party.meetingId);
      }
      setPendingAction(null);
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "처리하지 못했어요. 잠시 후 다시 시도해 주세요.");
    } finally {
      setActionBusy(false);
    }
  }

  function closePendingAction() {
    if (actionBusy) return;
    setPendingAction(null);
    setActionError(null);
  }

  // 채팅은 공용 ChatSheet가 담당한다(4초 폴링·본인/타인 정렬 포함) — 여기서는 어떤 파티의
  // 채팅을 열지만 결정한다. 예전엔 이 화면이 자체 채팅 구현을 갖고 있어서 폴링도 정렬도
  // 없었고, "내가 보내거나 다시 들어와야 새 메시지가 보인다"는 버그가 있었다.
  function handleChatProfileCreated(nextProfile: LocalProfile) {
    window.localStorage.setItem(PROFILE_STORAGE_KEY, JSON.stringify(nextProfile));
    setProfile(nextProfile);
  }

  // 호스트 목록 + 승인된 참가 목록을 '참여중인 파티' 하나로 합치고 날짜순으로 정렬한다.
  const participantParties: PartyListItem[] = approvedMeetings.map((meeting) => ({
    key: `participant-${meeting.application_id}`,
    role: "participant",
    meetingId: meeting.meeting_id,
    title: meeting.meeting_title,
    placeLabel: meeting.place_label,
    startsAt: meeting.starts_at,
    detailLabel: `호스트 ${meeting.host_nickname}`,
    applicationId: meeting.application_id,
    chatTarget: {
      meetingId: meeting.meeting_id,
      title: meeting.meeting_title,
      placeLabel: meeting.place_label,
    },
  }));

  const hostParties: PartyListItem[] = ownedMeetings.map((owned) => ({
    key: `host-${owned.meetingId}`,
    role: "host",
    meetingId: owned.meetingId,
    title: owned.meeting?.title ?? "삭제되었거나 찾을 수 없는 파티",
    placeLabel: owned.meeting?.place_label ?? null,
    startsAt: owned.meeting?.starts_at ?? null,
    detailLabel: owned.meeting ? `${owned.meeting.approved_count}/${owned.meeting.capacity}명` : null,
    ownerSecret: owned.ownerSecret,
    chatTarget: owned.meeting
      ? { meetingId: owned.meetingId, title: owned.meeting.title, placeLabel: owned.meeting.place_label }
      : null,
  }));

  const myParties = [...participantParties, ...hostParties].sort((a, b) => {
    // 날짜 정보가 없는 항목(삭제된 모임 등)은 맨 뒤로 보낸다.
    if (!a.startsAt) return 1;
    if (!b.startsAt) return -1;
    return new Date(a.startsAt).getTime() - new Date(b.startsAt).getTime();
  });

  return (
    <MobileShell active="profile" title="내정보">
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
                <div className={styles.partyActions}>
                  {party.chatTarget ? (
                    <button
                      className={styles.secondaryButton}
                      onClick={() => setChatTarget(party.chatTarget as ChatTarget)}
                      type="button"
                    >
                      <MessageCircle size={14} /> 채팅
                    </button>
                  ) : null}
                  {party.role === "participant" && party.applicationId ? (
                    <button
                      className={styles.secondaryButton}
                      onClick={() => setPendingAction({ kind: "leave", party })}
                      type="button"
                    >
                      <LogOut size={14} /> 파티 탈퇴
                    </button>
                  ) : null}
                  {party.role === "host" && party.ownerSecret ? (
                    <button
                      className={styles.dangerButton}
                      onClick={() => setPendingAction({ kind: "disband", party })}
                      type="button"
                    >
                      <Trash2 size={14} /> 파티 해산
                    </button>
                  ) : null}
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className={styles.profileGrid}>
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
        <ChatSheet
          meetingId={chatTarget.meetingId}
          meetingTitle={chatTarget.title}
          meetingPlaceLabel={chatTarget.placeLabel}
          hasAccess
          profile={profile}
          onProfileCreated={handleChatProfileCreated}
          onClose={() => setChatTarget(null)}
        />
      ) : null}

      {pendingAction ? (
        <CenterModal
          busy={actionBusy}
          cancelLabel="취소"
          confirmLabel={
            actionBusy ? "처리 중" : pendingAction.kind === "disband" ? "해산하기" : "탈퇴하기"
          }
          description={
            actionError
              ? actionError
              : pendingAction.kind === "disband"
                ? `'${pendingAction.party.title}' 파티를 해산합니다. 참가자들에게 알림 없이 파티가 삭제되며, 신청과 채팅도 함께 사라집니다. 되돌릴 수 없습니다.`
                : `'${pendingAction.party.title}' 파티에서 탈퇴합니다. 다시 참여하려면 새로 신청해야 합니다.`
          }
          destructive={pendingAction.kind === "disband"}
          onClose={closePendingAction}
          onConfirm={runPendingAction}
          title={pendingAction.kind === "disband" ? "파티를 해산할까요?" : "파티에서 탈퇴할까요?"}
        />
      ) : null}
    </MobileShell>
  );
}
