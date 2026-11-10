"""Dialog pages (G_Data/*, G_All/*): load, submit, read the result fields.

Every dialog save is an async postback with `ctl00$ScriptManagerDialog = ctl00$ScriptManagerDialog|<button>`
and the button's name/value in the body (knowledge/endpoints/dialogs.md). The reply's
`ctl00_UpdatePanelMain` carries `ctl00$Result_Status` (`Save`, `SaveExit`, `Exit_2`) and
`ctl00$Result_Value_1/2`.
"""

from __future__ import annotations

import html as html_lib
import re
import time
from dataclasses import dataclass, field

import httpx

from edu_by.api.changes import WriteError
from edu_by.webforms import WebFormPage, parse_form

DIALOG_SM = "ctl00$ScriptManagerDialog"
DIALOG_PANEL = "ctl00$Main$UpdatePanel1"  # tree panel inside ClassifierMove / SelectClassifier
SAVE = ("ctl00$ButtonSave", "Сохранить и остаться")
SAVE_EXIT = ("ctl00$ButtonSaveExit", "Сохранить и выйти")

_MESSAGE = re.compile(r"(?:Show_Error|alert)\(\s*['\"]((?:[^'\"\\]|\\.){1,300})['\"]")


@dataclass
class DialogResult:
    status: str
    values: dict[str, str] = field(default_factory=dict)  # Result_Value, Result_Value_1, ...
    messages: list[str] = field(default_factory=list)  # Show_Error / alert texts in the reply


def open_dialog(client: httpx.Client, base_url: str, path: str, guid: str) -> WebFormPage:
    page = WebFormPage.load(client, f"{base_url}{path}?guid={guid}")
    if 'type="password"' in page.html.lower():
        raise WriteError("got the login page – session expired")
    m = _MESSAGE.search(page.html)
    if m and "No object" in m.group(1):
        raise WriteError(f"{path}?guid={guid}: {m.group(1)}")
    return page


def submit(
    page: WebFormPage, button: tuple[str, str], extra: dict[str, str] | None = None
) -> DialogResult:
    records = page.submit(DIALOG_SM, DIALOG_SM, button[0], button[1], extra)
    result = DialogResult("")
    for rec in records:
        if rec.type == "error":
            raise WriteError(f"{page.url}: server error {rec.id} {rec.content[:200]}")
        if rec.type in ("updatePanel", "scriptBlock"):
            result.messages += [m.replace("<br/>", " ") for m in _MESSAGE.findall(rec.content)]
        if rec.type == "updatePanel":
            for k, v in parse_form(rec.content).items():
                if k == "ctl00$Result_Status":
                    result.status = v
                elif k.startswith("ctl00$Result_Value"):
                    result.values[k.removeprefix("ctl00$")] = v
    return result


def tree_select(page: WebFormPage, path: list[str], delay: float) -> None:
    """Select a section in a dialog's tree (`s<id>\\<id>…`), revealing ancestors top-down.

    The dialog trees are lazy like the explorer's: a node is clickable only once its parent
    was selected. A node already visible is selected directly.
    """
    html = html_lib.unescape(page.html)
    start = 0
    for i in range(len(path), 0, -1):  # deepest ancestor already rendered
        if _node_arg(path[:i]) in html:
            start = i - 1
            break
    for i in range(start, len(path)):
        arg = "s" + "\\".join(path[: i + 1])
        if _node_arg(path[: i + 1]) not in html:
            raise WriteError(f"section {path[i]} is not shown in the dialog tree")
        time.sleep(delay)
        records = page.async_postback(DIALOG_SM, DIALOG_PANEL, "ctl00$Main$TreeClassifier", arg)
        for rec in records:
            if rec.type == "error":
                raise WriteError(f"selecting {arg} in the dialog failed")
            if rec.type == "updatePanel":
                html = html_lib.unescape(rec.content)


def _node_arg(path: list[str]) -> str:
    # as written in the tree's javascript:__doPostBack(…,'s1001\\56621') links
    return "'s" + "\\\\".join(path) + "'"
