"""The second-model label filter (story B9; INIT > Label rules for own cases).

A different model from the engine's, Claude Haiku 4.5 (`LABEL_FILTER_MODEL` on its pinned EU
endpoint `LABEL_FILTER_PROVIDER`, fallbacks off, decision 005), labels every case of the sets
whose labels are the student's own, blind: it sees the description, the case's fixed answers to
follow-up questions (decision 019) and the date the case is judged on, never the label, its
citation, the notes, the tags or the Commission example it came from. Its context is the AI
Act's own text (the consolidated, amended version from `data/parsed/`), never a guideline, so
it can't read a Commission verdict either.

Each answer is appended to `ANSWERS_FILE` as soon as it arrives, so an interrupted run resumes
where it stopped: a case whose input is unchanged and already answered is not sent again.
`aiact.eval.label_filter_report` compares the answers with the labels and writes the
disagreements for the user to resolve. The filter catches mistakes; it is not validation.
"""

import hashlib
import logging
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from pydantic import Field, ValidationError

from aiact.corpus.eurlex import DEFAULT_PARSED_DIR, ParsedProvision, load_jsonl
from aiact.eval.cases import EVAL_DIR, OWN_LABELLED_SETS, BenchmarkCase, CaseSet, load_cases
from aiact.llm import chat_model
from aiact.llm.chat import reply_usage
from aiact.llm.structured import (
    ProviderRefusalError,
    describe_validation_error,
    json_schema_format,
    parse_reply,
)
from aiact.provision_names import provision_name
from aiact.schemas import Language, RiskClass, Role, Status
from aiact.schemas.base import ContractModel
from aiact.settings import Settings, get_settings

logger = logging.getLogger(__name__)

REPORTS_DIR = EVAL_DIR / "reports"
ANSWERS_FILE = REPORTS_DIR / "label_filter_answers.jsonl"
FILTERED_SETS: tuple[CaseSet, ...] = tuple(
    case_set for case_set in CaseSet if case_set in OWN_LABELLED_SETS
)
"""The sets whose labels are the student's own (INIT > Label rules for own cases), in `CaseSet`
order. The academic and appliedAI labels are other people's and aren't filtered."""

LAW_FILE = "ai-act-consolidated.en.jsonl"
LAW_PROVISIONS = (
    "art:2",
    "art:3:1",
    "art:3:3",
    "art:3:4",
    "art:3:6",
    "art:3:7",
    "art:5",
    "art:6",
    "art:25",
    "art:50",
    "art:111",
    "art:113",
    "annex:I",
    "annex:III",
)
"""What a label rests on: scope, the AI-system and role definitions, the prohibitions, the
high-risk rules with both Annexes, the role switch, Art. 50 and the dates. About 50,000
characters, sent first and cached, so each case pays for it at the cache-read price."""

MAX_OUTPUT_TOKENS = 1500
"""Bounds a runaway answer; one answer is a few hundred tokens."""
CALL_ESTIMATE_USD = 0.02
"""What one call costs before its cache is warm (decision 005: Haiku 4.5 on google-vertex/europe,
$0.0199 for a 6,463-token prompt; this prompt is about twice as long but caches after the first
call). Charged to the cap for a call whose real cost is unknown, and used for estimates."""
DEFAULT_MAX_COST_USD = 1.0
DEFAULT_CONCURRENCY = 4
MAX_CONCURRENCY = 8
CACHE_CONTROL = {"type": "ephemeral"}
"""Anthropic caches only when asked (decision 005). The breakpoint sits on the instructions and
the law, so every case reads them from the cache whatever its description."""


class FilterAnswer(ContractModel):
    """The second model's label; also the JSON schema it fills. Enum fields carry no
    description (strict structured output rejects keywords next to a `$ref`); the
    instructions explain them."""

    risk_class: RiskClass | None
    status: Status
    role: Role | None
    annex_point: str | None = Field(
        description="For high_risk, the Annex point, e.g. annex:III:4:a or annex:I:A:11."
    )
    reason: str = Field(min_length=1, description="Two or three sentences naming the provisions.")


