"""The EUR-Lex parser: hand-made excerpts of both layouts, and the committed `data/parsed/`."""

import hashlib
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from aiact import cli
from aiact.corpus.eurlex import (
    DEFAULT_PARSED_DIR,
    ParsedProvision,
    ParseError,
    RawFileError,
    html_entries,
    load_jsonl,
    parse_all,
    parse_document,
)
from aiact.corpus.fetch import DEFAULT_MANIFEST
from aiact.corpus.sources import Language
from aiact.settings import get_settings

FIXTURES = Path(__file__).parent.parent / "fixtures" / "eurlex"
LANGUAGES: tuple[Language, ...] = ("en", "de")
PARSED_DOCS = ("ai-act", "omnibus", "ai-act-consolidated")


def parse_fixture(name: str, language: Language) -> dict[str, ParsedProvision]:
    """An amending fixture (the Omnibus) resolves against the `oj` fixture's AI Act ids."""
    content = (FIXTURES / f"{name}.{language}.html").read_bytes()
    ai_act_ids = frozenset(parse_fixture("oj", language)) if name == "omnibus" else frozenset()
    return {row.provision_id: row for row in parse_document(content, name, language, ai_act_ids)}


# --- Official Journal layout -------------------------------------------------------------------


@pytest.mark.parametrize("language", LANGUAGES)
def test_oj_layout_gives_article_paragraph_point_annex_and_recital_ids(language: Language) -> None:
    rows = parse_fixture("oj", language)

    assert list(rows) == [
        "recital:53",
        "art:3",
        "art:3:1",
        "art:3:14",
        "art:5",
        "art:5:1",
        "art:5:1:a",
        "art:5:1:c",
        "art:5:1:c:i",
        "art:5:2",
        "art:43",
        "art:43:1",
        "art:43:1:a",
        "art:43:1:sub2:a",
        "art:43:1:sub2:b",
        "art:43:1:sub2:c",
        "annex:I",
        "annex:I:A",
        "annex:I:A:1",
        "annex:I:B",
        "annex:I:B:13",
        "annex:III",
        "annex:III:4",
        "annex:III:4:a",
        "annex:VI",
        "annex:VI:1",
    ]
    assert rows["art:5:1"].kind == "paragraph"
    assert rows["art:5:1:c:i"].parent_id == "art:5:1:c"
    assert rows["annex:I:B:13"].parent_id == "annex:I:B"


def test_oj_layout_texts_headings_and_labels() -> None:
    en, de = parse_fixture("oj", "en"), parse_fixture("oj", "de")

    assert en["art:5:1"].text == (
        "The following AI practices shall be prohibited:\n"
        "(a) the use of an AI system that deploys subliminal techniques;\n"
        "(c) social scoring leading to either or both of the following:\n"
        "(i) detrimental treatment in unrelated social contexts;"
    )
    assert de["art:5:1:c"].text.endswith("i) Schlechterstellung in sozialen Zusammenhängen;")
    assert en["art:5:1:a"].heading == "Article 5 — Prohibited AI practices"
    assert de["annex:III:4:a"].heading == (
        "ANHANG III — Hochrisiko-KI-Systeme gemäß Artikel 6 Absatz 2"
    )
    assert en["recital:53"].heading is None
    assert en["recital:53"].text.startswith("It is also important")


def test_footnote_references_and_bodies_are_left_out() -> None:
    rows = parse_fixture("oj", "en")

    assert rows["art:3:14"].text.endswith("means a component of a product;")
    assert "footnote" not in rows["art:3"].text


@pytest.mark.parametrize("language", LANGUAGES)
def test_a_restarted_list_goes_under_its_subparagraph_as_a_whole(language: Language) -> None:
    """Art. 43(1): list one is (a); list two is (a)-(c), so its (b) and (c) are sub2 too, even
    though list one has no (b) or (c)."""
    rows = parse_fixture("oj", language)
    points = [pid for pid in rows if pid.startswith("art:43:1:")]

    assert points == ["art:43:1:a", "art:43:1:sub2:a", "art:43:1:sub2:b", "art:43:1:sub2:c"]
    assert all(rows[pid].parent_id == "art:43:1" for pid in points)


