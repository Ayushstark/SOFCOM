from __future__ import annotations

import os
from pathlib import Path

from backend.schemas import AppConfig, RuntimeResult, ValidationIssue


GENERATED_ROOT = Path("/tmp/generated_apps") if os.getenv("VERCEL") else Path("generated_apps")


def _render_html(config: AppConfig) -> str:
    nav = "\n".join(f'<a href="#{page.route}">{page.title}</a>' for page in config.ui_schema)
    routes = "\n".join(
        f"""
        <section id="{page.route}">
          <h2>{page.title}</h2>
          <p>Layout: {page.layout} | Roles: {", ".join(page.roles)}</p>
          <ul>{''.join(f'<li>{component.type}: {component.id}</li>' for component in page.components)}</ul>
        </section>
        """
        for page in config.ui_schema
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{config.app_name}</title>
  <style>
    body {{ margin: 0; font-family: Inter, Arial, sans-serif; background: #f6f7fb; color: #172033; }}
    header {{ padding: 32px; background: #101827; color: white; }}
    nav {{ display: flex; flex-wrap: wrap; gap: 10px; padding: 16px 32px; background: white; border-bottom: 1px solid #dde3ee; }}
    nav a {{ color: #2251d1; text-decoration: none; font-weight: 700; }}
    main {{ display: grid; gap: 18px; padding: 24px 32px; }}
    section {{ background: white; border: 1px solid #dde3ee; border-radius: 8px; padding: 18px; }}
  </style>
</head>
<body>
  <header><h1>{config.app_name}</h1><p>Generated from strict compiler config.</p></header>
  <nav>{nav}</nav>
  <main>{routes}</main>
</body>
</html>"""


def simulate_runtime(config: AppConfig) -> RuntimeResult:
    issues: list[ValidationIssue] = []
    routes = [page.route for page in config.ui_schema]
    if not routes:
        issues.append(ValidationIssue(code="R001", severity="error", layer="runtime", message="No routes were available to render."))
    if any(issue.severity == "error" for issue in config.validation_report):
        issues.append(ValidationIssue(code="R002", severity="error", layer="runtime", message="Validation errors prevent execution."))

    app_dir = GENERATED_ROOT / config.app_id
    generated_files: list[str] = []
    executable = not any(issue.severity == "error" for issue in issues)
    if executable:
        app_dir.mkdir(parents=True, exist_ok=True)
        index = app_dir / "index.html"
        index.write_text(_render_html(config), encoding="utf-8")
        generated_files.append(str(index.as_posix()))

    return RuntimeResult(executable=executable, routes_checked=routes, generated_files=generated_files, issues=issues)
