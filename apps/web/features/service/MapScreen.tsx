"use client";

import { useState } from "react";
import { MobileShell } from "@/features/common/MobileShell";
import styles from "./MapScreen.module.css";

// 2D/3D 프리뷰는 public/campus-map 아래 같은 오리진 정적 HTML을 iframe으로 띄운다.
const MAP_SOURCES = {
  "2d": { src: "/campus-map/kakao_map_preview.html", title: "제주대 캠퍼스 2D 지도" },
  "3d": { src: "/campus-map/vworld_3d_preview.html", title: "제주대 캠퍼스 3D 지도" },
} as const;

type MapMode = keyof typeof MAP_SOURCES;

export function MapScreen() {
  const [mode, setMode] = useState<MapMode>("2d");
  const active = MAP_SOURCES[mode];

  return (
    <MobileShell active="map" title="지도" subtitle="제주대 캠퍼스를 2D·3D로 둘러봐요">
      <div className={styles.toggle} role="tablist" aria-label="지도 보기 방식">
        <button
          aria-selected={mode === "2d"}
          className={mode === "2d" ? styles.toggleActive : ""}
          onClick={() => setMode("2d")}
          role="tab"
          type="button"
        >
          2D 지도
        </button>
        <button
          aria-selected={mode === "3d"}
          className={mode === "3d" ? styles.toggleActive : ""}
          onClick={() => setMode("3d")}
          role="tab"
          type="button"
        >
          3D 지도
        </button>
      </div>
      {/* key로 모드 전환 시 iframe을 새로 마운트해 확실히 다시 로드한다. */}
      <div className={styles.mapFrameWrap}>
        <iframe key={mode} className={styles.mapFrame} src={active.src} title={active.title} />
      </div>
    </MobileShell>
  );
}