RESPONSE_FORMAT = json_schema_format("label_filter_answer", FilterAnswer)

INSTRUCTIONS = """\
You check the labels of a benchmark of AI system descriptions. Classify the system described \
under the EU AI Act (Regulation (EU) 2024/1689) as amended by the Digital Omnibus, the text \
quoted below. Rely on that text and the description only; nothing else will be looked up.

Check in this order and stop at the first class that applies:
1. Scope: is it an AI system (Art. 3(1)) within the Act's scope (Art. 2)? If not: out_of_scope.
2. Prohibited practices (Art. 5): prohibited. A point of Art. 5 that applies only from a later \
date (Art. 113) doesn't apply before that date.
3. High-risk (Art. 6 with Annex I or Annex III, including the Art. 6(3) exception and its \
profiling rule): high_risk.
4. Transparency duties (Art. 50): limited_risk.
5. Otherwise: minimal_risk.

Answer with JSON matching the schema:
- risk_class: the class.
- status: "decided" when the description settles the class. "needs_more_information" when a \
fact the description leaves out would change the class; risk_class is then the stricter \
reading, or null when the description is too thin to say what the system does at all. \
"legally_ambiguous" when the facts are clear but the law itself doesn't settle the class; \
risk_class is then the stricter reading. out_of_scope is always "decided".
- role: the role of the company describing the system: provider, deployer, importer or \
distributor (Art. 3(3), 3(4), 3(6), 3(7), Art. 25); null only when the class is out_of_scope or \
the description gives no basis at all.
- annex_point: for high_risk, the point it falls under, written like "annex:III:4:a" (Annex III, \
point 4(a)), "annex:III:2" or "annex:I:A:11" (Annex I, Section A, point 11); otherwise null.
- reason: two or three sentences in English naming the provisions that decide the class.

Judge the system on the date given with the description. Further answers from the company, \
when given, are part of the description.
"""


def law_context(parsed_dir: Path = DEFAULT_PARSED_DIR) -> str:
    """`LAW_PROVISIONS` from the consolidated English text, each under its heading. Raises
    `LookupError` when one is missing from the parsed file."""
    rows = {row.provision_id: row for row in load_jsonl(parsed_dir / LAW_FILE)}
    missing = [pid for pid in LAW_PROVISIONS if pid not in rows]
    if missing:
        raise LookupError(f"not in {LAW_FILE}: {', '.join(missing)}")
    return "\n\n".join(_quoted(rows[pid]) for pid in LAW_PROVISIONS)


def _quoted(row: ParsedProvision) -> str:
    name = provision_name(row.provision_id, Language.EN)
    title = row.heading if row.kind in ("article", "annex") else f"{name} ({row.heading})"
    return f"### {title}\n{row.text}"


def system_message(law: str) -> SystemMessage:
    """The instructions and the law as one cached block, the same for every case."""
    text = f"{INSTRUCTIONS}\n## The AI Act (consolidated text)\n\n{law}"
    return SystemMessage(content=[{"type": "text", "text": text, "cache_control": CACHE_CONTROL}])


def case_text(case: BenchmarkCase) -> str:
    """What the second model reads of a case: the description, then its fixed answers. The
    label, citation, notes, tags and source example are never part of it."""
    answers = "\n".join(f"- {key}: {value}" for key, value in case.key_fact_answers.items())
    further = f"\n\nFurther answers from the company:\n{answers}" if answers else ""
    return f"Description:\n{case.description}{further}"


def judged_on(case: BenchmarkCase, run_date: date) -> date:
    """The case's own date when its label depends on one, else the run's."""
    return case.as_of or run_date


