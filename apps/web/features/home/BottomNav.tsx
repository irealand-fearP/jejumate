"use client";

import { useRouter } from "next/navigation";
import { Home, MessageCircleQuestion, Newspaper, UserRound, UsersRound } from "lucide-react";
import styles from "./HomeScreen.module.css";

// MobileShell.tsx의 하단 탭과 동일한 구성(홈/모임/질문/정책/내정보)을 유지한다.
// 홈 화면은 잠금 캔버스 레이아웃이라 MobileShell을 감싸 쓰지 않고 자체 탭바를 쓰지만,
// 라우트/라벨/아이콘은 다른 화면들과 일치시켜 혼동이 없게 한다.
const NAV_ITEMS = [
  { href: "/", label: "홈", icon: Home, active: true },
  { href: "/meetings", label: "모임", icon: UsersRound },
  { href: "/question", label: "질문", icon: MessageCircleQuestion },
  { href: "/policies", label: "정책", icon: Newspaper },
  { href: "/profile", label: "내정보", icon: UserRound },
];

export function BottomNav() {
  const router = useRouter();

  return (
    <nav className={styles.bottomNav} aria-label="하단 탭">
      {NAV_ITEMS.map((item) => {
        const Icon = item.icon;
        return (
          <button
            className={item.active ? styles.navActive : ""}
            key={item.href}
            onClick={() => router.push(item.href)}
            type="button"
          >
            <Icon size={23} />
            <span>{item.label}</span>
          </button>
        );
      })}
    </nav>
  );
}
