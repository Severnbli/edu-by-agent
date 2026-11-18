# Find and read site content (MCP tools)

Read-only: these tools change nothing.

The site is a tree of **sections** (ids end in `1`; `1001` «Главная страница», `1011` «Служебный» with header, footer, banners and slider). Each section holds ordered **objects** (ids end in `3`) of a **type** (ids end in `4`): 524 «Блок html» for page text, 534 «Новость», 304 «Графический объект», 734 file link card. The public page `main.aspx?guid=<section id>` shows that section's published objects. More: resource `edu://knowledge/model.md`.

## Tools

- `edu_session_status`: check first. If it isn't valid, the user logs in (`./edu session login`).
- `edu_tree(root?, depth=1..3)`: sections. Each level costs a request per section above it.
- `edu_find_section(section)`: id, title, path.
- `edu_section(section)`: title, internal name, protection, template, redirect.
- `edu_objects(section, pages=3)`: objects in order (`published`, `type_label`, `title`). `more: true` means the list continues.
- `edu_object(id)`: type, section, `public_url`, all editable fields with values (full HTML).
- `edu_types`, `edu_trash_list(type_id, page)`.

## Speed

Pass **id paths** (`1001/1041/1201`) when you know them. A bare id that isn't cached walks the whole tree, which takes minutes. Calls run one at a time, since the server handles one request per session.

## From a public page to an object

`guid=<id>` in a public URL names a section (ends in 1) or an object (ends in 3). Images in HTML are `sm_full.aspx?guid=<image object id>`.

## Report

Give ids with titles and paths, say what is unpublished, and quote HTML only as much as needed.
