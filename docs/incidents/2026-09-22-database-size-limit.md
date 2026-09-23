# Incident: publishing blocked by the 100 MB file limit

**Date:** 2026-09-22 to 2026-09-23
**Impact:** No subscription update published for ~29 hours.
**Severity:** Medium — stale data served, no data lost.

---

## Summary

The hourly Discovery workflow began failing at its push step. The SQLite
database it carries between runs had grown to 100.71 MB, over GitHub's 100 MB
per-file limit, so every push to `gh-pages` was rejected by the pre-receive
hook. Subscriptions stopped updating and kept serving the 2026-09-22T00:19Z
snapshot until the fix shipped.

No data was lost: the rejected push left `gh-pages` untouched, and each run
restored the last successfully published database before failing again.

---

## Timeline

| Time (UTC) | Event |
|---|---|
| 2026-09-10 | First rows in `validation_history`. |
| 2026-09-22 00:19 | Last successful publish. |
| 2026-09-22 08:23 | First rejected push: `File data/geminiroute.db is 100.71 MB`. |
| 2026-09-22 → 09-23 | Every subsequent hourly run failed identically. |
| 2026-09-23 | Diagnosis, fix, and first successful publish after the fix. |

---

## Root causes

Three decisions, each defensible alone, combined into a limit that was going
to be hit eventually.

### 1. Retention was set longer than the data could ever fit

`history_retention_days` was 90. The project was 12 days old, so
`prune_history` had never deleted a single row. At roughly 40,000 rows per
day, a full 90-day window would have been ~3.6 million rows — far beyond what
a 100 MB file could hold. The failure was not a surprise event; it was
scheduled from the moment the default was chosen.

### 2. 59% of history rows were written and never read

`validation_history` recorded the outcome of every stage for every node. Only
three queries read that table, and between them they want two things:

| Query | Reads |
|---|---|
| `reliability()` | gemini stage only |
| `successful_fingerprints()` | gemini stage, passes only |
| `error_histogram()` | failures only |

Passes outside the gemini stage matched none of them:

```
pre / passed=1            234,839
connectivity / passed=1    92,936
                          -------
                          327,775 rows = 59% of the table
```

These rows recorded "this config was not malformed" and "this port was open" —
facts nothing downstream consulted.

### 3. A mutable binary was versioned in git

The database was committed to `gh-pages` on every run. Git stores binary blobs
whole rather than as deltas, so each hourly run added a full copy to branch
history. Beyond the per-file limit, this inflated the branch to ~167 MB of
history that served no purpose: nobody needs last week's snapshot of internal
pipeline state.

---

## Detection

The failure itself was loud — the workflow went red every hour — but nothing
had reported the *trend* that produced it. Diagnosis was done by measuring a
copy of the production database rather than by inspecting code and guessing:

| Step | What it ruled in or out |
|---|---|
| Fetched the `.db` from `gh-pages` into a scratch copy | Investigate without touching production |
| `PRAGMA freelist_count` → 0 | No reclaimable space: `VACUUM` alone would not help |
| Row counts grouped by stage and outcome | Surfaced the 234,839 `pre`/passed rows as suspicious |
| `grep` for every reader of `validation_history` | Confirmed those rows had no consumer |
| Row counts grouped by day | Data started 2026-09-10 → pruning had never run |

The fourth step mattered most. Row counts alone would have suggested "shorten
retention". Reading the consumers showed a larger share of the data should
never have been written at all.

---

## Resolution

| Change | Why |
|---|---|
| `record_results` skips rows no query reads | Removes 59% of writes with no loss of function |
| `prune_history` uses two windows: 30 days for gemini rows, 3 days for diagnostic rows | Reliability needs the long window; the error histogram only needs recent runs |
| `VACUUM` after a prune that deleted rows | `DELETE` frees pages inside the file but never shrinks it |
| `close()` checkpoints WAL | WAL parks recent writes in a side file nothing downstream copied |
| Database moved from `gh-pages` to a gzipped asset on the `db-state` release | 2 GB limit instead of 100 MB, and no hourly binary commit |
| `gh-pages` history squashed to a single root commit | Drops ~167 MB of historical database blobs |

Applied to the existing database: 554,025 rows → 102,621; 99.5 MB → 33 MB
(8.6 MB gzipped).

### A near-miss worth recording

The first plan set retention to 14 days. `reliability()` defaults to a 30-day
window, so that would have silently truncated the reliability score — no
error, no warning, just quietly wrong numbers feeding into node ranking. The
retention window and the query window are now both 30 days, with a comment in
`settings.py` tying them together.

---

## What prevents a recurrence

- The workflow logs `ls -lh` of the database (raw and gzipped) on every run, so
  growth is visible long before any limit is near.
- Retention is bounded and actually exercised, rather than set past the age of
  the project.
- `prune_history` reclaims space rather than only marking it free.
- The storage location's ceiling (2 GB) is two orders of magnitude above
  current usage.

---

## Lessons

**A retention setting longer than the data's lifetime is untested code.** Any
policy that has never fired is an assumption, not a safeguard.

**Write what something reads.** The cheapest fix here was not compression or a
bigger limit — it was noticing that most of the data had no consumer.

**Git is for code, not for mutable binary state.** Git's refusal to forget is
the right default for source and the wrong one for a file rewritten hourly
where only the latest version matters.

**The limit was not the problem; the absence of a trend signal was.** One
`ls -lh` line would have surfaced this ten days earlier.

---

## Responsibility separation after the fix

| Location | Holds |
|---|---|
| `main` | Source code and documentation |
| `gh-pages` | Public output: subscriptions, dashboard, API JSON |
| `db-state` release | Internal pipeline state |