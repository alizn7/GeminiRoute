<div align="center">

<img src="https://raw.githubusercontent.com/alizn7/GeminiRoute/main/docs/banner.svg" alt="GeminiRoute" width="100%">

[![verified routes](https://img.shields.io/endpoint?url=https://alizn7.github.io/GeminiRoute/api/badge.json)](https://alizn7.github.io/GeminiRoute/sub/best.txt)
[![exit countries](https://img.shields.io/endpoint?url=https://alizn7.github.io/GeminiRoute/api/badge-countries.json)](https://alizn7.github.io/GeminiRoute/)
[![verified of tested](https://img.shields.io/endpoint?url=https://alizn7.github.io/GeminiRoute/api/badge-success.json)](https://alizn7.github.io/GeminiRoute/api/stats.json)
[![rebuilt hourly](https://img.shields.io/github/actions/workflow/status/alizn7/GeminiRoute/discovery.yml?style=flat-square&label=rebuilt%20hourly&labelColor=1f2d3a)](https://github.com/alizn7/GeminiRoute/actions)
[![license](https://img.shields.io/badge/license-MIT-1f2d3a?style=flat-square)](LICENSE)

[English](README.md) &nbsp;·&nbsp; [فارسی](README.fa.md)

### An automated pipeline that discovers, verifies and ranks network routes.<br>Runs hourly on GitHub Actions. Publishes what survives.

![Python 3.12](https://img.shields.io/badge/Python%203.12-3776AB?style=flat-square&logo=python&logoColor=white)
![asyncio](https://img.shields.io/badge/asyncio-1f2d3a?style=flat-square)
![GitHub Actions](https://img.shields.io/badge/GitHub%20Actions-2088FF?style=flat-square&logo=githubactions&logoColor=white)
![GitHub Pages](https://img.shields.io/badge/GitHub%20Pages-222?style=flat-square&logo=github&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-003B57?style=flat-square&logo=sqlite&logoColor=white)
![Xray core](https://img.shields.io/badge/Xray%20core-1f2d3a?style=flat-square)
![Typer](https://img.shields.io/badge/Typer-1f2d3a?style=flat-square)
![httpx](https://img.shields.io/badge/httpx-1f2d3a?style=flat-square)
![Ruff](https://img.shields.io/badge/Ruff-D7FF64?style=flat-square&logo=ruff&logoColor=white)
![Mypy](https://img.shields.io/badge/Mypy-1f2d3a?style=flat-square)
![pytest](https://img.shields.io/badge/pytest-0A9EDC?style=flat-square&logo=pytest&logoColor=white)

[**Use it**](#start) &nbsp;·&nbsp; [**How it works**](#engineering) &nbsp;·&nbsp; [**Live status**](https://alizn7.github.io/GeminiRoute/) &nbsp;·&nbsp; [**Run it yourself**](#dev)

</div>

<a id="start"></a>

## 🚀 Start here

**1.** Copy this link

```
https://alizn7.github.io/GeminiRoute/sub/best.txt
```

**2.** Open your app and go to **Subscriptions** — some call it *Profiles* or *Groups*

**3.** Add a new subscription, paste the link, update, connect

That is the whole setup. No account, no signup. The list rebuilds itself every
hour, so tapping *update* in your app is all the maintenance there is.

### 📱 &nbsp; Which app?

| App | Platform | Where to paste |
|:--|:--|:--|
| [**v2rayN**](https://github.com/2dust/v2rayN) | Windows · macOS · Linux | Subscriptions → Add |
| [**v2rayNG**](https://github.com/2dust/v2rayNG) | Android | Subscription settings → **+** |
| [**NekoBox**](https://github.com/MatsuriDayo/NekoBoxForAndroid) | Android | Groups → **+** → Subscription |
| [**Hiddify**](https://github.com/hiddify/hiddify-next) | Everything | New profile → From URL |
| [**Streisand**](https://apps.apple.com/app/streisand/id6450534064) · [**V2Box**](https://apps.apple.com/app/v2box-v2ray-client/id6446814690) | iOS | Add subscription |
| [**sing-box**](https://github.com/SagerNet/sing-box) | Everything | Any subscription converter |

> [!IMPORTANT]
> **If Gemini says your country is unsupported, the route may be fine.**
>
> The Gemini web app also checks the country of the Google account signed into
> your browser, and no proxy changes that. Open `gemini.google.com` in a
> **private window, signed out**. If it works there, the block is on your
> account rather than the route.

<a id="links"></a>

## 🔗 All the links

<div align="center">

[![best](https://img.shields.io/endpoint?url=https://alizn7.github.io/GeminiRoute/api/badge-sub-best.json)](#best) &nbsp; [![all verified](https://img.shields.io/endpoint?url=https://alizn7.github.io/GeminiRoute/api/badge-sub-gemini.json)](#gemini) &nbsp; [![fast](https://img.shields.io/endpoint?url=https://alizn7.github.io/GeminiRoute/api/badge-sub-fast.json)](#fast) &nbsp; [![everything](https://img.shields.io/endpoint?url=https://alizn7.github.io/GeminiRoute/api/badge-sub-all.json)](#all)

<sub>counts update every hour</sub>

</div>

<a id="best"></a>

### 🎯 &nbsp; Best &nbsp;·&nbsp; start here

The 30 highest scoring routes, re-ranked every hour.

```
https://alizn7.github.io/GeminiRoute/sub/best.txt
```

<a id="gemini"></a>

### ✅ &nbsp; All verified

Every route that passed the check, best first. Use this if `best` runs dry.

```
https://alizn7.github.io/GeminiRoute/sub/gemini.txt
```

<a id="fast"></a>

### ⚡ &nbsp; Fast

Verified *and* under 500 ms. Fewer routes, quicker to connect.

```
https://alizn7.github.io/GeminiRoute/sub/fast.txt
```

<a id="all"></a>

### 📦 &nbsp; Everything

Every route tested, verified or not. For use outside Gemini.

```
https://alizn7.github.io/GeminiRoute/sub/all.txt
```

<sub>Append <code>.plain.txt</code> instead of <code>.txt</code> for a version that is not base64 encoded.</sub>

---

### 🌍 &nbsp; One country only

```
https://alizn7.github.io/GeminiRoute/sub/country/<code>.txt
```

Twenty countries from recent runs, each a subscription of its own. The set
changes hourly — the [status page](https://alizn7.github.io/GeminiRoute/) has the current one.

|   |   |   |   |   |
|:-:|:-:|:-:|:-:|:-:|
| [🇺🇸 `us`](https://alizn7.github.io/GeminiRoute/sub/country/us.txt) | [🇳🇱 `nl`](https://alizn7.github.io/GeminiRoute/sub/country/nl.txt) | [🇩🇪 `de`](https://alizn7.github.io/GeminiRoute/sub/country/de.txt) | [🇫🇷 `fr`](https://alizn7.github.io/GeminiRoute/sub/country/fr.txt) | [🇵🇱 `pl`](https://alizn7.github.io/GeminiRoute/sub/country/pl.txt) |
| [🇫🇮 `fi`](https://alizn7.github.io/GeminiRoute/sub/country/fi.txt) | [🇬🇧 `gb`](https://alizn7.github.io/GeminiRoute/sub/country/gb.txt) | [🇸🇬 `sg`](https://alizn7.github.io/GeminiRoute/sub/country/sg.txt) | [🇮🇹 `it`](https://alizn7.github.io/GeminiRoute/sub/country/it.txt) | [🇭🇰 `hk`](https://alizn7.github.io/GeminiRoute/sub/country/hk.txt) |
| [🇯🇵 `jp`](https://alizn7.github.io/GeminiRoute/sub/country/jp.txt) | [🇨🇦 `ca`](https://alizn7.github.io/GeminiRoute/sub/country/ca.txt) | [🇪🇸 `es`](https://alizn7.github.io/GeminiRoute/sub/country/es.txt) | [🇹🇷 `tr`](https://alizn7.github.io/GeminiRoute/sub/country/tr.txt) | [🇪🇪 `ee`](https://alizn7.github.io/GeminiRoute/sub/country/ee.txt) |
| [🇸🇪 `se`](https://alizn7.github.io/GeminiRoute/sub/country/se.txt) | [🇳🇴 `no`](https://alizn7.github.io/GeminiRoute/sub/country/no.txt) | [🇰🇷 `kr`](https://alizn7.github.io/GeminiRoute/sub/country/kr.txt) | [🇦🇺 `au`](https://alizn7.github.io/GeminiRoute/sub/country/au.txt) | [🇮🇳 `in`](https://alizn7.github.io/GeminiRoute/sub/country/in.txt) |

---

### 📈 &nbsp; Machine-readable

<div align="center">

[![stats.json](https://img.shields.io/badge/api-stats.json-1f2d3a?style=flat-square)](https://alizn7.github.io/GeminiRoute/api/stats.json)
&nbsp;
[![nodes.json](https://img.shields.io/badge/api-nodes.json-1f2d3a?style=flat-square)](https://alizn7.github.io/GeminiRoute/api/nodes.json)

</div>

`stats.json` carries the funnel, the country breakdown and the yield of every
source. `nodes.json` carries every tested route with its score and exit
country, and no credentials.

<a id="engineering"></a>

## 🏗 How it works

<div align="center">

<img src="https://alizn7.github.io/GeminiRoute/card.svg" alt="The funnel of the last run" width="100%">

</div>

Fifteen thousand candidates arrive each hour and a few hundred survive. Most
lists publish the survivors; the interesting number is what was discarded and
where, which is why the funnel above is the first thing on the status page.

```
collect → parse → normalize → dedup → plausibility → connect
        → exit check → Gemini → score → publish
```

Every stage is a package with no knowledge of the ones around it. `core/`
imports nothing outside the standard library, which is what lets the whole
pipeline be exercised without a network or a database.

### The decisions that turned out to matter

Each of these came from a measurement that contradicted the obvious choice.

**Latency ordering selects for dead servers.** With more reachable candidates
than the expensive stage can test, the obvious move is to test the fastest
first. Doing that picks CDN edges sitting in front of dead backends: they
complete a TLS handshake in milliseconds and proxy nothing. Adding one source
of low-latency CDN-fronted configs halved the verification rate while the
average handshake *improved* from 209 ms to 85 ms. Candidates are now ordered
proven-first, then shuffled — which also rotates coverage, so the whole
reachable pool is seen within about six hours instead of the same subset every
hour.

**Ask the tunnel where it comes out, not the config.** Geolocating a config's
address reports the CDN edge in front of it. Thirty routes were once published
labelled Canada while exiting somewhere Gemini refuses to serve. Every
candidate is now asked, through its own tunnel, for its real exit — which
decides both the published flag and whether the route is dropped outright.

**Ask the binary what it accepts.** Xray versions disagree about what a valid
config is; `allowInsecure` was accepted for years and is refused by recent
builds. A refused config is recorded as a route failure, indistinguishable from
a dead route — 139 routes in one run failed for that reason with no way to tell.
The pipeline now probes the binary once per run, and `geminiroute xray-check`
offers all 21 config shapes it generates to the installed binary and reports
which are accepted.

**Never-raise contracts belong at the batch level.** One config carried an SNI
the `idna` codec refuses to encode. The resulting `UnicodeError` is a
`ValueError`, so it slipped past the socket and TLS handlers and ended a run of
10,671 routes at 3,000 in. Enumerating exception types at each call site will
always have a gap; the guarantee is now made once per batch.

**Sources are kept on measured yield, not reputation.** Verified over reachable:
sources kept sit between 17% and 66%, and every one dropped sat under 3% while
having *better* TCP reachability. Three of the rejected lists came from an
upstream ranking that scores sources on TCP reachability — precisely the
property that does not predict a working route. `geminiroute try-source` now
screens a candidate against a sample in about two minutes.

<details>
<summary><b>Scoring, scheduling and output</b></summary>

<br>

Routes are scored on latency (30%), verification (30%), reliability over the
last 30 days (25%) and handshake quality (15%). A route with no history scores
0.5 on reliability — unknown, not bad — so new routes start mid-pack and earn
their position over the next few runs.

A failing route is not retried immediately. Backoff pushes it out 5 minutes,
then 30, then hours, to a daily ceiling. Three straight failures mark it dead,
and a dead route re-enters the pool once its wait elapses. Without this, routes
that failed three runs running would still occupy a slot every hour.

The SQLite database is carried between runs as a compressed asset on the
`db-state` release, because the runner is destroyed after every one; without it
the reliability history would reset hourly and every route would sit at the
unknown score forever. It lives there rather than in git because a binary that
size, rewritten hourly, bloats branch history and eventually trips GitHub's
100 MB file limit — see the
[postmortem](docs/incidents/2026-09-22-database-size-limit.md).

Every published label is rewritten to `<n>.<flag> GeminiRoute`, numbered from 1
within each file, carrying the flag of its real exit country. Only the label
changes — credential, host, port, transport and every parameter are
republished exactly as collected, because re-serialising from parsed fields
would silently drop any parameter the model does not represent.

</details>

<details>
<summary><b>What is in the repository</b></summary>

<br>

| | |
|:--|:--|
| **15 packages** | `core`, `parsing`, `normalization`, `collection`, `dedup`, `validation`, `scoring`, `reliability`, `retry`, `storage`, `generation`, `orchestration`, `observability`, `config` |
| **278 tests** | Unit tests plus integration tests against real local sockets and HTTP servers — no mocking library |
| **Two workflows** | `ci.yml` runs Ruff, Mypy and pytest on Python 3.12 and 3.13 for every pull request; `discovery.yml` runs the pipeline hourly and publishes to GitHub Pages |
| **Eight CLI commands** | Pipeline execution plus diagnostics: `doctor`, `errors`, `sources`, `try-source`, `xray-check`, `probe-node` |
| **Dependencies** | Two at runtime. Collection, parsing, connectivity, geo, scoring, storage and generation are all standard library |
| **Postmortems** | [Incident writeups](docs/incidents/) for failures that reached production |

</details>

<a id="faq"></a>

## ❓ Questions

<details>
<summary><b>My app imported nothing, or says "no servers"</b></summary>

<br>

Check that you pasted the link into a **subscription** field rather than
opening it as a single config. If the app still shows nothing, try the
`.plain.txt` twin — a few older clients do not decode base64 subscriptions.

</details>

<details>
<summary><b>A server connects but nothing loads</b></summary>

<br>

Every route here was verified from a runner in a country Google serves. That
proves the route reaches Gemini; it cannot prove the route is reachable *from
your* network, which is the one leg that cannot be tested from CI. Try another
entry — that is why more than one is published.

</details>

<details>
<summary><b>Is it really free? What is the catch?</b></summary>

<br>

Free, no account, no tracking. None of these servers are run by this project —
they are public configs other people published, collected and tested here. The
catch is inherent to what they are: free public servers are shared,
unpredictable, and can disappear between one hour and the next. That is exactly
why this rebuilds hourly.

</details>

<details>
<summary><b>Can I use these for something other than Gemini?</b></summary>

<br>

Yes — they are ordinary proxy configs. They are only *tested* against Gemini,
so "verified" here means one specific thing, and a route that fails that test
may still be perfectly good for everything else. That is what `sub/all.txt` is
for.

</details>

<a id="dev"></a>

## 🛠 Run it yourself

```bash
git clone https://github.com/alizn7/GeminiRoute.git && cd GeminiRoute
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

ruff check . && mypy geminiroute && pytest
```

The verification stage needs the [Xray](https://github.com/XTLS/Xray-core/releases)
binary on `PATH`, or set `XRAY_PATH`. Everything else runs without it.

| Command | What it does |
|:--|:--|
| `geminiroute doctor` | Check the environment before blaming the pipeline |
| `geminiroute collect` | Collect and parse only — no network validation |
| `geminiroute run-full-pipeline` | The whole thing. `--limit N` to try a subset |
| `geminiroute errors --stage gemini` | Why routes failed, grouped by reason |
| `geminiroute sources` | What each source actually contributed |
| `geminiroute try-source "<url>"` | Measure a candidate source before adding it |
| `geminiroute xray-check` | Which config shapes your xray build accepts |
| `geminiroute probe-node "<config>"` | Run one config through the full check |

<details>
<summary><b>Adding a source</b></summary>

<br>

Screen it before committing to it:

```bash
geminiroute try-source "https://raw.githubusercontent.com/owner/repo/main/sub.txt"
```

The number that matters is **verified over reachable**. Then add it to
`sources.toml`, which is content rather than code:

```toml
[[source]]
name = "some-list"
type = "raw"                      # or "github" for a contents-API directory
url = "https://raw.githubusercontent.com/owner/repo/main/sub.txt"
enabled = true
```

After a few runs the `sources` block in [`stats.json`](https://alizn7.github.io/GeminiRoute/api/stats.json)
shows the yield it really produced.

</details>

<details>
<summary><b>Configuration</b></summary>

<br>

| Variable | Default | Purpose |
|:--|:--|:--|
| `GEMINI_API_KEY` | unset | Upgrades verification from "reached Google" to "the model answered" |
| `XRAY_PATH` | auto-detected | Explicit path to the proxy core |
| `GR_MAX_GEMINI_CANDIDATES` | `1600` | Cap on the expensive stage |
| `GR_GEMINI_POOL_SIZE` | `20` | Concurrent xray processes |
| `GR_GEMINI_API_CONFIRM_LIMIT` | `10` | API calls per run, to stay inside the free quota |
| `GR_CONNECTIVITY_CONCURRENCY` | `100` | Handshakes in flight |
| `GR_HISTORY_RETENTION_DAYS` | `30` | History pruning window, matched to the reliability window |

`GEMINI_API_KEY` is optional. Without it every candidate still gets the exit
check and a free reachability probe; with it, the ten best-looking routes per
run get a real `generateContent` call. The split exists because the free tier
allows a few hundred calls a day while a run tests over a thousand candidates
every hour.

</details>

## ⚠️ Honest limits

These are **other people's servers**, collected automatically. Nothing here is
operated by this project, and a free public proxy can see your traffic — use
end-to-end encryption for anything you care about, and do not sign into
anything you would mind losing.

Verification runs from a GitHub runner in a country Google serves. That proves
a route reaches Gemini. It does not prove the route is reachable from *your*
network, which is the one leg that cannot be tested from CI.

Published for research and for reaching the open internet where it is
restricted. Obey the laws that apply to you.

---

<div align="center">
<sub>MIT licensed · built in the open · <a href="https://alizn7.github.io/GeminiRoute/">live status</a></sub>
</div>
