# Core

- Monorepo for JejuMate commercial MVP service scaffold.
- Source map: `apps/web` Next.js frontend, `services/api` FastAPI backend, `infra` local Postgres/Redis, `packages/design-tokens` shared visual tokens, `packages/fixtures` mock seed data.
- Product invariant: youth run-cation community/service with privacy-first onboarding, pseudonymous public identity, meetings, policy/RAG information, memories, and admin safety workflows.
- DB invariant: avoid public real-name/phone/birthdate exposure; identity verification should be represented by verification state and tokenized/hashed references, not plaintext PII.
- Read frontend-specific commands/conventions in `mem:tech_stack`, completion checks in `mem:task_completion`.