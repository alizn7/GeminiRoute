"""Validate every config shape we generate against the actual xray binary.

Config-building bugs are the worst kind here: xray rejects the config, the node
is recorded as a failure, and nothing distinguishes "our config was wrong" from
"the node is dead". Finding them one at a time means a full pipeline run per
question.

This checks all of them at once. Each variant exercises one branch of
`build_config`, is written to a temp file and offered to `xray run -test`. What
comes back is a table of which shapes this particular binary accepts — which
differs between xray versions, so it has to be asked rather than assumed.

The variants are pure data, so the list itself is unit-testable without xray.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import tempfile
from dataclasses import dataclass
from pathlib import Path

from geminiroute.core.enums import ProtocolType
from geminiroute.core.models import Node
from geminiroute.validation.gemini import clean_reason, detect_allow_insecure, free_port
from geminiroute.validation.xray import UnsupportedNodeError, build_config

TEST_TIMEOUT = 10.0
UUID = "11111111-2222-3333-4444-555555555555"
# A syntactically valid X25519 public key. REALITY rejects anything that is not
# 43 base64url characters, so a short placeholder would fail the variant for a
# reason that has nothing to do with our config generation.
REALITY_KEY = "jNXHt1yRo0vDuchQlIP6Z0ZvjT3KtzVI-T4E7RoLJS0"


@dataclass(frozen=True)
class Variant:
    """One config shape to offer the binary."""

    name: str
    node: Node
    allow_insecure: bool = True


@dataclass(frozen=True)
class CheckResult:
    name: str
    accepted: bool
    reason: str = ""


def _node(
    protocol: ProtocolType = ProtocolType.VLESS,
    transport: str = "tcp",
    security: str = "none",
    credential: str = UUID,
    **params: str,
) -> Node:
    return Node(
        protocol=protocol,
        address="check.example.net",
        port=443,
        transport=transport,
        security=security,
        credential=credential,
        params=dict(params),
        raw="vless://check",
    )


def variants(allow_insecure: bool = True) -> list[Variant]:
    """Every branch of `build_config` that a real source can produce.

    `allow_insecure` mirrors what the pipeline would actually send, so the
    report shows real outcomes. The two explicit allowInsecure variants below
    always test both settings, since that disagreement is the point.
    """
    default = allow_insecure
    return [
        # --- protocols -------------------------------------------------
        Variant("vless / tcp / none", _node()),
        Variant("vmess / tcp / none", _node(ProtocolType.VMESS, aid="0", scy="auto")),
        Variant("trojan / tcp / none", _node(ProtocolType.TROJAN, credential="password")),
        Variant(
            "shadowsocks / tcp / none",
            _node(ProtocolType.SHADOWSOCKS, credential="aes-256-gcm:secret"),
        ),
        # --- TLS layer -------------------------------------------------
        Variant("tls, allowInsecure on", _node(security="tls", sni="cdn.example.net")),
        Variant(
            "tls, allowInsecure off",
            _node(security="tls", sni="cdn.example.net"),
            allow_insecure=False,
        ),
        Variant(
            "tls + fingerprint",
            _node(security="tls", sni="a.example.net", fp="chrome"),
            default,
        ),
        Variant(
            "tls + alpn",
            _node(security="tls", sni="a.example.net", alpn="h2,http/1.1"),
            default,
        ),
        Variant("xtls (mapped to tls)", _node(security="xtls", sni="a.example.net"), default),
        Variant(
            "reality",
            _node(
                security="reality",
                sni="www.microsoft.com",
                pbk=REALITY_KEY,
                sid="ab",
                fp="chrome",
            ),
        ),
        # --- transports ------------------------------------------------
        Variant("ws", _node(transport="ws", path="/ray", host="cdn.example.net")),
        Variant(
            "ws + tls",
            _node(transport="ws", security="tls", path="/ray", sni="a.example.net"),
            default,
        ),
        Variant("grpc", _node(transport="grpc", servicename="GunService")),
        Variant(
            "grpc + tls", _node(transport="grpc", security="tls", servicename="Gun"), default
        ),
        Variant("http / h2 (via xhttp)", _node(transport="http", path="/h2", host="cdn.a.net")),
        Variant("httpupgrade", _node(transport="httpupgrade", path="/up", host="cdn.example.net")),
        Variant("xhttp", _node(transport="xhttp", path="/x")),
        Variant(
            "xhttp + tls",
            _node(transport="xhttp", security="tls", path="/x", sni="a.com"),
            default,
        ),
        Variant("xhttp stream-one", _node(transport="xhttp", path="/x", mode="stream-one")),
        Variant("xhttp packet-up", _node(transport="xhttp", path="/x", mode="packet-up")),
        # --- flow ------------------------------------------------------
        Variant(
            "vless + flow + reality",
            _node(
                security="reality",
                flow="xtls-rprx-vision",
                sni="www.microsoft.com",
                pbk=REALITY_KEY,
                sid="ab",
                fp="chrome",
            ),
        ),
    ]


async def check_variant(xray_path: str, variant: Variant) -> CheckResult:
    """Offer one config to the binary and report whether it was accepted."""
    try:
        config = build_config(variant.node, free_port(), variant.allow_insecure)
    except UnsupportedNodeError as exc:
        return CheckResult(variant.name, False, f"not built: {exc}")

    with tempfile.TemporaryDirectory(prefix="geminiroute-check-") as tmpdir:
        path = Path(tmpdir) / "config.json"
        path.write_text(json.dumps(config), encoding="utf-8")
        try:
            process = await asyncio.create_subprocess_exec(
                xray_path,
                "run",
                "-test",
                "-c",
                str(path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
        except OSError as exc:
            return CheckResult(variant.name, False, f"cannot run xray: {exc}")

        try:
            stdout, _ = await asyncio.wait_for(process.communicate(), TEST_TIMEOUT)
        except TimeoutError:
            # `-test` unsupported, so the config was accepted and xray started
            # serving it. That is the answer.
            with contextlib.suppress(ProcessLookupError):
                process.kill()
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(process.wait(), 2.0)
            return CheckResult(variant.name, True, "accepted (binary ignores -test)")

    if process.returncode == 0:
        return CheckResult(variant.name, True)

    text = stdout.decode("utf-8", errors="replace").strip()
    last = clean_reason(text.splitlines()[-1]) if text else ""
    return CheckResult(variant.name, False, last[:400])


async def run_checks(xray_path: str) -> tuple[bool, list[CheckResult]]:
    """Probe the binary's capabilities, then run every variant as the pipeline
    would actually send it.

    Returns the probed allowInsecure support alongside the results, because a
    failure of the explicit "allowInsecure on" variant is expected on binaries
    that removed it — and reporting it as a problem would be noise.

    Sequential: a couple of dozen checks, and interleaved output from parallel
    xray processes is harder to attribute.
    """
    allow_insecure = await detect_allow_insecure(xray_path)
    results = [await check_variant(xray_path, v) for v in variants(allow_insecure)]
    return allow_insecure, results


@dataclass(frozen=True)
class ProbeReport:
    """What one node's tunnel actually returned, step by step."""

    parsed: bool
    exit_ip: str = ""
    exit_country: str = ""
    web_status: int = 0
    web_bytes: int = 0
    region_marker_found: bool = False
    web_excerpt: str = ""
    web_body: str = ""
    api_status: int = 0
    api_excerpt: str = ""
    error: str = ""


