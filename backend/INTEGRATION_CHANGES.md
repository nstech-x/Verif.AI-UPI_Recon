**UPI-Recon — Integration & Implementation Summary**

- **Project Root**: UPI-Recon/backend
- **Purpose**: Batch reconciliation of UPI transactions across CBS, Switch, NPCI and NTSL, with file-based ingestion, reconciliation engine, auditing, maker/checker flow and a chatbot lookup microservice.

**Overview of What The Codebase Does**
- Ingests multiple financial files (CBS, Switch, NPCI, NTSL, Adjustments) per reconciliation run and organizes them under `data/uploads/RUN_*`.
- Runs reconciliation logic to match transactions by RRN/UPI ID, amount and date, classifying records as MATCHED, PARTIAL_MATCH, ORPHAN, HANGING, MISMATCH, etc.
- Produces reports and exports (CSV, TTUMs, GL statements) under `data/output` and per-run folders.
- Provides an HTTP API (FastAPI) for uploads, running reconciliation, querying results, downloading TTUMs, enquiry endpoints and administrative rollbacks.
- Includes a small chatbot microservice that serves transaction enquiry lookups from generated `recon_output.json`.
- Uses file-based storage (no DB) for MVP; audit logs and proposal storage are written to `data/output`.

**Key Files / Components**
- Backend API: [backend/app.py](backend/app.py)
- File handling and upload utilities: [backend/file_handler.py](backend/file_handler.py)
- Reconciliation logic & report generation: [backend/recon_engine.py](backend/recon_engine.py)
- Settlement / TTUM generation: [backend/settlement_engine.py](backend/settlement_engine.py)
- Audit & logging: [backend/audit_trail.py](backend/audit_trail.py)
- Chatbot microservice: [backend/chatbot_services/app.py](backend/chatbot_services/app.py)
- Chatbot lookup/indexing: [backend/chatbot_services/lookup.py](backend/chatbot_services/lookup.py)
- Configuration: [backend/config.py](backend/config.py)
- Tests (integration): [backend/tests/test_api_integration.py](backend/tests/test_api_integration.py)

**Implemented Endpoints and Behavior (current state)**
- Auth
  - `POST /api/v1/auth/login`: returns JWT access token for `fake_users_db` entries. See `create_access_token` in `app.py`.
  - `GET /api/v1/auth/me`: returns user profile for a valid bearer token.

- File Upload
  - `POST /api/v1/upload` (multipart/form-data): accepts seven required file fields (or legacy `files` list): `cbs_inward`, `cbs_outward`, `switch`, `npci_inward`, `npci_outward`, `ntsl`, `adjustment`.
  - Query params: `cycle` (1C..10C), `run_date` (YYYY-MM-DD, optional), `direction` (INWARD/OUTWARD).
  - Validations implemented: required files presence, per-file size limit 100 MB, basic CSV/XLSX content checks (columns, numeric Amount, Tran_Type values), cycle format.
  - Saves files under `data/uploads/RUN_<timestamp>/[cycle_<id>/][direction/]` and writes metadata files (`file_metadata.json`, `file_mapping.json`, top-level `metadata.json`).
  - Response: HTTP 201 { "status": "success", "run_id": "RUN_..." }

- Run Reconciliation
  - `POST /api/v1/recon/run` accepts JSON `{ "run_id": "RUN_..." }` and runs reconciliation for that run.
  - The server locates the actual folder (supports nested cycle/direction subfolders), loads files via `FileHandler.load_files_for_recon`, runs `ReconciliationEngine.reconcile`, and generates reports and TTUMs.
  - Audit logs reconciliation completion.
  - Behaviour is synchronous in this MVP (returns after run completes).

- Query & Reports
  - `GET /api/v1/recon/latest/summary`: returns latest `summary.json` (searches nested folders).
  - `GET /api/v1/recon/latest/unmatched`: returns unmatched list derived from `recon_output.json` (handles both dict and legacy list formats).
  - `GET /api/v1/recon/latest/hanging`: returns hanging state or `hanging.csv` when available.
  - `GET /api/v1/reports/ttum`: packages TTUM CSV files for a run into a zip (requires role enforcement).
  - `GET /api/v1/upload/metadata?run_id=...`: returns `file_metadata.json` for a run.

