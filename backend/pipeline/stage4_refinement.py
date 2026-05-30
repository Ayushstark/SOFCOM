from __future__ import annotations

import hashlib
import time
import asyncio
from typing import Any

from backend.pipeline.stage1_intent import extract_intent
from backend.pipeline.stage2_design import design_system
from backend.pipeline.stage3_schema import generate_api_schema, generate_auth_rules, generate_db_schema, generate_ui_schema
from backend.repair.engine import repair_config
from backend.repair.validators import validate_config
from backend.runtime.simulator import simulate_runtime
from backend.schemas import AppConfig, CompilerMetrics
from backend.llm.client import LLMClient


class CompileLog:
    """Collects structured log entries during a single compilation run."""

    def __init__(self) -> None:
        self._entries: list[dict[str, Any]] = []

    def info(self, stage: str, message: str, details: dict | None = None) -> None:
        entry: dict[str, Any] = {"level": "INFO", "stage": stage, "message": message}
        if details:
            entry["details"] = details
        self._entries.append(entry)

    def warn(self, stage: str, message: str, details: dict | None = None) -> None:
        entry: dict[str, Any] = {"level": "WARN", "stage": stage, "message": message}
        if details:
            entry["details"] = details
        self._entries.append(entry)

    def error(self, stage: str, message: str, details: dict | None = None) -> None:
        entry: dict[str, Any] = {"level": "ERROR", "stage": stage, "message": message}
        if details:
            entry["details"] = details
        self._entries.append(entry)

    def entries(self) -> list[dict[str, Any]]:
        return list(self._entries)


