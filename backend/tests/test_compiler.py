import pytest
from backend.pipeline import compile_prompt


@pytest.mark.anyio
async def test_crm_prompt_compiles_to_executable_config():
    config, log = await compile_prompt(
        "Build a CRM with login, contacts, dashboard, role-based access, premium plan with payments. Admins can see analytics."
    )

    assert config.runtime is not None
    assert config.runtime.executable is True
    assert not [issue for issue in config.validation_report if issue.severity == "error"]
    assert any(page.route == "/analytics" for page in config.ui_schema)
    assert any(endpoint.path == "/api/subscriptions/checkout" for endpoint in config.api_schema)


@pytest.mark.anyio
async def test_vague_prompt_documents_assumptions():
    config, log = await compile_prompt("Build an app.")

    assert config.intent.ambiguity_score > 0.4
    assert config.assumptions
    assert config.runtime and config.runtime.executable
