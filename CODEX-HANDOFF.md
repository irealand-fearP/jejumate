# 코덱스 인수인계 문서 (Claude 팀 → 코덱스)

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
  - **`services/api/.env`에 `OPENAI_API_KEY=...` 필요** (보안상 이 폴더엔 없음 — 소유자에게 요청. 키 없으면 RAG 질문 시 명시적 에러)
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

1. **activity-thumbs.png 교체**: 홈 "지금 제주 어딘가에서 N명" 배너의 썸네일 4장이 아직 실사진 스크린샷 조각이라 새 플랫 일러스트 배너와 톤이 어긋남 — 같은 스타일 일러스트로 교체 권장.
2. 시드 카테고리 균형(맛집/숙소 데이터 보강 — RAG에서 해당 질문 시 근거 부족).
3. 생활게시판(/board) 고도화: 현재 목록 최소 구현 — 글쓰기/상세 등은 미구현.
4. 제품 방향(소유자 결정): 카톡 데이터는 초반 유입용, 유입 후엔 서비스 내 작성 글로만 운영 예정.
5. 부제 중복 표시 의혹 1건: 실기기에서 "제주 런케이션 커뮤니티"가 두 번 보였다는 리포트가 있었으나 소스·렌더·서버 HTML 모두 1회만 확인됨(HMR 잔상 추정) — 재현되면 조사.
