"use client";

import { Bot, ChevronRight } from "lucide-react";
import styles from "./HomeScreen.module.css";

const SUGGESTIONS = ["동행", "맛집", "생활질문"];

export function AskEntryCard({ onOpen }: { onOpen: () => void }) {
  return (
    <button className={styles.askCard} onClick={onOpen} type="button">
      <span className={styles.botIcon}>
        <Bot size={28} />
      </span>
      <div className={styles.askText}>
        <strong>제주에서 궁금한 것, 바로 물어봐요</strong>
        <small>오픈채팅과 서비스 글을 근거로 답해드려요</small>
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
