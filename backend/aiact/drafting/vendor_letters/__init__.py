"""The short vendor letters (INIT > Documentation drafting; decision 026 item 3; P28): a message
to the vendor about a prohibited result, and a request for the vendor's assessment of a legally
ambiguous one, in English and German.

A letter is built only from the result's facts (`fills.py`, verified on their own by
`facts.py`), its template's fixed wording (`templates.py`) and the user's interview answers;
the names and addresses stay "To fill in" until the user gives them. Like every draft it is
labelled DRAFT, carries the "guidance, not legal advice" notice and passes P8a's three
automatic checks. `draft.py` picks the letter a result calls for and drafts it.

This module imports nothing, so the drafting core (`prefill.py`, `facts_check.py`) can import
`fills` and `facts` without loading the templates that import the core.
"""
