# 2026-07-13 최신 Claude 전달사항

카카오톡 수집기를 기존 팀원의 `dm.kggstudio.com` 없이 새로 구축했다. 상세 내용과
정확한 파일 목록·검증·남은 작업은 **`CODEX-HANDOFF.md` 맨 끝의
`2026-07-13 최우선 인계 — Windows 카카오톡 수집기 재구축`**을 먼저 읽을 것.

핵심 상태:

- 프로덕션 `https://jejumate-api.vercel.app` 배포 완료.
- 새 전용 비밀키 `KAKAO_UPLOAD_SECRET`은 Vercel Production(Sensitive)과 Windows
  사용자 환경에만 설정. 값은 절대 출력/문서화/커밋하지 말 것.
- 실제 7건 처리, 큐 0, 재실행 신규 0 확인.
- `Synapspot Kakao Export Collector` 예약 작업이 10분마다 내보내기 txt를 감지·업로드.
- 카카오톡 내보내기 버튼 자동 클릭만 미완료. 현재는 사용자가 txt를 만들면 그 뒤가 자동.
- 로컬 Kakao `.edb`는 암호화되어 표준 SQLite로 읽을 수 없음. 복호화 방식은 채택하지 말 것.
- 오늘 변경은 아직 커밋하지 않았으므로 `git status` 확인 후 이어갈 것.

---

# 이전 Codex 작업/검토 인계: 질문 영역 + 지도 프리뷰 융합 아이디어

현재 Claude가 작업 중이라 Codex는 추가 수정 중단. 워킹트리에 Codex 변경분 4개 파일이 남아 있음.

## 1. Codex가 실제 수정한 파일

- `apps/web/features/service/QuestionScreen.tsx`
- `apps/web/features/service/ServicePages.module.css`
- `apps/web/features/home/AskEntryCard.tsx`
- `apps/web/features/common/MobileShell.tsx`

## 2. 수정 의도

다운로드 폴더의 `제주대_챗봇_최종본.zip`을 구조 파악한 뒤, 독립 HTML 챗봇을 그대로 붙이지 않고 제주메이트의 기존 `/question` 화면에 UX만 흡수하는 방향으로 수정함.

이유:

- zip의 `jeju_chatbot.html`은 브라우저에서 OpenAI API를 직접 호출하는 정적 데모라 실서비스에 부적합.
- API 키가 HTML에 노출되는 구조.
- zip의 RAG는 `rag/corpus.jsonl` 직접 사용이 아니라 `rag_corpus.js` 전역 배열 기반.
- 제주메이트에는 이미 `/api/rag/ask`와 `/question` 화면이 있으므로 기존 백엔드 RAG를 유지하는 게 맞음.

## 3. Codex 변경 내용

### `QuestionScreen.tsx`

질문 화면을 "오픈채팅 + 서비스 데이터 기반 AI 질문" 느낌으로 개편.

추가/변경:

- 히어로 섹션 추가
  - `JejuMate AI`
  - `지금 제주에서 통하는 답을 찾아드려요`
  - `동행, 이동, 맛집, 생활 질문을 실제 수집 글과 서비스 근거로 확인합니다.`
- 추천 질문 변경
  - `오늘 제주공항에서 같이 이동할 사람 있어?`
  - `함덕 근처 점심 모임 찾아줘`
  - `비 오는 날 갈 만한 코스 있어?`
  - `오픈채팅에서 나온 최신 질문 알려줘`
- 주제 칩 추가
  - `동행`, `맛집`, `코스`, `생활질문`
- Enter 키로 질문 제출 가능
- 로딩 상태 추가
  - `근거를 찾고 답변을 정리하는 중이에요.`
- 신뢰도 문구 톤 변경
  - `근거가 잘 맞아요`
  - `일부 근거가 맞아요`
  - `근거 연결이 약해요`
- 후속 질문 버튼 표시 추가
- OpenAI 직접 호출 없음. 기존 `askRag()` -> `/api/rag/ask` 그대로 사용.

### `ServicePages.module.css`

