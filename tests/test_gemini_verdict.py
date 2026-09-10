"""The Gemini stage's verdict logic, isolated from the network."""

import json

from geminiroute.validation.gemini import (
    interpret_api,
    interpret_web,
    is_region_blocked,
)

REGION_ERROR = json.dumps(
    {"error": {"code": 400, "message": "User location is not supported for the API use.",
               "status": "FAILED_PRECONDITION"}}
)
WEB_BLOCKED = (
    "<html><body>Gemini isn't currently supported in your country. "
    "Stay tuned!</body></html>"
)


def ok_body() -> str:
    return json.dumps({"candidates": [{"content": {"parts": [{"text": "hi"}]}}]})


# ---- region detection ------------------------------------------------------

def test_api_region_error_is_detected() -> None:
    assert is_region_blocked(REGION_ERROR)


def test_web_country_notice_is_detected() -> None:
    assert is_region_blocked(WEB_BLOCKED)


def test_normal_bodies_are_not_flagged() -> None:
    assert not is_region_blocked(ok_body())
    assert not is_region_blocked("<html>Gemini</html>")


def test_detection_is_case_insensitive() -> None:
    assert is_region_blocked("USER LOCATION IS NOT SUPPORTED FOR THE API USE.")


# ---- authenticated API probe -----------------------------------------------

def test_valid_response_passes() -> None:
    assert interpret_api(200, ok_body()).passed


def test_region_block_fails_even_though_it_reached_google() -> None:
    """The whole point: a node can reach Google and still be unusable."""
    verdict = interpret_api(400, REGION_ERROR)
    assert not verdict.passed
    assert verdict.error == "region not supported"


def test_plain_400_is_not_treated_as_success() -> None:
    assert not interpret_api(400, '{"error": {"message": "Invalid JSON payload"}}').passed


def test_200_without_candidates_fails() -> None:
    verdict = interpret_api(200, json.dumps({"promptFeedback": {}}))
    assert not verdict.passed and verdict.error == "200 without candidates"


def test_200_with_unparseable_body_fails() -> None:
    """A captive portal answering 200 with HTML must not count as success."""
    assert not interpret_api(200, "<html>login</html>").passed


def test_rejected_api_key_is_reported_distinctly() -> None:
    """Otherwise a bad key looks like every node being broken."""
    verdict = interpret_api(403, "")
    assert not verdict.passed and "api key rejected" in (verdict.error or "")


# ---- keyless web probe -----------------------------------------------------

def test_web_app_loads_and_passes() -> None:
    assert interpret_web(200, "<html><body>Gemini</body></html>").passed


def test_web_country_block_fails() -> None:
    verdict = interpret_web(200, WEB_BLOCKED)
    assert not verdict.passed and verdict.error == "region not supported"


def test_web_redirect_to_sign_in_still_counts_as_reaching_google() -> None:
    assert interpret_web(200, "<html>Sign in - Google Accounts</html>").passed


def test_proxy_auth_required_is_treated_as_blocked() -> None:
    assert not interpret_web(407, "").passed
    assert not interpret_api(407, "").passed


def test_legal_block_is_treated_as_blocked() -> None:
    assert not interpret_web(451, "").passed


def test_unexpected_status_fails_in_both_modes() -> None:
    assert not interpret_web(302, "").passed
    assert not interpret_api(302, "").passed


def test_free_port_returns_a_usable_loopback_port() -> None:
    """Ports are allocated per node: a terminated xray can hold its old port
    briefly, and reusing it would either fail to bind or look ready while
    pointing at a dying process."""
    import socket

    from geminiroute.validation.gemini import free_port

    port = free_port()
    assert 1024 < port <= 65535
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", port))


def test_consecutive_free_ports_differ() -> None:
    from geminiroute.validation.gemini import free_port

    assert len({free_port() for _ in range(5)}) > 1


# ---- API budget ------------------------------------------------------------

def _validator(**kwargs: object):
    from geminiroute.validation.gemini import GeminiValidator

    defaults: dict[str, object] = {"xray_path": "/bin/true"}
    defaults.update(kwargs)
    return GeminiValidator(**defaults)  # type: ignore[arg-type]


