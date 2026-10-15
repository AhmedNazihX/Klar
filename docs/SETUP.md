# Setup beyond the tests

The README's *Setup from a clean clone* gets the tests running with no keys. This page covers the two steps after
it: a Supabase project of your own for the app, and the MCP server in Claude Desktop.

## A Supabase project of your own

Create a project in an EU region, then from the repo root: `supabase link --project-ref <ref>`, `supabase db push`
(the schema) and `supabase config push` (anonymous sign-ins). Load the legal texts from the committed
`data/parsed/` with `uv run aiact corpus load` (free), embed them with `uv run aiact corpus embed` (paid on your
OpenRouter key: about 1.3 million tokens, $0.013 in decision 003's Qwen3 run), and load the obligations table from
`backend/` (`supabase db push` doesn't run the seed, and `supabase db query -f` can't run this multi-statement
file):

```sh
uv run python -c "import pathlib, psycopg; from aiact.settings import get_settings; psycopg.connect(get_settings().database_url.get_secret_value(), autocommit=True).execute(pathlib.Path('../supabase/seed/obligations.sql').read_text())"
```

It loads into `DATABASE_URL` from `backend/.env`, replacing the amended-text rows, so it is safe to rerun.

## Claude Desktop (MCP)

Add the server to Claude Desktop's config (Settings › Developer › Edit Config; on macOS
`~/Library/Application Support/Claude/claude_desktop_config.json`) with absolute paths (`which uv` for the first),
then restart Claude Desktop:

```json
{
  "mcpServers": {
    "Klar": {
      "command": "/absolute/path/to/uv",
      "args": ["run", "--directory", "/absolute/path/to/repo/backend", "aiact", "mcp", "serve"],
      "env": { "MCP_OPENROUTER_API_KEY": "sk-or-v1-your-own-key" }
    }
  }
}
```

The server (`aiact mcp serve`, over stdio) reads the database and the model ids from `backend/.env`.
`classify_system` runs only on `MCP_OPENROUTER_API_KEY`, your own OpenRouter key, never on the app's
`OPENROUTER_API_KEY`, which embeds the lookups' search queries. A classification takes about 80 s. The key's
OpenRouter spending limit is its only budget cap. The recorded run is in [the demo](demo/mcp-claude-desktop.md).
