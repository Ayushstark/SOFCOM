from __future__ import annotations

from copy import deepcopy

from backend.pipeline.stage1_intent import _derive_entities_from_prompt
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
        elif issue.code in {"V014", "V015"}:
            # Semantic realignment for creative prompts: inject explicit capabilities
            # so the config reflects requested behavior rather than CRUD fallback.
            creative_entities = {"scenes", "assets", "interactions", "chatbot_sessions", "device_profiles"}
            for entity in sorted(creative_entities):
                if entity not in table_names:
                    fixed.db_schema.append(
                        DBTable(
                            name=entity,
                            columns=[
                                DBColumn(name="id", type=FieldType.string, unique=True),
                                DBColumn(name="created_at", type=FieldType.datetime),
                                DBColumn(name="name", type=FieldType.string, required=False),
                                DBColumn(name="config_json", type=FieldType.text, required=False),
                            ],
                        )
                    )
                    table_names.add(entity)

            capability_pages = {
                "/experience": UIPage(
                    route="/experience",
                    title="Experience",
                    roles=["public"],
                    layout="landing",
                    components=[
                        UIComponent(id="galaxy_scene_3d_visual", type="chart", entity="scenes", fields=["name", "config_json"], endpoint="/api/scenes"),
                        UIComponent(id="floating_assets_animation", type="list", entity="assets", fields=["name", "config_json"], endpoint="/api/assets"),
                    ],
                ),
                "/audio": UIPage(
                    route="/audio",
                    title="Interactive Audio",
                    roles=["public"],
                    layout="landing",
                    components=[
                        UIComponent(id="button_audio_randomizer", type="button", entity="interactions", fields=["name", "config_json"], endpoint="/api/interactions"),
                    ],
                ),
                "/assistant": UIPage(
                    route="/assistant",
                    title="Riddle Gardener Chatbot",
                    roles=["public"],
                    layout="landing",
                    components=[
                        UIComponent(id="gardening_riddle_chatbot", type="form", entity="chatbot_sessions", fields=["name", "config_json"], endpoint="/api/chatbot_sessions"),
                    ],
                ),
                "/devices": UIPage(
                    route="/devices",
                    title="Device Layout Profiles",
                    roles=["public"],
                    layout="landing",
                    components=[
                        UIComponent(id="smart_fridge_layout_profile", type="table", entity="device_profiles", fields=["name", "config_json"], endpoint="/api/device_profiles"),
                    ],
                ),
            }

            existing_routes = {page.route for page in fixed.ui_schema}
            for route, page in capability_pages.items():
                if route not in existing_routes:
                    fixed.ui_schema.append(page)
                    existing_routes.add(route)

            for entity in sorted(["assets", "chatbot_sessions", "device_profiles", "interactions", "scenes"]):
                path = f"/api/{entity}"
                if path not in endpoint_paths:
                    fixed.api_schema.extend(
                        [
                            APIEndpoint(path=path, method="GET", role_access=["public"], request_fields=[], response_entity=entity),
                            APIEndpoint(path=path, method="POST", role_access=["public"], request_fields=["name", "config_json"], response_entity=entity),
                        ]
                    )
                    endpoint_paths.add(path)

            # Keep intent and architecture coherent after repairs.
            for feature in ["chatbot", "3d_visual", "audio", "fridge_layout", "animated_experience"]:
                if feature not in fixed.intent.features:
                    fixed.intent.features.append(feature)
            fixed.intent.features = sorted(set(fixed.intent.features))
            fixed.architecture.product_type = "creative_experience"
            fixed.architecture.assumptions = list(dict.fromkeys([*fixed.architecture.assumptions, "Detected creative prompt; generated interactive experience-oriented architecture."]))
            fixed.architecture.pages = list(dict.fromkeys([*fixed.architecture.pages, "Experience", "Interactive Audio", "Riddle Gardener Chatbot", "Device Layout Profiles"]))
            fixed.architecture.flows = list(
                dict.fromkeys(
                    [
                        *fixed.architecture.flows,
                        "User explores animated galaxy-style homepage with interactive visual assets.",
                        "Button interactions trigger randomized audio effects.",
                        "Chatbot responds in gardening-themed riddles.",
                        "Responsive layouts include desktop and smart-fridge profile support.",
                    ]
                )
            )
        elif issue.code in {"V016", "V017", "V018"}:
            fixed.intent.ambiguity_score = max(fixed.intent.ambiguity_score, 0.85)
            template_questions = [
                "Should this be a website, an app, or both?",
                "What is the exact niche or use-case?",
                "Which pages/features are mandatory for v1 versus optional?",
                "Should authentication and payments be included in v1?",
            ]
            fixed.intent.clarification_questions = list(dict.fromkeys([*fixed.intent.clarification_questions, *template_questions]))
            fixed.intent.assumptions = list(
                dict.fromkeys(
                    [
                        *fixed.intent.assumptions,
                        "Detected unresolved placeholders; kept architecture domain-neutral until clarified.",
                    ]
                )
            )
            fixed.intent.product_type = "template_unspecified"
            fixed.architecture.product_type = "template_unspecified"
            fixed.architecture.assumptions = list(
                dict.fromkeys(
                    [
                        *fixed.architecture.assumptions,
                        "Detected unresolved placeholders; kept architecture domain-neutral until clarified.",
                    ]
                )
            )
        elif issue.code == "V020":
            prompt_entities = _derive_entities_from_prompt(fixed.intent.original_prompt.lower())
            for entity in prompt_entities:
                if entity not in fixed.intent.entities:
                    fixed.intent.entities.append(entity)
                if entity not in fixed.architecture.entities:
                    fixed.architecture.entities.append(entity)
                if entity not in table_names:
                    fixed.db_schema.append(
                        DBTable(
                            name=entity,
                            columns=[
                                DBColumn(name="id", type=FieldType.string, unique=True),
                                DBColumn(name="created_at", type=FieldType.datetime),
                                DBColumn(name="owner_id", type=FieldType.string, references="users.id"),
                                DBColumn(name="name", type=FieldType.string, required=False),
                                DBColumn(name="description", type=FieldType.text, required=False),
                                DBColumn(name="status", type=FieldType.string, required=False),
                            ],
                        )
                    )
                    table_names.add(entity)
                path = f"/api/{entity}"
                if path not in endpoint_paths:
                    fixed.api_schema.extend(
                        [
                            APIEndpoint(path=path, method="GET", role_access=fixed.architecture.roles or ["user"], request_fields=[], response_entity=entity),
                            APIEndpoint(path=path, method="POST", role_access=fixed.architecture.roles or ["user"], request_fields=["name", "description", "status"], response_entity=entity),
                        ]
                    )
                    endpoint_paths.add(path)
                title = entity.replace("_", " ").title()
                if title not in fixed.architecture.pages:
                    fixed.architecture.pages.append(title)
                route = f"/{entity}"
                if route not in {page.route for page in fixed.ui_schema}:
                    fixed.ui_schema.append(
                        UIPage(
                            route=route,
                            title=title,
                            roles=fixed.architecture.roles or ["user"],
                            layout="crud",
                            components=[
                                UIComponent(id=f"{entity}_list", type="list", entity=entity, fields=["name", "status"], endpoint=path),
                                UIComponent(id=f"{entity}_form", type="form", entity=entity, fields=["name", "description", "status"], endpoint=path),
                            ],
                        )
                    )
            fixed.intent.entities = sorted(set(fixed.intent.entities))
            fixed.architecture.entities = sorted(set(fixed.architecture.entities))

    fixed.validation_report = []
    return fixed
