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

Every candidate is first asked, through its own tunnel, where it comes out.
Geolocating the node's address instead reports the CDN edge in front of it, so
a config fronted by a Canadian edge looks Canadian while exiting somewhere
Gemini refuses to serve. The exit country decides both the published flag and
whether the node is rejected outright.

Then every candidate gets the free probe; the API key confirms the winners.

| Step | Applies to | Costs quota | What it proves |
|---|---|---|---|
| `GET ip-api.com` through the tunnel | every candidate | no | The real exit IP and country |
| `GET gemini.google.com` | every candidate | no | The web app loaded and did not say Gemini is unavailable in that country |
| `POST generateContent` | first N that passed step 1 | yes | A real call returned candidates — definitive |

The split exists because the free tier allows roughly 10–15 requests a minute
and a few hundred a day, while a run tests over a thousand candidates every
hour. Spending the key on everything would exhaust the quota in one run and
turn every later node into a 429. `GR_GEMINI_API_CONFIRM_LIMIT` (default 10)
caps calls per run; they are paced to stay inside the per-minute limit.

**Reaching Google is not enough.** A node can connect to Google perfectly and
still be useless, because Gemini is not offered where the node exits. Google
signals this with `400 FAILED_PRECONDITION / "User location is not supported
for the API use."`, and the web app says so in the page body. Both are treated
as failures (`region not supported`), not successes.

Set `GEMINI_API_KEY` if you can: the keyless path infers the region from the
web app's HTML, which is weaker than the API's explicit refusal.

## API access is not web access

Nodes are verified against the Gemini API, which decides on the caller's IP.
The Gemini web app applies a second gate: the country of the Google account
signed into the browser. A verified node can still show "Gemini isn't currently
supported in your country" for that reason alone — signing out (a private
window) isolates which of the two is refusing.

The same gate applies to obtaining a `GEMINI_API_KEY`: AI Studio requires a
sign-in and reads the account's country, not the exit IP.

## Published labels

Every published config's display label is rewritten to `<n>.<flag> GeminiRoute`
— numbered from 1 within each file, with the flag from the node's exit country.
Only the label changes; the credential, host, port, transport and every
parameter are republished exactly as collected. Change `BRAND` in
`geminiroute/generation/branding.py` to rename.

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
geminiroute errors --stage gemini     # why nodes failed a stage, grouped
geminiroute sources                   # what each source actually contributed
geminiroute xray-check                # which config shapes this xray accepts
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
| `GR_GEMINI_POOL_SIZE` | `20` | Concurrent xray processes |
| `GR_GEMINI_API_CONFIRM_LIMIT` | `10` | API calls per run (quota guard) |
| `GR_MAX_GEMINI_CANDIDATES` | `1200` | Cap on the expensive stage |
| `GR_HISTORY_RETENTION_DAYS` | `90` | History pruning window |

## Published output

Everything generated lives on the `gh-pages` branch, never on `main` — an
hourly job committing to `main` would bury real development history within
weeks.

```
https://<user>.github.io/geminiroute/
├── index.html           (landing page: links plus the last run's funnel)
├── .nojekyll            (Pages must serve the tree as-is, not build it)
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

## Checking config generation

`geminiroute xray-check` offers every config shape the generator produces to
the xray binary and reports which ones it accepts. Run it after changing xray
versions or touching `validation/xray.py`.

It exists because xray versions disagree about what a valid config is —
`allowInsecure` was accepted for years and is refused by recent builds — and a
refused config is recorded as a node failure, indistinguishable from a dead
node. One command answers what would otherwise take a pipeline run per
question.

The pipeline itself probes the same question at startup (`xray_capabilities` in
the log) and emits `allowInsecure` only when the binary in use still takes it.

## Scheduling

A node that fails is not retried immediately: backoff pushes it out 5 minutes,
then 30, then hours, up to a daily ceiling, and three straight failures mark it
dead. Nodes inside their window are skipped at the top of a run, so the hourly
slots go to nodes that might actually work. A dead node re-enters the pool as
`recheck` once its wait elapses — dead is a state, not a grave.

Candidates for the expensive stage are chosen proven-first, then fastest. Pure
latency ordering over-selects CDN-fronted configs: their TLS handshake succeeds
against the CDN whether or not the node behind it is alive, so they look fast
and healthy right up until the Gemini stage rejects them.

## Scoring

`latency 30% + gemini 30% + reliability 25% + connection 15%`, each normalised
to 0..1 first so changing a weight cannot change the scale of the result. A
node with no history scores 0.5 on reliability — unknown, not bad.

## Workflows

| File | Trigger | Does |
|---|---|---|
| `ci.yml` | pull request, push to main | ruff, mypy, pytest on Python 3.12 and 3.13 |
| `discovery.yml` | hourly cron, manual dispatch | full pipeline, publish to `gh-pages` |
