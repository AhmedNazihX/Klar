"""The default test run can't reach the network; only `live` tests may (see conftest.py)."""

import socket

import pytest

# TEST-NET-3 (RFC 5737): never routed, and the guard raises before any packet is sent.
UNROUTABLE_ADDRESS = ("203.0.113.1", 443)

# Run in a child pytest session with the conftest hook. Both tests connect to a local
# listener, and `--allowed-hosts` matches nothing, so only the `live` marker can let one through.
INNER_TESTS = """
import socket

import pytest


def _connect_to_local_listener() -> None:
    with socket.create_server(("127.0.0.1", 0)) as server:
        socket.create_connection(server.getsockname(), timeout=1).close()


@pytest.mark.live
def test_live_may_connect() -> None:
    _connect_to_local_listener()


def test_unmarked_is_blocked() -> None:
    with pytest.raises(RuntimeError, match="Network is disabled"):
        _connect_to_local_listener()
"""


def test_unmarked_network_call_is_blocked() -> None:
    with pytest.raises(RuntimeError, match="Network is disabled"):
        socket.create_connection(UNROUTABLE_ADDRESS, timeout=1)


def test_only_live_tests_get_through_the_block(pytester: pytest.Pytester) -> None:
    pytester.makeconftest("from tests.conftest import pytest_collection_modifyitems  # noqa\n")
    pytester.makeini("[pytest]\nmarkers =\n    live: calls a real service\n")
    pytester.makepyfile(INNER_TESTS)
    result = pytester.runpytest("--block-network", "--allowed-hosts=no-host-matches-this")
    result.assert_outcomes(passed=2)
