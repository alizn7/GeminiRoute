# GeminiRoute

Automated discovery, validation, scoring and continuous monitoring of network
routes to Gemini-compatible endpoints. Healthy routes are republished as
subscription files on a schedule, with no manual steps.

**Status:** Phase 1 (core engine) and Phase 2 (automation) implemented.

## The funnel

Cheap filters run first so the expensive stage sees hundreds of nodes instead
of tens of thousands:

```
collect → parse → normalize → dedup → pre-validate → connectivity/latency
        → cap → geo → Gemini validation → score → generate → publish
```

Only the Gemini stage proves a node is actually useful. Everything before it
exists to make that stage affordable.

## How Gemini validation actually works

Python cannot speak VLESS, VMess or Trojan — those need a proxy core. So each
node is tested like this:

```
Node → xray config with a local SOCKS5 inbound → start xray
     → HTTPS request through 127.0.0.1:<port> → verdict → stop xray
```

A fixed pool of workers each own a port, so xray processes never collide and
the pool size directly caps how many exist at once.

`GEMINI_API_KEY` is optional:

| Mode | What it proves |
|---|---|
| key set | A real `generateContent` call returned candidates |
| no key | The request reached Google (400/401/403 all count) rather than a censor or a blackhole |

Without the xray binary the Gemini stage is skipped and the run is recorded as
degraded — it does not silently publish unverified nodes as verified.

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# Optional, needed for the Gemini stage:
#   download the xray binary and put it on PATH (see .github/workflows/discovery.yml)

cp sources.toml sources.local.toml   # then add real sources and enable them
```

## Commands

```bash
geminiroute doctor                    # check environment before blaming the pipeline
geminiroute collect                   # collect + parse only; fast feedback loop
geminiroute run-full-pipeline         # the whole thing; what the hourly job runs
```

Exit codes: `0` success, `1` no sources configured, `2` the run produced zero
publishable nodes (deliberately a failure, so a broken run cannot overwrite a
good subscription with an empty one).

## Checks

```bash
pytest
ruff check .
mypy geminiroute
```

## Configuration

`sources.toml` is content, reviewed like code. Everything else comes from the
environment:

| Variable | Default | Purpose |
|---|---|---|
| `GEMINI_API_KEY` | unset | Enables authenticated validation |
| `XRAY_PATH` | auto-detected | Explicit path to the proxy core |
| `GR_OUTPUT_DIR` | `dist` | Where `sub/` and `api/` are written |
| `GR_DATABASE_PATH` | `data/geminiroute.db` | SQLite file |
| `GR_CONNECTIVITY_CONCURRENCY` | `100` | Handshakes in flight |
| `GR_GEMINI_POOL_SIZE` | `12` | Concurrent xray processes |
| `GR_MAX_GEMINI_CANDIDATES` | `1500` | Cap on the expensive stage |
| `GR_HISTORY_RETENTION_DAYS` | `90` | History pruning window |

## Published output

Everything generated lives on the `gh-pages` branch, never on `main` — an
hourly job committing to `main` would bury real development history within
weeks.

```
https://<user>.github.io/geminiroute/
├── sub/
│   ├── all.txt          (base64, what clients poll)
│   ├── all.plain.txt    (human-readable, for debugging)
│   ├── gemini.txt       (verified only)
│   ├── best.txt         (top 30 by score)
│   ├── fast.txt         (verified and under 500 ms)
│   └── country/<code>.txt
├── api/
│   ├── nodes.json
│   └── stats.json       (the funnel, stage by stage)
└── data/geminiroute.db  (carried between runs; the runner is ephemeral)
```

## Scoring

`latency 30% + gemini 30% + reliability 25% + connection 15%`, each normalised
to 0..1 first so changing a weight cannot change the scale of the result. A
node with no history scores 0.5 on reliability — unknown, not bad.

## Workflows

| File | Trigger | Does |
|---|---|---|
| `ci.yml` | pull request, push to main | ruff, mypy, pytest on Python 3.12 and 3.13 |
| `discovery.yml` | hourly cron, manual dispatch | full pipeline, publish to `gh-pages` |
