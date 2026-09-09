"""VMess: `vmess://<base64 of a JSON object>`

    {"v":"2","ps":"remark","add":"host","port":"443","id":"uuid",
     "aid":"0","net":"ws","type":"none","host":"","path":"/","tls":"tls"}

Values are frequently strings even when logically numeric. Note that `type` is
the header type; the transport is `net`.
"""

import base64
import binascii
import json
from typing import Any

from geminiroute.core.enums import ProtocolType
from geminiroute.core.models import Node
from geminiroute.parsing.base import Parser

# vmess JSON keys we promote or copy; anything else is ignored.
_PARAM_KEYS = {
    "host": "host",
    "path": "path",
    "sni": "sni",
    "alpn": "alpn",
    "fp": "fp",
    "aid": "aid",
    "scy": "scy",
    "type": "header_type",  # renamed to avoid clashing with the transport
}


def _decode_payload(payload: str) -> dict[str, Any] | None:
    """base64 -> JSON dict, or None if either step fails."""
    payload = payload.strip()
    # Many sources strip the '=' padding. Add it back before decoding.
    payload += "=" * (-len(payload) % 4)
    try:
        decoded = base64.b64decode(payload, validate=False).decode("utf-8")
        data = json.loads(decoded)
    except (binascii.Error, UnicodeDecodeError, json.JSONDecodeError, ValueError):
        return None
    return data if isinstance(data, dict) else None


class VmessParser(Parser):
    protocol = ProtocolType.VMESS
    scheme = "vmess"

    def parse(self, raw: str) -> Node | None:
        raw = raw.strip()
        prefix = f"{self.scheme}://"
        if not raw.lower().startswith(prefix):
            return None

        data = _decode_payload(raw[len(prefix) :])
        if data is None:
            return None

        address = str(data.get("add", "")).strip()
        credential = str(data.get("id", "")).strip()
        if not address or not credential:
            return None

        try:
            port = int(str(data.get("port", "")).strip())
        except ValueError:
            return None
        if not 1 <= port <= 65535:
            return None

        params = {
            out_key: str(data[in_key]).strip()
            for in_key, out_key in _PARAM_KEYS.items()
            if str(data.get(in_key, "")).strip()
        }

        return Node(
            protocol=self.protocol,
            address=address,
            port=port,
            transport=str(data.get("net", "")).strip(),
            security=str(data.get("tls", "")).strip(),
            credential=credential,
            params=params,
            remark=str(data.get("ps", "")).strip(),
            raw=raw,
        )
