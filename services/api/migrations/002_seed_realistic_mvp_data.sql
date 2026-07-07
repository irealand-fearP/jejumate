INSERT INTO users (id, role, status, anonymous_id)
VALUES
  ('11111111-1111-4111-8111-111111111111', 'user', 'active', 'host_profile_badang'),
  ('22222222-2222-4222-8222-222222222222', 'user', 'active', 'host_profile_island'),
  ('33333333-3333-4333-8333-333333333333', 'user', 'active', 'host_profile_runner'),
  ('44444444-4444-4444-8444-444444444444', 'user', 'active', 'host_profile_dolhareubang'),
  ('55555555-5555-4555-8555-555555555555', 'user', 'active', 'host_profile_oreum')
ON CONFLICT (id) DO UPDATE
SET anonymous_id = EXCLUDED.anonymous_id,
    updated_at = now();

INSERT INTO profiles (id, user_id, nickname, avatar_key, region)
VALUES
  ('67095530-a0cf-504d-8759-7954d6dc4e62', '11111111-1111-4111-8111-111111111111', '바당이', 'host_default', '함덕'),
  ('7c96158a-b7ec-5a38-b395-a03e10dc25d3', '22222222-2222-4222-8222-222222222222', '아일랜드', 'host_default', '구좌'),
  ('c9092e1f-f991-586c-a813-1b400add2002', '33333333-3333-4333-8333-333333333333', '러너제주', 'host_default', '이호'),
  ('b2834ffb-beb8-5528-baa6-a93efe331d8e', '44444444-4444-4444-8444-444444444444', '돌하르방', 'host_default', '서귀포'),
  ('58e0d4c4-3b6d-53af-8acf-bd061c922583', '55555555-5555-4555-8555-555555555555', '오름메이트', 'host_default', '애월')
ON CONFLICT (id) DO UPDATE
SET nickname = EXCLUDED.nickname,
    region = EXCLUDED.region,
    updated_at = now();

INSERT INTO meetings (
  id, host_user_id, host_profile_id, category, title, description, place_label,
  starts_at, ends_at, capacity, approved_count, status, visibility
)
VALUES
  (
    'df5cebff-009a-5e6a-ab14-5a0329f59719',
    '11111111-1111-4111-8111-111111111111',
    '67095530-a0cf-504d-8759-7954d6dc4e62',
    'meal',
    '함덕 점심 같이 먹자',
    '함덕 해변 근처에서 점심 먹고 산책까지 이어지는 소규모 밥친구 모임',
    '함덕해수욕장 근처',
    '2026-07-07T11:00:00+09:00',
    '2026-07-07T13:00:00+09:00',
    4,
    2,
    'open',
    'public'
  ),
  (
    '9b1ce43d-f15d-55f0-9629-96e40638cd00',
    '22222222-2222-4222-8222-222222222222',
    '7c96158a-b7ec-5a38-b395-a03e10dc25d3',
    'work',
    '오션뷰 카페 작업팟',
    '노트북 작업, 짧은 회고, 저녁 전 자유 해산으로 운영되는 워케이션 작업 모임',
    '구좌 오션뷰 카페',
    '2026-07-07T14:00:00+09:00',
    '2026-07-07T17:00:00+09:00',
    5,
    1,
    'open',
    'public'
  ),
  (
    '45bc4716-1dda-52b0-bfad-fd73aaa324dd',
    '33333333-3333-4333-8333-333333333333',
    'c9092e1f-f991-586c-a813-1b400add2002',
    'run',
    '해안도로 5km 러닝',
    '초보 페이스로 함께 달리고 바다 앞에서 쿨다운하는 저녁 러닝',
    '이호테우해변',
    '2026-07-07T17:30:00+09:00',
    '2026-07-07T19:00:00+09:00',
    6,
    3,
    'open',
    'public'
  ),
  (
    'c88d926d-f13b-5c3a-ad07-7d2628969b5e',
    '44444444-4444-4444-8444-444444444444',
    'b2834ffb-beb8-5528-baa6-a93efe331d8e',
    'move',
    '공항 → 서귀포 택시팟',
    '도착 시간이 맞는 참가자끼리 이동비를 나누는 안전 동행 이동팟',
    '제주공항 3번 게이트',
    '2026-07-07T20:00:00+09:00',
    '2026-07-07T21:30:00+09:00',
    4,
    1,
    'open',
    'public'
  ),
  (
    '28c26062-bc01-5ff9-b652-ae4214caf472',
    '55555555-5555-4555-8555-555555555555',
    '58e0d4c4-3b6d-53af-8acf-bd061c922583',
    'coffee',
    '애월 노을 커피챗',
    '런케이션 기간에 일, 취향, 정책 정보를 편하게 나누는 커피챗',
    '애월 해안도로 카페',
    '2026-07-08T18:00:00+09:00',
    '2026-07-08T19:30:00+09:00',
    5,
    2,
    'open',
    'public'
  )
