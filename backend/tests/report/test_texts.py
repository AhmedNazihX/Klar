"""The reports' copies of the screens' wording (P25) stay equal to the screens' locales
(`frontend/src/i18n/locales`), so a report never says a step, a class or a basis differently from
the Result screen. The repo is one checkout: the backend's CI job has `frontend/` too."""

import json
import re
from collections.abc import Iterator, Mapping
from functools import cache
from pathlib import Path

import pytest

from aiact.report import texts
from aiact.schemas import Language, RiskClass, Role, Status, StepName

LOCALES = Path(__file__).parents[3] / "frontend/src/i18n/locales"
PLACEHOLDER = re.compile(r"\{\{\s*(\w+)\s*\}\}")
ONE = "_one"
"""i18next's singular suffix: the report's own singular text has the count written in."""

STATUS_KEYS = {
    Status.DECIDED: "status.decided",
    Status.NEEDS_MORE_INFORMATION: "status.needs-info",
    Status.LEGALLY_AMBIGUOUS: "status.ambiguous",
}
STEP_KEYS = {
    StepName.SCOPE: "scope",
    StepName.PROHIBITED: "prohibited",
    StepName.HIGH_RISK: "high_risk",
    StepName.TRANSPARENCY: "transparency",
}
OUTCOME_KEYS = {
    **{key: key for key in texts.STEP_OUTCOMES},
    "transparencyDuty": f"transparencyDuties{ONE}",
    "transparencyDuties": "transparencyDuties_other",
}


@cache
def _locale(language: Language) -> Mapping[str, str]:
    data = json.loads((LOCALES / f"{language.value}.json").read_text(encoding="utf-8"))
    return dict(_flat(data, ""))


def _flat(node: Mapping[str, object], prefix: str) -> Iterator[tuple[str, str]]:
    for key, value in node.items():
        if isinstance(value, Mapping):
            yield from _flat(value, f"{prefix}{key}.")  # pyright: ignore[reportUnknownArgumentType]
        else:
            yield f"{prefix}{key}", str(value)


def _screen(key: str, language: Language) -> str:
    """The locale's text for `key`, its `{{x}}` placeholders written `{x}`, and a singular's
    count written in as 1."""
    text = PLACEHOLDER.sub(r"{\1}", _locale(language)[key])
    return text.replace("{count}", "1") if key.endswith(ONE) else text


def _copies() -> Iterator[tuple[str, texts.ByLanguage]]:
    """Each copied text with the locale key it copies."""
    for risk_class, name in texts.CLASS_NAMES.items():
        yield f"pill.{risk_class.value}", name
    for status, key in STATUS_KEYS.items():
        yield key, texts.STATUS_NAMES[status]
    for role in Role:
        yield f"result.roleName.{role.value}", texts.ROLE_NAMES[role]
    for step, key in STEP_KEYS.items():
        yield f"progress.check.{key}", texts.STEP_NAMES[step]
    yield "result.steps.role", texts.STEP_NAMES[StepName.ROLE_OBLIGATIONS]
    for step, reference in texts.STEP_REFERENCES.items():
        yield f"progress.reference.{step.value}", reference
    for key, outcome in texts.STEP_OUTCOMES.items():
        yield f"result.steps.{OUTCOME_KEYS[key]}", outcome
    for key, label in texts.ANNEX_III_LABELS.items():
        yield f"annexPoint.{key}", label
    yield "result.basis.annexI", texts.BASIS_ANNEX_I
    yield "result.basis.annexIII", texts.BASIS_ANNEX_III
    yield "result.basis.annexIIIPlain", texts.BASIS_ANNEX_III_PLAIN
    for risk_class, basis in texts.CLASS_BASIS.items():
        yield f"result.basis.{risk_class.value}", basis
    yield "inventory.needs.prohibited", texts.STOP_USING
    yield "inventory.table.appliesFrom", texts.FROM_HEADER


COPIES = tuple(_copies())


@pytest.mark.parametrize("language", list(Language))
@pytest.mark.parametrize(("key", "text"), COPIES, ids=[key for key, _ in COPIES])
def test_a_copied_text_is_the_screens(key: str, text: texts.ByLanguage, language: Language) -> None:
    assert text[language] == _screen(key, language)


def test_every_class_step_outcome_and_annex_label_is_checked() -> None:
    keys = {key for key, _ in COPIES}
    assert len(keys) == len(COPIES)
    assert {f"pill.{risk_class.value}" for risk_class in RiskClass} <= keys
    assert {f"result.basis.{risk_class.value}" for risk_class in RiskClass} <= keys
    assert len(texts.STEP_NAMES) == len(STEP_KEYS) + 1
