# 제주메이트 로컬 개발 Runbook

WSL(Ubuntu) + Docker Desktop(WSL 연동) + Windows 네이티브 Node 조합 환경 기준.
(코덱스 구현 `jejumate-service/docs/runbook.md` 형식을 참고해 우리 저장소 실제 구성으로 작성)

## 1. DB 컨테이너 실행

Docker Desktop이 켜져 있고 WSL 연동이 활성화돼 있어야 한다.

```bash
docker run -d --name jejumate-pg -p 55432:5432 \
  -e POSTGRES_PASSWORD=postgres \
  pgvector/pgvector:pg16
```

이미 떠 있는지 확인:

```bash
docker ps --filter name=jejumate-pg
```

마이그레이션 적용(최초 1회 또는 스키마 변경 시):

```bash
cd backend
source venv/bin/activate 2>/dev/null  # venv 없으면 시스템 python3 사용
alembic upgrade head
```

## 2. 백엔드 실행 (포트 8000)

`backend/.env`에 `DATABASE_URL`, `OPENAI_API_KEY`가 설정돼 있어야 한다(키는 절대 커밋 금지, `.gitignore` 대상).

```bash
cd backend
set -a; source .env; set +a   # OPENAI_API_KEY 등을 프로세스 환경변수로 반영해야 실제 provider가 동작함
nohup python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 \
  > logs/backend_$(date +%Y%m%d_%H%M%S).log 2>&1 &
```

확인:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/posts
```

**주의**: `.env`를 source하지 않고 백그라운드로 띄우면 `OPENAI_API_KEY`가 프로세스에 전달되지 않아
`/search`, `/posts/party` 등 임베딩을 쓰는 요청이 500 에러를 낸다.

## 3. 프론트엔드 실행 (포트 3000, Windows 네이티브 경로 방식)

이 개발 셸엔 리눅스용 node/npm이 없다(윈도우 node만 `/mnt/c`에 존재). WSL UNC 경로
(`\\wsl.localhost\...`)에서 직접 `next dev`/`npm install`을 돌리면 매우 느리거나 실패하므로,
**소스는 `jejumate/frontend`(git 추적 대상)에서 편집하고, 실행은 Windows 네이티브 경로에 동기화한 뒤 거기서 한다.**

```bash
SRC="/home/ai/agent-company/jejumate/frontend/"
DST="/mnt/c/Users/AI융합원/AppData/Local/Temp/jejumate-build/frontend/"
rsync -av --delete \
  --exclude node_modules --exclude .next --exclude .env.local --exclude .git \
  "$SRC" "$DST"
```

실행은 `%USERPROFILE%` 환경변수로 경로를 지정한다(사용자 폴더명에 한글이 섞여 있어, WSL에서
cmd.exe로 한글 경로를 직접 넘기면 인코딩이 깨져 실패한다 — 반드시 `%USERPROFILE%` 사용):

```bash
cd /mnt/c
nohup cmd.exe /c "cd /d %USERPROFILE%\AppData\Local\Temp\jejumate-build\frontend && npm run dev > next-dev.log 2>&1" </dev/null &
disown
```

`frontend/.env.local`(윈도우 경로에만 존재, git 추적 안 함)에 다음이 설정돼 있어야 한다:

```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

`next build`로 빌드만 확인할 때도 동일하게 윈도우 경로에서 실행한다:

```bash
cmd.exe /c "cd /d %USERPROFILE%\AppData\Local\Temp\jejumate-build\frontend && npm run build"
```

## 4. 접속 확인

| 방향 | 확인 방법 |
|---|---|
| WSL → 백엔드(8000) | `curl http://localhost:8000/health` (같은 머신이라 localhost로 바로 됨) |
| Windows → WSL 백엔드(8000) | `cmd.exe /c "curl http://localhost:8000/health"` (WSL2는 Windows에서 localhost로 접근 가능) |
| WSL → Windows 프론트(3000) | `localhost`로는 안 됨. 게이트웨이 IP로 접근: `curl http://$(ip route show default \| awk '{print $3}'):3000` |
| Windows → 프론트(3000) | 브라우저에서 `http://localhost:3000` |

## 5. 정리(작업 종료 시)

```bash
# 백엔드 종료
pkill -f "uvicorn app.main:app"

# 프론트 종료(Windows 프로세스)
cd /mnt/c && cmd.exe /c "netstat -ano | findstr :3000"   # PID 확인 후
cmd.exe /c "taskkill /PID <PID> /F"

# DB 컨테이너는 시드 데이터 유지를 위해 보통 계속 띄워둔다(중지하려면 docker stop jejumate-pg)
```
