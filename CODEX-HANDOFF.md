# 코덱스 인수인계 문서 (Claude 팀 → 코덱스)

## 2026-07-08 저녁 갱신 — 웹 재배포 + 카톡 실시간 수집 파이프라인(로컬 검증만)

Claude 토큰 소진으로 여기서 코덱스에게 인계. 오후 갱신(바로 아래 섹션)에 이어 저녁에
한 것:

1. **배포 웹(jejumate-web) 재배포 완료**: `jejumate-web` Vercel 프로젝트에
   `NEXT_PUBLIC_API_BASE_URL` 환경변수가 아예 등록돼 있지 않아서(QA가 발견 — 신청 문구가
   옛날 문구, 내정보 파티션도 안 보임) 웹이 API 재배포 이후로도 계속 구버전이었다.
   Production 환경변수로 `https://jejumate-api.vercel.app` 등록 후 재배포 완료.
   재배포판에서 `/policies` 404, 정책 문구 0건, 내정보 파티션·모임·게시판 실데이터 렌더
   전부 확인함. **배포 웹 재배포 상태: 완료.**
2. **카톡 실시간 수집 → RAG 증분 적재 파이프라인 추가 — 로컬 검증만 완료, 배포 연동은
   안 함(코덱스가 이어서 할 일).** 아래 "카톡 수집 API 연동" 섹션 참고.
3. **GitHub 푸시는 안 함**: 로컬 커밋까지만 하고 푸시는 안 했다(대표 담당 규칙). 오늘
   전체 작업이 로컬 `master`와 윈도우 사본(`C:\Users\AI융합원\jejumate-work\jejumate-fork`)
   양쪽에 커밋·동기화까지는 돼 있고, `origin/codex-latest` 대비 몇 개 커밋 앞서 있는지는
   `git log origin/codex-latest..master --oneline`으로 확인 가능. 시크릿 유출 여부는
   이미 스캔 확인함(`postgresql://` 패턴, `.env` 파일 커밋 이력 전부 없음).

### 카톡 수집 API 연동 (신규, 로컬만 검증됨)

- 수집 대상: `GET https://dm.kggstudio.com/chats?after_id=<커서>` — 팀원이 운영하는
  오픈채팅방("2026 제주대학교 하기 계절학기 학점교류방") 실시간 업로드. 응답
  `{"items":[{"id","room","sender","sent_at_text","content","raw","created_at"}]}`.
  `after_id`보다 큰 id만 반환(최대 500건/응답, 방이 활발해서 계속 늘어남 — 확인 시점
  기준 1000건 넘게 쌓여 있었음).
- 커서 저장: `ingest_cursors` 테이블(`source='kakao_live'`, `last_id`). 항목 하나 처리할
  때마다(노이즈로 걸러진 것도 포함) 커서를 그 항목 id로 전진시켜서, 중간에 실패해도
  이미 훑은 범위는 다음 실행에서 다시 안 건드린다.
- 노이즈 필터(`app/services/kakao_ingest.py::_is_noise`): 10자 미만 / 이모지 제거하면
  빈 문자열 / ㅋㅋㅋ·ㅇㅇ·물음표 반복 같은 반응만 있는 메시지는 제외.
- 통과한 메시지는 `embed_text`(OpenAI `text-embedding-3-small`)로 임베딩 후
  `rag_documents`(`source_type='kakao_chat'`, 기존 카톡 시드와 동일 관례)에 적재.
  RAG threshold(0.5)는 그대로 — 여기서 건드리지 않음.
- **로컬**: `app/main.py`의 FastAPI `startup` 이벤트에서 백그라운드 폴링 시작(주기
  `settings.kakao_poll_interval_seconds`, 기본 45초). `os.environ.get("VERCEL")`이
  있으면(=서버리스) 폴링을 안 돈다.