async def compile_prompt(prompt: str) -> tuple[AppConfig, list[dict[str, Any]]]:
    """Run the full compilation pipeline on a SINGLE user prompt.

    Returns (config, log_entries) where log_entries is a list of dicts
    describing every detection, repair, and generation step.
    """
    log = CompileLog()
    started = time.perf_counter()
    llm = LLMClient()
    mode = llm.mode

    # ── Stage 1: Intent Extraction ───────────────────────────────────
    log.info(
        "intent",
        f"Extracting intent from prompt ({len(prompt)} chars)",
        {"mode": mode, "strict_llm": llm.strict_llm, "provider": llm.provider, "model": llm.model},
    )
    try:
        intent = await extract_intent(prompt, llm)
        log.info("intent", f"Extracted product_type={intent.product_type}, ambiguity={intent.ambiguity_score}", {
            "product_type": intent.product_type,
            "features": intent.features,
            "entities": intent.entities,
            "roles": intent.roles,
            "ambiguity_score": intent.ambiguity_score,
        })
        if intent.assumptions:
            log.warn("intent", "Assumptions made for underspecified input", {"assumptions": intent.assumptions})
        if intent.clarification_questions:
            log.warn("intent", "Clarification questions for vague prompt", {"questions": intent.clarification_questions})
    except Exception as exc:
        log.error("intent", f"Intent extraction failed: {exc}")
        raise

    # ── Stage 2: System Design ───────────────────────────────────────
    log.info("design", "Designing system architecture")
    try:
        arch = await design_system(intent, llm)
        log.info("design", f"Architecture: {arch.app_name} with {len(arch.pages)} pages, {len(arch.entities)} entities", {
            "app_name": arch.app_name,
            "pages": arch.pages,
            "flows": arch.flows,
        })
    except Exception as exc:
        log.error("design", f"System design failed: {exc}")
        raise

    app_id = hashlib.sha1(f"{arch.app_name}:{intent.original_prompt}".encode()).hexdigest()[:10]

    # ── Stage 3: Schema Generation (parallel) ────────────────────────
    log.info("schema", "Generating schemas in parallel (UI, API, DB, Auth)")
    try:
        ui_schema, api_schema, db_schema, auth_rules = await asyncio.gather(
            generate_ui_schema(arch, llm),
            generate_api_schema(arch, llm),
            generate_db_schema(arch, llm),
            generate_auth_rules(arch, llm),
        )
        log.info("schema", "Schema generation complete", {
            "ui_pages": len(ui_schema),
            "api_endpoints": len(api_schema),
            "db_tables": len(db_schema),
            "auth_rules": len(auth_rules),
        })
    except Exception as exc:
        log.error("schema", f"Schema generation failed: {exc}")
        raise

    config = AppConfig(
        app_id=app_id,
        app_name=arch.app_name,
        intent=intent,
        architecture=arch,
        ui_schema=ui_schema,
        api_schema=api_schema,
        db_schema=db_schema,
        auth_rules=auth_rules,
        business_logic=arch.business_rules,
        assumptions=arch.assumptions,
        validation_report=[],
    )

    # ── Stage 4: Validation & Repair ─────────────────────────────────
    log.info("validation", "Running validation pass 1")
    validation_passes = 1
    issues = validate_config(config)
    repair_passes = 0

    if issues:
        errors = [i for i in issues if i.severity == "error"]
        warnings = [i for i in issues if i.severity == "warning"]
        log.warn("validation", f"Found {len(errors)} error(s) and {len(warnings)} warning(s)", {
            "errors": [{"code": i.code, "message": i.message, "layer": i.layer} for i in errors],
            "warnings": [{"code": i.code, "message": i.message, "layer": i.layer} for i in warnings],
        })

    while any(issue.severity == "error" for issue in issues) and repair_passes < 3:
        repair_passes += 1
        log.info("repair", f"Automatic repair pass {repair_passes}")

        before_issues = [i for i in issues if i.severity == "error"]
        config = repair_config(config, issues)
        validation_passes += 1
        issues = validate_config(config)
        after_issues = [i for i in issues if i.severity == "error"]

        fixed_codes = {i.code for i in before_issues} - {i.code for i in after_issues}
        remaining_codes = {i.code for i in after_issues}

        if fixed_codes:
            log.info("repair", f"Repaired {len(fixed_codes)} issue(s)", {
                "fixed": sorted(fixed_codes),
                "remaining": sorted(remaining_codes),
            })
        else:
            log.warn("repair", "Repair pass did not resolve any new issues", {
                "remaining": sorted(remaining_codes),
            })

    if not any(issue.severity == "error" for issue in issues):
        log.info("validation", "All validation errors resolved ✓")
    else:
        log.error("validation", f"Unresolved errors after {repair_passes} repair passes", {
            "unresolved": [{"code": i.code, "message": i.message} for i in issues if i.severity == "error"],
        })

    config.validation_report = issues

    # ── Stage 5: Runtime Simulation ──────────────────────────────────
    log.info("runtime", "Simulating runtime execution")
    config.runtime = simulate_runtime(config)
    if config.runtime.executable:
        log.info("runtime", f"Runtime simulation PASSED ✓ – {len(config.runtime.generated_files)} file(s) generated", {
            "routes_checked": config.runtime.routes_checked,
            "generated_files": config.runtime.generated_files,
        })
    else:
        log.error("runtime", "Runtime simulation FAILED – output is not executable", {
            "issues": [{"code": i.code, "message": i.message} for i in config.runtime.issues],
        })

    if config.runtime.issues:
        config.validation_report.extend(config.runtime.issues)

    # ── Metrics ──────────────────────────────────────────────────────
    latency = round((time.perf_counter() - started) * 1000, 2)
    config.metrics = CompilerMetrics(
        latency_ms=latency,
        validation_passes=validation_passes,
        repair_passes=repair_passes,
        issue_count=len(config.validation_report),
        cost_mode="llm-quality" if llm.mode == "gemini" else "deterministic-local",
    )

    log.info("metrics", f"Compilation complete in {latency}ms", {
        "latency_ms": latency,
        "validation_passes": validation_passes,
        "repair_passes": repair_passes,
        "issue_count": len(config.validation_report),
        "cost_mode": config.metrics.cost_mode,
        "success": config.runtime.executable if config.runtime else False,
    })

    return config, log.entries()
