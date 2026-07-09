"use client";

import { useState } from "react";
import {
  CheckCircle2,
  Info,
  MessageCircleQuestion,
  Search,
  SendHorizonal,
  ShieldAlert,
  ShieldCheck,
  ShieldQuestion,
  Sparkles,
} from "lucide-react";
import { askRag, type RagAnswer } from "@/lib/api";
import { MobileShell } from "@/features/common/MobileShell";
import { JejuMapPreview } from "@/features/map/JejuMapPreview";
import {
  JEJU_NATIONAL_UNIVERSITY_CENTER,
  JEJU_NATIONAL_UNIVERSITY_LANDMARKS,
  JEJU_NATIONAL_UNIVERSITY_ZOOM_LEVEL,
} from "@/features/map/jejuNationalUniversity";
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
          키가 없거나 SDK 로드에 실패하면 JejuMapPreview가 조용히 아무것도 그리지 않는다. */}
      <section className={styles.campusMap}>
        <JejuMapPreview
          center={JEJU_NATIONAL_UNIVERSITY_CENTER}
          height={CAMPUS_MAP_HEIGHT_PX}
          level={JEJU_NATIONAL_UNIVERSITY_ZOOM_LEVEL}
          places={JEJU_NATIONAL_UNIVERSITY_LANDMARKS}
        />
      </section>
    </MobileShell>
  );
}