- **배포(서버리스, 코덱스가 할 일)**: 상시 폴링이 안 되므로 `GET /api/ingest/kakao?secret=...`
  수동/크론 트리거 엔드포인트를 이미 만들어뒀다. 이 시크릿은 `INGEST_SECRET` 환경변수와
  일치해야 동작(로컬 `.env`엔 이미 랜덤 값으로 추가돼 있음, 절대 출력/커밋 금지). 배포에
  연동하려면: ① Vercel `jejumate-api` 프로젝트에 `INGEST_SECRET` 환경변수 등록(새 값으로
  발급해도 되고 로컬과 다르게 가도 무방) ② Vercel Cron(`vercel.json`의 `crons` 필드) 또는
  외부 크론으로 30~60초~수 분 주기로 `GET /api/ingest/kakao?secret=<그 값>` 호출 ③ 재배포.
- **로컬 검증 결과**: 실제 메시지 3건(산책 구인/애월 택시팟/제주대-쇠소깍 코스)을 임베딩→
  적재→`POST /api/rag/ask`("애월 택시팟 구해요")로 근거 반환까지 확인. 서버 기동 후
  백그라운드 폴러가 자동으로 이어받아 수백 건을 추가로 적재하는 것도 확인함.
- **주의(중요)**: 배포에 연동하기 전에 백로그 규모(1000건+, 계속 증가 중)를 감안할 것 —
  첫 배포 연동 시 한 번에 다 훑으면 OpenAI 임베딩 호출이 그만큼 발생한다(비용·시간).
  필요하면 첫 실행 전에 커서를 적당히 앞으로 세팅(`set_ingest_cursor`)해서 최근 N건만
  받아오게 조정하는 것도 방법.

## 2026-07-08 오후 갱신 — 정책 기능 삭제 + DB Postgres 이전 + 승인자 채팅

이날 오후에 Claude 팀이 이어서 한 작업(커밋 순, 전부 로컬 커밋까지 완료·GitHub 미푸시):

1. **홈 모임 필터 칩 수정**: 밥친구/작업/이동/커피챗/러닝 버튼이 카테고리 없이 `/meetings`로만
   가던 것을 `?category=` 쿼리로 실제 필터링되게 수정.
2. **청년 정책 기능 전면 삭제(제품 결정)**: 서비스 성격과 안 맞다고 판단해 `/policies` 라우트·
   화면, 백엔드 정책 API·테이블·스키마, RAG 시드의 정책 문서를 모두 제거. RAG는 이제 카톡+
   큐레이션 콘텐츠만 근거로 쓴다. (홈에 정책 미리보기 섹션을 잠깐 추가했다가 같은 날 다시
   삭제한 이력이 있음 — 최종은 "정책 기능 없음".)
3. **신청 모달 문구 교체**: "실명과 연락처를 메시지에 적지 않았습니다" → 노쇼 책임감 안내
   ("신중하게 신청해 주세요. 승인 후 불참하면 기다리는 분들에게 피해가 갑니다").
4. **모임 채팅 접근 제어(신규)**: 기존 채팅 API가 승인 여부와 무관하게 아무나 읽고 쓸 수
   있던 것을 호스트(`owner_secret`)/승인된 신청자(`anonymous_id`)만 접근 가능하도록 403
   게이팅 추가. `GET /api/meetings/{id}`(모임 단건 조회) 신규 추가.
5. **내정보 화면 파티션(신규)**: "① 내가 신청해서 승인된 모임" / "② 내가 만든 모임" 두
   목록을 추가하고 각 항목에서 위 채팅으로 바로 진입 가능.
6. **SQLite→Postgres 이전(★가장 중요, 배포 신청 유실 버그의 근본 해결)**: 아래 항목 참고.

### SQLite→Postgres 이전 상세

- **배경**: Vercel 서버리스는 인스턴스마다 `/tmp`가 독립돼 있어, 신청 API가 요청 A를 처리한
  인스턴스와 그 신청을 조회하는 요청 B가 다른 인스턴스에 뜨면 방금 만든 모임/신청이 안 보임.
  동시요청 15개를 배포 API에 직접 쏴서 4개가 "모임을 찾을 수 없어요" 404로 재현 확인함
  (사용자 리포트 "신청 처리가 안 되고 있다"의 근본 원인).
