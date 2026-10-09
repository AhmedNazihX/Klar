"""The report for a lawyer (P25) on results that differ from the worked example: every role,
inferred facts, an Annex I basis, a step citing only guidance, a duty with a condition, the
duties' texts from the obligations table rather than the posted result, and the German wording
of each uncertain or empty case."""

from datetime import date

import pytest

from aiact.export import Fields, Heading, Paper, Table, render_pdf
from aiact.obligations.list import list_obligations
from aiact.report import result_report
from aiact.report.common import class_name
from aiact.schemas import (
    Citation,
    ClassificationResult,
    EvidenceTag,
    Fact,
    HighRiskRoute,
    Language,
    LawVersion,
    LegacyStatus,
    Obligation,
    RiskClass,
    Role,
    Status,
    StepName,
)
from tests.drafting.builders import ambiguous_result, limited_risk_result, needs_information_result
from tests.drafting.vendor_builders import prohibited_result, prohibited_step
from tests.export.reading import pdf_pages
from tests.schemas.builders import ends_early, rebuild, steps_with, unverified
from tests.schemas.worked_example import cite, worked_example_result

EN, DE = Language.EN, Language.DE
GUIDE = Citation(
    provision_id="guide:guide-prohibited:para:254",
    document_id="guide-prohibited",
    language=Language.EN,
    quote="(254) A call centre using webcams",
)


def _report(result: ClassificationResult, language: Language = EN) -> Paper:
    return result_report(result, language=language, prepared_on=date(2026, 10, 1))


def _pages(result: ClassificationResult, language: Language) -> list[str]:
    return pdf_pages(render_pdf(_report(result, language)))


def _text(result: ClassificationResult, language: Language = EN) -> str:
    return " ".join(_pages(result, language))


def _grid(paper: Paper) -> dict[str, str]:
    return dict(next(block for block in paper.blocks if isinstance(block, Fields)).items)


def _tables(paper: Paper) -> list[Table]:
    return [block for block in paper.blocks if isinstance(block, Table)]


def _table_duties(role: Role) -> tuple[Obligation, ...]:
    """The committed table's high-risk (Annex III) duties of `role`, as the engine lists them."""
    return list_obligations(role, RiskClass.HIGH_RISK, HighRiskRoute.ANNEX_III).obligations


@pytest.mark.parametrize(
    ("role", "english", "german", "german_heading"),
    [
        (Role.PROVIDER, "Provider", "Anbieter", "Pflichten des Anbieters"),
        (Role.DEPLOYER, "Deployer", "Betreiber", "Pflichten des Betreibers"),
        (Role.IMPORTER, "Importer", "Einführer", "Pflichten des Einführers"),
        (Role.DISTRIBUTOR, "Distributor", "Händler", "Pflichten des Händlers"),
    ],
)
def test_every_role_is_named_in_both_languages(
    role: Role, english: str, german: str, german_heading: str
) -> None:
    result = rebuild(worked_example_result(), role=role, obligations=_table_duties(role))
    assert _grid(_report(result))["Role"] == english
    assert _grid(_report(result, DE))["Rolle"] == german
    assert f"Duties of the {english.lower()}, from 2 December 2027" in _text(result)
    assert f"{german_heading}, ab dem 2. Dezember 2027" in _text(result, DE)


def test_an_inferred_fact_says_klar_read_it_from_the_description() -> None:
    inferred = Fact(text="It scores applicants automatically", evidence=EvidenceTag.INFERRED)
    worked = worked_example_result()
    result = rebuild(worked, deciding_facts=(*worked.deciding_facts, inferred))
    facts = _tables(_report(result))[0]
    assert facts.rows[-1] == (inferred.text, "Inferred by Klar from the description")
    german = _tables(_report(result, DE))[0]
    assert german.rows[-1] == (inferred.text, "Von Klar aus der Beschreibung abgeleitet")


