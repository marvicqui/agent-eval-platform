"""Command-line entry point for the platform.

Why a CLI at all: the platform must be drivable from CI and from other
repos without writing Python. The verbs:

- `aep run`       execute a dataset against a SUT and evaluate the results
- `aep report`    render the scorecard, apply the gate (exit 1 on fail)
- `aep calibrate` judge-vs-human correlation report
- `aep dataset stats`  dataset coverage table

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
from typing import Any

import typer
from rich import print as rprint

from aep.config import get_settings
from aep.dataset.loader import DatasetError, load_dataset
from aep.dataset.stats import print_coverage
from aep.evaluators.base import Score
from aep.instrumentation import flush, init_tracing
from aep.runner.executor import run_dataset
from aep.runner.types import SystemUnderTest
from aep.scorecard.aggregate import aggregate_scores, derived_bias_metrics
from aep.scorecard.calibrate import (
    CALIBRATION_DIR,
    load_human_labels,
    render_calibration_report,
)
from aep.scorecard.calibrate import (
    calibrate as run_calibration,
)
from aep.scorecard.report import load_baseline, render_markdown, write_baseline
from aep.scorecard.thresholds import evaluate_gate, load_thresholds

app = typer.Typer(no_args_is_help=True, help="agent-eval-platform CLI")
dataset_app = typer.Typer(no_args_is_help=True, help="Golden dataset utilities")
app.add_typer(dataset_app, name="dataset")

DEFAULT_RUN_FILE = Path("evals/runs/latest.json")


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


def _load_run_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        rprint(f"[red]Run file {path} not found — run `aep run` first.[/red]")
        raise typer.Exit(code=2)
    data: dict[str, Any] = json.loads(path.read_text())
    return data


@app.command()
def run(
    dataset: str = typer.Option(..., help="Dataset name under datasets/golden/ (no .jsonl)"),
    sut: str = typer.Option(..., help="Python module exposing build_sut()"),
    output: Path = typer.Option(DEFAULT_RUN_FILE, help="Where to write results"),
    evaluate: bool = typer.Option(True, help="Run evaluators after the SUT runs"),
) -> None:
    """Run the golden dataset against a system under test, then evaluate it."""
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
    sut_seconds = time.perf_counter() - started

    scores: list[Score] = []
    if evaluate:
        from aep.evaluate import evaluate_all  # heavy import chain (ragas)

        rprint("Evaluating (trajectory + judge + RAG)...")
        scores = asyncio.run(evaluate_all(settings, cases, runs))
    wall_seconds = time.perf_counter() - started
    flush()

    succeeded = sum(1 for r in runs if r.succeeded)
    total_cost = sum(r.cost_usd for r in runs)
    payload = {
        "dataset": dataset,
        "sut": system.name,
        "judge": settings.judge_deployment,
        "cases": len(runs),
        "succeeded": succeeded,
        "sut_seconds": round(sut_seconds, 2),
        "wall_seconds": round(wall_seconds, 2),
        "total_cost_usd": round(total_cost, 6),
        "runs": [r.model_dump() for r in runs],
        "scores": [s.model_dump() for s in scores],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2))

    rprint(
        f"[green]{succeeded}/{len(runs)} cases succeeded[/green] in {wall_seconds:.1f}s "
        f"({sut_seconds:.1f}s SUT), SUT cost [bold]${total_cost:.4f}[/bold], "
        f"{len(scores)} scores → {output}"
    )
    for r in runs:
        if not r.succeeded:
            rprint(f"[red]  FAIL {r.case_id}: {r.error}[/red]")
    if succeeded < len(runs):
        raise typer.Exit(code=1)


@app.command()
def report(
    run_file: Path = typer.Option(DEFAULT_RUN_FILE, help="Run artifact from `aep run`"),
    output: Path | None = typer.Option(None, help="Also write the markdown here"),
    update_baseline: bool = typer.Option(
        False, help="Commit this run's means as the new regression baseline"
    ),
) -> None:
    """Render the scorecard and apply the gate. Exit code 1 when the gate fails."""
    data = _load_run_file(run_file)
    scores = [Score.model_validate(s) for s in data.get("scores", [])]
    if not scores:
        rprint("[red]Run file has no scores — re-run `aep run` with evaluation on.[/red]")
        raise typer.Exit(code=2)

    aggregates = aggregate_scores(scores)
    derived = derived_bias_metrics(scores)
    rules = load_thresholds()
    baseline = load_baseline()
    gate = evaluate_gate(aggregates, rules, baseline or None)

    markdown = render_markdown(aggregates, derived, rules, baseline, gate, data)
    print(markdown)
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(markdown)

    if update_baseline:
        meta = {
            "dataset": data.get("dataset"),
            "sut": data.get("sut"),
            "judge": data.get("judge"),
            "cases": data.get("cases"),
            "total_cost_usd": data.get("total_cost_usd"),
        }
        write_baseline(aggregates, derived, meta)
        rprint("[yellow]Baseline updated — commit evals/baseline.json deliberately.[/yellow]")

    if not gate.passed:
        raise typer.Exit(code=1)


@app.command()
def calibrate(
    run_file: Path = typer.Option(DEFAULT_RUN_FILE, help="Run artifact with judge scores"),
    make_template: bool = typer.Option(
        False, help="Generate the annotation sheet + labels template instead of calibrating"
    ),
    sample: int = typer.Option(20, help="Cases to include in the template"),
) -> None:
    """Correlate judge scores with the owner's hand annotations."""
    data = _load_run_file(run_file)

    if make_template:
        _write_annotation_template(data, sample)
        return

    scores = [Score.model_validate(s) for s in data.get("scores", [])]
    try:
        labels = load_human_labels()
    except (FileNotFoundError, ValueError) as exc:
        rprint(f"[red]{exc}[/red]")
        raise typer.Exit(code=2) from exc

    result = run_calibration(labels, scores)
    report_markdown = render_calibration_report(result, data)
    report_path = CALIBRATION_DIR / "report.md"
    report_path.write_text(report_markdown)
    print(report_markdown)
    rprint(f"[green]Calibration report written to {report_path}[/green]")


