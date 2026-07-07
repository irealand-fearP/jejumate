CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TYPE user_role AS ENUM ('user', 'admin', 'operator');
CREATE TYPE user_status AS ENUM ('active', 'suspended', 'deleted');
CREATE TYPE verification_type AS ENUM ('phone', 'social', 'program');
CREATE TYPE verification_status AS ENUM ('pending', 'verified', 'failed', 'revoked');
CREATE TYPE meeting_category AS ENUM ('meal', 'work', 'move', 'coffee', 'travel', 'run');
CREATE TYPE meeting_status AS ENUM ('draft', 'open', 'closing_soon', 'full', 'closed', 'hidden', 'cancelled');
CREATE TYPE application_status AS ENUM ('pending', 'approved', 'rejected', 'cancelled');
CREATE TYPE rag_source_type AS ENUM ('meeting', 'community', 'policy', 'curated', 'operator');
CREATE TYPE policy_status AS ENUM ('open', 'closing_soon', 'closed', 'draft', 'needs_review');
CREATE TYPE report_target_type AS ENUM ('meeting', 'user', 'application', 'content');
CREATE TYPE report_status AS ENUM ('open', 'reviewing', 'resolved', 'dismissed');
CREATE TYPE admin_action_type AS ENUM ('hide_meeting', 'restore_meeting', 'resolve_report', 'dismiss_report', 'suspend_user', 'restore_user', 'sync_policy', 'reindex_rag');

CREATE TABLE users (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  role user_role NOT NULL DEFAULT 'user',
  status user_status NOT NULL DEFAULT 'active',
  anonymous_id text UNIQUE,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE profiles (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL UNIQUE REFERENCES users(id),
  nickname varchar(40) NOT NULL,
  avatar_key varchar(80) NOT NULL DEFAULT 'default_01',
  bio varchar(160),
  region varchar(80),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE verifications (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES users(id),
  type verification_type NOT NULL,
  status verification_status NOT NULL DEFAULT 'pending',
  provider_ref text,
  phone_hash text,
  verified_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE programs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name varchar(100) NOT NULL,
  cohort_name varchar(100),
  invite_code_hash text,
  starts_at date,
  ends_at date,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE program_members (
  program_id uuid NOT NULL REFERENCES programs(id),
  user_id uuid NOT NULL REFERENCES users(id),
  badge_label varchar(80),
  joined_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (program_id, user_id)
);

CREATE TABLE places (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name varchar(120) NOT NULL,
  region varchar(80) NOT NULL,
  address_label varchar(160),
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE meetings (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  host_user_id uuid NOT NULL REFERENCES users(id),
  host_profile_id uuid NOT NULL REFERENCES profiles(id),
  program_id uuid REFERENCES programs(id),
  place_id uuid REFERENCES places(id),
  category meeting_category NOT NULL,
  title varchar(80) NOT NULL,
  description text,
  place_label varchar(160) NOT NULL,
  starts_at timestamptz NOT NULL,
  ends_at timestamptz,
  capacity integer NOT NULL CHECK (capacity >= 2),
  approved_count integer NOT NULL DEFAULT 0 CHECK (approved_count >= 0),
  status meeting_status NOT NULL DEFAULT 'open',
  visibility varchar(20) NOT NULL DEFAULT 'public',
  hidden_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE meeting_applications (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  meeting_id uuid NOT NULL REFERENCES meetings(id),
  applicant_user_id uuid NOT NULL REFERENCES users(id),
  applicant_profile_id uuid NOT NULL REFERENCES profiles(id),
  message varchar(300),
  status application_status NOT NULL DEFAULT 'pending',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (meeting_id, applicant_user_id)
);

CREATE TABLE policies (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  external_id varchar(100),
  title varchar(200) NOT NULL,
  summary text NOT NULL,
  target text,
  region varchar(80) NOT NULL,
  field varchar(80) NOT NULL,
  application_start_date date,
  application_end_date date,
  status policy_status NOT NULL DEFAULT 'needs_review',
  official_url text NOT NULL,
  last_synced_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE curated_contents (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  title varchar(160) NOT NULL,
  body text NOT NULL,
  region varchar(80),
  status varchar(20) NOT NULL DEFAULT 'published',
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE rag_documents (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  source_type rag_source_type NOT NULL,
  source_id uuid NOT NULL,
  title varchar(200) NOT NULL,
  body text NOT NULL,
  region varchar(80),
  category varchar(80),
  visibility varchar(20) NOT NULL DEFAULT 'public',
  program_id uuid,
  valid_until timestamptz,
  is_active boolean NOT NULL DEFAULT true,
  search_tsv tsvector,
  embedding vector(1536),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE rag_sources (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  rag_document_id uuid NOT NULL REFERENCES rag_documents(id),
  source_type rag_source_type NOT NULL,
  title varchar(200) NOT NULL,
  url text,
  official boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE rag_query_logs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid REFERENCES users(id),
  anonymous_id text,
  query text NOT NULL,
  intent varchar(80),
  used_source_count integer NOT NULL DEFAULT 0,
  confidence varchar(20) NOT NULL DEFAULT 'low',
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE rag_feedback (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid REFERENCES users(id),
  rag_query_log_id uuid REFERENCES rag_query_logs(id),
  rating varchar(20) NOT NULL,
  clicked_source_id uuid REFERENCES rag_sources(id),
  comment varchar(500),
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE reports (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  reporter_user_id uuid NOT NULL REFERENCES users(id),
  target_type report_target_type NOT NULL,
  target_id uuid NOT NULL,
  reason varchar(80) NOT NULL,
  description varchar(1000),
  status report_status NOT NULL DEFAULT 'open',
  assigned_admin_id uuid REFERENCES users(id),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE blocks (
  blocker_user_id uuid NOT NULL REFERENCES users(id),
  blocked_user_id uuid NOT NULL REFERENCES users(id),
  reason varchar(120),
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (blocker_user_id, blocked_user_id)
);

CREATE TABLE admin_action_logs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  admin_user_id uuid NOT NULL REFERENCES users(id),
  action_type admin_action_type NOT NULL,
  target_type varchar(80) NOT NULL,
  target_id uuid NOT NULL,
  reason varchar(300),
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE analytics_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid REFERENCES users(id),
  anonymous_id text,
  event_name varchar(100) NOT NULL,
  properties jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_meetings_home_feed ON meetings(status, starts_at);
CREATE INDEX idx_meetings_category_starts_at ON meetings(category, starts_at);
CREATE INDEX idx_meetings_program_status ON meetings(program_id, status);
CREATE INDEX idx_policies_status_end_date ON policies(status, application_end_date);
CREATE INDEX idx_reports_status_created_at ON reports(status, created_at);
CREATE INDEX idx_rag_documents_source ON rag_documents(source_type, source_id);
CREATE INDEX idx_rag_documents_active_region ON rag_documents(is_active, region);
CREATE INDEX idx_rag_documents_tsv ON rag_documents USING gin(search_tsv);