def test_committed_art_43_1_second_list_is_under_sub2() -> None:
    rows = committed("ai-act", "en")
    points = [pid for pid in rows if pid.startswith("art:43:1:")]

    assert points == ["art:43:1:a", "art:43:1:b"] + [f"art:43:1:sub2:{x}" for x in "abcd"]


def test_oj_layout_first_paragraph_line_loses_its_number() -> None:
    en, de = parse_fixture("oj", "en"), parse_fixture("oj", "de")

    assert en["art:5:2"].text == "The use of those systems shall be authorised."
    assert de["art:5:2"].text == "Die Verwendung dieser Systeme wird genehmigt."


# --- Consolidated layout -----------------------------------------------------------------------


@pytest.mark.parametrize("language", LANGUAGES)
def test_consolidated_layout_folds_flat_subparagraphs_into_their_paragraph(
    language: Language,
) -> None:
    rows = parse_fixture("consolidated", language)

    assert list(rows) == [
        "art:6",
        "art:6:1a",
        "art:6:3",
        "art:6:3:a",
        "art:6:3:b",
        "art:6:4",
        "annex:VII",
        "annex:VII:3",
        "annex:VII:3:1",
        "annex:VII:3:1:a",
        "annex:VII:3:2",
    ]
    assert rows["art:6:3:a"].parent_id == "art:6:3"
    assert rows["annex:VII:3:1:a"].parent_id == "annex:VII:3:1"


def test_consolidated_layout_drops_amendment_markers_and_footnote_references() -> None:
    rows = parse_fixture("consolidated", "en")

    article = rows["art:6"].text
    assert "▼" not in article
    assert "—————" not in article
    assert rows["art:6:3"].text.endswith("where it performs profiling.")
    assert rows["art:6:1a"].text.startswith("For the purposes of this Regulation")


def test_dash_items_stay_in_their_parents_text() -> None:
    rows = parse_fixture("consolidated", "en")

    assert rows["annex:VII:3:2"].text == "The quality management system shall be assessed.\n— rape,"


# --- Both languages ----------------------------------------------------------------------------


@pytest.mark.parametrize("name", ["oj", "consolidated", "omnibus"])
def test_fixture_provision_ids_are_the_same_in_english_and_german(name: str) -> None:
    assert list(parse_fixture(name, "en")) == list(parse_fixture(name, "de"))


def test_a_duplicate_id_is_an_error() -> None:
    html = b"""<html><body>
    <div id="art_1"><p class="oj-normal">Text.</p></div>
    <div id="art_1"><p class="oj-normal">Again.</p></div>
    </body></html>"""

    with pytest.raises(ParseError, match="duplicate provision_id art:1"):
        parse_document(html, "law", "en")


def test_a_document_without_provisions_is_an_error() -> None:
    with pytest.raises(ParseError, match="no articles"):
        parse_document(b"<html><body><p>Nothing</p></body></html>", "law", "en")


# --- parse_all and the CLI ---------------------------------------------------------------------


def write_manifest(tmp_path: Path, entries: list[dict[str, object]]) -> Path:
    path = tmp_path / "manifest.yaml"
    path.write_text(yaml.safe_dump({"documents": entries}), encoding="utf-8")
    return path


def html_entry(doc: str, language: str, raw: Path, available: bool | None = True) -> dict:
    content = (raw / f"{doc}.{language}.html").read_bytes()
    return {
        "id": doc,
        "language": language,
        "title": doc,
        "kind": "html",
        "status": "law",
        "version": "2024-07-12",
        "source_page": "https://eur-lex.example",
        "url": "https://cellar.example",
        "available": available,
        "file": f"{doc}.{language}.html" if available else None,
        "sha256": hashlib.sha256(content).hexdigest() if available else None,
    }


