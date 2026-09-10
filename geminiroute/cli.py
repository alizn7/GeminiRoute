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

    stats = asyncio.run(run_pipeline(settings))
    typer.echo(
        json.dumps(
            {
                "collected": stats.collected,
                "unique": stats.after_dedup,
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
