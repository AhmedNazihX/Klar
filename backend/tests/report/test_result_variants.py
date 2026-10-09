"""The report for a lawyer (P25) on results that differ from the worked example: every role,
inferred facts, an Annex I basis, a step citing only guidance, a duty with a condition, and the
German wording of each uncertain or empty case."""

from datetime import date

import pytest

from aiact.export import Fields, Paper, Table, render_pdf
from aiact.report import result_report
from aiact.report.common import class_name
from aiact.schemas import (
    Citation,
    ClassificationResult,
    EvidenceTag,
    Fact,
    Language,
    LawVersion,
    RiskClass,
    Role,
    Status,
    StepName,
)
from tests.drafting.builders import ambiguous_result, needs_information_result
from tests.drafting.vendor_builders import prohibited_result, prohibited_step
from tests.export.reading import pdf_pages
from tests.schemas.builders import rebuild, steps_with, unverified
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
    result = rebuild(worked_example_result(), role=role)
    assert _grid(_report(result))["Role"] == english
    assert _grid(_report(result, DE))["Rolle"] == german
    assert f"Duties of the {english.lower()}, from 2 December 2027" in _text(result)
    assert f"{german_heading}, ab dem 2. Dezember 2027" in _text(result, DE)


def test_an_inferred_fact_says_klar_read_it_from_the_description() -> None:
    inferred = Fact(text="It scores applicants automatically", evidence=EvidenceTag.INFERRED)
    result = rebuild(worked_example_result(), facts=(*worked_example_result().facts, inferred))
    facts = _tables(_report(result))[0]
    assert facts.rows[-1] == (inferred.text, "Inferred by Klar from the description")
    german = _tables(_report(result, DE))[0]
    assert german.rows[-1] == (inferred.text, "Von Klar aus der Beschreibung abgeleitet")


def test_an_annex_i_basis_names_the_product_law() -> None:
    result = rebuild(worked_example_result(), annex_point="annex:I:A:11")
    assert "A product, or a safety component of one, covered by Annex I Section A point 11." in (
        _text(result)
    )
    assert (
        "Ein Produkt oder Sicherheitsbauteil eines Produkts nach Anhang I Abschnitt A Nummer 11."
        in (_text(result, DE))
    )


def test_a_step_citing_only_guidance_names_what_it_checks() -> None:
    result = prohibited_result(prohibited_step(GUIDE))
    steps = _tables(_report(result))[1]
    assert steps.rows[-1][2] == "Art. 5"
    mixed = prohibited_result(prohibited_step(GUIDE, cite("art:5:1:f", "emotion recognition")))
    assert _tables(_report(mixed, DE))[1].rows[-1][2] == "Art. 5 Abs. 1 Buchst. f"


def test_a_minimal_risk_basis_is_that_no_check_found_anything() -> None:
    result = rebuild(
        worked_example_result(),
        risk_class=RiskClass.MINIMAL_RISK,
        annex_point=None,
        obligations=(),
    )
    assert (
        "Basis Not prohibited, not high-risk, and no transparency duty under Art. 50 applies."
        in (_text(result))
    )
    assert (
        "Grundlage Nicht verboten, kein Hochrisiko, und keine Transparenzpflicht nach Art. 50 "
        "greift." in _text(result, DE)
    )


def test_a_duty_with_a_condition_says_when_it_applies() -> None:
    result = worked_example_result()
    conditional = result.obligations[0].model_copy(
        update={"applies_if": "the deployer controls it"}
    )
    changed = rebuild(result, obligations=(conditional, *result.obligations[1:]))
    assert _tables(_report(changed))[-1].rows[0][0] == (
        "Use the system according to the provider's instructions Applies if: the deployer "
        "controls it"
    )
    assert _tables(_report(changed, DE))[-1].rows[0][0] == (
        "Das System gemäß der Betriebsanleitung verwenden. Gilt, wenn: the deployer controls it"
    )


def test_the_german_wording_of_open_and_empty_cases() -> None:
    ambiguous = _text(ambiguous_result(), DE)
    assert "Das Recht lässt dies offen; die strengere Lesart wird angewandt." in ambiguous
    assert "Offene Rechtsfrage (3 Hochrisiko):" in ambiguous
    assert "Hochrisiko (angenommen) Rechtlich unklar" in ambiguous
    paused = _text(needs_information_result(), DE)
    assert "Angenommen, bis eine fehlende Angabe bestätigt ist." in paused
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
