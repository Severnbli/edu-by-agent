# Tasks

Backlog for future sessions. Pick the top open task, keep work on `dev`, commit after each step, then update this file (tick the task, add what you learned to `knowledge/`). Read `CLAUDE.md` and `knowledge/README.md` first.

Before any task that talks to the site: `./edu proxy up` (direct mode; `EDU_INTERFACE` must name the uplink that is up – `wlo1` on Wi-Fi, `eno1` on cable), then `./edu session check`. If the session is expired, ask the user to run `./edu session login` (site, login and password are prefilled from `.env`; they only solve the captcha). You can also start it yourself in the background and wait for it to finish.

## 1. Capture the write flows – mostly done 2026-11-10

Capture `edit-2026-11-10` documented in `knowledge/endpoints/dialogs.md` and `explorer.md`: section add / rename / protection / move (ClassifierMove: above, inside, below) / delete, object create (`N_Count`, new ids in `Result_Value_1`), object save (Save, SaveExit; news and image fields), copy, move to another section, sort, move to trash, ClearCache, page templates.

Still missing – record a short second capture (`./edu browse --har edit2-<date>`) on a test section:
- [x] publish and unpublish (capture publish-2026-11-10)
- [x] image upload: tested by direct POSTs, limit ≈ 300 000 bytes, rejected files give no error (dialogs.md). Test section 59791 «Тест загрузки картинок (удалить)» under 1011 holds the test objects – delete it when done
- [x] document upload (type 734): documents are not stored on the site – 734 / 594 are cards with a Yandex.Disk link (`format`, `size`, `url`); only images (≤ 300 KB) upload
- [x] trash view, restore and permanent delete (verified on own test objects; the user allowed it 2026-11-10). Test section 59791 and its objects are deleted and purged
- [ ] copy a section; change a section's template (`fk_Template`)

Do **not** save page templates (G_RengerProvider/Templates.aspx) in captures: saving rewrites the site-wide template even with no edits.

## 2. Read-only API layer – done 2026-11-10

`src/edu_by/api/explorer.py` (tree, sections, object list with paging, types) and `api/objects.py` (ObjectEditor read); CLI `edu tree [--root ID] [--depth N | --all]`, `edu objects <section>`, `edu object <id>`, `edu types`, all with `--json`. Progress goes to stderr (`EDU_VERBOSE=1` when not a TTY). Learned: the tree is lazy (one request per section to list it all), selecting a hidden or the current node gives `error|500|`; see `knowledge/endpoints/explorer.md`.

Follow-ups:
- [x] Section path cache `.session/tree-<site>.json` (`api/treecache.py`): every explorer command adds what it saw; a cached bare ID costs one request per ancestor; a stale path falls back to the walk and is dropped.
- [ ] Seed the cache fast from the public «Карта сайта» (`/ru/main.aspx?guid=1091` on the public host: nested `<ul class="level_N">`, one GET ~1.3 s, published sections only – hidden ones such as «Служебный» still need the walk). The admin tree has no lightweight child callback (each selection re-renders the ~110 KB tree panel).
- [ ] `edu objects --type` / `--search` (the list has a title/content search: `ctl00$Main_Right$SS_text`, `SS_Button`, `SS_Button2` – not captured yet).
- [ ] Trash views (`sNodeTrashe\<group>\<id+1>`) and object-type views (`sNodeTemplate…`) as object lists.

## 3. Write operations with confirmation – done 2026-11-10

Planned writes in `api/` (`changes.Change`: plan reads only, returns before/after, level and a token; `apply()` writes and re-reads) and CLI commands: `edu object set|publish|unpublish|add|copy|move|sort|upload|trash`, `edu section add|set|move|delete`, `edu trash restore|purge` (+ reads `object show`, `section show`, `trash list`). Preview by default, `--yes` applies, delete level needs `--token` from the preview. Unit tests on a fake constructor (`tests/test_write.py`).

