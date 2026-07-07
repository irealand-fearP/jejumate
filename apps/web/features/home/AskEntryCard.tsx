"use client";

import { Bot, ChevronRight } from "lucide-react";
import styles from "./HomeScreen.module.css";

const SUGGESTIONS = ["질문게시판", "중고거래", "나눔"];

export function AskEntryCard({ onOpen }: { onOpen: () => void }) {
  return (
    <button className={styles.askCard} onClick={onOpen} type="button">
      <span className={styles.botIcon}>
        <Bot size={28} />
      </span>
      <div className={styles.askText}>
        <strong>궁금한 거 바로 물어봐</strong>
        <small>근거 있는 제주 답변 ✨</small>
      </div>
      <div className={styles.askChips}>
        {SUGGESTIONS.map((suggestion) => (
          <span key={suggestion}>{suggestion}</span>
        ))}
      </div>
      <ChevronRight size={23} />
    </button>
  );
}
