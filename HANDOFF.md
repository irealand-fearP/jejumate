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

- **Task9(파티 등록 폼, 오늘 완료)**: `POST /posts/party` API — 카테고리는 party 5종(`Literal`)만 허용(422로 거부), 정원 1 이상 검증, 4자리 숫자 관리 코드(`owner_secret`) 발급, **등록 즉시 임베딩까지 생성해 RAG 검색 대상에 바로 포함**(처음엔 빠뜨렸다가 테스트로 잡아서 고침 — `test_created_party_post_is_searchable_via_rag`). 프론트 `PartyRegisterModal`(카테고리 칩·내용·정원·마감시간 30분/1시간/2시간/직접입력·닉네임 → 등록 완료 시 관리 코드 표시+복사+localStorage 저장). "+ 파티 등록하기" 버튼은 화면흐름.md 6장의 1단계 유형선택 없이 파티 폼으로 바로 연결(정보공유 글쓰기 API가 없어 스코프 밖). 신청/승인 아코디언(5-5)은 오늘 범위 밖.
  - 테스트 5개 추가(백엔드 전체 69개 통과), 실 Postgres에 curl로 등록→피드 반영→422 검증까지 스모크 테스트 완료. 프론트는 `next build` 통과 확인(윈도우 네이티브 경로 방식, Task8 방식 그대로).

## Day 2.5 진행
- **Task11(applications 마이그레이션 실적용)**: `app/models.py`에 `Application`(post_id FK·nickname·message(nullable)·status pending/approved/rejected) 추가, `0002_create_applications` 실제 DDL 작성. **주의**: 예전(Day1)에 "번호만 선점"하려고 빈 스텁(`pass`)으로 `alembic upgrade head`를 이미 한 번 돌려서, 실 Postgres의 `alembic_version`이 테이블 없이 `0002_create_applications`로 이미 찍혀 있었음 → `alembic stamp 0001_create_posts`로 버전을 되돌린 뒤 재적용해서 실제 테이블 생성(기존 posts 데이터는 건드리지 않음, 당시 posts는 0건이었음). FK 제약·status CHECK 제약 모두 실 DB에서 위반 시 거부되는 것 확인. 파티 카테고리 값(ride/drink/run/walk/tour)은 Task2부터 이미 posts.category에 포함돼 있어 추가 확장 불필요함을 확인. 테스트 6개 추가(전체 75개 통과).
- **Task12(owner_secret 흐름 확인)**: Task9에서 이미 구현한 **4자리 숫자 관리 코드** 방식을 그대로 유지. **기획서 원문(3장-7)과의 차이**: 기획서 본문은 "owner_secret 발급"이라고만 돼 있어 긴 랜덤 토큰(uuid 등)으로 오해될 수 있으나, 화면흐름.md 6장이 명시적으로 "관리 코드: 4821"(4자리 숫자, 다른 기기에서도 직접 입력 가능해야 함)로 확정했고 이게 더 최신·구체적 지침이라 그 기준을 따름. 보안상 4자리는 브루트포스에 약하지만(1만 가지) 로그인 없는 해커톤 MVP 특성상 UX 우선으로 의도된 결정이라고 판단 — 승인 API(Task14)에도 그대로 적용.

- **Task13(참여 신청 API+UI)**: `POST /posts/{post_id}/applications`(닉네임+메시지, pending 저장). post_type≠party·closed·만료 글은 400으로 거부, 존재하지 않는 글은 404. applications는 embedding 컬럼 자체가 없어 구조적으로 RAG 대상이 될 수 없음을 테스트로도 확인(`test_application_does_not_create_a_searchable_post`). 프론트 `PartyAccordion`에 신청 폼("같이 갈래요" 버튼 + "호스트가 승인해야 약속이 확정돼요" 안내) 포함.
- **Task14(승인/거절+모집현황)**: `GET /posts/{id}/status`(capacity/approved_count/deadline/is_closed, 폴링용), `GET /posts/{id}/applications?owner_secret=`(코드 맞으면 전체 상세, 틀리거나 없으면 닉네임만+authorized:false), `POST .../approve`·`.../reject`(관리 코드 불일치 403, 정원 초과 시 승인 409, 이미 처리된 신청 재승인 400, 거절된 신청은 목록에서 제외). 프론트 `PartyAccordion`이 8초 간격 폴링으로 현황 갱신 + 관리 코드 입력(등록 시 localStorage 자동 저장분 자동 채움) + 승인("같이 가기로 하기")/거절 버튼.
  - **코덱스 제안 반영(대표 채택분)**: 헤더 태그라인 "혼자 가긴 아쉬울 때, 같이 갈 사람 찾기" 추가, 신청/승인 버튼·안내 카피 전부 적용, 모집 현황 "n/capacity명"+잔여 1명 강조("1명 남음")+마감 표기(`formatCapacityStatus`), 파티 등록 폼에 장소 프리셋 칩 9개(제주대/기숙사/제주공항/시청/함덕/김녕/애월/이호테우/서귀포 — 클릭 시 내용 textarea 커서 위치에 삽입). 기각 항목(로그인·바람지수·신뢰지표·알림)은 반영 안 함.
  - 테스트 16개 추가(백엔드 전체 91개 통과). **실 Postgres 검증**: QA가 쓰는 공유 `jejumate-pg`(55432)는 건드리지 않고, 별도 임시 컨테이너(`jejumate-pg-devtest`, 55433)+별도 포트(8099)로 등록→현황(0/1)→신청 2건→코드없이 조회(닉네임만)→승인→현황(1/1)→2번째 승인 시도(409)→RAG 검색(신청 데이터 안 섞임) 전체 흐름 curl로 확인 후 컨테이너·프로세스·`.env` 모두 정리함. 프론트는 `next build` 통과 확인(윈도우 네이티브 경로 방식 동일).
  - **주의(다음 사람 확인 필요)**: 이번 세션 시작 시점엔 QA로 보이는 백엔드(포트 8000, posts 7건)와 `npm run dev` 프로세스가 떠 있었는데, 세션 종료 시점엔 포트 8000 백엔드가 사라져 있었음. 내 작업은 전부 격리된 포트(8099)/컨테이너(`jejumate-pg-devtest`)에서만 이뤄졌고 QA의 `jejumate-pg`(55432)·포트 8000엔 어떤 명령도 실행하지 않았지만, 혹시 모르니 QA에게 확인 요망. `jejumate/QA-REPORT.md`는 QA가 작성 중인 파일로 보여 손대지 않음.

