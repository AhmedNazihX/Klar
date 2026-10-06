"""The citation existence validator (E9; INIT > Evaluation: citation existence is a hard 100%;
Corpus rules: "Where the Omnibus changed a provision, the answer says so").

- **Existence.** A citation resolves when `get_provision` finds its provision in the language it
  quotes, under the law version it names, on the run's date (`as_of` for the amended text and
  guidance; none for the original text), and the row belongs to the document the citation names
  by its manifest `doc_key` (`Citation.document_id`, the rule of the eval citation check, V2),
  with the same law version and language. A held-out example never resolves (decision 012). A
  citation of the Omnibus itself (`document_id` `omnibus`) resolves through the explicit
  `get_omnibus_provision`: `get_provision` never returns an amending act (decision 009).
- **Quoted from the corpus.** A citation that resolves is rebuilt from the row found, so its
  quote, status and language are the corpus's own (E7's citations quote the parsed files).
- **The Omnibus marker.** A resolved citation of the amended text is `changed_by_omnibus` when
  the slice it quotes is in force after the Omnibus and one of C1's amendment records targets
  the provision, a part of it or the provision it belongs to (`touches_target`, the rule the
  corpus build splits slices by). The original text and the Omnibus itself never carry it.
- **One repair retry.** `CitationValidator.checked` wraps a check node. A step citing something
  that doesn't resolve is run once more (a refused step is not: decision 029); if a citation
  still doesn't resolve, the step keeps the citations that do, gets the error
  `citation_unverified` (a refused step keeps `provider_refusal`) and says that a person must
  verify it. A decided step becomes `needs_more_information`, which may still end the run
  (`can_end_run`); an uncertain step keeps its status and its question, so the run goes on as it
  would have. Findings are kept.
"""

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from functools import cache
from pathlib import Path
from typing import Protocol

import psycopg
from pydantic import ValidationError

from aiact.corpus.build import OMNIBUS_DOC, omnibus_in_force, touches_target
from aiact.corpus.eurlex import load_jsonl as load_law_jsonl
from aiact.db import connect
from aiact.engine.graph import CheckNode
from aiact.engine.nodes.common import Lookup, lookup_for, provision_citation
from aiact.engine.state import CheckOutcome, EngineState
from aiact.retrieval.provisions import (
    PROVISION_ID_RE,
    Provision,
    ProvisionNotFoundError,
    get_omnibus_provision,
    get_provision,
)
from aiact.schemas import (
    PROVIDER_REFUSAL,
    Citation,
    Language,
    LawVersion,
    Status,
    StepName,
    StepResult,
)
from aiact.settings import Settings, get_settings

logger = logging.getLogger(__name__)

CITATION_UNVERIFIED = "citation_unverified"
"""The `error` of a step whose citations still don't all resolve after its retry."""

UNVERIFIED: Mapping[Language, str] = {
    Language.EN: "A provision this check cites could not be found in the legal corpus, so a "
    "person must verify this step.",
    Language.DE: "Eine Vorschrift, die diese Prüfung zitiert, wurde im Rechtskorpus nicht "
    "gefunden; eine Person muss diesen Schritt daher überprüfen.",
}
"""The sentence added to the decision of a step with an unverified citation."""


class CitationSource(Protocol):
    """Where citations are resolved: the corpus (`CorpusCitations`), or a stand-in in tests.
    Both methods raise `ProvisionNotFoundError` when no row matches, ValueError for a malformed
    request."""

    def provision(
        self,
        provision_id: str,
        language: Language,
        law_version: LawVersion | None,
        as_of: date | None,
    ) -> Provision:
        """`get_provision`'s answer."""
        ...

    def omnibus(self, provision_id: str, language: Language, as_of: date | None) -> Provision:
        """`get_omnibus_provision`'s answer."""
        ...


class CorpusCitations:
    """The corpus through `get_provision` and `get_omnibus_provision`, over one connection."""

    def __init__(self, connection: psycopg.Connection) -> None:
        self._connection = connection

    def provision(
        self,
        provision_id: str,
        language: Language,
        law_version: LawVersion | None,
        as_of: date | None,
    ) -> Provision:
        return get_provision(
            provision_id, language, law_version, as_of, connection=self._connection
        )

    def omnibus(self, provision_id: str, language: Language, as_of: date | None) -> Provision:
        return get_omnibus_provision(provision_id, language, as_of, connection=self._connection)


@dataclass(frozen=True)
class OmnibusChanges:
    """C1's amendment records reduced to what the marker needs: the Omnibus's entry into force
    and every AI Act provision id its amendments target."""

    in_force_from: date
    targets: frozenset[str]

    def marks(self, provision: Provision) -> bool:
        """Whether a citation quoting `provision` says the Omnibus changed it: amended text in
        force after the Omnibus, of a provision an amendment targets, contains or belongs to."""
        if provision.law_version is not LawVersion.AMENDED:
            return False
        is_current = provision.valid_to is None or provision.valid_to > self.in_force_from
        return is_current and touches_target(provision.provision_id, self.targets)


@cache
def load_omnibus_changes(data_dir: Path) -> OmnibusChanges:
    """The amendment records of the parsed Omnibus (`<data_dir>/parsed/omnibus.en.jsonl`; the
    German records target the same ids). Raises OSError when the file can't be read, and the
    corpus build's `LoadError` when the records don't share one entry-into-force date."""
    rows = load_law_jsonl(data_dir / "parsed" / f"{OMNIBUS_DOC}.en.jsonl")
    in_force, targets = omnibus_in_force(rows)
    return OmnibusChanges(in_force_from=in_force, targets=targets)


