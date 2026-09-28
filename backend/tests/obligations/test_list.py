"""`list_obligations` against the committed table, checked by hand against the consolidated AI Act.

Dates: Art. 113(c)(i) 2 Dec 2027 (Annex III), 113(c)(ii) 2 Aug 2028 (Annex I), 113(a) 2 Feb 2025
(Chapters I, II) and 2 Dec 2026 (Art. 5(1)(ba), (bb)), 113 second paragraph 2 Aug 2026 (Art. 50).
"""

import json
from datetime import date
from pathlib import Path

import pytest

from aiact.obligations.list import (
    ObligationsError,
    ObligationTable,
    UnknownLawVersionError,
    default_table,
    list_obligations,
    load_table,
)
from aiact.schemas import HighRiskRoute, LawVersion, Obligation, RiskClass, Role
from aiact.settings import DEFAULT_DATA_DIR

ANNEX_III_FROM = date(2027, 12, 2)
ANNEX_I_FROM = date(2028, 8, 2)
ART_50_FROM = date(2026, 8, 2)
CHAPTER_I_II_FROM = date(2025, 2, 2)
NEW_PROHIBITIONS_FROM = date(2026, 12, 2)
CONSOLIDATED_EN = DEFAULT_DATA_DIR / "parsed" / "ai-act-consolidated.en.jsonl"


def _list(
    role: Role | str,
    risk_class: RiskClass | str,
    route: HighRiskRoute | None = None,
    table: ObligationTable | None = None,
) -> tuple[Obligation, ...]:
    return list_obligations(role, risk_class, route, table=table).obligations


def _articles(obligations: tuple[Obligation, ...]) -> list[str]:
    return [obligation.article for obligation in obligations]


def _by_article(obligations: tuple[Obligation, ...]) -> dict[str, Obligation]:
    return {obligation.article: obligation for obligation in obligations}


def test_deployer_high_risk_annex_iii_gets_the_art_26_duties_from_2_dec_2027() -> None:
    duties = _list(Role.DEPLOYER, RiskClass.HIGH_RISK, HighRiskRoute.ANNEX_III)
    assert _articles(duties) == [
        "art:4:1",
        "art:26:1",
        "art:26:2",
        "art:26:4",
        "art:26:5",
        "art:26:6",
        "art:26:7",
        "art:26:8",
        "art:26:9",
        "art:26:10",
        "art:26:11",
        "art:26:12",
        "art:27:1",
        "art:86:1",
        "art:50:3",
        "art:50:4",
    ]
    art_26 = [d for d in duties if d.article.startswith(("art:26:", "art:27:", "art:86:"))]
    assert {d.applies_from for d in art_26} == {ANNEX_III_FROM}
    assert not any(d.is_informational for d in duties)
    # The worked example's duties (INIT > How it works) apply to every deployer of the system.
    unconditional = {d.article for d in art_26 if d.applies_if is None}
    assert {"art:26:1", "art:26:2", "art:26:6"} <= unconditional
    by_article = _by_article(duties)
    assert by_article["art:26:7"].applies_if is not None  # employers at the workplace
    assert by_article["art:26:11"].applies_if is not None  # decisions about people


def test_deployer_high_risk_annex_i_has_later_dates_and_no_annex_iii_only_duties() -> None:
    duties = _list(Role.DEPLOYER, RiskClass.HIGH_RISK, HighRiskRoute.ANNEX_I)
    articles = _articles(duties)
    assert "art:26:1" in articles
    # Art. 26(8) via Art. 49(3), 26(10), 26(11), 27(1) and 86(1) are limited to Annex III systems.
    assert not {"art:26:8", "art:26:10", "art:26:11", "art:27:1", "art:86:1"} & set(articles)
    art_26 = [d for d in duties if d.article.startswith("art:26:")]
    assert {d.applies_from for d in art_26} == {ANNEX_I_FROM}
    assert {d.high_risk_route for d in art_26} == {HighRiskRoute.ANNEX_I}


