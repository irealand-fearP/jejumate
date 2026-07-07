# Task Completion

- For backend syntax-only changes: run `python -m compileall app` from `services/api`.
- For frontend changes after dependencies are installed: run `npm run typecheck:web`; run `npm run build:web` for route/render changes.
- For schema changes: inspect `services/api/migrations` for required Postgres extensions and indexes; if Docker is available, apply against local Postgres before claiming DB verification.
- For app work that needs browser verification: run API on `127.0.0.1:8000`, web on `127.0.0.1:3000`, then check home page and `/health`.
- After memory maintenance, user can run `serena memories check` from project root.