-- Hoops Engine client domain schema (non-Supabase).
-- Safe to run on an empty database. Does not create auth.* tables.
-- App-managed *_staging tables are created by SQLAlchemy (bootstrap script).

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ---------------------------------------------------------------------------
-- Core org structure
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.organizations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL,
  sport text DEFAULT 'Basketball'::text,
  gender_focus text DEFAULT 'Mixed'::text,
  city text,
  state text,
  country text DEFAULT 'USA'::text,
  logo_url text,
  admin_email text NOT NULL,
  created_at timestamptz DEFAULT now(),
  join_code text UNIQUE,
  subscription_active boolean DEFAULT false,
  subscription_expires_at timestamptz,
  phone_number text,
  address text
);

CREATE TABLE IF NOT EXISTS public.teams (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id),
  name text NOT NULL,
  season text,
  level text,
  team_view_code text UNIQUE,
  created_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.subteams (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  team_id uuid NOT NULL REFERENCES public.teams(id),
  org_id uuid NOT NULL REFERENCES public.organizations(id),
  name text NOT NULL,
  coach_code text UNIQUE,
  created_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.coaches (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id),
  team_id uuid REFERENCES public.teams(id),
  subteam_id uuid REFERENCES public.subteams(id),
  first_name text NOT NULL,
  last_name text NOT NULL,
  email text,
  role text DEFAULT 'subteam_coach'::text,
  invite_token text UNIQUE,
  invite_accepted boolean DEFAULT false,
  created_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.players (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid REFERENCES public.organizations(id),
  team_id uuid REFERENCES public.teams(id),
  subteam_id uuid REFERENCES public.subteams(id),
  first_name text NOT NULL,
  last_name text NOT NULL,
  jersey_number text,
  grade text,
  birth_year integer,
  gender text,
  position text,
  home_state text,
  home_country text DEFAULT 'USA'::text,
  phone text,
  player_code text NOT NULL DEFAULT ('PC-'::text || upper(substring((gen_random_uuid())::text, 1, 8))) UNIQUE,
  active boolean DEFAULT true,
  created_at timestamptz DEFAULT now(),
  email text,
  parent_guardian text,
  joined_org_at timestamptz,
  birthdate date,
  -- No FK to auth.users (Supabase removed). IDs may still match users.id.
  user_id uuid
);

-- ---------------------------------------------------------------------------
-- Drills / plans
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.drills (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL UNIQUE,
  category text NOT NULL,
  description text,
  directions text,
  keys text,
  balls_required integer DEFAULT 1,
  passers_required integer DEFAULT 0,
  time_seconds integer,
  players_required integer DEFAULT 1,
  animation_brief text,
  animation_svg text,
  animation_ready boolean DEFAULT false,
  submitted_by_org uuid REFERENCES public.organizations(id),
  approved boolean DEFAULT true,
  global boolean DEFAULT true,
  created_at timestamptz DEFAULT now(),
  timing_type text DEFAULT 'countdown'::text,
  target_shots integer DEFAULT 0,
  categories text,
  rebounders integer DEFAULT 0,
  pr_required integer DEFAULT 0,
  tokens text,
  arrows text,
  shot_areas integer DEFAULT 1,
  sequence text,
  scoring_type text DEFAULT 'makes'::text
);

CREATE TABLE IF NOT EXISTS public.subteam_drill_sets (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  subteam_id uuid NOT NULL REFERENCES public.subteams(id),
  drill_id uuid NOT NULL REFERENCES public.drills(id),
  active boolean DEFAULT true,
  sort_order integer DEFAULT 0,
  added_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.practice_plans (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL,
  org_id uuid REFERENCES public.organizations(id),
  created_by_user uuid,
  created_by_name text,
  drill_count integer DEFAULT 0,
  created_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.practice_plan_drills (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  plan_id uuid REFERENCES public.practice_plans(id),
  drill_id uuid REFERENCES public.drills(id),
  drill_name text,
  reps integer DEFAULT 1,
  order_num integer DEFAULT 0
);

CREATE TABLE IF NOT EXISTS public.drill_submissions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid REFERENCES public.organizations(id),
  submitted_by uuid REFERENCES public.coaches(id),
  drill_name text NOT NULL,
  category text,
  description text,
  directions text,
  keys text,
  balls_required integer,
  passers_required integer,
  youtube_url text,
  animation_brief text,
  status text DEFAULT 'pending'::text,
  admin_notes text,
  submitted_at timestamptz DEFAULT now(),
  reviewed_at timestamptz
);

-- ---------------------------------------------------------------------------
-- Sessions / recording
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.session_codes (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  subteam_id uuid NOT NULL REFERENCES public.subteams(id),
  org_id uuid NOT NULL REFERENCES public.organizations(id),
  code text NOT NULL UNIQUE,
  created_by uuid REFERENCES public.coaches(id),
  duration_hrs integer DEFAULT 2,
  expires_at timestamptz NOT NULL,
  revoked boolean DEFAULT false,
  created_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.practice_sessions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id),
  team_id uuid REFERENCES public.teams(id),
  subteam_id uuid REFERENCES public.subteams(id),
  session_date date NOT NULL DEFAULT CURRENT_DATE,
  recorder_type text,
  recorder_player_id uuid REFERENCES public.players(id),
  recorder_coach_id uuid REFERENCES public.coaches(id),
  session_code_used uuid REFERENCES public.session_codes(id),
  device_id text,
  synced boolean DEFAULT true,
  created_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.session_data (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id uuid REFERENCES public.practice_sessions(id),
  org_id uuid NOT NULL REFERENCES public.organizations(id),
  subteam_id uuid REFERENCES public.subteams(id),
  player_id uuid NOT NULL REFERENCES public.players(id),
  drill_id uuid REFERENCES public.drills(id),
  makes integer NOT NULL DEFAULT 0,
  attempts integer NOT NULL DEFAULT 0,
  effort_score integer,
  court_spots jsonb,
  session_date date NOT NULL DEFAULT CURRENT_DATE,
  recorded_at timestamptz DEFAULT now(),
  synced boolean DEFAULT true,
  score integer
);

-- ---------------------------------------------------------------------------
-- Roles / usernames (legacy client tables; no auth.users FK)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.user_roles (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL UNIQUE,
  org_id uuid NOT NULL REFERENCES public.organizations(id),
  role text NOT NULL CHECK (role = ANY (ARRAY['admin'::text, 'coach'::text, 'player'::text])),
  entity_id uuid,
  team_id uuid,
  created_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.usernames (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  username text NOT NULL UNIQUE,
  email text NOT NULL,
  phone text,
  user_id uuid,
  created_at timestamptz DEFAULT now(),
  contact_email text
);

CREATE TABLE IF NOT EXISTS public.trial_users (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  code text NOT NULL,
  name text NOT NULL,
  email text NOT NULL,
  phone text,
  trial_org_id uuid,
  used_dates date[] DEFAULT '{}'::date[],
  max_uses integer DEFAULT 2,
  first_seen timestamptz DEFAULT now(),
  last_seen timestamptz DEFAULT now()
);
