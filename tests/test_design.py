"""Design writes against a fake RengerProvider (markup shapes from captures design-2026-11-10 /
design2-2026-11-11, made-up ids and texts)."""

import html
import re
import urllib.parse

import httpx
import pytest
from test_write import delta, fake_site

from edu_by.api import design
from edu_by.api.changes import WriteError
from edu_by.webforms import parse_form

FORM = (
    '<form><input type="hidden" name="__VIEWSTATE" value="vs" />'
    '<input type="hidden" name="ctl00$GuidSession" value="00000000-0000-0000-0000-000000000000" />'
    '<input type="hidden" name="ctl00$Result_Status" value="" />{body}</form>'
)


def template_page(
    title: str, css: list[str], body: str, master: str = "", sections: list[str] | None = None
) -> str:
    def lst(name: str, items: dict[str, str], checked: list[str]) -> str:
        divs = "".join(
            f"<div gg='{i}'><input type='checkbox'{' checked=' + chr(39) + 'checked' + chr(39) if i in checked else ''}>{n}</div>"
            for i, n in items.items()
        )
        return f'<div id="{name}" class="SortList">{divs}</div>'

    master_html = (
        '<select name="ctl00$Main$MasterList"><option value="901">Мастер А</option>'
        f'<option {"selected=" + chr(34) + "selected" + chr(34) if master == "902" else ""} value="902">Мастер Б</option></select>'
        if master
        else '<input type="hidden" name="ctl00$Main$TypeDocument" value="0" />'
    )
    field = "Body_Content_1" if master else "Body_Content"
    # Главный / Обычный / 404: «Классификаторы» = sections using the template, filled by JS
    zone = (
        '<input type="hidden" name="ctl00$Main$ClassifierL" id="ClassifierL" />'
        "<script>T_Init('ClassifierL');"
        + "".join(f"T_Add('ClassifierL','{s}','Раздел {s}/');" for s in sections or [])
        + "</script>"
        if master
        else ""
    )
    return FORM.format(
        body=f'<input name="ctl00$Main$TextBoxTitle_text" value="{html.escape(title)}" />'
        + master_html
        + f'<textarea name="ctl00$Main${field}$TextBoxRes">\r\n{html.escape(body)}</textarea>'
        + '<input type="hidden" name="ctl00$Main$HiddenFieldForSave" id="HiddenFieldForSave" />'
        + lst("ListJS", {"801": "jquery"}, ["801"])
        + lst("ListCss", {"701": "Основной", "702": "Меню", "703": "Новый"}, css)
        + zone
    )


def control_page(lang_checked: bool = True) -> str:
    box = '<input id="l" type="checkbox" name="ctl00$Main$CheckBoxListAccess$0"{c} />'.format(
        c=' checked="checked"' if lang_checked else ""
    )
    return CONTROL_TPL.replace("{lang}", box)


CONTROL_TPL = FORM.format(
    body='<input name="ctl00$Main$TextBoxTitle_text" value="Меню" />'
    '<textarea name="ctl00$Main$ASD_Link">\r\n&lt;li&gt;[[title]]&lt;/li&gt;</textarea>'
    '<input type="hidden" name="ctl00$Main$ASD_ClassifierList" id="ASD_ClassifierList" />'
    '<input id="a" type="checkbox" name="ctl00$Main$ASD_page_Use" checked="checked" />'
    '<input id="b" type="checkbox" name="ctl00$Main$ASD_D_Parent" />'
    "{lang}"
    "<script>T_Init('ASD_ClassifierList');T_Add('ASD_ClassifierList','5001','Раздел/');"
    "T_Add('ASD_ClassifierList','5002','Другой/');</script>"
)


def category(rows: dict[str, str], dialog: str) -> str:
    trs = "".join(
        f"<tr  class='line' id='obj_{i}' ><td><img src=x.png></td>"
        f"<td width='100%' onclick=\"Open('{dialog}',this,'{i}')\"  >{t}</td></tr>"
        for i, t in rows.items()
    )
    return FORM.format(
        body=f'<input type="hidden" name="ctl00$Result_Value" value="" /><table>{trs}</table>'
    )