@dataclass(frozen=True)
class CitationCheck:
    """A step's citations checked: those that resolve, rebuilt from the corpus and marked, and
    those that don't, as given."""

    verified: tuple[Citation, ...]
    unresolved: tuple[Citation, ...]


def resolve(citation: Citation, lookup: Lookup, source: CitationSource) -> Provision | None:
    """The corpus row `citation` names, or None when it doesn't resolve (see the module
    docstring): a malformed id or one of no known kind doesn't. A database error, or a row
    that doesn't fit `Provision`, is raised, never read as a missing citation."""
    if not PROVISION_ID_RE.fullmatch(citation.provision_id):
        return None
    try:
        provision = _find(citation, lookup, source)
    except ValidationError:
        raise  # a ValueError too, but a corrupt corpus row, not a missing citation
    except (ProvisionNotFoundError, ValueError):
        return None
    found = (provision.doc_key, provision.law_version, provision.language)
    named = (citation.document_id, citation.law_version, citation.language)
    return provision if found == named else None


def _find(citation: Citation, lookup: Lookup, source: CitationSource) -> Provision:
    if citation.document_id == OMNIBUS_DOC:
        return source.omnibus(citation.provision_id, citation.language, lookup.as_of)
    # The original text has one slice per unit and takes no date (`get_provision`).
    as_of = None if citation.law_version is LawVersion.ORIGINAL else lookup.as_of
    return source.provision(citation.provision_id, citation.language, citation.law_version, as_of)


def check_citations(
    citations: Sequence[Citation],
    lookup: Lookup,
    source: CitationSource,
    omnibus: OmnibusChanges,
) -> CitationCheck:
    """Every citation resolved against `source`: the verified ones quote the row found and carry
    the Omnibus marker; the others are listed as unresolved."""
    found = [(citation, resolve(citation, lookup, source)) for citation in citations]
    verified = tuple(
        provision_citation(provision).model_copy(
            update={
                "english_only": citation.english_only,
                "changed_by_omnibus": omnibus.marks(provision),
            }
        )
        for citation, provision in found
        if provision is not None
    )
    unresolved = tuple(citation for citation, provision in found if provision is None)
    return CitationCheck(verified=verified, unresolved=unresolved)


def with_checked_citations(
    outcome: CheckOutcome, checked: CitationCheck, language: Language
) -> CheckOutcome:
    """`outcome` with its step citing only the verified citations; when any didn't resolve, the
    step is flagged as the module docstring says."""
    step = outcome.step
    if not checked.unresolved:
        cited = step.model_copy(update={"citations": checked.verified})
        return outcome.model_copy(update={"step": cited})
    is_decided = step.status is Status.DECIDED
    unverified = StepResult.model_validate(
        {
            **dict(step),
            "citations": checked.verified,
            "decision": f"{step.decision} {UNVERIFIED[language]}",
            "status": Status.NEEDS_MORE_INFORMATION if is_decided else step.status,
            "error": step.error or CITATION_UNVERIFIED,
        }
    )
    return outcome.model_copy(update={"step": unverified})


class CitationValidator:
    """Checks every citation of a check's step against the corpus, with one retry of the step
    (see the module docstring). Wrap the check nodes with `checks` when building the graph."""

    def __init__(
        self,
        source: CitationSource | None = None,
        omnibus: OmnibusChanges | None = None,
        settings: Settings | None = None,
    ) -> None:
        """`source` replaces the corpus (tests); without it, each check reads the corpus over a
        short connection from DATABASE_URL. `omnibus` replaces C1's amendment records, which
        are read from the settings' data directory otherwise."""
        self._source = source
        data_dir = (settings or get_settings()).aiact_data_dir
        self._omnibus = omnibus or load_omnibus_changes(data_dir)

    def check(self, step: StepResult, state: EngineState) -> CitationCheck:
        """`step`'s citations resolved on the run's language, law version and date."""
        if not step.citations:
            return CitationCheck(verified=(), unresolved=())
        lookup = lookup_for(state)
        if self._source is not None:
            return check_citations(step.citations, lookup, self._source, self._omnibus)
        with connect() as connection:
            source = CorpusCitations(connection)
            return check_citations(step.citations, lookup, source, self._omnibus)

    def checked(self, node: CheckNode) -> CheckNode:
        """`node` with its step's citations verified, the step run once more when one doesn't
        resolve, and flagged when one still doesn't. A refused step (decision 029) is flagged
        without a retry: running it again would only be refused again."""

        def run(state: EngineState) -> CheckOutcome:
            outcome = node(state)
            checked = self.check(outcome.step, state)
            if checked.unresolved and outcome.step.error != PROVIDER_REFUSAL:
                _log_unresolved(outcome.step.step, checked, "retrying the step")
                outcome = node(state)
                checked = self.check(outcome.step, state)
            if checked.unresolved:
                _log_unresolved(outcome.step.step, checked, "the step is flagged")
            return with_checked_citations(outcome, checked, state["language"])

        return run

    def checks(self, nodes: Mapping[StepName, CheckNode]) -> dict[StepName, CheckNode]:
        """Every check node wrapped by `checked`, for `EngineNodes(checks=…)`."""
        return {name: self.checked(node) for name, node in nodes.items()}


def _log_unresolved(name: StepName, checked: CitationCheck, action: str) -> None:
    """Metadata only: the step and the provision ids that didn't resolve."""
    ids = [f"{c.document_id}/{c.provision_id}" for c in checked.unresolved]
    logger.warning("%s cites provisions that don't resolve (%s); %s", name.value, ids, action)