- **해결**: `services/api/app/repositories/local_store.py`에 `DATABASE_URL` 환경변수 유무로
  SQLite/Postgres를 분기하는 얇은 호환 레이어 추가(`_PgConnectionWrapper`). 로컬 개발은
  `DATABASE_URL` 미설정이라 기존 SQLite 그대로 동작. Supabase Postgres 17.6(Transaction
  pooler)에 스키마 생성+시드+RAG 임베딩(카톡 45건 포함) 적재 완료, Vercel `jejumate-api`
  프로젝트에 `DATABASE_URL`을 환경변수로 등록(Production)하고 재배포 완료.
- **검증**: 재배포 후 동일한 동시요청 15개 테스트를 배포판에서 재실행 → **15/15 200**.
  모임 생성→신청→승인→채팅(403→200 접근제어 포함) 전체 흐름, RAG 질문, 게시판 전부 배포
  판에서 직접 확인. 검증용 테스트 데이터는 정리 완료.
- **주의**: `requirements.txt`에 `psycopg2-binary` 추가(Supabase 트랜잭션 풀러 호환성 때문에
  기존 `psycopg`(v3) 대신 채택 — 둘 다 requirements에 있지만 `local_store.py`는 psycopg2만
  씀). `DATABASE_URL` 값은 Vercel 프로젝트 환경변수에만 있고 이 저장소 어디에도 커밋되지
  않았다(로컬 `.env`에도 넣지 않음 — 로컬은 SQLite 유지가 방침).
- 아래 "남은 항목" 1·2번(배포 DB 영구화, 배포 RAG 시드)은 이제 완료 처리.

## 2026-07-08 최신 전달사항 — 다음 작업자는 여기부터 읽을 것

**최신 본체는 이 로컬 폴더다.**

- 로컬 최신 본체: `C:\Users\AI융합원\jejumate-work\jejumate-fork`
- GitHub 백업/공유 브랜치: `https://github.com/irealand-fearP/jejumate` 의 **`codex-latest`**
- 주의: GitHub `master`는 예전 `backend/`, `frontend/` 구조의 별도 이력이다. **다음 작업은 `master`가 아니라 `codex-latest` 또는 이 로컬 폴더에서 이어갈 것.**
- 이 로컬 폴더에는 `.env`, `.vercel` 같은 로컬 설정이 있어서 바로 이어 작업하기 가장 좋다.
- `.env` 값은 절대 출력하지 말 것. `services/api/.env`에 `OPENAI_API_KEY`가 들어가 있으며 git에는 올라가지 않는다.

최신 배포:

- 웹: `https://jejumate-web.vercel.app`
- API: `https://jejumate-api.vercel.app`
- Vercel 프로젝트: `jejumate-web`, `jejumate-api`
- API Vercel env: `OPENAI_API_KEY`, `DATABASE_URL`(Supabase Postgres, 2026-07-08 오후 등록) 등록 완료. `API_CORS_ORIGINS`에 웹 도메인 등록 완료
- `DATABASE_URL`이 있으므로 이제 Postgres를 쓴다(`JEJUMATE_SQLITE_PATH`는 더 이상 배포에서 안 씀 — SQLite는 로컬 개발 전용). 데이터 영구 보존 문제는 해결됨(아래 2026-07-08 오후 갱신 참고).

최신 커밋 흐름(오래된 순, 위 오후 갱신 항목 포함):

- `82cdb8d` 생활게시판 MVP 마감: 글쓰기·상세·댓글·삭제·신고
- `f7d7c67` Vercel 배포용 API 어댑터 추가
- `03cfac3` Vercel 로컬 설정 디렉터리 무시
- `22229fb` RAG 임베딩 키를 `.env` 설정에서 읽도록 수정
- `178c6f5` 홈 모임 필터 칩에 카테고리 쿼리 파라미터 연결
- `dedcbbe` → `581e857` 홈 정책 섹션 추가했다가 같은 날 정책 기능 전면 삭제(제품 결정)
- `7136c44` 신청 모달 체크 문구를 노쇼 책임감 안내로 교체
- `5a37f2c` 승인된 참가자+호스트만 보이는 모임별 채팅 접근 제어 구현
- `9a6da8e` 내정보 화면에 '승인된 모임'/'내가 만든 모임' 파티션 추가
- `7896053` SQLite/Postgres 이중 지원(DATABASE_URL 있으면 Postgres) — 배포 신청 유실 버그 근본 해결