질문 화면 전용 스타일 추가.

추가 클래스:

- `.askHero`
- `.askHeroIcon`
- `.topicRow`
- `.answerLoading`
- `.followUpRow`

기존 카드/답변 스타일과 톤을 맞춤.

### `AskEntryCard.tsx`

홈 질문 진입 카드 문구 수정.

변경:

- 칩: `질문게시판/중고거래/나눔` -> `동행/맛집/생활질문`
- 타이틀:
  - `제주에서 궁금한 것, 바로 물어봐요`
- 설명:
  - `오픈채팅과 서비스 글을 근거로 답해드려요`

### `MobileShell.tsx`

하단 탭 렌더링 들여쓰기 정리만 반영됨. 기능 변경 없음.

## 4. 검증 결과

Codex가 실행한 검증:

- `npm.cmd run typecheck:web` 통과
- dev 서버 `http://127.0.0.1:3000` 기동
- `GET http://127.0.0.1:3000/question` 200 확인
- 새 히어로 문구 `지금 제주에서 통하는 답` 렌더링 HTML에서 확인

주의:

- 로컬 Windows 정책 때문에 Next 기본 SWC 바이너리는 차단됐지만, WASM SWC로 폴백되어 페이지는 정상 렌더링됨.

## 5. 현재 워킹트리 상태

Codex 변경분은 아직 커밋하지 않음.

변경 파일:

```text
M apps/web/features/common/MobileShell.tsx
M apps/web/features/home/AskEntryCard.tsx
M apps/web/features/service/QuestionScreen.tsx
M apps/web/features/service/ServicePages.module.css
```

Claude가 현재 `모임 -> 파티` 화면 문구 변경 작업을 하고 있다면 충돌 가능성 있음:

- `QuestionScreen.tsx`
- `ServicePages.module.css`
- `MobileShell.tsx`

특히 `MobileShell.tsx`는 하단 탭 문구/라벨 작업과 겹칠 수 있음.

## 6. 지도 프리뷰 관련 Codex 판단

zip 안의 `maps/` 구조:

```text
maps/
  map_switcher.html
  kakao_map_preview.html
  vworld_3d_preview.html
```

Codex 판단:

- 그대로 iframe으로 박는 방식은 비추천.
- 지도 기능/시각 아이디어만 가져와 제주메이트 컴포넌트로 재구성하는 것이 맞음.
- zip 지도 파일은 API 키/도메인 의존성이 강하고, 정적 데모 구조라 실서비스에 바로 넣기 위험함.

추천 융합 방향:

### 1순위: 질문/RAG 답변 지도화

질문 답변에 장소 근거가 있으면 "지도에서 보기" 섹션 표시.

예:

- 질문: `비 오는 날 갈 만한 코스 있어?`
- 답변 하단: 실내 스팟/장소 2~3개를 Kakao 지도 마커로 표시

서비스 가치가 가장 잘 드러남:

- "오픈채팅과 서비스 데이터를 읽고 실제 제주 장소로 연결한다"는 느낌이 생김.

### 2순위: 파티 상세 장소 미리보기

파티 상세에서 `place_label`이 있으면 지도 프리뷰 표시.

예:

- `함덕해수욕장 점심 파티`
- 상세 하단에 지도 카드 + Kakao 길찾기/지도 열기 버튼

### 3순위: 홈/탐색의 "지금 뜨는 제주" 지도

오픈채팅에서 많이 나온 장소나 파티 위치를 지도에 찍는 화면.
초기 구현 난이도는 조금 더 높음.

## 7. 3D 지도에 대한 판단

`vworld_3d_preview.html`은 데모/피치용으로는 멋있지만, 실서비스 메인 기능으로 바로 쓰기에는 부담이 있음.

이유:

- 모바일 성능/초기 로딩 부담
- API 키/도메인/트래픽 정책 확인 필요
- 상업 이용 정책 확인 필요
- 현재 서비스 핵심은 "질문 -> 근거 -> 장소/파티 연결"이므로 2D 지도부터 넣는 게 안정적

추천:

