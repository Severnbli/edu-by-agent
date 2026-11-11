"""Site design (RengerProvider): read and plan writes of templates, modules, style sets,
scripts and resource strings, clear the site cache, export the design archive.

Requests are the ones in knowledge/endpoints/design.md (captures design-2026-11-10 and
design2-2026-11-11, live tests 2026-11-11). Every design save is **site-wide** for an item in
use: there is no draft. Plans only read; `Change.apply()` writes and re-reads.

Two fields are filled by the page's JS before a save and are empty in the GET – a tool that
posts the GET value would wipe them:
- templates: `HiddenFieldForSave` = checked items of `#ListJS`, then `#ListCss`, in list order;
- modules: section lists (`ASD_ClassifierList`, `ListClasifier`, …) = `id;` per
  `T_Add('<field>','<id>','<title>')` call of the startup script;
- Главный / Обычный / 404 templates: `ClassifierL` («Классификаторы») = the sections that
  use the template, filled the same way. Posted empty it **detaches them all** (they fall
  back to «0», inherit) – seen live 2026-11-11 on a copy.
All are rebuilt here from the GET; a write is refused when they can't be read.
"""

from __future__ import annotations

import html as html_lib
import re
import time
from dataclasses import dataclass, field

from edu_by.api import dialogs
from edu_by.api.changes import Change, WriteError
from edu_by.site import Site
from edu_by.webforms import WebFormPage, parse_delta, parse_form

MAIN = "ctl00$Main$"
SM = "ctl00$ScriptManagerWindow"
MENU = "ctl00$ContentSecondMenu$"
TEMPLATE_SECTIONS = "ClassifierL"  # template «Классификаторы»: the sections using it
TEMPLATE_CATEGORIES = ("Master", "Head", "Normal", "404", "NotUseTemplate")
CONTROL_CATEGORIES = ("Actual", "Old", "NotUse")
CATEGORIES = (
    *TEMPLATE_CATEGORIES,
    *CONTROL_CATEGORIES,
    "CssPacked",
    "JavaScript",
    "ResourceString",
    "TemplateGlobal",
)
# Only items whose name starts like this may be deleted without `force` (a delete is
# immediate, no trash; on 2026-11-11 a wrong row selection deleted an original template).
SAFE_DELETE_PREFIXES = ("Редизайн", "Тест")


@dataclass(frozen=True)
class Kind:
    dialog: str  # G_RengerProvider/<dialog>.aspx and Open('<dialog>', …)
    categories: tuple[str, ...]  # category pages that list it (and carry its toolbar)
    name_field: str
    copy: str
    delete: str
    add: str | None = None


KINDS: dict[str, Kind] = {
    "template": Kind(
        "Templates", TEMPLATE_CATEGORIES, "TextBoxTitle_text", "TemplateCopy", "TemplateDel"
    ),
    "control": Kind(
        "Controls", CONTROL_CATEGORIES, "TextBoxTitle_text", "ControlCopy", "ControlDel"
    ),
    "css": Kind("CssPacked", ("CssPacked",), "TextBoxName_text", "CSSCopy", "CSSDel", "CSSAdd"),
    "js": Kind("JavaScript", ("JavaScript",), "TextBoxName_text", "JSCopy", "JSDel", "JSAdd"),
    "string": Kind(
        "ResourceString",
        ("ResourceString",),
        "S_Title_text",
        "MyButtonCopyResource",
        "MyButtonDelResource",
    ),
}

# Short names of template fields -> form field (without ctl00$Main$).
TEMPLATE_FIELDS = {
    "title": "TextBoxTitle_text",
    "master": "MasterList",
    "head": "Head_Content$TextBoxRes",
    "body": "Body_Content$TextBoxRes",
    **{f"body{n}": f"Body_Content_{n}$TextBoxRes" for n in range(1, 10)},
}
ITEM_FIELDS = {"name": "TextBoxName_text", "body": "TextBoxBody"}  # css, js
STRING_FIELDS = {"title": "S_Title_text"}  # + one textarea per language, `text` = the first

