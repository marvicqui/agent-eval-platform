"""Command-line entry point for the platform.

Why a CLI at all: the platform must be drivable from CI and from other
repos without writing Python. `aep run`, `aep calibrate` and `aep report`
are the only three verbs CI needs. Commands are stubs until their phase
lands; each raises with a clear message instead of pretending to work.
"""

import typer

app = typer.Typer(no_args_is_help=True, help="agent-eval-platform CLI")


@app.command()
def run() -> None:
    """Run the golden dataset against a system under test. (Phase 2)"""
    raise typer.Exit(code=_not_implemented("run", phase=2))


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
