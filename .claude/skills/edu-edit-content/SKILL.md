---
name: edu-edit-content
description: Change content on an edu.by school site – edit page text (HTML blocks), publish or unpublish objects, create, copy, move, reorder or delete objects, and add, rename, move or delete sections (pages in the menu). Use when the user asks to update a page, fix a text, add a page or subsection, hide or show something, reorder blocks, or clean up old content.
---

# Edit site content

These are **live public school websites**. Every write is planned first. The command prints what will change (`before -> after`), its level and a token, and changes nothing until you rerun it. **Show the preview to the user and get their OK before applying**, unless they already approved this exact change.

| Level in the preview | Meaning | Apply with |
|---|---|---|
| `[edit]` | not visible on the site (unpublished object, protection, tags) | `--yes` |
| `[publish]` | visible on the public site at once (published object, title, menu, order) | `--yes`, after the user's OK |
| `[delete]` | moves to the trash or deletes | `--token <token from the preview>` |

If the site changed after the preview, the token no longer matches (exit 3): preview again. After applying, the command re-reads the site. `Applied and verified.` means it matches. Exit 4 means applied, but the check failed: show the `mismatch`.

First locate the target with the `edu-find-content` skill and use **ID paths** for sections.

## Page text (HTML block, type 524)

```bash
./edu object show 2283                                   # current HTML and editable fields
mkdir -p .session/work                                   # working files; .session/ is git-ignored
./edu object set 2283 --text-file .session/work/page.html            # preview
./edu object set 2283 --text-file .session/work/page.html --yes      # apply
./edu object set 2283 --set name="Описание блока" --yes
```

- Keep the existing HTML structure and inline styles. Change only what was asked.
- Only images upload, so put files as links (see `edu-upload-file`).
- A text that is one bare `<p>…</p>` is stored without the tags. That is normal.

## Publish, create, copy, move, order

```bash
./edu object publish 2283 --yes           # / unpublish
./edu object add 1001/1041 --type 524 --set name="…" --set text=@.session/work/new.html --yes
./edu object copy 2283 --yes               # unpublished copy in the same section
./edu object move 2283 2293 --to 1001/1061 --yes
./edu object sort 1001/1041 2293 2283 117633 --yes   # all ids of the section, new order
./edu object trash 2283                    # preview → then --token …
```

New objects and copies are **unpublished**. Publish them once the user has checked them. Ids are reused, so take them from the command's result.

## Sections (menu pages)

```bash
./edu section show 1001/1041
./edu section add 1001/1041 --title "Новый раздел"           # protected from deletion by default
./edu section set 1001/1041/1201 --title "Новое название" --yes
./edu section move 1001/1041/1201 --to 1001/1041/1211 --position above   # above | inside | below
./edu section set 1001/1041/1201 --unprotect --yes          # needed before a delete
./edu section set 1011/59871 --template 1164 --yes          # page template (0 = inherit); the preview lists the offered ids on error
./edu section delete 1001/1041/1201                          # preview → --token …
```

- A new section appears in the site menu and map right away.
- Deleting a section can't be undone for the section itself. Its objects go to the trash of their types. A section with subsections is refused: handle them first.
- Root sections and page templates (`fk_Template`) are not changed by these tools. A template save rewrites the template of the whole site.

## Trash

```bash
./edu trash list 524                       # newest first; other people's deleted objects too
./edu trash restore 524 126743 --to 1001/1041 --yes
./edu trash purge 524 126743               # IRREVERSIBLE: preview → --token …
```

Restore and purge only objects the user named, or ones you deleted yourself in this task. Never purge other people's objects, and never "all".

## Common errors

- `Session expired` (exit 2): the user runs `./edu session login`, then repeat.
- `no field 'x'`: see `editable` in `object show`.
- `is protected from deletion`: unprotect it first (a separate, confirmed change).
- `TokenMismatch` (exit 3): something changed, so preview again and show the user.
- Exit 4 after apply: report what the check found. Don't retry blindly.
