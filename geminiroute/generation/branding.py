"""Rewriting the display label of a published config.

Clients show the config's own label, so republishing a source's label means
advertising whoever produced it. These functions replace that label with our
own numbered one, leaving every functional part of the config untouched.

Where the label lives depends on the protocol: it is the URI fragment for
VLESS/Trojan/Shadowsocks, and the `ps` field inside the base64 JSON for VMess.
Rewriting the wrong one produces a config that still works but keeps the old
name, which is why VMess is handled separately rather than by string
replacement.
"""

from __future__ import annotations

import base64
import binascii
import json
from urllib.parse import quote

from geminiroute.core.enums import ProtocolType

BRAND = "GeminiRoute"
DEFAULT_FLAG = "🏴"

# Regional indicator symbols start here; 'A' maps to the first one.
_FLAG_BASE = 0x1F1E6


def flag_emoji(country_code: str | None) -> str:
    """Turn an ISO 3166-1 alpha-2 code into its flag emoji."""
    if not country_code or len(country_code) != 2 or not country_code.isalpha():
        return DEFAULT_FLAG
    return "".join(chr(_FLAG_BASE + ord(c) - ord("A")) for c in country_code.upper())


def make_label(index: int, country_code: str | None, brand: str = BRAND) -> str:
    """`1.🇩🇪 GeminiRoute`"""
    return f"{index}.{flag_emoji(country_code)} {brand}"


def _rebrand_vmess(raw: str, label: str) -> str:
    payload = raw[len("vmess://") :].strip()
    try:
        decoded = base64.b64decode(payload + "=" * (-len(payload) % 4)).decode("utf-8")
        data = json.loads(decoded)
    except (binascii.Error, UnicodeDecodeError, json.JSONDecodeError, ValueError):
        return raw
    if not isinstance(data, dict):
        return raw

    data["ps"] = label
    encoded = base64.b64encode(
        json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).decode("ascii")
    return "vmess://" + encoded


def _rebrand_fragment(raw: str, label: str) -> str:
    base = raw.split("#", 1)[0]
    # safe="" so the flag and space are percent-encoded; some clients choke on
    # a literal space in a URI fragment.
    return f"{base}#{quote(label, safe='')}"


def rebrand(raw: str, protocol: ProtocolType, label: str) -> str:
    """Return the config with its label replaced. Unparseable input is returned
    unchanged rather than dropped — a working config with the wrong name beats
    no config."""
    if not raw:
        return raw
    if protocol is ProtocolType.VMESS:
        return _rebrand_vmess(raw, label)
    return _rebrand_fragment(raw, label)
