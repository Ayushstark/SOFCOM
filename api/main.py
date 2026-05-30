from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from pydantic import BaseModel, Field

from backend.cache.cache import compile_cached
from backend.evaluation.runner import run_evaluation
from backend.llm.client import LLMClient
from backend.repair.validators import validate_config
from backend.runtime.simulator import GENERATED_ROOT, simulate_runtime


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
load_dotenv(ROOT / ".env")
llm_client = LLMClient()

app = FastAPI(title="SOFCOM API", version="0.2.0")
cors_origins = [
    "http://127.0.0.1:4173",
    "http://localhost:4173",
    "http://127.0.0.1:5173",
    "http://localhost:5173",
]
frontend_origin = os.getenv("FRONTEND_ORIGIN")
if frontend_origin:
    cors_origins.append(frontend_origin)
extra_origins = os.getenv("FRONTEND_ORIGINS", "")
if extra_origins.strip():
    cors_origins.extend([origin.strip() for origin in extra_origins.split(",") if origin.strip()])
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_origin_regex=r"https:\/\/.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if FRONTEND.exists():
    app.mount("/static", StaticFiles(directory=FRONTEND), name="static")
GENERATED_ROOT.mkdir(parents=True, exist_ok=True)
app.mount("/apps", StaticFiles(directory=GENERATED_ROOT), name="apps")


class GenerateRequest(BaseModel):
    prompt: str = Field(min_length=3)
    force_refresh: bool = False


@app.get("/")
def home() -> FileResponse:
    if not (FRONTEND / "index.html").exists():
        return FileResponse((ROOT / "README.md"))
    return FileResponse(FRONTEND / "index.html")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "mode": llm_client.mode}


@app.post("/generate")
async def generate(request: GenerateRequest) -> dict:
    """Compile a SINGLE user prompt.

    Returns the config, a detailed log of every pipeline step, and metrics.
    Does NOT run the full evaluation dataset.
    """
    config, log = await compile_cached(request.prompt, force_refresh=request.force_refresh)
    return {
        "config": config.as_json_dict(),
        "log": log,
    }


@app.post("/validate")
async def validate(request: GenerateRequest) -> dict:
    config, _log = await compile_cached(request.prompt)
    return {"issues": [issue.model_dump(mode="json") for issue in validate_config(config)]}


@app.post("/simulate")
async def simulate(request: GenerateRequest) -> dict:
    config, _log = await compile_cached(request.prompt)
    return simulate_runtime(config).model_dump(mode="json")


@app.post("/evaluate")
async def evaluate() -> dict:
    """Run all 20 dataset prompts (on-demand only).

    This is the ONLY place the full dataset is exercised.
    """
    return await run_evaluation()
