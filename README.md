# SOFCOM

SOFCOM is a multi-stage natural-language-to-app compiler system with a production-style dashboard UI.

It takes a single product prompt, compiles it through strict intermediate stages, validates and repairs cross-layer inconsistencies, and produces executable output via runtime simulation.

## What SOFCOM Builds

SOFCOM compiles prompts into a typed `AppConfig` contract containing:

- intent graph
- system architecture
- UI schema
- API schema
- DB schema
- auth rules
- validation report
- runtime simulation result
- compiler metrics

## Pipeline (Clear Stage Separation)

### Stage 1: Intent Extraction (`backend/pipeline/stage1_intent.py`)
- Input: raw user prompt
- Output: `IntentGraph`
- Responsibilities:
  - product type detection
  - feature extraction
  - entities / roles
  - assumptions + clarification signals for vague prompts
  - ambiguity scoring

### Stage 2: System Design (`backend/pipeline/stage2_design.py`)
- Input: `IntentGraph`
- Output: `AppArchSpec`
- Responsibilities:
  - app architecture generation
  - pages, flows, and role-aware behavior
  - business-rule propagation

### Stage 3: Schema Generation (`backend/pipeline/stage3_schema.py`)
- Input: `AppArchSpec`
- Output:
  - UI schema
  - API schema
  - DB schema
  - Auth rules
- Responsibilities:
  - typed schema synthesis per layer
  - deterministic fallback generation

### Stage 4: Validation + Repair + Runtime (`backend/pipeline/stage4_refinement.py`)
- Input: assembled `AppConfig`
- Output: validated, repaired, runtime-checked `AppConfig`
- Responsibilities:
  - cross-layer validation
  - targeted repair passes (not blind full retries)
  - runtime simulation (execution awareness)
  - metrics collection (latency, repair passes, issue count)

## Validation + Repair Engine

- Validator: `backend/repair/validators.py`
- Repair engine: `backend/repair/engine.py`

Detects and handles:
- invalid/missing schema artifacts
- missing roles/endpoints/tables/fields
- UI ↔ API ↔ DB mapping mismatches
- business-logic consistency issues (for example premium flows)

Repairs are targeted by issue code and re-validated after each pass.

## Determinism Strategy

SOFCOM is deterministic-local by default, with optional Gemini integration:

- deterministic fallback logic in every stage
- typed Pydantic contracts in `backend/schemas/final_config.py`
- constrained JSON handling in `backend/llm/client.py`
- bounded repair loop for consistent behavior

## Execution Awareness

Runtime simulator: `backend/runtime/simulator.py`

- verifies executable readiness
- writes generated app artifacts to `generated_apps/<app_id>/index.html`
- marks compile success/failure based on runtime + validation state

## Evaluation Framework

Dataset:
- 10 product prompts
- 10 edge prompts (vague/conflicting/incomplete)
- source: `backend/evaluation/dataset.py`

Runner:
- `backend/evaluation/runner.py`
- metrics:
  - success rate
  - retries per request
  - failure types
  - latency
  - cost vs quality summary

## Dashboard (Frontend)

Stack:
- React + Vite + TypeScript
- Tailwind CSS
- Framer Motion
- Zustand
- TanStack Query
- Monaco Editor
- Recharts
- Sonner

Current UI capabilities:
- SOFCOM branded command center
- collapsible sidebar + tabbed views
- command palette (`Cmd/Ctrl + K`) with working actions
- real `/generate` integration (logs, pipeline, metrics)
- functional JSON / YAML / DIFF config tabs
- evaluation bar with:
  - summary metrics from `/evaluate`
  - testing prompts tab (20 dataset prompts)
  - session summary that includes user-entered prompts
- live runtime analytics from real compile session history

## API Endpoints

- `GET /health`
- `POST /generate`
- `POST /validate`
- `POST /simulate`
- `POST /evaluate`
- `GET /apps/<app_id>/index.html`

## Repository Structure

```text
api/
  main.py                      # FastAPI entrypoint + routes
backend/
  cache/cache.py               # prompt-level compile cache
  evaluation/
    dataset.py                 # 20-prompt benchmark dataset
    runner.py                  # evaluation metrics runner
  llm/client.py                # provider adapter + JSON guardrails
  pipeline/
    stage1_intent.py           # intent extraction
    stage2_design.py           # architecture design
    stage3_schema.py           # ui/api/db/auth generation
    stage4_refinement.py       # validation, repair, runtime, metrics
  repair/
    validators.py              # cross-layer checks
    engine.py                  # targeted issue repair
  runtime/simulator.py         # executable runtime simulation
  schemas/final_config.py      # strict typed contracts
frontend/
  src/features/dashboard/      # SOFCOM dashboard UI
generated_apps/                # runtime-generated artifacts
```

## Local Run

### Backend
```bash
pip install -r requirements.txt
uvicorn api.main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev -- --host 127.0.0.1 --port 4173
```

Open:
- frontend: `http://127.0.0.1:4173`
- backend health: `http://127.0.0.1:8000/health`

## Environment

Create `.env` from `.env.example`:

```bash
LLM_PROVIDER=gemini
GEMINI_API_KEY=YOUR_GEMINI_API_KEY
GEMINI_MODEL=gemini-1.5-flash
```

If no provider key is configured, SOFCOM runs in deterministic-local mode.
