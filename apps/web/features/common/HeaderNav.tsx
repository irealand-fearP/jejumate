"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ClipboardList, MessageCircleQuestion, UserRound, UsersRound } from "lucide-react";
import styles from "./HeaderNav.module.css";

// 상단 헤더 우측에 놓는 한 줄 메뉴(아이콘 위 · 라벨 아래). 홈은 왼쪽 로고 클릭으로 가므로
// 여기엔 홈 항목을 두지 않는다. MobileShell과 HomeScreen 양쪽 헤더에서 공용으로 쓴다.
const NAV_ITEMS = [
  { href: "/meetings", label: "파티", key: "meetings", icon: UsersRound },
  { href: "/question", label: "질문", key: "question", icon: MessageCircleQuestion },
  { href: "/board", label: "생활", key: "board", icon: ClipboardList },
  { href: "/profile", label: "내정보", key: "profile", icon: UserRound },
];

// active를 넘기면 그 값으로(MobileShell 쓰는 화면), 없으면 현재 경로로 활성 항목을 판단한다(홈).
export function HeaderNav({ active }: { active?: string }) {
  const pathname = usePathname();

  return (
    <nav className={styles.nav} aria-label="주요 메뉴">
      {NAV_ITEMS.map((item) => {
        const Icon = item.icon;
        const isActive = active ? active === item.key : pathname === item.href;
        return (
          <Link
            aria-label={item.label}
            aria-current={isActive ? "page" : undefined}
            className={`${styles.item} ${isActive ? styles.active : ""}`}
            href={item.href}
            key={item.key}
          >
            <Icon aria-hidden="true" size={22} strokeWidth={2.3} />
            <span>{item.label}</span>
          </Link>
        );
      })}
    </nav>
  );
}
