# Day 1 인수인계 (Task2까지)

## 완료한 것
- `backend/` FastAPI 프로젝트 스캐폴드(app/config.py, app/db.py, app/models.py) 생성.
- `posts` 테이블 alembic 마이그레이션 `0001_create_posts` 작성: source·post_type(party/info)·category(10종)·capacity·deadline·owner_secret·metadata(jsonb)·embedding(vector 1536) 전 필드 포함, CheckConstraint 4종 + 인덱스(category/post_type/status/embedding ivfflat) 포함.
- `0002_create_applications`는 번호만 선점한 빈 스텁으로 생성(Day 2.5에 내용 작성 예정).
- TDD로 `tests/test_posts_model.py` 12개 케이스(정상 insert/select, party 전용 필드, 임베딩 라운드트립, metadata jsonb, post_type/category/status 제약 위반) 작성 후 전부 통과.

## 검증 결과 (+ 한계)
- 이 개발 셸에는 docker·sudo·psql·podman이 전혀 없어 실제 Postgres+pgvector를 로컬에 띄울 수 없었음. 대신:
  - `pytest`: SQLite 인메모리 DB로 ORM 모델(제약조건 포함) insert/select 검증 — 12 passed.
  - `alembic upgrade head --sql` (오프라인 모드): 0001/0002가 생성할 실제 Postgres DDL을 접속 없이 렌더링해 문법 확인 완료 (CREATE EXTENSION vector, CREATE TABLE posts, 4개 CHECK, ivfflat 인덱스까지 정상 출력됨).
  - **아직 안 된 것**: 진짜 Postgres(+pgvector)에 대한 실제 `alembic upgrade head` 실행 및 insert/select. Supabase 프로젝트 연결정보(DATABASE_URL)나, docker가 있는 환경이 확보되면 `backend/.env`에 DATABASE_URL 채우고 `alembic upgrade head` 한 번 돌려서 확정 필요.
- frontend(Next.js) 스캐폴드는 오늘 범위 밖(대표 지시로 Task2를 DDL 검증까지로 한정)이라 아직 생성 안 함.

## 다음 시작 지점
- **Task3**: `/home/ai/agent-company/data/sample_kakao_chat.txt` 파서 + 대화 단위 청킹(같은 화자·5분 이내 연속 발화 병합, 입장/퇴장/삭제 메시지 노이즈 제거)부터 시작.
- Task3 전에 여유 있으면: 실제 Postgres/Supabase 연결 확보해 0001 마이그레이션 실제 적용 + frontend Next.js 스캐폴드 생성.
