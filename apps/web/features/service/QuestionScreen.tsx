"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import {
  Bell,
  BrainCircuit,
  ChevronRight,
  FileText,
  Info,
  MapPin,
  MessageCircle,
  SendHorizonal,
  ShieldAlert,
  ShieldCheck,
  ShieldQuestion,
  Sparkles,
} from "lucide-react";
import { askRag, type RagAnswer } from "@/lib/api";
import { MobileShell } from "@/features/common/MobileShell";
import styles from "./QuestionScreen.module.css";

const suggestions = [
  "오늘 제주공항에서 같이 이동할 사람 있어?",
  "함덕 근처 점심 파티 찾아줘",
  "비 오는 날 갈 만한 코스 있어?",
  "오픈채팅에서 나온 최신 질문 알려줘",
];

const PROFILE_STORAGE_KEY = "jejumate.localProfile";
const KAKAO_ROOM_TITLE = "2026 제주대학교 하기 계절학기 학점교류방";

type LocalProfile = {
  profileId: string;
  nickname: string;
  anonymousId: string;
};

type ConversationTurn = {
  id: number;
  question: string;
  askedAt: string;
  answer?: RagAnswer;
  error?: string;
  // 25초 하드 타임아웃 초과로 재시도 UI를 띄운 상태.
  timedOut?: boolean;
};

// 공식질문(장학금·셔틀·휴학 등)은 응답이 7~20초까지 걸릴 수 있다. 이 시간을 넘기면
// 화면이 '다운된' 것처럼 보이지 않게 재시도 UI로 전환한다.
const HARD_TIMEOUT_MS = 25000;

const CONFIDENCE_LABEL: Record<RagAnswer["confidence_grade"], string> = {
  high: "근거가 잘 맞아요",
  medium: "일부 근거가 맞아요",
  low: "근거 연결이 약해요",
  none: "커뮤니티 근거가 없어요",
};

function confidenceIcon(grade: RagAnswer["confidence_grade"]) {
  if (grade === "high") return <ShieldCheck size={18} />;
  if (grade === "medium") return <ShieldQuestion size={18} />;
  if (grade === "low") return <ShieldAlert size={18} />;
  return <Info size={18} />;
}

function sourceLabel(sourceType: string) {
  const normalized = sourceType.toLowerCase();
  if (normalized.includes("jejunu") || normalized.includes("official")) return "제주대 공식";
  if (normalized.includes("kakao")) return "오픈채팅";
  if (normalized.includes("board")) return "생활게시판";
  if (normalized.includes("meeting") || normalized.includes("party")) return "파티";
  return "참고자료";
}

function sourceTitle(sourceType: string, title: string) {
  return sourceLabel(sourceType) === "오픈채팅" ? KAKAO_ROOM_TITLE : title;
}

