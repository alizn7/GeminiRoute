"""Gemini validation — the only stage that proves a node is useful.

Per node: write config, start xray on a private SOCKS port, wait for the port,
request through the proxy, read the verdict, kill xray. Concurrency is a fixed
pool of workers that each own a port, so two nodes can never collide.

With GEMINI_API_KEY a real generateContent call is made. Without one, an
unauthenticated call to the same host still proves the request reached Google
rather than a censor or a blackhole.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import re
import shutil
import socket
import tempfile
from dataclasses import dataclass
from pathlib import Path

from geminiroute.core.enums import ValidationStage
from geminiroute.core.models import Node, ValidationResult
from geminiroute.observability.logging import get_logger
from geminiroute.validation.xray import UnsupportedNodeError, build_config

log = get_logger(__name__)

GEMINI_HOST = "generativelanguage.googleapis.com"
GEMINI_WEB_URL = "https://gemini.google.com/"
MODEL = "gemini-2.0-flash"
DEFAULT_TIMEOUT = 20.0
DEFAULT_POOL_SIZE = 12
# API calls per run. The free tier allows roughly 10-15 requests per minute and
# a few hundred per day, while a run tests over a thousand candidates every
# hour — so the key cannot validate everything. It is spent confirming the
# nodes that already passed the free web probe.
DEFAULT_API_CONFIRM_LIMIT = 10
# ~10 RPM. Cheap insurance against a burst of 429s poisoning good nodes.
API_MIN_INTERVAL = 6.0
BASE_PORT = 24000
# A rejected config now exits immediately and is detected as such, so this
# ceiling only ever costs time for a genuinely slow start — which happens when
# twenty xray processes launch at once on a loaded machine.
XRAY_STARTUP_TIMEOUT = 12.0
PROBE_UUID = "00000000-0000-0000-0000-000000000000"
# The web app serves a different, script-only shell to unknown clients; the
# country notice is in the HTML a browser gets.
BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

# Statuses proving the request reached Google. 401/403 mean it arrived and was
# rejected on its merits; a 5xx is Google's problem, not the node's.
#
# 400 is deliberately NOT here. Google answers 400 FAILED_PRECONDITION when the
# exit IP is in a country where Gemini is unavailable, so treating 400 as
# "reached Google" published exactly the nodes that cannot be used.
REACHED_GOOGLE = frozenset({200, 401, 403, 404, 429, 500, 502, 503})
# Statuses indicating an interception layer rather than Google.
BLOCKED_HINTS = frozenset({407, 451})

# A node can reach Google perfectly and still be useless, because Gemini is not
# offered in the country the node exits from. That refusal is what these
# markers identify — in the API's JSON error and in the web app's HTML.
REGION_BLOCK_MARKERS = (
    "user location is not supported",
    "not supported for the api use",
    "isn't currently supported in your country",
    "is not currently supported in your country",
    "not available in your country",
    "isn't available in your country",
)


@dataclass(frozen=True)
class Verdict:
    passed: bool
    error: str | None = None


def is_region_blocked(body: str) -> bool:
    """Does this response say Gemini is unavailable where the node exits?"""
    lowered = body.lower()
    return any(marker in lowered for marker in REGION_BLOCK_MARKERS)


def interpret_api(status_code: int, body: str) -> Verdict:
    """Verdict for an authenticated generateContent call."""
    if is_region_blocked(body):
        return Verdict(False, "region not supported")
    if status_code in BLOCKED_HINTS:
        return Verdict(False, f"blocked upstream (HTTP {status_code})")

    if status_code == 200:
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            return Verdict(False, "200 with unparseable body")
        if "candidates" in payload:
            return Verdict(True)
        return Verdict(False, "200 without candidates")

    if status_code in (401, 403):
        # The route is fine, the key is not. Surfaced distinctly, or every
        # node looks broken.
        return Verdict(False, f"api key rejected (HTTP {status_code})")
    return Verdict(False, f"HTTP {status_code}")


def interpret_web(status_code: int, body: str) -> Verdict:
    """Verdict for an unauthenticated fetch of the Gemini web app.

    Weaker than the API check but the only region signal available without a
    key: the web app states plainly, in the page body, when Gemini is not
    offered in the visitor's country.
    """
    if is_region_blocked(body):
        return Verdict(False, "region not supported")
    if status_code in BLOCKED_HINTS:
        return Verdict(False, f"blocked upstream (HTTP {status_code})")
    if status_code in REACHED_GOOGLE:
        return Verdict(True)
    return Verdict(False, f"HTTP {status_code}")


def find_xray_binary(explicit: str | None = None) -> str | None:
    """Locate the xray executable, or None if it is not installed."""
    if explicit:
        return explicit if Path(explicit).exists() else None
    return shutil.which("xray") or shutil.which("sing-box")


def free_port() -> int:
    """Ask the OS for an unused loopback port.

    A port per node, not per worker: a terminated xray can leave its port
    bound briefly, and the next launch on that port would either fail to bind
    or — worse — see the dying listener and be treated as ready.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


