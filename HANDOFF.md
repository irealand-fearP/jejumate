# jejumate 인수인계

## 완료한 것
- `backend/` FastAPI 프로젝트 스캐폴드(app/config.py, app/db.py, app/models.py) 생성.
- `posts` 테이블 alembic 마이그레이션 `0001_create_posts` 작성: source·post_type(party/info)·category(10종)·capacity·deadline·owner_secret·metadata(jsonb)·embedding(vector 1536) 전 필드 포함, CheckConstraint 4종 + 인덱스(category/post_type/status/embedding ivfflat) 포함.
- `0002_create_applications`는 번호만 선점한 빈 스텁으로 생성(Day 2.5에 내용 작성 예정).
- TDD로 `tests/test_posts_model.py` 12개 케이스(정상 insert/select, party 전용 필드, 임베딩 라운드트립, metadata jsonb, post_type/category/status 제약 위반) 작성 후 전부 통과.
- **Task3**: `app/parser.py`에 `parse_kakao_txt`(노이즈 제거 + 멀티라인 메시지 병합) + `chunk_messages`(같은 화자·5분 이내 연속 발화 병합) 구현. 실제 샘플 파일에서 백스페이스(0x08) 등 제어문자가 낀 닉네임을 발견해 정규화 로직 추가(회귀 테스트 포함). `tests/test_parser.py` 10개 케이스 전부 통과, 실 샘플 파싱 결과 123개 원시 메시지 → 112개 대화 단위로 정상 청킹됨(육안 확인).

## 검증 결과 (+ 한계)
- ~~docker·sudo·psql·podman 전부 없어 로컬 Postgres+pgvector 불가~~ → **해소됨**: 대표가 Docker Desktop WSL 연동을 켠 뒤 `docker run pgvector/pgvector:pg16`으로 실제 컨테이너 기동, `alembic upgrade head`로 0001/0002 실제 적용 성공. 실제 DB에서 확인한 것:
  - 일반 info 글 insert/select, party 글(capacity/owner_secret) insert/select
  - 1536차원 임베딩 벡터 라운드트립(값 손실 없음)
  - `embedding <=> vector` 코사인 거리 연산 + ivfflat 인덱스로 유사도 검색 정상 동작
  - `post_type` CHECK 제약이 실제 DB 레벨에서 잘못된 값을 거부함(`ck_posts_post_type` 위반 에러 확인)
  - 검증 후 테스트 데이터는 TRUNCATE로 정리, 컨테이너(`jejumate-pg`, 포트 55432)는 계속 개발용으로 띄워둔 상태.
  - 이전에 SQLite로 대체했던 pytest 12케이스는 그대로 유효(빠른 단위 테스트용으로 계속 사용).