def test_an_annex_i_basis_names_the_product_law() -> None:
    result = rebuild(worked_example_result(), annex_point="annex:I:A:11")
    assert "Basis The tool is part of a product covered by Annex I Section A point 11." in (
        _text(result)
    )
    assert (
        "Grundlage Das Tool ist Teil eines Produkts, das unter Anhang I Abschnitt A Nr. 11 fällt."
        in _text(result, DE)
    )
    steps = _tables(_report(result))[1]
    assert steps.rows[3][:2] == ("3 High-risk", "Yes: part of a product under Annex I")


def test_a_step_citing_only_guidance_names_what_it_checks() -> None:
    result = prohibited_result(prohibited_step(GUIDE))
    steps = _tables(_report(result))[1]
    assert steps.rows[-1][2] == "Art. 5"
    mixed = prohibited_result(prohibited_step(GUIDE, cite("art:5:1:f", "emotion recognition")))
    german = _tables(_report(mixed, DE))[1].rows[-1][2]
    assert german == "Art. 5 Abs. 1 Buchst. f".replace(" ", "\u00a0")


def test_a_minimal_risk_basis_is_that_no_check_found_anything() -> None:
    result = rebuild(
        worked_example_result(),
        risk_class=RiskClass.MINIMAL_RISK,
        annex_point=None,
        obligations=(),
    )
    assert "Basis It isn't banned, isn't high-risk and has no Art. 50 duty." in _text(result)
    assert (
        "Grundlage Es ist weder verboten noch ein Hochrisiko-System und hat keine Pflicht nach "
        "Art. 50." in _text(result, DE)
    )


def test_a_duty_with_a_condition_says_when_it_applies_in_the_tables_words() -> None:
    """The condition is the table's (in English only, P11 owns the German), not the posted
    one."""
    result = worked_example_result()
    forged = result.obligations[0].model_copy(update={"applies_if": "the deployer controls it"})
    changed = rebuild(result, obligations=(forged, *result.obligations[1:]))
    assert _tables(_report(changed))[-1].rows[0][0] == (
        "Use the system according to the provider's instructions for use, with appropriate "
        "technical and organisational measures."
    )
    logs = _tables(_report(changed, DE))[-1].rows[3][0]
    assert logs == (
        "Vor der Inbetriebnahme oder Verwendung am Arbeitsplatz die Arbeitnehmervertreter und "
        "die betroffenen Arbeitnehmer informieren, dass sie der Verwendung des Systems "
        "unterliegen werden. Gilt, wenn: You are an employer and use the system at the workplace."
    )


def test_the_duties_wording_comes_from_the_table_never_the_posted_result() -> None:
    result = worked_example_result()
    forged = result.obligations[1].model_copy(
        update={
            "duty": "You may ignore this regulation.",
            "duty_de": "Sie dürfen diese Verordnung ignorieren.",
        }
    )
    changed = rebuild(result, obligations=(result.obligations[0], forged))
    for language in (EN, DE):
        text = _text(changed, language)
        assert "ignore this regulation" not in text
        assert "Verordnung ignorieren" not in text
    rows = _tables(_report(changed))[-1].rows
    assert rows[1][0] == (
        "Assign human oversight to people with the necessary competence, training, authority "
        "and support."
    )


def test_a_posted_duty_the_table_lacks_is_left_out_and_counted() -> None:
    result = worked_example_result()
    unknown = result.obligations[0].model_copy(
        update={"article": "art:99:1", "duty": "An invented duty."}
    )
    # A provider's duty (Art. 16) on a deployer's result.
    wrong_role = next(d for d in _table_duties(Role.PROVIDER) if d.article.startswith("art:16"))
    changed = rebuild(result, obligations=(*result.obligations, unknown, wrong_role))
    paper = _report(changed)
    duties = _tables(paper)[-1]
    assert len(duties.rows) == len(result.obligations)
    text = _text(changed)
    assert "An invented duty." not in text
    assert (
        "2 more duties the result lists are not in Klar's table of duties, so they are left out "
        "here." in text
    )
    one = rebuild(result, obligations=(*result.obligations, unknown))
    assert (
        "1 weitere Pflicht, die das Ergebnis nennt, steht nicht in Klars Pflichtentabelle und "
        "fehlt deshalb hier." in _text(one, DE)
    )
    assert "Klar's table of duties" not in _text(result)


