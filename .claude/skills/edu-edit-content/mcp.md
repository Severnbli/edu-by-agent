# Edit site content (MCP tools)

These are **live public school websites**. Every write tool, called without `confirm_token`, returns only a preview: what changes (before/after), its `level` and a `token`. **Show the preview to the user and get their OK**, then call the same tool with the same arguments and `confirm_token`.

| `level` | Meaning |
|---|---|
| `edit` | not visible on the site (unpublished object, protection, tags) |
| `publish` | visible on the public site at once (published object, title, menu, order) |
| `delete` | moves to the trash or deletes for good |

`TokenMismatch` means the site changed since the preview: preview again. `result.verified: false` means the write happened, but the re-read differs: report `result.mismatch`.

Locate the target first (prompt `edu_find_content`) and use **id paths** for sections.

## Page text and objects

- `edu_object(id)`: current HTML (`fields.text`) and the editable field names.
- `edu_object_update(id, values={"text": "<html>"})`: keep the existing structure and inline styles, change only what was asked. A text that is one bare `<p>…</p>` is stored without the tags.
- `edu_object_update(id, published=true|false)`: show or hide.
- `edu_object_create(section, type_id, count, values)`: new objects are **unpublished**. Take the ids from `result.ids` (ids are reused).
- `edu_object_copy(id)`, `edu_object_move(ids, target_section)`, `edu_object_sort(section, order)` (all ids of the section in the new order).
- `edu_object_trash(ids)`: delete level, restorable from the trash.

## Sections (menu pages)

- `edu_section_add(parent, title, protected=true)`: appears in the menu at once.
- `edu_section_update(section, title?, name?, protected?, tags?)`.
- `edu_section_move(section, target, position=above|inside|below)`.
- `edu_section_delete(section)`: the section itself can't be restored, its objects go to the trash. A protected section or one with subsections is refused. Unprotect it first with `edu_section_update(protected=false)`, as a separate confirmed change.
- Root sections and page templates are not changed by these tools. A template save rewrites the template of the whole site.

## Trash

- `edu_trash_list(type_id, page)`: it also holds other people's deleted objects.
- `edu_trash_restore(type_id, ids, section)`.
- `edu_trash_purge(type_id, ids)`: **irreversible**. Only objects the user named, or ones you deleted in this task. Never "all".

## Errors

"Session expired": the user runs `./edu session login`, then retry. "no field 'x'": see `editable_fields` from `edu_object`. "is protected from deletion": unprotect it first.
