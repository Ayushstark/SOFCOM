from __future__ import annotations

from backend.schemas import APIEndpoint, AppArchSpec, AuthRule, DBColumn, DBTable, FieldType, UIComponent, UIPage
from backend.llm.client import LLMClient


def _entity_fields(entity: str) -> list[DBColumn]:
    base = [
        DBColumn(name="id", type=FieldType.string, required=True, unique=True),
        DBColumn(name="created_at", type=FieldType.datetime),
        DBColumn(name="owner_id", type=FieldType.string, references="users.id"),
    ]
    if entity == "users":
        return [
            DBColumn(name="id", type=FieldType.string, required=True, unique=True),
            DBColumn(name="email", type=FieldType.email, required=True, unique=True),
            DBColumn(name="role", type=FieldType.string, required=True),
            DBColumn(name="subscription_status", type=FieldType.string, required=False),
        ]
    if entity in {"payments", "orders"}:
        return base + [DBColumn(name="amount", type=FieldType.money), DBColumn(name="status", type=FieldType.string)]
    if entity == "work_samples":
        return base + [
            DBColumn(name="title", type=FieldType.string),
            DBColumn(name="category", type=FieldType.string, required=False),
            DBColumn(name="image_url", type=FieldType.string, required=False),
            DBColumn(name="description", type=FieldType.text, required=False),
        ]
    if entity == "testimonials":
        return base + [
            DBColumn(name="client_name", type=FieldType.string),
            DBColumn(name="quote", type=FieldType.text),
            DBColumn(name="role", type=FieldType.string, required=False),
        ]
    if entity == "contact_messages":
        return base + [
            DBColumn(name="name", type=FieldType.string),
            DBColumn(name="email", type=FieldType.email),
            DBColumn(name="message", type=FieldType.text),
        ]
    if entity == "events":
        return base + [
            DBColumn(name="title", type=FieldType.string),
            DBColumn(name="venue_id", type=FieldType.string, references="venues.id"),
            DBColumn(name="starts_at", type=FieldType.datetime),
            DBColumn(name="description", type=FieldType.text, required=False),
            DBColumn(name="status", type=FieldType.string),
        ]
    if entity == "venues":
        return base + [
            DBColumn(name="name", type=FieldType.string),
            DBColumn(name="address", type=FieldType.text, required=False),
            DBColumn(name="seat_map", type=FieldType.text, required=False),
        ]
    if entity == "seats":
        return base + [
            DBColumn(name="venue_id", type=FieldType.string, references="venues.id"),
            DBColumn(name="section", type=FieldType.string),
            DBColumn(name="row", type=FieldType.string),
            DBColumn(name="number", type=FieldType.string),
            DBColumn(name="status", type=FieldType.string),
        ]
    if entity == "tickets":
        return base + [
            DBColumn(name="event_id", type=FieldType.string, references="events.id"),
            DBColumn(name="seat_id", type=FieldType.string, references="seats.id"),
            DBColumn(name="order_id", type=FieldType.string, references="orders.id"),
            DBColumn(name="price", type=FieldType.money),
            DBColumn(name="status", type=FieldType.string),
        ]
    if entity in {"analytics", "reports"}:
        return base + [DBColumn(name="metric_name", type=FieldType.string), DBColumn(name="value", type=FieldType.number)]
    return base + [
        DBColumn(name="name", type=FieldType.string),
        DBColumn(name="description", type=FieldType.text, required=False),
        DBColumn(name="status", type=FieldType.string, required=False),
    ]


async def generate_db_schema(arch: AppArchSpec, llm: LLMClient) -> list[DBTable]:
    if llm.is_configured() and arch.product_type not in {"portfolio_site", "website"}:
        sys_prompt = f"""You are a Database Architect. Generate the database schema for: {arch.app_name}.
Entities to include: {['users', *arch.entities]}
For each table, provide the name and columns.
JSON Schema: list of objects with 'name' (string) and 'columns' (list of objects with 'name', 'type' (string/number/boolean/datetime/email/money/text), 'required' (bool), 'unique' (bool), 'references' (string, optional)).

Always include an 'id' string column for every table.
Use fields that match the entity and prompt, not generic name/status only when better domain fields are obvious.
"""
        try:
            data = await llm.generate_json(sys_prompt, temperature=0.1)
            return [DBTable(**table) for table in data]
        except Exception:
            if llm.strict_llm or not llm.allow_fallback:
                raise
            pass

    entities = sorted(set(["users", *arch.entities]))
    return [DBTable(name=entity, columns=_entity_fields(entity)) for entity in entities]


