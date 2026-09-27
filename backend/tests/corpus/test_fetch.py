"""`aiact corpus fetch` against a fake transport: no test touches the network."""

import hashlib
from collections.abc import Callable, Iterator
from functools import partial
from itertools import count
from pathlib import Path

import httpx
import pytest
from typer.testing import CliRunner

from aiact import cli
from aiact.corpus.fetch import Fetcher, fetch_all, load_manifest, make_client
from aiact.corpus.sources import Source

HTML_EN = b"<!DOCTYPE html><html><head><title>L_202401689EN</title></head><body>1</body></html>"
HTML_DE = HTML_EN.replace(b"EN<", b"DE<")
PDF = b"%PDF-1.7 fake guideline"

LAW_EN = Source(
    id="law",
    language="en",
    title="A law",
    kind="html",
    status="law",
    version="2024-07-12",
    source_page="https://eur-lex.example/law",
    url="https://eur-lex.example/law.en",
)
LAW_DE = LAW_EN.model_copy(update={"language": "de", "url": "https://eur-lex.example/law.de"})
GUIDE_EN = Source(
    id="guide",
    language="en",
    title="A guideline",
    kind="pdf",
    status="draft",
    version="2026-05-19",
    source_page="https://commission.example/guide",
    url="https://commission.example/guide.pdf",
)
GUIDE_DE = GUIDE_EN.model_copy(
    update={"language": "de", "url": None, "absent_reason": "English only"}
)
SOURCES = (LAW_EN, LAW_DE, GUIDE_EN, GUIDE_DE)

Handler = Callable[[httpx.Request], httpx.Response]


def serve(bodies: dict[str, bytes], requests: list[str] | None = None) -> Handler:
    """A handler that serves `bodies` by URL and answers 404 for anything else."""

    def handler(request: httpx.Request) -> httpx.Response:
        if requests is not None:
            requests.append(str(request.url))
        body = bodies.get(str(request.url))
        return httpx.Response(404) if body is None else httpx.Response(200, content=body)

    return handler


def clock() -> Callable[[], str]:
    """A fake clock: every call returns a later timestamp."""
    ticks: Iterator[int] = count()
    return lambda: f"2026-09-27T10:00:{next(ticks):02d}Z"


def run(
    tmp_path: Path, handler: Handler, now: Callable[[], str], sleeps: list[float] | None = None
):
    fetcher = Fetcher(
        make_client(httpx.MockTransport(handler)),
        sleep=(sleeps.append if sleeps is not None else lambda _: None),
    )
    return fetch_all(tmp_path / "manifest.yaml", tmp_path / "raw", fetcher, SOURCES, now)


ALL_PRESENT = {LAW_EN.url or "": HTML_EN, LAW_DE.url or "": HTML_DE, GUIDE_EN.url or "": PDF}


def test_first_run_records_present_and_absent_documents(tmp_path: Path) -> None:
    report = run(tmp_path, serve(ALL_PRESENT), clock())

    entries = {entry.key: entry for entry in load_manifest(tmp_path / "manifest.yaml").documents}
    assert report.manifest_written
    assert entries[("law", "en")].available
    assert entries[("law", "en")].sha256 == hashlib.sha256(HTML_EN).hexdigest()
    assert (tmp_path / "raw" / "law.en.html").read_bytes() == HTML_EN
    assert (tmp_path / "raw" / "guide.en.pdf").read_bytes() == PDF
    assert not entries[("guide", "de")].available
    assert entries[("guide", "de")].absent_reason == "English only"
    assert report.failures == ()


def test_rerun_with_same_content_changes_nothing(tmp_path: Path) -> None:
    now = clock()
    run(tmp_path, serve(ALL_PRESENT), now)
    before = (tmp_path / "manifest.yaml").read_bytes()

    report = run(tmp_path, serve(ALL_PRESENT), now)

    assert not report.manifest_written
    assert report.changed == ()
    assert (tmp_path / "manifest.yaml").read_bytes() == before


def test_changed_content_updates_sha_and_fetched_at(tmp_path: Path) -> None:
    now = clock()
    first = run(tmp_path, serve(ALL_PRESENT), now)
    new_html = HTML_EN.replace(b"<body>1", b"<body>1a")

    second = run(tmp_path, serve(ALL_PRESENT | {LAW_EN.url or "": new_html}), now)

    old, new = first.manifest.documents[0], second.manifest.documents[0]
    assert second.changed == ("law.en",)
    assert new.sha256 == hashlib.sha256(new_html).hexdigest() != old.sha256
    assert new.fetched_at != old.fetched_at
    assert (tmp_path / "raw" / "law.en.html").read_bytes() == new_html


