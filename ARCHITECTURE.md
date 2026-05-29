# SOFCOM Architecture

## End-to-End Flow

`Prompt`  
-> `IntentGraph`  
-> `AppArchSpec`  
-> `UI/API/DB/Auth schemas`  
-> `Validation`  
-> `Targeted repair passes`  
-> `Runtime simulation`  
-> `Executable result + metrics`

## Pipeline Boundaries

1. `stage1_intent.py`
   - parses natural language into typed intent
2. `stage2_design.py`
   - transforms intent into system architecture
3. `stage3_schema.py`
   - generates UI/API/DB/Auth schema layers
4. `stage4_refinement.py`
   - validates, repairs, simulates runtime, records metrics

## Strict Contracts

All stage outputs are validated through Pydantic models in:
- `backend/schemas/final_config.py`

Core guarantees:
- valid typed output objects
- required fields present
- cross-layer consistency checks before runtime pass

## Validation and Repair

Validator (`backend/repair/validators.py`) enforces:
- UI/API/DB/Auth presence
- API response entity exists in DB
- API request fields map to DB columns
- UI component endpoints/entities/fields map correctly
- role consistency across UI/API/Auth
- premium business-rule coherence

Repair engine (`backend/repair/engine.py`) performs:
- issue-code-driven targeted fixes
- bounded iterative re-validation
- no blind full-pipeline regeneration

## Execution Awareness

Runtime simulator (`backend/runtime/simulator.py`):
- blocks runtime pass if unresolved validation errors exist
- generates runtime artifact in `generated_apps/<app_id>/index.html`
- returns executable status + runtime issues

## Evaluation + Metrics

Evaluation runner (`backend/evaluation/runner.py`):
- executes 20-prompt dataset
- reports:
  - success rate
  - retries per request
  - failure type distribution
  - latency
  - cost vs quality summary
