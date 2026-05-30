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
        self.model = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
        self.strict_llm = os.getenv("STRICT_LLM", "true").strip().lower() in {"1", "true", "yes", "on"}

    @property
    def mode(self) -> str:
        if self.provider == "gemini" and self.api_key:
            return "gemini"
        return "deterministic-local"

    def is_configured(self) -> bool:
        return self.mode == "gemini"

    # ── raw text generation ──────────────────────────────────────────
    async def generate_text(self, prompt: str, *, temperature: float = 0.0) -> str:
        if not self.is_configured():
            raise RuntimeError("Gemini is not configured. Set GEMINI_API_KEY in .env.")

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        payload: dict[str, Any] = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": temperature},
        }
        async with httpx.AsyncClient(timeout=45) as client:
            response = await client.post(url, params={"key": self.api_key}, json=payload)
            response.raise_for_status()
            data = response.json()

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
