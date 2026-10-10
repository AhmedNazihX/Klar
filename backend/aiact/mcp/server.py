"""The MCP server with the three lookup tools: `search_ai_act`, `get_provision` and
`list_obligations` (story P2a; INIT > MCP tools). `classify_system` joins them in P2b.

The server is a thin client of the retrieval and obligations functions: it validates the
arguments, calls them and returns their own Pydantic results, which carry the law version and
the "guidance, not legal advice" notice, since a calling agent may show them without this
project's interface around them. It runs over stdio (`aiact mcp serve`).
- **Untrusted input.** Every argument comes from an outside agent. The input schema bounds the
  query and id lengths, the id pattern, the enums, the dates and the result count, so a bad
  call is rejected before any database or model work. Errors the caller can fix (a malformed
  id, `original` with `as_of`, a provision that doesn't exist) come back as tool errors with
  their message; anything else is a crash, whose text the SDK keeps on the server.
- **Held-out examples.** The tools never expose `include_held_out` or
  `exclude_source_example_ids`: Pile B stays hidden for every MCP caller (decision 012).
- **Relevance.** `search_ai_act` uses the `SEARCH_MAX_DISTANCE` cut-off (C8) and returns
  `found` and each hit's `similarity`, so a caller can tell "nothing relevant" from a match.
"""

import inspect
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from datetime import date
from importlib.metadata import version
from typing import Annotated, Literal

import psycopg
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field, ValidationError

from aiact import db
from aiact.corpus.build import AI_ACT_IN_FORCE
from aiact.llm import EmbeddingError
from aiact.obligations.list import ObligationList, UnknownLawVersionError, list_obligations
from aiact.retrieval.provisions import (
    MAX_PROVISION_ID_CHARS,
    PROVISION_ID_RE,
    Provision,
    ProvisionNotFoundError,
    get_provision,
)
from aiact.retrieval.search import (
    CANDIDATES,
    DEFAULT_LIMIT,
    QueryEmbedder,
    SearchResults,
    search_ai_act,
)
from aiact.schemas import HighRiskRoute, Language, LawVersion, RiskClass, Role

SERVER_NAME = "aiact"
MAX_QUERY_CHARS = 4000
"""The longest query accepted: room for a full system description, not for a document."""

INSTRUCTIONS = (
    "Lookup tools over the EU AI Act (as published in 2024, or as amended by the Digital "
    "Omnibus) and the Commission's guidelines, in English and German. Every result carries the "
    "law version it used and a 'guidance, not legal advice' notice: show the notice with any "
    "answer built on it. For an exact reference such as 'Article 50' or 'Annex III point 5(b)', "
    "call get_provision (ids like art:50, art:26:1, annex:III:5:b, recital:12); use "
    "search_ai_act to find provisions by meaning, and check its `found` flag before relying on "
    "the hits."
)

READ_ONLY = ToolAnnotations(read_only_hint=True, idempotent_hint=True, open_world_hint=False)

ConnectionFactory = Callable[[], AbstractContextManager[psycopg.Connection]]
"""Opens a database connection for one tool call; `aiact.db.connect` by default."""

LanguageArg = Annotated[
    Language, Field(description="The language of the texts searched or quoted, and the notice.")
]
LawVersionArg = Annotated[
    LawVersion,
    Field(
        description="'amended' (default): the AI Act as amended by the Digital Omnibus; "
        "'original': as published in 2024."
    ),
]
AsOfArg = Annotated[
    date | None,
    Field(
        ge=AI_ACT_IN_FORCE,
        description="The date whose text applies (YYYY-MM-DD, from 2024-08-01; default today). "
        "Only with law_version 'amended'.",
    ),
]


