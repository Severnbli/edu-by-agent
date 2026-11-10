"""Planned writes on objects: edit fields, publish, create, copy, move, sort, trash, image upload.

Requests are the ones documented in knowledge/endpoints/dialogs.md and explorer.md. Every
function only reads; the returned `Change.apply()` writes and then re-reads to verify.
"""

from __future__ import annotations

import mimetypes
import re
import time
from dataclasses import asdict
from pathlib import Path

from edu_by.api import dialogs
from edu_by.api.changes import Change, WriteError
from edu_by.api.objects import EDITOR_PATH, ObjectData, parse_object_editor, read_object
from edu_by.site import Site
from edu_by.webforms import WebFormPage

ADD_PATH = "/G_Data/AddObject.aspx"
SORT_PATH = "/G_Data/ObjectsSort.aspx"
FRAME_PATH = "/G_All/BinaryFrame.aspx"
MAIN = "ctl00$Main$"
PUBLISHED = MAIN + "CheckBoxStatusObject"
# Fields an edit may not touch: the section (use move), list label and helpers, languages.
FIXED = {"Classifier", "HiddenTitleObject", "IsClearCache", "CheckBoxStatusObject"}
IMAGE_LIMIT = 300_000  # bytes; larger files are dropped silently by the server
IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/bmp", "image/webp"}


def _norm(v: str) -> str:
    return v.replace("\r\n", "\n").strip("\n")


_ONE_PARAGRAPH = re.compile(r"^\s*<p>((?:(?!</?p[\s>]).)*)</p>\s*$", re.S)


def _stored(v: str) -> str:
    """The value as the server keeps it: a text that is one bare `<p>…</p>` loses the
    paragraph tags (live 2026-11-10); several blocks are kept as sent."""
    v = _norm(v)
    m = _ONE_PARAGRAPH.match(v)
    return m.group(1) if m else v


def _label(obj: ObjectData) -> str:
    title = obj.name or "(без названия)"
    return f"object {obj.id} «{title[:60]}» ({obj.type}) in {obj.section_id} {obj.section_path}"


def _summary(obj: ObjectData) -> dict:
    d = asdict(obj)
    for k in ("text", "dop"):
        if len(d[k]) > 400:
            d[k] = d[k][:400] + f"… ({len(obj.text if k == 'text' else obj.dop)} chars)"
    return d


def editable_fields(page_fields: dict[str, str]) -> list[str]:
    """Short names of the text fields an object editor offers (e.g. name, text, zag, url)."""
    out = []
    for k in page_fields:
        if not k.startswith(MAIN):
            continue
        short = k[len(MAIN) :]
        if short in FIXED or "$" in short or short.endswith("ClientState"):
            continue
        out.append(short)
    return out


def read_object_fields(site: Site, object_id: str) -> dict:
    """One object as `edu object show` prints it: the summary, the editable field names
    and their current values (news: `dt_text`, `zag`, `txt`, …)."""
    page = dialogs.open_dialog(site.client, site.base_url, EDITOR_PATH, object_id)
    obj = parse_object_editor(object_id, page.html)
    editable = editable_fields(page.fields)
    values = {k: page.fields.get(MAIN + k, "").strip("\r\n") for k in editable}
    return {**asdict(obj), "editable_fields": editable, "fields": values}


# ---------- edit / publish ----------


