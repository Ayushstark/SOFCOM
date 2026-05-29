# NL App Compiler

Compiler-style pipeline that converts open-ended product prompts into strict, validated, executable app configuration.

The demo task asks for:

- natural language to structured config
- multi-stage generation
- schema enforcement
- validation and repair
- deterministic behavior
- execution awareness
- failure handling
- evaluation metrics

This repository implements a deterministic first version of that workflow.

## Workflow

1. **Intent extraction**: parses product type, features, entities, roles, business rules, assumptions, and ambiguity.
2. **System design**: converts intent into architecture: pages, flows, entities, roles, and policies.
3. **Schema generation**: creates UI pages/components, API endpoints, DB tables, and auth rules.
4. **Refinement**: validates cross-layer consistency and repairs only the broken layer.
5. **Runtime simulation**: writes a generated `index.html` into `generated_apps/<app_id>` and exposes it at `/apps/<app_id>/index.html`.
6. **Evaluation**: runs 20 prompts and reports success rate, latency, repair count, and failure types.

## Run

```bash
pip install -r requirements.txt
uvicorn api.main:app --reload
```

Open `http://127.0.0.1:8000`.

If another local app is already using `8000`, run:

```bash
uvicorn api.main:app --reload --port 8002
```

## Environment

Create `.env` from `.env.example` and set:

```bash
LLM_PROVIDER=gemini
GEMINI_API_KEY=YOUR_GEMINI_API_KEY
GEMINI_MODEL=gemini-1.5-flash
```

The current compiler remains deterministic by default. Gemini is wired through `backend/llm/client.py` for provider-backed stage upgrades.

## API

- `POST /generate`: returns the final app config.
- `POST /validate`: returns validation issues.
- `POST /simulate`: runs runtime simulation.
- `POST /evaluate`: runs the 20-prompt evaluation suite.
- `GET /apps/<app_id>/index.html`: generated app runtime preview.

## UI

The frontend includes:

- prompt input
- stage progress strip
- validation report
- compiler metrics
- generated JSON viewer
- generated runtime preview link
- Spline-powered visual panel for the compiler/pipeline experience

Replace the Spline URL in `frontend/index.html` with your own scene before final submission.

## Tradeoff

The current implementation uses deterministic-local generation instead of live LLM calls. This keeps the system stable, cheap, and testable for the demo. A provider-backed LLM can be introduced behind the same stage interfaces later for richer generation, while preserving validation, repair, and runtime checks.
