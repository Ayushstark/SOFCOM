from __future__ import annotations

import re

from backend.schemas import IntentGraph
from backend.llm.client import LLMClient


FEATURE_KEYWORDS = {
    "login": ["login", "auth", "authentication", "sign in"],
    "dashboard": ["dashboard", "overview", "home"],
    "payments": ["payment", "stripe", "subscription", "premium", "billing", "plan"],
    "ticket_purchase": ["ticket", "tickets", "purchase", "checkout"],
    "seat_selection": ["seat", "seats", "seat selection", "venue map"],
    "responsive_design": ["responsive", "mobile", "desktop"],
    "analytics": ["analytics", "report", "metrics", "chart"],
    "role_based_access": ["role", "admin", "permission", "rbac"],
    "notifications": ["notification", "email", "reminder"],
    "search": ["search", "filter"],
    "chatbot": ["chatbot", "assistant", "bot"],
    "3d_visual": ["3d", "three-dimensional", "spinning", "rotate"],
    "audio": ["sound", "audio", "meow", "rocket"],
    "animated_experience": ["animation", "animated", "floating", "galaxy", "space", "game"],
    "fridge_layout": ["smart fridge", "fridge", "kiosk"],
    "portfolio_showcase": ["portfolio", "work samples", "case studies", "testimonials"],
    "contact_capture": ["contact form", "contact section", "contact page"],
}

ENTITY_HINTS = {
    "crm": ["contacts", "companies", "deals", "tasks"],
    "ecommerce": ["products", "orders", "customers", "payments"],
    "lms": ["courses", "lessons", "students", "enrollments"],
    "booking": ["bookings", "customers", "services"],
    "project": ["projects", "tasks", "teams", "comments"],
    "creative_experience": ["scenes", "assets", "interactions", "chatbot_sessions", "device_profiles"],
    "default": ["users", "items"],
}

RESOURCE_TERMS = {
    "account": "users",
    "accounts": "users",
    "booking": "bookings",
    "bookings": "bookings",
    "cart": "carts",
    "checkout": "orders",
    "concert": "events",
    "concerts": "events",
    "contact form": "contact_messages",
    "contact page": "contact_messages",
    "course": "courses",
    "courses": "courses",
    "customer": "customers",
    "customers": "customers",
    "deal": "deals",
    "deals": "deals",
    "event": "events",
    "events": "events",
    "listing": "listings",
    "listings": "listings",
    "lesson": "lessons",
    "lessons": "lessons",
    "order": "orders",
    "orders": "orders",
    "payment": "payments",
    "payments": "payments",
    "product": "products",
    "products": "products",
    "profile": "users",
    "purchase": "orders",
    "seat": "seats",
    "seats": "seats",
    "student": "students",
    "students": "students",
    "ticket": "tickets",
    "tickets": "tickets",
    "venue": "venues",
    "venues": "venues",
    "testimonial": "testimonials",
    "testimonials": "testimonials",
    "work sample": "work_samples",
    "work samples": "work_samples",
    "portfolio": "projects",
}

SECTION_TERMS = {
    "about": "About",
    "work": "Work",
    "work sample": "Work Samples",
    "work samples": "Work Samples",
    "portfolio": "Portfolio",
    "project": "Projects",
    "projects": "Projects",
    "testimonial": "Testimonials",
    "testimonials": "Testimonials",
    "contact": "Contact",
    "services": "Services",
    "pricing": "Pricing",
    "blog": "Blog",
    "gallery": "Gallery",
}


def _contains_any(text: str, terms: list[str]) -> bool:
    return any(term in text for term in terms)


def _derive_entities_from_prompt(text: str) -> list[str]:
    entities = {entity for term, entity in RESOURCE_TERMS.items() if re.search(rf"\b{re.escape(term)}\b", text)}
    if "user account" in text or "user accounts" in text:
        entities.add("users")
    if "ticket" in text and "purchase" in text:
        entities.add("orders")
    if "seat" in text:
        entities.add("seats")
    return sorted(entities)


def derive_sections_from_prompt(text: str) -> list[str]:
    sections = []
    for term, section in SECTION_TERMS.items():
        if re.search(rf"\b{re.escape(term)}\b", text):
            sections.append(section)
    return list(dict.fromkeys(sections))