def result(status: str, value: str = "", panel: str = "ctl00_UpdatePanelMain") -> str:
    inputs = (
        f'<input type="hidden" name="ctl00$Result_Status" value="{status}" />'
        f'<input type="hidden" name="ctl00$Result_Value" value="{html.escape(value)}" />'
    )
    return delta(("updatePanel", panel, inputs))


class FakeRP:
    """Templates 1001 (master) / 1002 (normal), module 3001, category pages, copy and delete."""

    def __init__(self) -> None:
        self.templates = {
            "1001": {
                "title": "Мастер",
                "css": ["701", "702"],
                "body": "<div>LoadModule(1,a)</div>",
                "master": "",
            },
            "1002": {
                "title": "Обычный",
                "css": [],
                "body": "<p>x</p>",
                "master": "901",
                "sections": ["1001"],
            },
        }
        self.posts: list[tuple[str, dict[str, str]]] = []
        self.control_posts: list[dict[str, str]] = []
        self.control_lang: dict[str, bool] = {}

    def handler(self, request: httpx.Request) -> httpx.Response:
        url = request.url
        guid = url.params.get("guid", "")
        form = dict(urllib.parse.parse_qsl(request.content.decode(), keep_blank_values=True))
        if url.path == "/G_RengerProvider/Templates.aspx":
            t = self.templates[guid]
            if request.method == "GET":
                return httpx.Response(
                    200,
                    text=template_page(
                        t["title"], t["css"], t["body"], t["master"], t.get("sections")
                    ),
                )
            self.posts.append((guid, form))
            hidden = form["ctl00$Main$HiddenFieldForSave"]
            t["css"] = re.findall(r'<css value="(\d+)"/>', hidden)
            t["title"] = form["ctl00$Main$TextBoxTitle_text"]
            key = "Body_Content_1" if t["master"] else "Body_Content"
            t["body"] = form[f"ctl00$Main${key}$TextBoxRes"].replace(
                "LoadModule(1,a)", "LoadModule(1,a) "
            )
            if t["master"]:
                t["master"] = form["ctl00$Main$MasterList"]
                # the post replaces the list: empty detaches every section (seen live)
                t["sections"] = [s for s in form["ctl00$Main$ClassifierL"].split(";") if s]
            return httpx.Response(200, text=result("Save"))
        if url.path == "/G_RengerProvider/Controls.aspx":
            if request.method == "GET":
                return httpx.Response(200, text=control_page(self.control_lang.get(guid, True)))
            self.control_posts.append(form)
            self.control_lang[guid] = "ctl00$Main$CheckBoxListAccess$0" in form
            return httpx.Response(200, text=result("Save"))
        if url.path == "/RengerProvider.aspx":
            cat = guid
            if cat == "Actual":
                if request.method == "GET":
                    return httpx.Response(200, text=category({"3001": "Меню"}, "Controls"))
                # a module copy comes with its «Язык» boxes unchecked (seen live 2026-11-11)
                self.control_lang["3099"] = False
                row = "<tr  class='line' id='obj_3099' ><td onclick=\"Open('Controls',this,'3099')\">x</td></tr>"
                return httpx.Response(200, text=result("Control_Copy", row))
            rows = {
                k: v["title"]
                for k, v in self.templates.items()
                if (cat == "Master") == (not v["master"])
            }
            if request.method == "GET":
                return httpx.Response(200, text=category(rows, "Templates"))
            target = form["__EVENTTARGET"].rsplit("$", 1)[-1]
            item = form["ctl00$Result_Value"]
            self.posts.append((target, form))
            if target == "TemplateCopy":
                self.templates["1099"] = dict(
                    self.templates[item], title="Копия " + self.templates[item]["title"]
                )
                row = "<tr  class='line' id='obj_1099' ><td onclick=\"Open('Templates',this,'1099')\">x</td></tr>"
                return httpx.Response(200, text=result("Copy", row))
            if target == "TemplateDel":
                self.templates.pop(item)
                return httpx.Response(200, text=result("Del", item))
        return httpx.Response(404, text="")


@pytest.fixture
def rp(monkeypatch):
    fake = FakeRP()
    monkeypatch.setattr(design, "guid_session", lambda site: "gs")
    return fake, fake_site(fake.handler)


def test_textarea_leading_newline_is_dropped():
    assert parse_form('<textarea name="a">\r\nx\n</textarea>')["a"] == "x\n"


