"use client";

import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Bell, ChevronRight, Info, LockKeyhole, MessageCircle, ShieldCheck, UserRound, UsersRound } from "lucide-react";
import {
  askRag,
  createNickname,
  getMyApplicationNotifications,
  submitMeetingApplication,
  type ApplicantNotification,
  type HomeData,
  type HomeMeeting,
  type NicknameProfile,
  type RagAnswer,
} from "@/lib/api";
import { getOwnerSecret } from "@/lib/ownerSecret";
import { getNotificationsSeenAt, markNotificationsSeenNow } from "@/lib/applicantNotifications";
import { ApplicantNotificationBanner } from "@/features/common/ApplicantNotificationBanner";
import { ChatSheet } from "@/features/common/ChatSheet";
import { HostPendingBanner } from "@/features/common/HostPendingBanner";
import { PlaceMapSection } from "@/features/map/PlaceMapSection";
import { AskEntryCard } from "./AskEntryCard";
import { BoardSection } from "./BoardSection";
import { BottomNav } from "./BottomNav";
import { MeetingTimeline } from "./MeetingTimeline";
import styles from "./HomeScreen.module.css";

type SheetKey = "nickname" | "privacy" | "apply" | "ask" | "chat" | "external" | "notifications";

type LocalProfile = {
  profileId: string;
  nickname: string;
  anonymousId: string;
};

type ResultState = {
  tone: "success" | "error" | "info";
  title: string;
  body: string;
};

const PROFILE_STORAGE_KEY = "jejumate.localProfile";

function buildLocalProfile(profile: NicknameProfile): LocalProfile {
  return {
    profileId: profile.profile_id,
    nickname: profile.nickname,
    anonymousId: profile.anonymous_id,
  };
}

function readProfile(): LocalProfile | null {
  const rawProfile = window.localStorage.getItem(PROFILE_STORAGE_KEY);
  if (!rawProfile) return null;

  try {
    const parsed = JSON.parse(rawProfile) as LocalProfile;
    return parsed.nickname && parsed.profileId && parsed.anonymousId ? parsed : null;
  } catch {
    window.localStorage.removeItem(PROFILE_STORAGE_KEY);
    return null;
  }
}

// 승인/거절인데 마지막으로 알림을 확인한 시각 이후 갱신된 건수 — 배지에 그대로 쓴다.
function countUnseenNotifications(notifications: ApplicantNotification[]): number {
  const seenAt = getNotificationsSeenAt();
  const seenAtMs = seenAt ? new Date(seenAt).getTime() : 0;
  return notifications.filter(
    (notification) =>
      (notification.status === "approved" || notification.status === "rejected") &&
      new Date(notification.updated_at).getTime() > seenAtMs
  ).length;
}

function BottomSheet({
  children,
  title,
  onClose,
}: {
  children: ReactNode;
  title: string;
  onClose: () => void;
}) {
  return (
    <div className={styles.sheetBackdrop} onClick={onClose}>
      <section className={styles.bottomSheet} onClick={(event) => event.stopPropagation()}>
        <button className={styles.sheetClose} onClick={onClose} aria-label="닫기" type="button">
          ×
        </button>
        <h2>{title}</h2>
        {children}
      </section>
    </div>
  );
}