function AnswerLocationMap({ location }: { location: NonNullable<RagAnswer["map_location"]> }) {
  const kakaoMapUrl = `https://map.kakao.com/link/map/${encodeURIComponent(location.title)},${location.lat},${location.lng}`;
  const latitudePadding = 0.0022;
  const longitudePadding = 0.0032;
  const boundingBox = [
    location.lng - longitudePadding,
    location.lat - latitudePadding,
    location.lng + longitudePadding,
    location.lat + latitudePadding,
  ].join(",");
  const osmMapUrl = `https://www.openstreetmap.org/export/embed.html?bbox=${encodeURIComponent(boundingBox)}&layer=mapnik&marker=${encodeURIComponent(`${location.lat},${location.lng}`)}`;

  return (
    <section className={styles.answerMap}>
      <div className={styles.answerMapHeader}>
        <span>
          <MapPin size={15} />
          {location.title}
        </span>
        <a href={kakaoMapUrl} rel="noreferrer" target="_blank">
          큰 지도 보기
          <ChevronRight size={14} />
        </a>
      </div>
      <iframe
        className={styles.answerMapFrame}
        loading="lazy"
        referrerPolicy="no-referrer"
        src={osmMapUrl}
        title={`${location.title} 위치 지도`}
      />
      {location.description ? <p>{location.description}</p> : null}
    </section>
  );
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

export function QuestionScreen() {
  const [question, setQuestion] = useState("");
  const [profile] = useState<LocalProfile | null>(() => readProfile());
  const [turns, setTurns] = useState<ConversationTurn[]>([]);
  const [busy, setBusy] = useState(false);
  const nextTurnId = useRef(1);
  const conversationEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    conversationEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [turns, busy]);

  async function submit(nextQuestion = question) {
    const trimmedQuestion = nextQuestion.trim();
    if (busy || trimmedQuestion.length < 2) return;

    const id = nextTurnId.current;
    nextTurnId.current += 1;
    const askedAt = new Intl.DateTimeFormat("ko-KR", {
      hour: "numeric",
      minute: "2-digit",
    }).format(new Date());

    setQuestion("");
    setTurns((previous) => [...previous, { id, question: trimmedQuestion, askedAt }]);
    runTurn(id, trimmedQuestion);
  }

  // 실제 RAG 요청 수행. 최초 질문과 '다시 시도'가 같은 로직을 공유하도록 분리했다.
  async function runTurn(id: number, questionText: string) {
    setBusy(true);
    // 재시도일 수 있으니 이 턴의 이전 상태(에러·타임아웃·이전 답변)를 먼저 비운다.
    setTurns((previous) =>
      previous.map((turn) =>
        turn.id === id ? { ...turn, answer: undefined, error: undefined, timedOut: false } : turn,
      ),
    );

    // askRag 규약(취소 인자 없음)은 그대로 두고 화면 표시만 타임아웃으로 끊는다.
    // settled로 '타임아웃'과 '응답 도착' 중 먼저 온 쪽만 반영한다.
    let settled = false;
    const timeoutId = window.setTimeout(() => {
      if (settled) return;
      settled = true;
      setTurns((previous) => previous.map((turn) => (turn.id === id ? { ...turn, timedOut: true } : turn)));
      setBusy(false);
      inputRef.current?.focus();
    }, HARD_TIMEOUT_MS);

    try {
      const answer = await askRag(questionText, profile?.anonymousId);
      if (settled) return; // 이미 타임아웃 처리됨 — 뒤늦게 온 응답은 버린다(재시도로 다시 받게).
      setTurns((previous) => previous.map((turn) => (turn.id === id ? { ...turn, answer } : turn)));
    } catch {
      if (settled) return;
      setTurns((previous) =>
        previous.map((turn) =>
          turn.id === id ? { ...turn, error: "답변을 불러오지 못했어요. 잠시 후 다시 시도해주세요." } : turn,
        ),
      );
    } finally {
      if (!settled) {
        settled = true;
        window.clearTimeout(timeoutId);
        setBusy(false);
        inputRef.current?.focus();
      }
    }
  }

  function chooseSuggestion(suggestion: string) {
    setQuestion(suggestion);
    inputRef.current?.focus();
  }

  const headerAction = (
    <Link aria-label="내 신청 알림" className={styles.notificationLink} href="/meetings?notifications=1">
      <Bell size={21} />
    </Link>
  );

  return (
    <MobileShell active="question" headerAction={headerAction} headerVariant="compact" title="질문">
      <div className={styles.chatPage}>
        <section className={styles.chatIntro}>
          <Sparkles size={19} />
          <p>실시간 커뮤니티 근거로 답해요</p>
        </section>

        {turns.length === 0 ? (
          <section className={styles.emptyState}>
            <div className={styles.emptyIcon}>
              <BrainCircuit size={27} />
            </div>
            <h2>제주에서 지금 궁금한 건?</h2>
            <p>오픈채팅과 시냅스팟에 올라온 최신 글을 찾아 답해드릴게요.</p>
            <div className={styles.starterQuestions}>
              {suggestions.map((suggestion) => (
                <button key={suggestion} onClick={() => chooseSuggestion(suggestion)} type="button">
                  {suggestion}
                  <ChevronRight size={15} />
                </button>
              ))}
            </div>
          </section>
        ) : null}

        <section aria-live="polite" className={styles.conversation}>
          {turns.map((turn) => (
            <article className={styles.turn} key={turn.id}>
              <div className={styles.userMessageRow}>
                <div className={styles.userBubble}>{turn.question}</div>
                <time>{turn.askedAt}</time>
              </div>

              {turn.answer ? (
                <div className={styles.assistantRow}>
                  <div className={styles.assistantAvatar}>
                    <BrainCircuit size={21} />
                  </div>
                  <div className={styles.assistantContent}>
                    <p className={styles.answerText}>{turn.answer.answer}</p>

                    {turn.answer.map_location ? <AnswerLocationMap location={turn.answer.map_location} /> : null}

                    <div
                      className={`${styles.confidence} ${styles[`confidence-${turn.answer.confidence_grade}`]}`}
                    >
                      {confidenceIcon(turn.answer.confidence_grade)}
                      <span>
                        {CONFIDENCE_LABEL[turn.answer.confidence_grade]}
                        {turn.answer.confidence_grade !== "none"
                          ? ` · ${turn.answer.verified_source_count}건 확인`
                          : ""}
                      </span>
                    </div>

                    {turn.answer.sources.length > 0 ? (
                      <div className={styles.sourceList}>
                        {turn.answer.sources.map((source, index) => (
                          <a
                            className={source.supports_answer === false ? styles.sourceNeedsReview : ""}
                            href={source.url}
                            key={`${turn.id}-${source.source_type}-${source.title}-${index}`}
                            rel="noreferrer"
                            target="_blank"
                          >
                            <span className={styles.sourceIcon}>
                              {sourceLabel(source.source_type) === "오픈채팅" ? (
                                <MessageCircle size={19} />
                              ) : (
                                <FileText size={19} />
                              )}
                            </span>
                            <span className={styles.sourceBody}>
                              <small>{sourceLabel(source.source_type)}</small>
                              <strong>{sourceTitle(source.source_type, source.title)}</strong>
                              {source.supports_answer === false ? <em>답변 근거 재확인 필요</em> : null}
                            </span>
                            <ChevronRight size={18} />
                          </a>
                        ))}
                      </div>
                    ) : null}

                    {turn.answer.answer_source === "general_knowledge" ? (
                      <div className={styles.generalKnowledge}>
                        <Info size={15} />
                        <span>커뮤니티 근거가 없어 일반 지식을 참고했어요.</span>
                      </div>
                    ) : null}

                    {turn.answer.safety_note ? <p className={styles.safetyNote}>{turn.answer.safety_note}</p> : null}

                    {turn.answer.suggestions.length > 0 ? (
                      <div className={styles.followUpBlock}>
                        <strong>후속 질문</strong>
                        <div className={styles.followUpRow}>
                          {turn.answer.suggestions.slice(0, 3).map((suggestion) => (
                            <button key={suggestion} onClick={() => chooseSuggestion(suggestion)} type="button">
                              {suggestion}
                              <ChevronRight size={14} />
                            </button>
                          ))}
                        </div>
                      </div>
                    ) : null}
                  </div>
                </div>
              ) : null}

              {/* 타임아웃(지연)이든 요청 실패(throw)든 같은 재시도 UI로 통일 — 어떤 실패도 막다른 길이 없다. */}
              {turn.timedOut || turn.error ? (
                <div className={styles.assistantRow}>
                  <div className={`${styles.assistantAvatar} ${styles.assistantAvatarError}`}>
                    <Info size={20} />
                  </div>
                  <div className={styles.timeoutBlock}>
                    <p>
                      {turn.timedOut
                        ? "답변이 지연되고 있어요. 다시 시도할까요?"
                        : turn.error}
                    </p>
                    <button disabled={busy} onClick={() => runTurn(turn.id, turn.question)} type="button">
                      다시 시도
                    </button>
                  </div>
                </div>
              ) : null}
            </article>
          ))}

          {busy ? (
            <div aria-label="답변 생성 중" className={styles.assistantRow}>
              <div className={styles.assistantAvatar}>
                <BrainCircuit size={21} />
              </div>
              <div className={styles.loadingBubble}>
                <div className={styles.typingIndicator}>
                  <span />
                  <span />
                  <span />
                </div>
                <p className={styles.loadingText}>근거를 찾고 답변을 정리하는 중이에요</p>
              </div>
            </div>
          ) : null}
          <div ref={conversationEndRef} />
        </section>

        <div aria-hidden="true" className={styles.composerSpacer} />
      </div>

      <div className={styles.composerDock}>
        <div className={styles.composer}>
          <textarea
            aria-label="질문 입력"
            disabled={busy}
            maxLength={120}
            onChange={(event) => setQuestion(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                submit();
              }
            }}
            placeholder="메시지를 입력하세요"
            ref={inputRef}
            rows={1}
            value={question}
          />
          <button
            aria-label="질문 보내기"
            disabled={busy || question.trim().length < 2}
            onClick={() => submit()}
            type="button"
          >
            <SendHorizonal size={20} />
          </button>
        </div>
        <p>답변은 커뮤니티 글을 요약하므로 중요한 정보는 원문에서 확인해주세요.</p>
      </div>
    </MobileShell>
  );
}