def _write_annotation_template(data: dict[str, Any], sample: int) -> None:
    """Annotation sheet for the owner: question, answer, required points.

    The human labels must come from a human — this only lays the table.
    """
    dataset = load_dataset(str(data["dataset"]))
    cases_by_id = {case.id: case for case in dataset}
    answered = [r for r in data["runs"] if r.get("result")][:sample]

    sheet_lines = [
        "# Calibration annotation sheet",
        "",
        "Score each answer 1-5 for OVERALL quality (accuracy + completeness +",
        "actionability), judging coverage of the required points — not length.",
        "Record your scores in `human_labels.jsonl` (template alongside this",
        "file; rename `human_labels.template.jsonl`, fill `human_score`).",
        "",
    ]
    template_lines = []
    for run_raw in answered:
        case = cases_by_id[run_raw["case_id"]]
        sheet_lines += [
            f"## {case.id}",
            "",
            f"**Q:** {case.input}",
            "",
            "**Required points:**",
            *[f"- {p}" for p in case.expected.required_points],
            "",
            f"**Answer:** {run_raw['result']['answer']}",
            "",
            "---",
            "",
        ]
        template_lines.append(
            json.dumps({"case_id": case.id, "human_score": 0, "notes": ""})
        )

    CALIBRATION_DIR.mkdir(parents=True, exist_ok=True)
    (CALIBRATION_DIR / "annotation_sheet.md").write_text("\n".join(sheet_lines))
    (CALIBRATION_DIR / "human_labels.template.jsonl").write_text(
        "\n".join(template_lines) + "\n"
    )
    rprint(
        f"[green]Wrote annotation sheet + template for {len(answered)} cases to "
        f"{CALIBRATION_DIR}/.[/green] Fill in human_score (1-5), save as "
        "human_labels.jsonl, then run `aep calibrate`."
    )


@dataset_app.command("stats")
def dataset_stats(name: str = typer.Argument(..., help="Dataset name")) -> None:
    """Print the coverage table (cases per category and difficulty)."""
    try:
        cases = load_dataset(name)
    except DatasetError as exc:
        rprint(f"[red]{exc}[/red]")
        raise typer.Exit(code=2) from exc
    print_coverage(name, cases)
