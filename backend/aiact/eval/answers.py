"""Fixed answers to follow-up questions, for the downgrade rate's second run (decision 019).

INIT > Metrics asks for the downgrade rate with and without key-fact questions: two stored runs
(V2). The first is a plain run. The second (`aiact evaluate run --answers-from <first run>`)
gives each case the questions its result in the first run asked, answered from the case's
stored `key_fact_answers` where the question's id is a key there; any other question, a
model-written one included, is answered "don't know" (decision 019 as amended 2026-10-07, BACKLOG
> B6). The classifier appends the answers to the description, as the interface does. A case
whose first run asked nothing, or failed, gets no answers, so its second run repeats the first.
The second run is refused when a planned case has no stored row in the first run at all.
"""

from collections.abc import Mapping, Sequence
from uuid import UUID

import psycopg

from aiact.eval.cases import BenchmarkCase
from aiact.schemas import Language

ANSWERING_CLASSIFIERS = frozenset({"engine", "dummy"})
"""The classifiers a run with answers may use: the engine, which appends them, and the dummy,
for a dry run. The baselines read the description alone."""
DONT_KNOW: Mapping[Language, str] = {Language.EN: "don't know", Language.DE: "weiß nicht"}
"""The answer to a question the case stores no answer for, in the case's language."""


class AnswerSourceError(ValueError):
    """The run named by `--answers-from` can't give the questions (missing, or another set)."""


def fixed_answers(case: BenchmarkCase, asked: Sequence[str]) -> dict[str, str]:
    """The case's answers to the questions `asked`, in the order asked: its stored answer where
    it has one, "don't know" otherwise."""
    unknown = DONT_KNOW[case.language]
    return {qid: case.key_fact_answers.get(qid, unknown) for qid in dict.fromkeys(asked)}


def asked_questions(
    conn: psycopg.Connection, run_id: UUID, benchmark: str
) -> dict[str, tuple[str, ...]]:
    """The follow-up question ids each case's stored result in `run_id` asked. Raises
    `AnswerSourceError` when the run doesn't exist or ran another case set."""
    row = conn.execute("select benchmark from eval_runs where id = %s", (run_id,)).fetchone()
    if row is None:
        raise AnswerSourceError(f"no eval run with id {run_id}")
    if row[0] != benchmark:
        raise AnswerSourceError(f"run {run_id} ran the {row[0]} set, not {benchmark}")
    rows = conn.execute(
        "select case_id, predicted -> 'follow_up_questions' from eval_case_results"
        " where run_id = %s",
        (run_id,),
    ).fetchall()
    return {case_id: _question_ids(case_id, questions) for case_id, questions in rows}


def check_answer_source(
    planned: Sequence[BenchmarkCase], asked: Mapping[str, Sequence[str]]
) -> None:
    """Raise `AnswerSourceError` unless the source run stored a row for every planned case: a
    case it never ran would silently get no answers. The message gives counts, not texts."""
    missing = [case.id for case in planned if case.id not in asked]
    if missing:
        raise AnswerSourceError(
            f"{len(missing)} of the {len(planned)} planned cases have no stored row in the "
            f"source run ({len(asked)} stored); give a run that covered every planned case"
        )


def _question_ids(case_id: str, questions: object) -> tuple[str, ...]:
    """The ids of a stored result's questions; none for a failed case (no result)."""
    if questions is None:
        return ()
    if not isinstance(questions, list):
        raise AnswerSourceError(f"case {case_id}: stored follow_up_questions is not a list")
    ids = [question.get("id") if isinstance(question, dict) else None for question in questions]
    if not all(isinstance(qid, str) for qid in ids):
        raise AnswerSourceError(f"case {case_id}: a stored follow-up question has no id")
    return tuple(qid for qid in ids if isinstance(qid, str))
