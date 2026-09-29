"""`get_provision` argument checks that fail before any database call (the lookups themselves are
in tests/db/test_get_provision.py)."""

from datetime import date

import pytest

from aiact.retrieval.provisions import get_provision


@pytest.mark.parametrize("provision_id", ["", "art", "Art:4", "art:4:", "art 4"])
def test_a_malformed_id_is_rejected(provision_id: str) -> None:
    with pytest.raises(ValueError, match="malformed provision id"):
        get_provision(provision_id)


def test_an_unknown_prefix_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown provision id prefix 'chapter'"):
        get_provision("chapter:III")


def test_original_with_as_of_is_rejected() -> None:
    with pytest.raises(ValueError, match="as_of resolves only against the amended text"):
        get_provision("art:4", law_version="original", as_of=date(2026, 9, 29))


@pytest.mark.parametrize(("language", "law_version"), [("fr", None), ("en", "draft")])
def test_unknown_language_or_version_strings_raise(language: str, law_version: str | None) -> None:
    with pytest.raises(ValueError, match="is not a valid"):
        get_provision("art:4", language, law_version)
