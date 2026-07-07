# Tech Stack

- Frontend: Next.js 15.1.4 App Router, React 19, TypeScript 5.7, CSS Modules for screen-level styling.
- Backend: Python FastAPI 0.115, Pydantic Settings 2.7, Uvicorn, Pydantic schemas under `services/api/app/schemas`.
- Data: PostgreSQL 16 with pgvector image (`pgvector/pgvector:pg16`), Redis 7, SQL migrations in `services/api/migrations`.
- Package manager: npm workspaces from repo root; web workspace is `apps/web`.
- Runtime config: root `.env.example` documents placeholders only; do not commit real secrets or print `.env` values.