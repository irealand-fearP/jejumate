#!/usr/bin/env bash
# 시냅스팟(제주메이트) 로컬 개발환경 기동 스크립트 (WSL/Linux)
# 왜: 새 PC에서 API·웹·DB를 한 번에 띄워 바로 작업하기 위함.
#   - API : http://127.0.0.1:8124  (FastAPI/uvicorn, .venv)
#   - Web : http://127.0.0.1:3128  (Next.js dev)
#   - DB  : Docker Postgres(pgvector)+Redis (infra/docker-compose.yml)
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "[1/3] Docker Postgres+Redis 기동"
(cd "$ROOT/infra" && docker compose up -d)

echo "[2/3] API 기동 (127.0.0.1:8124)"
cd "$ROOT/services/api"
pkill -f 'python -m uvicorn app.main:app' 2>/dev/null || true
nohup .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8124 \
  > /tmp/jejumate-api.log 2>&1 &
echo "  API PID=$!  (로그: /tmp/jejumate-api.log)"

echo "[3/3] Web 기동 (127.0.0.1:3128)"
cd "$ROOT/apps/web"
pkill -f 'next dev' 2>/dev/null || true
nohup npx next dev --hostname 127.0.0.1 --port 3128 \
  > /tmp/jejumate-web.log 2>&1 &
echo "  Web PID=$!  (로그: /tmp/jejumate-web.log)"

sleep 6
echo "---- 상태 ----"
curl -s -m 5 http://127.0.0.1:8124/health -w "  API  /health [%{http_code}]\n" || true
curl -s -m 8 http://127.0.0.1:3128/ -o /dev/null -w "  Web  / [%{http_code}]\n" || true
echo "완료. 코드 수정 후 API 반영은 이 스크립트 재실행 또는 uvicorn 재시작."
