---
status: partially verified
updated: 2026-11-11
source: captures design-2026-11-10 and design2-2026-11-11, read-only GETs of RengerProvider.aspx and G_RengerProvider/* (2026-11-10), public pages of the site, capture edit-2026-11-10
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

## Copy / delete templates and modules (verified, capture design2-2026-11-11)

Same pattern as style sets, on the category page (`RengerProvider.aspx?guid=Master|Head|Normal|…` for templates, `?guid=Actual|Old|NotUse` for modules): async postback with `ctl00$ScriptManagerWindow = ctl00$ScriptManagerWindow|<target>`, `__EVENTTARGET = <target>`, `ctl00$Result_Value = <id>` (the selected row), plus the left tree state (`ctl00_Main_Left_TreeList_SelectedNode`, `…_ExpandState`, `…_PopulateLog`) and `ctl00$GuidSession`. Targets on the toolbar («Создать копию» create a copy, «Удалить» delete): `ctl00$ContentSecondMenu$TemplateCopy`, `TemplateDel`, `ControlCopy`, `ControlDel` (and `TemplateAdd`, `ControlAdd` – not used yet).

- **Copy** replies `Result_Status = Copy` (templates) / `Control_Copy` (modules) and in `Result_Value` the new list row (`<tr … id='obj_<new id>'>` … `Open('Templates'|'Controls',this,'<new id>')`). The copy is named «Копия <name>» and gets the same body and the same checked CSS / JS (1134 → 1194: body and lists identical, read back 2026-11-11); a module copy keeps all settings (1211 → 3241). Take the new id from the reply, never guess it.
- **Delete** replies `Result_Status = Del`, `Result_Value = <id>`. It deletes **whatever id is posted** at once, with no trash – in this capture the original 1124 (an unused master from 2017, no template used it) was deleted instead of its fresh copy 1184 because the original row was selected. A tool must delete only an id it created itself in the same plan, and show the title first.

## Template dialog in detail (verified, capture design2-2026-11-11 and read-only GETs)

**`ClassifierL` («Классификаторы») of an Обычный template = the sections that use it** – the same list as each section's `fk_Template` (sections.md), shown from the template's side. It is a JS-filled list like the module ones: empty in the GET, `T_Init('ClassifierL');T_Add('ClassifierL','1001','Главная страница/')` in the startup script (live 1164 lists only `1001`, the root; the other sections inherit it). **A save that posts it empty detaches every listed section** – their `fk_Template` becomes `0` (inherit) and the template drops into «NotUseTemplate». Seen live 2026-11-11: a `--detach-js` save of copy 1234 reset test section 59871 from 1234 to `0`; with an inherited template the page rendered an empty `<form>` (5 KB, no head, no CSS). Rebuilt from `T_Add` and posted back, two further saves of 1234 kept 59871 (`design.py` refuses a template save when the field is there but the list isn't). Главный 1154 and 404 1174 have no such field.

`G_RengerProvider/Templates.aspx?guid=<id>` fields differ by type:
- **Master** (1004, 1144): `ctl00$Main$TypeDocument` (`0` seen), `ctl00$Main$Head_Content$TextBoxRes` (HTML for `<head>`), `ctl00$Main$Body_Content$TextBoxRes` (page body). No master select.
- **Главный / Обычный / 404** (1164): `ctl00$Main$MasterList` – select of the master templates (`<option selected="selected" value="1144">`), `ctl00$Main$ClassifierL` («Классификаторы», see below), and one body per master placeholder: `ctl00$Main$Body_Content_1..4$TextBoxRes`. Saving a different `MasterList` value works as a plain field (live test 2026-11-11: copy 1204 of 1024, `MasterList` 1004 → 1194 with `ButtonSave`, re-read shows 1194, CSS / JS lists unchanged, bodies differ only by the `LoadModule` re-spacing; copy deleted).
- Module calls in the bodies appear as `<{<id>,<title>}>` and `LoadModule(<id>,<title>)`; the export stores them as `<control>`.

**Attached CSS / JS are readable from the GET.** The dialog lists *every* script and style set as sortable lists: `<div id="ctl00_Main_ListJS" class="SortList">` and `…_ListCss`, items `<div gg='<id>'><input type='checkbox' checked='checked'>name</div>`. On save the page's JS walks `#ListJS>div`, then `#ListCss>div`, and for each checked item appends `<js value="<id>"/>` / `<css value="<id>"/>` to `HiddenFieldForSave` – so the value = checked JS in list order, then checked CSS in list order. Checked items read this way match the export's `<settings>` exactly (1134, 1144, 1164, 2026-11-11). A tool builds the field the same way (plus its change); the hidden input itself is empty in the GET – never post that.

Saving unchanged («Сохранить и выйти» on 1004) re-posted the same body and list (compared with the export) – a no-op except the `LoadModule` spacing noted below.

The module dialog (`Controls.aspx`) save posts `TextBoxTitle_text`, `WhereUse`, `ListClasifier`, `ListClasifierNotUse`, `Text_Before`, `Text_After` and the module's `ASD_*` fields (for `WJG.Core_MenuEasy2`: `ASD_ViewType`, `ASD_ClassifierList`, `ASD_ClassifierNotUse`, `ASD_Link`, `ASD_LinkSelect`). After a module copy the browser also GETs `G_RengerProvider/SIC.aspx?guid=<module type>` (e.g. `WJG.Core_MenuEasy2`) – not analysed.

## Resource strings – ResourceString.aspx?guid=<id> (live test 2026-11-11)

Category page `RengerProvider.aspx?guid=ResourceString` has toolbar targets `ctl00$ContentSecondMenu$MyButtonAddResource` «Создать новый», `MyButtonCopyResource` «Создать копию», `MyButtonDelResource` «Удалить» – same postback as templates (`ctl00$Result_Value = <id>`); copy replies `Result_Status = Copy` with `Open('ResourceString',this,'<new id>')`, delete `Del`. The dialog `G_RengerProvider/ResourceString.aspx?guid=<id>` has `ctl00$Main$S_Title_text` (name) and one textarea per language – on this site only `ctl00$Main$ctl00` (ru); saved with `ctl00$ButtonSave` → `Result_Status = Save`. Test: copy 1498 → 2158, name and text saved and re-read (the textarea value comes back with a leading newline), copy deleted. Strings are used as `<{<id>}>` in templates and modules.

## Module output markup (verified from the export and the backup, 2026-11-10)

Modules don't have fixed HTML: each one keeps its markup in its settings. `Controls.aspx` shows every setting as a field `ctl00$Main$ASD_<setting>`, plus `ctl00$Main$Text_Before` / `Text_After` (HTML around the module). The settings seen:

| Module (`fk`) | Markup settings | Placeholders |
|---|---|---|
| `WJG.Core_NavigationUniversal` (main menu 2601, section menu 2791, breadcrumbs 2801, page title 2491/2811, site map 3011) | `BlockStart`, `BlockEnd`, `m_BlockStart` / `m_BlockEnd` (per level, e.g. `<ul class="[[class]]">`), `m_ItemStart` / `m_ItemEnd`, `m_a` (link), `m_select` (current item); what it lists: `Status`, `D_Status`, `D_ClassifierList`, `D_Level` (depth), `D_Parent` | `[[url]]`, `[[title]]`, `[[class]]`, `[[guid]]` |
| `WJG.Core_MenuEasy`, `MenuEasy2` (old menus) | `ASD_LinkStyle`, `ASD_LinkSpan`, `ASD_Separator`, `ASD_ClassFirst` / `Link`, `LinkSelect`, `BlockStart`, `BlockEnd` | `[[guid]]`, `[[title]]` |
| `WJG.Core_ListObject` (lists of objects, e.g. 1021 the home HTML block, 1101 news) and `WJG.Core_ArxiwEasy` (archives, e.g. 3001 news) | `Format` – XSLT-like template of one item; `TemplateObjectList` / `TemplateObject` (object type), `ClassifierList`, paging `page_*` | `<%V(<field>)%>`, `<%WRITE(…)%>`, `<%G_OBJ%>` (object id), `WJG:FormatDate(<%V(dt)%>,'ShortDate')`, `<xsl:attribute>` |
| `WJG.Core_Lang` (2551 on this site, not used – `WhereUse=0`) | `Lang_<n>` (code), `LangNo_<n>` / `LangYes_<n>` (HTML of a not-chosen / chosen language) | – |
| `WJG.Core_Way` (1071) | `BlockStart`, `Separator`, `ShowActiveClassifier` | – |
| `WJG.Core_Tab` (tabs, e.g. 2711) | `Theme`, `ThemeUser`, `Str<n>` (tab title), `GuidControl<n>` (module in the tab) | – |
| `WJG.Core_Head` (1611, «Данные в блок head») | `ASD_Str` (HTML put into `<head>`), `ASD_KeyWords` | – |

`<{<id>}>` anywhere is a resource string (Localization item) – e.g. the cookie notice text is string 1498, its show / hide logic is in JS 1273.

`[[class]]` in `WJG.Core_NavigationUniversal` (seen on the public pages, 2026-11-11): on `m_BlockStart` it is `level_<n>` plus ` parent_active` when the list holds the current section; on `m_ItemStart` it is `parent` (has children), `active` (the current section, which is rendered with `m_select` instead of `m_a`), `parent_active` (an ancestor of it), combined (`active parent`, `parent_active parent`) or empty. Section menu 2791 («Начальный уровень» `ASD_D_Status`: `0` «От текущего», `1` «Путь к текущему», `2` «Потомки») with `0` lists the current section's children, so on a leaf page it outputs an empty `<ul>`. With `ASD_D_Parent` («Вывод родителя / текущего») on, a leaf page lists the current section with its siblings instead (live, copy 3271, 2026-11-11).

**«Язык:» boxes (`CheckBoxListAccess$<n>`, `$0` = Русский) decide on which language versions a module renders.** A module copy («Создать копию») comes with all of them unchecked, and such a module outputs nothing on `/ru/` pages – not even `Text_Before` (copies 3261–3311, 2026-11-11; fixed by checking `$0`). The tool's copy carries over the source's boxes.

A module copy keeps its source's `Text_Before` / `Text_After`: when the markup changes, empty them too – the section menu 2791 ends with `</div></div>` (closing its own wrapper), which in copy 3271 closed the new layout early and put the footer outside `.r26`.

**Tag filter of `WJG.Core_ListObject`** (dialog labels «Теги – Статус: Отключено / Включено (И) / Включено (ИЛИ)», «Список:»): radio `ASD_TagStatus` = `0` / `1` / `2`, text `ASD_TagText` (e.g. 2641 «Популярные разделы» has `1` + `популярный`). An object matches by its `Tags` field. This lets several copies of one list module show different objects of the same section: live test 2026-11-13 – three copies of the HTML-block module 2821 (`ASD_ViewType = NowClassifier`, «the current section») with one tag each rendered their own tagged 524 blocks in three places of one template body; `design set` sets both fields as plain values. Items come out in the section's sort order, and new objects are created at the top of it, so set the order with `object sort` after creating them.

`sm.aspx?guid=<object>` of an object without its own binary (e.g. a news item whose photos are only inside `txt`) answers `302` to `/SystemText/NotBinary.png` – a list module that uses it as a thumbnail shows that placeholder (live 2026-11-13). The placeholder is a 1×1 PNG, so a page script can spot it (`img.naturalWidth <= 1`). `sm.aspx` serves the object's own picture at full size (no thumbnail). Uploading a picture into the news object itself (`edu object upload <news id> FILE --shrink`) gives it a cover in every list at once (live 2026-11-13, 10 news).

After `ClearCache` a public `css.aspx?guid=<set>` may still answer with the old body for a short while (seen 2026-11-13: one page load right after the clear got the old set, the next ones the new) – reload before judging a CSS change.

So a redesign can change the HTML of menus, news lists, breadcrumbs and the language switcher, not only their CSS. Template bodies (`Content<N>` in the export, `Body_Content$TextBoxRes` in the dialog) are free HTML with `LoadModule` / `<control>` references.

## Fonts and files for a design

Binaries of a design are images only (the export has gif / jpeg / png; uploads reject other types, see dialogs.md). Web fonts can't be uploaded: the platform serves only `/fonts/glyphicons/…` and `/fonts/fontawesome/…` (used by sets 1212 and 1272). A new font must come from an external host (`@import` in a style set or `<link>` in the Head module) or be replaced by a system font stack. The public site sends no `Content-Security-Policy` (header or meta; IIS 8.5, checked 2026-11-10) and `/fonts/` itself answers 403, so an external font host is not blocked. Font files inside an import archive – not tried.

## HTML in content blocks

The home block 1063 (type 524, saved through the editor) keeps `class` (`content`, `entry`, `pc`, `MsoBodyText`), `id` and 152 `style` attributes.

**Direct save keeps everything (verified 2026-11-10, user-approved test):** an unpublished 524 block created by `edu object add --set text=@file` in a temporary section 59861 under 1011 stored this markup byte for byte – `<style>`, `<svg>`/`<path>`, `<button>`, `<details>`/`<summary>`, `<section>`, `<nav>`, `<aside>`, `<table>` with `<thead>`/`scope`, `class`, `id`, `style`, `data-*`, `aria-*`, `role`, `target`/`rel`, `loading`, and even `onclick` and `<script>`. The server does not clean HTML on save (`SystemWJG.asmx/ClearHtml` is not called). Test block 126743 purged, section deleted. **Public rendering verified the same day:** a published block in section 59871 is output byte for byte inside `<div class="html_block post">` (the list module's `Format`); in Chromium its `<style>` applies, the `<script>` runs, `<details>` and `<button>` work, and Golos Text loads from Google Fonts. A `<style>` in a block is page-wide, so scope it under a wrapper class.

**Sections under 1011 «Служебный» have no page template** (`fk_Template` option `0` reads «-- Шаблон по умолчанию --», not «по иерархии (…)»): their public page is a 3.6 KB shell without content. To show such a section publicly, set its template (`edu section set <path> --template 1164`) – it then renders with the site's look but is in no menu (menus list 1001). Field `dop` of HTML blocks and news is labelled for scripts and iframes.

## Languages on a typical site

The РУС / БЕЛ / АНГ switcher seen on sites is often **Google Translate** in an HTML module (`WJG.Core_Html`, «Google translate -при активации отключить модуль Список языков») in the master, not the constructor's language versions (the language module itself unused, `WhereUse=0`). Then БЕЛ and АНГ are machine translations of the Russian pages: `main.aspx?lang=be` returns the same page. Real language versions need translated content in the constructor.

## Attaching CSS / JS to a template

`G_RengerProvider/Templates.aspx` keeps the attached sets in `ctl00$Main$HiddenFieldForSave`, e.g. `<css value="1002"/><css value="1012"/><css value="1022"/><js value="1073"/>`. **The GET returns it empty – the page's JS fills it from the list on screen before saving**, so a tool must build it from the visible list, never post the GET value (that would detach all styles). Order = load order, so a new set appended last overrides the old ones.

Same for Controls (`G_RengerProvider/Controls.aspx`): `ASD_ClassifierList` / `ListClasifier` are empty in the GET and filled by JS (`1441;` for the guestbook form 2971). **Where JS takes them from (verified 2026-11-11):** the startup script calls `T_Init('<field>')` for every such list and `T_Add('<field>','<section id>','<path title>')` per section, e.g. `T_Add('ASD_ClassifierNotUse','1011','Служебный/')`; the posted value is `<id>;` per call (`1011;`). Rebuilt this way, the 3241 and 2971 saves match the browser's posts field for field. Checkboxes in module dialogs (`ASD_page_Use`, `ASD_D_Parent` «Вывод родителя / текущего», `ASD_IsShowWhenNo`, `ASD_TemplateObject$<type>`, …) post `on` when checked and are left out when not, like any form; the tool lists unchecked ones too (value empty) and drops a box it turns off. Textareas in all these dialogs start with a newline in the HTML that a browser drops – `parse_form` drops it too (2026-11-11), otherwise every save would "change" the text.

Tools: `edu_by.api.design` (CLI `edu design …`, `edu cache clear`; MCP `edu_design_*`, `edu_cache_clear`; skill `edu-design`). Live-tested 2026-11-11 on «Тест инструментов» items (CSS create / set / copy, template copy + master change + CSS attach, module copy + markup save, deletes), all removed.

Saving a template unchanged also re-spaces `LoadModule(...)` calls (adds a space or newline between them) – harmless, but it shows up as a change.

## Scripts: a second jQuery drops the plugins

The master 1144 loads jQuery 1.10.2 (1203) and 1.11.3 (1213), then the plugins (bxSlider, Fancybox, cookie, `privacy_policy.js` …). The live Обычный 1164 attaches jQuery 1.11.0 (1023) once more; it loads after the master's scripts, replaces `$` and loses the plugins, so the page throws `$(...).owlCarousel is not a function` and the cookie bar (`#privacy_policy`) never opens on ordinary pages (seen 2026-11-11; the 404 template, without that script, shows the bar). Detaching the extra jQuery from the template fixes it: no errors, the cookie bar opens.

## Low-vision mode (version for the visually impaired)

The live «Версия для слабовидящих» (verified 2026-11-11 – public page, export strings 1458 / 1468, `/fonts/slep/special.min.css`): the button is `<a id="specialButton">` from resource string 1468 in the master's top bar; the script in string 1458 (at the top of the master body) on click loads the platform stylesheet `/fonts/slep/special.min.css`, adds class **`special`** and `special-color-N`, `special-font-size-N`, `special-font-family-N`, `special-line-height-N`, `special-letter-spacing-N`, `special-images-N` to **`<html>`**, prepends its panel `#special` to `<body>` and keeps the choice in cookie `special`. The stylesheet sets colours, font sizes and families on `.special-color-N *` etc. with `!important`. A new design style must not apply in that mode – scope its selectors with **`html:not(.special)`**.

The `body.colorSite*` classes (`colorSiteBlack`, …) belong to an older mechanism – JS 1253 «settings - версия для слабовидящих», bound to `#versionForVisuallyImpaired`, which the current master doesn't render; CSS 1282 still has rules for them. Don't rely on them.

## Public site from the container browser

Chromium with the PAC file timed out on the public school host (the httpx client reaches it through the same proxy). Working approach: route the page's edu.by requests through the httpx client (`page.route` + `route.fulfill`) and let other hosts go direct.

## Utilities (RengerProvider.aspx?guid=Utility) – verified 2026-11-10

| Item | Dialog | What it does |
|---|---|---|
| «Экспорт в архив» (export to archive) | `G_RengerProvider/ExportToArchives.aspx` | tree of templates (Мастер / Главный / Обычный / 404) with checkboxes `ctl00_Main_TreeListn<N>CheckBox` (`title="Template"`); async postback `ctl00$ButtonSave = Экспорт`. Reply: `Result_Status = Info`, `Result_Value_1 = <a href=/sm_full.aspx?guid=-888 …>Нажмите здесь для загрузки архива</a>`; GET that URL → `application/x-zip-compressed`. **Read-only for the site; run with user approval 2026-11-10** (12 templates → 3.7 MB). **Unreliable (2026-11-11):** of 7 tool / script attempts that day 2 succeeded (morning, and one at midday), the rest got `error|500|` with an empty body – with and without `Origin` / `Referer`, before and after downloading the previous `guid=-888` archive, and again 10 min later. Cause unknown; a pending archive stays downloadable at `/sm_full.aspx?guid=-888`. Don't retry in a loop |
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
