from geminiroute.core.enums import ProtocolType
from geminiroute.core.models import Node
from geminiroute.validation import pre


def node(address: str = "real-host.net", port: int = 443, credential: str = "uuid",
         raw: str = "vless://uuid@real-host.net:443") -> Node:
    return Node(
        protocol=ProtocolType.VLESS, address=address, port=port,
        credential=credential, raw=raw,
    )


def test_good_node_passes() -> None:
    assert pre.check(node()).passed


def test_loopback_is_rejected() -> None:
    """Without this the validator would probe the CI runner itself."""
    assert pre.check(node(address="127.0.0.1")).error == "loopback address"


def test_private_ranges_are_rejected() -> None:
    for address in ("10.0.0.5", "192.168.1.1", "172.16.0.9"):
        assert pre.check(node(address=address)).error == "private address"


def test_link_local_is_rejected() -> None:
    assert pre.check(node(address="169.254.1.1")).error == "link-local address"


def test_public_ip_passes() -> None:
    assert pre.check(node(address="8.8.8.8")).passed


def test_placeholder_hostnames_are_rejected() -> None:
    assert pre.check(node(address="example.com")).error == "placeholder hostname"


def test_bare_hostname_without_dot_is_rejected() -> None:
    assert pre.check(node(address="myserver")).error == "hostname has no dot"


def test_invalid_hostname_is_rejected() -> None:
    assert pre.check(node(address="not a host!")).error == "invalid hostname"


def test_empty_address_is_rejected() -> None:
    assert pre.check(node(address="")).error == "empty address"


def test_missing_credential_is_rejected() -> None:
    assert pre.check(node(credential="")).error == "missing credential"


def test_missing_raw_config_is_rejected() -> None:
    """A node we cannot republish is useless even if it works."""
    assert pre.check(node(raw="")).error == "missing raw config"


def test_filter_returns_survivors_and_a_result_for_every_node() -> None:
    nodes = [node(), node(address="127.0.0.1"), node(address="8.8.8.8")]
    survivors, results = pre.filter_nodes(nodes)
    assert len(survivors) == 2
    assert len(results) == 3          # rejects are recorded too, not dropped
    assert sum(1 for r in results if not r.passed) == 1


# ---- hostname usability ----------------------------------------------------

def test_usable_hostnames_are_accepted() -> None:
    for name in ("example.net", "cdn.example.co.uk", "8.8.8.8", "2001:db8::1"):
        assert pre.is_usable_hostname(name), name


def test_hostnames_python_cannot_encode_are_rejected() -> None:
    """Python encodes SNI with the idna codec, which raises UnicodeError on an
    empty or over-long label. That is a ValueError, so it slips past socket and
    TLS error handling and ends the whole run."""
    for name in ("a..b", ".leading", "trailing.", "x" * 64 + ".com", "", "   "):
        assert not pre.is_usable_hostname(name), name


def test_over_length_hostnames_are_rejected() -> None:
    assert not pre.is_usable_hostname("a." * 200)
