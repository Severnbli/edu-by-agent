# Site design (MCP tools)

Everything here is **site-wide**: a saved template, module, style set or string changes every page using it at once; there is no draft. Work on copies named «Редизайн <year>. …», test on a hidden section, switch last – and only after the user's OK. Every write returns a preview first; confirm with the user, then call again with `confirm_token`.

Back up before the first change: the user runs `./edu design export .session/design/export-<date>/design.zip` (the full design archive; the server's export fails now and then – retry later).

## Read

- `edu_design_list(category)` – `Master`, `Head`, `Normal`, `404`, `NotUseTemplate` (templates), `Actual`, `Old`, `NotUse` (modules), `CssPacked`, `JavaScript`, `ResourceString`.
- `edu_design_item(kind, id)` – `kind`: `template`, `control` (module), `css`, `js`, `string`. Returns the field names `edu_design_update` takes; a template also shows its `master` and attached `js` / `css` in load order. `full=true` for whole HTML.

## Change on copies

1. `edu_design_create(kind="css", name="Редизайн 2026. Основной", body=...)` → confirm → `result.new_id`. Scope the CSS under `html:not(.special)` (low-vision mode adds `special` to `<html>`); fonts only from an external host.
2. `edu_design_copy(kind="template", id="<live master>", name="Редизайн 2026. Мастер")` → confirm → `result.new_id`. Same for the Обычный / Главный templates and the modules (menus, breadcrumbs, news) whose markup changes.
3. `edu_design_update(kind="template", id=<copy>, attach_css=[<new css>])` – attached ones go last (load after the others). `values={"master": <master copy>}` for a Обычный copy; `values={"body": ...}` for the master body (`LoadModule(<id>,<title>)` calls point at module copies).
4. `edu_design_update(kind="control", id=<module copy>, values={"ASD_m_ItemStart": "<li class=…>"})` – field names from `edu_design_item`; checkboxes take `"on"` / `"off"`. A module copy needs «Язык: Русский» (`CheckBoxListAccess$0` = `"on"`, carried over by the copy) or it renders nothing; empty leftover `Text_Before` / `Text_After` wrappers.
5. `edu_cache_clear()` → confirm.

## Test, switch, roll back

- Test: `edu_section_update(section="1011/<test section>", template=<Обычный copy>)`, clear the cache, check the public page with the user (desktop, 375 px, low-vision modes).
- Before switching write down the rollback (the reverse `edu_design_update` calls: old master id, `detach_css`); the archive import is the last resort (done by hand in the constructor).
- Switch one write at a time after the user's OK; clear the cache after each.

## Delete

`edu_design_delete(kind, id)` is immediate (no trash) and allowed only for «Редизайн…» / «Тест…» items; `force=true` only for an item the user named.

## Errors

"has no field(s)": take a name from the list in the error. "lists are not on the page – refusing": never save that template another way. "section lists … can't be set": leave module section lists and template sections as they are (a section's template is set with `edu_section_update`). "section list (ClassifierL) is not on the page – refusing": never save that template another way – an empty list detaches every section using it. "refusing without force": ask the user. "Session expired": the user runs `./edu session login`.
