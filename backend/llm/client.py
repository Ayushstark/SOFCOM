from __future__ import annotations

import json
import os
import re
from typing import Any

import httpx


class LLMClient:
    """Gemini adapter with constrained JSON decoding, retry, and sanitization.

    Uses temperature=0.0 by default for deterministic output.
    Strips markdown fences, repairs trailing commas, and retries on
    parse failure to guarantee valid JSON reaches the pipeline.
    """

    MAX_JSON_RETRIES = 2

    def __init__(self) -> None:
        self.provider = os.getenv("LLM_PROVIDER", "deterministic-local").lower()
        self.api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        self.model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
        self.api_version = os.getenv("GEMINI_API_VERSION", "v1beta")
        self.strict_llm = os.getenv("STRICT_LLM", "true").strip().lower() in {"1", "true", "yes", "on"}
        self.allow_fallback = os.getenv("ALLOW_DETERMINISTIC_FALLBACK", "false").strip().lower() in {"1", "true", "yes", "on"}
        self.used_llm = False
        self.model_fallbacks = [
            model.strip()
            for model in os.getenv(
                "GEMINI_MODEL_FALLBACKS",
                "gemini-2.0-flash,gemini-1.5-flash-latest,gemini-1.5-flash",
            ).split(",")
            if model.strip()
        ]
        self._discovered_models: list[str] | None = None

    @property
    def mode(self) -> str:
        if self.provider == "gemini" and self.api_key:
            return "gemini"
        return "deterministic-local"

    def is_configured(self) -> bool:
        return self.mode == "gemini"

    def _url(self, path: str) -> str:
        return f"https://generativelanguage.googleapis.com/{self.api_version}/{path.lstrip('/')}"

    @staticmethod
    def _redact_error(error: Exception) -> str:
        return re.sub(r"key=[^&\s]+", "key=REDACTED", str(error))

    async def _discover_generate_content_models(self, client: httpx.AsyncClient) -> list[str]:
        if self._discovered_models is not None:
            return self._discovered_models

        response = await client.get(self._url("models"), params={"key": self.api_key})
        response.raise_for_status()
        payload = response.json()
        models: list[str] = []
        for model in payload.get("models", []):
            name = str(model.get("name", "")).replace("models/", "")
            methods = set(model.get("supportedGenerationMethods") or [])
            if name and "generateContent" in methods:
                models.append(name)

        def score(model_name: str) -> tuple[int, str]:
            lowered = model_name.lower()
            if "2.5" in lowered and "flash" in lowered:
                return (0, model_name)
            if "2.0" in lowered and "flash" in lowered:
                return (1, model_name)
            if "1.5" in lowered and "flash" in lowered:
                return (2, model_name)
            if "flash" in lowered:
                return (3, model_name)
            if "pro" in lowered:
                return (4, model_name)
            return (5, model_name)

        self._discovered_models = sorted(dict.fromkeys(models), key=score)
        return self._discovered_models

    # ── raw text generation ──────────────────────────────────────────
    async def generate_text(self, prompt: str, *, temperature: float = 0.0) -> str:
        if not self.is_configured():
            raise RuntimeError("Gemini is not configured. Set GEMINI_API_KEY in .env.")

        payload: dict[str, Any] = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": temperature,
                "responseMimeType": "application/json",
                "maxOutputTokens": 8192,
            },
        }
        last_error: Exception | None = None
        async with httpx.AsyncClient(timeout=45) as client:
            try:
                discovered_models = await self._discover_generate_content_models(client)
            except httpx.HTTPStatusError as exc:
                discovered_models = []
                last_error = exc

            candidates_to_try = list(dict.fromkeys([self.model, *self.model_fallbacks, *discovered_models]))
            if not candidates_to_try:
                raise RuntimeError("Gemini model discovery returned no generateContent-capable models.")

            for model in candidates_to_try:
                url = self._url(f"models/{model}:generateContent")
                response = await client.post(url, params={"key": self.api_key}, json=payload)
                if response.status_code == 404:
                    last_error = httpx.HTTPStatusError(
                        f"Gemini model {model} was not found; trying fallback model.",
                        request=response.request,
                        response=response,
                    )
                    continue
                try:
                    response.raise_for_status()
                    self.model = model
                    self.used_llm = True
                    data = response.json()
                    break
                except httpx.HTTPStatusError as exc:
                    last_error = exc
            else:
                safe_error = self._redact_error(last_error) if last_error else "unknown error"
                raise RuntimeError(f"Gemini request failed for all discovered/configured models: {safe_error}") from last_error

        candidates = data.get("candidates", [])
        if not candidates:
            raise RuntimeError("Gemini returned no candidates.")
        parts = candidates[0].get("content", {}).get("parts", [])
        return "".join(part.get("text", "") for part in parts).strip()

    # ── constrained JSON generation ──────────────────────────────────
    @staticmethod
    def _sanitize_json(raw: str) -> str:
        """Strip markdown fences, trailing commas, and surrounding prose."""
        # Remove ```json ... ``` wrappers
        raw = re.sub(r"```(?:json)?\s*", "", raw)
        raw = raw.strip().rstrip("`")
        # Try to extract just the JSON object / array
        first_bracket = None
        for i, ch in enumerate(raw):
            if ch in "{[":
                first_bracket = i
                break
        if first_bracket is not None:
            raw = raw[first_bracket:]
        # Remove trailing commas before } or ]
        raw = re.sub(r",\s*([}\]])", r"\1", raw)
        return raw

    async def generate_json(self, prompt: str, *, temperature: float = 0.0) -> Any:
        """Generate and parse JSON with automatic retry on parse failure."""
        last_error: Exception | None = None
        for attempt in range(1, self.MAX_JSON_RETRIES + 1):
            suffix = (
                "\n\nReturn ONLY valid JSON. No markdown fences, no comments, no explanation."
                if attempt == 1
                else "\n\nYour previous response was not valid JSON. Return ONLY the raw JSON object/array. No prose."
            )
            text = await self.generate_text(prompt + suffix, temperature=temperature)
            cleaned = self._sanitize_json(text)
            try:
                return json.loads(cleaned)
            except json.JSONDecodeError as exc:
                last_error = exc
        raise RuntimeError(f"LLM returned invalid JSON after {self.MAX_JSON_RETRIES} attempts: {last_error}")
