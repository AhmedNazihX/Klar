# Local development. `make dev` runs the API (:8000) and the frontend (:5173) together;
# Ctrl-C stops both. The app's database is the hosted Supabase project in backend/.env and
# frontend/.env.local (decision 034). `make db` starts the local test database the backend tests
# use: Postgres only, the same services CI starts (`supabase stop` keeps its data; never reset it).

.PHONY: dev api web db

dev:
	$(MAKE) -j2 api web

api:
	cd backend && uv run aiact api serve

web:
	cd frontend && corepack pnpm dev

db:
	supabase start -x gotrue,realtime,storage-api,imgproxy,kong,mailpit,postgrest,postgres-meta,studio,edge-runtime,logflare,vector,supavisor
