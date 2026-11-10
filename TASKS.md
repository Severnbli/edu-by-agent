# Tasks

Backlog for future sessions. Pick the top open task, keep work on `dev`, commit after each step, then update this file (tick the task, add what you learned to `knowledge/`). Read `CLAUDE.md` and `knowledge/README.md` first.

Before any task that talks to the site: `./edu proxy up` (direct mode; `EDU_INTERFACE` must name the uplink that is up – `wlo1` on Wi-Fi, `eno1` on cable), then `./edu session check`. If the session is expired, ask the user to run `./edu session login` (site, login and password are prefilled from `.env`; they only solve the captcha). You can also start it yourself in the background and wait for it to finish.

## 1. Capture the write flows – mostly done 2026-11-10

Capture `edit-2026-11-10` documented in `knowledge/endpoints/dialogs.md` and `explorer.md`: section add / rename / protection / move (ClassifierMove: above, inside, below) / delete, object create (`N_Count`, new ids in `Result_Value_1`), object save (Save, SaveExit; news and image fields), copy, move to another section, sort, move to trash, ClearCache, page templates.

Still missing – record a short second capture (`./edu browse --har edit2-<date>`) on a test section:
- [x] publish and unpublish (capture publish-2026-11-10)
- [x] image upload: tested by direct POSTs, limit ≈ 300 000 bytes, rejected files give no error (dialogs.md). Test section 59791 «Тест загрузки картинок (удалить)» under 1011 holds the test objects – delete it when done
- [ ] document upload (type 734) and its limit
- [ ] open «Корзина объектов» (trash) and restore an object (the user does trash work themselves – don't touch it without asking)
- [ ] copy a section; change a section's template (`fk_Template`)

Do **not** save page templates (G_RengerProvider/Templates.aspx) in captures: saving rewrites the site-wide template even with no edits.

## 2. Read-only API layer – done 2026-11-10

`src/edu_by/api/explorer.py` (tree, sections, object list with paging, types) and `api/objects.py` (ObjectEditor read); CLI `edu tree [--root ID] [--depth N | --all]`, `edu objects <section>`, `edu object <id>`, `edu types`, all with `--json`. Progress goes to stderr (`EDU_VERBOSE=1` when not a TTY). Learned: the tree is lazy (one request per section to list it all), selecting a hidden or the current node gives `error|500|`; see `knowledge/endpoints/explorer.md`.

Follow-ups:
- [ ] Cache the section tree in `.session/tree.json` (with a timestamp) so `edu objects <id>` for a deep section needn't walk the tree each time; `--refresh` to rebuild.
- [ ] `edu objects --type` / `--search` (the list has a title/content search: `ctl00$Main_Right$SS_text`, `SS_Button`, `SS_Button2` – not captured yet).
- [ ] Trash views (`sNodeTrashe\<group>\<id+1>`) and object-type views (`sNodeTemplate…`) as object lists.

## 3. Write operations with confirmation

Section add/rename/move, object create, save text, copy, move, sort and trash are documented; publish and image upload are verified too. Each write command prints a dry-run of what changes and needs `--yes` (or an explicit confirmation from the user) to run:
- `edu object set-text <id> --file content.html`
- `edu object publish|unpublish <id>`
- `edu object add <section> --type 534 --title ...`
- `edu section add <parent> --title ...`
Delete and trash commands come last, and need double confirmation. Re-read the object after each write to verify it.

## 4. Skills for agents – `.claude/skills/`

One skill per task, using the CLI from tasks 2–3: `edu-browse-site` (find sections and objects), `edu-edit-content`, `edu-publish-news`, `edu-upload-file`. Each says when to use it, its inputs, exact commands, how to verify, and what to do on common errors.

## 5. MCP server

`edu mcp` exposing the api/ functions as MCP tools, reusing the same code (no duplicated logic). Write tools keep the confirmation step.

## 5a. Site design refresh (in progress)

Backup of all design items (read-only): `.session/design/backup-2026-11-10/` (338 items, `index.json`). Prototype: `.session/design/prototype/` (`modern.src.css` → `build.py` → `modern.css`, screenshots, `compare.html`). Plan: add the style as **one new style set** loaded last, so rollback = detach it. Next:
- [ ] user approves the prototype (or asks for changes)
- [ ] capture with the user: create a style set and attach it to a template (CssPacked / Templates save), on a test copy if possible
- [ ] apply, ClearCache, check public pages and low-vision mode; rollback plan ready

## 6. Open questions (small, any time)

- [ ] Does `IsSession` or a GET of explorer.aspx reset the ~1 h idle timer? Keep one session idle >1 h and test; then fix `session keepalive` to use the cheapest request that works.
- [ ] Does the security level change the idle timeout?
- [x] `ctl00$Main$CheckBoxStatusObject` («Разрешить публикацию»): checked = published (2026-11-10)
- [x] Preview requests to the public host: Chromium with the PAC times out there, httpx works; route edu.by through httpx (design.md)
- [ ] Language variants: field names for other languages (`title_<lang>`), `ClassifierLang.aspx`.

## Done

- [x] Repo setup, Docker runtime, `./edu` wrapper, proxy modes (direct over `wlo1`, Shadowsocks), proxy only for edu.by
- [x] Session: captcha login with `.env` prefill, import, check (`IsSession`), keepalive
- [x] `browse` desktop Chromium, live HAR recording and sanitizer, `har summary`
- [x] First capture mapped: login, data model, explorer postbacks, dialogs, SystemWJG (`knowledge/`)
- [x] Security level investigated (Hight / Medium / Low), default Hight
- [x] Read-only API and CLI: tree, objects, object, types (task 2)
