# Images and documents (MCP tools)

- **Images only** upload, ≤ ~300 000 bytes. A bigger file is dropped silently by the server. `edu_object_upload_image` re-encodes it under the limit by default (`shrink`). The file must be inside the server's repository.
- **Documents (PDF, DOCX) are not stored on the site.** They go on it as links: a type 734 «Гиперссылка на файл для скачивания» card (`name`, `format`, `size`, `url`), or an `<a href>` in a page text. The user puts the file on a disk (e.g. Yandex.Disk) and gives you the public link.

Every write returns a preview first. Confirm with the user, then call again with `confirm_token`.

## Image

1. `edu_object_create(section, type_id="304", values={"name": "Подпись"})` → confirm → `result.ids`.
2. `edu_object_upload_image(id, path)` → confirm. `result.verified` means the thumbnail is a JPEG.
3. Then either:
   - publish it as its own object: `edu_object_update(id, published=true)`, then place it with `edu_object_sort`;
   - or leave it unpublished and put it into an HTML text: `<p style="text-align: center;"><img src="sm_full.aspx?guid=<id>" width="800" /></p>` (see `edu_edit_content`).

## Document as a link

1. Ask the user for the public link, the format and the size in KB.
2. `edu_object_create(section, type_id="734", values={"name": "…", "format": "pdf", "size": "120", "url": "https://…"})` → confirm. Compare the fields with an existing card from `edu_object`.
3. Publish it after the user's OK. Or use a link in a text: `<a href="https://…" target="_blank">Название (PDF, 120 КБ)</a>`.

## Errors

"only images upload": use a link instead. "has no file upload": use a 304 image object. "files must be inside the repository": copy the file there first.
