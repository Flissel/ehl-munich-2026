# WP4 – Agent Chat Tools: `ehl-agents` MCP

**Branch:** `feat/ehl-agent-chat` · **Folder:** `agents-mcp/` · **Parent spec:** `2026-10-10-rowboat-ehl-space-design.md` (§5.4, §7, §8, §12 contracts)
**Status:** Draft awaiting approval

## 1. Goal

Let the Rowboat agent talk to the Sales agent and the Marketing agents (brand, editor) through chat,
as MCP tools — agent-to-agent, without exposing their raw tool sets and without any send/approve
capability.

**Done when:** from Rowboat, `sales_ask`, `brand_ask` and `content_design` each return a real answer
(or a clean timeout message); no path from these tools can send or approve anything.

## 2. First task: OpenClaw chat endpoint (time-boxed 60 min)

1. Claim the change in `C:\Users\User\Desktop\secondbrain\00_Meta\002_Koordination_Live.md`
   (machine-wide: mini PC config).
2. Check whether OpenClaw `2026.7.1` offers an OpenAI-compatible chat endpoint
   (`/v1/chat/completions`) and how to enable it in `openclaw.json`.
3. Check under which identity/rights a non-WhatsApp caller runs, and that it cannot trigger sends or
   approvals. The gateway binds to loopback: decide how it is reached from the demo PC (Tailscale
   serve on the mini PC, or an SSH tunnel).
4. Record the result here. **If it fails or is unsafe:** drop `sales_ask`; the demo uses WP2's
   bridge data for Sales and chat only for Marketing (parent §8).

## 3. Tools

| Tool | Calls | Behaviour |
|---|---|---|
| `sales_ask(text)` | OpenClaw gateway chat endpoint | sync, timeout `SALES_TIMEOUT_S` (default 60) |
| `brand_ask(text)` | `POST /api/pult/marke/chat`, then poll `GET` until done | async, timeout `MARKETING_TIMEOUT_S` (default 120) |
| `content_design(content_id, text)` | `POST /api/pult/inhalte/{id}/chat`, then poll | async, same timeout; returns draft text + image URLs |

All tools return plain text for the agent; on timeout: "no answer within N s – try again or use the
Sales UI".

## 4. Configuration

`.env` (template `.env.example`): `OPENCLAW_URL`, `OPENCLAW_TOKEN`, `MARKETING_API_URL`,
`PULT_KEY`, timeouts. Secrets never logged (mask in error messages).

## 5. Safety

- No tool may call `versand_beauftragen`, approve contacts, or anything that sends.
- Sales prompt is wrapped with a fixed prefix stating read/advise-only; still verified in §2.3.

## 6. Tests (pytest)

- Polling logic with a fake Marketing API: done, still running, timeout, 401.
- Secret masking in errors.
- Live smoke test script (`agents-mcp/smoke.py`, not in CI): one call per tool.

## 7. Dependencies

None to start. Hands `mcp.json` entry to WP1.
