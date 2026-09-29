import io
import json
import urllib.error
from email.message import Message
from pathlib import Path

import pytest
from typer.testing import CliRunner

from aiact import deps
from aiact.cli import app
from aiact.deps import PackageInfo

FIXTURE_LOCK = Path(__file__).parent / "fixtures" / "deps" / "uv.lock"
FIXTURE_PNPM_LOCK = FIXTURE_LOCK.with_name("pnpm-lock.yaml")

runner = CliRunner()


def fake_fetch(name: str, version: str) -> PackageInfo | None:
    """Deterministic metadata; `leaf` plays a package that no source knows about."""
    if name == "leaf":
        return None
    licence = {"beta": "MIT | Apache-2.0", "shared": "MIT" if version < "5" else "Apache-2.0"}
    return PackageInfo(licence=licence.get(name, "MIT"), summary=f"The {name} package")


def paths(directory: Path) -> tuple[Path, Path]:
    return directory / "DEPENDENCIES.md", directory / "dependency-licences.json"


def generate_into(directory: Path, lock: Path = FIXTURE_LOCK) -> tuple[Path, Path]:
    output, licences = paths(directory)
    deps.generate(lock, output, licences, fake_fetch)
    return output, licences


def fake_npm_fetch(name: str, version: str) -> PackageInfo | None:
    """Deterministic npm metadata; `esbin` plays a package that no source knows about."""
    if name == "esbin":
        return None
    return PackageInfo(licence="MIT", summary=f"npm {name} {version}")


def generate_with_frontend(
    directory: Path, pnpm_lock: Path = FIXTURE_PNPM_LOCK
) -> tuple[Path, Path]:
    output, licences = paths(directory)
    deps.generate(
        FIXTURE_LOCK,
        output,
        licences,
        fake_fetch,
        frontend_lock_path=pnpm_lock,
        npm_fetch=fake_npm_fetch,
    )
    return output, licences


def rows(document: str, heading: str, section_title: str = deps.PYTHON_TITLE) -> list[list[str]]:
    """The body rows of the table under `heading` in one lockfile's section, split into cells."""
    part = document.split(f"## {section_title}\n", 1)[1].split("\n## ", 1)[0]
    section = part.split(heading, 1)[1].split("\n### ", 1)[0]
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


