"""Planned writes on sections (classifiers): add, edit properties, move, delete.

Requests from knowledge/endpoints/explorer.md (section toolbar) and dialogs.md
(ClassifierEditor, ClassifierMove). Page templates (`fk_Template`) are not changed here.
"""

from __future__ import annotations

import re
import time
from typing import Literal

from edu_by.api import dialogs
from edu_by.api.changes import Change, WriteError
from edu_by.site import Site

EDITOR_PATH = "/G_Data/ClassifierEditor.aspx"
MOVE_PATH = "/G_Data/ClassifierMove.aspx"
MAIN = "ctl00$Main$"
PROTECT = MAIN + "IsDelete"
TITLE_ON = MAIN + "title_ru_status"
NEW_NAME = "New"  # a fresh section's internal name
Position = Literal["above", "inside", "below"]
MOVE_TARGETS = {
    "above": "ctl00$Main$MoveUp",  # «Выше выбранного»
    "inside": "ctl00$Main$MoveRight",  # «Правее выбранного»
    "below": "ctl00$Main$MoveDown",  # «Ниже выбранного»
}


def read_section(site: Site, section_id: str) -> dict:
    page = dialogs.open_dialog(site.client, site.base_url, EDITOR_PATH, section_id)
    return _props(section_id, page.fields)


def _props(section_id: str, f: dict[str, str]) -> dict:
    if MAIN + "Name" not in f:
        raise WriteError(f"section {section_id}: editor form not found (wrong id or no access?)")
    return {
        "id": section_id,
        "name": f.get(MAIN + "Name", ""),
        "title": f.get(MAIN + "title_ru", ""),
        "title_enabled": TITLE_ON in f,
        "protected": PROTECT in f,
        "template": f.get(MAIN + "fk_Template", ""),
        "redirect": f.get(MAIN + "StatusDirectLink", ""),
        "tags": f.get(MAIN + "Tags", ""),
    }


def _apply_props(fields: dict[str, str], title, name, protected, tags) -> None:
    if title is not None:
        fields[MAIN + "title_ru"] = title
    if name is not None:
        fields[MAIN + "Name"] = name
    if tags is not None:
        fields[MAIN + "Tags"] = tags
    if protected is True:
        fields[PROTECT] = "on"
    elif protected is False:
        fields.pop(PROTECT, None)


def _diff(before: dict, title, name, protected, tags) -> dict:
    want = {"title": title, "name": name, "protected": protected, "tags": tags}
    return {k: (before[k], v) for k, v in want.items() if v is not None}


def plan_update(
    site: Site,
    section_id: str,
    title: str | None = None,
    name: str | None = None,
    protected: bool | None = None,
    tags: str | None = None,
) -> Change:
    """Edit a section's title (Russian), internal name, delete protection or tags."""
    page = dialogs.open_dialog(site.client, site.base_url, EDITOR_PATH, section_id)
    before = _props(section_id, page.fields)
    fields = _diff(before, title, name, protected, tags)
    notes = []
    if title is not None:
        notes.append("the title shows in the site menu and page headings at once")
    if protected is False:
        notes.append("removes the protection from deletion")

    def do() -> dict:
        with site.lock:
            _apply_props(page.fields, title, name, protected, tags)
            res = dialogs.submit(page, dialogs.SAVE_EXIT)
            if res.status != "SaveExit":
                raise WriteError(f"save of section {section_id} not confirmed: {res.status!r}")
            _refresh(site, section_id)
            time.sleep(site.delay)
            after = read_section(site, section_id)
        bad = {k: after[k] for k, (_, v) in fields.items() if after[k] != v}
        return {"section": after, "verified": not bad, "mismatch": bad}

    return Change(
        "section.update",
        f"section {section_id} «{before['title'] or before['name']}»",
        "publish" if title is not None else "edit",
        fields,
        notes,
        {"id": section_id, "title": title, "name": name, "protected": protected, "tags": tags},
        do,
    )


def _refresh(site: Site, section_id: str) -> None:
    """The UI's explorer refresh after ClassifierEditor closed («Изменить»)."""
    ex = site.explorer()
    if ex.current == section_id:
        ex.main_menu("ctl00$ContentMainMenu$MyButtonEditClassifier")
        sec = ex.sections.get(section_id)
        for n in ex.nodes():
            if sec and n.id == section_id and n.title:
                sec.title = n.title


