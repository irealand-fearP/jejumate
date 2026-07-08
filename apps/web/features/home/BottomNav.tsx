"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ClipboardList, Home, MessageCircleQuestion, UserRound, UsersRound } from "lucide-react";
import styles from "./HomeScreen.module.css";

// MobileShell.tsx의 하단 탭과 동일한 구성·순서(모임/질문/홈/생활게시판/내정보, 홈이 가운데)를
// 유지한다. 홈 화면은 잠금 캔버스 레이아웃이라 MobileShell을 감싸 쓰지 않고 자체 탭바를 쓰지만,
// 라우트/라벨/아이콘은 다른 화면들과 일치시켜 혼동이 없게 한다.
const NAV_ITEMS = [
  { href: "/meetings", label: "파티", icon: UsersRound },
  { href: "/question", label: "질문", icon: MessageCircleQuestion },
  { href: "/", label: "홈", icon: Home },
  { href: "/board", label: "생활", icon: ClipboardList },
  { href: "/profile", label: "내정보", icon: UserRound },
];

export function BottomNav() {
  const pathname = usePathname();

  return (
    <nav className={styles.bottomNav} aria-label="하단 탭">
      {NAV_ITEMS.map((item) => {
        const Icon = item.icon;
        const isActive = pathname === item.href;
        return (
          <Link
            className={isActive ? styles.navActive : ""}
            href={item.href}
            key={item.href}
          >
            <Icon size={23} />
            <span>{item.label}</span>
          </Link>
        );
      })}
    </nav>
  );
}
