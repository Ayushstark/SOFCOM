from __future__ import annotations

import os
from typing import Any

from backend.pipeline.stage4_refinement import compile_prompt
from backend.schemas import AppConfig

_CACHE: dict[str, tuple[AppConfig, list[dict[str, Any]]]] = {}


async def compile_cached(prompt: str, force_refresh: bool = False) -> tuple[AppConfig, list[dict[str, Any]]]:
    """Cache compilation results by prompt text.

    Returns (config, log_entries).
    """
    bypass = os.getenv("BYPASS_COMPILE_CACHE", "false").strip().lower() in {"1", "true", "yes", "on"}
    if bypass or force_refresh:
        return await compile_prompt(prompt)
    if prompt not in _CACHE:
        _CACHE[prompt] = await compile_prompt(prompt)
    return _CACHE[prompt]
