# Architecture

## Data Flow

Prompt -> `IntentGraph` -> `AppArchSpec` -> UI/API/DB/Auth schemas -> validation -> targeted repair -> runtime simulation -> generated app preview

## Modules

- `backend/schemas`: strict Pydantic contracts.
- `backend/pipeline`: four-stage compiler pipeline.
- `backend/repair`: cross-layer validators and deterministic repairs.
- `backend/runtime`: execution simulator that writes generated app files.
- `backend/evaluation`: 10 product prompts and 10 edge cases with metrics.
- `api/main.py`: FastAPI interface and static frontend hosting.
- `frontend`: prompt UI, metrics, JSON viewer, Spline visual panel.

## Validation Rules

- UI pages and API endpoints must exist.
- Auth-aware apps require a users table.
- API response entities must map to DB tables.
- API request fields must map to DB columns.
- UI component endpoints must exist.
- UI component entities and fields must map to DB schema.
- Premium business rules must include billing and a premium role.
- Ambiguous prompts must carry assumptions or clarification signals.

## Reliability Strategy

The system avoids single-prompt generation. Each stage produces typed intermediate output, then validators catch mismatches across layers. Repairs are targeted: missing role, missing endpoint, missing DB field, and missing billing artifacts are fixed locally instead of retrying the whole compile.
