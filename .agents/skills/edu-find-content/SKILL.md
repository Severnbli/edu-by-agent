---
name: edu-find-content
description: Find sections, pages and content objects on an edu.by school site and read them (titles, HTML, publication state, public URL) – read-only. Use when the user asks what is on the site, where a page or text lives, which object shows something on a public page, or before any edit to locate its target.
---

# Find and read site content

Read-only: nothing here changes the site. Run everything from the repo root through `./edu`.

## Model in one paragraph

The site is a tree of **sections** (разделы, «классификаторы»). Ids end in `1`: `1001` is «Главная страница», `1011` «Служебный» (hidden service sections: header, footer, banners, slider). Each section holds ordered **objects** (ids end in `3`) of a **type** (ids end in `4`), for example 524 «Блок html (текст раздела)» for page text, 534 «Новость», 304 «Графический объект» for an image, 734 for a link to a file. A public page `main.aspx?guid=<section id>` shows that section's published objects. See `knowledge/model.md`.

## Commands

```bash
./edu session check                       # exit 2 → edu-session skill
./edu tree --depth 2                      # top of the tree (one request per listed section)
./edu tree --root 1001/1041 --depth 1     # one branch
./edu objects 1001/1041                   # objects of a section, in order ('-' = unpublished)
./edu objects 1001/1431/1031 --pages 1    # only the first page of a big list (news archive)
./edu object show 2283                    # type, section, state, public_url, editable fields and values
./edu section show 1001/1041              # title, internal name, protection, template, redirect
./edu types                               # object type ids
./edu trash list 304                      # one page of a type's trash
```

Add `--json` for machine-readable output.

## Speed

The tree is lazy. Every section that has to be opened costs one request of ~110 KB, about 1 s.
- Pass an **ID path** (`1001/1041/1201`) whenever you know it. A bare id is fast only if it is in the path cache (`.session/tree-<site>.json`, filled by every command). Otherwise it walks the whole tree, which takes minutes.
- Keep `--depth` small. `--all` walks everything, so use it only when the user wants a full map.
- Never run two `./edu` commands at once: the server handles one request per session at a time, and both slow down.

## From a public page to an object

- The public URL has the id: `main.aspx?guid=1041` is a section, `guid=126433` is an object.
- A page's text block: `./edu objects <section>` and look for «Блок html».
- Images in HTML are `sm_full.aspx?guid=<image object id>`.
- A public page's HTML can be read with the same client. Ask before crawling many pages, and keep a delay between requests.

## Report

Give ids together with titles and paths (e.g. `1041 «О школе» (1001/1041)`), say what is unpublished, and quote HTML only as much as needed.

## Errors

- `Session expired` (exit 2): ask the user to run `./edu session login`.
- `section X not found`: wrong id, or the section is in another branch. Try `tree --root` on the likely parent.
- `No object`: the object id doesn't exist (it may be purged; ids get reused).
