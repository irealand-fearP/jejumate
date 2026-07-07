"use client";

import { useMemo, useState } from "react";
import { ExternalLink, Newspaper } from "lucide-react";
import { MobileShell } from "@/features/common/MobileShell";
import type { PoliciesData } from "@/lib/api";
import styles from "./ServicePages.module.css";

export function PoliciesScreen({ data }: { data: PoliciesData }) {
  const filters = useMemo(() => ["전체", ...Array.from(new Set(data.policies.map((policy) => policy.field)))], [data.policies]);
  const [activeFilter, setActiveFilter] = useState(filters[0] ?? "전체");
  const policies = activeFilter === "전체" ? data.policies : data.policies.filter((policy) => policy.field === activeFilter);

  return (
    <MobileShell active="policies" title="정책" subtitle="공식 링크와 마감일을 같이 확인해요">
      <div className={styles.notice}>{data.source_note}</div>
      <div className={styles.toolbar}>
        {filters.map((filter) => (
          <button
            className={`${styles.chip} ${activeFilter === filter ? styles.chipActive : ""}`}
            key={filter}
            onClick={() => setActiveFilter(filter)}
            type="button"
          >
            {filter}
          </button>
        ))}
      </div>
      <section className={styles.policyList}>
        {policies.map((policy) => (
          <article className={styles.policyCard} key={policy.id}>
            <div className={styles.policyMeta}>
              <span>
                <Newspaper size={14} />
                {policy.region} · {policy.field}
              </span>
              <b className={styles.dday}>D-{policy.d_day}</b>
            </div>
            <h2>{policy.title}</h2>
            <p className={styles.meta}>{policy.summary}</p>
            <div className={styles.policyMeta}>
              <span>마감 {policy.application_end_date}</span>
              <a href={policy.official_url} rel="noreferrer" target="_blank">
                공식 확인
                <ExternalLink size={13} />
              </a>
            </div>
          </article>
        ))}
      </section>
    </MobileShell>
  );
}
