"""VLESS: `vless://<uuid>@<host>:<port>?type=ws&security=tls&...#<remark>`
"""

from geminiroute.core.enums import ProtocolType
from geminiroute.core.models import Node
from geminiroute.parsing.base import Parser, node_from_uri_parts, split_uri


class VlessParser(Parser):
    protocol = ProtocolType.VLESS
    scheme = "vless"

    def parse(self, raw: str) -> Node | None:
        parts = split_uri(raw, self.scheme)
        if parts is None:
            return None
        return node_from_uri_parts(self.protocol, parts, raw)
