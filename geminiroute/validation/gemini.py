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
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from geminiroute.core.enums import ValidationStage
from geminiroute.core.models import Node, ValidationResult
from geminiroute.observability.logging import get_logger
from geminiroute.validation.xray import UnsupportedNodeError, build_config

log = get_logger(__name__)

GEMINI_HOST = "generativelanguage.googleapis.com"
MODEL = "gemini-2.0-flash"
DEFAULT_TIMEOUT = 20.0
DEFAULT_POOL_SIZE = 12
BASE_PORT = 24000
XRAY_STARTUP_TIMEOUT = 8.0

# Statuses proving the request reached Google. 400/401/403 mean it arrived and
# was rejected on its merits; a 5xx is Google's problem, not the node's.
REACHED_GOOGLE = frozenset({200, 400, 401, 403, 404, 429, 500, 502, 503})
# Statuses indicating an interception layer rather than Google.
BLOCKED_HINTS = frozenset({407, 451})


@dataclass(frozen=True)
class Verdict:
    passed: bool
    error: str | None = None


def interpret(status_code: int, body: str, has_api_key: bool) -> Verdict:
    """Decide whether a response proves the route works. Pure function."""
    if status_code in BLOCKED_HINTS:
        return Verdict(False, f"blocked upstream (HTTP {status_code})")

    if has_api_key:
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

    if status_code in REACHED_GOOGLE:
        return Verdict(True)
    return Verdict(False, f"HTTP {status_code}")


def find_xray_binary(explicit: str | None = None) -> str | None:
    """Locate the xray executable, or None if it is not installed."""
    if explicit:
        return explicit if Path(explicit).exists() else None
    return shutil.which("xray") or shutil.which("sing-box")


async def _wait_for_port(port: int, timeout: float) -> bool:
    """Poll until the SOCKS port accepts a connection, or give up.

    Polled rather than a fixed sleep: xray binds in ~150ms, but a loaded
    runner can take much longer.
    """
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        try:
            _, writer = await asyncio.open_connection("127.0.0.1", port)
        except OSError:
            await asyncio.sleep(0.1)
            continue
        writer.close()
        with contextlib.suppress(OSError):
            await writer.wait_closed()
        return True
    return False


class GeminiValidator:
    """Runs Gemini reachability checks through a pool of xray processes."""

    def __init__(
        self,
        xray_path: str,
        api_key: str | None = None,
        pool_size: int = DEFAULT_POOL_SIZE,
        timeout: float = DEFAULT_TIMEOUT,
        base_port: int = BASE_PORT,
    ) -> None:
        self.xray_path = xray_path
        self.api_key = api_key
        self.pool_size = pool_size
        self.timeout = timeout
        self.base_port = base_port

    # ------------------------------------------------------------------ #

    def _request_url(self) -> str:
        if self.api_key:
            return f"https://{GEMINI_HOST}/v1beta/models/{MODEL}:generateContent"
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
            config = build_config(node, port)
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
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            try:
                if not await _wait_for_port(port, XRAY_STARTUP_TIMEOUT):
                    return failure("proxy failed to start")

                headers = {"Content-Type": "application/json"}
                if self.api_key:
                    headers["x-goog-api-key"] = self.api_key

                try:
                    async with httpx.AsyncClient(
                        proxy=f"socks5://127.0.0.1:{port}",
                        timeout=self.timeout,
                    ) as client:
                        response = await client.post(
                            self._request_url(),
                            headers=headers,
                            json=self._request_payload(),
                        )
                except httpx.TimeoutException:
                    return failure("timeout")
                except httpx.HTTPError as exc:
                    return failure(f"{type(exc).__name__}: {exc}")

                verdict = interpret(response.status_code, response.text, bool(self.api_key))
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
        queue: asyncio.Queue[tuple[int, Node]] = asyncio.Queue()
        for item in enumerate(nodes):
            queue.put_nowait(item)

        results: list[ValidationResult | None] = [None] * len(nodes)

        async def worker(worker_index: int) -> None:
            port = self.base_port + worker_index
            while True:
                try:
                    index, node = queue.get_nowait()
                except asyncio.QueueEmpty:
                    return
                try:
                    results[index] = await self._run_one(node, port)
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
            authenticated=bool(self.api_key),
        )
        return final
