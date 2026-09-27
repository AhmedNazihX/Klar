from email.message import Message
from pathlib import Path

import pytest
from typer.testing import CliRunner

from aiact import deps
from aiact.cli import app

FIXTURE_LOCK = Path(__file__).parent / "fixtures" / "deps" / "uv.lock"

runner = CliRunner()


def fake_info(name: str) -> deps.PackageInfo:
    """Deterministic metadata; `leaf` plays a package that isn't installed."""
    if name == "leaf":
        return deps.PackageInfo(deps.UNKNOWN, deps.UNKNOWN)
    return deps.PackageInfo("MIT | Apache-2.0" if name == "beta" else "MIT", f"The {name} package")


def rows(document: str, heading: str) -> list[list[str]]:
    """The body rows of the table under `heading`, split into cells."""
    section = document.split(heading, 1)[1].split("\n### ", 1)[0]
    lines = [line for line in section.splitlines() if line.startswith("| ")][2:]
    return [[part.strip() for part in line.strip("|").split(" | ")] for line in lines]


def with_new_dependency(tmp_path: Path) -> Path:
    """A copy of the fixture lock where the project gained a runtime dep without regenerating."""
    text = FIXTURE_LOCK.read_text(encoding="utf-8")
    text = text.replace(
        '    { name = "beta", marker',
        '    { name = "delta", specifier = ">=0.5" },\n    { name = "beta", marker',
    )
    text += '\n[[package]]\nname = "delta"\nversion = "0.5.1"\nsource = { registry = "x" }\n'
    path = tmp_path / "uv.lock"
    path.write_text(text, encoding="utf-8")
    return path


def test_direct_table_lists_groups_constraints_and_locked_versions() -> None:
    document = deps.render(FIXTURE_LOCK, fake_info)
    assert rows(document, "### Direct dependencies") == [
        ["alpha[fast]", "runtime", ">=1.0", "1.2.0", "MIT", "The alpha package"],
        [
            "beta",
            "runtime",
            "*; sys_platform == 'linux'",
            "2.0.0",
            "MIT \\| Apache-2.0",
            "The beta package",
        ],
        ["gamma", "dev", ">=3", "3.1.0", "MIT", "The gamma package"],
    ]


def test_transitive_table_names_the_direct_deps_that_pull_each_package_in() -> None:
    document = deps.render(FIXTURE_LOCK, fake_info)
    assert rows(document, "### Transitive packages") == [
        ["leaf", "0.1.0", "unknown", "alpha, beta, gamma"],
        ["shared", "4.9.0, 5.0.0", "MIT", "alpha, beta, gamma"],
        # Only alpha's `fast` extra pulls speedup in; gamma depends on plain alpha.
        ["speedup", "0.9.0", "MIT", "alpha"],
    ]


def test_header_says_generated_and_names_the_command() -> None:
    document = deps.render(FIXTURE_LOCK, fake_info)
    assert "do not edit by hand" in document.lower()
    assert deps.GENERATE_COMMAND in document


def test_generate_twice_gives_no_diff(tmp_path: Path) -> None:
    output = tmp_path / "DEPENDENCIES.md"
    assert deps.generate(FIXTURE_LOCK, output, fake_info) is True
    first = output.read_bytes()
    assert deps.generate(FIXTURE_LOCK, output, fake_info) is False
    assert output.read_bytes() == first


def test_check_passes_on_a_fresh_file(tmp_path: Path) -> None:
    output = tmp_path / "DEPENDENCIES.md"
    deps.generate(FIXTURE_LOCK, output, fake_info)
    assert deps.check(FIXTURE_LOCK, output, fake_info).is_fresh


def test_check_fails_with_the_fix_after_a_dependency_is_added(tmp_path: Path) -> None:
    output = tmp_path / "DEPENDENCIES.md"
    deps.generate(FIXTURE_LOCK, output, fake_info)
    result = deps.check(with_new_dependency(tmp_path), output, fake_info)
    assert not result.is_fresh
    assert "out of date" in result.message
    assert deps.GENERATE_COMMAND in result.message
    assert "+| delta | runtime | >=0.5 | 0.5.1 |" in result.message


def test_check_fails_when_the_file_is_missing(tmp_path: Path) -> None:
    result = deps.check(FIXTURE_LOCK, tmp_path / "DEPENDENCIES.md", fake_info)
    assert not result.is_fresh
    assert "does not exist" in result.message


def test_cli_check_exit_codes(tmp_path: Path) -> None:
    output = tmp_path / "DEPENDENCIES.md"
    args = ["--lock", str(FIXTURE_LOCK), "--output", str(output)]
    assert runner.invoke(app, ["deps", "generate", *args]).exit_code == 0
    assert runner.invoke(app, ["deps", "check", *args]).exit_code == 0

    stale = ["--lock", str(with_new_dependency(tmp_path)), "--output", str(output)]
    result = runner.invoke(app, ["deps", "check", *stale])
    assert result.exit_code == 1
    assert "out of date" in result.output


def test_cli_reports_a_missing_lockfile(tmp_path: Path) -> None:
    args = ["--lock", str(tmp_path / "nope.lock"), "--output", str(tmp_path / "out.md")]
    result = runner.invoke(app, ["deps", "check", *args])
    assert result.exit_code == 2
    assert "Error:" in result.output


def test_lockfile_without_a_project_package_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "uv.lock"
    path.write_text('version = 1\n[[package]]\nname = "x"\nversion = "1"\n', encoding="utf-8")
    with pytest.raises(ValueError, match="no project package"):
        deps.load_lock(path)


def metadata_with(**fields: str | list[str]) -> Message:
    message = Message()
    for key, value in fields.items():
        for item in value if isinstance(value, list) else [value]:
            message[key.replace("_", "-")] = item
    return message


@pytest.mark.parametrize(
    ("fields", "expected"),
    [
        ({"License_Expression": "Apache-2.0", "License": "MIT"}, "Apache-2.0"),
        ({"License": "BSD\n   3-Clause"}, "BSD 3-Clause"),
        (
            {
                "License": "Copyright (c) 2020 " + "Permission is hereby granted. " * 10,
                "Classifier": ["License :: OSI Approved", "License :: OSI Approved :: MIT License"],
            },
            "MIT License",
        ),
        ({"Classifier": ["License :: OSI Approved :: BSD License", "Topic :: X"]}, "BSD License"),
        ({"Summary": "no licence here"}, "unknown"),
    ],
)
def test_licence_prefers_expression_then_short_license_then_classifiers(
    fields: dict[str, str | list[str]], expected: str
) -> None:
    assert deps.licence_of(metadata_with(**fields)) == expected


def test_cell_is_single_line_escaped_and_truncated() -> None:
    long_text = "word " * 40
    assert deps.cell("a\n|b") == "a \\|b"
    assert len(deps.cell(long_text)) <= deps.MAX_CELL_LENGTH
    assert deps.cell(long_text).endswith("…")
    assert deps.cell("") == "unknown"


def test_installed_info_reads_real_metadata_and_falls_back_to_unknown() -> None:
    assert deps.installed_info("typer").summary != deps.UNKNOWN
    assert deps.installed_info("surely-not-an-installed-package") == deps.PackageInfo(
        deps.UNKNOWN, deps.UNKNOWN
    )
