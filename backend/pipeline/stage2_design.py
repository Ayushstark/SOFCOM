from __future__ import annotations

import re

from backend.schemas import AppArchSpec, IntentGraph
from backend.llm.client import LLMClient


def _title_from_prompt(prompt: str, product_type: str) -> str:
    match = re.search(r"build\s+(?:a|an)?\s*([a-zA-Z ]{3,32}?)(?:\s+with|\s+for|$)", prompt, re.I)
    if match:
        title = match.group(1).strip()
        if title:
            return " ".join(word.capitalize() for word in title.split())
    return f"{product_type.replace('_', ' ').title()} Compiler App"


async def design_system(intent: IntentGraph, llm: LLMClient) -> AppArchSpec:
    if llm.is_configured():
        sys_prompt = f"""You are a Systems Architect. Convert this parsed user intent into an architecture specification.
Return exact JSON matching this schema:
{{
  "app_name": "string (catchy name for this app based on the prompt)",
  "product_type": "{intent.product_type}",
  "entities": {intent.entities},
  "roles": {intent.roles},
  "flows": ["list of strings (core user journeys, e.g. 'Admin reviews analytics', 'User upgrades plan')"],
  "pages": ["list of strings (UI page names, e.g. 'Dashboard', 'Login', 'Billing')"],
  "business_rules": {intent.business_rules},
  "assumptions": {intent.assumptions}
}}

Keep the exact entities, roles, business_rules, and assumptions passed below. Expand on flows and pages.
Intent JSON:
{intent.model_dump_json()}
"""
        try:
            data = await llm.generate_json(sys_prompt, temperature=0.2)
            # Ensure critical lists match intent
            data["entities"] = intent.entities
            data["roles"] = intent.roles
            data["product_type"] = intent.product_type
            return AppArchSpec(**data)
        except Exception:
            if llm.strict_llm:
                raise
            pass  # Fallback

    if intent.product_type == "template_unspecified":
        pages = ["Home", "About", "Contact"]
        if "login" in intent.features:
            pages.append("Login")
        if "payments" in intent.features:
            pages.append("Billing")
        flows = [
            "Visitor lands on a responsive homepage with SEO-friendly structure and accessible content regions.",
            "User navigates core informational sections while pending requirements are represented as configurable modules.",
            "System waits for clarified niche and feature priorities before final domain schema lock-in.",
        ]
    elif intent.product_type == "creative_experience":
        pages = ["Home Experience", "Interactive Audio", "Riddle Chatbot", "Device Layout Profiles"]
        flows = [
            "Visitor lands on a galaxy-themed interactive homepage with animated assets.",
            "User interactions trigger randomized sound effects and visual transitions.",
            "User chats with a gardening-themed riddle chatbot.",
            "Layout adapts between desktop and smart-fridge profiles.",
        ]
    else:
        pages = ["Home"]
        if "login" in intent.features:
            pages.append("Login")
        if intent.product_type in {"crm", "ecommerce", "lms", "booking", "project"} or "dashboard" in intent.features:
            pages.append("Dashboard")
        if "payments" in intent.features:
            pages.append("Checkout")
        if "ticket_purchase" in intent.features:
            pages.append("Checkout")
        if "seat_selection" in intent.features:
            pages.append("Seat Selection")
        if "users" in intent.entities or "login" in intent.features:
            pages.append("Account")
        if "analytics" in intent.features:
            pages.append("Analytics")
        for entity in intent.entities:
            if entity != "users":
                pages.append(entity.replace("_", " ").title())
        pages = list(dict.fromkeys(pages))

        flows = [
            "Visitor opens the main experience and browses the primary domain content.",
            "User interacts with the requested resources and completes the core workflow.",
        ]
        if "login" in intent.features:
            flows.append("User signs in and manages account-specific records.")
        if "ticket_purchase" in intent.features or "payments" in intent.features:
            flows.append("User completes checkout and receives an order record.")
        if "seat_selection" in intent.features:
            flows.append("User selects an available seat before purchase is finalized.")
        if "analytics" in intent.features:
            flows.append("Admin reviews analytics computed from core business tables.")

    return AppArchSpec(
        app_name=_title_from_prompt(intent.original_prompt, intent.product_type),
        product_type=intent.product_type,
        entities=intent.entities,
        roles=intent.roles,
        flows=flows,
        pages=pages,
        business_rules=intent.business_rules,
        assumptions=intent.assumptions,
    )