_ROW = re.compile(r"<tr\s+class='line'\s+id='obj_(\d+)'\s*>(.*?)</tr>", re.S)
_OPEN = re.compile(r"Open\('(\w+)',this,'(\d+)'\)")
_LIST_ITEM = re.compile(r"<div gg='(\d+)'><input type='checkbox'( checked='checked')?\s*/?>([^<]*)")
_T_INIT = re.compile(r"T_Init\('(\w+)'\)")
_T_ADD = re.compile(r"T_Add\('(\w+)','(\d+)','((?:[^'\\]|\\.)*)'\)")


def _text(fragment: str) -> str:
    return re.sub(r"\s+", " ", html_lib.unescape(re.sub(r"<[^>]+>", " ", fragment))).strip()


def _norm(v: str) -> str:
    return v.replace("\r\n", "\n").strip("\n")


def _squash(v: str) -> str:
    """Whitespace-free form: the server re-spaces `LoadModule(…)` calls on every save."""
    return re.sub(r"\s+", "", v)


def kind_of(kind: str) -> Kind:
    if kind not in KINDS:
        raise WriteError(f"unknown kind {kind!r}; one of: {', '.join(KINDS)}")
    return KINDS[kind]


# ---------- category pages ----------


def guid_session(site: Site) -> str:
    gs = site.explorer().page.fields.get("ctl00$GuidSession", "")
    if not gs:
        raise WriteError("no GuidSession on the explorer page – session expired?")
    return gs


def open_category(site: Site, category: str) -> WebFormPage:
    if category not in CATEGORIES:
        raise WriteError(f"unknown category {category!r}; one of: {', '.join(CATEGORIES)}")
    url = f"{site.base_url}/RengerProvider.aspx?guid={category}&gs={guid_session(site)}"
    page = WebFormPage.load(site.client, url)
    if 'type="password"' in page.html.lower():
        raise WriteError("got the login page – session expired")
    return page


def parse_category(page_html: str) -> list[dict]:
    """Rows of a category page: id, title and the dialog that opens it."""
    out = []
    for item_id, row in _ROW.findall(page_html):
        m = _OPEN.search(html_lib.unescape(row))
        out.append({"id": item_id, "title": _text(row), "dialog": m.group(1) if m else ""})
    return out


def list_category(site: Site, category: str) -> list[dict]:
    return parse_category(open_category(site, category).html)


def find_category(site: Site, kind: str, item_id: str) -> tuple[str, str]:
    """(category, title) of an item, from the first category page that lists it."""
    for cat in kind_of(kind).categories:
        for row in list_category(site, cat):
            if row["id"] == str(item_id):
                return cat, row["title"]
        time.sleep(site.delay)
    raise WriteError(f"{kind} {item_id} is not listed in {', '.join(kind_of(kind).categories)}")


def category_action(site: Site, category: str, target: str, item_id: str = "") -> tuple[str, str]:
    """Toolbar postback (copy / delete / add) on a category page: (Result_Status, Result_Value)."""
    page = open_category(site, category)
    time.sleep(site.delay)
    records = page.async_postback(SM, SM, MENU + target, extra={"ctl00$Result_Value": str(item_id)})
    status = value = ""
    for rec in records:
        if rec.type == "error":
            raise WriteError(f"{target} {item_id}: server error {rec.content[:200]}")
        if rec.type == "updatePanel":
            f = parse_form(rec.content)
            status = f.get("ctl00$Result_Status", status)
            value = f.get("ctl00$Result_Value", value)
    return status, html_lib.unescape(value)


def _new_id(value: str, dialog: str) -> str:
    m = re.search(r"Open\('" + dialog + r"',this,'(\d+)'\)", value) or re.search(
        r"id='obj_(\d+)'", value
    )
    if not m:
        raise WriteError(f"no new id in the reply: {value[:200]!r}")
    return m.group(m.lastindex or 1)


# ---------- dialogs: read ----------


