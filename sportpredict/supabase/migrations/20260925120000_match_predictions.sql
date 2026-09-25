-- match_predictions
-- Precomputed football predictions, written by the backend's scheduled
-- precompute_predictions job (services/prediction_precompute.py) using the
-- service-role key. Read publicly (anon key) by the frontend so /sports can
-- render predictions without triggering a live football-data.org call per
-- page view.
create table if not exists public.match_predictions (
  fixture_id     bigint primary key,
  league_id      text not null,
  league         text not null default '',
  home_team      text not null,
  away_team      text not null,
  home_form      text not null default '',
  away_form      text not null default '',
  kickoff_at     timestamptz,
  home_prob      numeric not null,
  draw_prob      numeric not null,
  away_prob      numeric not null,
  prediction     text not null,
  confidence     integer not null,
  is_value_bet   boolean not null default false,
  bookmaker_odds numeric,
  edge           numeric,
  model_used     text not null,
  is_low_quality boolean not null default false,
  created_at     timestamptz default now() not null,
  updated_at     timestamptz default now() not null
);

create index if not exists match_predictions_kickoff_at_idx
  on public.match_predictions (kickoff_at);

alter table public.match_predictions enable row level security;

-- Public read-only — anyone (including anon/unauthenticated) can SELECT.
-- No insert/update/delete policy is defined for anon/authenticated roles,
-- so only the service-role key (used by the backend job) can write.
create policy "public read access"
  on public.match_predictions for select
  using (true);
