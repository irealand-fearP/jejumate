"use client";

import { X } from "lucide-react";
import { HostApprovalList } from "./HostApprovalList";
import { countPendingApplications, useHostApplications } from "./useHostApplications";
import styles from "./HostApprovalSheet.module.css";

type HostApprovalSheetProps = {
  onClose: () => void;
  /** 승인/거절로 대기 건수가 바뀌었을 때(배너 숫자 갱신용). */
  onChanged?: () => void;
};

/**
 * 호스트가 페이지 이동 없이 대기 신청을 처리하는 바텀시트.
 * 입력 폼이 아니라 목록 + 액션이라 중앙 모달보다 바텀시트가 자연스럽다(채팅 시트와 동일).
 * 목록과 승인/거절 로직은 admin 페이지와 공유한다(HostApprovalList + useHostApplications).
 */
export function HostApprovalSheet({ onClose, onChanged }: HostApprovalSheetProps) {
  const { groups, loading, error, busyApplicationId, decide } = useHostApplications(onChanged);

  // 시트에서는 아직 처리하지 않은(대기) 신청만 보여준다 — 처리하면 목록에서 사라진다.
  const pendingGroups = groups
    .map((group) => ({ ...group, applications: group.applications.filter((a) => a.status === "pending") }))
    .filter((group) => group.applications.length > 0);

  const pendingCount = countPendingApplications(groups);

  return (
    <div className={styles.backdrop} onClick={onClose} role="presentation">
      <section
        aria-modal="true"
        className={styles.sheet}
        onClick={(event) => event.stopPropagation()}
        role="dialog"
      >
        <button aria-label="닫기" className={styles.close} onClick={onClose} type="button">
          <X size={20} />
        </button>
        <div className={styles.grip} />

        <div className={styles.hero}>
          <h2>파티 신청함</h2>
          <p>{loading ? "불러오는 중..." : `대기 중인 신청 ${pendingCount}건`}</p>
        </div>

        {error ? <div className={styles.error}>{error}</div> : null}

        <div className={styles.body}>
          {loading ? (
            <div className={styles.loading}>불러오는 중...</div>
          ) : (
            <HostApprovalList
              busyApplicationId={busyApplicationId}
              emptyMessage="모든 신청을 처리했어요."
              groups={pendingGroups}
              onDecide={decide}
            />
          )}
        </div>

        <div className={styles.actions}>
          <button className={styles.closeButton} onClick={onClose} type="button">
            닫기
          </button>
        </div>
      </section>
    </div>
  );
}