def plan_update(
    site: Site,
    object_id: str,
    values: dict[str, str] | None = None,
    published: bool | None = None,
) -> Change:
    """Change text fields of an object and/or its «Разрешить публикацию» flag.

    `values` keys are the short field names of the object's editor (see `editable_fields`):
    `name`, `text`, `dop`, `tags`→`Tags`; news: `zag`, `txt`, `dt_text`; link cards: `format`,
    `size`, `url`. Unknown keys are refused – every save posts all fields, so the others keep
    their current values, including the publication flag unless `published` is given.
    """
    values = dict(values or {})
    if "tags" in values:
        values["Tags"] = values.pop("tags")
    page = dialogs.open_dialog(site.client, site.base_url, EDITOR_PATH, object_id)
    obj = parse_object_editor(object_id, page.html)
    allowed = editable_fields(page.fields)
    unknown = [k for k in values if k not in allowed]
    if unknown:
        raise WriteError(
            f"object {object_id} has no field(s) {unknown}; editable: {', '.join(allowed)}"
        )
    fields = {k: (_norm(page.fields[MAIN + k]), _norm(v)) for k, v in values.items()}
    if published is not None:
        fields["published"] = (obj.published, published)
    level = "publish" if obj.published or published else "edit"
    notes = []
    if obj.published and published is not False:
        notes.append("the object is published: the change is visible on the site at once")
    if published and not obj.published:
        notes.append("publishes the object on the public site")
    if published is False and obj.published:
        notes.append("removes the object from the public site")
    if any(_stored(v) != _norm(v) for v in values.values()):
        notes.append("a text that is one <p>…</p> is stored without the <p> tags")
    if "dt_text" in values:
        notes.append("news date: format dd.mm.yyyy (the calendar state is not changed)")

    def do() -> dict:
        with site.lock:
            for k, v in values.items():
                page.fields[MAIN + k] = v
            if published is True:
                page.fields[PUBLISHED] = "on"
            elif published is False:
                page.fields.pop(PUBLISHED, None)
            res = dialogs.submit(page, dialogs.SAVE)
            if res.status != "Save":
                raise WriteError(
                    f"save of {object_id} not confirmed: {res.status!r} {res.messages}"
                )
            time.sleep(site.delay)
            after = read_object(site.client, site.base_url, object_id)
            fresh = dialogs.open_dialog(site.client, site.base_url, EDITOR_PATH, object_id)
        mismatch = {
            k: _norm(fresh.fields.get(MAIN + k, ""))
            for k, v in values.items()
            if _stored(fresh.fields.get(MAIN + k, "")) != _stored(v)
        }
        if published is not None and after.published != published:
            mismatch["published"] = after.published
        return {"object": _summary(after), "verified": not mismatch, "mismatch": mismatch}

    return Change(
        "object.update",
        _label(obj),
        level,
        fields,
        notes,
        {"id": object_id, "values": values, "published": published},
        do,
    )


# ---------- create ----------


def plan_create(
    site: Site, section_id: str, type_id: str, count: int = 1, values: dict[str, str] | None = None
) -> Change:
    """Create `count` empty, unpublished objects of a type in a section (AddObject.aspx).

    `values` are then saved into each new object (same keys as `plan_update`).
    """
    if not (1 <= count <= 20):
        raise WriteError("count must be 1..20")
    page = dialogs.open_dialog(site.client, site.base_url, ADD_PATH, section_id)
    if f'gg="{type_id}"' not in page.html and f"gg='{type_id}'" not in page.html:
        raise WriteError(
            f"type {type_id} is not offered for section {section_id} (see `edu types`)"
        )
    values = dict(values or {})
    notes = ["new objects are unpublished"]
    if values:
        notes.append("fields are saved into each new object right after it is created")

    def do() -> dict:
        with site.lock:
            res = dialogs.submit(
                page,
                ("ctl00$AddButton$ButtonMake", "Создать"),
                {
                    MAIN + "Classifier": section_id,
                    MAIN + "SelType": type_id,
                    MAIN + "N_Count": str(count),
                },
            )
            ids = [i for i in res.values.get("Result_Value_1", "").split(";") if i]
            if res.status != "Exit_2" or len(ids) != count:
                raise WriteError(f"create not confirmed: {res.status!r} ids={ids} {res.messages}")
            out, unsaved = [], {}
            for oid in ids:
                time.sleep(site.delay)
                if values:
                    res = plan_update(site, oid, values).apply()
                    out.append(res["object"])
                    if not res["verified"]:
                        unsaved[oid] = res["mismatch"]
                else:
                    out.append(_summary(read_object(site.client, site.base_url, oid)))
        wrong = [o["id"] for o in out if o["section_id"] != section_id]
        return {
            "ids": ids,
            "objects": out,
            "verified": not wrong and not unsaved,
            "wrong_section": wrong,
            "fields_not_saved": unsaved,
        }

    return Change(
        "object.create",
        f"{count} object(s) of type {type_id} in section {section_id}",
        "edit",
        {k: (None, _norm(v)) for k, v in values.items()},
        notes,
        {"section": section_id, "type": type_id, "count": count, "values": values},
        do,
    )


# ---------- explorer toolbar actions ----------


def _objects_in_section(site: Site, ids: list[str]) -> tuple[str, list[ObjectData]]:
    objs = []
    for oid in ids:
        objs.append(read_object(site.client, site.base_url, oid))
        time.sleep(site.delay)
    sections = {o.section_id for o in objs}
    if len(sections) != 1 or "" in sections:
        raise WriteError(
            f"objects {ids} must all be in one section, they are in {sorted(sections)}"
        )
    return sections.pop(), objs


def _show_section(site: Site, section_id: str, ids: list[str]):
    ex = site.explorer()
    ex.find_section(section_id)
    ex.select_section(section_id)
    found = ex.find_in_list(set(ids))
    missing = [i for i in ids if i not in found]
    if missing:
        raise WriteError(f"objects {missing} not found in the list of section {section_id}")
    return ex


