---
status: partially verified
updated: 2026-11-09
source: capture constructor-2026-11-09 (#1128–#1258), read-only GETs of the dialogs
---

# Dialog pages (G_Data/*)

Opened by explorer.aspx in an iframe dialog. Each is its own WebForms page: GET it (safe, read-only), then POST the full form back with a submit button field. Dialog posts use `ctl00$ScriptManagerDialog` instead of `ctl00$ScriptManagerWindow`. After the dialog closes, the UI refreshes explorer.aspx with a postback (see explorer.md).

## ClassifierEditor.aspx?guid=<section id> – section properties

Fields (`ctl00$Main$…`):

| Field | Meaning |
|---|---|
| `Name` | internal name |
| `title_ru`, `title_ru_status` (checkbox) | Russian title, enabled. Other languages likely `title_<lang>` (unverified) |
| `IsDelete` (checkbox) | **protection from deletion**; `IsDelClassifier` returns `""` while it is on |
| `fk_Template` (select) | page template, `0` = inherit from hierarchy; options e.g. 1024 Базовый шаблон |
| `StatusDirectLink` | 0 in captures |
| `Tags`, `SpecialClasifierAA` | not explored |

Save: `ctl00$ButtonSaveExit = Сохранить и выйти` (Save and exit). Security dialog: `/G_Security/Classifier.aspx?guid=`.

## AddObject.aspx?guid=<section id> – create objects

- Types: elements with `gg="<type id>"` (see model.md); the click handler copies `gg` into the hidden `ctl00$Main$SelType`.
- POST fields: `ctl00$Main$Classifier = <section id>`, `ctl00$Main$SelType = <type id>`, `ctl00$Main$N_Count = 1` (how many), button `ctl00$AddButton$ButtonMake = Создать` (Create).
- Observed: one empty object is created (126653 for type 524). Fill it with ObjectEditor.

## ObjectEditor.aspx?guid=<object id> – edit an object

Fields (`ctl00$Main$…`):

| Field | Meaning |
|---|---|
| `name` | title |
| `text` | main HTML content (textarea, rich editor `ctl00_Main_text`) |
| `dop` | additional content (second editor, type-dependent) |
| `Tags` | tags |
| `CheckBoxStatusObject` (checkbox) | «Разрешить публикацию» (allow publication): checked = published (verified) |
| `Classifier` | parent section |
| `ListLang$<n>` (checkbox) | languages the object is shown in |
| `IsClearCache`, `HiddenTitleObject` | hidden helpers |

Read-only parts (verified 2026-11-10 by GET, used by `edu object`): the type name is the bold text after «Тип:», the section path label is the `<span>` after the `Classifier` input (e.g. `Главная страница/…/`), `ctl00$Title_1` = `[<id>] Редактирование данных`, `ctl00$Title_2` contains a link to the public page `http://<site>/main.aspx?guid=<id>`, language checkboxes `ListLang$<n>` have `<label>`s (`Русский`, ...). `name` is labelled «Описание блока» (block description) for HTML blocks.

Buttons: `ctl00$ButtonSave` (Сохранить и остаться, save and stay), `ctl00$ButtonSaveExit` (save and exit), `ctl00$ButtonExit` (exit without saving).
Binary objects (images, files) embed `/G_All/BinaryFrame.aspx?guid=<object id>` for upload – **upload flow not captured yet**.

## Other dialogs (referenced in JS, not explored)

`ClassifierLang.aspx?lang=`, `ClassifierMove.aspx?guid=`, `ObjectsSort.aspx?guid=`, `DirectLink.aspx?guid=`, `/G_All/SelectClassifier.aspx?guid=`, `/G_RengerProvider/Controls.aspx?guid=`, `/G_RengerProvider/Templates.aspx?guid=`, `RengerProvider.aspx?guid=Master|Head|Normal|NotUseTemplate|404|Actual&gs=<GuidSession>` (template rendering).
