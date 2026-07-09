"use client";

import type { HostMeetingGroup } from "./useHostApplications";
import styles from "./HostApprovalList.module.css";

const STATUS_LABEL: Record<string, string> = {
  pending: "대기",
  approved: "승인",
  rejected: "거절",
};

type HostApprovalListProps = {
  groups: HostMeetingGroup[];
  busyApplicationId: string | null;
  onDecide: (group: HostMeetingGroup, applicationId: string, action: "approve" | "reject") => void;
  /** 보여줄 신청이 하나도 없을 때 문구(시트와 admin이 다르다). */
  emptyMessage: string;
};

/**
 * 모임별로 묶은 신청 목록 + 승인/거절 버튼. 호스트 승인 시트와 admin 페이지가 함께 쓴다
 * (중복 구현을 없애 한 곳만 고치면 양쪽에 반영된다).
 */
export function HostApprovalList({ groups, busyApplicationId, onDecide, emptyMessage }: HostApprovalListProps) {
  const hasAny = groups.some((group) => group.applications.length > 0);
  if (!hasAny) return <div className={styles.empty}>{emptyMessage}</div>;

  return (
    <div className={styles.groups}>
      {groups.map((group) =>
        group.applications.length === 0 ? null : (
          <section className={styles.group} key={group.meetingId}>
            <h3 className={styles.groupTitle}>{group.meetingTitle}</h3>
            <ul className={styles.list}>
              {group.applications.map((application) => {
                const applicationId = application.application_id;
                const isPending = application.status === "pending";
                const busy = Boolean(applicationId) && busyApplicationId === applicationId;

                return (
                  <li className={styles.item} key={applicationId ?? `${group.meetingId}-${application.nickname}`}>
                    <div className={styles.itemMain}>
                      <div className={styles.itemHead}>
                        <b className={styles.nickname}>{application.nickname}</b>
                        <span className={`${styles.badge} ${styles[application.status ?? "pending"] ?? ""}`}>
                          {STATUS_LABEL[application.status ?? "pending"] ?? application.status}
                        </span>
                      </div>
                      {application.message ? <p className={styles.message}>{application.message}</p> : null}
                    </div>

                    {isPending && applicationId ? (
                      <div className={styles.actions}>
                        <button
                          className={styles.approveButton}
                          disabled={busy}
                          onClick={() => onDecide(group, applicationId, "approve")}
                          type="button"
                        >
                          {busy ? "처리 중" : "승인"}
                        </button>
                        <button
                          className={styles.rejectButton}
                          disabled={busy}
                          onClick={() => onDecide(group, applicationId, "reject")}
                          type="button"
                        >
                          거절
                        </button>
                      </div>
                    ) : null}
                  </li>
                );
              })}
            </ul>
          </section>
        ),
      )}
    </div>
  );
}
