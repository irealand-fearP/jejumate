import Link from "next/link";
import type { ReactNode } from "react";
import { HeaderNav } from "./HeaderNav";
import styles from "./MobileShell.module.css";

export function MobileShell({
  active,
  title,
  subtitle,
  children,
  headerAction,
  headerVariant = "default",
}: {
  active: string;
  title: string;
  subtitle?: string;
  children: ReactNode;
  headerAction?: ReactNode;
  headerVariant?: "default" | "compact";
}) {
  return (
    <main className={styles.page}>
      <section className={styles.phone}>
        <header className={`${styles.header} ${headerVariant === "compact" ? styles.headerCompact : ""}`}>
          {/* 윗줄: 왼쪽 로고(클릭 시 홈) + 오른쪽 공통 메뉴 */}
          <div className={styles.headerBar}>
            <Link className={styles.brand} href="/" aria-label="시냅스팟 홈">
              시냅스팟
            </Link>
            <HeaderNav active={active} />
          </div>
          {/* 아랫줄: 화면 제목 + (선택) 헤더 액션(예: 질문 화면의 알림 버튼) */}
          <div className={styles.headerTitleRow}>
            <div className={styles.headerTitle}>
              <h1>{title}</h1>
              {subtitle ? <p>{subtitle}</p> : null}
            </div>
            {headerAction ? <div className={styles.headerAction}>{headerAction}</div> : null}
          </div>
        </header>
        <div className={styles.content}>{children}</div>
      </section>
    </main>
  );
}