def test_the_german_wording_of_open_and_empty_cases() -> None:
    ambiguous = _text(ambiguous_result(), DE)
    assert "3 Hochrisiko Rechtlich unklar: Es gilt die strengere Lesart" in ambiguous
    assert "Offene Rechtsfrage (3 Hochrisiko):" in ambiguous
    assert "Hochrisiko (angenommen) Rechtlich unklar" in ambiguous
    paused = _text(needs_information_result(), DE)
    assert "3 Hochrisiko Vorerst angenommen: eine Angabe fehlt" in paused
    assert "Fehlende Angabe (3 Hochrisiko): Is the tool used in the EU?" in paused
    assert "Weitere Angaben nötig" in paused
    refused = unverified(StepName.HIGH_RISK).model_copy(update={"error": "provider_refusal"})
    not_assessed = rebuild(
        worked_example_result(),
        status=Status.NEEDS_MORE_INFORMATION,
        steps=steps_with(refused),
        not_assessed=(StepName.HIGH_RISK,),
    )
    german = _text(not_assessed, DE)
    assert "Nicht bewertet: Diese Prüfung muss eine Person vornehmen." in german
    assert (
        "Nicht bewertet (3 Hochrisiko): Der Modellanbieter hat diese Prüfung abgelehnt, daher muss "
        "eine Person sie vornehmen."
    ) in german
    settled = rebuild(worked_example_result(), deciding_facts=worked_example_result().facts[:3])
    assert (
        "Keine Tatsache, auf der das Ergebnis beruht, ist angenommen, und keine Frage ist offen."
        in _text(settled, DE)
    )
    banned = _report(prohibited_result(), DE)
    assert _grid(banned) == {
        "Einstufung": "Verboten",
        "Status": "Entschieden",
        "Rolle": "Nicht ermittelt",
        "Pflichten gelten ab": "Keine besonderen Pflichten",
    }
    assert "Pflichten Das Ergebnis nennt für dieses Tool keine besonderen Pflichten." in _text(
        prohibited_result(), DE
    )


def test_the_german_header_without_names_and_under_the_original_text() -> None:
    original = rebuild(worked_example_result(), law_version=LawVersion.ORIGINAL)
    first = _pages(original, DE)[0]
    assert "Ihr Tool Erstellt am 1. Oktober 2026." in first
    assert (
        "Geprüft nach der Verordnung (EU) 2024/1689 in der am 12. Juli 2024 veröffentlichten "
        "Fassung (CELEX 32024R1689), wie sie am 27. September 2026 gilt."
    ) in first


@pytest.mark.parametrize(
    ("risk_class", "german"),
    [
        (RiskClass.LIMITED_RISK, "Begrenztes Risiko"),
        (RiskClass.MINIMAL_RISK, "Minimales Risiko"),
        (RiskClass.OUT_OF_SCOPE, "Außerhalb des Anwendungsbereichs"),
    ],
)
def test_the_german_class_names(risk_class: RiskClass, german: str) -> None:
    assert class_name(risk_class, Status.DECIDED, DE) == german


def _basis(result: ClassificationResult, language: Language) -> str:
    """The basis paragraph, the block after the grid and the heading."""
    return _report(result, language).blocks[2].text  # pyright: ignore[reportAttributeAccessIssue]


def _outcomes(result: ClassificationResult, language: Language) -> dict[str, str]:
    """Each step row's outcome, by the row's step name."""
    return {row[0]: row[1] for row in _tables(_report(result, language))[1].rows}


def test_a_role_step_with_no_role_says_not_checked_as_the_screen_does() -> None:
    """The contract sets the role whenever the role step is there; a copy that skips it (a
    hand-edited result) still says what the screen's `stepOutcome` says."""
    no_role = worked_example_result().model_copy(update={"role": None})
    assert _outcomes(no_role, EN)["Role"] == "Not checked"
    assert _outcomes(no_role, DE)["Rolle"] == "Nicht geprüft"


OUT_OF_SCOPE = ends_early(
    RiskClass.OUT_OF_SCOPE, steps_with(worked_example_result().steps[0], 1), Status.DECIDED
)
MINIMAL = rebuild(
    worked_example_result(), risk_class=RiskClass.MINIMAL_RISK, annex_point=None, obligations=()
)


