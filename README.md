# 제주메이트 서비스

제주 런케이션 청년을 위한 RAG 기반 로컬 소셜 웹앱.

## 현재 단계

상용 MVP 개발 스캐폴딩.

포함:
- FastAPI API 서버
- Next.js 모바일 웹앱
- PostgreSQL + pgvector 마이그레이션 초안
- Redis/worker 확장 준비
- 홈 API mock
- seed fixture

## 로컬 실행

### API

```bash
cd services/api
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### Web

```bash
cd apps/web
npm install
npm run dev
```

기본 URL:
- Web: http://127.0.0.1:3000
- API: http://127.0.0.1:8000

## MVP 제외

- 실시간 GPS 매칭
- 데이팅 전용 매칭
- 결제
- 1:1 채팅 전체 기능
- 카카오톡 자동수집
- 사진 기반 추억 카드
- 모임 후기
- 나만의 제주 지도
