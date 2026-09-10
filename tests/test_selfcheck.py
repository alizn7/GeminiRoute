"""The self-check's variant list. The variants are pure data, so coverage of
every build_config branch can be asserted without xray present."""

from geminiroute.core.enums import ProtocolType
from geminiroute.validation.selfcheck import variants
from geminiroute.validation.xray import build_config


def test_every_protocol_is_covered() -> None:
    covered = {v.node.protocol for v in variants()}
    assert covered == set(ProtocolType)


def test_every_transport_we_emit_settings_for_is_covered() -> None:
    covered = {v.node.transport for v in variants()}
    assert {"tcp", "ws", "grpc", "http", "httpupgrade", "xhttp"} <= covered


def test_variants_follow_the_probed_capability() -> None:
    """The report should mirror what the pipeline would really send, or every
    TLS variant shows up red on a binary that dropped allowInsecure."""
    explicit = {"tls, allowInsecure on", "tls, allowInsecure off"}
    for variant in variants(allow_insecure=False):
        if variant.name not in explicit and variant.node.security == "tls":
            assert variant.allow_insecure is False


def test_both_sides_of_the_allow_insecure_switch_are_covered() -> None:
    """The switch exists because binaries disagree; testing one side would
    leave the disagreement undetected."""
    flags = {v.allow_insecure for v in variants() if v.node.security == "tls"}
    assert flags == {True, False}


def test_reality_and_flow_are_covered() -> None:
    securities = {v.node.security for v in variants()}
    assert "reality" in securities
    assert any(v.node.params.get("flow") for v in variants())


def test_every_variant_actually_builds() -> None:
    """A variant that cannot even be built would silently test nothing."""
    for variant in variants():
        config = build_config(variant.node, 24000, variant.allow_insecure)
        assert config["outbounds"][0]["protocol"] == variant.node.protocol.value


def test_variant_names_are_unique() -> None:
    names = [v.name for v in variants()]
    assert len(names) == len(set(names))
