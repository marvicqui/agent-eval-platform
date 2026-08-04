"""Load and validate golden datasets from JSONL.

Why fail loudly with line numbers: datasets are edited by hand in PRs. The
loader is the reviewer's safety net — a malformed line, a duplicate id or an
unknown field must stop the run with an error a human can act on, because a
dataset that half-loads produces metrics that look real and are not.
"""

import json
from pathlib import Path

from pydantic import ValidationError

from aep.dataset.schema import GoldenCase

GOLDEN_DIR = Path("datasets/golden")


class DatasetError(Exception):
    """Raised when a dataset file is malformed. Message is actionable."""


def load_dataset(name: str, golden_dir: Path = GOLDEN_DIR) -> list[GoldenCase]:
    """Load `datasets/golden/<name>.jsonl`, validating every line.

    Collects *all* errors before raising so one fix-run cycle surfaces every
    problem, not just the first.
    """
    path = golden_dir / f"{name}.jsonl"
    if not path.exists():
        available = sorted(p.stem for p in golden_dir.glob("*.jsonl"))
        raise DatasetError(f"No dataset '{name}' in {golden_dir}. Available: {available}")

    cases: list[GoldenCase] = []
    errors: list[str] = []
    seen_ids: dict[str, int] = {}

    for line_no, raw_line in enumerate(path.read_text().splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        try:
            case = GoldenCase.model_validate(json.loads(line))
        except json.JSONDecodeError as exc:
            errors.append(f"{path}:{line_no}: invalid JSON — {exc}")
            continue
        except ValidationError as exc:
            errors.append(f"{path}:{line_no}: schema violation — {exc}")
            continue

        if case.id in seen_ids:
            errors.append(
                f"{path}:{line_no}: duplicate id '{case.id}' (first seen line {seen_ids[case.id]})"
            )
            continue
        seen_ids[case.id] = line_no
        cases.append(case)

    if errors:
        raise DatasetError(f"{len(errors)} problem(s) in dataset '{name}':\n" + "\n".join(errors))
    if not cases:
        raise DatasetError(f"Dataset '{name}' is empty.")
    return cases
