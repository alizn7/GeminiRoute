"""Command line interface — a thin adapter over orchestration.runner.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import typer

from geminiroute.config.settings import Settings
from geminiroute.observability.logging import configure_logging
from geminiroute.orchestration.runner import collect_and_parse, run_pipeline
from geminiroute.storage.sqlite_repo import SqliteRepository
from geminiroute.validation.gemini import find_xray_binary
from geminiroute.validation.selfcheck import probe_node, run_checks

app = typer.Typer(add_completion=False, help="GeminiRoute pipeline")


def _settings(sources: Path, output: Path | None, database: Path | None) -> Settings:
    settings = Settings.from_env(sources)
    if output is not None:
        settings.output_dir = output
    if database is not None:
        settings.database_path = database
    configure_logging(settings.log_level)
    return settings


def _require_enabled_sources(settings: Settings, sources: Path) -> None:
    """Fail loudly rather than producing an empty run.

    All-disabled is its own message: it collects nothing and raises nothing,
    so without this it looks like every source simply returned no configs.
    """
    if not settings.sources:
        typer.secho(f"No sources found in {sources}", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    if not any(s.enabled for s in settings.sources):
        typer.secho(
            f"All {len(settings.sources)} sources in {sources} have enabled = false",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)


@app.command("run-full-pipeline")
def run_full_pipeline(
    sources: Path = typer.Option(Path("sources.toml"), help="TOML file listing sources"),
    output: Path = typer.Option(Path("dist"), help="Where to write sub/ and api/"),
    database: Path | None = typer.Option(None, help="SQLite file (overrides env)"),
    limit: int = typer.Option(0, help="Validate only the first N nodes (0 = all)"),
) -> None:
    """Collect, validate, score and publish. What the hourly job runs."""
    settings = _settings(sources, output, database)
    if limit > 0:
        settings.max_nodes = limit
    _require_enabled_sources(settings, sources)

    # Checked up front rather than at the stage that needs it: without this the
    # run spends a minute on collection and connectivity before revealing that
    # nothing could have been verified anyway.
    if find_xray_binary(settings.xray_path) is None:
        typer.secho(
            "xray not found — the Gemini stage will be skipped and this run "
            "will verify nothing. Set XRAY_PATH or put xray on PATH.",
            fg=typer.colors.YELLOW,
        )

    stats = asyncio.run(run_pipeline(settings))
    typer.echo(
        json.dumps(
            {
                "collected": stats.collected,
                "unique": stats.after_dedup,
                "skipped_in_backoff": stats.skipped_in_backoff,
                "pre_passed": stats.after_pre,
                "reachable": stats.after_connectivity,
                "gemini_tested": stats.gemini_tested,
                "gemini_passed": stats.gemini_passed,
                "errors": stats.errors,
            },
            indent=2,
        )
    )
    # Zero publishable nodes is a failure, or the workflow would overwrite a
    # good subscription with an empty one.
    if stats.gemini_passed == 0:
        raise typer.Exit(code=2)


@app.command("collect")
def collect(
    sources: Path = typer.Option(Path("sources.toml")),
) -> None:
    """Collect and parse only, no network validation."""
    settings = _settings(sources, None, None)
    _require_enabled_sources(settings, sources)
    nodes, stats = collect_and_parse(settings)
    typer.echo(
        json.dumps(
            {
                "collected": stats.collected,
                "parsed": stats.parsed,
                "unique": stats.after_dedup,
                "by_protocol": {
                    p: sum(1 for n in nodes if n.protocol.value == p)
                    for p in sorted({n.protocol.value for n in nodes})
                },
                "errors": stats.errors,
            },
            indent=2,
        )
    )


@app.command("errors")
def errors(
    stage: str = typer.Option("gemini", help="pre | connectivity | gemini"),
    database: Path = typer.Option(Path("data/geminiroute.db")),
) -> None:
    """Show why nodes failed a stage, grouped by reason."""
    if not database.exists():
        typer.secho(f"No database at {database}", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    repository = SqliteRepository(database)
    try:
        histogram = repository.error_histogram(stage)
    finally:
        repository.close()

    if not histogram:
        typer.echo(f"No recorded failures for stage {stage!r}.")
        return
    width = max(len(str(count)) for _, count in histogram)
    for reason, count in histogram:
        typer.echo(f"{count:>{width}}  {reason}")


@app.command("sources")
def sources_report(
    database: Path = typer.Option(Path("data/geminiroute.db")),
) -> None:
    """Show what each source actually contributed, worst yield last."""
    if not database.exists():
        typer.secho(f"No database at {database}", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    repository = SqliteRepository(database)
    try:
        rows = repository.source_report()
    finally:
        repository.close()

    if not rows:
        typer.echo("No source statistics recorded yet. Run the pipeline first.")
        return

    typer.echo(f"{'source':<28}{'nodes':>8}{'reachable':>11}{'gemini':>8}{'yield':>8}")
    for name, contributed, valid, ok in rows:
        rate = f"{ok / contributed:.2%}" if contributed else "-"
        typer.echo(f"{name:<28}{contributed:>8}{valid:>11}{ok:>8}{rate:>8}")


@app.command("xray-check")
def xray_check(
    xray: Path | None = typer.Option(None, help="Path to xray (defaults to XRAY_PATH)"),
) -> None:
    """Offer every config shape we generate to the xray binary and report which
    ones it accepts. Answers config-building questions without a pipeline run."""
    settings = Settings.from_env()
    path = str(xray) if xray else find_xray_binary(settings.xray_path)
    if not path:
        typer.secho("xray not found. Set XRAY_PATH or pass --xray.", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    typer.echo(f"Checking {path}")
    allow_insecure, results = asyncio.run(run_checks(path))
    typer.echo(f"allowInsecure supported: {allow_insecure}\n")

    # The explicit allowInsecure pair tests both settings on purpose, so
    # whichever one this binary rejects is an expected result, not a defect.
    expected_failures = {"tls, allowInsecure on", "tls, allowInsecure off"}

    problems = 0
    for result in results:
        expected = result.name in expected_failures
        if result.accepted:
            typer.secho(f"OK    {result.name}", fg=typer.colors.GREEN)
            continue
        if expected:
            typer.secho(f"n/a   {result.name} (not supported by this build)",
                        fg=typer.colors.YELLOW)
            continue
        problems += 1
        typer.secho(f"FAIL  {result.name}", fg=typer.colors.RED)
        typer.echo(f"        {result.reason}")

    typer.echo(f"\n{problems} problem(s)")
    if problems:
        raise typer.Exit(code=1)


@app.command("probe-node")
def probe_node_command(
    config: str = typer.Argument(..., help="A single vless:// / vmess:// / trojan:// config"),
    xray: Path | None = typer.Option(None, help="Path to xray (defaults to XRAY_PATH)"),
    save: Path | None = typer.Option(None, help="Write the fetched page here for inspection"),
) -> None:
    """Run one config through the full check and print what actually came back."""
    settings = Settings.from_env()
    path = str(xray) if xray else find_xray_binary(settings.xray_path)
    if not path:
        typer.secho("xray not found. Set XRAY_PATH or pass --xray.", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    report = asyncio.run(
        probe_node(path, config, settings.gemini_api_key, keep_body=save is not None)
    )

    if report.error:
        typer.secho(f"error: {report.error}", fg=typer.colors.RED)
    typer.echo(f"exit ip        : {report.exit_ip or '-'}")
    typer.echo(f"exit country   : {report.exit_country or '-'}")
    typer.echo(f"web status     : {report.web_status or '-'}")
    typer.echo(f"web size       : {report.web_bytes} bytes")
    typer.secho(
        f"region blocked : {report.region_marker_found}",
        fg=typer.colors.RED if report.region_marker_found else typer.colors.GREEN,
    )
    typer.echo(f"page excerpt   : {report.web_excerpt or '-'}")
    if save is not None and report.web_body:
        save.write_text(report.web_body, encoding="utf-8")
        typer.echo(f"page saved to  : {save}")
    if report.api_status:
        typer.echo(f"api status     : {report.api_status}")
        typer.echo(f"api response   : {report.api_excerpt}")
    if report.error:
        raise typer.Exit(code=1)


@app.command("doctor")
def doctor(
    sources: Path = typer.Option(Path("sources.toml")),
) -> None:
    """Check the environment before blaming the pipeline."""
    settings = Settings.from_env(sources)
    xray = find_xray_binary(settings.xray_path)

    checks = {
        "sources_file": str(sources.resolve()) if sources.exists() else "MISSING",
        "sources_loaded": len(settings.sources),
        "xray_binary": xray or "NOT FOUND (gemini stage will be skipped)",
        "gemini_api_key": "set" if settings.gemini_api_key else "not set (reachability mode)",
        "database_path": str(settings.database_path),
        "output_dir": str(settings.output_dir),
    }
    typer.echo(json.dumps(checks, indent=2))


def main() -> None:
    app()


if __name__ == "__main__":
    main()
