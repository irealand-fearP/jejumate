"use client";

import Link from "next/link";
import { ChevronRight, ClipboardList, Search, ShieldCheck } from "lucide-react";
import styles from "./HomeScreen.module.css";

const BOARD_ITEMS = [
  { title: "질문게시판", body: "장소, 영업시간, 맛집을 바로 물어봐요", icon: Search },
  { title: "중고거래", body: "기숙사 생활용품과 책을 사고팔아요", icon: ClipboardList },
  { title: "나눔", body: "버물리, 연고처럼 급한 물품을 나눠요", icon: ShieldCheck },
];

const BOARD_TARGET = "/board";

export function BoardSection() {
  return (
    <section className={styles.boardSection}>
      <div className={styles.sectionTitleRow}>
        <h2>생활게시판</h2>
        <Link href={BOARD_TARGET}>
          더 보기 <ChevronRight size={18} />
        </Link>
      </div>
      <div className={styles.boardList}>
        {BOARD_ITEMS.map((item) => {
          const Icon = item.icon;
          return (
            <Link
              className={styles.boardItem}
              href={BOARD_TARGET}
              key={item.title}
            >
              <span>
                <Icon size={22} />
              </span>
              <div>
                <strong>{item.title}</strong>
                <small>{item.body}</small>
              </div>
              <ChevronRight size={20} />
            </Link>
          );
        })}
      </div>
    </section>
  );
}