export function HomeScreen({ data }: { data: HomeData }) {
  const router = useRouter();
  const [sheetKey, setSheetKey] = useState<SheetKey | null>(null);
  const [selectedMeeting, setSelectedMeeting] = useState<HomeMeeting | null>(null);
  const [profile, setProfile] = useState<LocalProfile | null>(null);
  const [nickname, setNickname] = useState("");
  const [message, setMessage] = useState("");
  const [privacyChecked, setPrivacyChecked] = useState(false);
  const [question, setQuestion] = useState(data.rag_strip.suggestions[0] ?? "");
  const [answer, setAnswer] = useState<RagAnswer | null>(null);
  const [result, setResult] = useState<ResultState | null>(null);
  const [busy, setBusy] = useState(false);
  // 승인된 신청의 meeting_id -> application_id 매핑. 채팅 접근 권한 판단은 물론
  // 탈퇴 버튼에 필요한 application_id 조회에도 이 맵을 그대로 쓴다.
  const [approvedApplications, setApprovedApplications] = useState<Map<string, string>>(new Map());
  const [unseenNotificationCount, setUnseenNotificationCount] = useState(0);
  const [notifications, setNotifications] = useState<ApplicantNotification[] | null>(null);
  const [notificationsError, setNotificationsError] = useState<string | null>(null);

  useEffect(() => {
    const savedProfile = readProfile();
    if (savedProfile) {
      setProfile(savedProfile);
      setNickname(savedProfile.nickname);
    }
  }, []);

  // 채팅 접근 권한(승인된 신청자) 판단, 알림 뱃지 표시용. 호스트 여부는 getOwnerSecret으로
  // 그때그때 확인한다.
  useEffect(() => {
    if (!profile?.anonymousId) {
      setUnseenNotificationCount(0);
      return;
    }
    getMyApplicationNotifications(profile.anonymousId)
      .then((res) => {
        const approved = new Map(
          res.notifications
            .filter((n) => n.status === "approved")
            .map((n) => [n.meeting_id, n.application_id] as const)
        );
        setApprovedApplications(approved);
        setUnseenNotificationCount(countUnseenNotifications(res.notifications));
      })
      .catch(() => {
        // 조회 실패는 조용히 넘어간다 — 채팅 버튼/뱃지가 안 보이는 것 이상의 영향은 없다.
      });
  }, [profile?.anonymousId]);

  function hasChatAccess(meetingId: string): boolean {
    return getOwnerSecret(meetingId) !== null || approvedApplications.has(meetingId);
  }

  // 파티 탈퇴가 성공한 뒤 호출된다 — 이 모임에 대한 승인 상태를 지워서 채팅 접근권한과
  // 탈퇴 버튼이 다시 렌더링될 때 즉시 사라지게 한다.
  function handleMeetingLeft(meetingId: string) {
    setApprovedApplications((prev) => {
      const next = new Map(prev);
      next.delete(meetingId);
      return next;
    });
  }

  function openApply(meeting: HomeMeeting) {
    setResult(null);
    setAnswer(null);
    setSelectedMeeting(meeting);
    if (meeting.source === "kakao_chat") {
      // 오픈채팅에서 자동 변환된 글은 호스트가 없어 신청/승인 흐름을 붙이지 않는다.
      setSheetKey("external");
      return;
    }
    setMessage("");
    setPrivacyChecked(false);
    setNickname(profile?.nickname ?? nickname);
    setSheetKey("apply");
  }

  function openQuestionSheet() {
    setResult(null);
    setAnswer(null);
    setQuestion(data.rag_strip.suggestions[0] ?? "");
    setSheetKey("ask");
  }

  // '내 신청 알림 확인' 진입점 — 항상 노출되는 버튼에서 호출되며, 신청 결과 목록을
  // 다시 불러와 시트로 보여준다. 연 시점에 확인 시각을 갱신해 뱃지를 지운다.
  async function openNotifications() {
    setSheetKey("notifications");
    setNotificationsError(null);

    if (!profile?.anonymousId) {
      setNotifications([]);
      return;
    }

    try {
      const res = await getMyApplicationNotifications(profile.anonymousId);
      setNotifications(res.notifications);
      markNotificationsSeenNow();
      setUnseenNotificationCount(0);
    } catch {
      setNotificationsError("알림을 불러오지 못했어요");
    }
  }

  function closeSheet() {
    setSheetKey(null);
    setSelectedMeeting(null);
    setResult(null);
    setAnswer(null);
  }

  function saveProfileLocally(nextProfile: LocalProfile) {
    window.localStorage.setItem(PROFILE_STORAGE_KEY, JSON.stringify(nextProfile));
    setProfile(nextProfile);
    setNickname(nextProfile.nickname);
  }

  async function saveNickname() {
    if (nickname.trim().length < 2) return;
    setBusy(true);
    setResult(null);

    try {
      const savedProfile = buildLocalProfile(await createNickname(nickname.trim(), profile?.anonymousId));
      saveProfileLocally(savedProfile);
      setResult({
        tone: "success",
        title: "닉네임 저장 완료",
        body: `${savedProfile.nickname} 님으로 신청과 질문 기록이 연결됩니다.`,
      });
    } catch {
      setResult({ tone: "error", title: "저장 실패", body: "잠시 후 다시 시도해 주세요." });
    } finally {
      setBusy(false);
    }
  }

  async function submitApplication() {
    if (!selectedMeeting || nickname.trim().length < 2 || !privacyChecked) return;
    setBusy(true);
    setResult(null);

    try {
      let currentProfile = profile;
      if (!currentProfile) {
        currentProfile = buildLocalProfile(await createNickname(nickname.trim()));
        saveProfileLocally(currentProfile);
      }

      const application = await submitMeetingApplication(selectedMeeting.id, {
        nickname: currentProfile.nickname,
        message: message.trim() || undefined,
        anonymous_id: currentProfile.anonymousId,
      });
      setResult({
        tone: "success",
        title: "신청 접수 완료",
        body: `${application.public_alias} 님의 신청이 저장되었습니다. ${application.next_step}`,
      });
    } catch {
      setResult({ tone: "error", title: "신청 실패", body: "잠시 후 다시 시도해 주세요." });
    } finally {
      setBusy(false);
    }
  }

  // 메시지 로딩/폴링/전송은 ChatSheet 컴포넌트가 담당한다 — 여기서는 어떤 모임의
  // 채팅을 열지만 결정한다.
  function openChat(meeting: HomeMeeting | null = selectedMeeting) {
    if (!meeting) return;
    setSelectedMeeting(meeting);
    setSheetKey("chat");
    setResult(null);
  }

  async function submitQuestion() {
    if (question.trim().length < 2) return;
    setBusy(true);
    setResult(null);
    setAnswer(null);

    try {
      setAnswer(await askRag(question.trim(), profile?.anonymousId));
    } catch {
      setResult({ tone: "error", title: "답변 실패", body: "잠시 후 다시 시도해 주세요." });
    } finally {
      setBusy(false);
    }
  }

  function renderResult() {
    return result ? (
      <div className={`${styles.resultCard} ${styles[result.tone]}`}>
        <b>{result.title}</b>
        <span>{result.body}</span>
      </div>
    ) : null;
  }

  return (
    <main className={styles.canvas}>
      <section className={styles.phone}>
        <header className={styles.header}>
          <div className={styles.logoBlock}>
            <img src="/assets/jejumate-logo.png" alt="제주메이트" />
            <p>제주 런케이션 커뮤니티</p>
          </div>
          <div className={styles.headerActions}>
            <button onClick={() => setSheetKey("nickname")} type="button">
              <UserRound size={17} /> 닉네임
            </button>
            <button className={styles.privacyPill} onClick={() => setSheetKey("privacy")} type="button">
              <LockKeyhole size={18} /> 실명 비공개
            </button>
          </div>
        </header>

        <button className={styles.notificationEntryButton} onClick={openNotifications} type="button">
          <Bell size={16} />
          내 신청 알림 확인
          {unseenNotificationCount > 0 ? (
            <span className={styles.notificationBadge}>
              {unseenNotificationCount > 9 ? "9+" : unseenNotificationCount}
            </span>
          ) : null}
        </button>

        <HostPendingBanner variant="inline" />
        <ApplicantNotificationBanner variant="inline" />

        <button className={styles.privacyBanner} onClick={() => setSheetKey("privacy")} type="button">
          <span>
            <ShieldCheck size={26} />
          </span>
          <strong>비로그인으로 간단하게!!</strong>
          <img src="/assets/banner-illustration.png" alt="" />
          <ChevronRight size={24} />
        </button>

        <MeetingTimeline
          meetings={data.meetings}
          filters={data.meeting_filters}
          openCount={data.meeting_summary.open_count}
          onApply={openApply}
        />

        <Link className={styles.activityCard} href="/meetings">
          <img src="/assets/activity-thumbs.png" alt="" />
          <span>
            지금 제주 어딘가에서 <b>{data.activity_summary.active_people_count}명</b>이 함께 놀고 있어요!
          </span>
          <UsersRound size={25} />
        </Link>

        <AskEntryCard onOpen={openQuestionSheet} />

        <BoardSection />

        <BottomNav />

        <div className={styles.chatShortcut}>
          {data.meetings[0] ? (
            <button onClick={() => openChat(data.meetings[0])} type="button" aria-label="최근 파티 채팅">
              <MessageCircle size={18} />
            </button>
          ) : null}
        </div>

        {sheetKey === "nickname" ? (
          <BottomSheet title="닉네임으로 시작" onClose={closeSheet}>
            <div className={styles.sheetForm}>
              <label htmlFor="home-nickname">공개 닉네임</label>
              <input
                id="home-nickname"
                maxLength={20}
                onChange={(event) => setNickname(event.target.value)}
                placeholder="예: 바당이"
                value={nickname}
              />
              <p>공개 프로필에는 닉네임만 표시됩니다.</p>
              <button disabled={busy || nickname.trim().length < 2} onClick={saveNickname} type="button">
                {busy ? "저장 중" : "닉네임 저장"}
              </button>
            </div>
            {renderResult()}
          </BottomSheet>
        ) : null}

        {sheetKey === "privacy" ? (
          <BottomSheet title="실명 비공개" onClose={closeSheet}>
            <ul className={styles.privacyList}>
              <li>공개: 닉네임, 공개 관심사, 신청 상태</li>
              <li>비공개: 실명, 전화번호, 생년월일, 인증 원본</li>
              <li>운영자 확인: 신고, 안전 이슈, 정책 악용 의심 상황</li>
            </ul>
          </BottomSheet>
        ) : null}

        {sheetKey === "apply" && selectedMeeting ? (
          <BottomSheet title={selectedMeeting.title} onClose={closeSheet}>
            <div className={styles.meetingSummary}>
              <b>{selectedMeeting.place_label}</b>
              <span>
                {selectedMeeting.approved_count}/{selectedMeeting.capacity}명 참여 중 · 호스트{" "}
                {selectedMeeting.host.nickname}
              </span>
            </div>
            <div className={styles.sheetForm}>
              <label htmlFor="home-application-nickname">공개 닉네임</label>
              <input
                id="home-application-nickname"
                maxLength={20}
                onChange={(event) => setNickname(event.target.value)}
                value={nickname}
              />
              <label htmlFor="home-application-message">호스트에게 남길 말</label>
              <textarea
                id="home-application-message"
                maxLength={160}
                onChange={(event) => setMessage(event.target.value)}
                placeholder="선택 입력"
                value={message}
              />
              <button
                className={styles.checkRow}
                onClick={() => setPrivacyChecked((checked) => !checked)}
                type="button"
              >
                <span className={privacyChecked ? styles.checkedBox : ""} />
                신중하게 신청해 주세요. 승인 후 불참하면 기다리는 분들에게 피해가 갑니다.
              </button>
              <button
                disabled={busy || nickname.trim().length < 2 || !privacyChecked}
                onClick={submitApplication}
                type="button"
              >
                {busy ? "접수 중" : "신청 제출"}
              </button>
              {selectedMeeting && hasChatAccess(selectedMeeting.id) ? (
                <button
                  className={styles.secondaryAction}
                  disabled={busy}
                  onClick={() => openChat(selectedMeeting)}
                  type="button"
                >
                  파티 채팅 보기
                </button>
              ) : null}
            </div>
            {renderResult()}
          </BottomSheet>
        ) : null}

        {sheetKey === "external" && selectedMeeting ? (
          <BottomSheet title={selectedMeeting.title} onClose={closeSheet}>
            <div className={styles.meetingSummary}>
              <b>
                <span className={styles.externalBadge}>오픈채팅에서 온 글</span>
              </b>
              <span>{selectedMeeting.place_label}</span>
            </div>
            <p className={styles.externalNotice}>
              오픈채팅방에서 자동으로 가져온 글이에요. 서비스 내 신청·승인 없이, 오픈채팅방에서 직접 참여해
              주세요.
            </p>
            {selectedMeeting.description ? (
              <div className={styles.sheetForm}>
                <label>원문</label>
                <p className={styles.externalOriginal}>{selectedMeeting.description}</p>
              </div>
            ) : null}
          </BottomSheet>
        ) : null}

        {sheetKey === "chat" && selectedMeeting ? (
          <ChatSheet
            meetingId={selectedMeeting.id}
            meetingTitle={selectedMeeting.title}
            meetingPlaceLabel={selectedMeeting.place_label}
            hasAccess={hasChatAccess(selectedMeeting.id)}
            profile={profile}
            onProfileCreated={saveProfileLocally}
            myApplicationId={approvedApplications.get(selectedMeeting.id)}
            onLeft={() => handleMeetingLeft(selectedMeeting.id)}
            onClose={closeSheet}
          />
        ) : null}

        {sheetKey === "ask" ? (
          <BottomSheet title="제주메이트 질문" onClose={closeSheet}>
            <div className={styles.sheetForm}>
              <label htmlFor="home-rag-question">질문</label>
              <input
                id="home-rag-question"
                maxLength={120}
                onChange={(event) => setQuestion(event.target.value)}
                value={question}
              />
              <div className={styles.suggestionRow}>
                {data.rag_strip.suggestions.map((suggestion) => (
                  <button key={suggestion} onClick={() => setQuestion(suggestion)} type="button">
                    {suggestion}
                  </button>
                ))}
              </div>
              <button disabled={busy || question.trim().length < 2} onClick={submitQuestion} type="button">
                {busy ? "답변 생성 중" : "질문하기"}
              </button>
            </div>
            {answer ? (
              <div className={styles.answerCard}>
                <b>{answer.answer}</b>
                {answer.answer_source === "general_knowledge" ? (
                  <div className={styles.generalKnowledgeBadge}>
                    <Info size={14} />
                    <span>커뮤니티 근거 없음 · 일반 지식 참고 답변</span>
                  </div>
                ) : null}
                <div>
                  {answer.sources.map((source) => (
                    <a href={source.url} key={`${source.source_type}-${source.title}`} rel="noreferrer" target="_blank">
                      {source.title}
                    </a>
                  ))}
                </div>
                {answer.answer_source === "community" ? (
                  <PlaceMapSection
                    places={answer.sources.map((source) => ({ title: source.title, url: source.url }))}
                  />
                ) : null}
              </div>
            ) : null}
            {renderResult()}
          </BottomSheet>
        ) : null}

        {sheetKey === "notifications" ? (
          <BottomSheet title="내 신청 알림" onClose={closeSheet}>
            {!profile ? (
              <p className={styles.notificationEmpty}>아직 신청한 파티가 없어요. 먼저 파티에 신청해 보세요.</p>
            ) : null}
            {notificationsError ? (
              <div className={`${styles.resultCard} ${styles.error}`}>
                <span>{notificationsError}</span>
              </div>
            ) : null}
            {notifications && notifications.length > 0 ? (
              <ul className={styles.notificationList}>
                {notifications.map((notification) => (
                  <li className={styles.notificationRow} key={notification.application_id}>
                    <p className={styles.notificationTitle}>{notification.title}</p>
                    <p>{notification.body}</p>
                    <span>
                      {notification.meeting_title} · {notification.place_label} · 호스트{" "}
                      {notification.host_nickname}
                    </span>
                  </li>
                ))}
              </ul>
            ) : profile && notifications ? (
              <p className={styles.notificationEmpty}>아직 신청한 파티가 없어요.</p>
            ) : null}
          </BottomSheet>
        ) : null}
      </section>
    </main>
  );
}
