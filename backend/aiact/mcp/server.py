"""The MCP server with the four tools (INIT > MCP tools): the lookups `search_ai_act`,
`get_provision` and `list_obligations` (story P2a), and `classify_system` (P2b).

The server is a thin client of the retrieval, obligations and engine functions: it validates the
arguments, calls them and returns their own Pydantic results, which carry the law version and
the "guidance, not legal advice" notice, since a calling agent may show them without this
project's interface around them. It runs over stdio (`aiact mcp serve`).
- **Bring your own key.** `classify_system` runs the engine only on `MCP_OPENROUTER_API_KEY`, the
  MCP user's own OpenRouter key (INIT > Tech stack, Billing), never on the app's
  `OPENROUTER_API_KEY`: every model call and embedding of the run is billed to it. The key stays a
  `SecretStr`; no message or log names its value.
- **Untrusted input.** Every argument comes from an outside agent. The input schema bounds the
  query, description, answer and id lengths, the id pattern, the enums, the dates, the number of
  answers and the result count, so a bad call is rejected before any database or model work.
  Errors the caller can fix (a malformed id, `original` with `as_of`, a provision that doesn't
  exist, a blank description) come back as tool errors with their message, and so does a
  classification that failed (naming only its check); anything else is a crash, whose text the
  SDK keeps on the server.
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
from aiact.engine import ClassificationFailedError, ClassifyRequest, run_classification
from aiact.engine.classify import AnswerId, NodeBuilder, engine_nodes
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
from aiact.schemas import (
    ClassificationResult,
    HighRiskRoute,
    Language,
    LawVersion,
    LegacyStatus,
    RiskClass,
    Role,
)
from aiact.settings import Settings, get_settings

SERVER_NAME = "aiact"
MAX_QUERY_CHARS = 4000
"""The longest query accepted: room for a full system description, not for a document."""

INSTRUCTIONS = (
    "Tools over the EU AI Act (as published in 2024, or as amended by the Digital Omnibus) and "
    "the Commission's guidelines, in English and German. Every result carries the law version it "
    "used and a 'guidance, not legal advice' notice: show the notice with any answer built on it. "
    "To classify an AI system, call classify_system with its description. For an exact reference "
    "such as 'Article 50' or 'Annex III point 5(b)', call get_provision (ids like art:50, "
    "art:26:1, annex:III:5:b, recital:12); use search_ai_act to find provisions by meaning, and "
    "check its `found` flag before relying on the hits."
)

READ_ONLY = ToolAnnotations(read_only_hint=True, idempotent_hint=True, open_world_hint=False)
CLASSIFY = ToolAnnotations(read_only_hint=True, idempotent_hint=False, open_world_hint=True)
"""A classification changes nothing, but an outside model answers it (paid), so two runs can
differ."""

MISSING_KEY = (
    "classify_system runs on your own OpenRouter key: set MCP_OPENROUTER_API_KEY in this "
    "server's env in your MCP client's config, then restart the server"
)
FAILED_RUN_HINT = (
    "Try again later; if it keeps failing, check that MCP_OPENROUTER_API_KEY is a valid "
    "OpenRouter key with credit"
)

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
AnswersArg = Annotated[
    dict[
        AnswerId,
        Annotated[str, Field(min_length=1, max_length=ClassifyRequest.MAX_ANSWER_CHARS)],
    ]
    | None,
    Field(
        max_length=ClassifyRequest.MAX_ANSWERS,
        description="Answers to the follow-up questions of an earlier result, keyed by each "
        'question\'s id (e.g. {"uses_biometrics": "No, it only reads typed text."}). Call again '
        "with the same description and these answers to settle the open points.",
    ),
]


def build_server(
    *,
    connect: ConnectionFactory = db.connect,
    embedder: QueryEmbedder | None = None,
    settings: Settings | None = None,
    build_nodes: NodeBuilder = engine_nodes,
) -> MCPServer:
    """The MCP server with the four tools. The arguments are for tests: by default each lookup
    opens a connection from DATABASE_URL and embeds the query through OpenRouter, and
    `classify_system` runs the engine's own nodes with the process's settings (read at the
    call) on the caller's key (`own_key_settings`)."""
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
        legacy: Annotated[
            LegacyStatus | None,
            Field(
                description="Art. 111(2), for a high-risk system placed on the market or put "
                "into service before its route's date and not significantly changed since: "
                "'legacy_unchanged' (its high-risk duties apply only after a significant "
                "change) or 'legacy_public_authority' (meant for public authorities: providers "
                "and deployers comply by 2 August 2030). Default: not such a system."
            ),
        ] = None,
    ) -> ObligationList:
        """List the duties, article references and dates that apply to a role for a system of
        a risk class, with any relief for SMEs and small mid-caps. Each duty has its label and
        formal wording in English and German."""
        # Only UnknownLawVersionError: any other ObligationsError is a broken table (ours), and
        # its message names a server path.
        with _tool_errors(UnknownLawVersionError):
            return list_obligations(
                role, risk_class, route, law_version, language=language, legacy=legacy
            )

    def classify_tool(
        description: Annotated[
            str,
            Field(
                min_length=1,
                max_length=ClassifyRequest.MAX_DESCRIPTION_CHARS,
                description="The AI system in plain words: what it does, who uses it and for "
                "what, whether the company built or bought it, and where it is used.",
            ),
        ],
        language: Annotated[
            Language, Field(description="The language of the description and the result.")
        ] = Language.EN,
        law_version: LawVersionArg = LawVersion.AMENDED,
        as_of: Annotated[
            date | None,
            Field(
                ge=AI_ACT_IN_FORCE,
                description="The date the law is read on (YYYY-MM-DD, from 2024-08-01; "
                "default today).",
            ),
        ] = None,
        answers: AnswersArg = None,
    ) -> ClassificationResult:
        """Classify one AI system under the EU AI Act: the full staged check (scope, prohibited
        practices, high-risk, transparency, then role and duties), each step citing the
        provisions it relies on, then the risk class.

        Returns the facts read from the description (each stated, inferred or assumed), each
        step run with its decision and citations (a check that settles the class, such as out
        of scope, ends the run), `risk_class` (null when a check could not be assessed),
        `status`, the `role` and its `obligations`, `follow_up_questions` for what the
        description leaves open, `law_version`, `as_of` and the `disclaimer`. When the result
        has follow-up questions, ask the user and call again with the same description and
        their `answers`. A run takes about a minute; its model calls are paid on the user's
        own OpenRouter key.
        """
        request = _classify_request(description, language, law_version, as_of, answers)
        run_settings = own_key_settings(settings or get_settings())
        try:
            run = run_classification(request, settings=run_settings, build_nodes=build_nodes)
        except ClassificationFailedError as error:
            # Its message names the failed check only. Its cause, which may quote the model's
            # reply, stays out of the message and the server log.
            raise ToolError(f"{error}. {FAILED_RUN_HINT}") from None
        return run.result

    for name, tool, annotations in (
        ("search_ai_act", search_tool, READ_ONLY),
        ("get_provision", provision_tool, READ_ONLY),
        ("list_obligations", obligations_tool, READ_ONLY),
        ("classify_system", classify_tool, CLASSIFY),
    ):
        # The docstring, without its source indentation, is what a calling agent reads.
        description = inspect.cleandoc(tool.__doc__ or "")
        server.add_tool(tool, name=name, description=description, annotations=annotations)
    return server