async def generate_api_schema(arch: AppArchSpec, llm: LLMClient) -> list[APIEndpoint]:
    if llm.is_configured() and arch.product_type not in {"portfolio_site", "website"}:
        sys_prompt = f"""You are an API Architect. Generate the API schema for: {arch.app_name}.
Entities: {arch.entities}
Roles: {arch.roles}
Pages: {arch.pages}
JSON Schema: list of objects with 'path', 'method' (GET/POST/PUT/PATCH/DELETE), 'role_access' (list of roles allowed), 'request_fields' (list of strings), 'response_entity' (string).

Include CRUD endpoints for all entities and /auth/login.
Endpoints must match the generated entities and workflow from the prompt.
"""
        try:
            data = await llm.generate_json(sys_prompt, temperature=0.1)
            return [APIEndpoint(**ep) for ep in data]
        except Exception:
            if llm.strict_llm or not llm.allow_fallback:
                raise
            pass

    endpoints = []
    if "Login" in arch.pages or any(role != "public" for role in arch.roles):
        endpoints.append(APIEndpoint(path="/auth/login", method="POST", role_access=["public"], request_fields=["email"], response_entity="users"))
    for entity in sorted(set(arch.entities)):
        fields = [col.name for col in _entity_fields(entity) if col.name not in {"id", "created_at", "owner_id"}]
        endpoints.extend(
            [
                APIEndpoint(path=f"/api/{entity}", method="GET", role_access=arch.roles, response_entity=entity),
                APIEndpoint(path=f"/api/{entity}", method="POST", role_access=arch.roles, request_fields=fields, response_entity=entity),
            ]
        )
    if "Billing" in arch.pages:
        endpoints.append(APIEndpoint(path="/api/subscriptions/checkout", method="POST", role_access=["user"], request_fields=["plan_id"], response_entity="payments"))
    return endpoints