def _is_static_marketing_or_portfolio(text: str) -> bool:
    return bool(re.search(r"\b(portfolio|landing page|website|personal site|showcase)\b", text)) and not _contains_any(
        text,
        ["dashboard", "admin", "crm", "inventory", "booking system", "marketplace"],
    )


async def extract_intent(prompt: str, llm: LLMClient) -> IntentGraph:
    clean = " ".join(prompt.strip().split())
    lower = clean.lower()
    placeholder_tokens = re.findall(r"\[[^\]]+\]", clean)

    def _expected_features_from_prompt(text: str) -> list[str]:
        return sorted({name for name, terms in FEATURE_KEYWORDS.items() if _contains_any(text, terms)})

    def _template_questions() -> list[str]:
        return [
            "Should this be a website, an app, or both?",
            "What is the exact niche or use-case (for example portfolio, food delivery, or fitness tracker)?",
            "Which pages/features are mandatory for v1 versus optional?",
            "Do you want authentication and payments enabled in the first release?",
        ]

    if llm.is_configured():
        sys_prompt = f"""You are an expert software architect analyzing a product prompt.
Parse the user's intent into a structured JSON configuration matching this exact schema:
{{
  "original_prompt": "{clean}",
  "product_type": "string (e.g. crm, ecommerce, lms, booking, project, creative_experience, custom, default)",
  "features": ["list of strings (e.g. login, dashboard, payments)"],
  "entities": ["list of strings (plural nouns for core resources like users, contacts)"],
  "roles": ["list of strings (e.g. user, admin)"],
  "business_rules": ["list of strings detailing policies like 'Premium features require subscription'"],
  "assumptions": ["list of strings detailing any assumptions made for underspecified areas or resolving conflicting requirements"],
  "clarification_questions": ["list of strings asking about vague, conflicting, or ambiguous parts of the prompt"],
  "ambiguity_score": float (0.0 to 1.0)
}}

Important rules:
- Detect vague, conflicting, or underspecified inputs.
- If the prompt is vague or underspecified: set "ambiguity_score" > 0.5, make reasonable default assumptions (add them to "assumptions"), and list questions to clarify the app's goals (add them to "clarification_questions").
- If there are conflicting requirements: document the conflicts and how you resolved them as assumptions (e.g., "Assumed X instead of Y because...").
- Do not force the prompt into CRM/ecommerce/booking templates unless the user clearly asks for that category.
- Preserve domain resources directly named by the user (for example events, tickets, seats, courses, products, contacts).
- Always ensure valid JSON.
- Include 'login' feature and 'users' entity if they aren't explicitly excluded but are reasonably needed.

Prompt to analyze:
{clean}"""
        try:
            data = await llm.generate_json(sys_prompt, temperature=0.1)
            # Ensure required fields if LLM hallucinated
            data["original_prompt"] = clean
            # If prompt still contains placeholders, treat it as underspecified template input.
            if placeholder_tokens:
                data["product_type"] = "template_unspecified"
                data["ambiguity_score"] = max(float(data.get("ambiguity_score", 0.0)), 0.85)
                existing_assumptions = data.get("assumptions") or []
                data["assumptions"] = list(
                    dict.fromkeys(
                        [
                            *existing_assumptions,
                            "Detected unresolved placeholders; generated a neutral template plan instead of committing to a single domain.",
                        ]
                    )
                )
                # Only keep features that are explicitly present in prompt text.
                explicit_features = _expected_features_from_prompt(lower)
                data["features"] = explicit_features
                existing_questions = data.get("clarification_questions") or []
                data["clarification_questions"] = list(dict.fromkeys([*existing_questions, *_template_questions()]))
            else:
                prompt_entities = _derive_entities_from_prompt(lower)
                if prompt_entities:
                    data["entities"] = sorted(set([*(data.get("entities") or []), *prompt_entities]))
                data["features"] = sorted(set([*(data.get("features") or []), *_expected_features_from_prompt(lower)]))
                if _is_static_marketing_or_portfolio(lower):
                    data["product_type"] = "portfolio_site" if "portfolio" in lower else "website"
                    data["roles"] = ["public"]
                    data["entities"] = sorted(set(prompt_entities))
                    data["assumptions"] = [
                        assumption
                        for assumption in (data.get("assumptions") or [])
                        if "login" not in assumption.lower() and "authentication" not in assumption.lower()
                    ]
            return IntentGraph(**data)
        except Exception:
            if llm.strict_llm:
                raise
            pass  # Fallback to deterministic below

    features = [name for name, terms in FEATURE_KEYWORDS.items() if _contains_any(lower, terms)]

    if placeholder_tokens:
        product_type = "template_unspecified"
    elif _contains_any(lower, ["galaxy", "croissant", "meow", "rocket", "smart fridge", "riddle", "3d", "space exploration", "dating app for plants"]):
        product_type = "creative_experience"
    elif _is_static_marketing_or_portfolio(lower):
        product_type = "portfolio_site" if "portfolio" in lower else "website"
    elif _contains_any(lower, ["crm", "deal"]) or re.search(r"\bcontacts\b", lower):
        product_type = "crm"
    elif _contains_any(lower, ["shop", "store", "ecommerce", "product", "cart"]):
        product_type = "ecommerce"
    elif _contains_any(lower, ["course", "lesson", "student", "learn"]):
        product_type = "lms"
    elif _contains_any(lower, ["appointment", "booking", "clinic", "schedule"]):
        product_type = "booking"
    elif _contains_any(lower, ["project", "task", "kanban"]):
        product_type = "project"
    else:
        product_type = "default"

    roles = ["public"] if product_type in {"portfolio_site", "website"} else ["user"]
    if _contains_any(lower, ["admin", "analytics", "reports", "metrics", "manage"]):
        roles.insert(0, "admin")
    if _contains_any(lower, ["premium", "subscription", "paid"]):
        roles.append("premium_user")

    prompt_entities = _derive_entities_from_prompt(lower)
    entities = prompt_entities or list(ENTITY_HINTS[product_type])
    entities = sorted(set(entities))

    business_rules = []
    if "payments" in features or "ticket_purchase" in features:
        if {"tickets", "seats", "events"} & set(entities):
            business_rules.append("Ticket purchases create an order and reserve selected seats before checkout completes.")
        else:
            business_rules.append("Premium features require an active subscription before access is granted.")
    if "seat_selection" in features:
        business_rules.append("A seat can be reserved by only one active order at a time.")
    if "role_based_access" in features:
        business_rules.append("Admins can manage workspace data; users can only manage their own records.")
    if "analytics" in features:
        business_rules.append("Analytics pages are visible only to admin roles unless explicitly shared.")

    assumptions = []
    questions = []
    ambiguity_score = 0.15
    if placeholder_tokens:
        ambiguity_score = max(ambiguity_score, 0.85)
        assumptions.append("Detected unresolved placeholders; generated a neutral template plan instead of a fixed domain app.")
        questions.extend(_template_questions())
    if len(clean) < 35 or product_type == "default":
        ambiguity_score += 0.35
        assumptions.append("Defaulted to a generic CRUD SaaS because the product category was underspecified.")
    if product_type == "creative_experience":
        assumptions.append("Interpreted mixed creative requirements as an interactive experience website instead of a business CRUD app.")
        ambiguity_score = max(ambiguity_score, 0.45)
    if "tickets" in entities and "ticket_purchase" not in features:
        features.append("ticket_purchase")
    if "seats" in entities and "seat_selection" not in features:
        features.append("seat_selection")
    if "login" not in features and product_type not in {"creative_experience", "portfolio_site", "website"}:
        assumptions.append("Included email/password login because most generated business apps need authentication.")
        features.append("login")
    if not business_rules:
        assumptions.append("No complex business policy was specified, so standard owner-based access rules were used.")
    if "or" in lower and "?" in lower:
        questions.append("The prompt appears to contain alternatives; which option should be prioritized?")
        ambiguity_score += 0.2

    return IntentGraph(
        original_prompt=clean,
        product_type=product_type,
        features=sorted(set(features)),
        entities=entities,
        roles=sorted(set(roles), key=roles.index),
        business_rules=business_rules,
        assumptions=assumptions,
        clarification_questions=questions,
        ambiguity_score=min(1, ambiguity_score),
    )
