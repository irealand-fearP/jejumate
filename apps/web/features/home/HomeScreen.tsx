"use client";

import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { useRouter } from "next/navigation";
import { ChevronRight, LockKeyhole, MessageCircle, ShieldCheck, UserRound, UsersRound } from "lucide-react";
import {
  askRag,
  createNickname,
  getMeetingChatMessages,
  sendMeetingChatMessage,
  submitMeetingApplication,
  type ChatMessage,
  type HomeData,
  type HomeMeeting,
  type NicknameProfile,
  type RagAnswer,
} from "@/lib/api";
import { HostPendingBanner } from "@/features/common/HostPendingBanner";
import { AskEntryCard } from "./AskEntryCard";
import { BoardSection } from "./BoardSection";
import { BottomNav } from "./BottomNav";
import { MeetingTimeline } from "./MeetingTimeline";
import { PolicySection } from "./PolicySection";
import styles from "./HomeScreen.module.css";

type SheetKey = "nickname" | "privacy" | "apply" | "ask" | "chat";

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
  const [chatInput, setChatInput] = useState("");
  const [chatNotice, setChatNotice] = useState("");
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [privacyChecked, setPrivacyChecked] = useState(false);
  const [question, setQuestion] = useState(data.rag_strip.suggestions[0] ?? "");
  const [answer, setAnswer] = useState<RagAnswer | null>(null);
  const [result, setResult] = useState<ResultState | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const savedProfile = readProfile();
    if (savedProfile) {
      setProfile(savedProfile);
      setNickname(savedProfile.nickname);
    }
  }, []);

  function openApply(meeting: HomeMeeting) {
    setResult(null);
    setAnswer(null);
    setSelectedMeeting(meeting);
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

  function closeSheet() {
    setSheetKey(null);
    setSelectedMeeting(null);
    setResult(null);
    setAnswer(null);
    setChatInput("");
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

  async function openChat(meeting: HomeMeeting | null = selectedMeeting) {
    if (!meeting) return;
    setSelectedMeeting(meeting);
    setSheetKey("chat");
    setResult(null);
    setChatInput("");
    setBusy(true);

    try {
      const chat = await getMeetingChatMessages(meeting.id);
      setChatMessages(chat.messages);
      setChatNotice(chat.notice);
    } catch {
      setResult({ tone: "error", title: "채팅 불러오기 실패", body: "잠시 후 다시 시도해 주세요." });
    } finally {
      setBusy(false);
    }
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

  async function submitChatMessage() {
    if (!selectedMeeting || nickname.trim().length < 2 || chatInput.trim().length < 1) return;
    setBusy(true);
    setResult(null);

    try {
      let currentProfile = profile;
      if (!currentProfile) {
        currentProfile = buildLocalProfile(await createNickname(nickname.trim()));
        saveProfileLocally(currentProfile);
      }

      const chat = await sendMeetingChatMessage(selectedMeeting.id, {
        nickname: currentProfile.nickname,
        content: chatInput.trim(),
        anonymous_id: currentProfile.anonymousId,
      });
      setChatMessages(chat.messages);
      setChatNotice(chat.notice);
      setChatInput("");
    } catch {
      setResult({ tone: "error", title: "메시지 전송 실패", body: "잠시 후 다시 시도해 주세요." });
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

        <HostPendingBanner variant="inline" />

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

        <button className={styles.activityCard} onClick={() => router.push("/meetings")} type="button">
          <img src="/assets/activity-thumbs.png" alt="" />
          <span>
            지금 제주 어딘가에서 <b>{data.activity_summary.active_people_count}명</b>이 함께 놀고 있어요!
          </span>
          <UsersRound size={25} />
        </button>

        <AskEntryCard onOpen={openQuestionSheet} />

        <BoardSection />

        <PolicySection policies={data.policies} />

        <BottomNav />

        <div className={styles.chatShortcut}>
          {data.meetings[0] ? (
            <button onClick={() => openChat(data.meetings[0])} type="button" aria-label="최근 모임 채팅">
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
                실명과 연락처를 메시지에 적지 않았습니다.
              </button>
              <button
                disabled={busy || nickname.trim().length < 2 || !privacyChecked}
                onClick={submitApplication}
                type="button"
              >
                {busy ? "접수 중" : "신청 제출"}
              </button>
              <button
                className={styles.secondaryAction}
                disabled={busy || !selectedMeeting}
                onClick={() => openChat(selectedMeeting)}
                type="button"
              >
                모임 채팅 보기
              </button>
            </div>
            {renderResult()}
          </BottomSheet>
        ) : null}

        {sheetKey === "chat" && selectedMeeting ? (
          <BottomSheet title="모임 채팅" onClose={closeSheet}>
            <div className={styles.meetingSummary}>
              <b>{selectedMeeting.title}</b>
              <span>{selectedMeeting.place_label}</span>
            </div>
            <div className={styles.chatNotice}>
              {chatNotice || "연락처 공유는 신중하게 해주세요. 불편한 요청은 신고할 수 있어요."}
            </div>
            <div className={styles.chatList}>
              {chatMessages.length ? (
                chatMessages.map((chat) => (
                  <div className={styles.chatBubble} key={chat.id}>
                    <b>{chat.sender_nickname}</b>
                    <span>{chat.content}</span>
                  </div>
                ))
              ) : (
                <div className={styles.emptyChat}>아직 메시지가 없어요. 첫 인사를 남겨보세요.</div>
              )}
            </div>
            <div className={styles.sheetForm}>
              <label htmlFor="home-chat-nickname">닉네임</label>
              <input
                id="home-chat-nickname"
                maxLength={20}
                onChange={(event) => setNickname(event.target.value)}
                value={nickname}
              />
              <label htmlFor="home-chat-message">메시지</label>
              <textarea
                id="home-chat-message"
                maxLength={500}
                onChange={(event) => setChatInput(event.target.value)}
                placeholder="약속 장소나 준비물을 편하게 이야기해보세요."
                value={chatInput}
              />
              <button
                disabled={busy || nickname.trim().length < 2 || chatInput.trim().length < 1}
                onClick={submitChatMessage}
                type="button"
              >
                {busy ? "보내는 중" : "메시지 보내기"}
              </button>
            </div>
            {renderResult()}
          </BottomSheet>
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
                <div>
                  {answer.sources.map((source) => (
                    <a href={source.url} key={`${source.source_type}-${source.title}`} rel="noreferrer" target="_blank">
                      {source.title}
                    </a>
                  ))}
                </div>
              </div>
            ) : null}
            {renderResult()}
          </BottomSheet>
        ) : null}
      </section>
    </main>
  );
}