def test_high_risk_without_a_route_lists_route_dependent_duties_once_per_route() -> None:
    duties = _list(Role.DEPLOYER, RiskClass.HIGH_RISK)
    art_26_1 = [d for d in duties if d.article == "art:26:1"]
    assert [(d.high_risk_route, d.applies_from) for d in art_26_1] == [
        (HighRiskRoute.ANNEX_I, ANNEX_I_FROM),
        (HighRiskRoute.ANNEX_III, ANNEX_III_FROM),
    ]
    assert len([d for d in duties if d.article == "art:4:1"]) == 1


def test_provider_high_risk_gets_art_16_and_the_duties_it_points_to() -> None:
    duties = _list(Role.PROVIDER, RiskClass.HIGH_RISK, HighRiskRoute.ANNEX_III)
    articles = _articles(duties)
    art_16 = [f"art:16:{point}" for point in "abcdefghijkl"]
    assert set(art_16) <= set(articles)
    assert {"art:11:1", "art:22:1", "art:72:1", "art:73:1", "art:50:1", "art:50:2"} <= set(articles)
    high_risk = [d for d in duties if not d.article.startswith(("art:4:", "art:50:"))]
    assert {d.applies_from for d in high_risk} == {ANNEX_III_FROM}
    by_article = _by_article(duties)
    assert by_article["art:22:1"].applies_if is not None  # providers outside the Union


def test_provider_high_risk_relief_for_smes_and_small_mid_caps() -> None:
    by_article = _by_article(_list(Role.PROVIDER, RiskClass.HIGH_RISK, HighRiskRoute.ANNEX_III))
    for article in ("art:16:c", "art:11:1"):
        relief = by_article[article].relief_note
        assert relief is not None
        assert "SMC" in relief
        assert "SME" in relief
    assert by_article["art:16:a"].relief_note is None


def test_provider_registration_in_the_eu_database_is_annex_iii_only() -> None:
    annex_i = _articles(_list(Role.PROVIDER, RiskClass.HIGH_RISK, HighRiskRoute.ANNEX_I))
    assert "art:16:i" not in annex_i
    assert "art:16:a" in annex_i


def test_limited_risk_transparency_duties_apply_from_2_aug_2026() -> None:
    provider = _list(Role.PROVIDER, RiskClass.LIMITED_RISK)
    deployer = _list(Role.DEPLOYER, RiskClass.LIMITED_RISK)
    assert _articles(provider) == ["art:4:1", "art:50:1", "art:50:2", "art:6:4"]
    assert _articles(deployer) == ["art:4:1", "art:50:3", "art:50:4"]
    transparency = [d for d in provider + deployer if d.article.startswith("art:50:")]
    assert {d.applies_from for d in transparency} == {ART_50_FROM}
    assert all(d.applies_if for d in transparency)  # each duty needs its kind of system
    marking = _by_article(provider)["art:50:2"]
    assert marking.note is not None
    assert "2 December 2026" in marking.note  # Art. 111(4) grace period


def test_transparency_duties_stack_on_high_risk() -> None:
    articles = _articles(_list(Role.PROVIDER, RiskClass.HIGH_RISK))
    assert {"art:50:1", "art:50:2"} <= set(articles)


def test_importer_high_risk_gets_art_23() -> None:
    duties = _list(Role.IMPORTER, RiskClass.HIGH_RISK, HighRiskRoute.ANNEX_III)
    assert _articles(duties) == [f"art:23:{paragraph}" for paragraph in range(1, 8)]
    assert {d.applies_from for d in duties} == {ANNEX_III_FROM}


def test_distributor_high_risk_gets_art_24() -> None:
    duties = _list(Role.DISTRIBUTOR, RiskClass.HIGH_RISK, HighRiskRoute.ANNEX_I)
    assert _articles(duties) == [f"art:24:{paragraph}" for paragraph in range(1, 7)]
    assert {d.applies_from for d in duties} == {ANNEX_I_FROM}


@pytest.mark.parametrize("role", [Role.IMPORTER, Role.DISTRIBUTOR])
@pytest.mark.parametrize("risk_class", [RiskClass.LIMITED_RISK, RiskClass.MINIMAL_RISK])
def test_importers_and_distributors_have_no_duties_below_high_risk(
    role: Role, risk_class: RiskClass
) -> None:
    assert _list(role, risk_class) == ()


