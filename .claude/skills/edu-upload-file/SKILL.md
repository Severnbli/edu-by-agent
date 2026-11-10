---
name: edu-upload-file
description: Put images and documents on an edu.by school site – upload photos into image objects (with automatic shrinking to the size limit) and add documents (PDF, DOCX) as links. Use when the user wants to add a picture, photo, scan, poster, document, regulation or file for download to a page.
---

# Images and documents

## What the constructor accepts

- **Images only**, up to ~300 000 bytes. A bigger file is dropped **silently** (HTTP 200, no picture), so always use `--shrink`. The server re-encodes everything to JPEG.
- **Documents are not stored on the site.** A «Гиперссылка на файл для скачивания» object (type 734) is a card with a link, e.g. to Yandex.Disk (`name`, `format`, `size`, `url`). An `<a href>` in page text works too. The user uploads the file to their disk and gives you the link; you can't upload it there for them.
- Files must be inside the repo, since the container sees only the repo. Use `.session/work/` (`mkdir -p .session/work`; git-ignored).

## Image into a page

```bash
./edu object add 1001/1041 --type 304 --set name="Подпись" --yes        # → "ids": [<image id>]
./edu object upload <image id> .session/work/photo.jpg --shrink          # preview
./edu object upload <image id> .session/work/photo.jpg --shrink --yes
```

Then either:
- **show it as its own object** in the section: `./edu object publish <image id>` (after the user's OK), and `object sort` to place it; or
- **put it into an HTML text** and leave the image object unpublished, like the site's news do: `<p style="text-align: center;"><img src="sm_full.aspx?guid=<image id>" width="800" /></p>`, then edit the text (`edu-edit-content`).

Check: the upload result says `"verified": true` (the thumbnail `/sm.aspx?guid=<id>` returns `image/jpeg`).

## Document as a link

1. Ask the user for the public link (Yandex.Disk «Поделиться» → link) and the file's format and size.
2. A card object:
   ```bash
   ./edu object add 1001/1041 --type 734 --set name="Положение о конкурсе" \
     --set format=pdf --set size=120 --set url="https://disk.yandex.by/i/…"   # preview, then --yes
   ```
   Check the fields of the type with `./edu object show <id>` of an existing card. Publish it after the user's OK.
3. Or a link in a text: `<a href="https://disk.yandex.by/i/…" target="_blank">Положение о конкурсе (PDF, 120 КБ)</a>`.

## Common errors

- `only images upload`: a document goes as a link (above).
- `over the ~300000 B limit`: add `--shrink`.
- `has no file upload`: that object type takes no file. Use a 304 image object.
- `Session expired` (exit 2): the user runs `./edu session login`.
