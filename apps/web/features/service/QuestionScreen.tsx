"use client";

import { useState } from "react";
import { CheckCircle2, Info, Search, SendHorizonal, ShieldAlert, ShieldCheck, ShieldQuestion } from "lucide-react";
import { askRag, type RagAnswer } from "@/lib/api";
import { MobileShell } from "@/features/common/MobileShell";
import { JejuMapPreview } from "@/features/map/JejuMapPreview";
import {
  JEJU_NATIONAL_UNIVERSITY_CENTER,
  JEJU_NATIONAL_UNIVERSITY_LANDMARKS,
  JEJU_NATIONAL_UNIVERSITY_ZOOM_LEVEL,
} from "@/features/map/jejuNationalUniversity";
import styles from "./ServicePages.module.css";

const suggestions = ["함덕 맛집", "제주공항 택시팟", "비 오는 코스", "혼자 가기 좋은 카페"];
/** 질문 전 빈 공간을 채우기에 알맞은 지도 높이. */
const CAMPUS_MAP_HEIGHT_PX = 320;
const PROFILE_STORAGE_KEY = "jejumate.localProfile";

type LocalProfile = {
  profileId: string;
  nickname: string;
  anonymousId: string;
};

const CONFIDENCE_LABEL: Record<RagAnswer["confidence_grade"], string> = {
  high: "근거와 모두 일치",
  medium: "근거와 일부 일치",
  low: "근거와 불일치 감지",
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
      setError("답변을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <MobileShell active="question" title="질문" subtitle="제주 파티, 장소를 근거와 함께 확인해요">
      <section className={styles.questionBox}>
        <div className={styles.ragSearch}>
          <Search size={18} />
          <input
            id="rag-page-question"
            maxLength={120}
            onChange={(event) => setQuestion(event.target.value)}
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
        <div className={styles.suggestions}>
          {suggestions.map((suggestion) => (
            <button className={styles.chip} key={suggestion} onClick={() => setQuestion(suggestion)} type="button">
              {suggestion}
            </button>
          ))}
        </div>
      </section>

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
                    {source.supports_answer === false ? "⚠ " : ""}
                    {source.title}
                  </a>
                ))}
              </div>
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