- frontend(Next.js) 스캐폴드는 아직 생성 전(대표 지시로 Task2 범위를 DDL 검증까지로 한정했던 것이 그대로 이어짐). Task4 이후 여유 있으면 진행.
- **Task4**: `app/rule_filter.py`(키워드 후보 매칭, 미매칭 시 빈 집합=버림) → `app/tagging.py`(post_type/category/status 결정) → `app/embedding.py`(1536차원 벡터) → `app/pipeline.py`(`ingest_kakao_txt`)로 전체 배치 완성. `tests/` 규칙필터 6·태깅 5·임베딩 4·파이프라인 2케이스 전부 통과(총 39개 전체 스위트 통과).
  - **API 키 없음 확인**: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` 둘 다 이 환경에 없음. `AnthropicLLMTagger`/`OpenAIEmbeddingProvider` 실제 호출 코드는 작성했지만 **키가 없어 실제 API 응답으로는 한 번도 검증하지 못했다** — 인터페이스(`LLMTagger`/`EmbeddingProvider` Protocol)를 분리해 `MockLLMTagger`/`MockEmbeddingProvider`로 파이프라인 로직만 검증. **다음 단계: 대표가 두 API 키를 `backend/.env`에 넣어주면(`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`) `AnthropicLLMTagger()`/`OpenAIEmbeddingProvider()`로 교체 후 실제 응답 검증 필요.**
  - Mock 태거로 실제 Postgres(`jejumate-pg` 컨테이너)에 샘플 파일 전체를 적재해 확인: 대화 단위 112개 중 규칙 필터를 통과한 45개가 posts에 실제로 들어갔고(ride 21/run 9/cafe 7/qna 3/walk 2/stay 1/food 1/drink 1), 45개 전부 embedding이 NULL 아님을 실 DB 쿼리로 확인. 검증 후 TRUNCATE로 정리함(현재 posts 테이블은 비어 있음).

## Day 2 진행 (2026-07-07)
- 사전작업: `app/config.py`에 `llm_provider`/`embedding_provider` 설정 추가(기본 mock). `OpenAILLMTagger` 추가(추후 GPT 태깅+OpenAI 임베딩으로 통일 예정이라 기본 실제 구현체로 준비). `get_llm_tagger()`/`get_embedding_provider()` 팩토리로 mock↔실제 전환이 설정값 하나로 가능. **API 키는 아직 없음(내일 발급 예정)**, 오늘은 전부 mock으로 운용.
- **Task7(만료 판정)**: `app/expiry.py`의 `is_expired`/`is_active_post`. SQLite는 `DateTime(timezone=True)`라도 tzinfo를 버리는 걸 발견해(Postgres는 유지) naive UTC로 정규화하는 방식으로 해결. 테스트 8개 통과.
- **Task6(RAG 검색 API)**: `app/search.py`(카테고리 필터→활성 글만→코사인 유사도, Python 레벨 계산 — mock 임베딩 단계라 이식성 우선, 데이터 많아지면 DB단 pgvector 검색으로 전환 필요) + `app/main.py`(FastAPI: `GET /health`, `GET /posts` 피드, `POST /search` RAG, CORS 전체 허용 추가). 실제 uvicorn 기동 + 실 Postgres 대상 curl 스모크 테스트로 확인. 테스트 64개 전체 통과.
- **Task8(Next.js 단일 페이지)**: `frontend/` 생성 완료. 화면흐름.md 기준으로 헤더+RAG 질문창(예시 질문 chip, 근거 보기 토글, 결과 없을 때 "지금 유효한 정보가 없어요")+카테고리 필터 칩(11개, party=오렌지/info=블루 색 구분)+피드(출처뱃지·카테고리뱃지·원문보기) 구현. **파티 등록 버튼/모달·신청·승인 아코디언은 Task9 몫이라 이번 범위에서 제외**(카톡 party 카드는 "읽기전용·지난글" 뱃지로 표시).
  - **중요한 환경 이슈**: 이 개발 셸엔 리눅스용 node/npm이 없고(윈도우 node만 `/mnt/c`에 존재), WSL 경로(`\\wsl.localhost\...`)에서 직접 `npx`/`npm install`을 돌리면 cmd.exe가 UNC 경로를 거부하거나(create-next-app 최초 실패) 매우 느려서(설치 2분 타임아웃) 사실상 못 씀. **해결책**: 윈도우 네이티브 경로(`C:\Users\...\AppData\Local\Temp\jejumate-build\frontend`)에서 스캐폴드/`next build`/`next dev`를 실행하고, 실제 소스는 `rsync`로 `jejumate/frontend`(git 추적 대상, node_modules 제외)와 동기화하는 방식으로 진행함. **다음에 프론트 작업할 때도 이 방식 그대로 써야 함**(아래 "다음 시작 지점" 참고).
  - 실제 `next build` 성공(TS 에러 없음), `next dev` 기동 후 실제 백엔드(포트 8000, CORS 허용)와 연결해 페이지 HTML 렌더 확인(제목·질문창·카테고리 칩 텍스트 전부 응답에 포함됨). WSL→윈도우 접근은 `localhost`가 아니라 게이트웨이 IP(`ip route show default`)로 해야 닿음(반대 방향인 윈도우→WSL은 `localhost`로 잘 됨).
  - 검증 후 프론트 dev 서버·백엔드 프로세스 모두 종료, posts 테이블 TRUNCATE로 정리함.
  - 참고: 이전에 타임아웃난 `npm install` 시도의 잔재로 `jejumate/frontend/node_modules`가 일부 생겼는데 `.gitignore` 대상이라 커밋엔 안 잡힘(삭제는 보류함).

## 다음 시작 지점
- **Task9(시간 되면)**: 파티 등록 폼(카테고리·정원·마감시간) API+UI, `owner_secret` 발급. 화면흐름.md 5-5(아코디언 신청/승인)·6(글쓰기 모달) 참고. 폴백 규칙(기획서 5장): 지연 시 승인 로직 없이 신청=즉시 참여로 축소 가능하게 승인/카운트 로직을 분리해 구현할 것.
- 프론트 작업 계속할 때: 윈도우 네이티브 경로(`/mnt/c/Users/AI융합원/AppData/Local/Temp/jejumate-build/frontend`, node_modules 설치돼 있음)에서 `rsync`로 `jejumate/frontend` 최신 소스를 동기화한 뒤 그 경로에서 `next dev`/`next build` 실행.
- **선행 필요**: ANTHROPIC_API_KEY / OPENAI_API_KEY 확보 후(내일 예정) `llm_provider`/`embedding_provider` 설정을 "openai"로 바꾸고 실제 응답 검증.
