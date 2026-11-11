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

## 5a. Site design refresh

The plan and status of one school's redesign are site data and live in the git-ignored `.session/notes/` (see CLAUDE.md «Site data»). Constructor-side work:
- [x] design tools: `edu design list|show|set|copy|add|delete|export`, `edu cache clear`, MCP `edu_design_*`, skill `edu-design` (2026-11-11)
- [x] a template save keeps its sections (`ClassifierL`), module «Язык» boxes, module checkboxes (2026-11-11)
- [ ] module section lists (`ASD_ClassifierList`, …) are kept, not settable
- [ ] consider applying a redesign through «Импорт из архива» (new prefixed items) – needs a test on a copy
- [ ] find how the home page picks one of several «Главный» templates

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