def plan_copy(site: Site, object_id: str) -> Change:
    """«Создать копию»: an unpublished copy in the same section (it gets a new id)."""
    section, (obj,) = _objects_in_section(site, [object_id])

    def do() -> dict:
        with site.lock:
            ex = _show_section(site, section, [object_id])
            before = {r.id for r in ex.objects(section)}
            ex.toolbar(
                "ctl00$ContentSecondMenu$ButtonObjectCopy", {"ctl00$Result_Value": object_id}
            )
            new = [r.id for r in ex.objects(section) if r.id not in before]
        return {"ids": new, "verified": len(new) == 1}

    return Change(
        "object.copy", _label(obj), "edit", {}, ["the copy is unpublished"], {"id": object_id}, do
    )


def plan_move(site: Site, ids: list[str], target_section: str) -> Change:
    """«Переместить объекты»: move objects of one section to another section."""
    section, objs = _objects_in_section(site, ids)
    if section == target_section:
        raise WriteError(f"objects are already in section {target_section}")
    published = any(o.published for o in objs)
    fields = {f"{o.id}.section": (o.section_id, target_section) for o in objs}

    def do() -> dict:
        with site.lock:
            ex = _show_section(site, section, ids)
            ex.find_section(target_section)  # must exist
            ex.toolbar(
                "ctl00$ContentSecondMenu$ButtonObjectMove",
                {
                    "ctl00$Result_Value_2": "|".join(ids) + "|",
                    "ctl00$Result_Value_3": target_section,
                },
            )
            after = []
            for oid in ids:
                time.sleep(site.delay)
                after.append(read_object(site.client, site.base_url, oid))
        wrong = [o.id for o in after if o.section_id != target_section]
        return {"ids": ids, "section": target_section, "verified": not wrong, "not_moved": wrong}

    return Change(
        "object.move",
        f"{len(ids)} object(s) from section {section} to {target_section}",
        "publish" if published else "edit",
        fields,
        ["published objects move on the public site too"] if published else [],
        {"ids": ids, "target": target_section},
        do,
    )


def plan_trash(site: Site, ids: list[str]) -> Change:
    """«Переместить в корзину»: objects go to their type's trash (restorable, see trash.py)."""
    section, objs = _objects_in_section(site, ids)
    fields = {f"{o.id}.section": (o.section_id, "trash") for o in objs}
    notes = [f"«{o.name[:50]}» ({o.type})" for o in objs]
    if any(o.published for o in objs):
        notes.append("published objects disappear from the public site")

    def do() -> dict:
        with site.lock:
            ex = _show_section(site, section, ids)
            ex.toolbar(
                "ctl00$ContentSecondMenu$ButtonObjectDel",
                {"ctl00$Result_Value": ids[0], "ctl00$Result_Value_2": "|".join(ids) + "|"},
            )
            left = {r.id for r in ex.find_in_list(set(ids)).values()}
            after = []
            for oid in ids:
                time.sleep(site.delay)
                after.append(read_object(site.client, site.base_url, oid))
        wrong = [o.id for o in after if o.section_id] + sorted(left)
        return {"ids": ids, "verified": not wrong, "not_trashed": wrong}

    return Change(
        "object.trash",
        f"{len(ids)} object(s) in section {section}",
        "delete",
        fields,
        notes,
        {"ids": ids},
        do,
    )


# ---------- sort ----------


def sort_order(page_html: str) -> list[str]:
    """Current order in ObjectsSort.aspx: `<div id='SortList'><span guid='<id>'>…` (the
    hidden `HiddenFieldForSave` is empty until the page's Save() fills it)."""
    i = page_html.find("id='SortList'")
    if i < 0:
        return []
    end = page_html.find("</div>", i)
    return re.findall(r"<span guid='(\d+)'", page_html[i:end])


def plan_sort(site: Site, section_id: str, order: list[str]) -> Change:
    """«Сортировать»: set the order of a section's objects (all ids, new order)."""
    page = dialogs.open_dialog(site.client, site.base_url, SORT_PATH, section_id)
    current = sort_order(page.html)
    if not current:
        raise WriteError(f"section {section_id}: the sort dialog lists no objects")
    if sorted(order) != sorted(current):
        raise WriteError(f"order must list exactly the section's objects: {';'.join(current)}")

    def do() -> dict:
        with site.lock:
            res = dialogs.submit(
                page, dialogs.SAVE_EXIT, {MAIN + "HiddenFieldForSave": ";".join(order) + ";"}
            )
            if res.status != "SaveExit":
                raise WriteError(f"sort not confirmed: {res.status!r} {res.messages}")
            ex = site.explorer()
            ex.find_section(section_id)
            ex.select_section(section_id)
            ex.toolbar("ctl00$ContentSecondMenu$ButtonObjectSort", {"ctl00$Result_Value": order[0]})
            time.sleep(site.delay)
            again = dialogs.open_dialog(site.client, site.base_url, SORT_PATH, section_id)
        now = sort_order(again.html)
        return {"order": now, "verified": now == order}

    return Change(
        "object.sort",
        f"objects of section {section_id}",
        "publish",
        {"order": (";".join(current), ";".join(order))},
        ["the order is visible on the public site at once"],
        {"section": section_id},
        do,
    )