최신 검증(2026-07-08 오후, 배포판 기준):

- `npm run typecheck`, `python -m compileall app` 통과
- 배포 API 동시요청 15개 테스트: Postgres 이전 전 4개 404 → 이전 후 15/15 200
- 배포 모임 생성→신청→승인→채팅(403→200 접근제어) 전체 흐름 통과
- 배포 RAG `/api/rag/ask` 근거 포함 응답 확인(카톡 소스 포함)
- 배포 게시판 조회/작성 정상
- 로컬 SQLite 스택도 위 전체 흐름 회귀 없음 확인

다음 작업자가 GitHub에서 시작해야 할 경우:

```bash
git clone https://github.com/irealand-fearP/jejumate
cd jejumate
git checkout codex-latest
```

다음 작업자가 로컬에서 시작할 경우:

```powershell
cd C:\Users\AI융합원\jejumate-work\jejumate-fork
```

절대 바꾸지 말아야 할 API 규약:

- 신청 ID 필드명은 모든 응답에서 `application_id`
- 승인/거절은 `POST /api/meetings/{meeting_id}/applications/{application_id}/approve|reject?owner_secret=XXXX`
- `owner_secret`은 query parameter
- 에러 규약: 관리코드 불일치 403 / 정원 초과 409 / 이미 처리된 신청 400
- RAG threshold는 0.5 유지
- RAG 근거 없으면 sources 빈 배열 + 안내 문구. 임의 문서 반환 금지
- 모임 채팅(`GET/POST /api/meetings/{id}/chat/messages`)은 호스트(`owner_secret`)나 승인된
  신청자(`anonymous_id`)만 접근 가능(403 게이팅). 아무나 보이게 되돌리지 말 것.
- `local_store.py`는 `DATABASE_URL` 있으면 Postgres, 없으면 SQLite로 자동 분기한다. 로컬
  `.env`에 `DATABASE_URL`을 넣지 말 것(로컬은 SQLite 유지가 방침).

이 폴더는 `jejumate-service`(코덱스 원본)를 2026-07-07에 포크해서 Claude 팀이 이어 작업한 결과물이다.
**원본 폴더는 한 번도 수정하지 않았고**, 코덱스가 토큰 소진으로 중단한 작업도 여기에 흡수돼 있다.
git 저장소가 포함돼 있으니 `git log`로 전체 이력을 볼 수 있다.

## 여기서 이어서 작업하면 된다 (이 폴더가 최신 본체)

원본 대비 추가/변경된 것 (커밋 순):

1. **30246a7 — RAG를 진짜로 교체**: 기존 키워드 LIKE + "매칭 없으면 아무 문서나 반환" 폴백을 제거하고,
   OpenAI `text-embedding-3-small` 임베딩 + 코사인 유사도 + threshold 0.5로 교체.
   - `services/api/app/services/embedding_service.py` (신규)
   - `rag_documents.embedding` 컬럼 추가(SQLite, JSON 직렬화, 기존 DB엔 ALTER로 안전 추가)
   - `scripts/seed_rag_embeddings.py`: 기존 문서 임베딩 백필 + 카톡 파싱 데이터 45건 적재
   - threshold 미만 = 근거 없음 → "지금 조건에 맞는 유효한 정보를 찾지 못했어요"
2. **4a14793 — 모임 승인 흐름**: 모임 등록(4자리 관리코드 `owner_secret` 발급) → 신청 → 승인/거절.
   - 관리코드 불일치 403, 정원 초과 승인 409("정원이 찼어요"), 이미 처리된 신청 재승인 400
   - `GET /api/meetings/{id}/status` (정원/승인 수, 폴링용)
   - 웹: 등록 폼, 관리코드 표시(localStorage 저장), 승인/거절 바텀시트, "n/정원명"+"1명 남음"
