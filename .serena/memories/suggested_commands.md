# Suggested Commands

- List tracked project files on Windows: `rg --files` from repo root.
- Frontend install: `npm install` from repo root.
- Frontend dev: `npm run dev:web` from repo root, serves `http://127.0.0.1:3000`.
- Frontend typecheck/build: `npm run typecheck:web`, `npm run build:web`.
- API dependency setup: create a local venv, then `python -m pip install -r services/api/requirements.txt`.
- API dev: from `services/api`, run `python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload`.
- Local data services: `docker compose -f infra/docker-compose.yml up -d postgres redis` from repo root.