# Demo: Klar in Claude Desktop (MCP)

Recorded on 2026-10-13 with the `Klar` server from the Claude Desktop config in [docs/SETUP.md](../SETUP.md)
(stdio, `aiact mcp serve`), on the user's own `MCP_OPENROUTER_API_KEY`.

[![Claude Desktop calls Klar's classify_system on INIT's worked example](mcp-claude-desktop.png)](mcp-claude-desktop.mp4)

[Watch the recording (31 s, MP4)](mcp-claude-desktop.mp4)

## What it shows

1. **The question.** INIT's worked example: "We're a 40-person logistics company. We use a tool that reads
   incoming job applications, scores them, and shows HR a ranked shortlist. We bought it from a vendor and
   didn't change it."
2. **The first call.** Claude Desktop picks `classify_system` by itself and asks before running it (the tool is
   marked as not read-only, because every call is paid). The result: high-risk under Annex III point 4(a) as the
   working assumption, the company as deployer, its duties with their dates, and one open point: whether the
   tool is an AI system at all (Art. 3(1)).
3. **The answer loop.** The answer "the tool was trained on past hiring data to score applicants, and we use it
   in Germany" goes back into a second `classify_system` call. The scope question is settled and the high-risk
   classification confirmed.

## Measured

- **Time:** 80 s of server time per classification (Claude Desktop's log: call at 18:43:27, result at
  18:44:47 UTC); 1 min 48 s on the user's stopwatch, including the approval click and Claude's write-up. Claude
  Desktop waited without a timeout, so no start-and-poll tools are needed.
- **Cost:** about $0.0075 per classification on OpenRouter (the worked example's recorded e2e runs, P13), on
  the caller's key.

## Seen in the run

On the second call the engine left Art. 5(1)(c) (social scoring) open, so the result carried the ban as a
working assumption until that question is answered; the first call found no prohibited practice. Claude's own
write-up calls it a cautious placeholder. This is the over-strictness E19 worked on, seen once live; story E20
checks it.
