# GeminiRoute

Public proxy configs, collected every hour and kept only if they actually reach
the Gemini API from a country Google serves.

**[Live status &rarr;](https://alizn7.github.io/GeminiRoute/)**

Most lists publish a count. This one publishes what it threw away: a typical run
collects around 7,000 configs and verifies a few hundred. The rest are dead,
duplicated, or exit somewhere Gemini refuses to answer.

## Get a link

Paste one of these into your client's subscription field. That is the whole
setup.

| Link | What is in it |
|---|---|
| `https://alizn7.github.io/GeminiRoute/sub/best.txt` | The 30 highest scoring routes. **Start here.** |
| `https://alizn7.github.io/GeminiRoute/sub/gemini.txt` | Every route that passed verification, best first |
| `https://alizn7.github.io/GeminiRoute/sub/fast.txt` | Verified and under 500 ms |
| `https://alizn7.github.io/GeminiRoute/sub/all.txt` | Every route tested, verified or not |

Want one country? Swap in its two-letter code:
`.../sub/country/de.txt`, `.../sub/country/us.txt`, `.../sub/country/nl.txt`.
The [status page](https://alizn7.github.io/GeminiRoute/) lists which countries
had routes in the last run.

Every file has a `.plain.txt` twin that is not base64 encoded, if you want to
read it rather than import it.

### Machine-readable

| Link | What is in it |
|---|---|
| `https://alizn7.github.io/GeminiRoute/api/stats.json` | The funnel, success rate, countries, per-source yield |
| `https://alizn7.github.io/GeminiRoute/api/nodes.json` | Every tested route with its score, latency and country. No credentials. |

## If Gemini says your country is unsupported

The Gemini **web app** has a second gate that a proxy cannot change: the country
of the Google account signed into your browser. A working route can still be
refused for that reason alone.

Open `gemini.google.com` in a private window, signed out, to tell the two apart.
If it works there, the route is fine and the block is on your account.

The same gate applies to getting a `GEMINI_API_KEY`: AI Studio reads the
account's country, not the exit IP.

## How a route earns its place

```
collect -> parse -> normalize -> dedup -> plausibility -> connect
        -> exit check -> Gemini -> publish
```

Cheap filters run first so the expensive stage sees hundreds of candidates
instead of thousands.

The step that matters most is the **exit check**. Each candidate is asked, from
inside its own tunnel, where it comes out. Geolocating the config's address
instead would report the CDN edge in front of it &mdash; which is how thirty
routes once ended up labelled Canada while exiting somewhere Gemini refuses to
serve. Routes exiting from a country Google does not serve are dropped there.

Routes are then scored on latency (30%), Gemini verification (30%), reliability
over the last 30 days (25%) and handshake quality (15%). A route with no history
scores 0.5 on reliability &mdash; unknown, not bad &mdash; so new routes start
mid-pack and earn their position.

A route that fails is not retried immediately: backoff pushes it out 5 minutes,
then 30, then hours. Three straight failures mark it dead, and a dead route
re-enters the pool once its wait elapses.

## Published labels

Every published config's label is rewritten to `<n>.<flag> GeminiRoute`,
numbered from 1 within each file, with the flag of its real exit country. Only
the label changes &mdash; credential, host, port, transport and every parameter
are republished exactly as collected.

## Running it yourself

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

The Gemini stage needs the [Xray](https://github.com/XTLS/Xray-core/releases)
binary. Put it on `PATH` or set `XRAY_PATH`.

| Command | What it does |
|---|---|
| `geminiroute doctor` | Check the environment before blaming the pipeline |
| `geminiroute collect` | Collect and parse only &mdash; no network validation |
| `geminiroute run-full-pipeline` | The whole thing. `--limit N` to try a subset |
| `geminiroute errors --stage gemini` | Why routes failed, grouped by reason |
| `geminiroute sources` | What each source actually contributed |
| `geminiroute xray-check` | Which config shapes your xray build accepts |
| `geminiroute probe-node "<config>"` | Run one config through the full check and print what came back |

`xray-check` exists because xray versions disagree about what a valid config is
&mdash; `allowInsecure` was accepted for years and is refused by recent builds
&mdash; and a refused config is recorded as a route failure, indistinguishable
from a dead route.

### Checks

```bash
ruff check . && mypy geminiroute && pytest
```

## Adding a source

`sources.toml` is content, not code. Add an entry, run `geminiroute collect`,
and check that `unique` actually moves &mdash; a source that only repeats what
others supply costs run time and returns nothing.

```toml
[[source]]
name = "some-list"
type = "raw"                      # or "github" for a contents-API directory
url = "https://raw.githubusercontent.com/owner/repo/main/sub.txt"
enabled = true
```

After a few runs, the `sources` block in `stats.json` shows the yield each one
really produced. Anything under 2% is costing more than it returns.

## Configuration

`sources.toml` holds the source list; everything else comes from the
environment.

| Variable | Default | Purpose |
|---|---|---|
| `GEMINI_API_KEY` | unset | Upgrades verification from "reached Google" to "the model answered" |
| `XRAY_PATH` | auto-detected | Explicit path to the proxy core |
| `GR_MAX_GEMINI_CANDIDATES` | `1600` | Cap on the expensive stage |
| `GR_GEMINI_POOL_SIZE` | `20` | Concurrent xray processes |
| `GR_GEMINI_API_CONFIRM_LIMIT` | `10` | API calls per run, to stay inside the free quota |
| `GR_CONNECTIVITY_CONCURRENCY` | `100` | Handshakes in flight |
| `GR_HISTORY_RETENTION_DAYS` | `90` | History pruning window |

`GEMINI_API_KEY` is optional. Without it, every candidate still gets the exit
check plus a free reachability probe; with it, the ten best-looking routes per
run get a real `generateContent` call. The split exists because the free tier
allows a few hundred calls a day while a run tests over a thousand candidates
every hour.

## Automation

| Workflow | Trigger | Does |
|---|---|---|
| `ci.yml` | pull request, push to main | ruff, mypy, pytest on Python 3.12 and 3.13 |
| `discovery.yml` | hourly, or manually | Full pipeline, publishes to `gh-pages` |

Everything generated lives on `gh-pages`, never on `main` &mdash; an hourly job
committing to `main` would bury real history within weeks. The SQLite database
rides along on that branch, because the runner is destroyed after every run and
without it the reliability history would reset hourly.

## Honest limits

These are other people's servers, collected automatically. Nothing here is
operated by this project, and a free public proxy can see your traffic &mdash;
use end-to-end encryption for anything you care about.

Verification runs from a GitHub runner in a country Google serves. That proves
the route reaches Gemini; it does not prove the route is reachable *from* your
network, which is the one leg that cannot be tested from CI.

Published for research and for reaching the open internet where it is
restricted. Obey the laws that apply to you.