def test_direct_table_lists_groups_constraints_and_locked_versions(tmp_path: Path) -> None:
    output, _ = generate_into(tmp_path)
    assert rows(output.read_text(encoding="utf-8"), "### Direct dependencies") == [
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


def test_transitive_table_names_the_direct_deps_that_pull_each_package_in(tmp_path: Path) -> None:
    output, _ = generate_into(tmp_path)
    assert rows(output.read_text(encoding="utf-8"), "### Transitive packages") == [
        ["leaf", "0.1.0", "unknown", "alpha, beta, gamma"],
        # A forked package shows each version and each distinct licence.
        ["shared", "4.9.0, 5.0.0", "MIT / Apache-2.0", "alpha, beta, gamma"],
        # Only alpha's `fast` extra pulls speedup in; gamma depends on plain alpha.
        ["speedup", "0.9.0", "MIT", "alpha"],
    ]


def test_forked_packages_merge_the_edges_of_each_extra() -> None:
    shared = deps.load_lock(FIXTURE_LOCK).packages["shared"]
    assert [edge.name for edge in shared.optional["extra"]] == ["leaf", "speedup"]


def test_header_says_generated_and_names_the_command(tmp_path: Path) -> None:
    output, _ = generate_into(tmp_path)
    document = output.read_text(encoding="utf-8")
    assert "do not edit by hand" in document.lower()
    assert deps.GENERATE_COMMAND in document


def test_cache_has_one_sorted_entry_per_locked_version(tmp_path: Path) -> None:
    _, licences = generate_into(tmp_path)
    cache = json.loads(licences.read_text(encoding="utf-8"))
    assert list(cache) == sorted(cache)
    assert "shared==4.9.0" in cache and "shared==5.0.0" in cache
    assert cache["leaf==0.1.0"] == {"licence": "unknown", "summary": "unknown"}


def test_generate_twice_gives_no_diff(tmp_path: Path) -> None:
    output, licences = paths(tmp_path)
    assert deps.generate(FIXTURE_LOCK, output, licences, fake_fetch) is True
    first = (output.read_bytes(), licences.read_bytes())
    assert deps.generate(FIXTURE_LOCK, output, licences, fake_fetch) is False
    assert (output.read_bytes(), licences.read_bytes()) == first


def test_generate_keeps_cached_entries_and_prunes_stale_ones(tmp_path: Path) -> None:
    output, licences = paths(tmp_path)
    stale = {"gone==1.0": {"licence": "X", "summary": "x"}}
    kept = {"alpha==1.2.0": {"licence": "Cached", "summary": "from the cache"}}
    licences.write_text(json.dumps(stale | kept), encoding="utf-8")
    deps.generate(FIXTURE_LOCK, output, licences, fake_fetch)
    cache = json.loads(licences.read_text(encoding="utf-8"))
    assert "gone==1.0" not in cache
    assert cache["alpha==1.2.0"]["licence"] == "Cached"


def test_output_is_identical_whether_a_marker_gated_package_is_installed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`leaf` is gated on win32: installed on one machine, fetched from PyPI on another."""
    leaf = PackageInfo(licence="BSD-3-Clause", summary="The leaf package")

    def run(directory: Path, *, is_installed: bool) -> tuple[bytes, bytes]:
        installed = {"leaf": leaf} if is_installed else {}
        monkeypatch.setattr(deps, "installed_info", lambda name, _v: installed.get(name))
        monkeypatch.setattr(
            deps, "pypi_info", lambda name, v: leaf if name == "leaf" else fake_fetch(name, v)
        )
        directory.mkdir()
        output, licences = paths(directory)
        deps.generate(FIXTURE_LOCK, output, licences)  # the default fetch: installed, else PyPI
        return output.read_bytes(), licences.read_bytes()

    assert run(tmp_path / "linux", is_installed=True) == run(tmp_path / "mac", is_installed=False)


def test_check_never_reads_installed_metadata_or_the_network(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output, licences = generate_into(tmp_path)

    def forbidden(*_args: object) -> None:
        raise AssertionError("check must work from committed files only")

    monkeypatch.setattr(deps, "installed_info", forbidden)
    monkeypatch.setattr(deps, "pypi_info", forbidden)
    monkeypatch.setattr(deps.urllib.request, "urlopen", forbidden)
    assert deps.check(FIXTURE_LOCK, output, licences).is_fresh


def test_check_fails_with_the_fix_after_a_dependency_is_added(tmp_path: Path) -> None:
    output, licences = generate_into(tmp_path)
    result = deps.check(with_new_dependency(tmp_path), output, licences)
    assert not result.is_fresh
    assert "missing: delta==0.5.1" in result.message
    assert deps.GENERATE_COMMAND in result.message


def test_check_fails_with_a_diff_when_only_the_manifest_is_stale(tmp_path: Path) -> None:
    output, licences = generate_into(tmp_path)
    output.write_text(output.read_text(encoding="utf-8").replace("| gamma |", "| gama |"))
    result = deps.check(FIXTURE_LOCK, output, licences)
    assert not result.is_fresh
    assert "out of date" in result.message
    assert "+| gamma | dev |" in result.message


def test_check_fails_on_stale_cache_entries(tmp_path: Path) -> None:
    output, licences = generate_into(tmp_path)
    cache = json.loads(licences.read_text(encoding="utf-8"))
    licences.write_text(json.dumps(cache | {"gone==1.0": cache["leaf==0.1.0"]}), encoding="utf-8")
    result = deps.check(FIXTURE_LOCK, output, licences)
    assert not result.is_fresh
    assert "stale: gone==1.0" in result.message


def test_check_fails_when_the_file_is_missing(tmp_path: Path) -> None:
    output, licences = generate_into(tmp_path)
    output.unlink()
    result = deps.check(FIXTURE_LOCK, output, licences)
    assert not result.is_fresh
    assert "does not exist" in result.message


def test_cli_check_exit_codes(tmp_path: Path) -> None:
    output, licences = generate_with_frontend(tmp_path)
    args = [
        *("--output", str(output), "--licences", str(licences)),
        *("--frontend-lock", str(FIXTURE_PNPM_LOCK)),
    ]
    assert runner.invoke(app, ["deps", "check", "--lock", str(FIXTURE_LOCK), *args]).exit_code == 0
    stale_lock = str(with_new_dependency(tmp_path))
    result = runner.invoke(app, ["deps", "check", "--lock", stale_lock, *args])
    assert result.exit_code == 1
    assert "doesn't match" in result.output


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


def test_invalid_cache_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "dependency-licences.json"
    path.write_text('{"x==1": {"licence": 3}}', encoding="utf-8")
    with pytest.raises(ValueError, match="not a valid licence cache"):
        deps.load_cache(path)


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


def test_installed_info_needs_the_exact_locked_version() -> None:
    from importlib import metadata

    typer_version = metadata.version("typer")
    info = deps.installed_info("typer", typer_version)
    assert info is not None and info.summary != deps.UNKNOWN
    assert deps.installed_info("typer", "0.0.0-not-this") is None
    assert deps.installed_info("surely-not-an-installed-package", "1.0") is None


def test_pypi_info_reads_the_json_api(monkeypatch: pytest.MonkeyPatch) -> None:
    body = {
        "info": {
            "license_expression": None,
            "license": "",
            "classifiers": ["License :: OSI Approved :: MIT License"],
            "summary": "A  package",
        }
    }
    seen: list[str] = []

    def fake_urlopen(url: str, timeout: float) -> io.BytesIO:
        seen.append(url)
        assert timeout == deps.PYPI_TIMEOUT_SECONDS
        return io.BytesIO(json.dumps(body).encode())

    monkeypatch.setattr(deps.urllib.request, "urlopen", fake_urlopen)
    assert deps.pypi_info("demo-pkg", "1.0") == PackageInfo(
        licence="MIT License", summary="A package"
    )
    assert seen == ["https://pypi.org/pypi/demo-pkg/1.0/json"]


def test_pypi_info_returns_none_when_offline(monkeypatch: pytest.MonkeyPatch) -> None:
    def offline(url: str, timeout: float) -> io.BytesIO:
        raise urllib.error.URLError("no network")

    monkeypatch.setattr(deps.urllib.request, "urlopen", offline)
    assert deps.pypi_info("demo-pkg", "1.0") is None


# --- The frontend section (pnpm lockfile) ---------------------------------------------------


def test_frontend_direct_table_lists_groups_specifiers_and_locked_versions(tmp_path: Path) -> None:
    output, _ = generate_with_frontend(tmp_path)
    document = output.read_text(encoding="utf-8")
    assert rows(document, "### Direct dependencies", deps.FRONTEND_TITLE) == [
        ["@scope/ui", "runtime", "^1.0.0", "1.0.0", "MIT", "npm @scope/ui 1.0.0"],
        # vite also pulls in react 18.3.0; the row shows the version the project resolved.
        ["react", "runtime", "^19.0.0", "19.1.0", "MIT", "npm react 19.1.0"],
        ["vite", "dev", "^8.0.0", "8.0.0", "MIT", "npm vite 8.0.0"],
    ]
    assert "Source: `" in document and "pnpm-lock.yaml`" in document


def test_frontend_transitive_table_follows_dependencies_and_optional_ones(tmp_path: Path) -> None:
    output, _ = generate_with_frontend(tmp_path)
    assert rows(
        output.read_text(encoding="utf-8"), "### Transitive packages", deps.FRONTEND_TITLE
    ) == [
        ["@esbin/darwin", "1.0.0", "MIT", "vite"],
        ["esbin", "1.0.0", "unknown", "vite"],
        # Two versions, pulled in by different direct deps; peer suffixes are dropped.
        ["tiny", "2.0.0, 3.0.0", "MIT", "@scope/ui, vite"],
    ]


def test_the_package_manager_document_is_not_a_dependency() -> None:
    lock = deps.load_pnpm_lock(FIXTURE_PNPM_LOCK)
    assert "pnpm" not in lock.packages
    assert "pnpm" not in {dep.name for dep in lock.direct}


def test_frontend_cache_keys_are_namespaced(tmp_path: Path) -> None:
    _, licences = generate_with_frontend(tmp_path)
    cache = json.loads(licences.read_text(encoding="utf-8"))
    assert "npm:tiny==2.0.0" in cache and "npm:tiny==3.0.0" in cache
    assert "alpha==1.2.0" in cache  # the backend's entries stay
    assert cache["npm:esbin==1.0.0"] == {"licence": "unknown", "summary": "unknown"}


def test_generate_with_frontend_twice_gives_no_diff(tmp_path: Path) -> None:
    output, licences = generate_with_frontend(tmp_path)
    first = (output.read_bytes(), licences.read_bytes())
    assert (
        deps.generate(FIXTURE_LOCK, output, licences, fake_fetch, FIXTURE_PNPM_LOCK, fake_npm_fetch)
        is False
    )
    assert (output.read_bytes(), licences.read_bytes()) == first


def test_check_covers_the_frontend_lock(tmp_path: Path) -> None:
    output, licences = generate_with_frontend(tmp_path)
    assert deps.check(FIXTURE_LOCK, output, licences, FIXTURE_PNPM_LOCK).is_fresh

    text = FIXTURE_PNPM_LOCK.read_text(encoding="utf-8")
    text = text.replace(
        "    devDependencies:\n",
        "      zod:\n        specifier: ^4.0.0\n        version: 4.0.1\n    devDependencies:\n",
    )
    text += "\n  zod@4.0.1: {}\n"
    stale_lock = tmp_path / "pnpm-lock.yaml"
    stale_lock.write_text(text, encoding="utf-8")

    result = deps.check(FIXTURE_LOCK, output, licences, stale_lock)
    assert not result.is_fresh
    assert "missing: npm:zod==4.0.1" in result.message
    assert deps.GENERATE_COMMAND in result.message


def test_check_without_the_frontend_lock_calls_its_entries_stale(tmp_path: Path) -> None:
    output, licences = generate_with_frontend(tmp_path)
    result = deps.check(FIXTURE_LOCK, output, licences)
    assert not result.is_fresh
    assert "stale: npm:" in result.message


def test_pnpm_lock_without_a_project_importer_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "pnpm-lock.yaml"
    path.write_text("lockfileVersion: '9.0'\nimporters: {}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="no project importer"):
        deps.load_pnpm_lock(path)


@pytest.mark.parametrize(
    ("manifest", "expected"),
    [
        ({"license": "MIT", "description": "A  lib"}, PackageInfo(licence="MIT", summary="A lib")),
        (
            {"license": {"type": "BSD-3-Clause"}},
            PackageInfo(licence="BSD-3-Clause", summary="unknown"),
        ),
        (
            {"licenses": [{"type": "MIT"}, {"type": "Apache-2.0"}]},
            PackageInfo(licence="MIT OR Apache-2.0", summary="unknown"),
        ),
        ({}, PackageInfo(licence="unknown", summary="unknown")),
    ],
)
def test_npm_manifest_info_reads_the_licence_forms(
    manifest: dict[str, object], expected: PackageInfo
) -> None:
    assert deps.npm_manifest_info(manifest) == expected


def test_installed_npm_info_reads_the_pnpm_store_for_the_exact_version(tmp_path: Path) -> None:
    package_dir = (
        tmp_path / ".pnpm" / "@scope+ui@1.0.0_react@19.1.0" / "node_modules" / "@scope" / "ui"
    )
    package_dir.mkdir(parents=True)
    manifest = {"name": "@scope/ui", "version": "1.0.0", "license": "MIT", "description": "UI"}
    (package_dir / "package.json").write_text(json.dumps(manifest), encoding="utf-8")

    assert deps.installed_npm_info(tmp_path, "@scope/ui", "1.0.0") == PackageInfo(
        licence="MIT", summary="UI"
    )
    assert deps.installed_npm_info(tmp_path, "@scope/ui", "2.0.0") is None
    assert deps.installed_npm_info(tmp_path, "absent", "1.0.0") is None


def test_npm_registry_info_reads_the_version_document(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[str] = []

    def fake_urlopen(url: str, timeout: float) -> io.BytesIO:
        seen.append(url)
        return io.BytesIO(json.dumps({"license": "ISC", "description": "Types"}).encode())

    monkeypatch.setattr(deps.urllib.request, "urlopen", fake_urlopen)
    assert deps.npm_registry_info("@types/node", "24.0.0") == PackageInfo(
        licence="ISC", summary="Types"
    )
    assert seen == ["https://registry.npmjs.org/@types/node/24.0.0"]


def test_npm_registry_info_returns_none_when_offline(monkeypatch: pytest.MonkeyPatch) -> None:
    def offline(url: str, timeout: float) -> io.BytesIO:
        raise urllib.error.URLError("no network")

    monkeypatch.setattr(deps.urllib.request, "urlopen", offline)
    assert deps.npm_registry_info("react", "19.1.0") is None
