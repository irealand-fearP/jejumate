"use client";

import { useRouter } from "next/navigation";
import { ChevronRight, Newspaper } from "lucide-react";
import type { HomePolicy } from "@/lib/api";
import styles from "./HomeScreen.module.css";

const POLICIES_TARGET = "/policies";
const PREVIEW_COUNT = 3;

export function PolicySection({ policies }: { policies: HomePolicy[] }) {
  const router = useRouter();
  const preview = policies.slice(0, PREVIEW_COUNT);

  if (preview.length === 0) return null;

  return (
    <section className={styles.policySection}>
      <div className={styles.sectionTitleRow}>
        <h2>청년 정책</h2>
        <button onClick={() => router.push(POLICIES_TARGET)} type="button">
          전체 보기 <ChevronRight size={18} />
        </button>
      </div>
      <div className={styles.policyList}>
        {preview.map((policy) => (
          <button
            className={styles.policyItem}
            key={policy.id}
            onClick={() => router.push(POLICIES_TARGET)}
            type="button"
          >
            <span>
              <Newspaper size={20} />
            </span>
            <div>
              <strong>{policy.title}</strong>
              <small>
                {policy.region} · {policy.field} · D-{policy.d_day}
              </small>
            </div>
            <ChevronRight size={20} />
          </button>
        ))}
      </div>
    </section>
  );
}
