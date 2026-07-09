"use client";

import { useEffect, useRef, useState } from "react";
import {
  CheckCircle2,
  Info,
  Maximize2,
  MessageCircleQuestion,
  Search,
  SendHorizonal,
  ShieldAlert,
  ShieldCheck,
  ShieldQuestion,
  Sparkles,
  X,
} from "lucide-react";
import { askRag, type RagAnswer } from "@/lib/api";
import { MobileShell } from "@/features/common/MobileShell";
import styles from "./ServicePages.module.css";

const suggestions = [
  "오늘 제주공항에서 같이 이동할 사람 있어?",
  "함덕 근처 점심 파티 찾아줘",
  "비 오는 날 갈 만한 코스 있어?",
  "오픈채팅에서 나온 최신 질문 알려줘",
];

const quickTopics = ["동행", "맛집", "코스", "생활질문"];
/** 질문 전 빈 공간을 채우기에 알맞은 지도 높이. */
const CAMPUS_MAP_HEIGHT_PX = 320;
const PROFILE_STORAGE_KEY = "jejumate.localProfile";

/** 실제로 스크롤되는 조상을 찾는다.
 *  body는 globals.css에서 이미 overflow:hidden이라 잠가도 소용없고,
 *  진짜 스크롤러는 MobileShell의 .phone이다. */
function findScrollableParent(element: HTMLElement | null): HTMLElement | null {
  let node = element?.parentElement ?? null;
  while (node) {
    const overflowY = window.getComputedStyle(node).overflowY;
    if (overflowY === "auto" || overflowY === "scroll") return node;
    node = node.parentElement;
  }
  return null;
}

type LocalProfile = {
  profileId: string;
  nickname: string;
  anonymousId: string;
};

const CONFIDENCE_LABEL: Record<RagAnswer["confidence_grade"], string> = {
  high: "근거가 잘 맞아요",
  medium: "일부 근거가 맞아요",
  low: "근거 연결이 약해요",
  none: "근거 없음",
};

