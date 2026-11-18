---
name: edu-publish-news
description: Publish a news item («Новость») with photos on an edu.by school site through the constructor – date, headline, annotation, body text and pictures. Use when the user asks to add, post or publish news, an event report or an announcement with photos, or to fix the text or date of an existing news item.
---

# Publish a news item

A news item is an object of type **534 «Новость»**. Its photos are separate **image objects (304 «Графический объект»)** in the same section, left unpublished and shown inside the news text with `<img src="sm_full.aspx?guid=<image id>">`. That is how this site's existing news are built (knowledge/endpoints/dialogs.md, «News»).

The news object also takes **its own picture – the cover**. News lists (home page, archive) show it through `sm.aspx?guid=<news id>`; a news item without one shows the platform's empty placeholder there. Always give a news item with photos a cover: its first photo.

Everything goes through `./edu` from the repo root. Write commands only preview without `--yes`.

## Inputs – ask the user for what is missing

- **date** `dd.mm.yyyy` (required; usually the event date or today)
- **headline** (`zag` «Заголовок»)
- **annotation** (`name` «Аннотация»): one or two sentences shown in the news list. If the user gives none, propose one from the text and let them approve it.
- **body text**: their text or a draft you wrote that they approved. Don't invent facts, names or numbers.
- **photos**: files inside the repo (the container sees only the repo). Put working files in `.session/work/` (`mkdir -p .session/work`; git-ignored, never committed).
- **publish now or leave as a draft**. Default: a draft (unpublished), the user checks it first.

## Steps

1. Session: `./edu session check` (exit 2 → the `edu-session` skill; the user logs in).
2. Find the news section. Usually «Архив новостей» (e.g. path `1001/1431/1031`); if `.session/notes/site.md` names it, use that, else look for it with `./edu tree --depth 2` or ask the user. Always pass the **ID path**: a bare id that isn't cached costs a walk of the whole tree. Check the existing format first:
   ```bash
   ./edu objects 1001/1431/1031 --pages 1
   ./edu object show <id of a recent news>      # dt_text, zag, name, txt – copy its HTML style
   ```
3. Photos, one image object each. Create them before the news, so the news comes out above its photos in the list:
   ```bash
   ./edu object add 1001/1431/1031 --type 304 --count 3 --yes      # → "ids": [...]
   ./edu object upload <image id> .session/work/photo1.jpg --shrink --yes
   ```
   `--shrink` re-encodes a phone photo as JPEG under the ~300 KB limit, at most 1600 px. Without it the server silently drops bigger files. Leave the image objects **unpublished**, like the site's own news photos.
4. Write the body to `.session/work/news.html`. Use paragraphs, then one centered paragraph per photo, in the style of the site's news:
   ```html
   <p style="text-align: justify;">Текст новости…</p>
   <p style="text-align: center;"><img src="sm_full.aspx?guid=126443" width="800" /></p>
   ```
   Use plain HTML only: no scripts, no external images. Documents (PDF, DOCX) can't be uploaded. Link to them, e.g. on Yandex.Disk: `<a href="https://…">Положение (PDF)</a>`.
5. Preview the news, then **show the preview to the user and wait for their OK**:
   ```bash
   ./edu object add 1001/1431/1031 --type 534 --set dt_text=10.11.2026 \
     --set zag="Заголовок" --set name="Аннотация" --set txt=@.session/work/news.html
   ```
   On the OK, rerun with `--yes`. The result shows the new id. Don't assume ids grow: the constructor reuses old ids.
6. Cover: upload the first photo into the news object itself (same file as the first image object):
   ```bash
   ./edu object upload <news id> .session/work/photo1.jpg --shrink --yes
   ```
   For a news item without photos, skip this; the lists then show it without a picture.
7. Check the draft: `./edu object show <news id>`. Give the user the `public_url` and the constructor to look at. The public page works only after publishing.
8. Publish only when the user says so:
   ```bash
   ./edu object publish <news id>          # preview: published False -> True
   ./edu object publish <news id> --yes
   ```
   Publishing makes the news visible on the public site at once.

## Verify

- `Applied and verified.` means the fields were re-read and match. Exit code 4 means applied, but the check found a difference: show the `mismatch` to the user.
- `curl`/browser `sm.aspx?guid=<news id>` on the public host returns the cover (a 1×1 `NotBinary.png` means no cover).
- After publishing, the news appears at the top of `./edu objects 1001/1431/1031 --pages 1` without the `-` mark, and its `public_url` shows the headline and the photos.

## Editing an existing news item

```bash
./edu object show <id>
./edu object set <id> --set zag="…" --set dt_text=09.11.2026          # preview
./edu object set <id> --text-file .session/work/news.html --yes        # body (txt)
./edu object unpublish <id> --yes                                      # take it off the site
```

A published news item changes on the site at once (the preview says `[publish]`), so confirm with the user first. Each save sends all fields, so the publication state is kept unless you change it.

## Cover for an existing news item

The first photo of an older news item is an image object on the site: download `sm_full.aspx?guid=<image id>` from the public host (through the proxy) into `.session/work/`, then `./edu object upload <news id> <file> --shrink` (preview, `[publish]` level for a published news item: lists show the picture at once – confirm with the user first).

## Common errors

- `Session expired` (exit 2): the user runs `./edu session login`, then retry the same command.
- `no field 'x'`: the type has no such field. `object show` lists the editable fields (`dt_text`, `zag`, `name`, `txt`, `dop`, `Tags`).
- `only images upload`: a document can't be uploaded. Put a link to it in the text instead.
- `could not shrink it under …`: the photo is too detailed. Crop it or ask for a smaller file.
- A text that is one bare `<p>…</p>` is stored without the `<p>` tags. That is normal, the page looks the same.
- Removing a news item is a delete-level change: `./edu object trash <id>` (preview, then `--token`). Its photos go separately.
