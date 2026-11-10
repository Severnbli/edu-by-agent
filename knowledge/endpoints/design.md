---
status: partially verified
updated: 2026-11-10
source: capture design-2026-11-10, read-only GETs of RengerProvider.aspx and G_RengerProvider/* (2026-11-10), public pages of the site, capture edit-2026-11-10
---

# Site design (RengerProvider)

The site's look is made of page templates, modules (controls), style sets, scripts and resource strings. All are edited in the constructor under `RengerProvider.aspx`. **Everything here is site-wide** – a save changes every page at once, and there is no draft or preview.

## Category pages (read-only GET)

`GET /RengerProvider.aspx?guid=<category>&gs=<GuidSession>` (the `gs` value is the `ctl00$GuidSession` hidden field of explorer.aspx – a session secret, mask it). Categories (left tree labels verbatim):

| guid | Label | Items open in |
|---|---|---|
| `Master` | Мастер (master templates) | `Templates` |
| `Head` | Главный (home page templates) | `Templates` |
| `Normal` | Обычный (ordinary page templates) | `Templates` |
| `NotUseTemplate` | Не используемые (unused templates) | `Templates` |
| `404` | Документ не найден (404) | `Templates` |
| `Actual`, `Old`, `NotUse` | modules: current / old / unused | `Controls` |
| `TemplateGlobal` | object type templates | `TemplateGlobal` |
| `JavaScript` | scripts | `JavaScript` |
| `CssPacked` | style sets | `CssPacked` |
| `ResourceString` | resource strings | `ResourceString` |
| `Utility`, `ExportToXml` | tools – not explored |

Items are links calling `Open('<dialog>', this, '<id>')`, which opens `/G_RengerProvider/<dialog>.aspx?guid=<id>` (WebForms dialog, see dialogs.md). On the test site: 338 items (5+3+3+2+1 templates, 92 modules, 35 type templates, 25 scripts, 27 style sets, ~140 strings).

## Style sets – CssPacked.aspx?guid=<id>

Form: `ctl00$Title_1 = [<id>] Редактирование набора стилей` (editing a style set), CSS text in `ctl00$Main$TextBoxBody`. Public pages link the sets a template uses, in order: `<link href='css.aspx?guid=<id>' rel='stylesheet' data-name='<set name>'/>`. Saving a set is **not captured yet**.

Templates attach scripts through `ctl00$Main$HiddenFieldForSave` (`<js value="<id>"/>` list, see dialogs.md). How a template chooses its style sets is not known yet.

## Add / copy / delete style sets and scripts (verified, capture design-2026-11-10)

On the category page (`RengerProvider.aspx?guid=CssPacked&gs=…` or `?guid=JavaScript&gs=…`) a plain postback with `__EVENTTARGET` =
- `ctl00$ContentSecondMenu$CSSAdd` / `JSAdd` – create a new empty item (seen ids 1292 CSS, 1293 JS);
- `ctl00$ContentSecondMenu$CSSCopy` / `JSCopy` + `ctl00$Result_Value = <id>` – copy that item (1292 → 1302, 1293 → 1303);
- `ctl00$ContentSecondMenu$CSSDel` / `JSDel` + `ctl00$Result_Value = <id>` – delete it.

The item editor (`G_RengerProvider/CssPacked.aspx?guid=<id>`, `JavaScript.aspx?guid=<id>`) saves its text in `ctl00$Main$TextBoxBody` and name in `ctl00$Main$TextBoxName_text` with the usual `ctl00$ButtonSave` / `ButtonSaveExit`.

## Attaching CSS / JS to a template

`G_RengerProvider/Templates.aspx` keeps the attached sets in `ctl00$Main$HiddenFieldForSave`, e.g. `<css value="1002"/><css value="1012"/><css value="1022"/><js value="1073"/>`. **The GET returns it empty – the page's JS fills it from the list on screen before saving**, so a tool must build it from the visible list, never post the GET value (that would detach all styles). Order = load order, so a new set appended last overrides the old ones.

Same for Controls (`G_RengerProvider/Controls.aspx`): `ASD_ClassifierList` / `ListClasifier` are empty in the GET and filled by JS (`1441;` for the guestbook form 2971).

Saving a template unchanged also re-spaces `LoadModule(...)` calls (adds a space or newline between them) – harmless, but it shows up as a change.

## Low-vision mode (version for the visually impaired)

The public «Версия для слабовидящих» button switches classes on `<body>`: `colorSiteBlack`, `colorSiteWhite`, `colorSiteBlue`, `colorSiteBeige` (and others from the same script). A new design style must not apply in that mode – scope its selectors with `body:not([class*="colorSite"])`.

## Public site from the container browser

Chromium with the PAC file timed out on the public school host (the httpx client reaches it through the same proxy). Working approach: route the page's edu.by requests through the httpx client (`page.route` + `route.fulfill`) and let other hosts go direct.

## Utilities (RengerProvider.aspx?guid=Utility) – verified 2026-11-10

| Item | Dialog | What it does |
|---|---|---|
| «Экспорт в архив» (export to archive) | `G_RengerProvider/ExportToArchives.aspx` | tree of templates (Мастер / Главный / Обычный / 404) with checkboxes `ctl00_Main_TreeListn<N>CheckBox` (`title="Template"`); async postback `ctl00$ButtonSave = Экспорт`. Reply: `Result_Status = Info`, `Result_Value_1 = <a href=/sm_full.aspx?guid=-888 …>Нажмите здесь для загрузки архива</a>`; GET that URL → `application/x-zip-compressed`. **Read-only for the site; run with user approval 2026-11-10** (12 templates → 3.7 MB) |
| «Импорт из архива» (import) | `G_RengerProvider/ImportFromArchives.aspx` | `ctl00$Main$TextBoxPrefics` «Префикс имен» (default `Загрузка от <dd.mm.yyyy>.`), `ctl00$Main$TextBoxClassifier` (default `Дизайн от <date>.`, the section for imported binaries), `ctl00$Main$StatusHash`: `0` «Использовать существующие при совпадении HASH» (default), `1` «Заменять существующие…», `2` «Всегда создавать новые»; file `ctl00$Main$FileUploadArchive`, button `ctl00$AddButton$ButtonLoad` «Загрузить». **Not run.** The site's «Загрузка от 25.08.2025. …» items come from such an import |
| «Поиск пустых классификаторов» | `G_RengerProvider/Analis/ClassiferFindNull.aspx` | `ctl00$Main$RadioButtonListAccess`: `0` sections without objects, `1` sections whose objects are all unpublished or have no language; `ctl00$AddButton$ButtonFind` «Анализ». Not run |
| «Поиск больших вложений в объектах» | `G_RengerProvider/Analis/FindBigImg.aspx` | `ctl00$Main$SearchType` `all` / `img` / `non-img`; `ctl00$AddButton$ButtonAnalis` «Анализ». Not run |

Both analysers also have `ctl00$ButtonSave` «Сохранить настройки» (save settings).

### Archive format

A ZIP of one file per item, named `<id>.<Kind>`, each **UTF-16LE XML**:
- `<id>.Template` – `<Rp_Template guid title TypeTemplate=Master|Head|Normal|404 MasterPage SortId favicon dt_update>` with `<settings><root>` listing attached `<css value>`, `<js value>`, `<control value>` (the same thing `HiddenFieldForSave` edits), and `Content<N>` blocks of `<txt>` / `<control>` (the template body).
- `<id>.Css` – `<Rp_Css guid name body>`; `<id>.JS` – `<Rp_JavaScript …>`.
- `<id>.Control` – `<Rp_Controls guid fk="WJG.Core_<Module>" Title WhereUse>` with `<Settings><root><item guid value>` (module settings, e.g. `ClassifierList`).
- `<id>.Localization` – `<LanguageResource guid Status Title>` with `<lang guid="ru" value>` (resource strings).
- `<id>.Binary` – `<Binary fk BodyImage(base64) SizeImage MimeType Hash PreView(base64 jpeg)>` (images used by the design).

Everything the selected templates use is included (12 templates → 112 controls, 93 strings, 61 images, 20 CSS, 16 JS). This is a complete design backup, and the import dialog suggests a design can be **added** as a new set of prefixed items, then switched to by pointing sections / templates at it – a safer route for the redesign than editing live items (untested).