3. **bb02926 — 신청 ID 필드 표준화**: 모든 응답에서 `application_id`로 통일 (QA가 목록 응답의 `id`와 혼용돼 404를 겪음).
4. **98200c4 — 코덱스 중단분 흡수**: 코덱스가 원본에서 작업하다 만 것(신청자 알림, admin 결정 페이지, 신청 삭제)을
   위 API 규약에 맞춰 병합. 승인/모임등록은 QA 통과한 이쪽 구현 유지. 코덱스 원본 스냅샷은 `codex-wip` 브랜치에 보존.
5. **2fe93a6 — 호스트 알림 (신규)**: 신청자 알림만 있고 호스트가 새 신청을 못 받던 것 추가.
   홈/모임 화면에서 대기 신청 수 폴링 → "새 신청 n건" 배너 → 승인 화면 이동.
6. **0c6fa0b — 목록 버그 수정**: `/api/meetings`가 홈 미리보기 LIMIT 6을 공유해 7번째부터 모임이 목록에서
   잘리던 문제 수정(홈은 6개 유지, 목록은 전체). 시간 정렬도 `datetime()` 변환 비교로 교정(+09:00/+00:00 혼재 이슈).

## API 규약 (중요 — 이 규약을 유지할 것)

- 신청 ID 필드명: **`application_id`** (모든 응답에서 통일)
- 승인/거절: `POST /api/meetings/{meeting_id}/applications/{application_id}/approve|reject?owner_secret=XXXX`
  (owner_secret은 **쿼리 파라미터**)
- 에러 규약: 코드 불일치 403 / 정원 초과 409 / 중복 처리 400
- RAG: 근거 없으면 sources 빈 배열 + 안내 문구 (임의 문서 반환 금지)

## 실행 방법

- API: `services/api`에서 `python -m uvicorn app.main:app --host 0.0.0.0 --port 8125`
  - **`services/api/.env`에 `OPENAI_API_KEY=...` 필요**. 현재 로컬 폴더에는 키가 들어가 있으나 절대 출력하지 말 것.
- 웹: `apps/web`에서 `npm install` 후 `NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8125`로 `next dev --port 3128`
- SQLite DB(`services/api/.data/jejumate.sqlite3`)는 첫 기동 시 자동 생성·시드. 카톡 45건 임베딩 적재는 `python scripts/seed_rag_embeddings.py`

## 검증 상태 (2026-07-07 기준)

- QA 전 항목 통과: RAG 3종(관련 질문/무관 질문/기존 시드), 승인 전체 흐름(403·409·400 포함), 기존 기능 회귀.
- 데모 베스트 질문: "오전 10시 제주공항에서 출발하는 택시팟" / "함덕해수욕장 함께 가실 분?"
- 알려진 한계: 시드 데이터가 ride 편중(45%)이라 food/stay 질문은 근거가 적어 "정보 없음"이 뜰 수 있음(의도된 threshold 동작).

## 홈 개편 완료 (2026-07-07 밤 ~ 07-08, git log 참고)

홈이 잠금 PNG에서 **실데이터 React 컴포넌트 홈으로 완전 전환**됐고, 소유자(사용자)의 실기기 피드백까지 반영됐다. 커밋 순:

- `2426dfb` 홈 DOM 전환(컴포넌트 분리: MeetingTimeline/MeetingCard/AskEntryCard/BoardSection/BottomNav, /api/home 실데이터)
- `d068847` 가로폭 축소로 제목 잘리던 버그 수정
- `b662c39` 홈 배너를 새 플랫 일러스트(banner-illustration-new.png, 1584×672, AI 생성)로 교체
- `b586877` 잠금 시안 기준 타이포·간격 정밀 조정(시안 대비 비교 검증)
- `f5ebb65` **배지 시스템**: 인기/NEW를 제목 위 줄로 이동 + 백엔드 단일 판정(`is_popular`: capacity>=4 AND approved>=ceil(capacity/2), `is_new`: 생성 30분 이내) + **실시간 인원수**(활성 모임 호스트+승인 참가자 합, 하드코딩 276 제거)
- `5ea1028` **하단 내비 뷰포트 고정** + 메뉴 개편(모임·질문·홈(중앙)·생활게시판·내정보) + **생활게시판 신설**(/board 페이지 + board_posts 테이블 + GET /api/board + 시드)
- `8c036b0` 실기기 피드백: 모바일 터치 스크롤 수정, <=480px 타이포 축소, 배너 문구 "비로그인으로 간단하게!!"(keep-all), 하단 내비 불투명화

