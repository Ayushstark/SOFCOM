from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class FieldType(str, Enum):
    string = "string"
    text = "text"
    number = "number"
    boolean = "boolean"
    datetime = "datetime"
    email = "email"
    money = "money"


class IntentGraph(BaseModel):
    original_prompt: str
    product_type: str
    features: list[str] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list)
    roles: list[str] = Field(default_factory=list)
    business_rules: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    clarification_questions: list[str] = Field(default_factory=list)
    ambiguity_score: float = Field(ge=0, le=1)


class AppArchSpec(BaseModel):
    app_name: str
    product_type: str
    entities: list[str]
    roles: list[str]
    flows: list[str]
    pages: list[str]
    business_rules: list[str]
    assumptions: list[str]


class DBColumn(BaseModel):
    name: str
    type: FieldType
    required: bool = True
    unique: bool = False
    references: str | None = None


class DBTable(BaseModel):
    name: str
    columns: list[DBColumn]

    @field_validator("name")
    @classmethod
    def table_name_is_pluralish(cls, value: str) -> str:
        if not value:
            raise ValueError("table name is required")
        return value.lower().replace(" ", "_")


class APIEndpoint(BaseModel):
    path: str
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"]
    role_access: list[str]
    request_fields: list[str] = Field(default_factory=list)
    response_entity: str | None = None


class UIComponent(BaseModel):
    id: str
    type: Literal["form", "table", "chart", "stat", "nav", "button", "list"]
    entity: str | None = None
    fields: list[str] = Field(default_factory=list)
    endpoint: str | None = None


class UIPage(BaseModel):
    route: str
    title: str
    roles: list[str]
    layout: Literal["dashboard", "crud", "auth", "billing", "analytics", "landing"]
    components: list[UIComponent]


class AuthRule(BaseModel):
    role: str
    permissions: list[str]


class ValidationIssue(BaseModel):
    code: str
    severity: Literal["error", "warning"]
    layer: Literal["schema", "ui", "api", "db", "auth", "logic", "runtime"]
    message: str
    path: str | None = None


class RuntimeResult(BaseModel):
    executable: bool
    routes_checked: list[str]
    generated_files: list[str]
    issues: list[ValidationIssue] = Field(default_factory=list)


class CompilerMetrics(BaseModel):
    latency_ms: float
    validation_passes: int
    repair_passes: int
    issue_count: int
    cost_mode: Literal["deterministic-local", "llm-quality"]


class AppConfig(BaseModel):
    app_id: str
    app_name: str
    intent: IntentGraph
    architecture: AppArchSpec
    ui_schema: list[UIPage]
    api_schema: list[APIEndpoint]
    db_schema: list[DBTable]
    auth_rules: list[AuthRule]
    business_logic: list[str]
    assumptions: list[str]
    validation_report: list[ValidationIssue]
    runtime: RuntimeResult | None = None
    metrics: CompilerMetrics | None = None

    def as_json_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")