async def probe_node(
    xray_path: str, raw: str, api_key: str | None = None, keep_body: bool = False
) -> ProbeReport:
    """Run one config through the full check and report what came back.

    Aggregate counts say how many nodes failed, never what a specific node
    returned. This shows the raw answers for a single config, which is what
    settles questions like "does the web app really say the country is
    unsupported, or is that rendered by JavaScript we never run?".
    """
    import httpx

    from geminiroute.normalization.normalizer import normalize
    from geminiroute.parsing.registry import parse_line
    from geminiroute.validation.gemini import (
        BROWSER_UA,
        EXIT_TRACE_URL,
        GEMINI_HOST,
        GEMINI_WEB_URL,
        MODEL,
        XRAY_STARTUP_TIMEOUT,
        _read_output,
        _wait_for_port,
        detect_allow_insecure,
        is_region_blocked,
        parse_exit_trace,
    )

    node = parse_line(raw.strip())
    if node is None:
        return ProbeReport(parsed=False, error="config could not be parsed")
    node = normalize(node)

    allow_insecure = await detect_allow_insecure(xray_path)
    port = free_port()
    try:
        config = build_config(node, port, allow_insecure)
    except UnsupportedNodeError as exc:
        return ProbeReport(parsed=True, error=f"config not built: {exc}")

    with tempfile.TemporaryDirectory(prefix="geminiroute-probe-") as tmpdir:
        path = Path(tmpdir) / "config.json"
        path.write_text(json.dumps(config), encoding="utf-8")
        process = await asyncio.create_subprocess_exec(
            xray_path, "run", "-c", str(path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        try:
            if not await _wait_for_port(port, XRAY_STARTUP_TIMEOUT, process):
                return ProbeReport(parsed=True, error=f"proxy failed to start: "
                                                      f"{await _read_output(process)}")

            async with httpx.AsyncClient(
                proxy=f"socks5://127.0.0.1:{port}", timeout=20.0, follow_redirects=True
            ) as client:
                try:
                    trace = await client.get(EXIT_TRACE_URL)
                except httpx.HTTPError as exc:
                    return ProbeReport(parsed=True, error=f"exit lookup failed: {exc!r}")

                geo = parse_exit_trace(trace.text)
                # Normalised once: GeoInfo.country_code is optional, and the
                # report's field is not.
                exit_country = (geo.country_code or "") if geo else ""
                exit_ip = ""
                for line in trace.text.splitlines():
                    if line.startswith("ip="):
                        exit_ip = line[3:].strip()

                try:
                    web = await client.get(
                        GEMINI_WEB_URL,
                        headers={"User-Agent": BROWSER_UA},
                    )
                except httpx.HTTPError as exc:
                    return ProbeReport(
                        parsed=True,
                        exit_ip=exit_ip,
                        exit_country=exit_country,
                        error=f"web fetch failed: {exc!r}",
                    )

                excerpt = _excerpt(web.text)
                api_status = 0
                api_excerpt = ""
                if api_key:
                    api = await client.post(
                        f"https://{GEMINI_HOST}/v1beta/models/{MODEL}:generateContent",
                        headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
                        json={"contents": [{"parts": [{"text": "hi"}]}],
                              "generationConfig": {"maxOutputTokens": 1}},
                    )
                    api_status = api.status_code
                    api_excerpt = api.text[:300]

                return ProbeReport(
                    parsed=True,
                    exit_ip=exit_ip,
                    exit_country=exit_country,
                    web_body=web.text if keep_body else "",
                    web_status=web.status_code,
                    web_bytes=len(web.text),
                    region_marker_found=is_region_blocked(web.text),
                    web_excerpt=excerpt,
                    api_status=api_status,
                    api_excerpt=api_excerpt,
                )
        finally:
            with contextlib.suppress(ProcessLookupError):
                process.terminate()
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(process.wait(), 5.0)


def _excerpt(html: str, window: int = 160) -> str:
    """The part of the page that talks about availability, if any."""
    lowered = html.lower()
    for needle in ("your country", "not supported", "isn't available", "not available"):
        index = lowered.find(needle)
        if index != -1:
            start = max(0, index - window // 2)
            return " ".join(html[start : start + window].split())
    return " ".join(html[:window].split())
