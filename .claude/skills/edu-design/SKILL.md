---
name: edu-design
description: Change the look of an edu.by school site through the constructor's design area – page templates, modules (menus, breadcrumbs, news lists, language switcher), style sets (CSS), scripts and resource strings – safely, on copies, with a backup and a rollback. Use when the user wants to restyle the site, change the header, footer or menu markup, add CSS or JS, switch page templates, or back up / restore the design.
---

# Site design

Everything here is **site-wide**: a saved template, module, style set or string changes every page that uses it at once. There is no draft. Details: `knowledge/endpoints/design.md`.

## Rules

- **Back up first**: `./edu design export .session/design/export-<date>/design.zip` (read-only, asks the server for the full design archive). The server's export fails now and then (`server error 500`, cause unknown) – retry later or export by hand in the constructor (Утилиты → Экспорт в архив); don't hammer it.
- **Work on copies**, never on live items: copy with a «Редизайн <year>. …» name, change the copy, test it on a hidden section, switch last.
- Show every preview to the user and apply only after their OK (`--yes`; deletes need `--token`).
- Deletes are immediate, no trash. The tool deletes only «Редизайн…» / «Тест…» items unless `--force`; use `--force` only for an item the user named.
- New CSS must not apply in the low-vision mode: scope it under `html:not(.special)` (the mode adds class `special` to `<html>` and its own `!important` colours). A `<style>` in an HTML block is page-wide – scope it under a wrapper class.
- Web fonts can't be uploaded: use an external host (`@import` in a style set) or system fonts.
- A module copy must keep «Язык: Русский» (`CheckBoxListAccess$0=on`) – without it the module renders nothing. `design copy` carries it over; check with `design show`.
- When a copy gets new markup, look at its `Text_Before` / `Text_After` too: leftovers of the old wrapper (`</div></div>`) break the page layout.

## Read

```bash
./edu design list Master            # also Head, Normal, 404, NotUseTemplate, Actual, Old, NotUse,
                                    # CssPacked, JavaScript, ResourceString, TemplateGlobal
./edu design show template 1164     # master, attached JS / CSS (in load order), body parts,
                                    # lists: ClassifierL = sections using it (1001 = whole site)
./edu design show control 2601      # module settings: Text_Before/After, ASD_* markup, section lists
./edu design show css 1212 --full   # name, body; also js, string (resource string <{id}>)
```

Field names shown in `[brackets]` are what `design set --set` takes. Templates: `title`, `master` (Главный / Обычный / 404 only), `head`, `body` (masters), `body1`…`body4` (master placeholders). Modules: `title`, `Text_Before`, `Text_After`, `ASD_<setting>` (e.g. `ASD_m_a`, `ASD_m_ItemStart`, news lists `ASD_Format$TextBoxXslt`); checkboxes (`ASD_page_Use`, `ASD_D_Parent`, …) take `on` / `off`. Style sets / scripts: `name`, `body`. Strings: `title`, `text`.

## Change (on a copy)

```bash
./edu design add css --name "Редизайн 2026. Основной" --body @.session/design/new.css   # preview, then --yes → new_id
./edu design copy template 1144 --name "Редизайн 2026. Мастер"                           # --yes → new_id
./edu design set template <copy> --attach-css <css id> --yes        # attached last = loads last
./edu design set template <copy> --set body=@.session/design/master-body.html --yes
./edu design copy template 1164 --name "Редизайн 2026. Обычный" --yes
./edu design set template <normal copy> --set master=<master copy> --yes
./edu design copy control 2601 --name "Редизайн 2026. Главное меню" --yes
./edu design set control <copy> --set 'ASD_m_ItemStart=<li class="nav__item [[class]]">' --yes
./edu cache clear --yes                                             # public pages rebuilt from the new state
```

Module calls in template bodies are `LoadModule(<id>,<title>)`; point them at the module copies. Resource strings appear as `<{id}>`.

## Test before switching

Give a hidden test section the copied template: `./edu section set 1011/<test section> --template <normal copy> --yes`, clear the cache and look at the public page (desktop and 375 px, the low-vision modes). Show the user.

## Switch and roll back

Switch only after the user's OK, one write at a time, e.g. point the live Главный / Обычный / 404 templates at the new master (`--set master=…`) or attach the new style set to the live master. Write the rollback down **before** switching: the reverse `design set` commands (old master id, `--detach-css`), and as the last resort the archive from the backup (constructor «Утилиты» → «Импорт из архива», by hand). Clear the cache after each step.

## Verify

Every write re-reads the item: `Applied and verified.` with the new values. A template save is checked ignoring whitespace (the server re-spaces `LoadModule` calls). If verified is false, `design show` the item and tell the user.

## Common errors

- `has no field(s) …; fields: …` – use a name from the list (they differ per module type).
- `the CSS / JS lists are not on the page – refusing` – the template page changed or the session expired; don't save it by other means (it would detach all styles).
- `section lists … can't be set here yet` – module section lists (`ASD_ClassifierList`, …) and a template's sections (`ClassifierL`) are kept as they are; give a section its template with `edu section set … --template`.
- `its section list (ClassifierL) is not on the page – refusing` – never save that template another way: an empty list detaches every section using it (the whole site for the live Обычный template).
- `verified: false` with `lists` before / after – a section list changed on save: `design show` the item and tell the user at once.
- `refusing without force` – not a redesign / test item; ask the user before `--force`.
- `Session expired` (exit 2) – the user runs `./edu session login`.
