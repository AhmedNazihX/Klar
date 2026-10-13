# Local development. `make dev` runs the API (:8000) and the frontend (:5173) together;
# Ctrl-C stops both. The app's database is the hosted Supabase project in backend/.env and
# frontend/.env.local (decision 034). `make db` starts the local test database the backend tests
# use: Postgres only, the same services CI starts (`supabase stop` keeps its data; never reset it).
# `make e2e-db` starts the end-to-end tests' own stack (frontend/e2e/supabase: Postgres, Auth and the
# REST API on ports 54331-54332, beside the test database) and loads the corpus into it; then
# `make e2e` runs the Playwright flows (frontend/README.md › End-to-end tests).

.PHONY: dev api web db e2e-db e2e

dev:
	$(MAKE) -j2 api web

api:
	cd backend && uv run aiact api serve

web:
	cd frontend && corepack pnpm dev

db:
	supabase start -x gotrue,realtime,storage-api,imgproxy,kong,mailpit,postgrest,postgres-meta,studio,edge-runtime,logflare,vector,supavisor

E2E_DATABASE_URL := postgresql://postgres:postgres@127.0.0.1:54332/postgres

e2e-db:
	supabase start --workdir frontend/e2e -x imgproxy,postgres-meta,vector,logflare,supavisor,mailpit,studio,edge-runtime,realtime,storage-api
	cd backend && DATABASE_URL=$(E2E_DATABASE_URL) uv run aiact corpus load --stats "$${TMPDIR:-/tmp}/aiact_e2e_corpus_stats.md"

e2e:
	cd frontend && corepack pnpm e2e