async def _wait_for_port(
    port: int, timeout: float, process: asyncio.subprocess.Process | None = None
) -> bool:
    """Poll until the SOCKS port accepts a connection, or give up.

    Polled rather than a fixed sleep: xray binds in ~150ms, but a loaded
    runner can take much longer. Returns early if the process has already
    exited, so a config xray rejects fails in milliseconds, not seconds.
    """
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        if process is not None and process.returncode is not None:
            return False
        try:
            _, writer = await asyncio.open_connection("127.0.0.1", port)
        except OSError:
            await asyncio.sleep(0.1)
            continue
        with contextlib.suppress(OSError, AttributeError, RuntimeError):
            writer.transport.abort()
        return True
    return False


# The config path is a fresh temp directory every time, so leaving it in the
# message gives every failure a unique string and the error histogram degrades
# into one row per node instead of one row per cause.
_CONFIG_PATH_RE = re.compile(r"\s*\[[^\]]*config\.json\]\s*>?\s*")


def clean_reason(text: str) -> str:
    """Strip the per-run temp path so identical failures group together."""
    return _CONFIG_PATH_RE.sub(" ", text).strip()


async def detect_allow_insecure(xray_path: str, timeout: float = 8.0) -> bool:
    """Ask the binary whether it still accepts `allowInsecure`.

    Recent xray builds removed the field and refuse any config containing it,
    while older ones need it to tolerate the self-signed certificates a lot of
    working nodes use. Neither answer is safe to assume, and getting it wrong
    silently kills every TLS node — so the binary is asked once per run.

    A config that xray accepts either exits 0 under `-test` or starts serving;
    both count as support. A rejected config exits non-zero.
    """
    probe = {
        "log": {"loglevel": "error"},
        "inbounds": [
            {
                "listen": "127.0.0.1",
                "port": free_port(),
                "protocol": "socks",
                "settings": {"auth": "noauth", "udp": False},
            }
        ],
        "outbounds": [
            {
                "protocol": "vless",
                "settings": {
                    "vnext": [
                        {
                            "address": "example.invalid",
                            "port": 443,
                            "users": [{"id": PROBE_UUID, "encryption": "none"}],
                        }
                    ]
                },
                "streamSettings": {
                    "network": "tcp",
                    "security": "tls",
                    "tlsSettings": {"serverName": "example.invalid", "allowInsecure": True},
                },
            }
        ],
    }

    with tempfile.TemporaryDirectory(prefix="geminiroute-probe-") as tmpdir:
        path = Path(tmpdir) / "probe.json"
        path.write_text(json.dumps(probe), encoding="utf-8")
        try:
            process = await asyncio.create_subprocess_exec(
                xray_path, "run", "-test", "-c", str(path),
                # Discarded, not piped: only the exit code matters here, and an
                # unread pipe leaves a transport asyncio complains about later.
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
        except OSError:
            return False

        try:
            code = await asyncio.wait_for(process.wait(), timeout)
        except TimeoutError:
            # Still running means the config was accepted and xray is serving
            # it, which is itself the answer.
            with contextlib.suppress(ProcessLookupError):
                process.kill()
            # Reaped, or asyncio complains about the transport at GC time.
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(process.wait(), 2.0)
            return True
        return code == 0


async def _read_output(process: asyncio.subprocess.Process, limit: int = 600) -> str:
    """Whatever xray complained about, trimmed to one useful line.

    Read from stdout, not stderr: xray writes its log to stdout, so capturing
    only stderr yields an empty string and a failure with no explanation.
    stderr is merged into stdout by the launcher below.
    """
    if process.stdout is None:
        return ""
    with contextlib.suppress(Exception):
        data = await asyncio.wait_for(process.stdout.read(4096), 2.0)
        text = data.decode("utf-8", errors="replace").strip()
        if text:
            # The last line is the actual complaint; earlier ones are banners.
            return clean_reason(text.splitlines()[-1])[:limit]
    return ""


class GeminiValidator:
    """Runs Gemini reachability checks through a pool of xray processes."""

    def __init__(
        self,
        xray_path: str,
        api_key: str | None = None,
        pool_size: int = DEFAULT_POOL_SIZE,
        timeout: float = DEFAULT_TIMEOUT,
        base_port: int = BASE_PORT,
        api_confirm_limit: int = DEFAULT_API_CONFIRM_LIMIT,
    ) -> None:
        self.xray_path = xray_path
        self.api_key = api_key
        self.pool_size = pool_size
        self.timeout = timeout
        self.base_port = base_port
        self.api_confirm_limit = api_confirm_limit if api_key else 0
        # Resolved once per run by validate_all, before any node is tested.
        self.allow_insecure = True
        self._api_budget = self.api_confirm_limit
        self._api_lock = asyncio.Lock()
        self._api_last_call = 0.0

    async def _claim_api_call(self) -> bool:
        """Take one slot from the run's API budget, pacing calls to stay under
        the per-minute limit. False when the budget is spent."""
        async with self._api_lock:
            if self._api_budget <= 0:
                return False
            self._api_budget -= 1
            loop = asyncio.get_running_loop()
            wait = API_MIN_INTERVAL - (loop.time() - self._api_last_call)
            if wait > 0:
                await asyncio.sleep(wait)
            self._api_last_call = loop.time()
            return True

    # ------------------------------------------------------------------ #

    def _request_url(self) -> str:
        return f"https://{GEMINI_HOST}/v1beta/models/{MODEL}:generateContent"

    def _request_payload(self) -> dict[str, object]:
        # Smallest possible prompt: this runs against hundreds of nodes every
        # hour and bills real tokens.
        return {
            "contents": [{"parts": [{"text": "hi"}]}],
            "generationConfig": {"maxOutputTokens": 1},
        }

    async def _run_one(self, node: Node, port: int) -> ValidationResult:
        import httpx  # lazy: the rest of the pipeline needs no HTTP client

        def failure(error: str) -> ValidationResult:
            return ValidationResult(
                node_fingerprint=node.fingerprint,
                stage=ValidationStage.GEMINI,
                passed=False,
                error=error,
            )

        try:
            config = build_config(node, port, self.allow_insecure)
        except UnsupportedNodeError as exc:
            return failure(str(exc))

        with tempfile.TemporaryDirectory(prefix="geminiroute-") as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            config_path.write_text(json.dumps(config), encoding="utf-8")

            process = await asyncio.create_subprocess_exec(
                self.xray_path,
                "run",
                "-c",
                str(config_path),
                # Captured, not discarded: when xray refuses a config it says
                # exactly why, and that message is the only useful diagnostic.
                # Both streams are merged because xray logs to stdout.
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            try:
                if not await _wait_for_port(port, XRAY_STARTUP_TIMEOUT, process):
                    reason = await _read_output(process)
                    # The node's own transport settings are appended so the
                    # histogram shows which combination xray rejects, rather
                    # than only that something was rejected.
                    shape = (
                        f"[security={node.security or 'none'} "
                        f"transport={node.transport or 'tcp'} "
                        f"fp={node.params.get('fp', '-')} "
                        f"alpn={node.params.get('alpn', '-')}]"
                    )
                    return failure(
                        f"proxy failed to start: {reason} {shape}"
                        if reason
                        else f"proxy failed to start {shape}"
                    )

                try:
                    async with httpx.AsyncClient(
                        proxy=f"socks5://127.0.0.1:{port}",
                        timeout=self.timeout,
                        follow_redirects=True,
                    ) as client:
                        # Free probe first, on every node: it costs no quota
                        # and already catches dead proxies and country blocks.
                        response = await client.get(
                            GEMINI_WEB_URL, headers={"User-Agent": BROWSER_UA}
                        )
                        verdict = interpret_web(response.status_code, response.text)

                        # The key is scarce, so it is spent only on nodes that
                        # already look good — turning a likely pass into a
                        # proven one.
                        if verdict.passed and await self._claim_api_call():
                            api_response = await client.post(
                                self._request_url(),
                                headers={
                                    "Content-Type": "application/json",
                                    "x-goog-api-key": self.api_key or "",
                                },
                                json=self._request_payload(),
                            )
                            verdict = interpret_api(api_response.status_code, api_response.text)
                except httpx.TimeoutException:
                    return failure("timeout")
                except httpx.HTTPError as exc:
                    # Several httpx errors stringify to "", which produced the
                    # useless "ConnectError: " in the histogram.
                    detail = str(exc).strip() or "no detail"
                    return failure(f"{type(exc).__name__}: {detail}")

                return ValidationResult(
                    node_fingerprint=node.fingerprint,
                    stage=ValidationStage.GEMINI,
                    passed=verdict.passed,
                    error=verdict.error,
                )
            finally:
                # Always reap, including on cancellation: a leaked xray holds
                # its port and fails the next node assigned to this worker.
                with contextlib.suppress(ProcessLookupError):
                    process.terminate()
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(process.wait(), 5.0)
                if process.returncode is None:
                    with contextlib.suppress(ProcessLookupError):
                        process.kill()

    async def validate_all(self, nodes: list[Node]) -> list[ValidationResult]:
        """Run every node through the pool, preserving input order."""
        self.allow_insecure = await detect_allow_insecure(self.xray_path)
        log.info("xray_capabilities", allow_insecure=self.allow_insecure)

        queue: asyncio.Queue[tuple[int, Node]] = asyncio.Queue()
        for item in enumerate(nodes):
            queue.put_nowait(item)

        results: list[ValidationResult | None] = [None] * len(nodes)

        async def worker(worker_index: int) -> None:
            while True:
                try:
                    index, node = queue.get_nowait()
                except asyncio.QueueEmpty:
                    return
                try:
                    results[index] = await self._run_one(node, free_port())
                finally:
                    queue.task_done()

        workers = min(self.pool_size, max(len(nodes), 1))
        await asyncio.gather(*(worker(i) for i in range(workers)))

        final = [
            r
            or ValidationResult(
                node_fingerprint=nodes[i].fingerprint,
                stage=ValidationStage.GEMINI,
                passed=False,
                error="not tested",
            )
            for i, r in enumerate(results)
        ]
        log.info(
            "gemini_batch_done",
            total=len(final),
            passed=sum(1 for r in final if r.passed),
            api_confirmations_used=self.api_confirm_limit - self._api_budget,
            api_confirmation_budget=self.api_confirm_limit,
        )
        return final