def build_server(
    *, connect: ConnectionFactory = db.connect, embedder: QueryEmbedder | None = None
) -> MCPServer:
    """The MCP server with the lookup tools. `connect` and `embedder` are for tests; by default
    each call opens a connection from DATABASE_URL and embeds the query through OpenRouter."""
    server = MCPServer(SERVER_NAME, version=version("aiact"), instructions=INSTRUCTIONS)

    def search_tool(
        query: Annotated[
            str,
            Field(
                min_length=1,
                max_length=MAX_QUERY_CHARS,
                description="What to look for, in plain words (a question or a description).",
            ),
        ],
        language: LanguageArg = Language.EN,
        law_version: LawVersionArg = LawVersion.AMENDED,
        as_of: AsOfArg = None,
        doc_types: Annotated[
            list[Literal["law", "guideline", "code"]] | None,
            Field(
                min_length=1,
                max_length=3,
                description="Only these kinds of document; default all. Most guidance exists "
                "only in English, so search in English to find it.",
            ),
        ] = None,
        limit: Annotated[
            int, Field(ge=1, le=CANDIDATES, description="The most hits to return.")
        ] = DEFAULT_LIMIT,
    ) -> SearchResults:
        """Search the AI Act and the Commission's guidance by meaning and keywords.

        Returns the best hits with their text, provision id, document and version. `found` is
        false when nothing relevant was found; each hit's `similarity` (1 is closest) shows how
        close it is. A provision the query names by number ('Article 50', 'Annex III point
        5(b)', 'Artikel 26 Absatz 2') comes first and counts as found; an article of another
        act ('Article 22 GDPR', 'Art. 17 DSGVO') is not taken as one. For one provision's exact
        text, get_provision is the direct way.
        """
        # ValueError: the search's own argument checks (an empty query, `original` with as_of).
        with _tool_errors(ValueError), connect() as connection:
            return search_ai_act(
                query,
                language,
                law_version,
                as_of,
                doc_types=None if doc_types is None else frozenset(doc_types),
                limit=limit,
                embedder=embedder,
                connection=connection,
            )

    def provision_tool(
        provision_id: Annotated[
            str,
            Field(
                max_length=MAX_PROVISION_ID_CHARS,
                pattern=PROVISION_ID_RE.pattern,
                description="The provision's id: art:<n>[:<paragraph>[:<point>]], "
                "annex:<roman>[:<point>…], recital:<n> or guide:<doc_key>:…; "
                "e.g. art:26:1, annex:III:5:b.",
            ),
        ],
        language: LanguageArg = Language.EN,
        law_version: LawVersionArg = LawVersion.AMENDED,
        as_of: AsOfArg = None,
    ) -> Provision:
        """Return the exact text of one article, paragraph, annex point, recital or guideline
        passage, with its version, language and status.

        When German is asked for but only the English text exists (most guidance), the English
        text is returned with `english_only` set.
        """
        # ValueError: a malformed id or prefix, or `original` with as_of.
        with _tool_errors(ValueError, ProvisionNotFoundError), connect() as connection:
            return get_provision(provision_id, language, law_version, as_of, connection=connection)

    def obligations_tool(
        role: Annotated[Role, Field(description="The operator's role under the Act.")],
        risk_class: Annotated[RiskClass, Field(description="The system's risk class.")],
        route: Annotated[
            HighRiskRoute | None,
            Field(
                description="For a high-risk system: the route (Annex III or Annex I), which "
                "sets the dates; without it, route-dependent duties appear once per route."
            ),
        ] = None,
        law_version: Annotated[
            Literal["amended"],
            Field(description="The table covers the AI Act as amended by the Digital Omnibus."),
        ] = "amended",
        language: LanguageArg = Language.EN,
    ) -> ObligationList:
        """List the duties, article references and dates that apply to a role for a system of
        a risk class, with any relief for SMEs and small mid-caps. The duties are in English."""
        # Only UnknownLawVersionError: any other ObligationsError is a broken table (ours), and
        # its message names a server path.
        with _tool_errors(UnknownLawVersionError):
            return list_obligations(role, risk_class, route, law_version, language=language)

    for name, tool in (
        ("search_ai_act", search_tool),
        ("get_provision", provision_tool),
        ("list_obligations", obligations_tool),
    ):
        # The docstring, without its source indentation, is what a calling agent reads.
        description = inspect.cleandoc(tool.__doc__ or "")
        server.add_tool(tool, name=name, description=description, annotations=READ_ONLY)
    return server


@contextmanager
def _tool_errors(*fixable: type[Exception]) -> Iterator[None]:
    """Turn the `fixable` errors, which a caller can fix, into tool errors with their message.
    Everything else stays a crash, whose text the SDK keeps on the server; so does a failed
    pydantic validation (a ValueError too), which is our bug, not the caller's."""
    try:
        yield
    except ValidationError:
        raise
    except fixable as error:
        raise ToolError(str(error)) from error
    except EmbeddingError as error:
        raise ToolError("the query could not be embedded just now; try again later") from error


def serve() -> None:
    """Run the server over stdio until the client disconnects."""
    build_server().run("stdio")
