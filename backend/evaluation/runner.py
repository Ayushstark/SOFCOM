from __future__ import annotations

from statistics import mean

from backend.evaluation.dataset import DATASET
from backend.pipeline.stage4_refinement import compile_prompt


async def run_evaluation() -> dict:
    """Run all 20 dataset prompts and return aggregate metrics.

    This is ONLY called by the /evaluate endpoint – it is never
    triggered automatically when a user submits a single prompt.
    """
    rows = []
    for item in DATASET:
        config, log_entries = await compile_prompt(item["prompt"])
        errors = [issue for issue in config.validation_report if issue.severity == "error"]
        rows.append(
            {
                "kind": item["kind"],
                "prompt": item["prompt"],
                "success": not errors and bool(config.runtime and config.runtime.executable),
                "error_count": len(errors),
                "warning_count": len(config.validation_report) - len(errors),
                "repair_passes": config.metrics.repair_passes if config.metrics else 0,
                "latency_ms": config.metrics.latency_ms if config.metrics else 0,
                "app_id": config.app_id,
                "failure_type": (
                    "validation_error" if errors
                    else "runtime_failure" if not (config.runtime and config.runtime.executable)
                    else None
                ),
            }
        )

    success_count = sum(1 for row in rows if row["success"])
    avg_retries = round(mean(row["repair_passes"] for row in rows), 2) if rows else 0
    avg_latency = round(mean(row["latency_ms"] for row in rows), 2) if rows else 0
    return {
        "total": len(rows),
        "success_count": success_count,
        "success_rate": round(success_count / len(rows), 3) if rows else 0,
        "average_latency_ms": avg_latency,
        "average_repair_passes": avg_retries,
        "retries_per_request": avg_retries,
        "failure_types": {
            "validation_error": sum(1 for row in rows if row["failure_type"] == "validation_error"),
            "runtime_failure": sum(1 for row in rows if row["failure_type"] == "runtime_failure"),
        },
        "cost_vs_quality": {
            "cost_mode": "deterministic-local",
            "quality_proxy_success_rate": round(success_count / len(rows), 3) if rows else 0,
            "quality_proxy_runtime_pass_rate": round(sum(1 for row in rows if row["failure_type"] != "runtime_failure") / len(rows), 3) if rows else 0,
            "latency_tradeoff_ms": avg_latency,
        },
        "rows": rows,
    }


if __name__ == "__main__":
    import json
    import asyncio
    from pathlib import Path
    from dotenv import load_dotenv

    ROOT = Path(__file__).resolve().parents[2]
    load_dotenv(ROOT / ".env")

    print(json.dumps(asyncio.run(run_evaluation()), indent=2))
