"""Trojan: `trojan://<password>@<host>:<port>?security=tls&type=tcp#<remark>`

Same URI shape as VLESS; only the credential's meaning differs.
"""

from geminiroute.core.enums import ProtocolType
from geminiroute.core.models import Node
from geminiroute.parsing.base import Parser, node_from_uri_parts, split_uri


class TrojanParser(Parser):
    protocol = ProtocolType.TROJAN
    scheme = "trojan"

    def parse(self, raw: str) -> Node | None:
        parts = split_uri(raw, self.scheme)
        if parts is None:
            return None
        return node_from_uri_parts(self.protocol, parts, raw)
