# MCP server – design (task 5)

What `edu mcp` must be, so the implementation is mechanical. Everything it calls already exists in `edu_by.site` and `edu_by.api`; the server adds **no request logic** (CLAUDE.md).

## Ready (2026-11-10)

| Piece | Where | State |
|---|---|---|
| MCP SDK | `mcp>=1.9,<2` in `pyproject.toml`; 1.30.0 in the image | `from mcp.server.fastmcp import FastMCP` works |
| stdio through Docker | `./edu` without a TTY runs `docker compose run --rm -T` | verified: stdin reaches the container, stdout carries only the program's output (compose messages go to stderr). A throwaway FastMCP server answered `initialize` and `tools/call` this way |
| Shared runtime | `edu_by.site.Site` | settings, httpx client, session check, explorer page, section path cache, `lock` |
| Reads | `api/explorer.py`, `api/objects.py`, `api/sections.read_section`, `api/trash.list_trash` | used by the CLI, live-tested |
| Planned writes | `api/changes.py` + `api/objects_write.py`, `api/sections.py`, `api/trash.py` | previews live-tested read-only; **apply not yet tested on the live site** (needs the owner's go-ahead, see TASKS.md task 3) |
| Request fakes for tests | `tests/test_write.py` (`httpx.MockTransport`, `fake_site`) | reuse for server tests |

## Shape

- Module `src/edu_by/mcp_server.py`, CLI command `edu mcp` (stdio). Built with `FastMCP("edu-by")`.
- Registered for Claude Code in a project `.mcp.json`:
  ```json
  {"mcpServers": {"edu-by": {"command": "./edu", "args": ["mcp"]}}}
  ```
  Uses the same `.env`, `.session/` and proxy as the CLI. `./edu proxy up` must be running.
- **stdout is the protocol.** Nothing may print to stdout: progress (`Site.on_request`) and logs go to stderr. Never log cookies, `GuidSession`, `EDU_PASSWORD` or `ss://` links; mask as `config.mask` does.
- One `Site` per server process, created on the first tool call (not at start-up, so the server starts even with an expired session). Hold `site.lock` for the whole tool call: the constructor keeps **one UI state per session** (current section, list page), so tool calls must not interleave. Run the sync api code with `anyio.to_thread.run_sync` so the event loop keeps answering pings.
- On `ExplorerError` / `RuntimeError` from a half-done postback: `site.reset_explorer()` so the next call reloads explorer.aspx.

## Session

- `SessionExpired` → tool error: «Session expired. Ask the user to run `./edu session login` (they solve the captcha), then retry.» The server never tries to log in, and never touches the captcha.
- `edu_session_status` tool: `IsSession` result plus the masked cookie tail, so an agent can check before a batch of work.
- Keepalive is not the server's job (`./edu session keepalive` in a terminal); an idle server just reports expiry.

## Tools

Names prefixed `edu_`. Inputs are plain JSON types; section arguments accept an ID or an ID path (`1001/1041`). Every result is a JSON object.

Read tools (annotations `readOnlyHint: true`):

| Tool | Calls | Notes |
|---|---|---|
| `edu_session_status` | `session.check` | |
| `edu_tree(root?, depth=1)` | `Explorer.find_section`, `walk` | cap `depth` (e.g. ≤ 3) – each level costs one request per section; say so in the description |
| `edu_find_section(section)` | `Explorer.find_section` | returns id, title, path; uses the path cache |
| `edu_section(section)` | `sections.read_section` | title, name, protection, template, redirect |
| `edu_objects(section)` | `Explorer.objects` | all pages |
| `edu_object(id)` | `objects.read_object` + `objects_write.editable_fields` | full HTML; the list of fields an update may set |
| `edu_types` | `types_from_tree` | |
| `edu_trash_list(type_id, page=0)` | `trash.list_trash` | |

Write tools – one per planned write, all with the same contract:

| Tool | Plan function | Level |
|---|---|---|
| `edu_object_update(id, values?, published?)` | `objects_write.plan_update` | edit / publish |
| `edu_object_create(section, type_id, count=1, values?)` | `plan_create` | edit |
| `edu_object_copy(id)` | `plan_copy` | edit |
| `edu_object_move(ids, target_section)` | `plan_move` | edit / publish |
| `edu_object_sort(section, order)` | `plan_sort` | publish |
| `edu_object_upload_image(id, path)` | `plan_upload_image` | edit / publish – `path` must be inside the repo (bind mount); refuse others |
| `edu_object_trash(ids)` | `plan_trash` | delete |
| `edu_section_add(parent, title, protected=true)` | `sections.plan_add` | publish |
| `edu_section_update(section, title?, name?, protected?, tags?)` | `sections.plan_update` | edit / publish |
| `edu_section_move(section, target, position)` | `sections.plan_move` | publish |
| `edu_section_delete(section)` | `sections.plan_delete` | delete |
| `edu_trash_restore(type_id, ids, section)` | `trash.plan_restore` | edit |
| `edu_trash_purge(type_id, ids)` | `trash.plan_purge` | delete, irreversible |

**Contract** (the confirmation step of CLAUDE.md, same as the CLI's `--token`):

1. Called **without** `confirm_token`: the tool plans and returns `Change.preview()` – action, target, level, before/after per field, notes, `token` – and changes nothing. The description tells the agent to show this preview to the user and ask.
2. Called **with** `confirm_token`: the tool plans again and calls `change.apply(confirm_token)`. A changed site or a different request gives a new token → `TokenMismatch` → error «preview again». Returns `{"plan": preview, "result": result}`; `result.verified` is the re-read check.
3. A `noop` plan returns the preview with `noop: true` and is never applied.

Annotations: `destructiveHint: true` for delete-level tools, `idempotentHint: false` for all writes, `openWorldHint: true` (live public site). Leave write tools on "ask" in Claude Code permissions; read tools may be allowed.

Not exposed: page templates (`Templates.aspx` saves rewrite the site-wide template), design import, security/permissions, «select all» in the trash, login.

## Resources (optional)

`knowledge/*.md` as resources (`edu://knowledge/<file>`), so an agent without the repo can read the constructor facts: documents are links, images ≤ 300 000 B, every save posts all fields.

## Tests

- In-memory MCP client (`mcp.shared.memory.create_connected_server_and_client_session`) against the server with a `fake_site` from `tests/test_write.py`: tool list and annotations, a preview, an apply with the right token, a refused wrong token, `SessionExpired` mapped to a tool error.
- Live smoke test with the owner's consent, on a test section under «Служебный» (1011), deleted afterwards.
