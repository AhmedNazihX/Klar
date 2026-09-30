"""The recording scrubber in `tests/conftest.py`: headers and reasoning blobs never reach disk."""

import json

from tests.conftest import _scrub_response

REPLY = {
    "id": "gen-1",
    "choices": [
        {
            "message": {
                "content": '{"answer": "yes"}',
                "reasoning": "thinking",
                "reasoning_details": [{"type": "reasoning.encrypted", "data": "gAAAA"}],
            }
        }
    ],
    "usage": {"cost": 0.001},
}


def _recorded(body: str | bytes) -> dict[str, object]:
    response = {
        "headers": {"Set-Cookie": ["x"], "Content-Type": ["json"]},
        "body": {"string": body},
    }
    return _scrub_response(response)


def test_reasoning_fields_are_dropped_and_the_rest_is_kept() -> None:
    scrubbed = _recorded(json.dumps(REPLY).encode())
    body = scrubbed["body"]
    assert isinstance(body, dict)
    raw = body["string"]
    assert isinstance(raw, bytes)  # the HTTP client reads the recording back as bytes
    message = json.loads(raw)["choices"][0]["message"]
    assert message == {"content": '{"answer": "yes"}'}
    assert json.loads(raw)["usage"] == {"cost": 0.001}
    assert scrubbed["headers"] == {"Content-Type": ["json"]}


def test_a_text_body_stays_text_and_a_non_json_body_is_untouched() -> None:
    text = _recorded(json.dumps(REPLY))["body"]
    assert isinstance(text, dict)
    assert isinstance(text["string"], str)
    assert "reasoning_details" not in text["string"]
    assert _recorded(b"not json")["body"] == {"string": b"not json"}
