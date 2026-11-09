---
status: verified
updated: 2026-11-09
source: capture constructor-2026-11-09 (#96–#1271), read-only replay of tree selection
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
- **Quirk:** selecting the node that is already current returns an `error|500|` record with no message. Select a different node first.
- Reply panels: `ctl00_Main_Left_UpdatePanel1` (tree), `ctl00_Main_Right_UpdatePanelMainList` (objects), `ctl00_ContentMainMenu_UpdatePanel2`, `ctl00_ContentSecondMenu_UpdatePanel3` (toolbars).

## Object list (right panel)

`<table id='ListElements'>` rows: `<tr guid='<object id>' [class='obj_not_published']>` with a checkbox and `Obj_Open(this)`; text is `<type label>: <title>`. Pagination: `ctl00$ContentSecondMenu$PageList`, `ST_pages` (page size, 10).

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
| Delete objects | `ctl00$ContentSecondMenu$ButtonObjectDel` | `ctl00$Result_Value_2 = id|id|` | permanent delete (UI confirms twice) |
| Move to trash | `Object_Trash` button | `Result_Value_2 = id|id|` | not captured yet |
| Move objects | dialog `/G_All/SelectClassifier.aspx`, then postback | `Result_Value_2 = ids`, `Result_Value_3 = target section` | not captured yet |
| Sort objects | dialog `/G_Data/ObjectsSort.aspx?guid=` | | not captured yet |
