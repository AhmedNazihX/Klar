# Local development. `make dev` runs the API (:8000) and the frontend (:5173) together;
# Ctrl-C stops both. The database is the hosted Supabase project in backend/.env and
# frontend/.env.local (decision 034); `make db` starts a local stack only for offline work.

.PHONY: dev api web db

dev:
	$(MAKE) -j2 api web

api:
	cd backend && uv run aiact api serve

web:
	cd frontend && corepack pnpm dev

db:
	supabase start
