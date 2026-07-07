"use client";

import { useEffect, useState } from "react";
import { Eye, EyeOff, ShieldCheck, UserRound } from "lucide-react";
import { createNickname, type ProfilePreviewData } from "@/lib/api";
import { MobileShell } from "@/features/common/MobileShell";
import styles from "./ServicePages.module.css";

type LocalProfile = {
  profileId: string;
  nickname: string;
  anonymousId: string;
};

const PROFILE_STORAGE_KEY = "jejumate.localProfile";

export function ProfileScreen({ data }: { data: ProfilePreviewData }) {
  const [profile, setProfile] = useState<LocalProfile | null>(null);
  const [nickname, setNickname] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<string | null>(null);

  useEffect(() => {
    const raw = window.localStorage.getItem(PROFILE_STORAGE_KEY);
    if (!raw) return;

    try {
      const parsed = JSON.parse(raw) as LocalProfile;
      setProfile(parsed);
      setNickname(parsed.nickname);
    } catch {
      window.localStorage.removeItem(PROFILE_STORAGE_KEY);
    }
  }, []);

  async function save() {
    if (nickname.trim().length < 2) return;
    setBusy(true);
    setResult(null);

    try {
      const created = await createNickname(nickname.trim(), profile?.anonymousId);
      const nextProfile = {
        profileId: created.profile_id,
        nickname: created.nickname,
        anonymousId: created.anonymous_id,
      };
      window.localStorage.setItem(PROFILE_STORAGE_KEY, JSON.stringify(nextProfile));
      setProfile(nextProfile);
      setResult("닉네임이 저장됐습니다. 공개 프로필에는 닉네임만 표시됩니다.");
    } catch {
      setResult("닉네임을 저장하지 못했습니다. 잠시 후 다시 시도해 주세요.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <MobileShell active="profile" title="내정보" subtitle="공개 정보와 비공개 정보를 분리해 관리해요">
      <section className={styles.profileCard}>
        <div className={styles.profileHero}>
          <div className={styles.avatar}>
            <UserRound size={24} />
          </div>
          <div>
            <h2>{profile ? profile.nickname : "닉네임 없음"}</h2>
            <p className={styles.meta}>{profile ? profile.anonymousId : "실명 없이 닉네임부터 만들 수 있습니다."}</p>
          </div>
        </div>
        <label className={styles.label} htmlFor="profile-nickname">
          공개 닉네임
        </label>
        <input
          className={styles.input}
          id="profile-nickname"
          maxLength={20}
          onChange={(event) => setNickname(event.target.value)}
          placeholder="예: 바당이"
          value={nickname}
        />
        <button className={styles.primaryButton} disabled={busy || nickname.trim().length < 2} onClick={save} type="button">
          {busy ? "저장 중" : "닉네임 저장"}
        </button>
        {result ? <div className={styles.result}>{result}</div> : null}
      </section>

      <section className={styles.profileGrid}>
        <div className={styles.profileCard}>
          <h2>
            <Eye size={17} /> 공개되는 정보
          </h2>
          <ul>
            {data.public_fields.map((field) => (
              <li key={field}>{field}</li>
            ))}
          </ul>
        </div>
        <div className={styles.profileCard}>
          <h2>
            <EyeOff size={17} /> 공개되지 않는 정보
          </h2>
          <ul>
            {data.hidden_fields.map((field) => (
              <li key={field}>{field}</li>
            ))}
          </ul>
        </div>
        <div className={styles.profileCard}>
          <h2>
            <ShieldCheck size={17} /> 안전 기준
          </h2>
          <ul>
            {data.safety_notes.map((note) => (
              <li key={note}>{note}</li>
            ))}
          </ul>
        </div>
      </section>
    </MobileShell>
  );
}
