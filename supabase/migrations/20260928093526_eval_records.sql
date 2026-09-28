-- Evaluation records: one row per benchmark run and one per scored case (story F5; INIT > Evaluation,
-- Tech stack > Tracing and evaluation). Reports quote numbers only from these rows, by run id.
--
-- Like the corpus, these tables are server-side: the eval runner writes them over a direct
-- connection, so RLS is enabled with no policies and the Data API roles get no grants. Rows hold
-- benchmark results only, never real user input.

create table public.eval_runs (
  -- A uuid rather than an identity, so a run id quoted in a report never gets reused after a reset.
  id uuid primary key default gen_random_uuid(),
  -- The full commit the run was made from, so a reported number can be reproduced.
  git_sha text not null check (git_sha ~ '^[0-9a-f]{40}$'),
  -- The test set scored, e.g. commission_b, own, appliedai, soft_pairs, qa, annex_match.
  benchmark text not null check (benchmark ~ '^[a-z0-9]+(_[a-z0-9]+)*$'),
  -- Everything that shaped the run. The model, embedding and retrieval keys are required (a value
  -- may be JSON null, e.g. retrieval for the no-retrieval baseline); other keys are free-form.
  config jsonb not null check (
    jsonb_typeof(config) = 'object' and config ?& array['model', 'embedding', 'retrieval']
  ),
  started_at timestamptz not null default now(),
  -- Running totals over the run's model calls; the runner updates them as cases finish.
  cost_usd numeric(12, 6) not null default 0 check (cost_usd >= 0),
  tokens bigint not null default 0 check (tokens >= 0)
);

comment on table public.eval_runs is 'Benchmark runs: commit, test set, configuration, cost and tokens.';
comment on column public.eval_runs.config is
  'Run configuration: model, embedding and retrieval settings (required keys), plus e.g. classifier and exclude mode.';

create table public.eval_case_results (
  run_id uuid not null references public.eval_runs (id) on delete cascade,
  -- The benchmark case id (eval/cases/**), not a foreign key: cases live in files, not tables.
  case_id text not null check (length(case_id) > 0),
  -- The classifier's structured result and the frozen label it was scored against.
  predicted jsonb not null check (jsonb_typeof(predicted) = 'object'),
  label jsonb not null check (jsonb_typeof(label) = 'object'),
  -- Metric name to score: a number, a boolean (hit or miss) or null (metric not applicable).
  scores jsonb not null default '{}' check (
    jsonb_typeof(scores) = 'object'
    and not jsonb_path_exists(
      scores, 'strict $.* ? (@.type() != "number" && @.type() != "boolean" && @.type() != "null")'
    )
  ),
  -- LangSmith trace of the case, for tool-call checks; null when tracing was off.
  trace_id text,
  created_at timestamptz not null default now(),
  -- Also serves lookups by run.
  primary key (run_id, case_id)
);

comment on table public.eval_case_results is 'One scored case per run: prediction, label, per-metric scores and trace.';

-- Comparing one case across runs (e.g. held-out vs in-corpus, engine vs baselines).
create index eval_case_results_case_id_idx on public.eval_case_results (case_id);

alter table public.eval_runs enable row level security;
alter table public.eval_case_results enable row level security;

revoke all on public.eval_runs, public.eval_case_results from anon, authenticated;