def test_no_api_calls_are_budgeted_without_a_key() -> None:
    assert _validator(api_key=None, api_confirm_limit=10).api_confirm_limit == 0


def test_budget_applies_when_a_key_is_present() -> None:
    assert _validator(api_key="k", api_confirm_limit=4).api_confirm_limit == 4


async def test_budget_is_spent_then_refused() -> None:
    """The free tier allows a few hundred calls a day and this runs hourly, so
    the budget must be a hard stop, not a suggestion."""
    import asyncio

    from geminiroute.validation import gemini as module

    original = module.API_MIN_INTERVAL
    module.API_MIN_INTERVAL = 0.0
    try:
        validator = _validator(api_key="k", api_confirm_limit=3)
        claims = [await validator._claim_api_call() for _ in range(5)]
    finally:
        module.API_MIN_INTERVAL = original
    assert claims == [True, True, True, False, False]
    assert isinstance(asyncio.Lock(), asyncio.Lock)


async def test_keyless_validator_never_claims_a_call() -> None:
    validator = _validator(api_key=None)
    assert await validator._claim_api_call() is False


def test_config_path_is_stripped_from_failure_reasons() -> None:
    """The temp path differs every run, so leaving it in gives every failure a
    unique string and the error histogram becomes one row per node."""
    from geminiroute.validation.gemini import clean_reason

    a = clean_reason(
        "Failed to start: main: failed to load config files: "
        r"[C:\Temp\geminiroute-aaaa\config.json] > infra/conf: Failed to build TLS config."
    )
    b = clean_reason(
        "Failed to start: main: failed to load config files: "
        r"[C:\Temp\geminiroute-bbbb\config.json] > infra/conf: Failed to build TLS config."
    )
    assert a == b
    assert "geminiroute-" not in a


# ---- exit location ---------------------------------------------------------

def trace_body(code: str, ip: str = "203.0.113.7") -> str:
    return (
        f"fl=123abc\nh=www.cloudflare.com\nip={ip}\nts=1789000000.1\n"
        f"visit_scheme=https\nuag=curl\ncolo=FRA\nloc={code}\ntls=TLSv1.3\n"
    )


def test_trace_output_is_parsed() -> None:
    from geminiroute.validation.gemini import parse_exit_trace

    geo = parse_exit_trace(trace_body("DE"))
    assert geo is not None
    assert geo.country_code == "DE"


def test_trace_without_a_location_yields_no_geo() -> None:
    from geminiroute.validation.gemini import parse_exit_trace

    assert parse_exit_trace("ip=1.2.3.4\nloc=XX1\n") is None
    assert parse_exit_trace("<html>captive portal</html>") is None
    assert parse_exit_trace("") is None


def test_supported_exit_country_passes() -> None:
    from geminiroute.validation.gemini import interpret_exit, parse_exit_trace

    assert interpret_exit(parse_exit_trace(trace_body("CA"))).passed
    assert interpret_exit(parse_exit_trace(trace_body("TR"))).passed
    assert interpret_exit(parse_exit_trace(trace_body("DE"))).passed


def test_blocked_exit_country_fails() -> None:
    """A node can be perfectly healthy and still useless because Gemini is not
    served where it comes out."""
    from geminiroute.validation.gemini import interpret_exit, parse_exit_trace

    for code in ("IR", "RU", "CN", "KP", "CU", "SY"):
        verdict = interpret_exit(parse_exit_trace(trace_body(code)))
        assert not verdict.passed
        assert code in (verdict.error or "")


def test_unknown_exit_country_is_not_treated_as_proof() -> None:
    """An unavailable lookup says nothing; the later checks still decide."""
    from geminiroute.validation.gemini import interpret_exit

    assert interpret_exit(None).passed


def test_country_code_is_normalised() -> None:
    from geminiroute.validation.gemini import interpret_exit, parse_exit_trace

    assert not interpret_exit(parse_exit_trace(trace_body("ir"))).passed
