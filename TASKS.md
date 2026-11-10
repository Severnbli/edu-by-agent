# Tasks

Backlog for future sessions. Pick the top open task, keep work on `dev`, commit after each step, then update this file (tick the task, add what you learned to `knowledge/`). Read `CLAUDE.md` and `knowledge/README.md` first.

Before any task that talks to the site: `./edu proxy up` (direct mode; `EDU_INTERFACE` must name the uplink that is up – `wlo1` on Wi-Fi, `eno1` on cable), then `./edu session check`. If the session is expired, ask the user to run `./edu session login` (site, login and password are prefilled from `.env`; they only solve the captcha). You can also start it yourself in the background and wait for it to finish.

## 1. Capture the missing write flows (needs the user)

Ask the user to run `./edu browse --har edit-<date>` and do, on a **test section**:
- open an object (HTML block), change its text, Save (Сохранить и остаться) and Save and exit
- publish and unpublish an object
- create a news item (type 534) and fill its fields
- upload an image (type 304) and a downloadable file (type 734) – `BinaryFrame.aspx`
- move an object to trash and restore it; move an object to another section; sort objects
- copy a section, move a section; change a section's template (`fk_Template`)

Then: check the sanitized capture for leaks (no cookie values or GuidSession UUIDs from the raw file), summarize it with `./edu har summary`, and extend `knowledge/endpoints/*.md`. Done when every action in the "Not captured yet" list in `knowledge/README.md` is documented.

## 2. Read-only API layer – done 2026-11-10

`src/edu_by/api/explorer.py` (tree, sections, object list with paging, types) and `api/objects.py` (ObjectEditor read); CLI `edu tree [--root ID] [--depth N | --all]`, `edu objects <section>`, `edu object <id>`, `edu types`, all with `--json`. Progress goes to stderr (`EDU_VERBOSE=1` when not a TTY). Learned: the tree is lazy (one request per section to list it all), selecting a hidden or the current node gives `error|500|`; see `knowledge/endpoints/explorer.md`.

Follow-ups:
- [ ] Cache the section tree in `.session/tree.json` (with a timestamp) so `edu objects <id>` for a deep section needn't walk the tree each time; `--refresh` to rebuild.
- [ ] `edu objects --type` / `--search` (the list has a title/content search: `ctl00$Main_Right$SS_text`, `SS_Button`, `SS_Button2` – not captured yet).
- [ ] Trash views (`sNodeTrashe\<group>\<id+1>`) and object-type views (`sNodeTemplate…`) as object lists.

## 3. Write operations with confirmation

Only after task 1 has documented the flow. Each write command prints a dry-run of what changes and needs `--yes` (or an explicit confirmation from the user) to run:
- `edu object set-text <id> --file content.html`
- `edu object publish|unpublish <id>`
- `edu object add <section> --type 534 --title ...`
- `edu section add <parent> --title ...`
Delete and trash commands come last, and need double confirmation. Re-read the object after each write to verify it.

## 4. Skills for agents – `.claude/skills/`

One skill per task, using the CLI from tasks 2–3: `edu-browse-site` (find sections and objects), `edu-edit-content`, `edu-publish-news`, `edu-upload-file`. Each says when to use it, its inputs, exact commands, how to verify, and what to do on common errors.

## 5. MCP server

`edu mcp` exposing the api/ functions as MCP tools, reusing the same code (no duplicated logic). Write tools keep the confirmation step.

## 6. Open questions (small, any time)

- [ ] Does `IsSession` or a GET of explorer.aspx reset the ~1 h idle timer? Keep one session idle >1 h and test; then fix `session keepalive` to use the cheapest request that works.
- [ ] Does the security level change the idle timeout?
- [x] `ctl00$Main$CheckBoxStatusObject` («Разрешить публикацию»): checked = published (2026-11-10)
- [ ] Why preview requests to the public site host failed during the first capture (the site itself is reachable).
- [ ] Language variants: field names for other languages (`title_<lang>`), `ClassifierLang.aspx`.

## Done

- [x] Repo setup, Docker runtime, `./edu` wrapper, proxy modes (direct over `wlo1`, Shadowsocks), proxy only for edu.by
- [x] Session: captcha login with `.env` prefill, import, check (`IsSession`), keepalive
- [x] `browse` desktop Chromium, live HAR recording and sanitizer, `har summary`
- [x] First capture mapped: login, data model, explorer postbacks, dialogs, SystemWJG (`knowledge/`)
- [x] Security level investigated (Hight / Medium / Low), default Hight
- [x] Read-only API and CLI: tree, objects, object, types (task 2)
