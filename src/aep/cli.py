"""Command-line entry point for the platform.

Why a CLI at all: the platform must be drivable from CI and from other
repos without writing Python. `aep run`, `aep calibrate` and `aep report`
are the only verbs CI needs; `aep dataset stats` exists because dataset
coverage is a reviewable artifact, not trivia.

SUT loading convention: `--sut some.module` imports that module and calls
its `build_sut()` factory. A convention beats a plugin system here — five
known projects, zero need for discovery machinery.
"""

import asyncio
import importlib
import json
import sys
import time
from pathlib import Path

import typer
from rich import print as rprint

from aep.config import get_settings
from aep.dataset.loader import DatasetError, load_dataset
from aep.dataset.stats import print_coverage
from aep.instrumentation import flush, init_tracing
from aep.runner.executor import run_dataset
from aep.runner.types import SystemUnderTest

app = typer.Typer(no_args_is_help=True, help="agent-eval-platform CLI")
dataset_app = typer.Typer(no_args_is_help=True, help="Golden dataset utilities")
app.add_typer(dataset_app, name="dataset")


def _load_sut(module_path: str) -> SystemUnderTest:
    # The CLI runs as an installed entry point, so the working directory is
    # not on sys.path the way `python -m` would put it. SUT modules live in
    # the *caller's* repo (e.g. examples/ here, or a downstream project), so
    # the working directory is exactly where they should be resolved from.
    if "" not in sys.path and str(Path.cwd()) not in sys.path:
        sys.path.insert(0, str(Path.cwd()))
    try:
        module = importlib.import_module(module_path)
    except ModuleNotFoundError as exc:
        rprint(f"[red]Cannot import SUT module '{module_path}': {exc}[/red]")
        raise typer.Exit(code=2) from exc
    if not hasattr(module, "build_sut"):
        rprint(f"[red]SUT module '{module_path}' has no build_sut() factory.[/red]")
        raise typer.Exit(code=2)
    sut: SystemUnderTest = module.build_sut()
    return sut


@app.command()
def run(
    dataset: str = typer.Option(..., help="Dataset name under datasets/golden/ (no .jsonl)"),
    sut: str = typer.Option(..., help="Python module exposing build_sut()"),
    output: Path = typer.Option(Path("evals/runs/latest.json"), help="Where to write results"),
) -> None:
    """Run the golden dataset against a system under test."""
    settings = get_settings()
    init_tracing(settings)
    try:
        cases = load_dataset(dataset)
    except DatasetError as exc:
        rprint(f"[red]{exc}[/red]")
        raise typer.Exit(code=2) from exc

    system = _load_sut(sut)
    rprint(
        f"Running [bold]{len(cases)}[/bold] cases from '{dataset}' against "
        f"'{system.name}' (concurrency {settings.max_concurrency})..."
    )
    started = time.perf_counter()
    runs = asyncio.run(run_dataset(system, cases, settings.max_concurrency))
    wall_seconds = time.perf_counter() - started
    flush()

    succeeded = sum(1 for r in runs if r.succeeded)
    total_cost = sum(r.cost_usd for r in runs)
    payload = {
        "dataset": dataset,
        "sut": system.name,
        "cases": len(runs),
        "succeeded": succeeded,
        "wall_seconds": round(wall_seconds, 2),
        "total_cost_usd": round(total_cost, 6),
        "runs": [r.model_dump() for r in runs],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2))

    rprint(
        f"[green]{succeeded}/{len(runs)} cases succeeded[/green] in {wall_seconds:.1f}s, "
        f"total cost [bold]${total_cost:.4f}[/bold] → {output}"
    )
    for r in runs:
        if not r.succeeded:
            rprint(f"[red]  FAIL {r.case_id}: {r.error}[/red]")
    if succeeded < len(runs):
        raise typer.Exit(code=1)


@dataset_app.command("stats")
def dataset_stats(name: str = typer.Argument(..., help="Dataset name")) -> None:
    """Print the coverage table (cases per category and difficulty)."""
    try:
        cases = load_dataset(name)
    except DatasetError as exc:
        rprint(f"[red]{exc}[/red]")
        raise typer.Exit(code=2) from exc
    print_coverage(name, cases)


@app.command()
def calibrate() -> None:
    """Correlate judge scores with human annotations. (Phase 4)"""
    raise typer.Exit(code=_not_implemented("calibrate", phase=4))


@app.command()
def report() -> None:
    """Render the markdown scorecard. (Phase 4)"""
    raise typer.Exit(code=_not_implemented("report", phase=4))


def _not_implemented(name: str, phase: int) -> int:
    typer.echo(f"'aep {name}' lands in phase {phase} — not implemented yet.", err=True)
    return 2
