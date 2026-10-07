"""How a result names a provision, in English and German.

Shared by the engine's texts (E4-E6, writing decisions) and the drafted documents (P8a), so
drafting needn't import the engine.
"""

from aiact.schemas import Language

DE = Language.DE


def article_provision_name(provision_id: str, language: Language) -> str:
    """An article's paragraph or point: `art:50:1` is "Art. 50(1)" in English and "Art. 50 Abs. 1"
    in German; `art:5:1:ba` is "Art. 5(1)(ba)" or "Art. 5 Abs. 1 Buchst. ba"; `art:5:1:c:i` is
    "Art. 5(1)(c)(i)" or "Art. 5 Abs. 1 Buchst. c Ziff. i". An article with points and no
    paragraphs: `art:16:a` is "Art. 16(a)" or "Art. 16 Buchst. a"."""
    _, article, paragraph, *points = provision_id.split(":")
    if not paragraph[0].isdigit():
        if language is DE:
            return f"Art. {article} Buchst. " + " Ziff. ".join((paragraph, *points))
        return f"Art. {article}" + "".join(f"({p})" for p in (paragraph, *points))
    if language is DE:
        letters = ("Buchst.", "Ziff.")
        tail = "".join(f" {letters[min(n, 1)]} {p}" for n, p in enumerate(points))
        return f"Art. {article} Abs. {paragraph}{tail}"
    return f"Art. {article}({paragraph})" + "".join(f"({p})" for p in points)


def annex_point_name(point: str, language: Language) -> str:
    """An Annex point: `annex:III:4:a` is "Annex III point 4(a)" in English and "Anhang III
    Nummer 4 Buchstabe a" in German; `annex:I:A:11` is "Annex I Section A point 11" or "Anhang I
    Abschnitt A Nummer 11"."""
    parts = point.split(":")[1:]
    if parts[0] == "I" and len(parts) == 3:
        _, section, number = parts
        if language is DE:
            return f"Anhang I Abschnitt {section} Nummer {number}"
        return f"Annex I Section {section} point {number}"
    number, letter = parts[1], parts[2] if len(parts) > 2 else None
    if language is DE:
        return f"Anhang III Nummer {number}" + (f" Buchstabe {letter}" if letter else "")
    return f"Annex III point {number}" + (f"({letter})" if letter else "")
