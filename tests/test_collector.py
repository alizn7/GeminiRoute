"""Collector tests against a real local HTTP server.
"""

import base64
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from geminiroute.collection.collector import (
    collect_source,
    get_collector,
    maybe_decode_base64,
    split_lines,
)
from geminiroute.core.models import Source

BODIES: dict[str, tuple[int, bytes]] = {}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        status, body = BODIES.get(self.path, (404, b"nope"))
        self.send_response(status)
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args: object) -> None:
        pass


@pytest.fixture
def server() -> Iterator[str]:
    httpd = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


def test_plain_body_is_split_into_lines(server: str) -> None:
    BODIES["/plain"] = (200, b"vless://a\n\nvless://b\n")
    result = collect_source(Source("s", "raw", f"{server}/plain"))
    assert result.ok and result.lines == ["vless://a", "vless://b"]


def test_base64_subscription_is_decoded(server: str) -> None:
    payload = base64.b64encode(b"vless://a\nvmess://b").decode()
    BODIES["/b64"] = (200, payload.encode())
    result = collect_source(Source("s", "raw", f"{server}/b64"))
    assert result.lines == ["vless://a", "vmess://b"]


def test_plain_text_that_happens_to_decode_is_left_alone() -> None:
    """The classic failure: a plain list decodes into binary noise and every
    node silently disappears. The '://' check is what prevents it."""
    assert maybe_decode_base64("vless://aaaa") == "vless://aaaa"


def test_http_error_degrades_the_source_but_does_not_raise(server: str) -> None:
    result = collect_source(Source("s", "raw", f"{server}/missing"))
    assert not result.ok and result.lines == []


def test_unreachable_host_is_reported_as_an_error() -> None:
    result = collect_source(Source("s", "raw", "http://127.0.0.1:9/x"))
    assert not result.ok and result.error


def test_unknown_source_type_is_reported() -> None:
    result = collect_source(Source("s", "gopher", "http://x"))
    assert not result.ok and "unknown source type" in (result.error or "")


def test_disabled_sources_are_skipped() -> None:
    from geminiroute.collection.collector import collect_all
    assert collect_all([Source("s", "raw", "http://127.0.0.1:9/x", enabled=False)]) == []


def test_collector_registry_resolves_known_types() -> None:
    assert get_collector("raw") is not None
    assert get_collector("GITHUB") is not None
    assert get_collector("nope") is None


def test_split_lines_drops_blanks_and_trims() -> None:
    assert split_lines("  a  \n\n  b\n") == ["a", "b"]
