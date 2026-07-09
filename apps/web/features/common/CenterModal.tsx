"use client";

import styles from "./CenterModal.module.css";

type CenterModalProps = {
  title: string;
  description: string;
  /** 확인 버튼 문구. 기본 '확인'. */
  confirmLabel?: string;
  /** 넘기면 '취소' 버튼이 함께 나온다(확인 다이얼로그). 없으면 확인 버튼 하나만. */
  cancelLabel?: string;
  /** 파티 해산처럼 되돌릴 수 없는 동작이면 확인 버튼을 경고색으로 보여준다. */
  destructive?: boolean;
  busy?: boolean;
  /** 배경 클릭·취소 버튼으로 닫을 때. */
  onClose: () => void;
  /** 확인 버튼을 눌렀을 때. 없으면 그냥 닫는다(단순 안내 팝업). */
  onConfirm?: () => void;
};

/**
 * 화면 중앙에 뜨는 공용 모달. 단순 안내(확인 버튼 하나)와 확인 다이얼로그(취소/확인)를
 * 같은 컴포넌트로 처리한다 — 바텀시트(BottomSheet)와 달리 흐름을 끊고 결과를 알릴 때 쓴다.
 */
export function CenterModal({
  title,
  description,
  confirmLabel = "확인",
  cancelLabel,
  destructive = false,
  busy = false,
  onClose,
  onConfirm,
}: CenterModalProps) {
  return (
    <div className={styles.backdrop} onClick={onClose} role="presentation">
      {/* 내용 클릭이 배경으로 전파돼 모달이 닫히지 않도록 막는다. */}
      <div
        aria-modal="true"
        className={styles.modal}
        onClick={(event) => event.stopPropagation()}
        role="dialog"
      >
        <b className={styles.title}>{title}</b>
        <p className={styles.description}>{description}</p>
        <div className={styles.actions}>
          {cancelLabel ? (
            <button className={styles.cancelButton} disabled={busy} onClick={onClose} type="button">
              {cancelLabel}
            </button>
          ) : null}
          <button
            className={destructive ? styles.destructiveButton : styles.confirmButton}
            disabled={busy}
            onClick={onConfirm ?? onClose}
            type="button"
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
