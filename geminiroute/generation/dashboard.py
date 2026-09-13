"""The published status page.

The page's subject is a measurement, so the funnel leads: seven thousand
candidates in, a few hundred proven. Every other project of this kind publishes
a count; the interesting number here is how much was discarded and where.

No web fonts and no external assets by design. The people reading this are on
networks where `fonts.googleapis.com` may not resolve, and a status page that
half-loads is worse than a plain one.
"""

from __future__ import annotations

import html
import json
from typing import Any

from geminiroute.generation.branding import flag_emoji

STYLE = """
:root {
  --ground: #0e1a24;
  --panel:  #15242f;
  --rule:   #22384a;
  --ink:    #dce8f0;
  --muted:  #7793a8;
  --signal: #e8a33d;
  --pass:   #5bc08c;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  padding: 3rem 1.25rem 5rem;
  background: var(--ground);
  color: var(--ink);
  font: 400 16px/1.6 ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto,
        "Helvetica Neue", Arial, sans-serif;
  font-variant-numeric: tabular-nums;
}
main { max-width: 58rem; margin: 0 auto; }

.masthead {
  display: flex; flex-wrap: wrap; align-items: baseline;
  justify-content: space-between; gap: .75rem;
  padding-bottom: 1.25rem; border-bottom: 1px solid var(--rule);
}
.masthead h1 {
  margin: 0; font-size: 1.5rem; font-weight: 600; letter-spacing: -0.01em;
}
.masthead p { margin: 0; color: var(--muted); font-size: .875rem; }

.lede {
  margin: 2.5rem 0 2rem; max-width: 34rem;
  font-size: 1.0625rem; color: var(--muted);
}
.lede b { color: var(--ink); font-weight: 600; }

section { margin-top: 3.25rem; }
section h2 {
  margin: 0 0 1.25rem; font-size: .9375rem; font-weight: 600;
  color: var(--muted);
}

/* The funnel: one row per stage, bar width proportional to survivors. */
.funnel { display: grid; gap: .5rem; }
.stage {
  display: grid; grid-template-columns: 11rem 1fr auto;
  align-items: center; gap: 1rem;
}
.stage span:first-child { color: var(--muted); font-size: .875rem; }
.track { height: 1.75rem; background: var(--panel); border-radius: 2px; }
.fill { height: 100%; background: var(--rule); border-radius: 2px; }
.stage:last-child .fill { background: var(--pass); }
.stage:last-child span:last-child { color: var(--pass); font-weight: 600; }
.count { font-size: .9375rem; min-width: 4rem; text-align: right; }

.links { display: grid; gap: .5rem; }
.link {
  display: grid; grid-template-columns: 6.5rem 1fr auto auto;
  align-items: center; gap: 1rem;
  padding: .875rem 1rem; background: var(--panel);
  border: 1px solid var(--rule); border-radius: 3px;
}
.link .name { font-weight: 600; }
.link .what { color: var(--muted); font-size: .875rem; }
.link .n { color: var(--muted); font-size: .875rem; }
.link button {
  font: inherit; font-size: .8125rem; padding: .3rem .75rem; cursor: pointer;
  color: var(--ground); background: var(--signal);
  border: 0; border-radius: 3px;
}
.link button:focus-visible { outline: 2px solid var(--ink); outline-offset: 2px; }
.link button[data-copied] { background: var(--pass); }

.exits { display: grid; gap: .375rem; }
.exit { display: grid; grid-template-columns: 3.5rem 1fr auto; gap: 1rem;
        align-items: center; }
.exit .place { color: var(--muted); font-size: .875rem; }
.exit .bar { height: .625rem; background: var(--signal); border-radius: 2px;
             min-width: 2px; opacity: .85; }
.exit .n { font-size: .875rem; color: var(--muted); }

table { width: 100%; border-collapse: collapse; font-size: .9375rem; }
th, td { padding: .625rem .5rem; border-bottom: 1px solid var(--rule);
         text-align: right; }
th:first-child, td:first-child { text-align: left; }
th { color: var(--muted); font-weight: 400; font-size: .8125rem; }

.note { color: var(--muted); font-size: .9375rem; max-width: 36rem; }
.note code { color: var(--ink); background: var(--panel);
             padding: .1rem .35rem; border-radius: 2px; font-size: .875em; }
a { color: var(--signal); }
footer { margin-top: 4rem; padding-top: 1.25rem; border-top: 1px solid var(--rule);
         color: var(--muted); font-size: .8125rem; }

@media (max-width: 34rem) {
  .stage { grid-template-columns: 1fr auto; }
  .stage .track { display: none; }
  .link { grid-template-columns: 1fr auto; }
  .link .what, .link .n { grid-column: 1 / -1; }
}
@media (prefers-reduced-motion: no-preference) {
  .link button { transition: background-color .15s; }
}
"""

SCRIPT = """
for (const button of document.querySelectorAll('[data-file]')) {
  button.addEventListener('click', async () => {
    const base = location.href.replace(/index\\.html$/, '').replace(/\\/?$/, '/');
    try {
      await navigator.clipboard.writeText(base + button.dataset.file);
      button.dataset.copied = '1';
      button.textContent = 'Copied';
      setTimeout(() => { delete button.dataset.copied;
                         button.textContent = 'Copy'; }, 1600);
    } catch { button.textContent = 'Press ctrl+C'; }
  });
}
"""

# Order matters: this is the funnel, and each stage is a subset of the one above.
FUNNEL_LABELS = [
    ("collected", "collected"),
    ("after_dedup", "unique"),
    ("after_pre_validation", "plausible"),
    ("after_connectivity", "reachable"),
    ("after_gemini", "verified"),
]

