-- prediction_history
create table if not exists public.prediction_history (
  id           uuid primary key default gen_random_uuid(),
  user_id      uuid references auth.users(id) on delete cascade not null,
  "homeTeam"   text not null,
  "awayTeam"   text not null,
  league       text not null,
  prediction   text not null,
  confidence   integer not null,
  "isValueBet" boolean not null default false,
  "matchDate"  text not null,
  result       text,        -- actual outcome: HOME | DRAW | AWAY (null while pending)
  correct      boolean,     -- null while pending, true/false once result is known
  created_at   timestamptz default now() not null
);

alter table public.prediction_history enable row level security;

create policy "select own predictions"
  on public.prediction_history for select
  using (auth.uid() = user_id);

create policy "insert own predictions"
  on public.prediction_history for insert
  with check (auth.uid() = user_id);

create policy "delete own predictions"
  on public.prediction_history for delete
  using (auth.uid() = user_id);

-- lottery_grids
create table if not exists public.lottery_grids (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid references auth.users(id) on delete cascade not null,
  lottery    text not null,
  numbers    integer[] not null,
  bonus      integer,
  strategy   text,
  label      text,
  created_at timestamptz default now() not null
);

alter table public.lottery_grids enable row level security;

create policy "select own grids"
  on public.lottery_grids for select
  using (auth.uid() = user_id);

create policy "insert own grids"
  on public.lottery_grids for insert
  with check (auth.uid() = user_id);

create policy "delete own grids"
  on public.lottery_grids for delete
  using (auth.uid() = user_id);
