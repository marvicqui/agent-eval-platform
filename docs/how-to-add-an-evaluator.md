# How to add an evaluator

An evaluator turns `(GoldenCase, CaseRun)` into a list of `Score`s. The
whole contract is `src/aep/evaluators/base.py` — one protocol, one model.

## 1. Decide what kind of check it is

Ask, in this order:

1. **Can code check it?** Then write a deterministic evaluator (no LLM).
   Deterministic checks outrank everything else in this platform — see
   ADR-0003. `trajectory.py` is the template: pure functions first, a thin
   protocol adapter after.
2. **Is it a statistical property of RAG?** Wrap the metric in
   `evaluators/rag.py` — that module is the only file allowed to import
   ragas.
3. **Does it need judgment?** Extend the judge with a new rubric YAML in
   `evaluators/rubrics/` rather than writing a new judge. New failure modes
   of judgment need a mitigation *and a metric proving the mitigation works*
   (see `docs/judge-failure-modes.md`) before they are trusted.

## 2. Implement the protocol

```python
from aep.dataset.schema import GoldenCase
from aep.evaluators.base import Score
from aep.runner.executor import CaseRun


class MyEvaluator:
    name = "my_evaluator"

    async def evaluate(self, case: GoldenCase, run: CaseRun) -> list[Score]:
        if run.result is None:          # SUT failed; nothing to evaluate
            return []
        value = ...                     # compute from case + run.result
        return [Score(case_id=case.id, metric="my_metric", value=value)]
```

Rules that keep the platform honest — these are enforced by review, and
they are the difference between a metric and a decoration:

- **Errors are missing data, not zeros.** If your evaluator fails, return
  `Score(..., value=None, detail="why")`. The aggregator excludes `None`
  from means and reports an error count instead.
- **Never read `case.expected` inside a SUT**, and never leak it into the
  SUT's inputs. Evaluators see ground truth; systems under test do not.
- **Docstring says why, not what.** Every module explains the reasoning an
  interviewer would ask about.

## 3. Wire it in

1. Add it to `evaluate_all()` in `src/aep/evaluate.py`, with the condition
   that decides which cases it applies to (look at how judge/rag/trajectory
   gate themselves).
2. Export it from `src/aep/evaluators/__init__.py`.

## 4. Test it without LLM calls

Deterministic logic gets direct unit tests (`tests/test_trajectory.py` is
the model). LLM-dependent evaluators get tested with scripted fake clients
(`tests/test_bias_mitigation.py` shows the pattern: program a client with a
known defect and prove your machinery catches it).

## 5. Threshold it deliberately

Run the full dataset (`aep run`), look at the real distribution, then add
the metric to `evals/thresholds.yaml` with a comment recording the observed
mean/min/max and why the floor is where it is. Update `docs/metrics.md`.
A threshold nobody can defend in review is worse than no threshold.
