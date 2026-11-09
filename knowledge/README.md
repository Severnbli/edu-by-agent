# Knowledge index

Facts about the edu.by site constructor, taken from real traffic only. Each file's frontmatter has `status` (verified / partially verified / unverified) and its `source`.

| File | What it covers | Status |
|---|---|---|
| [auth.md](auth.md) | login form, captcha, cookies, GuidSession, session check | partially verified |
| [model.md](model.md) | sections (classifiers), objects, object types, ID suffix scheme | verified |
| [endpoints/explorer.md](endpoints/explorer.md) | explorer.aspx postbacks, tree, object list, toolbar actions | verified |
| [endpoints/dialogs.md](endpoints/dialogs.md) | ClassifierEditor, AddObject, ObjectEditor forms | partially verified |
| [endpoints/systemwjg.md](endpoints/systemwjg.md) | SystemWJG.asmx JSON methods | partially verified |

## Captures

| ID | Date | Content |
|---|---|---|
| constructor-2026-11-09 | 2026-11-09 | login; tree browsing; system templates view; add section under 1051, rename, add HTML block object, delete it, remove delete protection, delete the section |

Raw and sanitized captures live in `.session/har/` (git-ignored). Excerpts copied into `captures/` must come from the sanitized file.

## Not captured yet

Saving object content (ObjectEditor POST), publishing/unpublishing, file and image upload (BinaryFrame.aspx), trash, move, sort, section copy and move, menu changes.