@dataclass
class DesignItem:
    kind: str
    id: str
    title: str
    page: WebFormPage = field(repr=False)
    fields: dict[str, str] = field(default_factory=dict)  # short name -> value
    form: dict[str, str] = field(default_factory=dict)  # short name -> form field name
    # templates
    master: str | None = None
    masters: dict[str, str] = field(default_factory=dict)  # id -> title (MasterList options)
    js: list[str] = field(default_factory=list)  # attached, in order
    css: list[str] = field(default_factory=list)
    all_js: dict[str, str] = field(default_factory=dict)  # id -> name, every script
    all_css: dict[str, str] = field(default_factory=dict)
    # modules
    lists: dict[str, list[str]] = field(default_factory=dict)  # JS-filled section lists
    checkboxes: set[str] = field(default_factory=set)  # short names; value "on" or ""

    def summary(self, full: bool = False) -> dict:
        limit = None if full else 400

        def cut(v: str) -> str:
            return v if limit is None or len(v) <= limit else f"{v[:limit]}… ({len(v)} chars)"

        d = {
            "kind": self.kind,
            "id": self.id,
            "title": self.title,
            "fields": {k: cut(v) for k, v in self.fields.items()},
        }
        if self.kind == "template":
            d.update(
                master=self.master,
                masters=self.masters,
                js=[f"{i} {self.all_js.get(i, '')}" for i in self.js],
                css=[f"{i} {self.all_css.get(i, '')}" for i in self.css],
            )
        if self.kind == "control" or self.lists:
            d["lists"] = self.lists  # a template's ClassifierL = the sections using it
        return d


def parse_sort_list(page_html: str, name: str) -> tuple[list[str], dict[str, str]] | None:
    """(checked ids in order, all id -> name) of `<div id="<name>" class="SortList">`, or None."""
    m = re.search(r'id="' + name + r'" class="SortList">', page_html)
    if not m:
        return None
    rest = page_html[m.end() :]
    items, pos = [], 0
    while True:
        it = _LIST_ITEM.match(rest, pos)
        if not it:
            break
        items.append(it)
        end = rest.find("</div>", it.end())
        pos = end + len("</div>") if end >= 0 else it.end()
    checked = [i.group(1) for i in items if i.group(2)]
    return checked, {i.group(1): html_lib.unescape(i.group(3)).strip() for i in items}


def template_hidden(js: list[str], css: list[str]) -> str:
    """`HiddenFieldForSave` as the page's JS builds it."""
    return "".join(f'<js value="{i}"/>' for i in js) + "".join(f'<css value="{i}"/>' for i in css)


def control_lists(page_html: str) -> dict[str, list[str]]:
    """Section lists of a module dialog, as its JS fills them on load."""
    lists: dict[str, list[str]] = {n: [] for n in _T_INIT.findall(page_html)}
    for name, item_id, _title in _T_ADD.findall(page_html):
        lists.setdefault(name, []).append(item_id)
    return lists


