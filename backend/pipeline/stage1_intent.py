from __future__ import annotations

import re

from backend.schemas import IntentGraph
from backend.llm.client import LLMClient


FEATURE_KEYWORDS = {
    "login": ["login", "auth", "authentication", "sign in"],
    "dashboard": ["dashboard", "overview", "home"],
    "payments": ["payment", "stripe", "subscription", "premium", "billing", "plan"],
    "analytics": ["analytics", "report", "metrics", "chart"],
    "role_based_access": ["role", "admin", "permission", "rbac"],
    "notifications": ["notification", "email", "reminder"],
    "search": ["search", "filter"],
    "chatbot": ["chatbot", "assistant", "bot"],
    "3d_visual": ["3d", "three-dimensional", "spinning", "rotate"],
    "audio": ["sound", "audio", "meow", "rocket"],
    "animated_experience": ["animation", "animated", "floating", "galaxy", "space", "game"],
    "fridge_layout": ["smart fridge", "fridge", "kiosk"],
}

ENTITY_HINTS = {
    "crm": ["contacts", "companies", "deals", "tasks"],
    "ecommerce": ["products", "orders", "customers", "payments"],
    "lms": ["courses", "lessons", "students", "enrollments"],
    "booking": ["appointments", "customers", "staff", "services"],
    "project": ["projects", "tasks", "teams", "comments"],
    "creative_experience": ["scenes", "assets", "interactions", "chatbot_sessions", "device_profiles"],
    "default": ["users", "items"],
}


def _contains_any(text: str, terms: list[str]) -> bool:
    return any(term in text for term in terms)


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
  "product_type": "string (e.g. crm, ecommerce, lms, booking, project, default)",
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
    elif _contains_any(lower, ["crm", "contact", "deal"]):
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

    roles = ["user"]
    if _contains_any(lower, ["admin", "analytics", "reports", "metrics", "manage"]):
        roles.insert(0, "admin")
    if _contains_any(lower, ["premium", "subscription", "paid"]):
        roles.append("premium_user")

    entities = list(ENTITY_HINTS[product_type])
    explicit_nouns = re.findall(r"\b(?:contacts?|dashboards?|payments?|plans?|analytics?|roles?|users?)\b", lower)
    entities.extend(noun.rstrip("s") + "s" for noun in explicit_nouns if noun not in entities)
    entities = sorted(set(entities))

    business_rules = []
    if "payments" in features:
        business_rules.append("Premium features require an active subscription before access is granted.")
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
    if "login" not in features and product_type != "creative_experience":
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
