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


@pytest.mark.anyio
async def test_creative_prompt_is_not_collapsed_into_business_template():
    prompt = (
        "Make me a website thats a mix of coffee menu, space exploration game, and a dating app for plants. "
        "Use galaxy background with floating croissants, random cat meow or rocket sounds on clicks, "
        "a spinning 3D coffee cup, riddle gardening chatbot, and support desktop and smart fridge."
    )
    config, _ = await compile_prompt(prompt)

    assert config.intent.product_type == "creative_experience"
    assert any(feature in config.intent.features for feature in ["chatbot", "3d_visual", "audio", "fridge_layout"])
    assert not [issue for issue in config.validation_report if issue.code in {"V014", "V015"}]


@pytest.mark.anyio
async def test_template_prompt_with_placeholders_stays_domain_neutral_and_asks_questions():
    prompt = (
        "Create a modern, responsive [website/app] for [purpose or niche]. "
        "Include [specific features] and use [color palette/style]. Add SEO and accessibility."
    )
    config, _ = await compile_prompt(prompt)

    assert config.intent.product_type == "template_unspecified"
    assert config.intent.ambiguity_score >= 0.7
    assert config.intent.clarification_questions
    assert not [issue for issue in config.validation_report if issue.code in {"V016", "V017", "V018"}]


@pytest.mark.anyio
async def test_prompt_grounding_uses_resources_named_by_user():
    config, _ = await compile_prompt(
        "Design a responsive event booking website for concerts, with event listings, "
        "ticket purchase, seat selection, and user accounts. Use vibrant colors and bold typography."
    )

    assert {"events", "tickets", "seats", "orders", "users"}.issubset({table.name for table in config.db_schema})
    assert {"ticket_purchase", "seat_selection", "responsive_design"}.issubset(set(config.intent.features))
    assert {"/events", "/seat-selection", "/checkout", "/account"}.issubset({page.route for page in config.ui_schema})


@pytest.mark.anyio
async def test_portfolio_prompt_preserves_public_sections_without_crm_login():
    config, _ = await compile_prompt(
        "Create a sleek, responsive portfolio website for a graphic designer, with sections for "
        "About, Work Samples, Testimonials, and Contact. Use a minimal black-and-white theme with subtle animations."
    )

    assert config.intent.product_type == "portfolio_site"
    assert config.intent.roles == ["public"]
    assert "login" not in config.intent.features
    assert {"Home", "About", "Work Samples", "Testimonials", "Contact"}.issubset(set(config.architecture.pages))
    assert {"/about", "/work-samples", "/testimonials", "/contact"}.issubset({page.route for page in config.ui_schema})
