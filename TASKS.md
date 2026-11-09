# Tasks

Backlog for future sessions. Pick the top open task, keep work on `dev`, commit after each step, then update this file (tick the task, add what you learned to `knowledge/`). Read `CLAUDE.md` and `knowledge/README.md` first.

Before any task that talks to the site: `./edu proxy up` (direct mode), then `./edu session check`. If the session is expired, ask the user to run `./edu session login` (site, login and password are prefilled from `.env`; they only solve the captcha). You can also start it yourself in the background and wait for it to finish.

## 1. Capture the missing write flows (needs the user)

Ask the user to run `./edu browse --har edit-<date>` and do, on a **test section**:
- open an object (HTML block), change its text, Save (Сохранить и остаться) and Save and exit
- publish and unpublish an object
- create a news item (type 534) and fill its fields
- upload an image (type 304) and a downloadable file (type 734) – `BinaryFrame.aspx`
- move an object to trash and restore it; move an object to another section; sort objects
- copy a section, move a section; change a section's template (`fk_Template`)

Then: check the sanitized capture for leaks (no cookie values or GuidSession UUIDs from the raw file), summarize it with `./edu har summary`, and extend `knowledge/endpoints/*.md`. Done when every action in the "Not captured yet" list in `knowledge/README.md` is documented.

## 2. Read-only API layer – `src/edu_by/api/`

Build on `edu_by.webforms.WebFormPage`. Never write.
- `tree.py`: list sections as `{id, title, parent_id, path}` from explorer.aspx (`sNodeClassifier\...` links)
- `objects.py`: list objects of a section (select the node via async postback, parse `#ListElements` rows: id, type label, title, published)
- `object.py`: read one object via `G_Data/ObjectEditor.aspx?guid=` (name, text, dop, tags, status, languages)
- `types.py`: object types from `G_Data/AddObject.aspx` (`gg` attributes)
- Handle the quirk: selecting the already-current node returns an `error|500|` record – select another node first.
- CLI: `edu tree`, `edu objects <section>`, `edu object <id>`, `edu types` (JSON output with `--json`)
- Tests: parse saved HTML fixtures. Fixtures must be built from sanitized captures, with personal data replaced.
Done when the commands work against the live site and their tests pass.

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
- [ ] `ctl00$Main$CheckBoxStatusObject` – which state means published?
- [ ] Why preview requests to the public site host failed during the first capture (the site itself is reachable).
- [ ] Language variants: field names for other languages (`title_<lang>`), `ClassifierLang.aspx`.

## Done

- [x] Repo setup, Docker runtime, `./edu` wrapper, proxy modes (direct over `wlo1`, Shadowsocks), proxy only for edu.by
- [x] Session: captcha login with `.env` prefill, import, check (`IsSession`), keepalive
- [x] `browse` desktop Chromium, live HAR recording and sanitizer, `har summary`
- [x] First capture mapped: login, data model, explorer postbacks, dialogs, SystemWJG (`knowledge/`)
- [x] Security level investigated (Hight / Medium / Low), default Hight
