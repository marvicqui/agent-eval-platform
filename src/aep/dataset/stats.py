"""Dataset coverage report.

Why: "30 cases" means nothing if 28 are basic networking questions. The
coverage table (cases per category x difficulty) is a first-class artifact —
it goes in the README and it is how a reviewer sees dataset skew at a glance.
"""

from collections import Counter

from rich.console import Console
from rich.table import Table

from aep.dataset.schema import GoldenCase

DIFFICULTIES = ["basic", "intermediate", "advanced"]


def coverage(cases: list[GoldenCase]) -> dict[str, Counter[str]]:
    """Map category -> Counter of difficulty -> case count."""
    result: dict[str, Counter[str]] = {}
    for case in cases:
        result.setdefault(case.category, Counter())[case.difficulty] += 1
    return result


def print_coverage(name: str, cases: list[GoldenCase]) -> None:
    table = Table(title=f"Dataset '{name}' — {len(cases)} cases")
    table.add_column("category")
    for difficulty in DIFFICULTIES:
        table.add_column(difficulty, justify="right")
    table.add_column("total", justify="right", style="bold")

    for category, counts in sorted(coverage(cases).items()):
        table.add_row(
            category,
            *(str(counts.get(d, 0)) for d in DIFFICULTIES),
            str(sum(counts.values())),
        )
    Console().print(table)