def input_sha256(case: BenchmarkCase) -> str:
    """Identifies what was sent for a case, so an edited case is labelled again. The run's date
    isn't part of it: a case whose label depends on the date carries its own `as_of`."""
    as_of = case.as_of.isoformat() if case.as_of else ""
    return hashlib.sha256(f"{as_of}\n{case_text(case)}".encode()).hexdigest()


def filter_messages(case: BenchmarkCase, law: str, run_date: date) -> list[BaseMessage]:
    """The cached instructions and law first, the case last (decision 005)."""
    when = judged_on(case, run_date).isoformat()
    return [system_message(law), HumanMessage(f"Date: {when}\n\n{case_text(case)}")]


class FilterRecord(ContractModel):
    """One case's labelling, a line of `ANSWERS_FILE`. `answer` is None when the call failed;
    `error` then says why, by type only (never the description or the reply)."""

    case_id: str
    set_name: CaseSet
    input_sha256: str
    judged_on: date
    model: str
    provider: str
    answer: FilterAnswer | None
    error: str | None = None
    cost_usd: float = Field(ge=0)
    is_cost_estimated: bool = Field(
        default=False, description="No usage came back; `CALL_ESTIMATE_USD` was charged."
    )
    tokens: int = Field(ge=0)


class LabelFilter:
    """The second model labelling one case at a time."""

    def __init__(
        self,
        settings: Settings | None = None,
        chat: BaseChatModel | None = None,
        law: str | None = None,
    ) -> None:
        """`chat` replaces the OpenRouter model and `law` the parsed text (tests). The model makes
        exactly one attempt per case (`max_retries=0`), pinned to its EU endpoint with fallbacks
        off. Raises `LLMConfigError` when the API key is not set."""
        settings = settings or get_settings()
        self.model = settings.label_filter_model
        self.provider = settings.label_filter_provider
        self.law = law if law is not None else law_context()
        self._chat = chat or chat_model(
            model=self.model,
            provider_order=[self.provider],
            allow_fallbacks=False,
            max_tokens=MAX_OUTPUT_TOKENS,
            max_retries=0,
            settings=settings,
        )

    def label(self, case: BenchmarkCase, run_date: date) -> FilterRecord:
        """The second model's label for `case`; a failed call is a record with its error, and
        its cost counts (the estimate when none came back)."""
        record = self._record(case, run_date)
        try:
            reply = self._chat.invoke(
                filter_messages(case, self.law, run_date), response_format=RESPONSE_FORMAT
            )
        except Exception as exc:
            logger.warning("label filter call for %s failed: %s", case.id, type(exc).__name__)
            return record(None, _error(exc), CALL_ESTIMATE_USD, 0, is_estimated=True)
        cost, tokens = reply_usage(reply)
        is_estimated = cost is None
        spent = CALL_ESTIMATE_USD if cost is None else cost
        try:
            answer = parse_reply(reply, FilterAnswer)
        except (ValidationError, ProviderRefusalError) as exc:
            return record(None, _error(exc), spent, tokens, is_estimated=is_estimated)
        return record(answer, None, spent, tokens, is_estimated=is_estimated)

    def _record(self, case: BenchmarkCase, run_date: date) -> Callable[..., FilterRecord]:
        def make(
            answer: FilterAnswer | None,
            error: str | None,
            cost_usd: float,
            tokens: int,
            *,
            is_estimated: bool,
        ) -> FilterRecord:
            return FilterRecord(
                case_id=case.id,
                set_name=case.set_name,
                input_sha256=input_sha256(case),
                judged_on=judged_on(case, run_date),
                model=self.model,
                provider=self.provider,
                answer=answer,
                error=error,
                cost_usd=cost_usd,
                is_cost_estimated=is_estimated,
                tokens=tokens,
            )

        return make