# ---------- image upload ----------


def _thumbnail_type(site: Site, object_id: str) -> str:
    r = site.client.get(f"{site.base_url}/sm.aspx", params={"guid": object_id})
    return r.headers.get("content-type", "").split(";")[0]


def shrink_image(file: Path, out_dir: Path, limit: int = IMAGE_LIMIT) -> Path:
    """Re-encode a photo as JPEG small enough to upload (the server re-encodes to JPEG anyway).

    Longest side at most 1600 px, quality stepped down until the file is under `limit`.
    Returns `file` itself when it is already a small image.
    """
    from PIL import Image, ImageOps

    if file.stat().st_size <= limit and mimetypes.guess_type(file.name)[0] in IMAGE_TYPES:
        return file
    try:
        img = ImageOps.exif_transpose(Image.open(file))
    except Exception as e:  # not an image Pillow can read
        raise WriteError(f"{file.name}: can't read it as an image ({e})") from e
    if img.mode not in ("RGB", "L"):
        bg = Image.new("RGB", img.size, "white")
        bg.paste(img.convert("RGBA"), mask=img.convert("RGBA").getchannel("A"))
        img = bg
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / (file.stem + ".jpg")
    side = 1600
    while side >= 400:
        im = img.copy()
        im.thumbnail((side, side))
        for quality in (85, 75, 65, 55):
            im.save(out, "JPEG", quality=quality, optimize=True)
            if out.stat().st_size <= limit:
                return out
        side = int(side * 0.8)
    raise WriteError(f"{file.name}: could not shrink it under {limit} B")


def plan_upload_image(site: Site, object_id: str, file: Path) -> Change:
    """Upload an image into an image object (BinaryFrame.aspx). Documents can't be stored on
    the site – use a link card (type 734) with an external URL instead."""
    file = Path(file)
    if not file.is_file():
        raise WriteError(f"{file}: no such file")
    size = file.stat().st_size
    ctype = mimetypes.guess_type(file.name)[0] or ""
    if ctype not in IMAGE_TYPES:
        raise WriteError(
            f"{file.name}: only images upload ({ctype or 'unknown type'}); documents go on the "
            "site as an external link (type 734 card or <a> in HTML)"
        )
    if size > IMAGE_LIMIT:
        raise WriteError(f"{file.name}: {size} B is over the ~{IMAGE_LIMIT} B limit – shrink it")
    editor = dialogs.open_dialog(site.client, site.base_url, EDITOR_PATH, object_id)
    obj = parse_object_editor(object_id, editor.html)
    if f"BinaryFrame.aspx?guid={object_id}" not in editor.html:
        raise WriteError(f"{_label(obj)} has no file upload")
    time.sleep(site.delay)
    had = _thumbnail_type(site, object_id) == "image/jpeg"
    notes = ["replaces the current image"] if had else []
    if obj.published:
        notes.append("the object is published: the image is visible on the site at once")

    def do() -> dict:
        with site.lock:
            url = f"{site.base_url}{FRAME_PATH}?guid={object_id}"
            frame = WebFormPage.load(site.client, url)
            time.sleep(site.delay)
            r = site.client.post(
                url,
                data={**frame.fields, "ButtonSaveBinary": ""},
                files={"FileUploadIco": (file.name, file.read_bytes(), ctype)},
                headers={"Referer": url},
                timeout=max(site.settings.timeout, 180),
            )
            r.raise_for_status()
            time.sleep(site.delay)
            now = _thumbnail_type(site, object_id)
        return {
            "id": object_id,
            "thumbnail": f"/sm.aspx?guid={object_id}",
            "verified": now == "image/jpeg",
        }

    return Change(
        "object.upload_image",
        _label(obj),
        "publish" if obj.published else "edit",
        {"file": ("image" if had else "(none)", f"{file.name} ({size} B)")},
        notes,
        {"id": object_id, "file": file.name, "size": size},
        do,
    )
