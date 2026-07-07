# 제주메이트 로컬 실행 메모

## 현재 확인된 실행 포트

- API: `http://127.0.0.1:8124`
- Web: `http://127.0.0.1:3127`

## 실행 명령

API:

```powershell
cd C:\Users\AI융합원\jejumate-work\jejumate-service\services\api
python -m uvicorn app.main:app --host 127.0.0.1 --port 8124
```

Web:

```powershell
cd C:\Users\AI융합원\jejumate-work\jejumate-service\apps\web
npx.cmd next dev --hostname 127.0.0.1 --port 3127
```

## 로컬 환경 설정

`apps/web/.env.local`:

```text
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8124
```

## 확인 완료

- `GET /health` 200
- `GET /api/home` 200
- `POST /api/onboarding/nickname` 200
- `POST /api/rag/ask` 200
- `GET /api/meetings/{meeting_id}/chat/messages` 200
- `POST /api/meetings/{meeting_id}/chat/messages` 200
- Web `/` 200
- Web typecheck 통과

## 추가 구현 메모

- 모임별 미니 채팅 API를 추가했다.
- 연락처/카톡ID/링크 입력은 차단하지 않는다.
- 채팅 화면에는 "연락처 공유는 신중하게 해주세요. 불편한 요청은 신고할 수 있어요." 안내만 표시한다.
- 현재 MVP에서는 승인 여부를 강제하지 않고, 닉네임 기반으로 메시지를 저장한다.

## 참고

압축에 포함된 `.venv`는 다른 PC의 Python 경로를 가리켜 현재 PC에서는 그대로 사용할 수 없다. 현재 환경에서는 시스템 Python에 requirements를 설치해 실행한다.

Postgres가 없거나 `psycopg` binary wrapper가 없어도 MVP 데모는 SQLite local store fallback으로 동작한다.
