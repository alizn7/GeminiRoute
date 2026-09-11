"""Parser registry.

Adding a protocol: write the class, add it to `_PARSERS`. Nothing downstream
changes, because every other stage only sees `Node`.
"""

from collections.abc import Iterable

from geminiroute.core.models import Node
from geminiroute.parsing.base import Parser
from geminiroute.parsing.trojan import TrojanParser
from geminiroute.parsing.vless import VlessParser
from geminiroute.parsing.vmess import VmessParser

_PARSERS: tuple[Parser, ...] = (
    VlessParser(),
    VmessParser(),
    TrojanParser(),
)

_BY_SCHEME: dict[str, Parser] = {p.scheme: p for p in _PARSERS}


def supported_schemes() -> tuple[str, ...]:
    return tuple(sorted(_BY_SCHEME))


def get_parser(raw: str) -> Parser | None:
    """Pick a parser by the URI scheme, or None for an unknown protocol."""
    scheme, separator, _ = raw.strip().partition("://")
    if not separator:
        return None
    return _BY_SCHEME.get(scheme.lower())


def parse_line(raw: str) -> Node | None:
    """Parse a single config line. Unknown or malformed -> None."""
    parser = get_parser(raw)
    return parser.parse(raw) if parser is not None else None


def parse_lines(lines: Iterable[str]) -> list[Node]:
    """Parse many lines, skipping comments, blanks and anything unparseable."""
    nodes = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        try:
            node = parse_line(stripped)
        except Exception:  # noqa: BLE001
            # Parsers promise to return None rather than raise; this is the
            # net that makes that true even when one forgets.
            continue
        if node is not None:
            nodes.append(node)
    return nodes