- Enquiry
  - `GET /api/v1/enquiry?rrn=...`: searches latest runs for a specified RRN and returns the matching record or 404 if not found.
  - Chatbot microservice exposes equivalent endpoints on port 5001 by default (see `chatbot_services/app.py`).

- Maker / Checker Force-Match Flow (Newly implemented)
  - `POST /api/v1/force-match` (Maker): propose a force-match. Body: `{ "run_id": "...", "rrn": "...", "action": "match_same_file", "direction": "Inward", "reason": "..." }`.
    - Stores proposals in `data/output/<run_id>_proposals.json` and returns `{ "status": "proposed", "proposal_id": "PROP_..." }`.
  - `POST /api/v1/force-match/approve` (Checker): approve a proposal. Body: `{ "proposal_id": "PROP_...", "comments": "..." }`.
    - Enforces maker != checker (rejects if same user).
    - Updates proposal status to `approved`, persists, and marks the corresponding RRN in `recon_output.json` as `FORCE_MATCHED`.
    - Returns `{ "status": "approved", "ttum_generated": true }` (demo behavior).

- Security, CORS & Rate Limiting
  - JWT auth required for write operations (implemented via `HTTPBearer` dependency `get_current_user`).
  - CORS tightened to `FRONTEND_ORIGIN` env var (default `http://localhost:5173`) and allowed methods/headers restricted.
  - Simple in-memory per-user rate limiter added: default 10 requests per 60 seconds (configurable via `RATE_LIMIT_MAX` env var). Implemented as `rate_limiter` FastAPI dependency and used on write endpoints.

**Recent Integration Fixes (what was changed during work)**
- Made upload endpoint accept both named fields and legacy `files` list (backwards compatibility for tests/clients).
- Enforced 100 MB per-file limit and improved validation error reporting.
- Save files into a logical nested folder structure: `data/uploads/RUN_<ts>/cycle_<X>/inward`.
- Robust run-folder discovery for reconciliation and reporting (search nested cycle/direction folders for `recon_output.json`, `summary.json`, etc.).
- Defensive fixes in `recon_engine` summary generation to ignore non-transaction entries (e.g., `hanging_list`) to avoid AttributeError.
- Fixed `recon_output.json` writing bug related to local variable shadowing of `json`.
- Added maker/checker proposal persistence (file-backed) and enforcement of maker ≠ checker.
- Added a simple rate limiter and tightened CORS configuration.
- Improved logging (exception tracebacks when reconciliation fails) and resiliency for missing user information in audit calls.

**Tests & Verification**
- Ran integration test: `tests/test_api_integration.py::test_full_flow_upload_and_recon` — it passed locally after fixes.
- Recommendation: run the full test suite next:

```bash
# from backend folder
.venv\Scripts\python.exe -m pytest -q
```

**How to run services locally**
- Backend API (default port 8000)

```bash
# from backend folder
.venv\Scripts\python.exe -m uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

- Chatbot microservice (port 5001 by default)

```bash
# from backend/chatbot_services
.venv\Scripts\python.exe -m uvicorn app:app --host 0.0.0.0 --port 5001 --reload
```

**Environment variables & configuration**
- `FRONTEND_ORIGIN`: override allowed frontend origin for CORS (default `http://localhost:5173`).
- `RATE_LIMIT_MAX`: requests per window (default `10`).
- `CHATBOT_PORT`: port for chatbot microservice (default `5001`).
- `SECRET_KEY`: currently hard-coded in `backend/app.py` — replace with secure secret in production.

**Limitations / Notes**
- Current MVP uses file-based persistence; for production move to a DB for proposals, jobs, audit and rate-limiting (Redis).
- Reconciliation is synchronous in the API; consider background job queuing (Celery / RQ) for long runs and return 202 + job_id.
- TTUM generation / settlement code contains business rules and strict validations; sample/test data must include required fields (e.g., dates) or TTUM generation will error for missing fields.
- Auth uses an in-memory `fake_users_db` populated from `config/roles.json` — replace with proper user management in production.

.

**Files modified during integration work**
- [backend/app.py](backend/app.py)
- [backend/recon_engine.py](backend/recon_engine.py)
- [backend/file_handler.py](backend/file_handler.py) (existing behavior reviewed; no breaking changes)
- [backend/chatbot_services/app.py](backend/chatbot_services/app.py)

---