def read_item(site: Site, kind: str, item_id: str) -> DesignItem:
    k = kind_of(kind)
    page = dialogs.open_dialog(
        site.client, site.base_url, f"/G_RengerProvider/{k.dialog}.aspx", str(item_id)
    )
    f = page.fields
    if MAIN + k.name_field not in f:
        raise WriteError(f"{kind} {item_id}: dialog has no {k.name_field} (wrong id or kind?)")
    item = DesignItem(kind, str(item_id), f[MAIN + k.name_field], page)

    if kind == "template":
        for short, name in TEMPLATE_FIELDS.items():
            if MAIN + name in f:
                item.form[short] = name
                item.fields[short] = f[MAIN + name]
        sel = re.search(r'<select name="ctl00\$Main\$MasterList".*?</select>', page.html, re.S)
        if sel:
            item.masters = {
                v: _text(t)
                for v, t in re.findall(
                    r'<option[^>]*value="(\d+)"[^>]*>(.*?)</option>', sel.group(0)
                )
            }
            item.master = f.get(MAIN + "MasterList")
        js, css = parse_sort_list(page.html, "ListJS"), parse_sort_list(page.html, "ListCss")
        if js is None or css is None:
            raise WriteError(
                f"template {item_id}: the CSS / JS lists are not on the page – refusing "
                "(a save without them would detach every style set and script)"
            )
        (item.js, item.all_js), (item.css, item.all_css) = js, css
        item.lists = control_lists(page.html)
        if MAIN + TEMPLATE_SECTIONS in f and TEMPLATE_SECTIONS not in item.lists:
            raise WriteError(
                f"template {item_id}: its section list ({TEMPLATE_SECTIONS}) is not on the "
                "page – refusing (a save without it would detach every section using it)"
            )
    elif kind == "control":
        for name, value in f.items():
            if not name.startswith(MAIN) or name.endswith("ClientState"):
                continue
            short = name[len(MAIN) :]
            short = "title" if short == "TextBoxTitle_text" else short
            item.form[short] = name[len(MAIN) :]
            item.fields[short] = value
        for name in _checkbox_names(page.html):
            short = name[len(MAIN) :]
            item.checkboxes.add(short)
            item.form.setdefault(short, short)
            item.fields.setdefault(short, "")  # unchecked boxes are not in the form
        item.lists = control_lists(page.html)
        for name, ids in item.lists.items():
            if name in item.fields:
                item.fields[name] = "".join(f"{i};" for i in ids)
    elif kind in ("css", "js"):
        for short, name in ITEM_FIELDS.items():
            item.form[short] = name
            item.fields[short] = f.get(MAIN + name, "")
    elif kind == "string":
        item.form["title"] = STRING_FIELDS["title"]
        item.fields["title"] = f[MAIN + STRING_FIELDS["title"]]
        langs = [n for n in f if n.startswith(MAIN) and re.fullmatch(r"ctl\d+", n[len(MAIN) :])]
        for i, name in enumerate(langs):
            short = "text" if i == 0 else name[len(MAIN) :]
            item.form[short] = name[len(MAIN) :]
            item.fields[short] = f[name]
    return item


_CHECKBOX = re.compile(r"<input\b[^>]*>", re.I)


def _checkbox_names(page_html: str) -> list[str]:
    """Names of the dialog's checkboxes (checked or not), in page order."""
    out = []
    for tag in _CHECKBOX.findall(page_html):
        if re.search(r'type="checkbox"', tag, re.I):
            m = re.search(r'name="(ctl00\$Main\$[^"]+)"', tag)
            if m and m.group(1) not in out:
                out.append(m.group(1))
    return out


LANG_BOX = "CheckBoxListAccess$"  # module «Язык:» boxes, one per site language

_ON, _OFF = {"on", "1", "true", "yes"}, {"", "off", "0", "false", "no"}


def _checkbox_value(item: DesignItem, short: str, value: str) -> str:
    v = str(value).strip().lower()
    if v in _ON:
        return "on"
    if v in _OFF:
        return ""
    raise WriteError(f"{_label(item)}: {short} is a checkbox – give on / off, not {value!r}")


# ---------- writes ----------


def _label(item: DesignItem) -> str:
    return f"{item.kind} {item.id} «{item.title[:70]}»"


def _post_fields(item: DesignItem) -> dict[str, str]:
    """The fields a save must carry besides the GET ones (what the page's JS fills)."""
    extra: dict[str, str] = {}
    if item.kind == "template":
        extra[MAIN + "HiddenFieldForSave"] = template_hidden(item.js, item.css)
    if item.kind in ("control", "template"):
        for name, ids in item.lists.items():
            extra[MAIN + name] = "".join(f"{i};" for i in ids)
    return extra


def _check_ids(ids: list[str], known: dict[str, str], what: str, item_id: str) -> None:
    unknown = [i for i in ids if str(i) not in known]
    if unknown:
        raise WriteError(f"template {item_id}: no {what} {unknown} on this site")


