"""Label rewriting. The functional half of every config must survive intact."""

import base64
import json
from urllib.parse import unquote, urlsplit

from geminiroute.core.enums import ProtocolType
from geminiroute.generation.branding import flag_emoji, make_label, rebrand

VLESS = "vless://uuid@a.example.net:443?type=ws&security=tls&sni=cdn.example.net#SomeoneElse"


def vmess_link(ps: str = "SomeoneElse") -> str:
    payload = json.dumps({
        "v": "2", "ps": ps, "add": "b.example.net", "port": "8443",
        "id": "uuid", "net": "ws", "path": "/ray", "tls": "tls",
    })
    return "vmess://" + base64.b64encode(payload.encode()).decode()


def test_flag_from_country_code() -> None:
    assert flag_emoji("DE") == "🇩🇪"
    assert flag_emoji("nl") == "🇳🇱"


def test_flag_falls_back_when_code_is_missing_or_junk() -> None:
    assert flag_emoji(None) == flag_emoji("") == flag_emoji("XYZ") == flag_emoji("1")


def test_label_shape() -> None:
    assert make_label(12, "DE") == "12.🇩🇪 GeminiRoute"


def test_vless_label_is_replaced() -> None:
    result = rebrand(VLESS, ProtocolType.VLESS, make_label(3, "DE"))
    assert unquote(urlsplit(result).fragment) == "3.🇩🇪 GeminiRoute"
    assert "SomeoneElse" not in result


def test_vless_functional_parts_survive() -> None:
    result = rebrand(VLESS, ProtocolType.VLESS, make_label(1, "DE"))
    parts = urlsplit(result)
    assert parts.username == "uuid"
    assert parts.hostname == "a.example.net"
    assert parts.port == 443
    assert parts.query == "type=ws&security=tls&sni=cdn.example.net"


def test_fragment_is_percent_encoded() -> None:
    """A literal space in a fragment breaks some clients."""
    result = rebrand(VLESS, ProtocolType.VLESS, make_label(1, "DE"))
    assert " " not in result.split("#", 1)[1]


def test_config_without_a_fragment_gets_one() -> None:
    bare = "vless://uuid@a.example.net:443"
    assert "#" in rebrand(bare, ProtocolType.VLESS, make_label(1, "DE"))


def test_vmess_ps_is_replaced_inside_the_payload() -> None:
    result = rebrand(vmess_link(), ProtocolType.VMESS, make_label(7, "NL"))
    payload = result[len("vmess://"):]
    data = json.loads(base64.b64decode(payload + "=" * (-len(payload) % 4)))
    assert data["ps"] == "7.🇳🇱 GeminiRoute"


def test_vmess_other_fields_survive() -> None:
    result = rebrand(vmess_link(), ProtocolType.VMESS, make_label(7, "NL"))
    payload = result[len("vmess://"):]
    data = json.loads(base64.b64decode(payload + "=" * (-len(payload) % 4)))
    assert data["add"] == "b.example.net"
    assert data["port"] == "8443"
    assert data["id"] == "uuid"
    assert data["path"] == "/ray"


def test_undecodable_vmess_is_returned_unchanged() -> None:
    """A working config with the wrong name beats no config."""
    assert rebrand("vmess://!!!", ProtocolType.VMESS, "x") == "vmess://!!!"


def test_empty_input_is_returned_unchanged() -> None:
    assert rebrand("", ProtocolType.VLESS, "x") == ""


def test_trojan_uses_the_fragment_path() -> None:
    result = rebrand("trojan://pw@c.example.net:443#Old", ProtocolType.TROJAN,
                     make_label(2, "FR"))
    assert unquote(urlsplit(result).fragment) == "2.🇫🇷 GeminiRoute"
    assert urlsplit(result).username == "pw"
