-- Let a case's scores keep which model served each node's calls (story V8a; X2c, decision 033).
--
-- F5's check (20260928093526_eval_records.sql) allowed only number, boolean or null scores. Since
-- X2c the runner also stores `models` = {node: {model: calls}}, so V8's first paid run failed on
-- its first case write. Every other key stays as F5 had it; `models`, when present, must be an
-- object of objects whose values are non-negative numbers.
--
-- Rows stored before this migration passed the stricter check, so they pass this one too.

alter table public.eval_case_results drop constraint eval_case_results_scores_check;

alter table public.eval_case_results add constraint eval_case_results_scores_check check (
  jsonb_typeof(scores) = 'object'
  -- Metric name to score: a number, a boolean (hit or miss) or null (metric not applicable).
  and not jsonb_path_exists(
    scores,
    'strict $.keyvalue() ? (@.key != "models"'
    ' && @.value.type() != "number" && @.value.type() != "boolean" && @.value.type() != "null")'
  )
  -- `models`: node to {model: calls}. A node that isn't an object is refused before its values
  -- are read, so the filter never compares a non-object's members.
  and (
    not scores ? 'models'
    or (
      jsonb_typeof(scores -> 'models') = 'object'
      and not jsonb_path_exists(
        scores -> 'models',
        'strict $.* ? (@.type() != "object" || exists(@.* ? (@.type() != "number" || @ < 0)))'
      )
    )
  )
);

comment on column public.eval_case_results.scores is
  'Metric name to number, boolean or null; plus `models`, each node''s calls by the model that served them.';
