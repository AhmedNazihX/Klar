"""What a check's fixed texts say about one reading of an open question (E12), shared by the
texts modules and `questions`, which builds the contract's readings from it."""

from dataclasses import dataclass

from aiact.schemas import RiskClass


@dataclass(frozen=True)
class ReadingSide:
    """What a step knows about one reading besides its explanation: its title, what follows if
    it holds, the class it gives (None when it gives none by itself) and the provision it rests
    on, quoted from the step's citations."""

    title: str
    consequence: str
    risk_class: RiskClass | None = None
    provision_id: str | None = None
