"""Trash («Корзина объектов»): list, restore, permanent delete – one trash per object type.

knowledge/endpoints/explorer.md, section Trash. Other people's deleted objects live in the
same trash, so restore and purge only ever take explicitly named ids, never "all".
"""

from __future__ import annotations

from dataclasses import asdict

from edu_by.api.changes import Change, WriteError
from edu_by.api.explorer import ObjectRow, parse_pages
from edu_by.site import Site

MAX_PURGE = 50


def list_trash(site: Site, type_id: str, page: int = 0) -> dict:
    """One page of a type's trash (newest first) and the number of pages offered."""
    ex = site.explorer()
    ex.select_trash(type_id)
    current, pages = parse_pages(ex.pager_html)
    if (current or 0) != page:
        from edu_by.api.explorer import PAGER_PANEL, PAGER_TARGET

        ex._postback(PAGER_PANEL, PAGER_TARGET, "", {PAGER_TARGET: str(page)})
        current, pages = parse_pages(ex.pager_html)
    return {
        "type": type_id,
        "page": current or 0,
        "last_page": max(pages) if pages else 0,
        "objects": [asdict(r) for r in ex.rows()],
    }


def _find(site: Site, type_id: str, ids: list[str], max_pages: int) -> dict[str, ObjectRow]:
    ex = site.explorer()
    ex.select_trash(type_id)
    found = ex.find_in_list(set(ids), max_pages=max_pages)
    missing = [i for i in ids if i not in found]
    if missing:
        raise WriteError(
            f"objects {missing} not found in the first {max_pages} page(s) of trash {int(type_id) + 1}"
        )
    return found


def _check_ids(ids: list[str]) -> None:
    if not ids or not all(i.isdigit() for i in ids):
        raise WriteError("name the objects by id")
    if len(ids) > MAX_PURGE:
        raise WriteError(f"at most {MAX_PURGE} objects at a time")


def plan_restore(
    site: Site, type_id: str, ids: list[str], section_id: str, max_pages: int = 20
) -> Change:
    """«Восстановить объекты»: move objects from a type's trash into a section."""
    _check_ids(ids)
    found = _find(site, type_id, ids, max_pages)
    target = site.explorer().find_section(section_id)

    def do() -> dict:
        from edu_by.api.objects import read_object

        with site.lock:
            ex = site.explorer()
            ex.select_trash(type_id)
            ex.find_in_list(set(ids), max_pages=max_pages)
            ex.toolbar(
                "ctl00$ContentSecondMenu$ButtonObjectMove",
                {"ctl00$Result_Value_2": "|".join(ids) + "|", "ctl00$Result_Value_3": target.id},
            )
            wrong = [
                o for o in ids if read_object(site.client, site.base_url, o).section_id != target.id
            ]
        return {"ids": ids, "section": target.id, "verified": not wrong, "not_restored": wrong}

    return Change(
        "trash.restore",
        f"{len(ids)} object(s) from trash {int(type_id) + 1} into section {target.id} «{target.title}»",
        "edit",
        {f"{i}.section": ("trash", target.id) for i in ids},
        [f"{r.id}: {r.type_label}: {r.title[:60]}" for r in found.values()]
        + ["restored objects keep their publication flag"],
        {"type": type_id, "ids": ids, "section": target.id},
        do,
    )


def plan_purge(site: Site, type_id: str, ids: list[str], max_pages: int = 20) -> Change:
    """«Удалить объекты» in a trash: permanent, irreversible delete of the named objects."""
    _check_ids(ids)
    found = _find(site, type_id, ids, max_pages)

    def do() -> dict:
        from edu_by.api.objects import ObjectError, read_object

        with site.lock:
            ex = site.explorer()
            ex.select_trash(type_id)
            ex.find_in_list(set(ids), max_pages=max_pages)
            ex.toolbar(
                "ctl00$ContentSecondMenu$ButtonObjectDel",
                {"ctl00$Result_Value_2": "|".join(ids) + "|"},
            )
            alive = []
            for oid in ids:
                try:
                    read_object(site.client, site.base_url, oid)
                    alive.append(oid)
                except ObjectError:
                    pass  # "No object" – deleted
        return {"ids": ids, "verified": not alive, "still_there": alive}

    return Change(
        "trash.purge",
        f"{len(ids)} object(s) in trash {int(type_id) + 1}",
        "delete",
        {f"{i}": ("in trash", "deleted for good") for i in ids},
        [f"{r.id}: {r.type_label}: {r.title[:60]}" for r in found.values()]
        + ["IRREVERSIBLE: the objects can't be restored afterwards"],
        {"type": type_id, "ids": ids},
        do,
    )
