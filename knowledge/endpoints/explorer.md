---
status: verified
updated: 2026-11-10
source: capture constructor-2026-11-09 (#96–#1271), read-only replay of tree selection, live read-only probes 2026-11-10 (edu tree/objects/types)
---

# explorer.aspx – the main constructor window

ASP.NET WebForms page. Everything is a **postback** of the whole form to `/explorer.aspx`; the UI uses async postbacks (UpdatePanel). Helper: `edu_by.webforms.WebFormPage`.

## Async postback mechanics

- `POST /explorer.aspx`, `application/x-www-form-urlencoded; charset=UTF-8`
- Headers: `X-MicrosoftAjax: Delta=true`, `X-Requested-With: XMLHttpRequest`, `Origin`, `Referer`
- Body: **all** form fields from the last page state (`__VIEWSTATE`, `__VIEWSTATEGENERATOR`, `__EVENTVALIDATION`, `ctl00$GuidSession`, `ctl00$Main_Left$GUID_CLASSIFIER`, tree `ExpandState`/`SelectedNode`, `ST_icon`/`ST_pages`/`ST_window`, `PageList`, ...) plus:
  - `ctl00$ScriptManagerWindow = <panel>|<event target>`
  - `__EVENTTARGET`, `__EVENTARGUMENT`
  - `__ASYNCPOST = true`
- Reply: `text/plain` delta, records `length|type|id|content|` (`updatePanel`, `hiddenField` incl. new `__VIEWSTATE`, `pageRedirect`, `error`). Apply `hiddenField` values before the next postback.

## Tree (left panel)

- Select a node: target `ctl00$Main_Left$TreeClassifier`, panel `ctl00$Main_Left$UpdatePanel1`, argument
  - section: `sNodeClassifier\1001\1051` (path of IDs from the root)
  - object type: `sNodeTemplate\<group>\<id>` e.g. `sNodeTemplate\Стандартные\534`
  - trash: `sNodeTrashe\<group>\<id+1>`
- Tree node links in HTML: `__doPostBack('ctl00$Main_Left$TreeClassifier','sNodeClassifier\\1001\\1051')`, label after the `<img ... guid=1051>` icon.
- **The tree is lazy.** A fresh GET shows the roots (and whatever the session had expanded); a section's children are rendered only after that section is **selected**. Nodes carry no "has children" marker until then, so listing the whole tree costs one postback per section (~1.4 s each incl. a 0.5 s pause; ~150 KB reply). Measured 2026-11-10 on the test site: 711 sections, 7 levels deep, 711 requests, 17 min. A section given as an ID path (`1001/1041/1201`) is reached with one request per ancestor. The server keeps the current node and the expanded branches per session, across GETs of explorer.aspx.
- **Quirk (verified 2026-11-10):** selecting a node that is **not present in the current tree HTML**, or the node that is **already current** (`ctl00$Main_Left$GUID_CLASSIFIER`), returns an `error|500|` record with no message. The page state stays usable: the next valid selection works. So reveal a section by selecting its ancestors top-down, and skip the request if it is already current (its object list is already on the page).
- Depth-first walking keeps every visited branch visible: siblings of an ancestor stay rendered after a deeper node is selected, so each section is selected exactly once (`Explorer.walk`).
- Node markup: each node is a `<table>` with an optional toggle `<a id="…TreeClassifiern<N>">` and a text element `id="…TreeClassifiert<N>"` – an `<a href="javascript:__doPostBack(…,'sNodeClassifier\\1001\\1051')">` with `<img … guid=<id>>` + title, or for the **selected** node a `<span>` (no postback argument, title in `<span id='SelectTree'>`). Children are inside `<div id="…TreeClassifiern<N>Nodes">`. Template nodes also have an icon link `id="…t<N>i"`. Grouping nodes (Классификаторы, Шаблоны, Корзина объектов, group names) are plain spans.
- Reply panels: `ctl00_Main_Left_UpdatePanel1` (tree), `ctl00_Main_Right_UpdatePanelMainList` (objects), `ctl00_ContentMainMenu_UpdatePanel2`, `ctl00_ContentSecondMenu_UpdatePanel3` (toolbars).

## Object list (right panel)

`<table id='ListElements'>` rows: `<tr guid='<object id>' [class='obj_not_published']>` with a checkbox and `Obj_Open(this)`; text is `<type label>: <title>` (short labels such as `Блок html`, `Граф объект`; the title may be empty or contain `:`). Images have an `<img src=/sm.aspx?guid=<id>>` thumbnail. Opening a row loads `/G_Data/ObjectEditor.aspx?guid=<id>` in an iframe.

**Pagination (verified 2026-11-10):** page size is `ctl00$Main_Right$ST_pages` (10; a user setting, saved by `SettingSave` – not changed by the CLI). The toolbar panel `ctl00_ContentSecondMenu_UpdatePanel3` holds a hidden `<select name="ctl00$ContentSecondMenu$PageList">` whose option values are **0-based page indexes**, shown as a window around the current page plus `<<` / `>>` entries (e.g. on page 6 of 12: `0…10, 11 (>>)`); the selected option is the current page. To change page: async postback, panel `ctl00$ContentSecondMenu$UpdatePanel3`, `__EVENTTARGET = ctl00$ContentSecondMenu$PageList`, field `ctl00$ContentSecondMenu$PageList = <index>` (what `StepByStep('PageList', n)` does). The reply refreshes the list and the pager.

## Toolbar actions (postback targets)

Write actions – **never run without user confirmation** (see CLAUDE.md).

| Action | `__EVENTTARGET` | Extra fields | Observed effect |
|---|---|---|---|
| Add section | `ctl00$ContentMainMenu$MyButtonAddClassifier` | current `GUID_CLASSIFIER` = parent | creates child section (named `New`) immediately, then the UI opens ClassifierEditor |
| Edit section (refresh after dialog) | `ctl00$ContentMainMenu$MyButtonEditClassifier` | | |
| Delete section | `ctl00$ContentMainMenu$MyButtonDelClassifierAll` (sent as a submit button field `=Button`, no `__EVENTTARGET`) | | deletes current section; UI first calls `SystemWJG.IsDelClassifier` |
| Copy section | `Classifier_Copy` button (target not captured yet) | | |
| Move section | dialog `/G_Data/ClassifierMove.aspx?guid=` | | |
| Add object (refresh after dialog) | `ctl00$ContentSecondMenu$ButtonObjectAdd` | | objects are created by AddObject.aspx |
| Delete objects | `ctl00$ContentSecondMenu$ButtonObjectDel` | `ctl00$Result_Value_2 = id|id|` | in the capture: permanent delete (UI confirms twice). Note: in a section view this button's title is «Переместить в корзину» (move to trash) and its onclick is `Object_Trash(...)` – what it does depends on the view; capture before use |
| Move to trash | `Object_Trash` button | `Result_Value_2 = id|id|` | not captured yet |
| Move objects | dialog `/G_All/SelectClassifier.aspx`, then postback | `Result_Value_2 = ids`, `Result_Value_3 = target section` | not captured yet |
| Sort objects | dialog `/G_Data/ObjectsSort.aspx?guid=` | | not captured yet |
