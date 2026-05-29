from __future__ import annotations

from copy import deepcopy

from backend.schemas import APIEndpoint, AppConfig, AuthRule, DBColumn, DBTable, FieldType, UIComponent, UIPage, ValidationIssue


def repair_config(config: AppConfig, issues: list[ValidationIssue]) -> AppConfig:
    fixed = deepcopy(config)
    table_names = {table.name for table in fixed.db_schema}
    role_names = {rule.role for rule in fixed.auth_rules}
    endpoint_paths = {endpoint.path for endpoint in fixed.api_schema}

    for issue in issues:
        if issue.code == "V003" and "users" not in table_names:
            fixed.db_schema.append(
                DBTable(
                    name="users",
                    columns=[
                        DBColumn(name="id", type=FieldType.string, unique=True),
                        DBColumn(name="email", type=FieldType.email, unique=True),
                        DBColumn(name="role", type=FieldType.string),
                    ],
                )
            )
            table_names.add("users")
        elif issue.code in {"V005", "V007"}:
            referenced_roles = set(fixed.architecture.roles)
            referenced_roles.update(role for endpoint in fixed.api_schema for role in endpoint.role_access if role != "public")
            referenced_roles.update(role for page in fixed.ui_schema for role in page.roles if role != "public")
            for role in sorted(referenced_roles):
                if role not in role_names:
                    fixed.auth_rules.append(AuthRule(role=role, permissions=["read:own", "create:own", "update:own"]))
                    role_names.add(role)
        elif issue.code == "V004":
            response_entities = {endpoint.response_entity for endpoint in fixed.api_schema if endpoint.response_entity}
            for entity in sorted(response_entities - table_names):
                fixed.db_schema.append(
                    DBTable(
                        name=entity,
                        columns=[
                            DBColumn(name="id", type=FieldType.string, unique=True),
                            DBColumn(name="created_at", type=FieldType.datetime),
                            DBColumn(name="owner_id", type=FieldType.string, references="users.id"),
                            DBColumn(name="name", type=FieldType.string, required=False),
                            DBColumn(name="status", type=FieldType.string, required=False),
                            DBColumn(name="amount", type=FieldType.money, required=False),
                        ],
                    )
                )
                table_names.add(entity)
        elif issue.code == "V008":
            for page in fixed.ui_schema:
                for component in page.components:
                    if component.endpoint and component.endpoint not in endpoint_paths:
                        fixed.api_schema.append(
                            APIEndpoint(
                                path=component.endpoint,
                                method="GET" if component.type in {"table", "chart", "list"} else "POST",
                                role_access=[role for role in page.roles if role != "public"] or ["user"],
                                request_fields=component.fields if component.type in {"form", "button"} else [],
                                response_entity=component.entity,
                            )
                        )
                        endpoint_paths.add(component.endpoint)
        elif issue.code == "V009":
            for page in fixed.ui_schema:
                for component in page.components:
                    if component.entity and component.entity not in table_names:
                        fixed.db_schema.append(
                            DBTable(
                                name=component.entity,
                                columns=[
                                    DBColumn(name="id", type=FieldType.string, unique=True),
                                    DBColumn(name="name", type=FieldType.string),
                                    DBColumn(name="status", type=FieldType.string, required=False),
                                ],
                            )
                        )
                        table_names.add(component.entity)
        elif issue.code == "V010":
            for table in fixed.db_schema:
                ui_fields = {
                    field
                    for page in fixed.ui_schema
                    for component in page.components
                    if component.entity == table.name
                    for field in component.fields
                }
                existing = {col.name for col in table.columns}
                for field in ui_fields - existing:
                    if field not in {"total_records", "active_users", "plan_id"}:
                        table.columns.append(DBColumn(name=field, type=FieldType.string, required=False))
        elif issue.code == "V011" and "premium_user" not in role_names:
            fixed.auth_rules.append(AuthRule(role="premium_user", permissions=["read:own", "create:own", "update:own", "use:premium"]))
            role_names.add("premium_user")
        elif issue.code == "V012":
            fixed.ui_schema.append(
                UIPage(
                    route="/billing",
                    title="Billing",
                    roles=["user", "premium_user", "admin"],
                    layout="billing",
                    components=[UIComponent(id="plan_checkout", type="button", fields=["plan_id"], endpoint="/api/subscriptions/checkout")],
                )
            )
            if "/api/subscriptions/checkout" not in endpoint_paths:
                fixed.api_schema.append(
                    APIEndpoint(path="/api/subscriptions/checkout", method="POST", role_access=["user"], request_fields=["plan_id"], response_entity="payments")
                )
                endpoint_paths.add("/api/subscriptions/checkout")

    fixed.validation_report = []
    return fixed