def test_missing_raw_file_is_restored_without_changing_the_manifest(tmp_path: Path) -> None:
    now = clock()
    run(tmp_path, serve(ALL_PRESENT), now)
    (tmp_path / "raw" / "law.en.html").unlink()

    report = run(tmp_path, serve(ALL_PRESENT), now)

    assert not report.manifest_written
    assert (tmp_path / "raw" / "law.en.html").read_bytes() == HTML_EN


def test_http_404_is_recorded_as_not_published(tmp_path: Path) -> None:
    requests: list[str] = []
    bodies = {LAW_EN.url or "": HTML_EN, GUIDE_EN.url or "": PDF}

    report = run(tmp_path, serve(bodies, requests), clock())

    law_de = report.manifest.documents[1]
    assert not law_de.available
    assert law_de.absent_reason is not None and "HTTP 404" in law_de.absent_reason
    assert report.failures == ()
    assert len(requests) == 3  # the declared-absent German guideline is never requested


def test_failure_keeps_the_earlier_entry_and_is_reported(tmp_path: Path) -> None:
    now = clock()
    first = run(tmp_path, serve(ALL_PRESENT), now)

    def broken_law_en(request: httpx.Request) -> httpx.Response:
        if str(request.url) == LAW_EN.url:
            return httpx.Response(503)
        return serve(ALL_PRESENT)(request)

    second = run(tmp_path, broken_law_en, now)

    assert second.manifest.documents[0] == first.manifest.documents[0]
    assert second.failures == ("law.en: gave up after 4 attempts (HTTP 503)",)
    assert not second.manifest_written


def test_failure_without_earlier_entry_is_recorded_absent(tmp_path: Path) -> None:
    def challenge(request: httpx.Request) -> httpx.Response:
        return httpx.Response(202, headers={"x-amzn-waf-action": "challenge"})

    report = run(tmp_path, challenge, clock())

    law_en = report.manifest.documents[0]
    assert not law_en.available
    assert law_en.absent_reason is not None and law_en.absent_reason.startswith("Fetch failed")
    assert len(report.failures) == 3  # both laws and the English guideline


def test_waf_challenge_is_retried_with_backoff(tmp_path: Path) -> None:
    calls = count()

    def challenge_once(request: httpx.Request) -> httpx.Response:
        if str(request.url) == LAW_EN.url and next(calls) == 0:
            return httpx.Response(202)
        return serve(ALL_PRESENT)(request)

    sleeps: list[float] = []
    report = run(tmp_path, challenge_once, clock(), sleeps)

    assert report.failures == ()
    assert report.manifest.documents[0].available
    assert sleeps[0] == 10.0  # the first backoff, before any pause between documents


def test_wrong_content_type_is_a_failure(tmp_path: Path) -> None:
    bodies = ALL_PRESENT | {GUIDE_EN.url or "": b"<html>Page not found</html>"}

    report = run(tmp_path, serve(bodies), clock())

    assert report.failures == ("guide.en: response is not pdf (27 bytes)",)
    assert not (tmp_path / "raw" / "guide.en.pdf").exists()


def test_html_in_the_wrong_language_is_a_failure(tmp_path: Path) -> None:
    bodies = ALL_PRESENT | {LAW_DE.url or "": HTML_EN}

    report = run(tmp_path, serve(bodies), clock())

    assert report.failures == ("law.de: html title doesn't name language de",)


def test_accept_language_is_sent_for_cellar_sources(tmp_path: Path) -> None:
    cellar_de = LAW_DE.model_copy(update={"accept_language": "deu"})
    seen: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers.get("Accept-Language"))
        return httpx.Response(200, content=HTML_DE)

    fetcher = Fetcher(make_client(httpx.MockTransport(handler)), sleep=lambda _: None)
    report = fetch_all(tmp_path / "m.yaml", tmp_path / "raw", fetcher, (cellar_de,), clock())

    assert seen == ["deu"]
    assert report.manifest.documents[0].accept_language == "deu"


def test_malformed_manifest_is_an_error(tmp_path: Path) -> None:
    (tmp_path / "manifest.yaml").write_text("documents: [{id: 1}]\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_manifest(tmp_path / "manifest.yaml")


def test_cli_fetch_writes_to_the_given_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        cli, "make_client", lambda: make_client(httpx.MockTransport(serve(ALL_PRESENT)))
    )
    monkeypatch.setattr(cli, "Fetcher", partial(Fetcher, sleep=lambda _: None))
    monkeypatch.setattr(cli, "fetch_all", partial(fetch_all, sources=SOURCES))
    manifest, raw = tmp_path / "m.yaml", tmp_path / "raw"

    result = CliRunner().invoke(
        cli.app, ["corpus", "fetch", "--manifest", str(manifest), "--raw-dir", str(raw)]
    )

    assert result.exit_code == 0, result.output
    assert "absent  guide.de  English only" in result.output
    assert manifest.exists()
    assert (raw / "law.de.html").exists()
