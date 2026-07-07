"use client";

import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { useRouter } from "next/navigation";
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
import styles from "./HomeScreen.module.css";

type SheetKey = "nickname" | "privacy" | "apply" | "ask" | "chat";

type HotspotAction =
  | { type: "sheet"; key: SheetKey; meetingIndex?: number }
  | { type: "route"; href: string };

type Hotspot = {
  action: HotspotAction;
  label: string;
  left: number;
  top: number;
  width: number;
  height: number;
};

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

const hotspots: Hotspot[] = [
  { action: { type: "sheet", key: "nickname" }, label: "닉네임 만들기", left: 56.8, top: 2.6, width: 15.2, height: 3.2 },
  { action: { type: "sheet", key: "privacy" }, label: "실명 비공개 안내", left: 74.9, top: 2.6, width: 20.1, height: 3.2 },
  { action: { type: "sheet", key: "privacy" }, label: "개인정보 안내 배너", left: 4.9, top: 8.5, width: 90.2, height: 5.9 },
  { action: { type: "route", href: "/meetings" }, label: "전체 모임 보기", left: 81.4, top: 16.9, width: 13.7, height: 3.1 },
  { action: { type: "route", href: "/meetings" }, label: "전체 필터", left: 4.8, top: 20.7, width: 13.0, height: 3.0 },
  { action: { type: "route", href: "/meetings" }, label: "밥친구 필터", left: 20.0, top: 20.7, width: 18.0, height: 3.0 },
  { action: { type: "route", href: "/meetings" }, label: "작업 필터", left: 39.6, top: 20.7, width: 17.9, height: 3.0 },
  { action: { type: "route", href: "/meetings" }, label: "이동 필터", left: 59.5, top: 20.7, width: 16.5, height: 3.0 },
  { action: { type: "route", href: "/meetings" }, label: "커피챗 필터", left: 78.0, top: 20.7, width: 17.0, height: 3.0 },
  { action: { type: "sheet", key: "apply", meetingIndex: 0 }, label: "함덕 점심 같이 먹자 신청", left: 76.4, top: 31.0, width: 18.3, height: 2.4 },
  { action: { type: "sheet", key: "apply", meetingIndex: 1 }, label: "오션뷰 카페 작업팟 신청", left: 76.4, top: 41.0, width: 18.3, height: 2.4 },
  { action: { type: "sheet", key: "apply", meetingIndex: 2 }, label: "해안도로 러닝 신청", left: 76.4, top: 51.0, width: 18.3, height: 2.4 },
  { action: { type: "sheet", key: "apply", meetingIndex: 3 }, label: "공항 서귀포 택시팟 신청", left: 76.4, top: 60.9, width: 18.3, height: 2.4 },
  { action: { type: "route", href: "/meetings" }, label: "제주 활동 현황", left: 4.6, top: 64.3, width: 90.6, height: 5.3 },
  { action: { type: "sheet", key: "ask" }, label: "RAG 질문 열기", left: 4.6, top: 70.8, width: 90.6, height: 5.9 },
  { action: { type: "route", href: "/policies" }, label: "청년 기회 더 보기", left: 81.0, top: 79.0, width: 14.0, height: 3.2 },
  { action: { type: "route", href: "/policies" }, label: "제주 청년 큐레이션 여행 지원", left: 4.6, top: 81.2, width: 90.6, height: 6.6 },
  { action: { type: "route", href: "/meetings" }, label: "하단 탭 모임", left: 20.0, top: 94.1, width: 15.0, height: 5.7 },
  { action: { type: "route", href: "/question" }, label: "하단 탭 질문", left: 39.0, top: 94.1, width: 15.0, height: 5.7 },
  { action: { type: "route", href: "/policies" }, label: "하단 탭 정책", left: 58.6, top: 94.1, width: 15.0, height: 5.7 },
  { action: { type: "route", href: "/profile" }, label: "하단 탭 내정보", left: 78.2, top: 94.1, width: 15.0, height: 5.7 },
];

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

  function openHotspot(action: HotspotAction) {
    setResult(null);
    setAnswer(null);

    if (action.type === "route") {
      router.push(action.href);
      return;
    }

    setSheetKey(action.key);
    if (action.key === "apply") {
      setSelectedMeeting(typeof action.meetingIndex === "number" ? data.meetings[action.meetingIndex] ?? null : null);
      setMessage("");
      setPrivacyChecked(false);
      setNickname(profile?.nickname ?? nickname);
    }
    if (action.key === "ask") {
      setQuestion(data.rag_strip.suggestions[0] ?? "");
    }
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
    <main className={styles.prototypeCanvas}>
      <section className={styles.lockedPhone} aria-label="제주메이트 최종 잠금 시안">
        <img
          className={styles.lockedMock}
          src="/assets/jejumate-final-locked.png"
          alt="제주메이트 홈 화면 최종 시안"
          draggable="false"
        />
        <div className={styles.hotspotLayer} aria-label="서비스 연결 영역">
          {hotspots.map((hotspot, index) => (
            <button
              key={`${hotspot.label}-${index}`}
              className={styles.hotspot}
              style={{
                left: `${hotspot.left}%`,
                top: `${hotspot.top}%`,
                width: `${hotspot.width}%`,
                height: `${hotspot.height}%`,
              }}
              onClick={() => openHotspot(hotspot.action)}
              aria-label={hotspot.label}
              type="button"
            />
          ))}
        </div>
      </section>

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
              {selectedMeeting.approved_count}/{selectedMeeting.capacity}명 참여 중 · 호스트 {selectedMeeting.host.nickname}
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
    </main>
  );
}