def plan_add(site: Site, parent_id: str, title: str, protected: bool = True) -> Change:
    """«Добавить новый»: a child section at the end of `parent_id`, with a title.

    The constructor creates the section (named `New`) at once, then the title is saved.
    """
    ex = site.explorer()
    parent = ex.find_section(parent_id)
    notes = [
        "the section is created as soon as this runs; it may appear in the site menu and map",
        "its objects and subsections are added separately",
    ]

    def do() -> dict:
        with site.lock:
            ex.select_section(parent.id)
            ex.main_menu("ctl00$ContentMainMenu$MyButtonAddClassifier")
            new_id = ex.current
            if not new_id or new_id == parent.id:
                raise WriteError("the constructor did not create a section")
            time.sleep(site.delay)
            page = dialogs.open_dialog(site.client, site.base_url, EDITOR_PATH, new_id)
            if page.fields.get(MAIN + "Name") != NEW_NAME:
                raise WriteError(f"section {new_id} is not a fresh one – stopped before saving")
            _apply_props(page.fields, title, title, protected, None)
            time.sleep(site.delay)
            res = dialogs.submit(page, dialogs.SAVE_EXIT)
            if res.status != "SaveExit":
                raise WriteError(f"section {new_id} created but its title was not saved")
            _refresh(site, new_id)
            time.sleep(site.delay)
            after = read_section(site, new_id)
        sec = ex.sections.get(new_id)
        return {
            "section": after,
            "path": "/".join(sec.path) if sec else None,
            "verified": after["title"] == title,
        }

    return Change(
        "section.add",
        f"new section «{title}» under {parent.id} «{parent.title}» ({'/'.join(parent.path)})",
        "publish",
        {"title": (None, title), "protected": (None, protected)},
        notes,
        {"parent": parent.id, "title": title, "protected": protected},
        do,
    )


def plan_move(site: Site, section_id: str, target_id: str, position: Position = "inside") -> Change:
    """ClassifierMove: put a section `above` / `below` the target (same parent) or `inside` it."""
    if position not in MOVE_TARGETS:
        raise WriteError(f"position must be one of {', '.join(MOVE_TARGETS)}")
    ex = site.explorer()
    sec = ex.find_section(section_id)
    section_id = sec.id  # the caller may pass an id path
    target = ex.find_section(target_id)
    if section_id in target.path:
        raise WriteError("a section can't be moved into itself or its own subsection")
    new_parent = target.id if position == "inside" else target.parent_id
    notes = ["the section moves on the public site together with its subsections and objects"]

    def do() -> dict:
        with site.lock:
            page = dialogs.open_dialog(site.client, site.base_url, MOVE_PATH, section_id)
            dialogs.tree_select(page, target.path, site.delay)
            time.sleep(site.delay)
            records = page.async_postback(
                dialogs.DIALOG_SM, dialogs.DIALOG_PANEL, MOVE_TARGETS[position]
            )
            if any(r.type == "error" for r in records):
                raise WriteError("the move was refused by the server")
            ex.forget(section_id)
            site.reset_explorer()
            ex2 = site.explorer()
            parent_path = target.path if position == "inside" else target.path[:-1]
            if parent_path:
                ex2.find_path(parent_path)
                ex2.select_section(parent_path[-1])
            moved = ex2.sections.get(section_id)
        ok = moved is not None and moved.parent_id == new_parent
        return {
            "section": section_id,
            "path": "/".join(moved.path) if moved else None,
            "verified": ok,
        }

    return Change(
        "section.move",
        f"section {section_id} «{sec.title}» ({'/'.join(sec.path)})",
        "publish",
        {
            "parent": (sec.parent_id, new_parent),
            "place": (None, f"{position} {target.id} «{target.title}»"),
        },
        notes,
        {"id": section_id, "target": target.id, "position": position},
        do,
    )


def delete_info(site: Site, section_id: str) -> str:
    r = site.client.post(
        f"{site.base_url}/SystemWJG.asmx/IsDelClassifier", json={"guid": section_id}
    )
    r.raise_for_status()
    return r.json().get("d") or ""


def plan_delete(site: Site, section_id: str) -> Change:
    """«Удалить» a section without subsections. Its objects go to the trash of their types;
    the section itself can't be restored. A protected section must be unprotected first."""
    ex = site.explorer()
    sec = ex.find_section(section_id)
    section_id = sec.id  # the caller may pass an id path
    if sec.parent_id is None:
        raise WriteError("root sections are not deleted by this tool")
    props = read_section(site, section_id)
    if props["protected"]:
        raise WriteError(
            f"section {section_id} is protected from deletion; remove the protection first "
            "(`edu section set --unprotect`), then plan the delete again"
        )
    ex.select_section(section_id)
    time.sleep(site.delay)
    info = delete_info(site, section_id)
    m_sub = re.search(r"Подклассификаторов:\s*(\d+)", info)
    m_obj = re.search(r"Объектов:\s*(\d+)", info)
    subs = int(m_sub.group(1)) if m_sub else None
    objs = int(m_obj.group(1)) if m_obj else None
    if subs is None or objs is None:
        raise WriteError(f"unexpected IsDelClassifier answer: {info!r}")
    if subs:
        raise WriteError(
            f"section {section_id} has {subs} subsection(s); delete or move them first"
        )
    notes = [
        "the section itself is deleted for good (there is no section trash)",
        f"its {objs} object(s) go to the trash of their types (restorable, without a section)",
    ]

    def do() -> dict:
        with site.lock:
            ex.select_section(section_id)
            ex.main_menu_submit("ctl00$ContentMainMenu$MyButtonDelClassifierAll")
            gone = not any(n.id == section_id for n in ex.nodes())
            ex.forget(section_id)
        return {"section": section_id, "current": ex.current, "verified": gone}

    return Change(
        "section.delete",
        f"section {section_id} «{sec.title}» ({'/'.join(sec.path)})",
        "delete",
        {
            "section": (sec.title, None),
            "objects": (f"{objs} in the section", f"{objs} in the trash"),
        },
        notes,
        {"id": section_id},
        do,
    )