@pytest.fixture
def raw_dir(tmp_path: Path) -> Path:
    raw = tmp_path / "raw"
    raw.mkdir()
    for language in LANGUAGES:
        for doc, fixture in (("ai-act", "oj"), ("omnibus", "omnibus")):
            content = (FIXTURES / f"{fixture}.{language}.html").read_bytes()
            (raw / f"{doc}.{language}.html").write_bytes(content)
    return raw


def test_parse_all_writes_one_file_per_document_and_language_and_is_idempotent(
    tmp_path: Path, raw_dir: Path
) -> None:
    entries = [html_entry(d, lang, raw_dir) for d in ("omnibus", "ai-act") for lang in LANGUAGES]
    manifest = write_manifest(tmp_path, entries)
    out = tmp_path / "parsed"

    first = parse_all(manifest, raw_dir, out)
    second = parse_all(manifest, raw_dir, out)

    assert sorted(p.name for p in out.iterdir()) == [
        "ai-act.de.jsonl",
        "ai-act.en.jsonl",
        "omnibus.de.jsonl",
        "omnibus.en.jsonl",
    ]
    assert len(first.written) == 4
    assert second.written == ()
    assert [label for label, _ in first.counts] == [
        "omnibus.en",
        "omnibus.de",
        "ai-act.en",
        "ai-act.de",
    ]


def test_parse_all_resolves_omnibus_targets_against_the_ai_act_parsed_first(
    tmp_path: Path, raw_dir: Path
) -> None:
    """The fixture AI Act has Article 5(1), so German `Absatz 1` resolves under it."""
    entries = [html_entry(d, lang, raw_dir) for d in ("omnibus", "ai-act") for lang in LANGUAGES]
    out = tmp_path / "parsed"
    parse_all(write_manifest(tmp_path, entries), raw_dir, out)

    rows = {r.provision_id: r for r in load_jsonl(out / "omnibus.de.jsonl")}
    amendment = rows["art:1:2:a"].amendment
    assert amendment is not None
    assert amendment.targets == ("art:5:1:ba", "art:5:1:bb")


def test_parse_all_rejects_a_raw_file_that_changed(tmp_path: Path, raw_dir: Path) -> None:
    manifest = write_manifest(tmp_path, [html_entry("ai-act", "en", raw_dir)])
    (raw_dir / "ai-act.en.html").write_bytes(b"<html>changed</html>")

    with pytest.raises(RawFileError, match="sha256 differs"):
        parse_all(manifest, raw_dir, tmp_path / "parsed")


def test_a_failed_fetch_is_an_error_but_an_absent_language_is_skipped(
    tmp_path: Path, raw_dir: Path
) -> None:
    absent = html_entry("ai-act", "de", raw_dir, available=False)
    failed = html_entry("omnibus", "de", raw_dir, available=None)

    assert html_entries(write_manifest(tmp_path, [absent])) == ()
    with pytest.raises(RawFileError, match=r"fetch failed for omnibus\.de"):
        html_entries(write_manifest(tmp_path, [absent, failed]))


def test_cli_parse_prints_counts_and_fails_cleanly(tmp_path: Path, raw_dir: Path) -> None:
    manifest = write_manifest(tmp_path, [html_entry("ai-act", "en", raw_dir)])
    runner = CliRunner()
    args = ["corpus", "parse", "--manifest", str(manifest), "--raw-dir", str(raw_dir)]

    ok = runner.invoke(cli.app, [*args, "--out-dir", str(tmp_path / "out")])
    (raw_dir / "ai-act.en.html").write_bytes(b"<html>changed</html>")
    failed = runner.invoke(cli.app, [*args, "--out-dir", str(tmp_path / "out")])

    assert ok.exit_code == 0, ok.output
    assert "ai-act.en: 26 provisions" in ok.output
    assert failed.exit_code == 1
    assert "sha256 differs" in failed.output


# --- The committed output (DoD) ----------------------------------------------------------------


def committed(doc: str, language: Language) -> dict[str, ParsedProvision]:
    return {r.provision_id: r for r in load_jsonl(DEFAULT_PARSED_DIR / f"{doc}.{language}.jsonl")}


