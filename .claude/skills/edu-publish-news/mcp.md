# Publish a news item (MCP tools)

A news item is an object of type **534 «Новость»** with fields `dt_text` (date `dd.mm.yyyy`, required), `zag` (headline), `name` (annotation shown in the news list), `txt` (body HTML). Its photos are separate **image objects (304)** in the same section, left **unpublished** and shown inside `txt` with `<img src="sm_full.aspx?guid=<image id>">`, as the site's own news are built.

Every write tool first returns a preview. Show it to the user, and call again with `confirm_token` only after their OK.

## Inputs – ask for what is missing

Date, headline, annotation (propose one from the text if none is given, and let the user approve it), body text (don't invent facts, names or numbers), photos (image files inside the server's repository), publish now or keep as a draft (default: draft).

## Steps

1. `edu_session_status`. If it isn't valid, the user logs in (`./edu session login`, captcha).
2. Find the news section. On sch12.baranovichi it is `1001/1431/1031` «Архив новостей». Elsewhere use `edu_tree` (depth 2) or ask. Call `edu_objects(section, pages=1)` and `edu_object(<a recent news id>)` to copy the site's HTML style.
3. Photos, created before the news so the news comes out above them:
   - `edu_object_create(section, type_id="304", count=N)` → preview → after the OK, again with `confirm_token` → `result.ids`.
   - for each: `edu_object_upload_image(id, path)` (`shrink` is on by default) → preview → confirm.
   - leave them unpublished.
4. Compose `txt`: paragraphs of the text, then one paragraph per photo:
   `<p style="text-align: center;"><img src="sm_full.aspx?guid=<image id>" width="800" /></p>`.
   Use plain HTML: no scripts, no external images. Documents go in as links (`<a href="https://…">`).
5. `edu_object_create(section, type_id="534", values={"dt_text": "10.11.2026", "zag": "…", "name": "…", "txt": "…"})` → show the preview → confirm. Take the id from `result.ids`, since ids are reused.
6. `edu_object(<news id>)`: check the fields, and give the user the `public_url`. The page shows only after publishing.
7. Only when the user says so: `edu_object_update(id, published=true)` → preview (`published: false → true`, level `publish`) → confirm.

## Verify and errors

- `result.verified: true` means it was re-read and matches. If false, show `result.mismatch` and don't retry blindly.
- A body that is one bare `<p>…</p>` is stored without the `<p>` tags. That is normal.
- "only images upload": put a link to the document instead. "could not shrink": crop the photo or ask for a smaller one.
- Edit later with `edu_object_update(id, values={...})`. A published news item changes on the site at once, so confirm first.
