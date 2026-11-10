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

Form: `ctl00$Title_1 = [<id>] Редактирование набора стилей` (editing a style set), CSS text in `ctl00$Main$TextBoxBody`. Public pages link the sets a template uses, in order: `<link href='css.aspx?guid=<id>' rel='stylesheet' data-name='<set name>'/>`. Save: see the next section (captured in design-2026-11-10).

Templates attach scripts through `ctl00$Main$HiddenFieldForSave` (`<js value="<id>"/>` list, see dialogs.md). How a template chooses its style sets is not known yet.

## Add / copy / delete style sets and scripts (verified, capture design-2026-11-10)

On the category page (`RengerProvider.aspx?guid=CssPacked&gs=…` or `?guid=JavaScript&gs=…`) a plain postback with `__EVENTTARGET` =
- `ctl00$ContentSecondMenu$CSSAdd` / `JSAdd` – create a new empty item (seen ids 1292 CSS, 1293 JS);
- `ctl00$ContentSecondMenu$CSSCopy` / `JSCopy` + `ctl00$Result_Value = <id>` – copy that item (1292 → 1302, 1293 → 1303);
- `ctl00$ContentSecondMenu$CSSDel` / `JSDel` + `ctl00$Result_Value = <id>` – delete it.

The item editor (`G_RengerProvider/CssPacked.aspx?guid=<id>`, `JavaScript.aspx?guid=<id>`) saves its text in `ctl00$Main$TextBoxBody` and name in `ctl00$Main$TextBoxName_text` with the usual `ctl00$ButtonSave` («Сохранить и остаться», save and stay) / `ButtonSaveExit`. Async postback: `ctl00$ScriptManagerDialog = ctl00$ScriptManagerDialog|ctl00$ButtonSave`, plus `ctl00$Title_1`, `ctl00$Title_2`, `ctl00$Main$TextBoxName_warning_ClientState` (empty), `ctl00$GuidSession`, empty `ctl00$Result_*`. Captured for CSS 1002 and JS 1023 (design-2026-11-10). The same capture also has saves of `Controls.aspx` (2971) and `Templates.aspx` (1064, with a filled `HiddenFieldForSave`), so every design item can be written.

## Module output markup (verified from the export and the backup, 2026-11-10)

Modules don't have fixed HTML: each one keeps its markup in its settings. `Controls.aspx` shows every setting as a field `ctl00$Main$ASD_<setting>`, plus `ctl00$Main$Text_Before` / `Text_After` (HTML around the module). The settings seen:

| Module (`fk`) | Markup settings | Placeholders |
|---|---|---|
| `WJG.Core_NavigationUniversal` (main menu 2601, section menu 2791, breadcrumbs 2801, page title 2491/2811, site map 3011) | `BlockStart`, `BlockEnd`, `m_BlockStart` / `m_BlockEnd` (per level, e.g. `<ul class="[[class]]">`), `m_ItemStart` / `m_ItemEnd`, `m_a` (link), `m_select` (current item); what it lists: `Status`, `D_Status`, `D_ClassifierList`, `D_Level` (depth), `D_Parent` | `[[url]]`, `[[title]]`, `[[class]]`, `[[guid]]` |
| `WJG.Core_MenuEasy`, `MenuEasy2` (old menus) | `ASD_LinkStyle`, `ASD_LinkSpan`, `ASD_Separator`, `ASD_ClassFirst` / `Link`, `LinkSelect`, `BlockStart`, `BlockEnd` | `[[guid]]`, `[[title]]` |
| `WJG.Core_ListObject` (lists of objects, e.g. 1021 the home HTML block, 1101 news) and `WJG.Core_ArxiwEasy` (archives, e.g. 3001 news) | `Format` – XSLT-like template of one item; `TemplateObjectList` / `TemplateObject` (object type), `ClassifierList`, paging `page_*` | `<%V(<field>)%>`, `<%WRITE(…)%>`, `<%G_OBJ%>` (object id), `WJG:FormatDate(<%V(dt)%>,'ShortDate')`, `<xsl:attribute>` |
| `WJG.Core_Lang` (2551 on this site) | `Lang_<n>` (code), `LangNo_<n>` / `LangYes_<n>` (HTML of a not-chosen / chosen language) | – |
| `WJG.Core_Way` (1071) | `BlockStart`, `Separator`, `ShowActiveClassifier` | – |
| `WJG.Core_Tab` (tabs, e.g. 2711) | `Theme`, `ThemeUser`, `Str<n>` (tab title), `GuidControl<n>` (module in the tab) | – |
| `WJG.Core_Head` (1611, «Данные в блок head») | `ASD_Str` (HTML put into `<head>`), `ASD_KeyWords` | – |

`<{<id>}>` anywhere is a resource string (Localization item) – e.g. the cookie notice text is string 1498, its show / hide logic is in JS 1273.

So a redesign can change the HTML of menus, news lists, breadcrumbs and the language switcher, not only their CSS. Template bodies (`Content<N>` in the export, `Body_Content$TextBoxRes` in the dialog) are free HTML with `LoadModule` / `<control>` references.

## Fonts and files for a design

Binaries of a design are images only (the export has gif / jpeg / png; uploads reject other types, see dialogs.md). Web fonts can't be uploaded: the platform serves only `/fonts/glyphicons/…` and `/fonts/fontawesome/…` (used by sets 1212 and 1272). A new font must come from an external host (`@import` in a style set or `<link>` in the Head module) or be replaced by a system font stack. The public site sends no `Content-Security-Policy` (header or meta; IIS 8.5, checked 2026-11-10) and `/fonts/` itself answers 403, so an external font host is not blocked. Font files inside an import archive – not tried.

## HTML in content blocks

The home block 1063 (type 524, saved through the editor) keeps `class` (`content`, `entry`, `pc`, `MsoBodyText`), `id` and 152 `style` attributes.

**Direct save keeps everything (verified 2026-11-10, user-approved test):** an unpublished 524 block created by `edu object add --set text=@file` in a temporary section 59861 under 1011 stored this markup byte for byte – `<style>`, `<svg>`/`<path>`, `<button>`, `<details>`/`<summary>`, `<section>`, `<nav>`, `<aside>`, `<table>` with `<thead>`/`scope`, `class`, `id`, `style`, `data-*`, `aria-*`, `role`, `target`/`rel`, `loading`, and even `onclick` and `<script>`. The server does not clean HTML on save (`SystemWJG.asmx/ClearHtml` is not called). Test block 126743 purged, section deleted. How the public page renders it through the list module (`Format` with `<%WRITE(<%V(text)%>)%>`) was not checked, because the block stayed unpublished. Field `dop` of HTML blocks and news is labelled for scripts and iframes.

## This site's live design (sch12, 2026-11-10)

Master 1144 «Загрузка от 25.08.2025. Основной мастер шаблон» (Главный 1154, Обычный 1164, 404 1174 use it) – CSS 1212–1282 (8 sets), JS 1203–1283 (9). Languages in module 2551: **ru and be only** (`<span>РУС</span>`, `<span>БЕЛ</span>`), no English version (`main.aspx?lang=en` and `?lang=be` return the same 141 994-byte page; the home block 1063 has only «Русский» among its languages). Adding `en` to the module is easy, but pages would be empty without translated content.

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
