"use client";

import { useEffect, useState } from "react";
import {
  createNickname,
  deleteMyApplication,
  getMeetingChatMessages,
  sendMeetingChatMessage,
  type ChatMessage,
} from "@/lib/api";
import { getOwnerSecret } from "@/lib/ownerSecret";
// 채팅 시트 전용 CSS는 아직 없고, HomeScreen.module.css에 있던 걸 그대로 재사용한다
// (sheetBackdrop/bottomSheet/sheetForm/chatBubble 등은 채팅 전용이 아니라 시트 공통 스타일이라
// 이름 그대로 재사용해도 자연스럽다. 별도 모듈로 옮기는 건 과도한 리팩터링이라 하지 않는다).
import styles from "@/features/home/HomeScreen.module.css";

// 채팅 시트가 열려있는 동안 새 메시지를 반영하는 폴링 주기(HomeScreen 원본과 동일).
const CHAT_POLL_INTERVAL_MS = 4000;

export type ChatSheetProfile = {
  profileId: string;
  nickname: string;
  anonymousId: string;
};

type ChatSheetErrorState = {
  title: string;
  body: string;
};

type ChatSheetProps = {
  meetingId: string;
  meetingTitle: string;
  meetingPlaceLabel: string;
  /** 호출부(HomeScreen/MeetingsScreen)가 판단한 채팅 접근 가능 여부(호스트 or 승인된 신청자). */
  hasAccess: boolean;
  /** 로컬(무로그인) 프로필. 아직 없으면 첫 메시지 전송 시 새로 만든다. */
  profile: ChatSheetProfile | null;
  /** 채팅 중 프로필이 새로 만들어졌을 때 상위 화면 상태(및 localStorage)를 동기화하는 콜백. */
  onProfileCreated: (profile: ChatSheetProfile) => void;
  /**
   * 현재 프로필이 이 모임에 승인된 신청자로 갖고 있는 신청 ID.
   * 값이 있어야만(=승인된 참가자) 탈퇴 버튼을 보여준다 — 호스트는 별도 흐름(모임 관리)이 있으므로 제외.
   */
  myApplicationId?: string;
  /** 탈퇴가 성공적으로 처리된 뒤 상위 화면이 접근 권한/목록 상태를 갱신할 수 있게 알리는 콜백. */
  onLeft?: () => void;
  onClose: () => void;
};

/**
 * 모임 채팅 공용 시트. HomeScreen.tsx에 있던 채팅 로직(목록 렌더링, 본인/타인 정렬,
 * 4초 폴링, 전송)을 그대로 뽑아낸 것 — 동작은 바꾸지 않았다.
 */
