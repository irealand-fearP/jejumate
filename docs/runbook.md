# 제주메이트 로컬 개발 Runbook

## 1. 인프라 실행

```bash
cd infra
docker compose up -d
```

초기 DB 스키마 적용:

```bash
docker exec -i jejumate-postgres psql -U jejumate -d jejumate < ../services/api/migrations/001_initial_mvp.sql
docker exec -i jejumate-postgres psql -U jejumate -d jejumate < ../services/api/migrations/002_seed_realistic_mvp_data.sql
```

이미 적용된 DB인지 확인:

```bash
docker exec jejumate-postgres psql -U jejumate -d jejumate -tAc "select to_regclass('public.users');"
```

## 2. API 실행

```bash
cd services/api
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

확인:

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/api/home
```

현재 서비스 QA 포트로 실행할 때:

```bash
cd services/api
uvicorn app.main:app --reload --host 127.0.0.1 --port 8123
```

## 3. Web 실행

```bash
cd apps/web
npm install
npm run dev
```

확인:

```bash
open http://127.0.0.1:3000
```

현재 서비스 QA 포트로 실행할 때:

```bash
npm run dev -- --port 3124
```

Windows PowerShell에서는 API 주소를 먼저 지정한다.

```powershell
$env:NEXT_PUBLIC_API_BASE_URL="http://127.0.0.1:8123"
npm run dev -- --port 3124
```

잠금 시안 프로토타입은 `http://127.0.0.1:5173/`에서 별도로 유지한다. 서비스 구현 QA는 `http://127.0.0.1:3124/`에서 진행한다.

## 4. 영속화 확인

API는 로컬 개발 환경에서 `services/api/.data/jejumate.sqlite3` 파일 DB를 자동 생성하고, 실제 서비스처럼 보이는 모임/정책/RAG 문서를 시드한다. Postgres가 연결된 환경에서는 위 마이그레이션과 시드 SQL을 적용한다.

닉네임 생성, 모임 신청, RAG 질문 로그 응답의 `persisted`가 `true`이면 DB 저장까지 완료된 상태다.

```bash
curl -X POST http://127.0.0.1:8123/api/onboarding/nickname \
  -H "Content-Type: application/json" \
  -d '{"nickname":"바당이"}'

curl -X POST http://127.0.0.1:8123/api/meetings/meeting_lunch_hamdeok/applications \
  -H "Content-Type: application/json" \
  -d '{"nickname":"바당이","anonymous_id":"anon_test_local","message":"참여하고 싶어요"}'

curl -X POST http://127.0.0.1:8123/api/rag/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"오늘 신청 가능한 청년정책 알려줘","anonymous_id":"anon_test_local"}'
```

## 5. 개인정보 규칙

- 실명, 전화번호 원문, 생년월일은 저장하지 않는다.
- 공개 API 응답에는 phone_hash, provider id, invite_code_hash, report detail을 포함하지 않는다.
- 인증 정보는 상대 사용자에게 공개하지 않는다.
