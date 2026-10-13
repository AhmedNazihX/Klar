"""The parsed Omnibus's amendment records, as the routes that quote the corpus read them (P31).

The Omnibus marks the provisions it changed. A Q&A answer about a result (`aiact.qa.clients`)
and a vendor letter's quotes (`aiact.api.documents`) read its records through `omnibus_changes`,
which turns any failure to read or load the file into `OmnibusUnavailableError`. The API answers
that like an unreachable corpus: a 503 whose log names the error's type and the failure's type,
never its text, which may name the file's path.
"""

from pathlib import Path

from aiact.corpus.build import LoadError
from aiact.engine.citations import OmnibusChanges, load_omnibus_changes


class OmnibusUnavailableError(RuntimeError):
    """The parsed Omnibus can't be read or loaded. It carries the failure's type only (its
    message is the type's name), so neither a log nor a response can quote the path."""

    def __init__(self, failure: type[BaseException]) -> None:
        super().__init__(failure.__name__)
        self.failure = failure.__name__


def omnibus_changes(data_dir: Path) -> OmnibusChanges:
    """The Omnibus's amendment records (`load_omnibus_changes`, read once per `data_dir`). A file
    that can't be read (`OSError`), isn't UTF-8 or JSON, or doesn't fit the records
    (`ValueError`, pydantic's `ValidationError` among them) or the corpus build's checks
    (`LoadError`) raises `OmnibusUnavailableError`, and is tried again on the next request."""
    try:
        return load_omnibus_changes(data_dir)
    except (OSError, LoadError, ValueError) as exc:
        raise OmnibusUnavailableError(type(exc)) from None