- 실사용: Kakao 2D 지도
- 피치/데모용: 3D 프리뷰를 숨은 페이지 또는 관리자/데모 화면으로 분리

## 8. 구현 제안

처음에는 아래 구조로 작게 시작 추천.

```text
apps/web/features/map/
  JejuMapPreview.tsx
  PlaceMapSection.tsx
```

### `JejuMapPreview.tsx`

- client component
- Kakao Maps SDK 동적 로딩
- props:
  - `places: Array<{ title: string; lat: number; lng: number; description?: string }>`
  - `height?: number`
- API 키는 `NEXT_PUBLIC_KAKAO_MAP_APP_KEY` 사용
- 키를 코드에 직접 박지 말 것

### `PlaceMapSection.tsx`

- 질문 답변 또는 파티 상세에서 쓰는 UI 래퍼
- 장소 데이터가 없으면 렌더링하지 않음
- "지도에서 보기" 버튼 제공

## 9. 환경/도메인 주의

자체 서버가 현재 메인:

- Web: `http://115.68.226.19:8126`
- API: `http://115.68.226.19:8125`

Kakao 지도 사용 시 Kakao Developers에 아래 도메인 등록 필요:

- `http://115.68.226.19:8126`
- 로컬 개발용이 필요하면 `http://127.0.0.1:3000` 또는 실제 dev 포트도 등록

zip README에는 기존 지도 키가 `http://lvh.me:8791` 기준이라고 되어 있었음.
그 키/구조를 그대로 쓰면 자체 서버에서 `domain mismatched` 가능성이 높음.

## 10. Claude에게 물어볼 결정사항

Claude가 현재 작업과 충돌 없이 융합 가능하면 아래 방향으로 진행 추천:

1. Codex 질문 화면 변경분을 유지할지?
2. `모임 -> 파티` 문구 변경 시 Codex가 넣은 질문 카피도 같이 톤 맞출지?
   - 예: `동행`, `파티`, `맛집`, `생활질문`
3. 지도는 우선 `Kakao 2D 지도`만 넣고, 3D는 데모용으로 미룰지?
4. RAG 답변 sources에 장소 좌표가 아직 없으면, 1차는 `place_label` 기반 정적 후보/링크만 보여줄지?
5. Kakao 지도 키를 새 환경변수 `NEXT_PUBLIC_KAKO_MAP_APP_KEY`가 아니라 `NEXT_PUBLIC_KAKAO_MAP_APP_KEY`로 추가할지?

Codex 추천 결론:

- 지금 질문 화면 개편은 유지해도 괜찮음.
- 단, Claude의 `모임 -> 파티` 문구 작업과 충돌 나면 Claude 쪽 변경 위에 Codex 질문 UX를 다시 얹는 방식이 안전함.
- 지도는 3D부터 넣지 말고, 질문 답변/파티 상세에 Kakao 2D 미니맵부터 녹이는 게 가장 실용적.

## 11. Claude 판단 (2026-07-09)

1. **질문 화면 변경분 유지 확정.** 백엔드 안 건드리고 프론트 카피/UX만 바꿨고 typecheck도 통과했으니 안전함. dev의 [C](모임→파티 용어 변경)가 끝나는 대로 그 위에 이 4개 파일 변경분을 얹을 것 — 지금 시점(C 시작 전)엔 충돌 없음.
2. **Codex 질문 카피 톤도 파티 용어로 맞출 것.** 다만 확인해보니 Codex가 추가한 문구(`동행`/`맛집`/`코스`/`생활질문`, 히어로 텍스트)엔 애초에 "모임"이라는 단어가 없어서 실질적으로 고칠 게 거의 없을 것으로 보임 — 얹을 때 한 번만 훑어서 "모임"이 남아있으면 "파티"로.
3. ~~지도는 지금 넣지 않는다~~ **[2026-07-09 갱신] 사용자가 팀원이 만든 지도를 꼭 넣고 싶다고 확인 — 진행으로 방향 전환.** 아래 12번 참고.
4. RAG sources에 좌표 아직 없으니, 1차는 `place_label` 기반 정적 텍스트/링크만으로 시작(코덱스 원안 그대로).
5. 환경변수명은 오타 없는 쪽으로: **`NEXT_PUBLIC_KAKAO_MAP_APP_KEY`**(KAKO 오타 아님).

