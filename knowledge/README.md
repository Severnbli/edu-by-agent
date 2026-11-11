# Knowledge index

Facts about the edu.by site constructor, taken from real traffic only. Each file's frontmatter has `status` (verified / partially verified / unverified) and its `source`.

| File | What it covers | Status |
|---|---|---|
| [auth.md](auth.md) | login form, captcha, cookies, GuidSession, session check | partially verified |
| [model.md](model.md) | sections (classifiers), objects, object types, ID suffix scheme | verified |
| [endpoints/explorer.md](endpoints/explorer.md) | explorer.aspx postbacks, tree, object list, toolbar actions | verified |
| [endpoints/dialogs.md](endpoints/dialogs.md) | ClassifierEditor, ClassifierMove, AddObject, ObjectEditor, SelectClassifier, ObjectsSort, Templates, upload frames | partially verified |
| [endpoints/design.md](endpoints/design.md) | RengerProvider: templates, modules, style sets, scripts; low-vision mode; utilities (design export / import archive, analysers) | partially verified |
| [endpoints/security.md](endpoints/security.md) | Security tab: users, groups, access, access map, audit | partially verified |
| [endpoints/systemwjg.md](endpoints/systemwjg.md) | SystemWJG.asmx JSON methods | partially verified |

## Captures

| ID | Date | Content |
|---|---|---|
| constructor-2026-11-09 | 2026-11-09 | login; tree browsing; system templates view; add section under 1051, rename, add HTML block object, delete it, remove delete protection, delete the section |
| edit-2026-11-10 | 2026-11-10 | add sections, rename, move a section (above / inside / below), create 5 HTML blocks, save text (stay / exit), copy objects, move an object to another section, sort, move to trash, create a news item and an image object, open upload dialogs, delete sections, open and save page templates, ClearCache |
| publish-2026-11-10 | 2026-11-10 | add section, add HTML block, publish it, unpublish it |
| design-2026-11-10 | 2026-11-10 | create / copy / delete / save a style set and a script, save a module and a template |
| design2-2026-11-11 | 2026-11-11 | copy and delete templates and a module (`TemplateCopy`, `TemplateDel`, `ControlCopy`, `ControlDel`), save a module copy, save master 1004 unchanged |

Raw and sanitized captures live in `.session/har/` (git-ignored). Excerpts copied into `captures/` must come from the sanitized file.

## Not captured yet

There is no «copy section» action in the explorer toolbar (only add, move, delete sections).

design import from archive, the two analysers, menu changes.
