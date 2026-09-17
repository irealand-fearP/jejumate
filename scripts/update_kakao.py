#!/usr/bin/env python3
"""
카톡 대화를 시냅스팟에 반영하는 원클릭 스크립트. 업로드 → RAG 색인까지 한 번에 끝낸다.

왜 기존 kakao_export_collector.py를 안 쓰고 이걸 쓰나 (2026-07-21 장애에서 얻은 것):
  - 기존 업로더는 타임아웃 15초 고정이라 서버가 느리면 배치마다 죽는다 → 여기선 120초 + 재시도.
  - 색인(큐 드레인)은 자동 크론이 없어 직접 돌려야 한다 → 업로드에 이어서 여기서 병렬로 처리.
  - 엔드포인트는 /api/ingest/kakao/messages · /process (경로 빼먹으면 405).

사용법:
    python3 update_kakao.py              # 최신 카톡 내보내기 파일 자동 탐색
    python3 update_kakao.py <파일경로>    # 파일 직접 지정
    python3 update_kakao.py --upload-only # 업로드만 (색인 생략)
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

API_DIR = Path(__file__).resolve().parent.parent / "services" / "api"
sys.path.insert(0, str(API_DIR))

BASE = "https://synapsepot-production.up.railway.app"
UPLOAD_URL = f"{BASE}/api/ingest/kakao/messages"
PROCESS_URL = f"{BASE}/api/ingest/kakao/process?max_items=5"
# 서버가 원자적 선점을 하므로 병렬 안전(2026-07-21 검증). 단일 워커 uvicorn이 병목이라 5면 충분.
WORKERS = 5
STATE = Path(os.path.expanduser("~/.local/share/Synapspot/kakao-export-state.json"))

# 서버 스키마가 요청당 messages 최대 20건이라 초과하면 HTTP 422로 죽는다.
BATCH = 10
TIMEOUT = 120

# 카톡 내보내기가 떨어지는 곳 — 둘 다 본다.
EXPORT_DIRS = [
    Path("/mnt/c/Users/USER/Downloads"),
    Path("/mnt/c/Users/USER/Documents/카카오톡 받은 파일"),
]


def get_secret() -> str:
    """업로드 시크릿은 로컬에 없다. Railway에서 조회한다(값은 출력하지 않는다)."""
    if env := os.environ.get("KAKAO_UPLOAD_SECRET"):
        return env
    # railway CLI는 프로젝트에 link된 디렉터리에서 실행해야 한다(scripts/에는 link 정보가 없음).
    out = subprocess.run(
        ["railway", "variables", "--service", "synapsepot", "--json"],
        capture_output=True, text=True, timeout=90, cwd=API_DIR,
    )
    if out.returncode != 0:
        sys.exit("Railway 변수 조회 실패. `railway login` 상태를 확인하세요.")
    secret = json.loads(out.stdout).get("KAKAO_UPLOAD_SECRET")
    if not secret:
        sys.exit("KAKAO_UPLOAD_SECRET이 Railway에 없습니다.")
    return secret


def find_latest_export() -> Path:
    files = [f for d in EXPORT_DIRS if d.is_dir()
             for f in d.glob("KakaoTalk_*_group.txt")]
    if not files:
        sys.exit("카톡 내보내기 파일을 찾지 못했습니다. 카톡에서 대화 내보내기(Ctrl+S) 먼저 하세요.")
    return max(files, key=lambda f: f.stat().st_mtime)


def call(url: str, secret: str, body: bytes = b"") -> dict:
    req = Request(url, data=body, method="POST", headers={
        "Content-Type": "application/json; charset=utf-8",
        "Authorization": f"Bearer {secret}",
    })
    with urlopen(req, timeout=TIMEOUT) as r:
        return json.loads(r.read() or b"{}")


def upload(path: Path, secret: str) -> int:
    from app.services.kakao_export import parse_kakao_export

    state = json.loads(STATE.read_text()) if STATE.exists() else {"uploaded_hashes": []}
    done = set(state["uploaded_hashes"])

    messages = parse_kakao_export(path).messages
    pending = [m for m in messages if m.client_message_hash not in done]
    print(f"[업로드] 파일={path.name} 전체={len(messages)} 신규={len(pending)}", flush=True)
    if not pending:
        print("  신규 없음 — 건너뜀", flush=True)
        return 0

    ok = fail = 0
    for i in range(0, len(pending), BATCH):
        batch = pending[i:i + BATCH]
        payload = json.dumps(
            {"messages": [m.to_api_payload() for m in batch]}, ensure_ascii=False
        ).encode()
        for attempt in range(4):
            try:
                call(UPLOAD_URL, secret, payload)
                done.update(m.client_message_hash for m in batch)
                # 배치마다 저장해야 중간에 끊겨도 진행이 보존된다.
                state["uploaded_hashes"] = sorted(done)
                STATE.parent.mkdir(parents=True, exist_ok=True)
                STATE.write_text(json.dumps(state, ensure_ascii=False))
                ok += len(batch)
                break
            except (HTTPError, URLError, TimeoutError, OSError) as e:
                if attempt == 3:
                    fail += len(batch)
                    print(f"  배치 {i} 실패: {type(e).__name__}", flush=True)
                else:
                    time.sleep(5 * (attempt + 1))
        if (i // BATCH) % 20 == 0 and i:
            print(f"  진행 {ok}/{len(pending)}", flush=True)

    print(f"[업로드] 완료 성공={ok} 실패={fail}", flush=True)
    return ok


def drain(secret: str) -> None:
    """업로드는 큐 적재일 뿐이다. 색인은 pending=0까지 드레인해야 한다.

    서버 dequeue가 FOR UPDATE SKIP LOCKED로 원자적 선점을 하므로(2026-07-21 수정)
    워커를 여러 개 띄워도 같은 행을 중복 처리하지 않는다. 색인은 건당 AI 2회 호출
    (임베딩+분류)이라 느려서, 병렬이 아니면 수천 건에 몇 시간이 걸린다.
    """
    print(f"[색인] 큐 드레인 시작 (워커 {WORKERS}개, 실측 분당 20건 안팎)", flush=True)
    stats = {"ingested": 0, "filtered": 0, "pending": None, "errors": 0}
    lock = threading.Lock()
    stop = threading.Event()

    def worker() -> None:
        idle = 0
        while not stop.is_set():
            try:
                data = (call(PROCESS_URL, secret) or {}).get("data") or {}
            except HTTPError as e:
                with lock:
                    stats["errors"] += 1
                    too_many = stats["errors"] > 30
                if too_many:
                    # 500이면 대개 OpenAI 키 무효 또는 크레딧 소진. 로그로 구분해야 한다.
                    print(f"  HTTP {e.code} 반복 — `railway logs --service synapsepot`으로 확인 "
                          f"(401=키 문제 / insufficient_quota=크레딧 소진)", flush=True)
                    stop.set()
                time.sleep(10)
                continue
            except (URLError, TimeoutError, OSError):
                time.sleep(10)
                continue

            ing, filt = int(data.get("ingested", 0)), int(data.get("filtered", 0))
            with lock:
                stats["ingested"] += ing
                stats["filtered"] += filt
                stats["pending"] = data.get("pending")
            if ing + filt == 0:
                idle += 1
                if idle >= 3:
                    return
            else:
                idle = 0

    threads = [threading.Thread(target=worker, daemon=True) for _ in range(WORKERS)]
    for t in threads:
        t.start()
    while any(t.is_alive() for t in threads):
        time.sleep(30)
        with lock:
            print(f"  적재={stats['ingested']} 필터={stats['filtered']} "
                  f"남음={stats['pending']}", flush=True)
    for t in threads:
        t.join()

    print(f"[색인] 완료 적재={stats['ingested']} 필터={stats['filtered']}", flush=True)


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    upload_only = "--upload-only" in sys.argv

    path = Path(args[0]) if args else find_latest_export()
    if not path.is_file():
        sys.exit(f"파일이 없습니다: {path}")

    secret = get_secret()
    upload(path, secret)
    if upload_only:
        print("--upload-only — 색인은 생략했습니다.")
        return
    drain(secret)
    print("\n✅ 전부 끝났습니다. synapsepot.com에서 검색해보세요.")


if __name__ == "__main__":
    main()