export function ChatSheet({
  meetingId,
  meetingTitle,
  meetingPlaceLabel,
  hasAccess,
  profile,
  onProfileCreated,
  myApplicationId,
  onLeft,
  onClose,
}: ChatSheetProps) {
  const [nickname, setNickname] = useState(profile?.nickname ?? "");
  const [chatInput, setChatInput] = useState("");
  const [chatNotice, setChatNotice] = useState("");
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ChatSheetErrorState | null>(null);
  const [leaving, setLeaving] = useState(false);
  // 호스트는 자기 모임을 "탈퇴"하지 않는다(모임 관리/삭제는 별도 흐름) — 탈퇴 버튼은
  // 호스트가 아니면서 승인된 신청 ID를 가진 경우에만 노출한다.
  const isHost = getOwnerSecret(meetingId) !== null;
  const canLeaveMeeting = !isHost && Boolean(myApplicationId) && Boolean(profile?.anonymousId);

  async function leaveMeeting() {
    if (!myApplicationId || !profile?.anonymousId) return;
    if (!window.confirm("정말 이 파티에서 나가시겠어요? 채팅과 참가 정보가 사라져요.")) return;

    setLeaving(true);
    setError(null);
    try {
      await deleteMyApplication(meetingId, myApplicationId, profile.anonymousId);
      onLeft?.();
      onClose();
    } catch (err) {
      setError({
        title: "탈퇴 실패",
        body: err instanceof Error ? err.message : "잠시 후 다시 시도해 주세요.",
      });
    } finally {
      setLeaving(false);
    }
  }

  // 최초 로드 + 4초 폴링. 이 컴포넌트가 열려있는 동안에만 마운트되므로, 시트를 닫으면
  // (=언마운트되면) cleanup으로 interval이 확실히 멈춘다 — 원본의 setInterval + cleanup 패턴 그대로.
  useEffect(() => {
    if (!hasAccess) return;
    let cancelled = false;

    async function loadChatMessages(showBusy: boolean) {
      if (showBusy) {
        setBusy(true);
        setError(null);
      }
      try {
        const chat = await getMeetingChatMessages(meetingId, {
          anonymousId: profile?.anonymousId,
          ownerSecret: getOwnerSecret(meetingId) ?? undefined,
        });
        if (!cancelled) {
          setChatMessages(chat.messages);
          setChatNotice(chat.notice);
        }
      } catch (err) {
        // 폴링(showBusy=false) 실패는 조용히 넘어가고 다음 주기에 다시 시도한다.
        if (!cancelled && showBusy) {
          setError({
            title: "채팅 불러오기 실패",
            body: err instanceof Error ? err.message : "잠시 후 다시 시도해 주세요.",
          });
        }
      } finally {
        if (!cancelled && showBusy) setBusy(false);
      }
    }

    loadChatMessages(true);
    const timer = setInterval(() => loadChatMessages(false), CHAT_POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [meetingId, hasAccess, profile?.anonymousId]);

  async function submitChatMessage() {
    if (nickname.trim().length < 2 || chatInput.trim().length < 1) return;
    setBusy(true);
    setError(null);

    try {
      let currentProfile = profile;
      if (!currentProfile) {
        const created = await createNickname(nickname.trim());
        currentProfile = {
          profileId: created.profile_id,
          nickname: created.nickname,
          anonymousId: created.anonymous_id,
        };
        onProfileCreated(currentProfile);
      }

      const chat = await sendMeetingChatMessage(meetingId, {
        nickname: currentProfile.nickname,
        content: chatInput.trim(),
        anonymous_id: currentProfile.anonymousId,
        owner_secret: getOwnerSecret(meetingId) ?? undefined,
      });
      setChatMessages(chat.messages);
      setChatNotice(chat.notice);
      setChatInput("");
    } catch (err) {
      setError({
        title: "메시지 전송 실패",
        body: err instanceof Error ? err.message : "잠시 후 다시 시도해 주세요.",
      });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className={styles.sheetBackdrop} onClick={onClose}>
      <section className={styles.bottomSheet} onClick={(event) => event.stopPropagation()}>
        <button className={styles.sheetClose} onClick={onClose} aria-label="닫기" type="button">
          ×
        </button>
        <h2>파티 채팅</h2>
        <div className={styles.meetingSummary}>
          <b>{meetingTitle}</b>
          <span>{meetingPlaceLabel}</span>
        </div>
        {canLeaveMeeting ? (
          <button
            className={styles.leaveButton}
            disabled={leaving}
            onClick={leaveMeeting}
            type="button"
          >
            {leaving ? "나가는 중" : "파티 탈퇴"}
          </button>
        ) : null}
        <div className={styles.chatNotice}>
          {chatNotice || "연락처 공유는 신중하게 해주세요. 불편한 요청은 신고할 수 있어요."}
        </div>
        <div className={styles.chatList}>
          {chatMessages.length ? (
            chatMessages.map((chat) => {
              const isMine = profile?.anonymousId === chat.sender_anonymous_id;
              return (
                <div
                  className={isMine ? `${styles.chatBubble} ${styles.chatBubbleMine}` : styles.chatBubble}
                  key={chat.id}
                >
                  <b>{chat.sender_nickname}</b>
                  <span>{chat.content}</span>
                </div>
              );
            })
          ) : (
            <div className={styles.emptyChat}>아직 메시지가 없어요. 첫 인사를 남겨보세요.</div>
          )}
        </div>
        <div className={styles.sheetForm}>
          <label htmlFor="chat-sheet-nickname">닉네임</label>
          <input
            id="chat-sheet-nickname"
            maxLength={20}
            onChange={(event) => setNickname(event.target.value)}
            value={nickname}
          />
          <label htmlFor="chat-sheet-message">메시지</label>
          <textarea
            id="chat-sheet-message"
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
        {error ? (
          <div className={`${styles.resultCard} ${styles.error}`}>
            <b>{error.title}</b>
            <span>{error.body}</span>
          </div>
        ) : null}
      </section>
    </div>
  );
}