def test_sort_list_and_hidden_field():
    page = template_page("T", ["702", "701"], "b")
    css, names = design.parse_sort_list(page, "ListCss")
    assert css == ["701", "702"] and names["703"] == "Новый"  # list order, not click order
    assert design.template_hidden(["801"], css) == (
        '<js value="801"/><css value="701"/><css value="702"/>'
    )
    assert design.parse_sort_list("<div>nothing</div>", "ListCss") is None


def test_attach_css_goes_last_and_keeps_the_others(rp):
    fake, site = rp
    ch = design.plan_set(site, "template", "1001", attach_css=["703"])
    assert ch.level == "publish" and ch.fields["css"] == (["701", "702"], ["701", "702", "703"])
    out = ch.apply(ch.token)
    hidden = fake.posts[-1][1]["ctl00$Main$HiddenFieldForSave"]
    assert hidden == '<js value="801"/><css value="701"/><css value="702"/><css value="703"/>'
    assert out["verified"] is True


def test_body_save_tolerates_loadmodule_respacing(rp):
    fake, site = rp
    ch = design.plan_set(site, "template", "1001", {"body": "<div>LoadModule(1,a)</div><p>new</p>"})
    out = ch.apply(ch.token)
    # the GET leaves HiddenFieldForSave empty – the save must still carry the attached sets
    assert fake.posts[-1][1]["ctl00$Main$HiddenFieldForSave"].count("<css") == 2
    assert out["verified"] is True


def test_master_change_and_unknown_values_refused(rp):
    fake, site = rp
    ch = design.plan_set(site, "template", "1002", {"master": "902"})
    assert ch.apply(ch.token)["verified"] is True and fake.templates["1002"]["master"] == "902"
    with pytest.raises(WriteError, match="not offered"):
        design.plan_set(site, "template", "1002", {"master": "999"})
    with pytest.raises(WriteError, match="no style set"):
        design.plan_set(site, "template", "1001", attach_css=["999"])
    with pytest.raises(WriteError, match="no field"):
        design.plan_set(site, "template", "1001", {"colour": "red"})


def test_template_save_keeps_its_sections(rp):
    fake, site = rp
    item = design.read_item(site, "template", "1002")
    assert item.lists == {"ClassifierL": ["1001"]}
    ch = design.plan_set(site, "template", "1002", {"master": "902"})
    assert ch.apply(ch.token)["verified"] is True
    assert fake.posts[-1][1]["ctl00$Main$ClassifierL"] == "1001;"
    assert fake.templates["1002"]["sections"] == ["1001"]
    with pytest.raises(WriteError, match="no field"):  # not a settable field
        design.plan_set(site, "template", "1002", {"ClassifierL": ""})


def test_template_without_its_section_list_is_refused(rp, monkeypatch):
    fake, site = rp
    monkeypatch.setattr(design, "_T_INIT", re.compile(r"(?!)"))
    monkeypatch.setattr(design, "_T_ADD", re.compile(r"(?!)()()()"))
    with pytest.raises(WriteError, match="detach every section"):
        design.plan_set(site, "template", "1002", {"title": "x"})


def test_template_without_lists_is_refused(rp, monkeypatch):
    fake, site = rp
    monkeypatch.setattr(design, "parse_sort_list", lambda page, name: None)
    with pytest.raises(WriteError, match="detach every style set"):
        design.plan_set(site, "template", "1001", {"title": "x"})


def test_control_save_rebuilds_section_lists(rp):
    fake, site = rp
    item = design.read_item(site, "control", "3001")
    assert item.lists == {"ASD_ClassifierList": ["5001", "5002"]}
    assert item.fields["ASD_Link"] == "<li>[[title]]</li>"
    ch = design.plan_set(site, "control", "3001", {"ASD_Link": "<li class='m'>[[title]]</li>"})
    ch.apply(ch.token)
    post = fake.control_posts[-1]
    assert post["ctl00$Main$ASD_ClassifierList"] == "5001;5002;"
    assert post["ctl00$Main$ASD_Link"] == "<li class='m'>[[title]]</li>"
    with pytest.raises(WriteError, match="section lists"):
        design.plan_set(site, "control", "3001", {"ASD_ClassifierList": "1;"})


