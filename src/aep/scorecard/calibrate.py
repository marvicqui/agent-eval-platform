"""Judge-vs-human calibration: the platform's own trust check.

The judge grades the golden dataset; the owner grades a sample of the same
answers by hand (evals/calibration/human_labels.jsonl). This module measures
how well the two agree:

- **Spearman correlation** — do judge and human RANK answers the same way?
  Robust to the two using the scale differently.
- **Cohen's kappa (linear weights)** — do they assign the same CATEGORY,
  beyond chance agreement? Harsher and more honest than raw agreement.

The output report names the biggest disagreements, because that list — not
the headline number — is where the judge's blind spots live. A low score is
reported as-is with a diagnosis; a doctored calibration would defeat the
entire point of having one.
"""

from pathlib import Path

from pydantic import BaseModel, ConfigDict

from aep.evaluators.base import Score

CALIBRATION_DIR = Path("evals/calibration")
HUMAN_LABELS_FILE = CALIBRATION_DIR / "human_labels.jsonl"

SCALE = (1, 5)


class HumanLabel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    human_score: int  # 1-5, same scale as the judge rubric
    notes: str | None = None


def load_human_labels(path: Path = HUMAN_LABELS_FILE) -> list[HumanLabel]:
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found. Calibration needs hand-annotated cases: run "
            "`aep calibrate --make-template` and score each case yourself (1-5)."
        )
    labels = [
        HumanLabel.model_validate_json(line)
        for line in path.read_text().splitlines()
        if line.strip()
    ]
    if len(labels) < 10:
        raise ValueError(f"Only {len(labels)} labels; calibration needs at least 10 (target 20).")
    return labels


def judge_overall_to_scale(overall: float) -> int:
    """Map the judge's normalized 0-1 overall back to the 1-5 rubric scale."""
    low, high = SCALE
    return round(low + overall * (high - low))


def _ranks(values: list[float]) -> list[float]:
    """Average ranks with tie handling — the textbook Spearman prerequisite."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        average_rank = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[order[k]] = average_rank
        i = j + 1
    return ranks


def spearman(xs: list[float], ys: list[float]) -> float | None:
    """Pearson correlation of the ranks. Implemented here (30 lines) rather
    than importing scipy for one function — the arithmetic being visible is
    part of the point of a calibration you can defend out loud."""
    if len(xs) < 3:
        return None
    rank_x, rank_y = _ranks(xs), _ranks(ys)
    n = len(xs)
    mean_x, mean_y = sum(rank_x) / n, sum(rank_y) / n
    cov = sum((a - mean_x) * (b - mean_y) for a, b in zip(rank_x, rank_y, strict=True))
    var_x = sum((a - mean_x) ** 2 for a in rank_x)
    var_y = sum((b - mean_y) ** 2 for b in rank_y)
    if var_x == 0 or var_y == 0:
        return None
    return float(cov / (var_x**0.5 * var_y**0.5))


def cohens_kappa_linear(xs: list[int], ys: list[int]) -> float | None:
    """Linearly-weighted Cohen's kappa on the 1-5 scale.

    Linear weights because being off by one rubric level is a small
    disagreement and off by four is a large one; unweighted kappa would
    punish both identically.
    """
    if not xs:
        return None
    low, high = SCALE
    categories = list(range(low, high + 1))
    k = len(categories)
    n = len(xs)

    observed = [[0.0] * k for _ in range(k)]
    for a, b in zip(xs, ys, strict=True):
        observed[a - low][b - low] += 1

    row_totals = [sum(observed[i]) for i in range(k)]
    col_totals = [sum(observed[i][j] for i in range(k)) for j in range(k)]

    weight = [[1 - abs(i - j) / (k - 1) for j in range(k)] for i in range(k)]

    agreement_observed = sum(
        weight[i][j] * observed[i][j] / n for i in range(k) for j in range(k)
    )
    agreement_expected = sum(
        weight[i][j] * (row_totals[i] / n) * (col_totals[j] / n)
        for i in range(k)
        for j in range(k)
    )
    if agreement_expected == 1:
        return None
    return (agreement_observed - agreement_expected) / (1 - agreement_expected)


class CalibrationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    n: int
    spearman: float | None
    kappa_linear: float | None
    disagreements: list[dict[str, object]]  # worst first


def calibrate(labels: list[HumanLabel], judge_scores: list[Score]) -> CalibrationResult:
    judge_by_case = {
        s.case_id: s.value
        for s in judge_scores
        if s.metric == "judge_overall" and s.value is not None
    }
    paired = [
        (label, judge_by_case[label.case_id])
        for label in labels
        if label.case_id in judge_by_case
    ]

    human = [float(label.human_score) for label, _ in paired]
    judge_raw = [overall for _, overall in paired]
    judge_binned = [judge_overall_to_scale(v) for v in judge_raw]

    disagreements = sorted(
        (
            {
                "case_id": label.case_id,
                "human": label.human_score,
                "judge": judge_overall_to_scale(overall),
                "judge_raw": round(overall, 3),
                "delta": abs(label.human_score - judge_overall_to_scale(overall)),
                "notes": label.notes or "",
            }
            for label, overall in paired
        ),
        key=lambda d: -int(d["delta"]),  # type: ignore[call-overload]
    )

    return CalibrationResult(
        n=len(paired),
        spearman=spearman(human, judge_raw),
        kappa_linear=cohens_kappa_linear([int(h) for h in human], judge_binned),
        disagreements=disagreements[:10],
    )


def render_calibration_report(result: CalibrationResult, meta: dict[str, object]) -> str:
    lines = [
        "# Judge calibration report",
        "",
        f"Judge vs {result.n} human-annotated cases "
        f"(dataset `{meta.get('dataset', '?')}`, judge `{meta.get('judge', '?')}`).",
        "",
        f"- **Spearman correlation**: "
        f"{f'{result.spearman:.3f}' if result.spearman is not None else 'n/a'}",
        f"- **Cohen's kappa (linear weights)**: "
        f"{f'{result.kappa_linear:.3f}' if result.kappa_linear is not None else 'n/a'}",
        "",
        "## Largest disagreements",
        "",
        "| case | human | judge (binned) | judge raw | Δ | notes |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for d in result.disagreements:
        lines.append(
            f"| {d['case_id']} | {d['human']} | {d['judge']} | {d['judge_raw']} "
            f"| {d['delta']} | {d['notes']} |"
        )
    lines += [
        "",
        "_Generated by `aep calibrate`. Human labels: evals/calibration/human_labels.jsonl._",
    ]
    return "\n".join(lines) + "\n"
