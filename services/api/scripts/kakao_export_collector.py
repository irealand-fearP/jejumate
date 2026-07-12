"""카카오톡 PC 내보내기 파일을 감시해 dm.kggstudio.com에 올리는 로컬 CLI.

기본 실행은 본문을 출력하지 않는 dry-run이다. 실제 업로드는 ``--upload``를
명시해야만 수행한다.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import time


API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.services.kakao_export import (  # noqa: E402
    parse_kakao_export,
    post_chat_messages,
    process_queued_messages,
)


DEFAULT_ENDPOINT = "https://jejumate-api.vercel.app/api/ingest/kakao/messages"
DEFAULT_PROCESS_ENDPOINT = "https://jejumate-api.vercel.app/api/ingest/kakao/process"
DEFAULT_UPLOAD_SECRET_ENV = "KAKAO_UPLOAD_SECRET"


def _default_export_directory() -> Path:
    return Path.home() / "Documents"


def _default_state_file() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    root = Path(local_app_data) if local_app_data else Path.home() / ".local" / "share"
    return root / "Synapspot" / "kakao-export-state.json"


def _load_uploaded_hashes(path: Path) -> set[str]:
    if not path.exists():
        return set()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    return {value for value in payload.get("uploaded_hashes", []) if isinstance(value, str)}


def _save_uploaded_hashes(path: Path, hashes: set[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps({"uploaded_hashes": sorted(hashes)}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary.replace(path)


def _latest_export(directory: Path, pattern: str) -> Path | None:
    candidates = [path for path in directory.glob(pattern) if path.is_file()]
    return max(candidates, key=lambda path: path.stat().st_mtime, default=None)


def run_once(args: argparse.Namespace) -> int:
    export_path = args.file or _latest_export(args.directory, args.pattern)
    if not export_path:
        print("내보내기 파일을 찾지 못했습니다.")
        return 1

    exported = parse_kakao_export(export_path)
    uploaded_hashes = _load_uploaded_hashes(args.state_file)
    pending = [
        message
        for message in exported.messages
        if message.client_message_hash not in uploaded_hashes
    ]

    # 채팅방 이름·작성자·본문은 콘솔과 작업 스케줄러 로그에 남기지 않는다.
    print(
        f"파일={export_path.name} 전체={len(exported.messages)} "
        f"신규={len(pending)} 모드={'upload' if args.upload else 'dry-run'}"
    )
    if not args.upload:
        return 0

    upload_secret = os.environ.get(args.upload_secret_env)
    if not upload_secret:
        print(
            f"업로드 중단: {args.upload_secret_env} 환경변수가 설정되지 않았습니다.",
            file=sys.stderr,
        )
        return 2

    for start in range(0, len(pending), args.batch_size):
        batch = pending[start : start + args.batch_size]
        post_chat_messages(args.endpoint, batch, upload_secret=upload_secret)
        uploaded_hashes.update(message.client_message_hash for message in batch)
        _save_uploaded_hashes(args.state_file, uploaded_hashes)
    if pending:
        print(f"업로드 완료={len(pending)}")

    for _ in range(args.process_cycles):
        response = process_queued_messages(
            args.process_endpoint,
            upload_secret=upload_secret,
            max_items=1,
        )
        data = (response or {}).get("data") or {}
        queue_size = int(data.get("pending", 0))
        print(
            f"큐 처리 적재={int(data.get('ingested', 0))} "
            f"필터={int(data.get('filtered', 0))} 남음={queue_size}"
        )
        if queue_size == 0:
            break
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, help="처리할 내보내기 파일")
    parser.add_argument("--directory", type=Path, default=_default_export_directory())
    parser.add_argument("--pattern", default="KakaoTalk_*_group.txt")
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    parser.add_argument("--process-endpoint", default=DEFAULT_PROCESS_ENDPOINT)
    parser.add_argument(
        "--upload-secret-env",
        default=DEFAULT_UPLOAD_SECRET_ENV,
        help="시냅스팟 업로드 비밀키를 읽을 환경변수 이름",
    )
    parser.add_argument("--state-file", type=Path, default=_default_state_file())
    parser.add_argument("--batch-size", type=int, default=10)
    parser.add_argument("--process-cycles", type=int, default=20)
    parser.add_argument("--upload", action="store_true", help="실제 서버 업로드 수행")
    parser.add_argument("--watch", action="store_true", help="주기적으로 최신 파일 확인")
    parser.add_argument("--interval", type=int, default=600, help="감시 주기(초)")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.batch_size < 1:
        raise SystemExit("--batch-size는 1 이상이어야 합니다.")
    if args.interval < 1:
        raise SystemExit("--interval은 1 이상이어야 합니다.")
    if args.process_cycles < 1:
        raise SystemExit("--process-cycles는 1 이상이어야 합니다.")
    if not args.watch:
        return run_once(args)

    while True:
        try:
            run_once(args)
        except Exception as exc:  # noqa: BLE001 - 장기 감시는 다음 주기에 재시도한다.
            print(f"처리 실패: {type(exc).__name__}", file=sys.stderr)
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
