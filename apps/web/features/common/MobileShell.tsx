import Link from "next/link";
import type { ReactNode } from "react";
import { ClipboardList, Home, MessageCircleQuestion, UserRound, UsersRound } from "lucide-react";
import styles from "./MobileShell.module.css";

// 홈을 가운데 두는 5탭 순서: 모임 · 질문 · 홈 · 생활게시판 · 내정보
const navItems = [
  { href: "/meetings", label: "파티", key: "meetings", icon: UsersRound },
  { href: "/question", label: "질문", key: "question", icon: MessageCircleQuestion },
  { href: "/", label: "홈", key: "home", icon: Home },
  { href: "/board", label: "생활", key: "board", icon: ClipboardList },
  { href: "/profile", label: "내정보", key: "profile", icon: UserRound },
];

export function MobileShell({
  active,
  title,
  subtitle,
  children,
}: {
  active: string;
  title: string;
  subtitle?: string;
  children: ReactNode;
}) {
  return (
    <main className={styles.page}>
      <section className={styles.phone}>
        <header className={styles.header}>
          <Link className={styles.brand} href="/">
            제주메이트
          </Link>
          <div>
            <h1>{title}</h1>
            {subtitle ? <p>{subtitle}</p> : null}
          </div>
        </header>
        <div className={styles.content}>{children}</div>
        <nav className={styles.nav} aria-label="하단 탭">
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
            <Link className={active === item.key ? styles.active : ""} href={item.href} key={item.key}>
              <Icon aria-hidden="true" size={20} strokeWidth={2.4} />
              <span>{item.label}</span>
            </Link>
            );
          })}
        </nav>
      </section>
    </main>
  );
}
