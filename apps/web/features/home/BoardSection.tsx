"use client";

import { useRouter } from "next/navigation";
import { ChevronRight, ClipboardList, Search, ShieldCheck } from "lucide-react";
import styles from "./HomeScreen.module.css";

const BOARD_ITEMS = [
  { title: "질문게시판", body: "장소, 영업시간, 맛집을 바로 물어봐요", icon: Search },
  { title: "중고거래", body: "기숙사 생활용품과 책을 사고팔아요", icon: ClipboardList },
  { title: "나눔", body: "버물리, 연고처럼 급한 물품을 나눠요", icon: ShieldCheck },
];

// 코덱스 원본은 별도 /board 페이지로 연결했지만, 이 fork엔 아직 없는 화면이라
// 죽은 링크가 되는 걸 막기 위해 이미 있는 /policies로 연결한다(시각 구성만 이식).
const BOARD_TARGET = "/policies";

export function BoardSection() {
  const router = useRouter();

  return (
    <section className={styles.boardSection}>
      <div className={styles.sectionTitleRow}>
        <h2>생활게시판</h2>
        <button onClick={() => router.push(BOARD_TARGET)} type="button">
          더 보기 <ChevronRight size={18} />
        </button>
      </div>
      <div className={styles.boardList}>
        {BOARD_ITEMS.map((item) => {
          const Icon = item.icon;
          return (
            <button
              className={styles.boardItem}
              key={item.title}
              onClick={() => router.push(BOARD_TARGET)}
              type="button"
            >
              <span>
                <Icon size={22} />
              </span>
              <div>
                <strong>{item.title}</strong>
                <small>{item.body}</small>
              </div>
              <ChevronRight size={20} />
            </button>
          );
        })}
      </div>
    </section>
  );
}
