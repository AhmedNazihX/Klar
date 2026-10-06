"""The shared corpus record/replay helper (E4), and the committed replay recordings it reads: a
replayed node's cassette never lacks its `.corpus.json` (or the other way round), so a lost file
fails here instead of silently turning a replay into a skip."""

import json
from contextlib import nullcontext
from datetime import date
from pathlib import Path

import pytest

from aiact.engine.nodes.common import Lookup
from aiact.eval.cases import CASES_DIR, CaseSet, load_yaml_file
from aiact.retrieval.provisions import Provision, ProvisionNotFoundError
from aiact.schemas import DISCLAIMER, DocumentStatus, Language, LawVersion
from tests.conftest import RECORDINGS_DIR
from tests.engine.nodes.corpus_recording import CORPUS_SUFFIX, CorpusRecording, corpus_recording

LOOKUP = Lookup(Language.EN, LawVersion.AMENDED, date(2026, 9, 30), ())
NODE_RECORDINGS = RECORDINGS_DIR / "engine" / "nodes"
CORPUS_REPLAYS = ("test_scope", "test_high_risk", "test_prohibited", "test_transparency")
"""The replay modules whose cassettes come with a `.corpus.json`."""


def _provision(pid: str) -> Provision:
    return Provision(
        provision_id=pid,
        doc_key="ai-act-consolidated",
        document_title="AI Act (consolidated)",
        doc_type="law",
        law_version=LawVersion.AMENDED,
        status=DocumentStatus.CONSOLIDATED,
        language=Language.EN,
        english_only=False,
        heading=None,
        text=f"Text of {pid}.",
        valid_from=date(2026, 7, 27),
        valid_to=None,
        disclaimer=DISCLAIMER[Language.EN],
    )


class Live:
    def provision(self, pid: str) -> Provision:
        if pid == "art:999":
            raise ProvisionNotFoundError(pid)
        return _provision(pid)


def _record(tmp_path: Path) -> Path:
    with corpus_recording(
        str(tmp_path), "case", "once", "record it", lambda: nullcontext(Live())
    ) as recording:
        recording.provision("art:5", LOOKUP, lambda live: live.provision("art:5"))
        with pytest.raises(ProvisionNotFoundError):
            recording.provision("art:999", LOOKUP, lambda live: live.provision("art:999"))
    return tmp_path / f"case{CORPUS_SUFFIX}"


def test_a_recording_replays_its_answers_and_its_not_found(tmp_path: Path) -> None:
    replay = CorpusRecording[Live](_record(tmp_path), None)
    assert replay.provision("art:5", LOOKUP, lambda live: live.provision("art:5")).text == (
        "Text of art:5."
    )
    with pytest.raises(ProvisionNotFoundError):
        replay.provision("art:999", LOOKUP, lambda live: live.provision("art:999"))


def test_a_call_the_recording_never_saw_fails_the_replay(tmp_path: Path) -> None:
    replay = CorpusRecording[Live](_record(tmp_path), None)
    with pytest.raises(pytest.fail.Exception, match="no recorded corpus answer"):
        replay.provision("art:6", LOOKUP, lambda live: live.provision("art:6"))


def test_the_corpus_file_is_saved_when_the_recording_test_fails(tmp_path: Path) -> None:
    with (
        pytest.raises(AssertionError),
        corpus_recording(
            str(tmp_path), "case", "once", "record it", lambda: nullcontext(Live())
        ) as recording,
    ):
        recording.provision("art:5", LOOKUP, lambda live: live.provision("art:5"))
        raise AssertionError("the label didn't match")
    saved = json.loads((tmp_path / f"case{CORPUS_SUFFIX}").read_text(encoding="utf-8"))
    assert len(saved) == 1


def test_a_replay_without_its_files_is_skipped(tmp_path: Path) -> None:
    with (
        pytest.raises(pytest.skip.Exception, match="record it"),
        corpus_recording(str(tmp_path), "case", "none", "record it", lambda: nullcontext(Live())),
    ):
        pass


def _stems(folder: Path, suffix: str) -> set[str]:
    return {p.name.removesuffix(suffix) for p in folder.glob(f"*{suffix}")}


@pytest.mark.parametrize("module", CORPUS_REPLAYS)
def test_every_cassette_has_its_corpus_file_and_back(module: str) -> None:
    folder = NODE_RECORDINGS / module
    assert _stems(folder, ".yaml") == _stems(folder, CORPUS_SUFFIX)


def _case_ids(category: str) -> set[str]:
    folder = CASES_DIR / CaseSet.OWN.value / category
    return {case.id for path in sorted(folder.rglob("*.yaml")) for case in load_yaml_file(path)}


@pytest.mark.parametrize(
    ("module", "test", "category", "extra"),
    [
        ("test_scope", "test_b5b_case_replay", "b", set()),
        ("test_high_risk", "test_replay_annex_i_case", "e", {"test_replay_worked_example"}),
        ("test_prohibited", "test_b5c_case_replay", "c", set()),
        ("test_transparency", "test_b5a_case_replay", "a", set()),
        (
            "test_role_obligations",
            "test_b5d_case_replay",
            "d",
            {"test_recorded_rebrander_becomes_the_provider"},
        ),
    ],
)
def test_every_recorded_replay_case_has_its_recording(
    module: str, test: str, category: str, extra: set[str]
) -> None:
    """Every case of a recorded replay has its cassette: none may skip for a missing file."""
    expected = {f"{test}[{case_id}]" for case_id in _case_ids(category)} | extra
    assert expected <= _stems(NODE_RECORDINGS / module, ".yaml")
