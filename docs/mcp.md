# MCP server

`edu mcp` (`src/edu_by/mcp_server.py`, stdio): the constructor's reads and planned writes as MCP tools, the skills' scenarios as prompts, `knowledge/` as resources. Everything it calls lives in `edu_by.site` and `edu_by.api`; the server adds **no request logic** (CLAUDE.md). Live-tested 2026-11-10 (section add, object create and update, section delete, purge on a test section, since deleted).

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
| `edu_design_list(category)` | `design.list_category` | templates, modules, CSS, JS, strings of a RengerProvider category |
| `edu_design_item(kind, id, full=false)` | `design.read_item` | fields `edu_design_update` takes; template master and attached CSS / JS |

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
| `edu_section_update(section, title?, name?, protected?, tags?, template?)` | `sections.plan_update` | edit / publish |
| `edu_section_move(section, target, position)` | `sections.plan_move` | publish |
| `edu_section_delete(section)` | `sections.plan_delete` | delete |
| `edu_trash_restore(type_id, ids, section)` | `trash.plan_restore` | edit |
| `edu_trash_purge(type_id, ids)` | `trash.plan_purge` | delete, irreversible |
| `edu_design_update(kind, id, values?, attach_css?, detach_css?, attach_js?, detach_js?)` | `design.plan_set` | publish – site-wide for an item in use |
| `edu_design_copy(kind, id, name)` | `design.plan_copy` | edit – a new item, used nowhere yet |
| `edu_design_create(kind, name, body)` | `design.plan_create` | edit – css / js only |
| `edu_design_delete(kind, id, force=false)` | `design.plan_delete` | delete, immediate (no trash); «Редизайн…» / «Тест…» items only unless `force` |
| `edu_cache_clear()` | `design.plan_clear_cache` | publish, harmless |

**Contract** (the confirmation step of CLAUDE.md, same as the CLI's `--token`):

1. Called **without** `confirm_token`: the tool plans and returns `Change.preview()` – action, target, level, before/after per field, notes, `token` – and changes nothing. The description tells the agent to show this preview to the user and ask.
2. Called **with** `confirm_token`: the tool plans again and calls `change.apply(confirm_token)`. A changed site or a different request gives a new token → `TokenMismatch` → error «preview again». Returns `{"plan": preview, "result": result}`; `result.verified` is the re-read check.
3. A `noop` plan returns the preview with `noop: true` and is never applied.

Annotations: `destructiveHint: true` for delete-level tools, `idempotentHint: false` for all writes, `openWorldHint: true` (live public site). Leave write tools on "ask" in Claude Code permissions; read tools may be allowed.

Design writes (`edu_design_*`) rebuild the fields the page's JS fills before a save (template `HiddenFieldForSave` from the CSS / JS lists, module section lists) and refuse a template save when the lists can't be read. Not exposed: design export (CLI `edu design export`, a big download), design import, security/permissions, «select all» in the trash, login.

## Prompts and resources

- **Prompts** are the skills' scenarios for MCP clients: each `.claude/skills/<name>/SKILL.md` (CLI commands, for agents in this repo) has a `mcp.md` beside it with the same steps in tool calls. Prompt name = skill name with `_` (`edu_publish_news`), description from the skill, optional argument `request` (the user's ask). `tests/test_mcp.py` checks that every skill has one and that it names only existing tools and prompts – change both files together.
- **Resources**: `knowledge/**/*.md` as `edu://knowledge/<path>` (e.g. `edu://knowledge/endpoints/dialogs.md`).

## Tests

- `tests/test_mcp.py`: in-memory MCP client against the server with a `fake_site` from `tests/test_write.py` – tool list and annotations, a preview, an apply with the right token, a refused wrong token, `SessionExpired` mapped to a tool error, a file outside the repo refused, prompts and resources.
- Live: a stdio client in the container (`mcp.client.stdio`, command `edu mcp`) on a test section under «Служебный» (1011), deleted afterwards.
