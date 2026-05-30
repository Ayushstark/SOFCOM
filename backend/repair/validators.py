from __future__ import annotations

import re
from typing import Literal

from backend.pipeline.stage1_intent import _derive_entities_from_prompt
from backend.schemas import AppConfig, ValidationIssue


def _issue(code: str, layer: Literal["schema", "ui", "api", "db", "auth", "logic", "runtime"], message: str, path: str | None = None, severity: Literal["error", "warning"] = "error") -> ValidationIssue:
    return ValidationIssue(code=code, layer=layer, message=message, path=path, severity=severity)


def validate_config(config: AppConfig) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    table_names = {table.name for table in config.db_schema}
    roles = {rule.role for rule in config.auth_rules}
    endpoints = {endpoint.path for endpoint in config.api_schema}
    prompt_text = config.intent.original_prompt.lower()

    if not config.ui_schema:
        issues.append(_issue("V001", "ui", "At least one UI page is required.", "ui_schema"))
    if not config.api_schema:
        issues.append(_issue("V002", "api", "At least one API endpoint is required.", "api_schema"))
    if "users" not in table_names:
        issues.append(_issue("V003", "db", "A users table is required for auth-aware apps.", "db_schema"))

    for endpoint in config.api_schema:
        if endpoint.response_entity and endpoint.response_entity not in table_names:
            issues.append(_issue("V004", "api", f"Endpoint {endpoint.path} returns missing DB entity {endpoint.response_entity}.", "api_schema"))
        for role in endpoint.role_access:
            if role != "public" and role not in roles:
                issues.append(_issue("V005", "auth", f"Endpoint {endpoint.path} references unknown role {role}.", "api_schema"))
        if endpoint.response_entity in table_names:
            columns = {col.name for table in config.db_schema if table.name == endpoint.response_entity for col in table.columns}
            for field in endpoint.request_fields:
                if field not in columns and field != "plan_id":
                    issues.append(_issue("V006", "api", f"Request field {field} is not present on {endpoint.response_entity}.", "api_schema"))

    for page in config.ui_schema:
        for role in page.roles:
            if role != "public" and role not in roles:
                issues.append(_issue("V007", "ui", f"Page {page.route} references unknown role {role}.", "ui_schema"))
        for component in page.components:
            if component.endpoint and component.endpoint not in endpoints:
                issues.append(_issue("V008", "ui", f"Component {component.id} points to missing endpoint {component.endpoint}.", "ui_schema"))
            if component.entity:
                if component.entity not in table_names:
                    issues.append(_issue("V009", "ui", f"Component {component.id} uses missing entity {component.entity}.", "ui_schema"))
                    continue
                columns = {col.name for table in config.db_schema if table.name == component.entity for col in table.columns}
                for field in component.fields:
                    if field not in columns and field not in {"total_records", "active_users", "plan_id"}:
                        issues.append(_issue("V010", "ui", f"UI field {field} is not present on {component.entity}.", "ui_schema"))

    if any("Premium" in rule or "premium" in rule for rule in config.business_logic):
        if "premium_user" not in roles:
            issues.append(_issue("V011", "logic", "Premium business logic exists without premium_user role.", "business_logic"))
        if "/billing" not in {page.route for page in config.ui_schema}:
            issues.append(_issue("V012", "logic", "Premium app needs a billing page.", "ui_schema"))

    if config.intent.ambiguity_score > 0.65 and not config.intent.clarification_questions:
        issues.append(_issue("V013", "logic", "Highly ambiguous prompt should include clarification questions or assumptions.", "intent", "warning"))

    # Semantic prompt-to-output alignment checks for creative or non-CRUD prompts.
    required_capabilities: list[tuple[str, str]] = []
    if any(term in prompt_text for term in ["chatbot", "assistant"]):
        required_capabilities.append(("chatbot", "Prompt requests a chatbot but no chatbot capability is present."))
    if any(term in prompt_text for term in ["3d", "three-dimensional", "spinning", "rotate"]):
        required_capabilities.append(("3d_visual", "Prompt requests a 3D visual but no 3D/visual capability is present."))
    if any(term in prompt_text for term in ["sound", "audio", "meow", "rocket"]):
        required_capabilities.append(("audio", "Prompt requests interactive audio behavior but no audio capability is present."))
    if any(term in prompt_text for term in ["smart fridge", "fridge"]):
        required_capabilities.append(("fridge_layout", "Prompt requests smart-fridge support but no kiosk/fridge layout capability is present."))
    if any(term in prompt_text for term in ["game", "exploration", "galaxy", "floating", "animation"]):
        required_capabilities.append(("animated_experience", "Prompt requests an animated/interactive experience but no matching capability is present."))

    if required_capabilities:
        coverage_text = " ".join(
            [
                config.app_name,
                config.architecture.product_type,
                " ".join(config.architecture.pages),
                " ".join(config.architecture.flows),
                " ".join(config.intent.features),
                " ".join(config.intent.entities),
                " ".join(component.id + " " + component.type + " " + " ".join(component.fields) for page in config.ui_schema for component in page.components),
                " ".join(endpoint.path for endpoint in config.api_schema),
                " ".join(table.name for table in config.db_schema),
            ]
        ).lower()

        missing = [tag for tag, _ in required_capabilities if tag not in coverage_text]
        if missing:
            issues.append(
                _issue(
                    "V014",
                    "logic",
                    f"Output is semantically misaligned with prompt; missing capabilities: {', '.join(sorted(missing))}.",
                    "intent",
                )
            )

    # Guardrail against obvious domain fallback for highly creative prompts.
    creative_prompt = any(term in prompt_text for term in ["galaxy", "croissant", "plant", "riddle", "meow", "rocket"])
    business_template_selected = config.architecture.product_type in {"ecommerce", "crm", "lms", "booking", "project"}
    if creative_prompt and business_template_selected:
        issues.append(
            _issue(
                "V015",
                "logic",
                "Creative prompt appears to be forced into a business CRUD template.",
                "architecture.product_type",
            )
        )

    has_placeholders = bool(re.search(r"\[[^\]]+\]", config.intent.original_prompt))
    if has_placeholders:
        if config.intent.ambiguity_score < 0.7:
            issues.append(
                _issue(
                    "V016",
                    "logic",
                    "Prompt contains unresolved placeholders but ambiguity score is too low.",
                    "intent.ambiguity_score",
                )
            )
        if not config.intent.clarification_questions:
            issues.append(
                _issue(
                    "V017",
                    "logic",
                    "Prompt contains unresolved placeholders but clarification questions are missing.",
                    "intent.clarification_questions",
                )
            )
        if config.architecture.product_type in {"crm", "ecommerce", "booking", "lms", "project"}:
            issues.append(
                _issue(
                    "V018",
                    "logic",
                    "Template prompt was incorrectly locked to a specific business domain.",
                    "architecture.product_type",
                )
            )

    prompt_entities = set(_derive_entities_from_prompt(prompt_text))
    missing_prompt_entities = sorted(entity for entity in prompt_entities if entity not in table_names)
    if missing_prompt_entities:
        issues.append(
            _issue(
                "V020",
                "logic",
                f"Prompt-mentioned resources are missing from generated schema: {', '.join(missing_prompt_entities)}.",
                "intent.entities",
            )
        )

    return issues
