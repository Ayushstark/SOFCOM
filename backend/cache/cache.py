from __future__ import annotations

from typing import Any

from backend.pipeline.stage4_refinement import compile_prompt
from backend.schemas import AppConfig

_CACHE: dict[str, tuple[AppConfig, list[dict[str, Any]]]] = {}


async def compile_cached(prompt: str) -> tuple[AppConfig, list[dict[str, Any]]]:
    """Cache compilation results by prompt text.

    Returns (config, log_entries).
    """
    if prompt not in _CACHE:
        _CACHE[prompt] = await compile_prompt(prompt)
    return _CACHE[prompt]