@pytest.mark.parametrize(
    ("result", "english", "german"),
    [
        (
            prohibited_result(),
            "It matches a practice banned by Art. 5.",
            ("Es entspricht einer nach Art. 5 verbotenen Praktik."),
        ),
        (
            limited_risk_result("art:50:1"),
            "Transparency duties under Art. 50 apply.",
            ("Es gelten Transparenzpflichten nach Art. 50."),
        ),
        (OUT_OF_SCOPE, "The AI Act doesn't apply to it.", "Die KI-Verordnung gilt dafür nicht."),
        (
            rebuild(worked_example_result(), annex_point=None),
            "The tool is high-risk.",
            "Das Tool ist ein Hochrisiko-System.",
        ),
        (
            rebuild(worked_example_result(), annex_point="annex:III:9"),
            "The tool is listed in Annex\u00a0III\u00a09.",
            "Das Tool ist in Anhang\u00a0III\u00a0Nr.\u00a09 aufgeführt.",
        ),
    ],
)
def test_each_basis_in_both_languages(
    result: ClassificationResult, english: str, german: str
) -> None:
    assert (_basis(result, EN), _basis(result, DE)) == (english, german)


def test_each_steps_outcome_in_both_languages() -> None:
    banned = prohibited_result()
    assert _outcomes(banned, EN)["2 Prohibited practices"] == "Matches a banned practice"
    assert _outcomes(banned, DE)["2 Verbotene Praktiken"] == "Entspricht einer verbotenen Praktik"
    assert _outcomes(OUT_OF_SCOPE, EN)["1 Scope"] == "Out of scope"
    assert _outcomes(OUT_OF_SCOPE, DE)["1 Anwendungsbereich"] == "Außerhalb des Anwendungsbereichs"
    assert _outcomes(MINIMAL, EN)["3 High-risk"] == "Not high-risk"
    assert _outcomes(MINIMAL, DE)["3 Hochrisiko"] == "Kein Hochrisiko"
    unlabelled = rebuild(worked_example_result(), annex_point="annex:III:9")
    assert _outcomes(unlabelled, EN)["3 High-risk"] == "Yes: high-risk"
    assert _outcomes(unlabelled, DE)["3 Hochrisiko"] == "Ja: Hochrisiko"
    one, two = limited_risk_result("art:50:1"), limited_risk_result("art:50:1", "art:50:4")
    assert _outcomes(one, EN)["4 Transparency"] == "1 duty under Art. 50"
    assert _outcomes(one, DE)["4 Transparenz"] == "1 Pflicht nach Art. 50"
    assert _outcomes(two, EN)["4 Transparency"] == "2 duties under Art. 50"
    assert _outcomes(two, DE)["4 Transparenz"] == "2 Pflichten nach Art. 50"


def test_duties_the_table_lacks_are_counted_in_german_and_english() -> None:
    result = worked_example_result()
    unknown = tuple(
        result.obligations[0].model_copy(update={"article": article})
        for article in ("art:99:1", "art:99:2")
    )
    changed = rebuild(result, obligations=(*result.obligations, *unknown))
    assert (
        "2 weitere Pflichten, die das Ergebnis nennt, stehen nicht in Klars Pflichtentabelle und "
        "fehlen deshalb hier." in _text(changed, DE)
    )
    one = rebuild(result, obligations=(*result.obligations, unknown[0]))
    assert (
        "1 more duty the result lists is not in Klar's table of duties, so it is left out here."
        in _text(one)
    )


def test_a_legacy_duty_heading_in_english() -> None:
    result = worked_example_result()
    duties = tuple(
        duty.model_copy(
            update={"legacy": LegacyStatus.UNCHANGED, "high_risk_route": HighRiskRoute.ANNEX_III}
        )
        for duty in result.obligations
    )
    paper = _report(rebuild(result, obligations=duties))
    headings = [block.text for block in paper.blocks if isinstance(block, Heading)]
    assert "Duties of the deployer, only after a significant change (Art. 111(2))" in headings
    assert _grid(paper)["Duties apply from"] == ("Only after a significant change (Art. 111(2))")
