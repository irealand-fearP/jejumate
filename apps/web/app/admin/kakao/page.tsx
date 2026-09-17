"use client";

import { useEffect, useRef, useState } from "react";
import styles from "./kakao.module.css";

// 카톡 PC 대화 .txt를 사장님이 원할 때 직접 올려 RAG에 즉시 반영하는 페이지.
// 자동 스케줄러 대신 수동 업로드 방식이라 별도 인증(업로드 비밀키)이 필요하다.
// 비밀키는 이 브라우저의 localStorage에만 저장하고 코드에는 절대 하드코딩하지 않는다.

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";
const SECRET_STORAGE_KEY = "synapsepot_kakao_upload_secret";

type UploadResult = {
  parsed: number;
  accepted: number;
  duplicates: number;
  indexed: number;
};

type UploadState =
  | { status: "idle" }
  | { status: "uploading" }
  | { status: "success"; result: UploadResult }
  | { status: "error"; message: string };

export default function KakaoUploadPage() {
  const [secret, setSecret] = useState<string | null>(null);
  const [secretInput, setSecretInput] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [uploadState, setUploadState] = useState<UploadState>({ status: "idle" });
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    const saved = window.localStorage.getItem(SECRET_STORAGE_KEY);
    if (saved) {
      setSecret(saved);
    }
  }, []);

  function handleSaveSecret() {
    const trimmed = secretInput.trim();
    if (!trimmed) return;
    window.localStorage.setItem(SECRET_STORAGE_KEY, trimmed);
    setSecret(trimmed);
    setSecretInput("");
  }

  function handleChangeSecret() {
    window.localStorage.removeItem(SECRET_STORAGE_KEY);
    setSecret(null);
    setUploadState({ status: "idle" });
  }

  async function handleUpload() {
    if (!file || !secret) return;
    setUploadState({ status: "uploading" });

    try {
      const formData = new FormData();
      formData.append("file", file);

      const response = await fetch(`${API_BASE_URL}/api/ingest/kakao/upload-file`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${secret}`,
        },
        body: formData,
      });

      if (response.status === 403) {
        setUploadState({
          status: "error",
          message: "업로드 비밀키가 올바르지 않아요. 비밀키를 다시 확인해 주세요.",
        });
        return;
      }

      if (!response.ok) {
        let detail: string | undefined;
        try {
          const body = (await response.json()) as { detail?: string };
          detail = body?.detail;
        } catch {
          // 에러 바디가 JSON이 아니면 기본 메시지를 쓴다.
        }
        setUploadState({
          status: "error",
          message: detail ?? `업로드에 실패했어요 (${response.status})`,
        });
        return;
      }

      const body = (await response.json()) as { data: UploadResult };
      setUploadState({ status: "success", result: body.data });
      setFile(null);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    } catch {
      setUploadState({
        status: "error",
        message: "업로드에 실패했어요. 네트워크 상태를 확인한 뒤 다시 시도해 주세요.",
      });
    }
  }

  return (
    <main className={styles.page}>
      <header className={styles.header}>
        <p className={styles.eyebrow}>Admin</p>
        <h1 className={styles.title}>카톡 대화 업로드</h1>
        <p className={styles.subtitle}>
          카카오톡 PC에서 내보낸 대화 .txt 파일을 올리면 즉시 파싱해 RAG에 반영합니다. 자동
          수집 없이 원할 때만 직접 반영하는 방식입니다.
        </p>
      </header>

      {!secret ? (
        <section className={styles.card}>
          <label className={styles.label} htmlFor="kakao-upload-secret">
            업로드 비밀키
          </label>
          <input
            id="kakao-upload-secret"
            className={styles.input}
            type="password"
            value={secretInput}
            onChange={(event) => setSecretInput(event.target.value)}
            placeholder="비밀키를 입력하세요"
          />
          <button className={styles.primaryButton} type="button" onClick={handleSaveSecret}>
            저장
          </button>
        </section>
      ) : (
        <section className={styles.card}>
          <div className={styles.label}>대화 파일(.txt)</div>
          <div className={styles.fileRow}>
            <input
              ref={fileInputRef}
              type="file"
              accept=".txt"
              onChange={(event) => setFile(event.target.files?.[0] ?? null)}
            />
          </div>
          {file ? <div className={styles.fileName}>선택된 파일: {file.name}</div> : null}

          <button
            className={styles.primaryButton}
            type="button"
            disabled={!file || uploadState.status === "uploading"}
            onClick={handleUpload}
          >
            {uploadState.status === "uploading" ? "업로드 중..." : "업로드"}
          </button>

          <button className={styles.linkButton} type="button" onClick={handleChangeSecret}>
            비밀키 변경
          </button>
        </section>
      )}

      {uploadState.status === "success" ? (
        <div className={styles.notice}>
          {uploadState.result.indexed}건 반영됨 · {uploadState.result.duplicates}건 중복
          {uploadState.result.parsed > 0 ? ` (총 ${uploadState.result.parsed}건 파싱)` : ""}
        </div>
      ) : null}

      {uploadState.status === "error" ? (
        <div className={styles.errorNotice}>{uploadState.message}</div>
      ) : null}
    </main>
  );
}