ON CONFLICT (id) DO UPDATE
SET title = EXCLUDED.title,
    description = EXCLUDED.description,
    place_label = EXCLUDED.place_label,
    starts_at = EXCLUDED.starts_at,
    ends_at = EXCLUDED.ends_at,
    capacity = EXCLUDED.capacity,
    approved_count = EXCLUDED.approved_count,
    status = EXCLUDED.status,
    updated_at = now();

INSERT INTO policies (
  id, external_id, title, summary, target, region, field,
  application_start_date, application_end_date, status, official_url, last_synced_at
)
VALUES
  (
    '0274f4fa-d154-5549-8bb7-38331c92f95a',
    'jeju-youth-trip-2026',
    '제주 청년 큐레이션 여행 지원',
    '런케이션 기간 중 체류형 여행 경비를 최대 30만원까지 지원',
    '제주 체류 청년 및 워케이션 참가자',
    '제주',
    '여행',
    '2026-07-01',
    '2026-08-15',
    'open',
    'https://www.jeju.go.kr',
    '2026-07-07T09:00:00+09:00'
  ),
  (
    '56f1a3f9-5b63-5568-85ec-17de467b89b6',
    'jeju-local-startup-2026',
    '청년 로컬창업 지원사업 참여자 모집',
    '로컬 문제를 해결하는 청년 창업팀에 사업화 자금과 멘토링 제공',
    '만 19~39세 청년 예비창업자',
    '제주',
    '창업',
    '2026-07-05',
    '2026-08-31',
    'open',
    'https://www.jeju.go.kr',
    '2026-07-07T09:00:00+09:00'
  ),
  (
    'fd5895a1-ce80-5911-862d-010fbe86de36',
    'jeju-workation-pass-2026',
    '제주 워케이션 오피스 패스',
    '공유오피스, 회의실, 네트워킹 프로그램을 묶어 할인 지원',
    '제주 체류 근로자 및 프리랜서',
    '제주',
    '일자리',
    '2026-07-10',
    '2026-09-10',
    'open',
    'https://www.jeju.go.kr',
    '2026-07-07T09:00:00+09:00'
  )
ON CONFLICT (id) DO UPDATE
SET title = EXCLUDED.title,
    summary = EXCLUDED.summary,
    target = EXCLUDED.target,
    field = EXCLUDED.field,
    application_end_date = EXCLUDED.application_end_date,
    status = EXCLUDED.status,
    official_url = EXCLUDED.official_url,
    last_synced_at = EXCLUDED.last_synced_at,
    updated_at = now();

INSERT INTO rag_documents (
  id, source_type, source_id, title, body, region, category, visibility, is_active
)
VALUES
  (
    'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa1',
    'policy',
    '0274f4fa-d154-5549-8bb7-38331c92f95a',
    '제주 청년 큐레이션 여행 지원 핵심 조건',
    '제주 체류 청년은 체류 기간, 참여 프로그램, 증빙 자료 조건을 충족하면 여행 경비 일부를 지원받을 수 있습니다. 신청 마감은 2026년 8월 15일입니다.',
    '제주',
    '정책',
    'public',
    true
  ),
  (
    'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa2',
    'curated',
    'df5cebff-009a-5e6a-ab14-5a0329f59719',
    '함덕 점심 추천 동선',
    '함덕 해수욕장 근처 점심은 2~4명 밥친구 모임으로 예약하면 대기 시간이 짧고, 식사 후 해변 산책까지 이어가기 좋습니다.',
    '제주',
    '장소',
    'public',
    true
  ),
  (
    'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa3',
    'curated',
    '28c26062-bc01-5ff9-b652-ae4214caf472',
    '비 오는 날 제주 코스',
    '비가 오는 날은 오션뷰 카페 작업, 실내 전시, 공유오피스 네트워킹을 묶은 코스가 만족도가 높습니다. 이동팟을 함께 잡으면 비용 부담을 줄일 수 있습니다.',
    '제주',
    '코스',
    'public',
    true
  )
ON CONFLICT (id) DO UPDATE
SET title = EXCLUDED.title,
    body = EXCLUDED.body,
    is_active = EXCLUDED.is_active,
    updated_at = now();

INSERT INTO rag_sources (id, rag_document_id, source_type, title, url, official)
VALUES
  ('bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbb1', 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa1', 'policy', '제주특별자치도 청년정책', 'https://www.jeju.go.kr', true),
  ('bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbb2', 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa2', 'curated', '제주메이트 검증 데이터', 'https://jejumate.local/curation', false),
  ('bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbb3', 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa3', 'curated', '제주메이트 검증 데이터', 'https://jejumate.local/curation', false)
ON CONFLICT (id) DO UPDATE
SET title = EXCLUDED.title,
    url = EXCLUDED.url,
    official = EXCLUDED.official;

INSERT INTO analytics_events (id, anonymous_id, event_name, properties, created_at)
SELECT gen_random_uuid(),
       'anon_seed_' || lpad(index::text, 3, '0'),
       'app_opened',
       '{}'::jsonb,
       now()
FROM generate_series(1, 276) AS index
WHERE NOT EXISTS (
  SELECT 1
  FROM analytics_events
  WHERE event_name = 'app_opened'
    AND anonymous_id = 'anon_seed_001'
);
