"""Planned writes: previews, tokens and the request flow, against a fake constructor
(httpx.MockTransport) built from the live markup shapes with made-up data."""

import urllib.parse

import httpx
import pytest
from test_api import EDITOR

from edu_by.api import objects_write as ow
from edu_by.api.changes import Change, TokenMismatch, WriteError
from edu_by.api.dialogs import tree_select
from edu_by.config import Settings
from edu_by.site import Site
from edu_by.webforms import WebFormPage

BASE = "https://wp.example.edu.by"


def delta(*records: tuple[str, str, str]) -> str:
    return "".join(f"{len(c)}|{t}|{i}|{c}|" for t, i, c in records)


def result_panel(status: str, **values: str) -> tuple[str, str, str]:
    inputs = f'<input type="hidden" name="ctl00$Result_Status" value="{status}" />'
    for k, v in values.items():
        inputs += f'<input type="hidden" name="ctl00${k}" value="{v}" />'
    return ("updatePanel", "ctl00_UpdatePanelMain", inputs)


class FakeEditor:
    """ObjectEditor.aspx for one object: GET renders the stored fields, a Save stores them."""

    def __init__(self) -> None:
        self.html = EDITOR
        self.posts: list[dict[str, str]] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, text=self.html)
        form = dict(urllib.parse.parse_qsl(request.content.decode(), keep_blank_values=True))
        self.posts.append(form)
        name = form["ctl00$Main$name"]
        self.html = EDITOR.replace('value="основной"', f'value="{name}"')
        if "ctl00$Main$CheckBoxStatusObject" not in form:
            self.html = self.html.replace(
                'name="ctl00$Main$CheckBoxStatusObject" checked="checked"',
                'name="ctl00$Main$CheckBoxStatusObject"',
            )
        return httpx.Response(200, text=delta(result_panel("Save")))


def fake_site(handler) -> Site:
    site = Site(Settings(constructor_url=f"{BASE}/explorer.aspx", request_delay=0), check=False)
    site.client = httpx.Client(transport=httpx.MockTransport(handler))
    return site


def test_change_token_depends_on_state_and_request():
    a = Change("object.update", "object 1", "edit", {"name": ("x", "y")})
    b = Change("object.update", "object 1", "edit", {"name": ("x", "y")})
    c = Change("object.update", "object 1", "edit", {"name": ("z", "y")})  # site changed
    assert a.token == b.token != c.token
    assert not a.noop and Change("a", "t", "edit", {"n": ("x", "x")}).noop
    assert a.preview()["changes"] == {"name": {"before": "x", "after": "y"}}


def test_apply_refuses_a_wrong_token():
    ch = Change("object.update", "object 1", "edit", {"name": ("x", "y")}, _do=lambda: {})
    with pytest.raises(TokenMismatch):
        ch.apply("000000000000")
    assert ch.apply(ch.token)["applied"] is True


def test_editable_fields_skip_fixed_and_lang():
    page = WebFormPage.__new__(WebFormPage)
    from edu_by.webforms import parse_form

    page.fields = parse_form(EDITOR)
    assert ow.editable_fields(page.fields) == ["Tags", "name", "text", "dop"]


def test_plan_update_preview_keeps_other_fields_and_verifies():
    fake = FakeEditor()
    site = fake_site(fake.handler)
    change = ow.plan_update(site, "1063", {"name": "новый"})
    assert change.level == "publish"  # the object is published: edits are live
    assert change.fields == {"name": ("основной", "новый")}
    assert fake.posts == []  # planning only reads
    result = change.apply(change.token)
    (post,) = fake.posts
    assert post["ctl00$ScriptManagerDialog"] == "ctl00$ScriptManagerDialog|ctl00$ButtonSave"
    assert post["ctl00$ButtonSave"] == "Сохранить и остаться" and post["__EVENTTARGET"] == ""
    assert post["ctl00$Main$CheckBoxStatusObject"] == "on"  # publication flag carried over
    assert post["ctl00$Main$text"].endswith("<p>Добро пожаловать</p>")
    assert result["verified"] is True and result["object"]["name"] == "новый"


def test_plan_update_unpublish_and_unknown_field():
    fake = FakeEditor()
    site = fake_site(fake.handler)
    with pytest.raises(WriteError, match="no field"):
        ow.plan_update(site, "1063", {"zag": "x"})
    change = ow.plan_update(site, "1063", published=False)
    assert change.fields == {"published": (True, False)}
    assert change.apply()["verified"] is True
    assert "ctl00$Main$CheckBoxStatusObject" not in fake.posts[-1]


def test_sort_order_from_sort_list():
    html = (
        "<div id='SortList'><span guid='117633'><img src=/sm.aspx?guid=117633>Граф объект: "
        "</span><span guid='2283'>Блок html: </span></div><span guid='9'></span>"
    )
    assert ow.sort_order(html) == ["117633", "2283"]


def test_upload_refuses_documents_and_big_files(tmp_path):
    site = fake_site(lambda r: httpx.Response(500))
    pdf = tmp_path / "a.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    with pytest.raises(WriteError, match="external link"):
        ow.plan_upload_image(site, "1", pdf)
    big = tmp_path / "a.png"
    big.write_bytes(b"\0" * (ow.IMAGE_LIMIT + 1))
    with pytest.raises(WriteError, match="limit"):
        ow.plan_upload_image(site, "1", big)


def test_dialog_tree_select_reveals_ancestors():
    def link(arg: str) -> str:
        js = arg.replace("\\", "\\\\")
        return f'<a href="javascript:__doPostBack(&#39;ctl00$Main$TreeClassifier&#39;,&#39;{js}&#39;)">x</a>'

    sent = []

    def handler(request: httpx.Request) -> httpx.Response:
        form = dict(urllib.parse.parse_qsl(request.content.decode()))
        sent.append(form["__EVENTARGUMENT"])
        nxt = {"s1001\\56621": link("s1001\\56621\\59631")}.get(form["__EVENTARGUMENT"], "")
        panel = link("s1001") + link("s1001\\56621") + nxt
        return httpx.Response(200, text=delta(("updatePanel", "ctl00_Main_UpdatePanel1", panel)))

    client = httpx.Client(transport=httpx.MockTransport(handler))
    page = WebFormPage(client, f"{BASE}/G_Data/ClassifierMove.aspx?guid=1")
    page.html = link("s1001") + link("s1001\\56621")
    tree_select(page, ["1001", "56621", "59631"], 0)
    assert sent == ["s1001\\56621", "s1001\\56621\\59631"]
