# Conventions

- Keep frontend UI data-driven through `apps/web/lib/api.ts`; screen components receive typed API payloads instead of hardcoded UI-only data where possible.
- Use CSS Modules for app screen styling unless a design-system package is introduced later.
- FastAPI routes live under `services/api/app/api/routes`; route handlers should return `ApiResponse[T]` schemas from `services/api/app/schemas/common.py`.
- Backend mock/business data belongs in `services/api/app/services` until persistence repositories are introduced.
- Migrations should be explicit SQL files; enable required extensions in the migration that first uses their functions/types.