KNOWN_PROVISIONS: dict[str, dict[Language, str]] = {
    "art:5:1:a": {
        "en": "deploys subliminal techniques beyond a person\u2019s consciousness",
        "de": "Techniken der unterschwelligen Beeinflussung außerhalb des Bewusstseins",
    },
    "art:6:3": {
        "en": "shall not be considered to be high-risk where it does not pose a significant risk",
        "de": "gilt ein in Anhang III genanntes KI-System nicht als hochriskant",
    },
    "annex:III:4:a": {
        "en": "used for the recruitment or selection of natural persons",
        "de": "für die Einstellung oder Auswahl natürlicher Personen",
    },
    "art:50:2": {
        "en": "generating synthetic audio, image, video or text content, shall ensure",
        "de": "die synthetische Audio-, Bild-, Video- oder Textinhalte erzeugen",
    },
    "recital:53": {
        "en": "do not materially influence the decision-making",
        "de": "da sie die Entscheidungsfindung nicht wesentlich beeinflussen",
    },
}


@pytest.mark.parametrize("language", LANGUAGES)
@pytest.mark.parametrize("pid", list(KNOWN_PROVISIONS))
def test_known_provisions_in_the_ai_act(pid: str, language: Language) -> None:
    row = committed("ai-act", language)[pid]

    assert KNOWN_PROVISIONS[pid][language] in row.text


@pytest.mark.parametrize("language", LANGUAGES)
@pytest.mark.parametrize("pid", [p for p in KNOWN_PROVISIONS if not p.startswith("recital")])
def test_known_provisions_in_the_consolidated_text(pid: str, language: Language) -> None:
    """The consolidation leaves out the preamble, so it has no recitals."""
    row = committed("ai-act-consolidated", language)[pid]

    assert KNOWN_PROVISIONS[pid][language] in row.text


@pytest.mark.parametrize("language", LANGUAGES)
def test_art_6_3_includes_its_conditions_and_links_to_them(language: Language) -> None:
    rows = committed("ai-act", language)
    condition = "narrow procedural task" if language == "en" else "eng gefasste Verfahrensaufgabe"

    assert condition in rows["art:6:3"].text
    assert condition in rows["art:6:3:a"].text
    assert rows["art:6:3:a"].parent_id == "art:6:3"


@pytest.mark.parametrize("doc", PARSED_DOCS)
def test_english_and_german_provision_ids_match(doc: str) -> None:
    en, de = committed(doc, "en"), committed(doc, "de")

    assert set(en) == set(de)
    assert list(en) == list(de)


@pytest.mark.parametrize("doc", PARSED_DOCS)
@pytest.mark.parametrize("language", LANGUAGES)
def test_committed_rows_are_well_formed(doc: str, language: Language) -> None:
    rows = committed(doc, language)

    assert rows
    assert all(r.doc == doc and r.language == language for r in rows.values())
    assert all(r.text.strip() for r in rows.values())
    assert all(r.parent_id is None or r.parent_id in rows for r in rows.values())


def test_every_html_entry_of_the_manifest_is_parsed() -> None:
    labels = {f"{e.id}.{e.language}" for e in html_entries(DEFAULT_MANIFEST)}

    assert {p.name.removesuffix(".jsonl") for p in DEFAULT_PARSED_DIR.glob("*.jsonl")} == labels


def test_committed_output_matches_a_fresh_parse_of_the_raw_files(tmp_path: Path) -> None:
    """Needs the shared raw folder (`aiact corpus fetch`); skipped where it isn't there."""
    raw = get_settings().aiact_data_dir / "raw"
    entries = html_entries(DEFAULT_MANIFEST)
    if not all(e.file and (raw / e.file).exists() for e in entries):
        pytest.skip("raw files not fetched")

    parse_all(DEFAULT_MANIFEST, raw, tmp_path)

    for path in tmp_path.glob("*.jsonl"):
        assert path.read_text(encoding="utf-8") == (DEFAULT_PARSED_DIR / path.name).read_text(
            encoding="utf-8"
        ), path.name
