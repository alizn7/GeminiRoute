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


@app.command("run-full-pipeline")
def run_full_pipeline(
    sources: Path = typer.Option(Path("sources.toml"), help="TOML file listing sources"),
    output: Path = typer.Option(Path("dist"), help="Where to write sub/ and api/"),
    database: Path | None = typer.Option(None, help="SQLite file (overrides env)"),
) -> None:
    """Collect, validate, score and publish. What the hourly job runs."""
    settings = _settings(sources, output, database)
    if not settings.sources:
        typer.secho(f"No sources found in {sources}", fg=typer.colors.RED)
        raise typer.Exit(code=1)

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