def plan_set(
    site: Site,
    kind: str,
    item_id: str,
    values: dict[str, str] | None = None,
    attach_css: list[str] | None = None,
    detach_css: list[str] | None = None,
    attach_js: list[str] | None = None,
    detach_js: list[str] | None = None,
) -> Change:
    """Save fields of a design item (others keep their values) and, for a template, attach
    or detach style sets / scripts (attached ones go last, i.e. load after the others).

    Field names (`values` keys): template `title`, `master`, `head`, `body`, `body1`…;
    module `title`, `Text_Before`, `Text_After`, `WhereUse`, `ASD_<setting>` (see `show`;
    checkboxes take `on` / `off`, an unchecked one is left out of the post);
    css / js `name`, `body`; string `title`, `text`.
    """
    values = dict(values or {})
    item = read_item(site, kind, item_id)
    unknown = [k for k in values if k not in item.form]
    if unknown:
        raise WriteError(
            f"{_label(item)} has no field(s) {unknown}; fields: {', '.join(item.form)}"
        )
    bad = [k for k in values if k in item.lists]
    if bad:
        raise WriteError(f"section lists {bad} can't be set here yet (ids `1011;` …)")
    for k in values:
        if k in item.checkboxes:
            values[k] = _checkbox_value(item, k, values[k])
    if kind == "template" and "master" in values and values["master"] not in item.masters:
        raise WriteError(f"template {item_id}: master {values['master']} is not offered")
    fields = {k: (_norm(item.fields[k]), _norm(v)) for k, v in values.items()}

    js, css = list(item.js), list(item.css)
    if kind == "template":
        for ids, known, what in (
            (attach_css or [], item.all_css, "style set"),
            (detach_css or [], item.all_css, "style set"),
            (attach_js or [], item.all_js, "script"),
            (detach_js or [], item.all_js, "script"),
        ):
            _check_ids([str(i) for i in ids], known, what, item_id)
        css = [i for i in css if i not in {str(x) for x in detach_css or []}]
        css = [i for i in css if i not in {str(x) for x in attach_css or []}]
        css += [str(i) for i in attach_css or []]
        js = [i for i in js if i not in {str(x) for x in detach_js or []}]
        js = [i for i in js if i not in {str(x) for x in attach_js or []}]
        js += [str(i) for i in attach_js or []]
        if css != item.css:
            fields["css"] = (item.css, css)
        if js != item.js:
            fields["js"] = (item.js, js)
    elif attach_css or detach_css or attach_js or detach_js:
        raise WriteError("only templates attach style sets and scripts")
    if not fields:
        raise WriteError("nothing to change: give field values or CSS / JS to attach / detach")

    notes = [
        "design items are site-wide: if this one is in use, every page using it changes at once"
    ]
    if kind == "template" and ("head" in values or any(k.startswith("body") for k in values)):
        notes.append("the server re-spaces LoadModule(…) calls; the check ignores whitespace")
    if kind == "template" and "master" in values:
        notes.append(
            "a new master changes the page frame of every section using this template; "
            "its body parts follow the new master's placeholders"
        )

    def do() -> dict:
        with site.lock:
            page = item.page
            extra = _post_fields(item)
            if kind == "template":
                extra[MAIN + "HiddenFieldForSave"] = template_hidden(js, css)
            for k, v in values.items():
                if k in item.checkboxes and not v:
                    page.fields.pop(MAIN + item.form[k], None)  # unchecked = not posted
                    continue
                extra[MAIN + item.form[k]] = v
            res = dialogs.submit(page, dialogs.SAVE, extra)
            if res.status != "Save":
                raise WriteError(
                    f"save of {_label(item)} not confirmed: {res.status!r} {res.messages}"
                )
            time.sleep(site.delay)
            after = read_item(site, kind, item_id)
            got: dict[str, object] = {k: _norm(after.fields.get(k, "")) for k in values}
            ok = all(
                got[k] == _norm(v) or _squash(str(got[k])) == _squash(_norm(v))
                for k, v in values.items()
            )
            if kind == "template":
                got["css"], got["js"] = after.css, after.js
                ok = ok and after.css == css and after.js == js
            if after.lists != item.lists:  # section lists must survive every save
                ok = False
                got["lists"] = {"before": item.lists, "after": after.lists}
            return {"verified": ok, "now": {k: _short(v) for k, v in got.items()}}

    return Change(
        action=f"design.{kind}.set",
        target=_label(item),
        level="publish",
        fields=fields,
        notes=notes,
        params={"kind": kind, "id": str(item_id), "values": values},
        _do=do,
    )


def _short(v: object) -> object:
    return v if not isinstance(v, str) or len(v) <= 300 else f"{v[:300]}… ({len(v)} chars)"


