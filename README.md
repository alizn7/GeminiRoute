<div align="center">

<img src="https://raw.githubusercontent.com/alizn7/GeminiRoute/main/docs/banner.svg" alt="GeminiRoute — routes to the Gemini API, proved hourly" width="100%">

[![verified routes](https://img.shields.io/endpoint?url=https://alizn7.github.io/GeminiRoute/api/badge.json)](https://alizn7.github.io/GeminiRoute/sub/best.txt)
[![exit countries](https://img.shields.io/endpoint?url=https://alizn7.github.io/GeminiRoute/api/badge-countries.json)](https://alizn7.github.io/GeminiRoute/)
[![verified of tested](https://img.shields.io/endpoint?url=https://alizn7.github.io/GeminiRoute/api/badge-success.json)](https://alizn7.github.io/GeminiRoute/api/stats.json)
[![hourly rebuild](https://img.shields.io/github/actions/workflow/status/alizn7/GeminiRoute/discovery.yml?style=flat-square&label=hourly%20rebuild&labelColor=1f2d3a)](https://github.com/alizn7/GeminiRoute/actions)

**English**

### Public proxy configs, collected every hour.<br>Kept only if they actually reach the Gemini API.

<a href="https://alizn7.github.io/GeminiRoute/"><b>Live status</b></a> &nbsp;&#183;&nbsp;
<a href="https://alizn7.github.io/GeminiRoute/sub/best.txt"><b>Get a link</b></a> &nbsp;&#183;&nbsp;
<a href="https://alizn7.github.io/GeminiRoute/api/stats.json"><b>Raw numbers</b></a>

</div>

---

## Just give me a link

Copy one of these into your client's subscription field. That is the whole
setup — no account, no signup.

<div align="center">

| | Paste this | What is in it |
|---|---|---|
| 🎯 **Start here** | `https://alizn7.github.io/GeminiRoute/sub/best.txt` | The 30 highest scoring routes |
| ✅ **All verified** | `https://alizn7.github.io/GeminiRoute/sub/gemini.txt` | Everything that passed, best first |
| ⚡ **Low latency** | `https://alizn7.github.io/GeminiRoute/sub/fast.txt` | Verified and under 500 ms |
| 📦 **Everything** | `https://alizn7.github.io/GeminiRoute/sub/all.txt` | Every route tested, verified or not |

</div>

Each file has a `.plain.txt` twin that is not base64 encoded, if you would
rather read it than import it.

### One country only

Swap the two-letter code. These are the countries the last runs actually
produced:

<div align="center">

| | | | | |
|---|---|---|---|---|
| 🇺🇸 `https://alizn7.github.io/GeminiRoute/sub/country/us.txt` | 🇳🇱 `.../nl.txt` | 🇩🇪 `.../de.txt` | 🇫🇷 `.../fr.txt` | 🇵🇱 `.../pl.txt` |
| 🇸🇬 `.../sg.txt` | 🇯🇵 `.../jp.txt` | 🇫🇮 `.../fi.txt` | 🇬🇧 `.../gb.txt` | 🇹🇷 `.../tr.txt` |
| 🇷🇸 `.../rs.txt` | 🇮🇹 `.../it.txt` | 🇪🇪 `.../ee.txt` | 🇧🇬 `.../bg.txt` | 🇨🇦 `.../ca.txt` |

</div>

Which countries have routes changes every hour. The
[status page](https://alizn7.github.io/GeminiRoute/) shows the current list.

---

## What happened to everything else

<div align="center">

<img src="https://alizn7.github.io/GeminiRoute/card.svg" alt="Funnel of the last run" width="100%">

</div>

Most lists publish a count. The number worth publishing is what got thrown
away, and where.

The step that does most of the discarding is the **exit check**: every
candidate is asked, from inside its own tunnel, where it comes out. Geolocating
the config's address instead reports the CDN edge in front of it — which is how
thirty routes once ended up labelled Canada while exiting somewhere Gemini
refuses to serve.

<details>
<summary><b>The rest of the pipeline</b></summary>

<br>

```
collect → parse → normalize → dedup → plausibility → connect
        → exit check → Gemini → publish
```

Cheap filters run first, so the expensive stage sees hundreds of candidates
rather than thousands.

More candidates survive the connectivity check than the expensive stage can
test, so which ones get tested matters. Routes with a verified history go
first; the rest are **shuffled, not sorted by latency**. The fastest responders
are CDN edges in front of dead backends — they answer a handshake in
milliseconds and proxy nothing. Adding a source of low-latency CDN-fronted
configs once halved this pipeline's verification rate while the average
handshake dropped from 209 ms to 85 ms. Shuffling also rotates coverage: the
whole reachable pool gets seen over a few hours instead of the same subset
every hour.

Routes are scored on latency (30%), Gemini verification (30%), reliability over
the last 30 days (25%) and handshake quality (15%). A route with no history
scores 0.5 on reliability — unknown, not bad — so new routes start mid-pack and
earn their position over the next few runs.

A route that fails is not retried immediately. Backoff pushes it out 5 minutes,
then 30, then hours. Three straight failures mark it dead, and a dead route
re-enters the pool once its wait elapses.

Every published config's label is rewritten to `<n>.<flag> GeminiRoute`,
numbered from 1 within each file, carrying the flag of its real exit country.
Only the label changes — credential, host, port, transport and every parameter
are republished exactly as collected.

</details>

---

## Gemini still says my country is unsupported

The Gemini **web app** has a second gate that no proxy can change: the country
of the Google account signed into your browser. A perfectly good route is still
refused if that country is blocked.

> Open `gemini.google.com` in a **private window, signed out**.
> If it works there, the route is fine and the block is on your account.

The same gate applies to getting a `GEMINI_API_KEY` — AI Studio reads the
account's country, not the exit IP.

---

## Machine-readable

| Link | What is in it |
|---|---|
| `https://alizn7.github.io/GeminiRoute/api/stats.json` | The funnel, success rate, countries, per-source yield |
| `https://alizn7.github.io/GeminiRoute/api/nodes.json` | Every tested route with score, latency and country. No credentials. |

---

<details>
<summary><b>Run it yourself</b></summary>

<br>

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

The Gemini stage needs the [Xray](https://github.com/XTLS/Xray-core/releases)
binary on `PATH`, or set `XRAY_PATH`.

| Command | What it does |
|---|---|
| `geminiroute doctor` | Check the environment before blaming the pipeline |
| `geminiroute collect` | Collect and parse only — no network validation |
| `geminiroute run-full-pipeline` | The whole thing. `--limit N` to try a subset |
| `geminiroute errors --stage gemini` | Why routes failed, grouped by reason |
| `geminiroute sources` | What each source actually contributed |
| `geminiroute xray-check` | Which config shapes your xray build accepts |
| `geminiroute probe-node "<config>"` | Run one config through the full check and print what came back |
| `geminiroute try-source "<url>"` | Measure a candidate source against a sample before adding it |

`xray-check` exists because xray versions disagree about what a valid config is
— `allowInsecure` was accepted for years and is refused by recent builds — and
a refused config is recorded as a route failure, indistinguishable from a dead
route.

```bash
ruff check . && mypy geminiroute && pytest
```

</details>

<details>
<summary><b>Add a source</b></summary>

<br>

`sources.toml` is content, not code.

```toml
[[source]]
name = "some-list"
type = "raw"                      # or "github" for a contents-API directory
url = "https://raw.githubusercontent.com/owner/repo/main/sub.txt"
enabled = true
```

Screen it first:

```bash
geminiroute try-source "https://raw.githubusercontent.com/owner/repo/main/sub.txt"
```

The number that matters is **verified over reachable**. Sources kept in this
list sit between 17% and 66%; every one dropped so far sat under 3% while
having *better* TCP reachability than the ones kept. A wall of CDN edges
answers a handshake in milliseconds and proxies nothing.

After a few runs the `sources` block in
[`stats.json`](https://alizn7.github.io/GeminiRoute/api/stats.json) shows the yield each one really produced.
Anything under 2% is costing more than it returns.

</details>

<details>
<summary><b>Configuration</b></summary>

<br>

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

`GEMINI_API_KEY` is optional. Without it every candidate still gets the exit
check and a free reachability probe; with it, the ten best-looking routes per
run get a real `generateContent` call. The split exists because the free tier
allows a few hundred calls a day while a run tests over a thousand candidates
every hour.

Two workflows: `ci.yml` runs ruff, mypy and pytest on every pull request;
`discovery.yml` runs the pipeline hourly and publishes to `gh-pages`. Everything
generated lives on that branch, never on `main` — an hourly job committing to
`main` would bury real history within weeks.

</details>

---

## Honest limits

These are other people's servers, collected automatically. Nothing here is
operated by this project, and a free public proxy can see your traffic — use
end-to-end encryption for anything you care about.

Verification runs from a GitHub runner in a country Google serves. That proves
a route reaches Gemini. It does not prove the route is reachable *from your
network*, which is the one leg that cannot be tested from CI.

Published for research and for reaching the open internet where it is
restricted. Obey the laws that apply to you.
