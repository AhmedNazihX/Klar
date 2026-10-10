"""P7: the plain "are we compliant?" questions are caught before any search; questions about what
compliance requires are not."""

import pytest

from aiact.qa.scope import is_compliance_question


@pytest.mark.parametrize(
    "question",
    [
        "Are we GDPR compliant?",
        "Are we, as a deployer, compliant with the AI Act?",
        "Am I in compliance?",
        "Is our chatbot compliant with Article 50?",
        "Is my company compliant?",
        "Do we comply with the AI Act?",
        "Does our recruiting tool comply with the rules?",
        "We bought a chatbot. Are we compliant?",
        "Sind wir konform?",
        "Sind wir mit unserem Chatbot KI-Verordnung-konform?",
        "Ist unser Tool rechtskonform?",
        "Bin ich compliant?",
    ],
)
def test_asking_whether_we_comply_is_a_compliance_question(question: str) -> None:
    assert is_compliance_question(question)


@pytest.mark.parametrize(
    "question",
    [
        "What do we need to do to comply with Article 50?",
        "What does compliance with Article 9 involve?",
        "Is it legal to use emotion recognition at work?",
        "What counts as a deployer?",
        "Are deployers bound by Article 26?",
        "Welche Pflichten erfüllen wir als Betreiber?",
        "Was bedeutet Konformitätsbewertung?",
        "Wie werden wir konform?",
    ],
)
def test_asking_what_the_act_requires_is_not(question: str) -> None:
    assert not is_compliance_question(question)
