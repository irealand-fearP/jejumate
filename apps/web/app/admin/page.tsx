"use client";

import { useState } from "react";
import { HostApprovalList } from "@/features/common/HostApprovalList";
import { useHostApplications } from "@/features/common/useHostApplications";
import styles from "./admin.module.css";

// 코덱스 원본 admin 페이지(전역 조회, 인증 없음)를 참고했지만, 우리 API 규약대로
// 이 기기에 저장된 관리 코드(owner_secret)를 가진 모임만 조회/승인/거절한다
// (jejumate/backend와 동일하게 로그인 없는 관리 코드 인증 유지).
//
// 조회·승인·거절 로직과 목록 UI는 호스트 승인 시트(HostApprovalSheet)와 공유한다 —
// 이 페이지는 직접 URL로 들어오는 진입점이고, 평소에는 배너 -> 시트로 처리한다.

export default function AdminPage() {
  const { groups, ownedCount, loading, error, busyApplicationId, decide } = useHostApplications();
  const [filter, setFilter] = useState<"pending" | "all">("pending");

  const visibleGroups =
    filter === "all"
      ? groups
      : groups
          .map((group) => ({
            ...group,
            applications: group.applications.filter((application) => application.status === "pending"),
          }))
          .filter((group) => group.applications.length > 0);

  return (
    <main className={styles.page}>
      <header className={styles.header}>
        <div>
          <p className={styles.eyebrow}>Host Console</p>
          <h1 className={styles.title}>파티 신청함</h1>
        </div>
        <div className={styles.segment}>
          <button
            className={filter === "pending" ? styles.segmentActive : styles.segmentButton}
            onClick={() => setFilter("pending")}
            type="button"
          >
            대기
          </button>
          <button
            className={filter === "all" ? styles.segmentActive : styles.segmentButton}
            onClick={() => setFilter("all")}
            type="button"
          >
            전체
          </button>
        </div>
      </header>

      {error ? <div className={styles.notice}>{error}</div> : null}
      {!error && !loading && ownedCount === 0 ? (
        <div className={styles.notice}>
          이 기기에서 등록한 파티가 없어요. 파티 화면에서 &quot;+ 파티 만들기&quot;로 등록하면 여기서 관리할 수 있어요.
        </div>
      ) : null}

      <section className={styles.list}>
        {loading ? (
          <div className={styles.empty}>불러오는 중...</div>
        ) : (
          <HostApprovalList
            busyApplicationId={busyApplicationId}
            emptyMessage="표시할 신청이 없습니다."
            groups={visibleGroups}
            onDecide={decide}
          />
        )}
      </section>
    </main>
  );
}
