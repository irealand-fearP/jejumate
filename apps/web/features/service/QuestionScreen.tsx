"use client";

import { useState } from "react";
import { CheckCircle2, Search, SendHorizonal } from "lucide-react";
import { askRag, type RagAnswer } from "@/lib/api";
import { MobileShell } from "@/features/common/MobileShell";
import styles from "./ServicePages.module.css";

const suggestions = ["함덕 맛집", "제주공항 택시팟", "비 오는 코스", "혼자 가기 좋은 카페"];
const PROFILE_STORAGE_KEY = "jejumate.localProfile";

type LocalProfile = {
  profileId: string;
  nickname: string;
  anonymousId: string;
};

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
    <MobileShell active="question" title="질문" subtitle="제주 모임, 장소를 근거와 함께 확인해요">
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

      {answer ? (
        <section className={styles.answer}>
          <div className={styles.answerStatus}>
            <CheckCircle2 size={16} />
            <span>{answer.persisted ? "질문 로그 저장됨" : "답변 생성 완료"}</span>
          </div>
          <strong>{answer.answer}</strong>
          <p className={styles.meta}>{answer.safety_note}</p>
          <div className={styles.sources}>
            {answer.sources.map((source) => (
              <a href={source.url} key={`${source.source_type}-${source.title}`} rel="noreferrer" target="_blank">
                {source.title}
              </a>
            ))}
          </div>
        </section>
      ) : null}
    </MobileShell>
  );
}
