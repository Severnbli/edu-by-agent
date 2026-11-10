"""ASP.NET WebForms helpers: read a page's form state, post back, parse async (UpdatePanel) replies.

The constructor is a WebForms app: every action is a postback carrying the whole form
(__VIEWSTATE, __EVENTVALIDATION, hidden fields). Async postbacks (ScriptManager +
__ASYNCPOST=true) answer with a "delta" of `length|type|id|content|` records.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser

import httpx


class _FormParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.fields: dict[str, str] = {}
        self._select: str | None = None
        self._select_first: str | None = None
        self._select_chosen = False
        self._textarea: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag, attrs):
        a = {k: (v or "") for k, v in attrs}
        name = a.get("name")
        if tag == "input" and name:
            kind = a.get("type", "text").lower()
            if kind in ("submit", "button", "image", "reset", "file"):
                return
            if kind in ("checkbox", "radio") and "checked" not in a:
                return
            self.fields[name] = a.get("value", "on" if kind == "checkbox" else "")
        elif tag == "select" and name:
            self._select, self._select_first, self._select_chosen = name, None, False
        elif tag == "option" and self._select:
            value = a.get("value", "")
            if self._select_first is None:
                self._select_first = value
            if "selected" in a:
                self.fields[self._select] = value
                self._select_chosen = True
        elif tag == "textarea" and name:
            self._textarea, self._text = name, []

    def handle_endtag(self, tag):
        if tag == "select" and self._select:
            if not self._select_chosen and self._select_first is not None:
                self.fields[self._select] = self._select_first
            self._select = None
        elif tag == "textarea" and self._textarea:
            self.fields[self._textarea] = "".join(self._text)
            self._textarea = None

    def handle_data(self, data):
        if self._textarea:
            self._text.append(data)


def parse_form(page_html: str) -> dict[str, str]:
    """Successful-control values of the page's form, as a browser would submit them."""
    p = _FormParser()
    p.feed(page_html)
    return p.fields


@dataclass
class DeltaRecord:
    type: str
    id: str
    content: str


def parse_delta(text: str) -> list[DeltaRecord]:
    """Parse an ASP.NET AJAX async postback reply (`len|type|id|content|` repeated)."""
    out: list[DeltaRecord] = []
    i = 0
    while i < len(text):
        j = text.index("|", i)
        length = int(text[i:j])
        k = text.index("|", j + 1)
        rtype = text[j + 1 : k]
        m = text.index("|", k + 1)
        rid = text[k + 1 : m]
        content = text[m + 1 : m + 1 + length]
        out.append(DeltaRecord(rtype, rid, content))
        i = m + 1 + length + 1  # skip trailing '|'
    return out


def strip_tags(fragment: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", fragment))).strip()


@dataclass
class WebFormPage:
    """A loaded page whose form state is kept current across async postbacks."""

    client: httpx.Client
    url: str
    fields: dict[str, str] = field(default_factory=dict)
    html: str = ""

    @classmethod
    def load(cls, client: httpx.Client, url: str) -> WebFormPage:
        r = client.get(url)
        r.raise_for_status()
        return cls(client, str(r.url), parse_form(r.text), r.text)

    def async_postback(
        self,
        script_manager: str,
        panel: str,
        event_target: str,
        event_argument: str = "",
        extra: dict[str, str] | None = None,
    ) -> list[DeltaRecord]:
        """Async postback raised by a control (`__EVENTTARGET`), e.g. a tree node click."""
        return self._post(
            {
                script_manager: f"{panel}|{event_target}",
                "__EVENTTARGET": event_target,
                "__EVENTARGUMENT": event_argument,
                **(extra or {}),
            }
        )

    def submit(
        self,
        script_manager: str,
        panel: str,
        button: str,
        value: str,
        extra: dict[str, str] | None = None,
    ) -> list[DeltaRecord]:
        """Async postback of a submit button: the button's name and value go in the body
        and `__EVENTTARGET` stays empty (dialog Save buttons, «Удалить» section)."""
        return self._post(
            {
                script_manager: f"{panel}|{button}",
                "__EVENTTARGET": "",
                "__EVENTARGUMENT": "",
                **(extra or {}),
                button: value,
            }
        )

    def _post(self, overrides: dict[str, str]) -> list[DeltaRecord]:
        data = {**self.fields, "__ASYNCPOST": "true", **overrides}
        u = httpx.URL(self.url)
        r = self.client.post(
            self.url,
            data=data,
            headers={
                "X-MicrosoftAjax": "Delta=true",
                "X-Requested-With": "XMLHttpRequest",
                "Origin": f"{u.scheme}://{u.host}",
                "Referer": self.url,
            },
        )
        r.raise_for_status()
        records = parse_delta(r.text)
        for rec in records:
            if rec.type == "hiddenField":
                self.fields[rec.id] = rec.content
            elif rec.type == "updatePanel":
                # Inputs inside refreshed panels replace the old values.
                self.fields.update(parse_form(rec.content))
            elif rec.type == "pageRedirect":
                raise RuntimeError(f"redirected to {rec.content} (session expired?)")
        return records
