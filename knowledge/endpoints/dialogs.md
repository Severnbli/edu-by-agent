---
status: partially verified
updated: 2026-11-10
source: guarded browser walk-through 2026-11-10 (read-only), capture constructor-2026-11-09 (#1128–#1258), capture edit-2026-11-10 (#145–#2390), capture publish-2026-11-10 (#231–#340), upload probes 2026-11-10 (test section 59791), read-only GETs of the dialogs
---

# Dialog pages (G_Data/*, G_All/*)

Opened by explorer.aspx in an iframe dialog. Each is its own WebForms page: GET it (safe, read-only), then POST the full form back as an **async postback** with a submit button field. Dialog posts use `ctl00$ScriptManagerDialog` instead of `ctl00$ScriptManagerWindow`.

**Result convention (verified 2026-11-10):** the reply's `ctl00_UpdatePanelMain` panel carries hidden fields `ctl00$Result_Status` (`Save` = saved and stays open, `SaveExit` = saved and closes, `Exit_2` = done with a result), `ctl00$Result_Value_1`, `ctl00$Result_Value_2`. After a dialog closes, the UI refreshes explorer.aspx with a postback (see explorer.md); the dialog's result is passed on in `ctl00$Result_Value*` of that postback.

Buttons common to edit dialogs: `ctl00$ButtonSave` (Сохранить и остаться, save and stay), `ctl00$ButtonSaveExit` (Сохранить и выйти, save and exit), `ctl00$ButtonExit` (Выйти без сохранения / Закрыть, exit without saving).

## ClassifierEditor.aspx?guid=<section id> – section properties

Fields (`ctl00$Main$…`):

| Field | Meaning |
|---|---|
| `Name` | internal name (a new section is created as `New`) |
| `title_ru`, `title_ru_status` (checkbox) | Russian title shown on the site, and whether it is enabled. Other languages likely `title_<lang>` (unverified) |
| `IsDelete` (checkbox) | **protection from deletion**, on for a new section; `IsDelClassifier` returns `""` while it is on |
| `fk_Template` (select) | «Шаблон» (page template): `0` = «-- Шаблон по иерархии (…) --» (inherit, the inherited name in brackets), else a «Обычный» template id (on the test site 1024 Базовый шаблон, 1164, 1114). A save posts the chosen id; not saved by us yet |
| `StatusDirectLink` (radio) | «Редирект»: `0` «ничего не делать» (no redirect), `2` «переход на первый под-классификатор» (go to the first subsection), `3` «переход на специальный классификатор» (go to the section in `SpecialClasifierAA`) |
| `SpecialClasifierAA` (hidden) | target section id for redirect `3`, picked with SelectClassifier |
| icon | «Иконка для карты сайта и меню»: separate dialog `/G_All/Binary.aspx?guid=<section id>` – `ctl00$Main$FileUploadIco` + `ctl00$AddButton$ButtonSaveBinary` «Загрузить», `ctl00$AddButton$ButtonDelBinary` «Удалить»; full image `/sm_full.aspx?guid=<id>` |
| `Tags` | «Теги:» |

Save (verified 2026-11-10): POST with `ctl00$ButtonSave` or `ctl00$ButtonSaveExit`; reply `Result_Status = Save | SaveExit`. Unchecked checkboxes are simply absent from the POST (standard HTML), so turning protection off = leave `IsDelete` out. Then the UI refreshes with `MyButtonEditClassifier` (explorer.md). Security dialog: `/G_Security/Classifier.aspx?guid=`.

## ClassifierMove.aspx?guid=<section id> – move a section (verified 2026-11-10)

Two trees: «Исходный классификатор» (source, `ctl00$Main$TreeViewSource`) and «Принимающий классификатор» (target, `ctl00$Main$TreeClassifier`). Steps:

1. GET the dialog.
2. Select the target node: async postback, `ctl00$ScriptManagerDialog = ctl00$Main$UpdatePanel1|ctl00$Main$TreeClassifier`, `__EVENTTARGET = ctl00$Main$TreeClassifier`, `__EVENTARGUMENT = s<path>` – **note the prefix is `s`, not `sNodeClassifier`**, e.g. `s1001\56621` or `s1001\56621\59631`. Selecting a node expands it (lazy, like explorer).
   The dialog's tree links are `__doPostBack('ctl00$Main$TreeClassifier','s1001\\1041')` (read-only GET 2026-11-10: the first level of the root is rendered, deeper levels after selecting the parent).
3. Place the section relative to it: async postback (`ctl00$ScriptManagerDialog = ctl00$Main$UpdatePanel1|<target>`) with `__EVENTTARGET` =
   - `ctl00$Main$MoveUp` – «Выше выбранного» (above the selected, same parent)
   - `ctl00$Main$MoveRight` – «Правее выбранного» (inside the selected, as a child)
   - `ctl00$Main$MoveDown` – «Ниже выбранного» (below the selected, same parent)
4. The dialog closes and the UI re-GETs `/Explorer.aspx`.

So the same dialog both moves sections between parents and sorts sections.

## AddObject.aspx?guid=<section id> – create objects (verified 2026-11-10)

- Types: elements with `gg="<type id>"` (see model.md); the click handler copies `gg` into the hidden `ctl00$Main$SelType`.
- POST fields: `ctl00$Main$Classifier = <section id>`, `ctl00$Main$SelType = <type id>`, `ctl00$Main$N_Count = <how many>`, button `ctl00$AddButton$ButtonMake = Создать` (Create).
- Reply: `Result_Status = Exit_2`, **`Result_Value_1 = ;<id>;<id>;…`** (ids of the new objects), `Result_Value_2 = Новый объект`. `N_Count = 5` created 5 empty objects at once.
- New objects are **unpublished**. The UI then refreshes explorer.aspx with `ButtonObjectAdd` and opens ObjectEditor for the new object. Seen for types 524 (Блок html), 534 (Новость), 304 (Графический объект).

## ObjectEditor.aspx?guid=<object id> – edit an object

Common fields (`ctl00$Main$…`):

| Field | Meaning |
|---|---|
| `CheckBoxStatusObject` (checkbox) | «Разрешить публикацию» (allow publication): checked = published (verified) |
| `Classifier` | parent section; label warns «при смене классификатора объект…» (changing it moves the object) |
| `ListLang$<n>` (checkbox) | languages the object is shown in (`ListLang$0` = Русский) |
| `Tags` | tags |
| `IsClearCache`, `HiddenTitleObject` | hidden helpers (`IsClearCache = 0` in all saves) |

Type-specific fields (labels verbatim):

| Type | Fields |
|---|---|
| 524 Блок html (текст раздела) | `name` «Описание блока» (block description), `text` (HTML, rich editor), `dop` |
| 534 Новость (news) | `dt_text` «Дата *» (date, `dd.mm.yyyy`, required) + `_ClientState`, `zag` «Заголовок» (headline), `name` «Аннотация» (summary), `txt` (body HTML, rich editor), `dop` «Используйте для вставки кода скриптов, iframe и пр.» (scripts, iframes) |
| 304 Графический объект (image) | `name` «Подпись» (caption), `text` «Комментарий» (comment); the file itself goes through BinaryFrame (below) |

**Save (verified 2026-11-10):** async postback of the full form + `ctl00$ButtonSave` (stay) or `ctl00$ButtonSaveExit`. Reply: `Result_Status = Save | SaveExit` and a refreshed `ctl00$Main$HiddenTitleObject` (the list label, e.g. `Новость: 02.11.2026 : `). The UI then refreshes explorer.aspx with `ctl00$ContentSecondMenu$ButtonRePage = Button` and `ctl00$Result_Value = <object id>`. Every save sends **all** fields, so a save without `CheckBoxStatusObject` unpublishes – a write command must carry the current value unless it means to change it. **Publish / unpublish (verified, capture publish-2026-11-10):** save with `ctl00$Main$CheckBoxStatusObject = on` publishes, a save without the field unpublishes; the list row loses / gets `class='obj_not_published'` after the refresh.

Read-only parts (verified by GET, used by `edu object`): the type name is the bold text after «Тип:», the section path label is the `<span>` after the `Classifier` input (e.g. `Главная страница/…/`), `ctl00$Title_1` = `[<id>] Редактирование данных`, `ctl00$Title_2` contains a link to the public page `http://<site>/main.aspx?guid=<id>`.

## BinaryFrame.aspx – file upload (verified 2026-11-10 for images)

News and image editors embed `/G_All/BinaryFrame.aspx?guid=<object id>`: a **plain (non-async) multipart form** (`enctype="multipart/form-data"`, action `./BinaryFrame.aspx?guid=<id>`) with `__EVENTTARGET`, `__EVENTARGUMENT`, `__VIEWSTATE`, `__VIEWSTATEGENERATOR`, `__EVENTVALIDATION`, the file input `FileUploadIco` and the hidden submit `ButtonSaveBinary` (value `""`; the page's `SendFile()` clicks it when a file is chosen).

Upload = GET the frame, then POST its fields + `ButtonSaveBinary=` + the file as `FileUploadIco`. Tested by direct POSTs on image objects (type 304) in a test section:
- The file is stored **at once** – no ObjectEditor save needed. The server re-encodes it: `/sm.aspx?guid=<id>` (thumbnail) then returns `image/jpeg`; for an object without a file it returns a placeholder (`text/html` content type, PNG bytes, 2214 B).
- **Size limit ≈ 300 000 bytes**: 299 000 B accepted, 301 000 B rejected (PNG). Pixel size doesn't matter (8000×6000 at 148 KB accepted). A rejected file still gets **HTTP 200 and no message** – the frame just re-renders. So the only way to know is to check the thumbnail afterwards.
- **Documents (PDF, DOCX…) are not stored on the site at all** (verified 2026-11-10, objects 126813–126863 in test section 59791). Type 734 «Гиперссылка на файл для скачивания» (and 594 «Методический материал», which adds `author`, `subject`, `ano`, `dt_text`) is a card with `name` «Название», `format` «формат файла» (e.g. `docx`), `size` «размер файла» (e.g. `20`) and `url` «Ссылка на Яндекс.Диск»; the only existing filled one on this site points to `https://disk.yandex.by/i/…`. In its editor the BinaryFrame file input is hidden (`display: none`); a direct BinaryFrame POST of a 100 KB PDF returns HTTP 200 but stores nothing (`/sm_full.aspx?guid=<id>` keeps answering «Информация не найдена»). The «Выбрать...» button opens SelectImage.aspx, whose «Загрузить» rejects a PDF with the alert «Это не графический файл» (not an image file). TinyMCE in the editors has no upload handler either (`link image` take URLs). So a document goes on the site as an external link (Yandex.Disk or another host) – in a 734 card or an `<a>` in HTML.
- Browser note: Playwright request interception drops the file part of a multipart body, so uploads must be sent directly with httpx, not through the guarded browser.

`/G_All/SelectImage.aspx?guid=<object id>` («Выбор изображения», choose image; opened by «Выбрать...» → `CopyBinary()`) has the same pair `ctl00$Main$FileUploadIco` / `ctl00$Main$ButtonSaveBinary` «Загрузить» (plain multipart postback, images only), a section tree (`ctl00$Main$TreeClassifier`) and a pager of the images of the selected section; clicking a picture calls `Exit(<image object id>)`, and the editor then reloads the frame as `BinaryFrame.aspx?guid=<id>&status=copy&copyguid=<image object id>` – reusing an existing image instead of uploading (not saved by us yet). Thumbnails: `/sm.aspx?guid=<id>`, `/G_All/sm.aspx?guid=<id>&tyui=<random>`.

## SelectClassifier.aspx?guid=<section id> – pick a section (verified 2026-11-10)

Used by «Переместить объекты». Select a node (`__EVENTTARGET = ctl00$Main$TreeClassifier`, `__EVENTARGUMENT = s1001\56621\59771`), then POST `ctl00$ButtonSaveExit = Выбрать` (Choose). Reply: `Result_Status = Exit_2`, `Result_Value_1 = <section id>`, `Result_Value_2 = <title path>/`. The explorer postback that follows does the move (explorer.md).

## ObjectsSort.aspx?guid=<section id> – sort objects (verified 2026-11-10)

GET lists the section's objects in their current order as `<div id='SortList'><span guid='<id>'>…</span>…</div>` (read-only GET 2026-11-10). `ctl00$Main$HiddenFieldForSave` is **empty** on GET – the page's `Save()` fills it from `#SortList` just before posting; POST `ctl00$Main$HiddenFieldForSave = <id>;<id>;…;` (new order, trailing `;`) + `ctl00$ButtonSaveExit`. Reply `Result_Status = SaveExit`; then explorer postback `ButtonObjectSort`.

## G_RengerProvider/Templates.aspx?guid=<template id> – page templates

Site page templates (Мастер, Шапка, Обычные …, listed by `RengerProvider.aspx?guid=Master|Head|Normal|Utility|JavaScript|CssPacked|ResourceString|Old|Actual|ExportToXml&gs=<GuidSession>`). Form: `ctl00$Main$TextBoxTitle_text` (name), `ctl00$Main$MasterList` (master template id), `ctl00$Main$Body_Content_<n>$TextBoxRes` (template HTML with `LoadModule(<id>,<name>)` calls), `ctl00$Main$HiddenFieldForSave` (attached scripts, e.g. `<js value="1023"/>`), `ctl00$Main$ClassifierL`, save `ctl00$ButtonSaveExit`.
**Affects the whole site.** In the capture, saving 1024 «Базовый шаблон» unchanged still rewrote it: the editor put each `LoadModule(...)` on its own line and filled `HiddenFieldForSave`. Never save a template from a tool without explicit user request.

## Other dialogs (referenced in JS, not explored)

`ClassifierLang.aspx?lang=`, `DirectLink.aspx?guid=`, `/G_RengerProvider/Controls.aspx?guid=`, `RengerProvider.aspx?guid=NotUseTemplate|404`.