function confidenceIcon(grade: RagAnswer["confidence_grade"]) {
  if (grade === "high") return <ShieldCheck size={14} />;
  if (grade === "medium") return <ShieldQuestion size={14} />;
  if (grade === "low") return <ShieldAlert size={14} />;
  return null;
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
  const [question, setQuestion] = useState(suggestions[0]);
  const [profile] = useState<LocalProfile | null>(() => readProfile());
  const [answer, setAnswer] = useState<RagAnswer | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [mapFullscreen, setMapFullscreen] = useState(false);
  const mapSectionRef = useRef<HTMLElement>(null);
  const mapToggleRef = useRef<HTMLButtonElement>(null);

  // 전체화면 동안: 뒤쪽 스크롤을 잠그고, ESC로 닫을 수 있게 한다.
  useEffect(() => {
    if (!mapFullscreen) return;

    const scroller = findScrollableParent(mapSectionRef.current);
    const previousOverflow = scroller?.style.overflow ?? "";
    if (scroller) scroller.style.overflow = "hidden";

    // 지도(iframe) 안을 터치하면 포커스가 iframe으로 넘어가 ESC가 부모까지 오지 않는다.
    // 그래서 진입 직후 닫기 버튼에 포커스를 준다. (닫기 버튼은 항상 보이므로 대체 수단은 있다)
    mapToggleRef.current?.focus();

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") setMapFullscreen(false);
    }
    document.addEventListener("keydown", handleKeyDown);

    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      if (scroller) scroller.style.overflow = previousOverflow;
    };
  }, [mapFullscreen]);

  async function submit() {
    if (question.trim().length < 2) return;
    setBusy(true);
    setError(null);

    try {
      setAnswer(await askRag(question.trim(), profile?.anonymousId));
    } catch {
      setError("답변을 불러오지 못했어요. 잠시 후 다시 시도해주세요.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <MobileShell active="question" title="질문" subtitle="오픈채팅과 서비스 데이터를 근거로 제주 정보를 찾아요">
      <section className={styles.askHero}>
        <div className={styles.askHeroIcon}>
          <MessageCircleQuestion size={24} />
        </div>
        <div>
          <span>JejuMate AI</span>
          <h2>지금 제주에서 통하는 답을 찾아드려요</h2>
          <p>동행, 이동, 맛집, 생활 질문을 실제 수집 글과 서비스 근거로 확인합니다.</p>
        </div>
      </section>

      <section className={styles.questionBox}>
        <div className={styles.ragSearch}>
          <Search size={18} />
          <input
            id="rag-page-question"
            maxLength={120}
            onChange={(event) => setQuestion(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") submit();
            }}
            placeholder="예: 오늘 공항에서 애월 가는 택시팟 있어?"
            value={question}
            aria-label="질문"
          />
          <button
            aria-label="질문하기"
            disabled={busy || question.trim().length < 2}
            onClick={submit}
            type="button"
          >
            <SendHorizonal size={17} />
          </button>
        </div>
        <div className={styles.topicRow} aria-label="질문 주제">
          {quickTopics.map((topic) => (
            <span key={topic}>{topic}</span>
          ))}
        </div>
        <div className={styles.suggestions}>
          {suggestions.map((suggestion) => (
            <button className={styles.chip} key={suggestion} onClick={() => setQuestion(suggestion)} type="button">
              {suggestion}
            </button>
          ))}
        </div>
      </section>

      {busy ? (
        <section className={styles.answerLoading}>
          <Sparkles size={16} />
          <span>근거를 찾고 답변을 정리하는 중이에요.</span>
        </section>
      ) : null}

      {error ? <div className={styles.result}>{error}</div> : null}

      {/* 답변이 생기면 높이가 0에서 자연스럽게 펼쳐지고, 아래 지도가 그만큼 부드럽게 밀려난다.
          (지도는 조건부가 아니라 항상 같은 자리에 렌더링되므로 다시 마운트되지 않는다) */}
      <div className={`${styles.answerReveal} ${answer ? styles.answerRevealOpen : ""}`}>
        <div className={styles.answerRevealInner}>
          {answer ? (
            <section className={styles.answer}>
              <div className={styles.answerStatus}>
                <CheckCircle2 size={16} />
                <span>{answer.persisted ? "질문 로그 저장됨" : "답변 생성 완료"}</span>
              </div>
              <strong>{answer.answer}</strong>
              {answer.confidence_grade !== "none" ? (
                <div className={`${styles.confidenceBadge} ${styles[`confidence-${answer.confidence_grade}`]}`}>
                  {confidenceIcon(answer.confidence_grade)}
                  <span>
                    {CONFIDENCE_LABEL[answer.confidence_grade]} (근거 {answer.total_source_count}건 중{" "}
                    {answer.verified_source_count}건 일치)
                  </span>
                </div>
              ) : null}
              {answer.answer_source === "general_knowledge" ? (
                <div className={styles.generalKnowledgeBadge}>
                  <Info size={14} />
                  <span>커뮤니티 근거 없음 · 일반 지식 참고 답변</span>
                </div>
              ) : null}
              <p className={styles.meta}>{answer.safety_note}</p>
              <div className={styles.sources}>
                {answer.sources.map((source) => (
                  <a href={source.url} key={`${source.source_type}-${source.title}`} rel="noreferrer" target="_blank">
                    {source.supports_answer === false ? "검토 필요 · " : ""}
                    {source.title}
                  </a>
                ))}
              </div>
              {answer.suggestions.length ? (
                <div className={styles.followUpRow}>
                  {answer.suggestions.slice(0, 3).map((suggestion) => (
                    <button key={suggestion} onClick={() => setQuestion(suggestion)} type="button">
                      {suggestion}
                    </button>
                  ))}
                </div>
              ) : null}
            </section>
          ) : null}
        </div>
      </div>

      {/* 질문 전에는 아래 빈 공간을 채우고, 답변이 생기면 답변 아래로 밀려난다.
          팀원이 만든 캠퍼스 지도(카카오/V-World 전환)를 정적 HTML 그대로 띄운다.
          배포 도메인이 바뀌어도 따라가도록 절대 IP가 아닌 상대경로를 쓴다. */}
      {/* 전체화면일 때 iframe이 fixed로 흐름에서 빠지므로, 원래 높이만큼 자리를 예약해
          뒤쪽 레이아웃과 스크롤 위치가 튀지 않게 한다. */}
      <section
        className={styles.campusMap}
        ref={mapSectionRef}
        style={mapFullscreen ? { minHeight: CAMPUS_MAP_HEIGHT_PX } : undefined}
      >
        <iframe
          className={
            mapFullscreen ? `${styles.campusMapFrame} ${styles.campusMapFrameFullscreen}` : styles.campusMapFrame
          }
          height={CAMPUS_MAP_HEIGHT_PX}
          src="/campus-map/map_switcher.html"
          title="제주대학교 캠퍼스 지도"
        />
        <button
          aria-label={mapFullscreen ? "지도 전체화면 닫기" : "지도 전체화면으로 보기"}
          aria-pressed={mapFullscreen}
          className={
            mapFullscreen ? `${styles.campusMapToggle} ${styles.campusMapToggleFullscreen}` : styles.campusMapToggle
          }
          onClick={() => setMapFullscreen((previous) => !previous)}
          ref={mapToggleRef}
          type="button"
        >
          {mapFullscreen ? <X size={18} /> : <Maximize2 size={18} />}
        </button>
      </section>
    </MobileShell>
  );
}