def test_minimal_risk_brings_only_ai_literacy_and_the_art_6_3_registration() -> None:
    assert _articles(_list(Role.DEPLOYER, RiskClass.MINIMAL_RISK)) == ["art:4:1"]
    provider = _list(Role.PROVIDER, RiskClass.MINIMAL_RISK)
    assert _articles(provider) == ["art:4:1", "art:6:4"]
    assert provider[0].applies_from == CHAPTER_I_II_FROM


def test_deployer_right_to_explanation_is_conditional_with_the_chapter_ix_note() -> None:
    by_article = _by_article(_list(Role.DEPLOYER, RiskClass.HIGH_RISK, HighRiskRoute.ANNEX_III))
    explanation = by_article["art:86:1"]
    assert explanation.applies_from == ANNEX_III_FROM
    assert explanation.high_risk_route is HighRiskRoute.ANNEX_III
    assert explanation.applies_if is not None
    assert "legal effects" in explanation.applies_if
    assert "point 2" in explanation.applies_if
    assert explanation.note is not None
    assert "Chapter IX" in explanation.note


def test_deployer_post_remote_biometric_identification_is_conditional() -> None:
    by_article = _by_article(_list(Role.DEPLOYER, RiskClass.HIGH_RISK, HighRiskRoute.ANNEX_III))
    biometric = by_article["art:26:10"]
    assert biometric.applies_from == ANNEX_III_FROM
    assert biometric.applies_if is not None
    assert "post-remote biometric identification" in biometric.applies_if
    assert "law enforcement" in biometric.applies_if


def test_chapter_ix_duties_keep_the_high_risk_dates_with_a_note() -> None:
    by_article = _by_article(_list(Role.PROVIDER, RiskClass.HIGH_RISK, HighRiskRoute.ANNEX_I))
    for article in ("art:72:1", "art:73:1"):
        assert by_article[article].applies_from == ANNEX_I_FROM
        note = by_article[article].note
        assert note is not None
        assert "2 August 2026" in note


def test_art_6_4_keeps_2_dec_2027_and_flags_the_literal_reading() -> None:
    exemption = _by_article(_list(Role.PROVIDER, RiskClass.MINIMAL_RISK))["art:6:4"]
    assert exemption.applies_from == ANNEX_III_FROM
    assert exemption.note is not None
    assert "2 August 2026" in exemption.note
    assert "lawyer" in exemption.note


def test_distributor_of_a_prohibited_system_gets_information_not_a_duty() -> None:
    rows = _list(Role.DISTRIBUTOR, RiskClass.PROHIBITED)
    assert [(d.article, d.applies_from) for d in rows] == [
        ("art:5:1", CHAPTER_I_II_FROM),
        ("art:5:1:ba", NEW_PROHIBITIONS_FROM),
        ("art:5:1:bb", NEW_PROHIBITIONS_FROM),
    ]
    assert all(d.is_informational for d in rows)
    assert all("don't supply it" in d.duty for d in rows)
    formal = _list(Role.DEPLOYER, RiskClass.PROHIBITED)
    assert not any(d.is_informational for d in formal)


def test_the_dates_have_been_reviewed() -> None:
    assert load_table().dates_reviewed is True


def test_prohibited_dates_follow_art_113_a() -> None:
    duties = _list(Role.DEPLOYER, RiskClass.PROHIBITED)
    assert [(d.article, d.applies_from) for d in duties] == [
        ("art:5:1", CHAPTER_I_II_FROM),
        ("art:5:1:ba", NEW_PROHIBITIONS_FROM),
        ("art:5:1:bb", NEW_PROHIBITIONS_FROM),
    ]


@pytest.mark.parametrize("role", list(Role))
def test_out_of_scope_has_no_obligations(role: Role) -> None:
    assert _list(role, RiskClass.OUT_OF_SCOPE) == ()