## 실기기(휴대폰) 접속 설정 (이미 구성됨)

- 폰 접속 주소: `http://192.168.200.171:3128` (같은 와이파이). 프론트는 0.0.0.0:3128, `NEXT_PUBLIC_API_BASE_URL=http://192.168.200.171:8125`.
- 윈도우→WSL 포트 연결: `netsh interface portproxy`(8125→WSL IP)+방화벽 허용이 등록돼 있음. **주의: WSL 재시작 시 WSL 내부 IP가 바뀌므로 portproxy의 connectaddress를 새 IP(`ip addr show eth0`)로 재등록해야 함**(관리자 권한).

## 남은 일 (이어서 하면 좋은 것)

완료된 항목:

- `activity-thumbs.png` 교체 완료. 홈 "지금 제주 어딘가에서 N명" 배너 썸네일을 새 플랫 일러스트 톤으로 맞춤.
- 생활게시판(/board) MVP 고도화 완료: 글쓰기, 상세, 댓글 1단계, 본인 글 삭제, 신고, 빈 상태, 작성 시간 표시.
- Vercel 배포 완료: 웹/API 분리 배포.
- `services/api/.env`의 `OPENAI_API_KEY`를 RAG 코드가 읽도록 수정 완료.

완료(2026-07-08 오후~저녁):

1. ~~배포 DB 영구화~~ → Supabase Postgres로 이전 완료.
2. ~~배포 RAG 시드~~ → 배포 Postgres에 카톡 45건 포함 임베딩 적재 완료.
3. ~~배포 웹 재배포~~ → `NEXT_PUBLIC_API_BASE_URL` 등록 후 재배포 완료(위 "저녁 갱신" 참고).

남은 항목(우선순위 순):

4. **카톡 파이프라인 배포 연동**: 로컬은 백그라운드 폴링으로 동작 확인됐지만, Vercel API에
   `INGEST_SECRET` 등록 + 크론 연결이 아직 안 됨(위 "카톡 수집 API 연동" 섹션 참고). 백로그가
   1000건 넘고 계속 느는 중이라 최초 연동 시 비용/시간 고려할 것.
5. 시드 카테고리 균형: 맛집/숙소/생활 데이터 보강. RAG threshold 0.5는 유지하고 데이터만 늘릴 것.
   (카톡 파이프라인이 자연히 채워줄 수도 있음 — 4번과 겹치는 목표.)
6. 제품 방향(소유자 결정): 카톡 데이터는 초반 유입용, 유입 후엔 서비스 내 작성 글로만 운영 예정.
7. 부제 중복 표시 의혹 1건: 실기기에서 "제주 런케이션 커뮤니티"가 두 번 보였다는 리포트가 있었으나 소스·렌더·서버 HTML 모두 1회만 확인됨(HMR 잔상 추정) — 재현되면 조사.
8. 청년 정책 기능은 제품 결정으로 삭제됨(위 갱신 참고) — 되살릴 계획 없음.

## 주의(절대 지킬 것)

- `DATABASE_URL`은 Vercel 프로젝트 환경변수에만 둔다. 로컬 `.env`에 넣지 말 것(로컬 개발은
  SQLite 유지가 방침). 어떤 경우에도 이 값을 git에 커밋하거나 로그/문서에 출력하지 말 것.
- `INGEST_SECRET`도 마찬가지로 값 자체를 출력/커밋하지 말 것.
- API 규약(신청 ID `application_id`, `owner_secret` 쿼리 파라미터, 403/409/400, 채팅 접근
  제어)은 아래 "API 규약" 섹션대로 유지할 것.
- RAG `rag_similarity_threshold`는 0.5 유지. 근거 없으면 sources 빈 배열 + 안내 문구(임의
  문서 반환 금지) 원칙도 유지.
