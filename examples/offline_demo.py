"""Show the hard gate without credentials, model calls, or executed tools.

A reviewer needs a reproducible way to inspect the safety invariant before
configuring cloud services. Synthetic tool lists make the allowed/forbidden
contrast explicit; these are fixtures, not recorded agent behavior or model
quality measurements. The normal RAG threshold configuration is not used.
"""

import asyncio

from aep.dataset.loader import load_dataset
from aep.evaluators.trajectory import TrajectoryEvaluator
from aep.runner.executor import CaseRun
from aep.runner.types import SUTResult
from aep.scorecard.aggregate import aggregate_scores
from aep.scorecard.thresholds import evaluate_gate


async def main() -> None:
    case = load_dataset("agent_tasks")[0]
    evaluator = TrajectoryEvaluator()
    print("SYNTHETIC trajectory demo: no tools executed; no model quality measured.")
    print("Gate scope: forbidden-tool hard rule only, no RAG thresholds or baseline.")
    scenarios = [
        ("allowed", ["retrieve"], True),
        ("forbidden", ["retrieve", "delete_resource"], False),
    ]
    for name, calls, expected_pass in scenarios:
        run = CaseRun(
            case_id=case.id,
            result=SUTResult(answer="Synthetic fixture; not graded.", tool_calls=calls),
        )
        aggregates = aggregate_scores(await evaluator.evaluate(case, run))
        gate = evaluate_gate(aggregates, rules={})
        print(f"{name}: {'PASS' if gate.passed else 'FAIL (expected)'}; tools={calls}")
        for failure in gate.failures:
            print(f"  {failure.metric}: {failure.reason}")
        if gate.passed != expected_pass:
            raise SystemExit(f"Unexpected gate result for {name}")
    print("Demo verified: a reported forbidden call overrides all other scores.")


if __name__ == "__main__":
    asyncio.run(main())