def plan_copy(site: Site, kind: str, item_id: str, name: str) -> Change:
    """«Создать копию» of a design item, then name the copy. The copy is used nowhere until
    a template / section points at it, so this changes nothing on the public site."""
    if not name.strip():
        raise WriteError("give the copy a name (e.g. «Редизайн 2026. Основной мастер»)")
    k = kind_of(kind)
    category, title = find_category(site, kind, item_id)
    item = read_item(site, kind, item_id)
    target = f"{kind} {item_id} «{title[:70]}» (from {category})"

    def do() -> dict:
        with site.lock:
            status, value = category_action(site, category, k.copy, item_id)
            if status not in ("Copy", "Control_Copy"):
                raise WriteError(f"copy of {target} not confirmed: {status!r} {value[:200]!r}")
            new_id = _new_id(value, k.dialog)
            time.sleep(site.delay)
            copy = read_item(site, kind, new_id)
            extra = {**_post_fields(copy), MAIN + k.name_field: name}
            # «Язык» boxes (CheckBoxListAccess$<n>) come unchecked on a module copy, and a
            # module without its language renders nothing on the public pages (2026-11-11)
            for f in sorted(item.checkboxes):
                if f.startswith(LANG_BOX) and item.fields.get(f) == "on":
                    extra[MAIN + f] = "on"
            res = dialogs.submit(copy.page, dialogs.SAVE, extra)
            if res.status != "Save":
                raise WriteError(f"copy {new_id} made, but naming it failed: {res.status!r}")
            time.sleep(site.delay)
            after = read_item(site, kind, new_id)
            same = {
                f: _squash(_norm(after.fields.get(f, ""))) == _squash(_norm(v))
                for f, v in item.fields.items()
                if f not in ("title", "name")
            }
            ok = after.title == name and all(same.values())
            if kind == "template":
                ok = ok and after.css == item.css and after.js == item.js
            return {"verified": ok, "new_id": new_id, "name": after.title, "same_content": same}

    return Change(
        action=f"design.{kind}.copy",
        target=target,
        level="edit",
        fields={"copy": ("", name)},
        notes=["a new item, used nowhere until something points at it"],
        params={"kind": kind, "id": str(item_id), "name": name},
        _do=do,
    )


def plan_create(site: Site, kind: str, name: str, body: str = "") -> Change:
    """A new style set or script (`CSSAdd` / `JSAdd`) with a name and text. Attach it to a
    template with `plan_set(..., attach_css=[id])` – until then it is used nowhere."""
    k = kind_of(kind)
    if not k.add or kind not in ("css", "js"):
        raise WriteError("only style sets (css) and scripts (js) can be created")
    if not name.strip():
        raise WriteError("give the new item a name")
    category = k.categories[0]
    open_category(site, category)  # session / access check before the preview

    def do() -> dict:
        with site.lock:
            status, value = category_action(site, category, k.add)
            if status != "Add":
                raise WriteError(f"{kind} add not confirmed: {status!r} {value[:200]!r}")
            new_id = _new_id(value, k.dialog)
            time.sleep(site.delay)
            item = read_item(site, kind, new_id)
            res = dialogs.submit(
                item.page,
                dialogs.SAVE,
                {MAIN + ITEM_FIELDS["name"]: name, MAIN + ITEM_FIELDS["body"]: body},
            )
            if res.status != "Save":
                raise WriteError(f"{kind} {new_id} created, but the save failed: {res.status!r}")
            time.sleep(site.delay)
            after = read_item(site, kind, new_id)
            ok = after.title == name and _norm(after.fields["body"]) == _norm(body)
            return {"verified": ok, "new_id": new_id, "name": after.title}

    return Change(
        action=f"design.{kind}.create",
        target=f"new {kind} «{name}»",
        level="edit",
        fields={"name": ("", name), "body": ("", body)},
        notes=["used nowhere until a template attaches it"],
        params={"kind": kind, "name": name},
        _do=do,
    )


