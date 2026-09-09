"""EXERCISE — Shadowsocks parser (your turn).

These tests are written but skipped. To do the exercise:

  1. Create `geminiroute/parsing/shadowsocks.py` with a `ShadowsocksParser`.
  2. Register it in `geminiroute/parsing/registry.py` (_PARSERS + the
     `test_supported_schemes_is_reported` assertion in test_parser.py).
  3. Delete the `pytestmark` line below and run `pytest` until it is green.

Shadowsocks has TWO formats in the wild, which is exactly why it is a real
exercise and not a copy of the Trojan parser:

  SIP002 (modern):  ss://<base64(method:password)>@host:port#remark
  Legacy:           ss://<base64(method:password@host:port)>#remark

Hints:
  - Try SIP002 first; if there is no `@` outside the base64 blob, fall back.
  - The base64 here is usually URL-safe (`-` and `_`): base64.urlsafe_b64decode.
  - Padding is often stripped, same as VMess. Reuse that trick.
  - The credential for the fingerprint should be `method:password`, so that
    the same host:port with a rotated password is a different node.
  - Shadowsocks has no TLS layer: security is "" and transport is "" here.
    Let the Normalizer turn those into "none"/"tcp" — do not hardcode
    defaults in the parser.
"""

import base64

import pytest

from geminiroute.core.enums import ProtocolType
from geminiroute.parsing.registry import parse_line

pytestmark = pytest.mark.skip(reason="exercise: implement ShadowsocksParser, then delete this")

METHOD_PASSWORD = "aes-256-gcm:hunter2"


def _b64(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode()).decode().rstrip("=")


def test_sip002_format() -> None:
    node = parse_line(f"ss://{_b64(METHOD_PASSWORD)}@example.com:8388#SG-01")
    assert node is not None
    assert node.protocol is ProtocolType.SHADOWSOCKS
    assert node.address == "example.com"
    assert node.port == 8388
    assert node.credential == METHOD_PASSWORD
    assert node.remark == "SG-01"


def test_legacy_format() -> None:
    node = parse_line(f"ss://{_b64(f'{METHOD_PASSWORD}@example.com:8388')}#SG-02")
    assert node is not None
    assert node.address == "example.com"
    assert node.port == 8388
    assert node.credential == METHOD_PASSWORD


def test_both_formats_describe_the_same_node() -> None:
    """The whole point: the same server written two ways must dedup to one."""
    a = parse_line(f"ss://{_b64(METHOD_PASSWORD)}@example.com:8388#a")
    b = parse_line(f"ss://{_b64(f'{METHOD_PASSWORD}@example.com:8388')}#b")
    assert a is not None and b is not None
    assert a.fingerprint == b.fingerprint


def test_rotated_password_is_a_different_node() -> None:
    a = parse_line(f"ss://{_b64('aes-256-gcm:old')}@example.com:8388#a")
    b = parse_line(f"ss://{_b64('aes-256-gcm:new')}@example.com:8388#b")
    assert a is not None and b is not None
    assert a.fingerprint != b.fingerprint


def test_malformed_returns_none() -> None:
    assert parse_line("ss://!!!not-base64!!!@example.com:8388") is None
    assert parse_line(f"ss://{_b64(METHOD_PASSWORD)}@example.com:abc") is None
    assert parse_line(f"ss://{_b64('no-colon-here')}@example.com:8388") is None
