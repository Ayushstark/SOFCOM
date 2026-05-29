from __future__ import annotations

from typing import Literal

from backend.schemas import AppConfig, ValidationIssue


def _issue(code: str, layer: Literal["schema", "ui", "api", "db", "auth", "logic", "runtime"], message: str, path: str | None = None, severity: Literal["error", "warning"] = "error") -> ValidationIssue:
    return ValidationIssue(code=code, layer=layer, message=message, path=path, severity=severity)


def validate_config(config: AppConfig) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    table_names = {table.name for table in config.db_schema}
    roles = {rule.role for rule in config.auth_rules}
    endpoints = {endpoint.path for endpoint in config.api_schema}

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

    return issues