def plan_delete(site: Site, kind: str, item_id: str, force: bool = False) -> Change:
    """Delete a design item at once (no trash). Without `force` only items named
    «Редизайн…» / «Тест…» – what the redesign creates – may be deleted."""
    k = kind_of(kind)
    category, title = find_category(site, kind, item_id)
    if not force and not title.startswith(SAFE_DELETE_PREFIXES):
        raise WriteError(
            f"{kind} {item_id} «{title}» is not a redesign / test item "
            f"({', '.join(SAFE_DELETE_PREFIXES)}…); refusing without force"
        )

    def do() -> dict:
        with site.lock:
            status, value = category_action(site, category, k.delete, item_id)
            if status != "Del":
                raise WriteError(f"delete of {kind} {item_id} not confirmed: {status!r}")
            time.sleep(site.delay)
            gone = all(r["id"] != str(item_id) for r in list_category(site, category))
            return {"verified": gone, "deleted": str(item_id)}

    return Change(
        action=f"design.{kind}.delete",
        target=f"{kind} {item_id} «{title[:70]}» (from {category})",
        level="delete",
        fields={"exists": (True, False)},
        notes=["deleted at once, no trash – restore only from a design export (archive import)"],
        params={"kind": kind, "id": str(item_id), "force": force},
        _do=do,
    )


def plan_clear_cache(site: Site) -> Change:
    """`SystemWJG.asmx/ClearCache` for the site: the public pages are rebuilt on next view."""
    host = site.settings.site
    if not host:
        raise WriteError("EDU_SITE is not set (the public host, e.g. sch1.example.edu.by)")

    def do() -> dict:
        with site.lock:
            r = site.client.post(f"{site.base_url}/SystemWJG.asmx/ClearCache", json={"url": host})
            r.raise_for_status()
            d = r.json().get("d", "")
            return {"verified": "обновлен" in str(d), "reply": d}

    return Change(
        action="design.cache.clear",
        target=f"site cache of {host}",
        level="publish",
        fields={"cache": ("current", "cleared")},
        notes=["harmless: pages are rebuilt from the current design on the next view"],
        params={"host": host},
        _do=do,
    )


# ---------- export (read-only) ----------


def export_archive(site: Site) -> bytes:
    """«Экспорт в архив» of every template (with all they use): the ZIP bytes. Read-only for
    the site; this is the design backup and the rollback point."""
    url = f"{site.base_url}/G_RengerProvider/ExportToArchives.aspx"
    page = WebFormPage.load(site.client, url)
    boxes = re.findall(r'name="(ctl00_Main_TreeListn\d+CheckBox)"[^>]*title="Template"', page.html)
    if not boxes:
        raise WriteError("export dialog: no templates to tick (session expired?)")
    time.sleep(site.delay)
    data = {
        **page.fields,
        **{b: "on" for b in boxes},
        "ctl00$ScriptManagerDialog": "ctl00$UpdatePanelMain|ctl00$ButtonSave",
        "__EVENTTARGET": "",
        "__EVENTARGUMENT": "",
        "__ASYNCPOST": "true",
        "ctl00$ButtonSave": "Экспорт",
    }
    r = site.client.post(
        url,
        data=data,
        timeout=600,  # the server builds the whole archive before replying
        headers={  # as the browser sends them
            "X-MicrosoftAjax": "Delta=true",
            "X-Requested-With": "XMLHttpRequest",
            "Origin": site.base_url,
            "Referer": url,
        },
    )
    r.raise_for_status()
    link = ""
    for rec in parse_delta(r.text):
        if rec.type == "error":
            raise WriteError(
                f"export: server error {rec.id} – the export fails intermittently "
                "(2026-11-11, cause unknown); retry later, or export in the constructor "
                "(Утилиты → Экспорт в архив)"
            )
        if rec.type == "updatePanel":
            v = parse_form(rec.content).get("ctl00$Result_Value_1", "")
            m = re.search(r"href=([^\s>]+)", html_lib.unescape(v))
            link = m.group(1).strip("'\"") if m else link
    if not link:
        raise WriteError("export: no archive link in the reply")
    time.sleep(site.delay)
    r = site.client.get(
        f"{site.base_url}{link if link.startswith('/') else '/' + link}", timeout=600
    )
    r.raise_for_status()
    if not r.content.startswith(b"PK"):
        raise WriteError(f"export: not a ZIP ({r.headers.get('content-type')})")
    return r.content