def test_every_row_cites_an_article_of_the_consolidated_act() -> None:
    provision_ids = {
        json.loads(line)["provision_id"]
        for line in CONSOLIDATED_EN.read_text(encoding="utf-8").splitlines()
    }
    rows = load_table().rows()
    assert rows
    missing = sorted({row.obligation.article for row in rows} - provision_ids)
    assert missing == []
    assert all(row.obligation.article.startswith("art:") for row in rows)


# --- Loader rules -----------------------------------------------------------------------------

ENTRY = {
    "key": "a-duty",
    "roles": ["provider"],
    "risk_classes": ["high_risk"],
    "duty": "Do something.",
    "article": "art:16:a",
    "applies_from": {"annex_iii": "2027-12-02"},
}


def _table(*entries: dict[str, object]) -> dict[str, object]:
    return {
        "law_version": "amended",
        "checked_on": "2026-09-28",
        "dates_reviewed": False,
        "obligations": list(entries),
    }


def test_a_custom_table_is_used_when_given() -> None:
    table = ObligationTable.model_validate(_table(ENTRY))
    duties = _list(Role.PROVIDER, RiskClass.HIGH_RISK, table=table)
    assert duties == (
        Obligation(
            duty="Do something.",
            article="art:16:a",
            applies_from=ANNEX_III_FROM,
            high_risk_route=HighRiskRoute.ANNEX_III,
        ),
    )


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"risk_classes": ["high_risk", "limited_risk"]}, "only for high-risk-only"),
        ({"applies_from": {}}, "at least one route"),
        ({"risk_classes": ["out_of_scope"], "applies_from": "2026-08-02"}, "out_of_scope"),
        ({"article": "annex:III:4:a"}, "article"),
        ({"roles": []}, "roles"),
    ],
)
def test_invalid_entries_are_rejected(change: dict[str, object], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        ObligationTable.model_validate(_table(ENTRY | change)).rows()


@pytest.mark.parametrize(
    "change",
    [{"roles": ["provider", "provider"]}, {"risk_classes": ["high_risk", "high_risk"]}],
)
def test_repeated_roles_or_classes_are_rejected(change: dict[str, object]) -> None:
    with pytest.raises(ValueError, match="repeated value"):
        ObligationTable.model_validate(_table(ENTRY | change))


def test_the_default_law_version_is_amended_and_travels_with_the_result() -> None:
    result = list_obligations(Role.DEPLOYER, RiskClass.HIGH_RISK, HighRiskRoute.ANNEX_III)
    assert result.law_version is LawVersion.AMENDED
    assert "art:26:1" in _articles(result.obligations)
    assert default_table().law_version is LawVersion.AMENDED


@pytest.mark.parametrize("law_version", [LawVersion.ORIGINAL, "original"])
def test_a_law_version_the_table_does_not_hold_raises(law_version: LawVersion | str) -> None:
    with pytest.raises(UnknownLawVersionError, match="not original"):
        list_obligations(Role.DEPLOYER, RiskClass.HIGH_RISK, law_version=law_version)


def test_plain_strings_work_like_the_enums() -> None:
    assert list_obligations("deployer", "high_risk", "annex_iii", "amended") == list_obligations(
        Role.DEPLOYER, RiskClass.HIGH_RISK, HighRiskRoute.ANNEX_III, LawVersion.AMENDED
    )


@pytest.mark.parametrize(
    ("role", "risk_class"), [("auditor", "high_risk"), ("deployer", "very_high_risk")]
)
def test_unknown_role_or_class_strings_raise(role: str, risk_class: str) -> None:
    with pytest.raises(ValueError, match="is not a valid"):
        list_obligations(role, risk_class)


def test_duplicate_keys_are_rejected() -> None:
    with pytest.raises(ValueError, match="duplicate obligation keys: a-duty"):
        ObligationTable.model_validate(_table(ENTRY, ENTRY))


def test_load_table_reports_a_missing_or_invalid_file(tmp_path: Path) -> None:
    with pytest.raises(ObligationsError, match="cannot read"):
        load_table(tmp_path / "missing.yaml")
    bad = tmp_path / "bad.yaml"
    bad.write_text("law_version: amended\n", encoding="utf-8")
    with pytest.raises(ObligationsError, match="invalid obligations file"):
        load_table(bad)