async def generate_ui_schema(arch: AppArchSpec, llm: LLMClient) -> list[UIPage]:
    if llm.is_configured() and arch.product_type not in {"portfolio_site", "website"}:
        sys_prompt = f"""You are a Frontend Architect. Generate the UI schema for: {arch.app_name}.
Pages needed: {arch.pages}
Roles: {arch.roles}
Entities: {arch.entities}
JSON Schema: list of objects with 'route', 'title', 'roles' (list), 'layout' (dashboard/crud/auth/billing/analytics), and 'components' (list of objects with 'id', 'type' (form/table/chart/stat/nav/button), 'entity' (optional), 'fields' (list), 'endpoint' (optional)).
Use prompt-specific pages and components, not generic dashboard/CRUD pages unless requested.
"""
        try:
            data = await llm.generate_json(sys_prompt, temperature=0.1)
            return [UIPage(**page) for page in data]
        except Exception:
            if llm.strict_llm or not llm.allow_fallback:
                raise
            pass

    pages = []
    if "Login" in arch.pages:
        pages.append(
            UIPage(
                route="/login",
                title="Login",
                roles=["public"],
                layout="auth",
                components=[UIComponent(id="login_form", type="form", entity="users", fields=["email"], endpoint="/auth/login")],
            )
        )
    if "Home" in arch.pages:
        primary = next((entity for entity in arch.entities if entity != "users"), None)
        primary_fields = [col.name for col in _entity_fields(primary) if col.name not in {"id", "created_at", "owner_id"}][:4] if primary else ["total_records"]
        pages.append(
            UIPage(
                route="/",
                title="Home",
                roles=["public"],
                layout="landing",
                components=[
                    UIComponent(id="hero_overview", type="stat", entity=primary, fields=primary_fields, endpoint=f"/api/{primary}" if primary else None),
                    UIComponent(id="featured_items", type="list", entity=primary, fields=primary_fields, endpoint=f"/api/{primary}" if primary else None),
                ],
            )
        )
    if "Dashboard" in arch.pages:
        pages.append(
            UIPage(
                route="/dashboard",
                title="Dashboard",
                roles=arch.roles,
                layout="dashboard",
                components=[
                    UIComponent(id="summary_stats", type="stat", fields=["total_records", "active_users"]),
                    UIComponent(id="main_nav", type="nav"),
                ],
            )
        )

    existing_routes = {page.route for page in pages}
    page_entity_lookup = {entity.replace("_", " ").title(): entity for entity in arch.entities}
    page_entity_lookup.update(
        {
            "Work": "work_samples" if "work_samples" in arch.entities else None,
            "Work Samples": "work_samples" if "work_samples" in arch.entities else None,
            "Portfolio": "projects" if "projects" in arch.entities else ("work_samples" if "work_samples" in arch.entities else None),
            "Testimonials": "testimonials" if "testimonials" in arch.entities else None,
            "Contact": "contact_messages" if "contact_messages" in arch.entities else None,
            "About": None,
        }
    )
    page_entity_lookup["Account"] = "users"
    page_entity_lookup["Checkout"] = "orders" if "orders" in arch.entities else ("payments" if "payments" in arch.entities else None)
    page_entity_lookup["Seat Selection"] = "seats" if "seats" in arch.entities else None

    for page_name in arch.pages:
        if page_name in {"Home", "Login", "Dashboard"}:
            continue
        entity = page_entity_lookup.get(page_name)
        route = "/" + page_name.lower().replace(" ", "-")
        if page_name in {"Checkout", "Billing"}:
            layout = "billing"
            component_type = "button"
        elif arch.product_type in {"portfolio_site", "website"}:
            layout = "landing"
            component_type = "form" if page_name == "Contact" else "list"
        elif page_name in {"Account", "Seat Selection"}:
            layout = "dashboard"
            component_type = "table" if page_name == "Seat Selection" else "form"
        elif page_name == "Analytics":
            layout = "analytics"
            component_type = "chart"
        else:
            layout = "crud"
            component_type = "list"
        if route in existing_routes:
            continue
        fields = [col.name for col in _entity_fields(entity)] if entity else []
        fields = [field for field in fields if field not in {"id", "created_at", "owner_id"}][:4]
        pages.append(
            UIPage(
                route=route,
                title=page_name,
                roles=["public"] if arch.product_type in {"portfolio_site", "website"} or page_name not in {"Checkout", "Account", "Seat Selection"} else arch.roles,
                layout=layout,
                components=[
                    UIComponent(
                        id=f"{page_name.lower().replace(' ', '_')}_primary",
                        type=component_type,
                        entity=entity,
                        fields=fields,
                        endpoint=f"/api/{entity}" if entity else None,
                    )
                ],
            )
        )
        existing_routes.add(route)

    for entity in sorted(set(arch.entities)):
        if entity == "users" or any(page.title == entity.replace("_", " ").title() for page in pages):
            continue
        pages.append(
            UIPage(
                route=f"/{entity}",
                title=entity.replace("_", " ").title(),
                roles=arch.roles,
                layout="crud",
                components=[
                    UIComponent(id=f"{entity}_table", type="table", entity=entity, fields=["name", "status"], endpoint=f"/api/{entity}"),
                    UIComponent(id=f"{entity}_form", type="form", entity=entity, fields=["name", "description", "status"], endpoint=f"/api/{entity}"),
                ],
            )
        )
    if "Billing" in arch.pages:
        billing_roles = sorted(set([*arch.roles, "premium_user", "user"]), key=[*arch.roles, "premium_user", "user"].index)
        pages.append(
            UIPage(
                route="/billing",
                title="Billing",
                roles=billing_roles,
                layout="billing",
                components=[UIComponent(id="plan_checkout", type="button", fields=["plan_id"], endpoint="/api/subscriptions/checkout")],
            )
        )
    if "Analytics" in arch.pages:
        pages.append(
            UIPage(
                route="/analytics",
                title="Analytics",
                roles=["admin"],
                layout="analytics",
                components=[UIComponent(id="admin_metrics", type="chart", entity="analytics", fields=["metric_name", "value"], endpoint="/api/analytics")],
            )
        )
    return pages


async def generate_auth_rules(arch: AppArchSpec, llm: LLMClient) -> list[AuthRule]:
    if llm.is_configured():
        sys_prompt = f"""You are a Security Architect. Generate auth rules for: {arch.app_name}.
Roles: {arch.roles}
Business Rules: {arch.business_rules}
JSON Schema: list of objects with 'role' (string) and 'permissions' (list of strings, e.g., 'read:own', 'create:*').
"""
        try:
            data = await llm.generate_json(sys_prompt, temperature=0.1)
            return [AuthRule(**rule) for rule in data]
        except Exception:
            if llm.strict_llm or not llm.allow_fallback:
                raise
            pass

    rules = []
    for role in arch.roles:
        if role == "admin":
            permissions = ["read:*", "create:*", "update:*", "delete:*", "view:analytics"]
        elif role == "premium_user":
            permissions = ["read:own", "create:own", "update:own", "use:premium"]
        else:
            permissions = ["read:own", "create:own", "update:own"]
        rules.append(AuthRule(role=role, permissions=permissions))
    return rules