def _error(exc: Exception) -> str:
    """Metadata only: a validation error by location and message, anything else by type."""
    if isinstance(exc, ValidationError):
        return f"answer doesn't fit the schema: {describe_validation_error(exc)}"
    if isinstance(exc, ProviderRefusalError):
        return "refused by the provider's content filter"
    return type(exc).__name__


# --- the run ------------------------------------------------------------------------------------


def load_filtered_cases(sets: Iterable[CaseSet] = FILTERED_SETS) -> tuple[BenchmarkCase, ...]:
    """Every case of `sets`, in set order then file order."""
    return tuple(case for case_set in sets for case in load_cases(case_set))


def read_records(path: Path = ANSWERS_FILE) -> dict[str, FilterRecord]:
    """The latest record per case id; none when the file doesn't exist yet."""
    if not path.exists():
        return {}
    lines = path.read_text(encoding="utf-8").splitlines()
    records = (FilterRecord.model_validate_json(line) for line in lines if line.strip())
    return {record.case_id: record for record in records}


def is_current(record: FilterRecord | None, case: BenchmarkCase, model: str, provider: str) -> bool:
    """Whether `record` answers `case` as it is now, from this model and endpoint."""
    return (
        record is not None
        and record.answer is not None
        and record.input_sha256 == input_sha256(case)
        and (record.model, record.provider) == (model, provider)
    )


def cases_to_label(
    cases: Sequence[BenchmarkCase], records: Mapping[str, FilterRecord], model: str, provider: str
) -> tuple[BenchmarkCase, ...]:
    """The cases without a current answer: new, edited or failed ones."""
    return tuple(c for c in cases if not is_current(records.get(c.id), c, model, provider))


@dataclass(frozen=True)
class RunSummary:
    planned: int
    labelled: int
    failed: int
    cost_usd: float
    tokens: int
    is_stopped_at_cap: bool


def run_filter(
    cases: Sequence[BenchmarkCase],
    labeller: LabelFilter,
    *,
    run_date: date,
    max_cost_usd: float = DEFAULT_MAX_COST_USD,
    concurrency: int = DEFAULT_CONCURRENCY,
    answers_file: Path = ANSWERS_FILE,
) -> RunSummary:
    """Label `cases` in batches, appending each record as its batch ends. The first batch is a
    single call, so the cached prefix is written before the others read it. No batch starts
    unless the money spent plus `CALL_ESTIMATE_USD` per call in it stays within `max_cost_usd`.
    A batch in which every call fails stops the run (a wrong key or a down endpoint)."""
    answers_file.parent.mkdir(parents=True, exist_ok=True)
    spent, tokens, labelled, failed = 0.0, 0, 0, 0
    is_stopped_at_cap = False
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        for batch in _batches(cases, concurrency):
            if spent + CALL_ESTIMATE_USD * len(batch) > max_cost_usd:
                is_stopped_at_cap = True
                break
            done = list(pool.map(lambda case: labeller.label(case, run_date), batch))
            _append(answers_file, done)
            spent += sum(record.cost_usd for record in done)
            tokens += sum(record.tokens for record in done)
            batch_failed = sum(record.answer is None for record in done)
            labelled, failed = labelled + len(done) - batch_failed, failed + batch_failed
            if batch_failed == len(done):
                logger.warning("every call in a batch failed; stopping the run")
                break
    return RunSummary(len(cases), labelled, failed, spent, tokens, is_stopped_at_cap)


def _batches(cases: Sequence[BenchmarkCase], size: int) -> Iterator[Sequence[BenchmarkCase]]:
    if cases:
        yield cases[:1]
    for start in range(1, len(cases), size):
        yield cases[start : start + size]


def _append(path: Path, records: Iterable[FilterRecord]) -> None:
    lines = "".join(f"{record.model_dump_json()}\n" for record in records)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(lines)


def estimate_usd(count: int) -> float:
    """An upper estimate for `count` calls at the cold price; cached calls cost less."""
    return round(count * CALL_ESTIMATE_USD, 2)
