"""The source registry: every legal text and guidance document the corpus is built from.

One `Source` per document and language (INIT, section "Legal corpus"). A language version that
isn't published has `url=None` and an `absent_reason`, so the manifest records it as absent
instead of the fetcher guessing.

Laws are the XHTML that EUR-Lex shows (`source_page`), downloaded from the Publications Office's
Cellar by CELEX number with `Accept-Language` picking the language. EUR-Lex itself sits behind a
bot challenge (HTTP 202) after a few requests and injects a per-response tracking script, so its
bytes differ on every download and a sha256 comparison would never be stable; Cellar serves the
same document without either. Guidelines are the Commission's PDFs, whose download links
(`ec.europa.eu/newsroom/dae/redirection/document/<n>`) are listed on `source_page`.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

Language = Literal["en", "de"]
Kind = Literal["html", "pdf"]
DocStatus = Literal["law", "consolidated", "final", "draft"]
"""Legal status of a document: an Official Journal act, the official consolidation, or guidance."""

LANGUAGES: tuple[Language, ...] = ("en", "de")
EURLEX_PAGE = "https://eur-lex.europa.eu/legal-content/{lang}/TXT/?uri=CELEX:{celex}"
CELLAR = "https://publications.europa.eu/resource/celex/{celex}"
CELLAR_LANGUAGE: dict[Language, str] = {"en": "eng", "de": "deu"}
"""ISO 639-2 codes, as Cellar expects them in `Accept-Language`."""
COMMISSION_PDF = "https://ec.europa.eu/newsroom/dae/redirection/document/{n}"
LIBRARY = "https://digital-strategy.ec.europa.eu/{lang}/library/"
POLICIES = "https://digital-strategy.ec.europa.eu/{lang}/policies/"
CHECKED_ON = "2026-09-27"
"""The date the absent German versions below were last checked by hand."""


class Source(BaseModel):
    """One document in one language, as the fetcher needs it."""

    model_config = ConfigDict(frozen=True)

    id: str
    language: Language
    title: str
    kind: Kind
    status: DocStatus
    version: str
    """Publication date (ISO) of the version fetched; for the consolidation, its cut-off date."""
    source_page: str
    """The human-facing page the download URL comes from."""
    url: str | None = None
    absent_reason: str | None = None
    accept_language: str | None = None
    """For a Cellar URL: the ISO 639-2 language to request (the URL itself is language-neutral)."""

    @model_validator(mode="after")
    def _url_xor_reason(self) -> "Source":
        if (self.url is None) == (self.absent_reason is None):
            raise ValueError(f"{self.id}.{self.language}: set exactly one of url, absent_reason")
        return self

    @property
    def filename(self) -> str:
        """The raw file name under `data/raw/`, for example `ai-act.en.html`."""
        return f"{self.id}.{self.language}.{self.kind}"


def _eurlex(
    doc_id: str, celex: str, title: str, status: DocStatus, version: str
) -> tuple[Source, ...]:
    """The EN and DE XHTML versions of one EUR-Lex document, fetched from Cellar."""
    return tuple(
        Source(
            id=doc_id,
            language=lang,
            title=title,
            kind="html",
            status=status,
            version=version,
            source_page=EURLEX_PAGE.format(lang=lang.upper(), celex=celex),
            url=CELLAR.format(celex=celex),
            accept_language=CELLAR_LANGUAGE[lang],
        )
        for lang in LANGUAGES
    )


def _commission_pdf(
    doc_id: str,
    title: str,
    status: DocStatus,
    version: str,
    page: str,
    en: int,
    de: int | None,
) -> tuple[Source, ...]:
    """The EN and DE versions of a Commission PDF; `en`/`de` are its document numbers.

    `de=None` means the German Commission page links only the English PDF.
    """
    numbers: dict[Language, int | None] = {"en": en, "de": de}
    return tuple(
        Source(
            id=doc_id,
            language=lang,
            title=title,
            kind="pdf",
            status=status,
            version=version,
            source_page=page.format(lang=lang),
            url=None if n is None else COMMISSION_PDF.format(n=n),
            absent_reason=None
            if n is not None
            else (
                "No German version published: the German Commission page links only the "
                f"English PDF (checked {CHECKED_ON})."
            ),
        )
        for lang, n in numbers.items()
    )


DEFINITION_PAGE = (
    LIBRARY + "commission-publishes-guidelines-ai-system-definition-"
    "facilitate-first-ai-acts-rules-application"
)
PROHIBITED_PAGE = (
    LIBRARY + "commission-publishes-guidelines-prohibited-artificial-intelligence-"
    "ai-practices-defined-ai-act"
)
HIGH_RISK_PAGE = LIBRARY + "draft-commission-guidelines-classification-high-risk-ai-systems"
ART50_PAGE = LIBRARY + "guidelines-transparency-obligations-providers-and-deployers-ai-systems"
CODE_OF_PRACTICE_PAGE = POLICIES + "code-practice-ai-generated-content"
HIGH_RISK_TITLE = "Draft Commission Guidelines on the classification of high-risk AI systems"
HIGH_RISK_DATE = "2026-05-19"

SOURCES: tuple[Source, ...] = (
    *_eurlex("ai-act", "32024R1689", "Regulation (EU) 2024/1689 (AI Act)", "law", "2024-07-12"),
    *_eurlex(
        "omnibus",
        "32026R1744",
        "Regulation (EU) 2026/1744 (Digital Omnibus on AI)",
        "law",
        "2026-07-24",
    ),
    *_eurlex(
        "ai-act-consolidated",
        "02024R1689-20260727",
        "AI Act, consolidated text as of 27 July 2026",
        "consolidated",
        "2026-07-27",
    ),
    *_commission_pdf(
        "guide-definition",
        "Commission Guidelines on the definition of an AI system",
        "final",
        "2025-02-06",
        DEFINITION_PAGE,
        en=112455,
        de=118628,
    ),
    *_commission_pdf(
        "guide-prohibited",
        "Commission Guidelines on prohibited AI practices",
        "final",
        "2025-02-04",
        PROHIBITED_PAGE,
        en=112367,
        de=118661,
    ),
    *_commission_pdf(
        "guide-high-risk-general",
        f"{HIGH_RISK_TITLE}: general principles",
        "draft",
        HIGH_RISK_DATE,
        HIGH_RISK_PAGE,
        en=128559,
        de=None,
    ),
    *_commission_pdf(
        "guide-high-risk-annex-i",
        f"{HIGH_RISK_TITLE}: Annex I",
        "draft",
        HIGH_RISK_DATE,
        HIGH_RISK_PAGE,
        en=128560,
        de=None,
    ),
    *_commission_pdf(
        "guide-high-risk-annex-iii",
        f"{HIGH_RISK_TITLE}: Annex III",
        "draft",
        HIGH_RISK_DATE,
        HIGH_RISK_PAGE,
        en=128561,
        de=None,
    ),
    *_commission_pdf(
        "guide-art50",
        "Commission Guidelines on the transparency obligations under Article 50",
        "final",
        "2026-07-20",
        ART50_PAGE,
        en=131215,
        de=None,
    ),
    *_commission_pdf(
        "code-of-practice-transparency",
        "Code of Practice on Transparency of AI-generated Content",
        "final",
        "2026-06-10",
        CODE_OF_PRACTICE_PAGE,
        en=129555,
        de=None,
    ),
)