def own_key_settings(settings: Settings) -> Settings:
    """`settings` with `MCP_OPENROUTER_API_KEY` as the OpenRouter key, so every paid call of a
    run (the engine and refusal models, the query embeddings) goes on the MCP user's own key.
    Equal settings give equal copies, so the engine's clients are still built once per process
    (`aiact.engine.clients`). Raises a tool error when the key is not set: an MCP
    classification never falls back to the app's `OPENROUTER_API_KEY`."""
    key = settings.mcp_openrouter_api_key
    if key is None or not key.get_secret_value().strip():
        raise ToolError(MISSING_KEY)
    return settings.model_copy(update={"openrouter_api_key": key})


def _classify_request(
    description: str,
    language: Language,
    law_version: LawVersion,
    as_of: date | None,
    answers: dict[str, str] | None,
) -> ClassifyRequest:
    """The engine's request, whose limits the tool's schema repeats. A blank description or
    answer is a tool error naming the rule only: pydantic's own message would quote the
    caller's text."""
    values: dict[str, object] = {
        "description": description,
        "language": language,
        "law_version": law_version,
        "answers": answers or {},
    }
    if as_of is not None:
        values["as_of"] = as_of
    try:
        return ClassifyRequest.model_validate(values)
    except ValidationError as error:
        rules = "; ".join(detail["msg"] for detail in error.errors(include_input=False))
        raise ToolError(rules) from None


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
