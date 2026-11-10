"""Read one object through G_Data/ObjectEditor.aspx (GET only, nothing is saved)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from html.parser import HTMLParser

import httpx

from edu_by.webforms import parse_form, strip_tags

EDITOR_PATH = "/G_Data/ObjectEditor.aspx"


class ObjectError(RuntimeError):
    pass


@dataclass
class ObjectData:
    id: str
    type: str  # full type name, e.g. "Блок html (текст раздела)"
    name: str  # title / block description (ctl00$Main$name)
    published: bool  # "Разрешить публикацию" (allow publication) checkbox
    section_id: str  # ctl00$Main$Classifier
    section_path: str  # label next to it, e.g. "Главная страница/О школе/"
    tags: str
    languages: list[str] = field(default_factory=list)
    public_url: str | None = None
    text: str = ""  # main HTML content
    dop: str = ""  # additional content (type-dependent)


class _LangLabels(HTMLParser):
    """Labels of checked ctl00$Main$ListLang$<n> checkboxes."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.checked: set[str] = set()
        self.labels: dict[str, str] = {}
        self._label_for: str | None = None

    def handle_starttag(self, tag, attrs):
        a = {k: (v or "") for k, v in attrs}
        if tag == "input" and a.get("name", "").startswith("ctl00$Main$ListLang$"):
            if "checked" in a:
                self.checked.add(a.get("id", ""))
        elif tag == "label" and a.get("for", "").startswith("ctl00_Main_ListLang_"):
            self._label_for = a["for"]

    def handle_endtag(self, tag):
        if tag == "label":
            self._label_for = None

    def handle_data(self, data):
        if self._label_for:
            self.labels[self._label_for] = self.labels.get(self._label_for, "") + data


def parse_object_editor(object_id: str, page_html: str) -> ObjectData:
    f = parse_form(page_html)
    if "ctl00$Main$text" not in f and "ctl00$Main$name" not in f:
        raise ObjectError(f"object {object_id}: editor form not found (wrong id or no access?)")
    m = re.search(r"Тип:</td>\s*<td>\s*<b>(.*?)</b>", page_html, re.S)
    obj_type = strip_tags(m.group(1)) if m else ""
    m = re.search(r"name=\"ctl00\$Main\$Classifier\"[^>]*/>.*?<span>(.*?)</span>", page_html, re.S)
    section_path = strip_tags(m.group(1)) if m else ""
    m = re.search(r"href=['\"]?([^'\" >]*main\.aspx\?guid=\d+)", f.get("ctl00$Title_2", ""))
    langs = _LangLabels()
    langs.feed(page_html)
    return ObjectData(
        id=object_id,
        type=obj_type,
        name=f.get("ctl00$Main$name", ""),
        published="ctl00$Main$CheckBoxStatusObject" in f,
        section_id=f.get("ctl00$Main$Classifier", ""),
        section_path=section_path,
        tags=f.get("ctl00$Main$Tags", ""),
        languages=[langs.labels[i].strip() for i in sorted(langs.checked) if i in langs.labels],
        public_url=m.group(1) if m else None,
        text=f.get("ctl00$Main$text", "").strip("\r\n"),
        dop=f.get("ctl00$Main$dop", "").strip("\r\n"),
    )


def read_object(client: httpx.Client, base_url: str, object_id: str) -> ObjectData:
    if not object_id.isdigit():
        raise ObjectError(f"object id must be a number, got {object_id!r}")
    r = client.get(f"{base_url}{EDITOR_PATH}", params={"guid": object_id})
    r.raise_for_status()
    if 'type="password"' in r.text.lower():
        raise ObjectError("got the login page – session expired")
    return parse_object_editor(object_id, r.text)