def test_control_section_list_is_replaced(rp):
    fake, site = rp
    with pytest.raises(WriteError, match="no section list"):
        design.plan_set(site, "control", "3001", lists={"ASD_Other": ["1"]})
    with pytest.raises(WriteError, match="must be numbers"):
        design.plan_set(site, "control", "3001", lists={"ASD_ClassifierList": ["x"]})
    ch = design.plan_set(site, "control", "3001", lists={"ASD_ClassifierList": ["1001"]})
    assert ch.fields == {"ASD_ClassifierList": (["5001", "5002"], ["1001"])}
    ch.apply(ch.token)
    assert fake.control_posts[-1]["ctl00$Main$ASD_ClassifierList"] == "1001;"


def test_copy_names_the_copy_and_delete_is_guarded(rp):
    fake, site = rp
    ch = design.plan_copy(site, "template", "1001", "Редизайн 2026. Мастер")
    assert ch.level == "edit"
    out = ch.apply(ch.token)
    assert out["new_id"] == "1099" and fake.templates["1099"]["title"] == "Редизайн 2026. Мастер"
    assert out["verified"] is True and fake.templates["1099"]["css"] == ["701", "702"]
    with pytest.raises(WriteError, match="refusing without force"):
        design.plan_delete(site, "template", "1001")
    d = design.plan_delete(site, "template", "1099")
    assert d.level == "delete" and d.apply(d.token)["verified"] is True
    assert "1099" not in fake.templates and "1001" in fake.templates


def test_clear_cache_needs_the_site_host():
    site = fake_site(lambda r: httpx.Response(200, json={"d": "Cache сайта обновлен."}))
    site.settings.site = None
    with pytest.raises(WriteError, match="EDU_SITE"):
        design.plan_clear_cache(site)
    site.settings.site = "school.example.edu.by"
    ch = design.plan_clear_cache(site)
    assert ch.apply(ch.token)["verified"] is True


def test_export_posts_referer_and_downloads_the_zip():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("ExportToArchives.aspx") and request.method == "GET":
            box = '<input type="checkbox" name="ctl00_Main_TreeListn1CheckBox" title="Template" />'
            return httpx.Response(200, text=FORM.format(body=box))
        if request.method == "POST":
            seen["referer"] = request.headers.get("referer")
            link = html.escape("<a href=/sm_full.aspx?guid=-888 target=_new>x</a>")
            panel = f'<input type="hidden" name="ctl00$Result_Value_1" value="{link}" />'
            return httpx.Response(200, text=delta(("updatePanel", "ctl00_UpdatePanelMain", panel)))
        return httpx.Response(200, content=b"PK\x03\x04zip")

    site = fake_site(handler)
    assert design.export_archive(site).startswith(b"PK")
    assert seen["referer"].endswith("/G_RengerProvider/ExportToArchives.aspx")


def test_control_checkboxes_on_and_off(rp):
    fake, site = rp
    item = design.read_item(site, "control", "3001")
    assert item.checkboxes == {"ASD_page_Use", "ASD_D_Parent", "CheckBoxListAccess$0"}
    assert item.fields["ASD_page_Use"] == "on" and item.fields["ASD_D_Parent"] == ""
    ch = design.plan_set(site, "control", "3001", {"ASD_page_Use": "off", "ASD_D_Parent": "on"})
    assert ch.fields["ASD_page_Use"] == ("on", "") and ch.fields["ASD_D_Parent"] == ("", "on")
    ch.apply(ch.token)
    post = fake.control_posts[-1]
    assert "ctl00$Main$ASD_page_Use" not in post and post["ctl00$Main$ASD_D_Parent"] == "on"
    with pytest.raises(WriteError, match="checkbox"):
        design.plan_set(site, "control", "3001", {"ASD_D_Parent": "maybe"})


def test_module_copy_keeps_the_language_box(rp):
    fake, site = rp
    assert design.read_item(site, "control", "3001").fields["CheckBoxListAccess$0"] == "on"
    ch = design.plan_copy(site, "control", "3001", "Редизайн 2026. Меню")
    out = ch.apply(ch.token)
    assert out["new_id"] == "3099"
    assert fake.control_posts[-1]["ctl00$Main$CheckBoxListAccess$0"] == "on"
    assert fake.control_lang["3099"] is True and out["same_content"]["CheckBoxListAccess$0"]
