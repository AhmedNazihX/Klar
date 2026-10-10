# Local development. `make dev` runs the API (:8000) and the frontend (:5173) together;
# Ctrl-C stops both. The database is `supabase start`, run once (`make db`).

.PHONY: dev api web db

dev:
	$(MAKE) -j2 api web

api:
	cd backend && uv run aiact api serve

web:
	cd frontend && corepack pnpm dev

db:
	supabase start