SUBSCRIPTIONS = [
    ("best", "sub/best.txt", "the highest scoring, capped at 30"),
    ("gemini", "sub/gemini.txt", "everything that passed verification"),
    ("fast", "sub/fast.txt", "verified and under 500 ms"),
    ("all", "sub/all.txt", "every route tested, verified or not"),
]

MAX_COUNTRIES = 12


def _escape(value: object) -> str:
    return html.escape(str(value), quote=True)


def _funnel(funnel: dict[str, Any]) -> str:
    top = max((int(v) for v in funnel.values() if isinstance(v, int)), default=0) or 1
    rows = []
    for key, label in FUNNEL_LABELS:
        value = funnel.get(key)
        if not isinstance(value, int):
            continue
        width = max(round(value / top * 100, 2), 0.4)
        rows.append(
            f'      <div class="stage"><span>{label}</span>'
            f'<span class="track"><span class="fill" style="width:{width}%"></span></span>'
            f'<span class="count">{value:,}</span></div>'
        )
    return "\n".join(rows)


def _subscriptions(files: dict[str, int]) -> str:
    rows = []
    for name, path, what in SUBSCRIPTIONS:
        count = files.get(name)
        label = f"{count:,} routes" if isinstance(count, int) else ""
        rows.append(
            f'      <div class="link"><span class="name">{name}</span>'
            f'<span class="what">{what}</span>'
            f'<span class="n">{label}</span>'
            f'<button type="button" data-file="{path}">Copy</button></div>'
        )
    return "\n".join(rows)


def _exits(countries: dict[str, int]) -> str:
    if not countries:
        return '      <p class="note">No verified routes in the last run.</p>'
    top = max(countries.values()) or 1
    rows = []
    for code, count in list(countries.items())[:MAX_COUNTRIES]:
        width = max(round(count / top * 100, 2), 1.0)
        flag = flag_emoji(code if len(code) == 2 else None)
        rows.append(
            f'      <div class="exit"><span class="place">{flag} {_escape(code)}</span>'
            f'<span class="bar" style="width:{width}%"></span>'
            f'<span class="n">{count}</span></div>'
        )
    return "\n".join(rows)


def _sources(sources: list[Any]) -> str:
    rows = []
    for entry in sources:
        if not isinstance(entry, dict):
            continue
        share = entry.get("yield")
        share_text = "" if share is None else format(float(share), ".1%")
        rows.append(
            f"      <tr><td>{_escape(entry.get('name', ''))}</td>"
            f"<td>{int(entry.get('contributed', 0)):,}</td>"
            f"<td>{int(entry.get('reachable', 0)):,}</td>"
            f"<td>{int(entry.get('gemini_ok', 0)):,}</td>"
            f"<td>{share_text}</td></tr>"
        )
    if not rows:
        return ""
    body = "\n".join(rows)
    return f"""  <section>
    <h2>Where they came from</h2>
    <table>
      <tr><th>source</th><th>collected</th><th>reachable</th><th>verified</th>
          <th>yield</th></tr>
{body}
    </table>
  </section>
"""


def render(stats: dict[str, Any], files: dict[str, int] | None = None) -> str:
    """Build the status page from one run's statistics."""
    funnel = stats.get("funnel", {})
    funnel = funnel if isinstance(funnel, dict) else {}
    countries = stats.get("nodes_by_country", {})
    countries = countries if isinstance(countries, dict) else {}
    sources = stats.get("sources", [])
    sources = sources if isinstance(sources, list) else []

    verified = funnel.get("after_gemini", 0)
    collected = funnel.get("collected", 0)
    latency = stats.get("average_latency_ms")
    latency_text = f"{latency:.0f} ms median handshake" if latency else "latency unmeasured"
    generated = _escape(stats.get("generated_at", ""))

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>GeminiRoute</title>
<meta name="description" content="Routes to the Gemini API, measured hourly.">
<style>{STYLE}</style>
</head>
<body>
<main>
  <div class="masthead">
    <h1>GeminiRoute</h1>
    <p>scheduled hourly &middot; last run {generated}</p>
  </div>

  <p class="lede">Every hour this collects public proxy configs, asks each one
  from inside its own tunnel where it comes out, and keeps only the ones that
  reach the Gemini API from a country Google serves. Last run:
  <b>{verified:,} of {collected:,}</b> survived.</p>

  <section>
    <h2>What happened to the {collected:,} collected</h2>
    <div class="funnel">
{_funnel(funnel)}
    </div>
  </section>

  <section>
    <h2>Get a link</h2>
    <div class="links">
{_subscriptions(files or {})}
    </div>
    <p class="note" style="margin-top:1rem">Paste one into a client's
    subscription field. Every file has a <code>.plain.txt</code> twin that is
    not base64 encoded, if you want to read it.</p>
  </section>

  <section>
    <h2>Where the verified routes come out</h2>
    <div class="exits">
{_exits(countries)}
    </div>
  </section>

{_sources(sources)}
  <section>
    <h2>If Gemini still says your country is unsupported</h2>
    <p class="note">The Gemini web app has a second gate: the country of the
    Google account signed into your browser, which a proxy does not change. A
    working route can still be refused for that reason alone. Open
    <code>gemini.google.com</code> in a private window, signed out, to tell the
    two apart.</p>
  </section>

  <footer>{latency_text} &middot; <a href="api/stats.json">stats.json</a>
  &middot; <a href="api/nodes.json">nodes.json</a></footer>
</main>
<script>{SCRIPT}</script>
</body>
</html>
"""


def render_json(stats: dict[str, Any]) -> str:
    return json.dumps(stats, ensure_ascii=False, indent=2)
