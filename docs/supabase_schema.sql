-- Future cloud schema mirroring the local repository contract.
-- Add auth/RLS policies before using this with private production data.

create extension if not exists pgcrypto;

create table accounts (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) on delete cascade,
  prop_firm text not null,
  account_type text not null,
  account_size numeric(14,2) not null default 0,
  status text not null,
  purchase_cost numeric(14,2) not null default 0,
  current_pnl numeric(14,2) not null default 0,
  profit_target numeric(14,2) not null default 0,
  drawdown_remaining numeric(14,2) not null default 0,
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table cash_ledger (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) on delete cascade,
  date date not null,
  type text not null check (type in ('Payout', 'Expense')),
  prop_firm text,
  account_id uuid references accounts(id) on delete set null,
  amount numeric(14,2) not null check (amount >= 0),
  notes text,
  created_at timestamptz not null default now()
);

create table journals (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) on delete cascade,
  date date not null,
  session text,
  pnl numeric(14,2) not null default 0,
  what_happened text,
  what_worked text,
  what_went_wrong text,
  main_lesson text,
  strategy_tags text[],
  setup_tags text[],
  screenshot_paths text[],
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table trades (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) on delete cascade,
  trade_key text not null,
  source text,
  account_id uuid references accounts(id) on delete set null,
  symbol text not null,
  side text,
  quantity numeric(14,4) not null,
  entry_time timestamptz,
  exit_time timestamptz,
  entry_price numeric(18,6),
  exit_price numeric(18,6),
  gross_pnl numeric(14,2) not null default 0,
  fees numeric(14,2) not null default 0,
  net_pnl numeric(14,2) not null default 0,
  strategy text,
  setup text,
  session text,
  notes text,
  imported_at timestamptz not null default now(),
  unique (user_id, trade_key)
);

create table daily_performance (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) on delete cascade,
  date date not null,
  label text,
  net_pnl numeric(14,2) not null default 0,
  trades_reported integer not null default 0,
  win_rate_percent numeric(7,2),
  max_drawdown numeric(14,2),
  avg_winner numeric(14,2),
  avg_loser numeric(14,2),
  largest_winner numeric(14,2),
  largest_loss numeric(14,2),
  source_file text,
  journal_summary text,
  include_in_daily_total boolean not null default true,
  created_at timestamptz not null default now()
);

create table behavior_rules (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) on delete cascade,
  name text not null,
  trigger text not null,
  action text not null,
  active boolean not null default true,
  rationale text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index trades_user_exit_time_idx on trades (user_id, exit_time desc);
create index journals_user_date_idx on journals (user_id, date desc);