- [x] **Live test of apply** (2026-11-10, owner's go-ahead): test section 59801 «Тест инструментов (удалить)» under 1011 with subsections 59811 / 59821 – every command applied and verified, then sections deleted and the 3 test objects purged. News test in 59831 «Тест новости (удалить)»: 534 with `dt_text`, `zag`, `name`, `txt`, picture upload, date change – verified, then deleted and purged.
- [x] Fixed on the way: a text that is one bare `<p>…</p>` is stored without the tags (the check now accepts it); `object show` prints all editable field values; `objects --pages N`; `object upload --shrink` (Pillow).
- [x] Confirmed: ClassifierMove buttons (checked by the new parent), `IsDelClassifier` counts, the news date `dt_text` without touching its `_ClientState`, `object copy` id by list diff (ids are reused: copy got 6713).
- Left in the 524 / 304 trash: empty objects 126733, 126723 and others from earlier captures – not purged (not named by the owner).

## 4. Skills for agents – done 2026-11-10

`.claude/skills/`: `edu-session`, `edu-find-content` (read), `edu-edit-content` (text, publish, objects, sections, trash), `edu-publish-news` (news with photos as unpublished 304 objects in `txt`), `edu-upload-file` (images with `--shrink`, documents as 734 link cards). To do later: a design skill once task 5a has CLI commands (style sets, ClearCache) – design writes are site-wide and not exposed yet.

## 5. MCP server – done 2026-11-10

`edu mcp` (`src/edu_by/mcp_server.py`), design and contract in [`docs/mcp.md`](docs/mcp.md): 8 read and 13 write tools (preview, then `confirm_token`), the skills' `mcp.md` as prompts, `knowledge/` as resources; `.mcp.json`; `tests/test_mcp.py`. Live-tested through a stdio client on a test section (since deleted). Fixed on the way: section move / delete with an id path, the create preview shows the field values, create reports fields that didn't save.
- [ ] Claude Code permissions: allow the read tools (`mcp__edu-by__edu_session_status`, `…edu_tree`, `…edu_find_section`, `…edu_section`, `…edu_objects`, `…edu_object`, `…edu_types`, `…edu_trash_list`) in `.claude/settings.json`, keep writes on "ask" – the owner adds them (an agent may not change its own permissions).

## 5a. Site design refresh (in progress)

Backup of all design items (read-only): `.session/design/backup-2026-11-10/` (338 items, `index.json`). Prototype: `.session/design/prototype/` (`modern.src.css` → `build.py` → `modern.css`, screenshots, `compare.html`). Plan: add the style as **one new style set** loaded last, so rollback = detach it. Next:
- [x] full design export via «Экспорт в архив» (2026-11-10, user-approved): `.session/design/export/download_-888.zip`, decoded to `decoded/` (format in design.md)
- [ ] consider applying the redesign through «Импорт из архива» (new prefixed items) instead of editing live ones – needs a test on a copy
- [ ] user approves the prototype (or asks for changes)
- [x] capture: create / copy / delete / save a style set and a script, save a module and a template with `HiddenFieldForSave` – all in design-2026-11-10 (design.md)
- [x] feasibility of the redesign prototype (2026-11-10): templates are free HTML, every module's output markup is in its settings (menus, news lists, breadcrumbs, languages – design.md «Module output markup»), so the layout is reachable; web fonts can't be uploaded (external or system font); languages are Google Translate (module 2561), not real versions
- [x] direct POST of an HTML block keeps all markup, `<style>` / `<svg>` / `<script>` included (2026-11-10, test 126743 in 59861, cleaned up; design.md)
- [x] public rendering of such a block: byte for byte, CSS / JS / web font work (test page 59871 «Тест редизайна (удалить)» under 1011 with template 1164, block 126743 – **delete after the owner's verdict**)
- [x] prototypes: ENG dropped (2026-11-10, holst v7); decide with the owner whether to keep the Google Translate switcher (РУС / БЕЛ / АНГ, module 2561) or show only РУС / БЕЛ
- [ ] CLI / MCP: plan-based writes for style sets, scripts and module settings (`Controls.aspx` `ASD_*`), template body; never post `HiddenFieldForSave` from the GET
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
- [x] `browse` desktop Chromium (saved session or prefilled login, `--login`), live HAR recording and sanitizer, `har summary`
- [x] First capture mapped: login, data model, explorer postbacks, dialogs, SystemWJG (`knowledge/`)
- [x] Security level investigated (Hight / Medium / Low), default Hight
- [x] Read-only API and CLI: tree, objects, object, types (task 2)
