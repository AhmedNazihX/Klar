"""The Omnibus as amending text: which AI Act provisions each instruction changes, and when."""

from datetime import date
from pathlib import Path

import pytest

from aiact.corpus.amendments import Amendment
from aiact.corpus.eurlex import DEFAULT_PARSED_DIR, ParsedProvision, load_jsonl, parse_document
from aiact.corpus.sources import Language

FIXTURES = Path(__file__).parent.parent / "fixtures" / "eurlex"
LANGUAGES: tuple[Language, ...] = ("en", "de")
ENTRY_INTO_FORCE = date(2026, 7, 27)
"""Published 24.7.2026, in force on the third day after."""

AI_ACT_IDS = frozenset(
    {"art:5", "art:5:1", "art:10", "art:10:5", "art:40", "art:40:2", "art:111", "art:111:2"}
    | {"art:113", "art:113:a", "annex:VIII", "annex:VIII:B", "annex:VIII:B:7", "annex:VIII:B:9"}
)
"""The AI Act ids the fixture's instructions point at. Article 113 has no numbered paragraphs."""


def omnibus(language: Language) -> dict[str, ParsedProvision]:
    content = (FIXTURES / f"omnibus.{language}.html").read_bytes()
    rows = parse_document(content, "omnibus", language, AI_ACT_IDS)
    return {row.provision_id: row for row in rows}


def amendment(rows: dict[str, ParsedProvision], pid: str) -> Amendment:
    found = rows[pid].amendment
    assert found is not None, pid
    return found


EXPECTED: dict[str, tuple[str, tuple[str, ...]]] = {
    "art:1:1": ("insert", ("art:4a",)),
    "art:1:2:a": ("insert", ("art:5:1:ba", "art:5:1:bb")),
    "art:1:3": ("delete", ("art:10:5",)),
    "art:1:4": ("add", ("art:40:2",)),
    "art:1:5": ("add", ("art:111:4",)),
    "art:1:6:a": ("replace", ("art:113:a",)),
    "art:1:7": ("delete", ("annex:VIII:B:7", "annex:VIII:B:9")),
}


@pytest.mark.parametrize("language", LANGUAGES)
@pytest.mark.parametrize("pid", list(EXPECTED))
def test_each_instruction_names_its_action_and_targets(pid: str, language: Language) -> None:
    found = amendment(omnibus(language), pid)

    assert (found.action, found.targets) == EXPECTED[pid]
    assert found.in_force_from == ENTRY_INTO_FORCE


@pytest.mark.parametrize("language", LANGUAGES)
def test_only_leaf_instructions_carry_an_amendment(language: Language) -> None:
    rows = omnibus(language)

    with_amendment = sorted(pid for pid, row in rows.items() if row.amendment is not None)
    assert with_amendment == sorted(EXPECTED)
    assert rows["art:1:2"].amendment is None  # `Article 5 is amended as follows:` groups (a)


@pytest.mark.parametrize("language", LANGUAGES)
def test_quoted_text_stays_inside_its_instruction(language: Language) -> None:
    rows = omnibus(language)

    assert not any(pid.startswith("art:1:2:a:") for pid in rows)  # not art:1:2:a:ba
    assert "bb" in rows["art:1:2:a"].text
    assert "4a" in rows["art:1:1"].text


@pytest.mark.parametrize("language", LANGUAGES)
def test_an_act_amending_another_regulation_gets_no_ai_act_targets(language: Language) -> None:
    rows = omnibus(language)

    assert "art:2:1" in rows
    assert rows["art:2:1"].amendment is None
    assert not any(pid.startswith("art:2:1:") for pid in rows)


@pytest.mark.parametrize("language", LANGUAGES)
def test_dates_in_the_instruction_are_kept_but_dates_of_cited_acts_are_not(
    language: Language,
) -> None:
    rows = omnibus(language)

    assert amendment(rows, "art:1:5").dates == (date(2026, 8, 2), date(2026, 12, 2))
    assert amendment(rows, "art:1:6:a").dates == (date(2025, 2, 2), date(2026, 12, 2))
    assert amendment(rows, "art:1:4").dates == ()  # Regulation … of 25 October 2012


def test_without_the_ai_act_ids_the_german_paragraph_level_is_kept() -> None:
    """German counts the unnumbered third paragraph of Article 113 as `Absatz 3`; only the AI
    Act's ids show that level doesn't exist."""
    content = (FIXTURES / "omnibus.de.html").read_bytes()
    rows = {r.provision_id: r for r in parse_document(content, "omnibus", "de")}

    assert amendment(rows, "art:1:6:a").targets == ("art:113:3:a",)


# --- The committed Omnibus ---------------------------------------------------------------------


def committed(doc: str, language: Language) -> dict[str, ParsedProvision]:
    return {r.provision_id: r for r in load_jsonl(DEFAULT_PARSED_DIR / f"{doc}.{language}.jsonl")}


def committed_amendments(language: Language) -> dict[str, Amendment]:
    rows = committed("omnibus", language)
    return {pid: row.amendment for pid, row in rows.items() if row.amendment is not None}


def test_english_and_german_amendments_agree() -> None:
    en, de = committed_amendments("en"), committed_amendments("de")

    assert len(en) > 60
    assert en == de


def test_known_omnibus_changes() -> None:
    by_target = {t: a for a in committed_amendments("en").values() for t in a.targets}

    assert by_target["art:5:1:ba"].action == "insert"  # intimate imagery prohibition
    assert by_target["art:5:1:bb"].action == "insert"  # CSAM prohibition
    assert by_target["art:111:4"].dates == (date(2026, 8, 2), date(2026, 12, 2))  # Art. 50(2)
    assert by_target["art:113:a"].dates == (date(2025, 2, 2), date(2026, 12, 2))
    assert by_target["art:10:5"].action == "delete"
    assert by_target["annex:XIV"].action == "add"
    assert {a.in_force_from for a in by_target.values()} == {ENTRY_INTO_FORCE}


@pytest.mark.parametrize("language", LANGUAGES)
def test_targets_exist_in_the_texts_before_and_after(language: Language) -> None:
    """New provisions exist in the consolidated text; changed or deleted ones in the original."""
    original = committed("ai-act", language)
    consolidated = committed("ai-act-consolidated", language)

    for pid, found in committed_amendments(language).items():
        texts = consolidated if found.action in ("insert", "add") else original
        missing = [t for t in found.targets if t not in texts]
        assert found.targets, pid
        assert not missing, (pid, missing)


@pytest.mark.parametrize("language", LANGUAGES)
def test_deleted_provisions_are_gone_from_the_consolidated_text(language: Language) -> None:
    consolidated = committed("ai-act-consolidated", language)
    deleted = [
        t
        for a in committed_amendments(language).values()
        if a.action == "delete"
        for t in a.targets
    ]

    assert deleted == ["art:10:5", "annex:I:A:1", "annex:VIII:B:7", "annex:VIII:B:9"]
    assert not any(t in consolidated for t in deleted)