## QA 버그 수정 + 서버 장애 복구 (후속 지시)
- **QA 발견 버그**: `PostCard.tsx`의 카톡 party 카드가 deadline 무관하게 항상 "읽기전용 · 지난글"을 표시하던 문제 수정. `isDeadlinePassed = post.deadline != null && new Date(post.deadline) < now`를 계산해 마감 지난 글에만 "· 지난글"을 덧붙이도록 변경(deadline이 없는 대부분의 카톡 글은 "읽기전용"만 표시). `next build` 통과 확인.
- **백엔드(8000)+시드 데이터 소실 원인 조사**: `docker inspect jejumate-pg` 결과 `RestartCount=0`, `FinishedAt`이 비어 있어 **DB 컨테이너 자체는 세션 내내 한 번도 재시작/중단되지 않음**(원인이 컨테이너 크래시가 아님을 확인). `docker events`에도 내가 실행한 psql/exec 기록만 남아 있고 다른 주체의 `docker exec` 흔적은 없음 — 다만 앱(백엔드 프로세스나 스크립트)이 포트 55432로 직접 접속해 TRUNCATE/DELETE를 실행했다면 이 로그엔 안 잡히므로 **정확한 원인은 특정 못 함**(백엔드 프로세스 자체가 왜 죽었는지도 로그 파일이 없어 확인 불가). 확실한 사실: 컨테이너 하드웨어/재시작 문제는 아니고, 내 작업(격리된 포트 8099·별도 컨테이너 `jejumate-pg-devtest`)이 원인일 가능성도 배제(그쪽엔 흔적 없음).
  - **프론트(포트 3000)는 살아있었음**: QA로 보이는 `next dev` 프로세스가 `C:\Users\...\Temp\jejumate-build\frontend`에서 계속 떠 있어 손대지 않음. 같은 폴더에서 중복 실행된 좀비 프로세스(포트 3001 충돌 에러)가 하나 더 있었는데 이것도 트래픽을 안 받고 있어 그대로 둠(필요시 정리).
  - **복구 조치**: 백엔드를 원래와 동일하게 `--host 0.0.0.0 --port 8000`으로 재기동(`backend/.env`에 DATABASE_URL 유지, 이번엔 서버를 계속 띄워둘 목적이라 삭제 안 함). posts 테이블이 실제로 0건이라 시드 소실 확정 → `ingest_kakao_txt` 파이프라인(mock, 기존에 검증된 방식)으로 카톡 샘플 45건 재적재 + QA-REPORT에 언급된 "제주공항 택시팟" 예시를 `/posts/party`로 재현 등록(정원3·90분) → 총 46건, 카테고리 다양성 확보(ride 22/run 9/cafe 7/qna 3/walk 2/food 1/stay 1/drink 1). RAG 검색·피드 API 정상 응답 확인, 윈도우→WSL 백엔드 접근(`localhost:8000`)도 재확인함.
  - QA의 원래 6건과 완전히 동일하진 않지만(정확한 6건 목록은 QA-REPORT에 카테고리 개수만 나와 있어 전체 복원 불가), 데모에 필요한 카테고리 다양성·활성 파티 1건은 충분히 갖춰짐.

## 다음 시작 지점
- Day 2.5 태스크(11~14) 모두 완료. 폴백(선착순 전환)은 시간 내 끝나서 사용 안 함 — 승인 로직과 카운트 로직은 이미 분리돼 있어(승인 시에만 approved_count 반영) 필요하면 나중에도 전환 쉬움.
- 다음은 Day 3: 시연용 시드 데이터 적재, (여유 시) 카톡 자동수집 라이브+피드 polling, QA 데모 시나리오 전체 테스트, 리허설.
- 프론트 작업 계속할 때: 윈도우 네이티브 경로(`/mnt/c/Users/AI융합원/AppData/Local/Temp/jejumate-build/frontend`, node_modules 설치돼 있음)에서 `rsync`로 `jejumate/frontend` 최신 소스를 동기화한 뒤 그 경로에서 `next dev`/`next build` 실행.
- **선행 필요**: ANTHROPIC_API_KEY / OPENAI_API_KEY 확보 후 `llm_provider`/`embedding_provider` 설정을 "openai"로 바꾸고 실제 응답 검증.
- **권장**: 백엔드/DB가 다시 죽는 걸 방지하려면 QA·dev가 같은 컨테이너/포트를 쓸 때 서로 어떤 명령을 실행했는지 간단히 공유하는 게 좋겠음(이번엔 원인 특정 실패).
