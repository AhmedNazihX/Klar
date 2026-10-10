"""Q&A over the corpus with citations (P7): general AI Act questions and questions about one
result, answered from the provisions found and never about whether anyone complies."""

from aiact.qa.answer import QA_TOP_K, Searcher, answer_question, generate, shown_text
from aiact.qa.models import AnswerKind, ModelReply, QaAnswer

__all__ = [
    "QA_TOP_K",
    "AnswerKind",
    "ModelReply",
    "QaAnswer",
    "Searcher",
    "answer_question",
    "generate",
    "shown_text",
]
