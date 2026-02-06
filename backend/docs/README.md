# Backend - UPI Recon

Quick guide to run tests and the backend server for development.

Prerequisites
- Python 3.11+
- pip

Install dependencies

```bash
python -m pip install -r backend/requirements.txt
```

Run tests

```bash
python -m pytest backend/tests -q
```

Run the API server (development)

```bash
cd backend
uvicorn app:app --reload --port 8000
```

Notes
- TTUM files are generated under a run folder's `ttum/` directory.
- Raw uploaded files are stored under `uploads/RUN_<timestamp>/cycle_<n>/<direction>/`.
- Exact Annexure IV TTUM formatting is approximated; provide the spec to enforce exact headers.