**Codex에게**: 질문 화면 변경분은 dev의 [C]/[D] 완료 후 대표가 동기화·재배포 마치면 그때 windows fork에 커밋하는 걸 도와주면 됩니다. **지도는 지금 바로 시작해도 좋습니다** — 12번 참고.

## 12. 지도 기능 진행 승인 (2026-07-09)

사용자 확정: 지도 기능 진행. 코덱스가 제안한 설계·우선순위 그대로 진행해도 됩니다.

- **지금 시작 가능** — dev가 지금 [C]/[D](모임→파티 용어 변경, 내정보 통합) 작업 중이라 `HomeScreen.tsx`/`MeetingsScreen.tsx`/`ChatSheet.tsx`를 건드리고 있음. 지도 컴포넌트는 새 파일(`features/map/JejuMapPreview.tsx`, `PlaceMapSection.tsx`)이라 겹칠 위험 적음 — 다만 이 컴포넌트를 QuestionScreen.tsx나 파티 상세에 실제로 "끼워 넣는" 지점은 dev 작업 완료 후 대표가 동기화한 뒤에 진행해줄 것(끼워 넣는 지점이 겹칠 수 있는 파일이라).
- 순서 추천: ①`JejuMapPreview.tsx`/`PlaceMapSection.tsx` 컴포넌트 자체는 독립적으로 지금 만들어도 됨 ②실제 QuestionScreen/파티 상세에 연결하는 건 dev 동기화 후.
- 1순위(질문/RAG 답변 지도화)부터, place_label 기반 정적 표시로 시작. RAG sources에 좌표 없으니 좌표는 place_label→좌표 매핑 테이블이나 지오코딩이 필요할 수 있음 — 이 부분은 백엔드(dev) 협업이 필요할 수 있으니 설계 확정되면 대표에게 공유해줄 것.
- 3D 프리뷰는 여전히 보류(데모/피치용으로 별도 숨은 페이지 정도만, 메인 기능 아님).
- Kakao Maps 키 발급·도메인 등록(115.68.226.19:8126 등)은 사용자/팀원이 직접 처리 필요 — 대표가 대신 계정을 만들 수 없는 부분.

## 13. 추가 권고사항 (2026-07-09, 사용자 질문에 대한 답)

1. **지도는 `answer_source === 'community'` 답변에만 연결할 것.** dev가 지금 만들고 있는 RAG 일반지식 폴백이 배포되면 응답에 `answer_source: 'community' | 'general_knowledge'` 필드가 생긴다(근거 있으면 community, 근거 없어서 gpt-5-mini가 일반 지식으로 답한 경우 general_knowledge). **general_knowledge 답변에는 지도를 절대 붙이지 말 것** — 검증 안 된 장소 정보에 지도까지 달면 "이것도 우리 데이터"처럼 보여서 신뢰도 컨셉이 흐려진다.
2. **카카오맵 도메인(`http://115.68.226.19:8126`) 등록을 지금 미리 해둘 것.** 데모 당일 domain mismatched 에러 나는 걸 방지하려면 계정 가진 팀원이 최대한 빨리 등록해야 함.
3. **`NEXT_PUBLIC_KAKAO_MAP_APP_KEY`가 없어도 앱이 안 깨지게.** 장소 데이터 없을 때 미렌더는 이미 설계에 있음 — 키 자체가 없을 때도 똑같이 조용히 안 보이기만 하고 다른 화면엔 영향 없어야 함.
4. **순서 재확인**: 컴포넌트(`JejuMapPreview.tsx`/`PlaceMapSection.tsx`) 자체는 지금 만들어도 됨. 질문 화면에 실제로 끼워 넣는 건 dev의 RAG 폴백 작업 완료·동기화 후에(answer_source 필드가 그때 확정되니까).
