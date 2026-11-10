"""Parsers of the read-only API layer. Fixtures mirror the live markup with made-up data."""

import pytest

from edu_by.api.explorer import (
    SECTION,
    TEMPLATE,
    Explorer,
    parse_object_list,
    parse_pages,
    parse_tree,
    types_from_tree,
)
from edu_by.api.objects import parse_object_editor
from edu_by.webforms import WebFormPage

PB = "javascript:__doPostBack(&#39;ctl00$Main_Left$TreeClassifier&#39;,&#39;{}&#39;)"
T = "ctl00_Main_Left_TreeClassifier"


def node(i: int, value: str | None, label: str, guid: str | None = None, toggle=False) -> str:
    """One TreeView node as rendered (toggle link, then text link or selected span)."""
    tog = (
        f'<a id="{T}n{i}" href="javascript:TreeView_ToggleNode()"><img alt="Expand"/></a>'
        if toggle
        else ""
    )
    icon = (
        f"<img src=/Images/Default/classifier.png  guid={guid} border=0 width='15px'>"
        if guid
        else ""
    )
    if value is None:
        text = f'<span class="x" id="{T}t{i}">{icon}<span id=\'SelectTree\'>{label}</span></span>'
    else:
        href = PB.format(value.replace("\\", "\\\\"))
        text = f'<a href="{href}" onclick="TreeView_SelectNode()" id="{T}t{i}">{icon}{label}</a>'
    return f"<table><tr><td>{tog}</td><td>{text}</td></tr></table>"


def children(i: int, *inner: str) -> str:
    return f'<div id="{T}n{i}Nodes" style="display:block;">{"".join(inner)}</div>'


TEMPLATE_ICON = (
    '<a href="' + PB.format("sNodeTemplate\\\\Стандартные\\\\524") + f'" id="{T}t7i"><img/></a>'
)

TREE = (
    f'<div id="{T}">'
    + node(0, None, "Классификаторы", toggle=True)
    + children(
        0,
        node(1, None, "Главная страница", guid="1001", toggle=True),  # selected
        children(
            1,
            node(2, SECTION + "\\1001\\1041", "О школе", guid="1041"),
            node(3, SECTION + "\\1001\\1051", "Учительская", guid="1051"),
        ),
        node(4, SECTION + "\\1011", "Служебный", guid="1011"),
    )
    + node(5, None, "Шаблоны объектов", toggle=True)
    + children(
        5,
        node(6, None, "Стандартные", toggle=True),
        children(
            6,
            # icon link (id ...t7i) and text link, as on the live page
            TEMPLATE_ICON + node(7, TEMPLATE + "\\Стандартные\\524", "Блок html (текст раздела)"),
            node(8, TEMPLATE + "\\Стандартные\\534", "Новость"),
        ),
    )
    + "</div>"
)


def test_parse_tree_sections_and_parents():
    nodes = {n.index: n for n in parse_tree(TREE)}
    assert nodes[1].kind == SECTION and nodes[1].id == "1001" and nodes[1].selected
    assert nodes[1].value is None and nodes[1].has_children
    assert nodes[2].value == "sNodeClassifier\\1001\\1041" and nodes[2].parent_index == 1
    assert nodes[2].title == "О школе" and not nodes[2].has_children
    assert nodes[4].parent_index == 0 and nodes[4].id == "1011"
    assert nodes[0].kind is None and nodes[0].title == "Классификаторы"


def test_types_from_tree():
    types = types_from_tree(parse_tree(TREE))
    assert [(t.id, t.group, t.name) for t in types] == [
        ("524", "Стандартные", "Блок html (текст раздела)"),
        ("534", "Стандартные", "Новость"),
    ]


def test_explorer_learns_sections_with_paths():
    page = WebFormPage(client=None, url="https://wp.example.edu.by/explorer.aspx")  # type: ignore[arg-type]
    page.fields["ctl00$Main_Left$GUID_CLASSIFIER"] = "1001"
    ex = Explorer(page)
    ex._learn(TREE)
    assert ex.sections["1001"].path == ["1001"] and ex.sections["1001"].parent_id is None
    assert ex.sections["1051"].path == ["1001", "1051"]
    assert ex.sections["1011"].parent_id is None
    assert [s.id for s in ex.children("1001")] == ["1041", "1051"]
    # The current section needs no request and returns at once.
    assert ex.select_section("1001").id == "1001" and ex._requests == 0


LIST = (
    '<span id="ctl00_Main_Right_UpdatePanelMainList">'
    "<table style=\"width: 96%\" id='ListElements'><tbody>"
    "<tr guid='1063'><td><input type='checkbox'></td>"
    "<td onclick='Obj_Open(this)' style='width: 100%'>Блок html: основной</td></tr>"
    "<tr class='obj_not_published' guid='122203'><td><input type='checkbox'></td>"
    "<td onclick='Obj_Open(this)' style='width: 100%'><img src=/sm.aspx?guid=122203 "
    "style='float: left' class='ObjectIco'>Граф объект: </td></tr>"
    "<tr guid='93963'><td><input type='checkbox'></td>"
    "<td onclick='Obj_Open(this)'>Новость: День знаний: линейка</td></tr>"
    "</tbody></table></span>"
)


def test_parse_object_list():
    rows = parse_object_list(LIST)
    assert [(r.id, r.type_label, r.title, r.published) for r in rows] == [
        ("1063", "Блок html", "основной", True),
        ("122203", "Граф объект", "", False),
        ("93963", "Новость", "День знаний: линейка", True),
    ]
    assert parse_object_list("<div>nothing</div>") == []


PAGER = (
    "<span class='PagePageSelect'>6</span>"
    '<select size="4" name="ctl00$ContentSecondMenu$PageList" id="PageList">'
    '<option value="0">1</option><option value="4">5</option>'
    '<option selected="selected" value="5">6</option><option value="6">7</option>'
    '<option value="11">&gt;&gt;</option></select>'
)


def test_parse_pages():
    assert parse_pages(PAGER) == (5, [0, 4, 5, 6, 11])
    assert parse_pages("<div></div>") == (None, [])


EDITOR = """<form>
<input type="hidden" name="ctl00$Title_1" id="Title_1" value="[1063] Редактирование  данных" />
<input type="hidden" name="ctl00$Title_2" id="Title_2" value="&lt;a href=http://school.example.edu.by/main.aspx?guid=1063 target=_new>&lt;img src=/x.png/>&lt;/a>" />
<span id='MERT'><span id="ctl00_Main_ListLang"><input id="ctl00_Main_ListLang_0" type="checkbox" name="ctl00$Main$ListLang$0" checked="checked" /><label for="ctl00_Main_ListLang_0">Русский</label><input id="ctl00_Main_ListLang_1" type="checkbox" name="ctl00$Main$ListLang$1" /><label for="ctl00_Main_ListLang_1">Беларуская</label></span></span>
<table class='ZoneEdit'>
<tr><td valign="top">Тип:</td><td><b>Блок html (текст раздела)</b></td></tr>
<tr><td valign="top">Доступ:</td><td><input id="CheckBoxStatusObject" type="checkbox" name="ctl00$Main$CheckBoxStatusObject" checked="checked" />Разрешить публикацию</td></tr>
<tr><td valign="top">Классификатор:</td><td><span class='OneClassifier'><input type="hidden" name="ctl00$Main$Classifier" id="Classifier" value="1001" /><img src='/images/ElementList/classifier_open.gif' onclick="OneOne.children('span').html(a2);" title='Выбрать'/><span>Главная страница/</span></span></td></tr>
<tr><td valign="top">Теги:</td><td><input name="ctl00$Main$Tags" type="text" id="ctl00_Main_Tags" value="школа" /></td></tr>
<tr><td>Описание блока:</td><td><input name="ctl00$Main$name" type="text" id="ctl00_Main_name" value="основной" /></td></tr>
</table>
<textarea name="ctl00$Main$text" id="ctl00_Main_text">
&lt;p&gt;Добро пожаловать&lt;/p&gt;</textarea>
<textarea name="ctl00$Main$dop" id="ctl00_Main_dop">
</textarea>
</form>"""


def test_parse_object_editor():
    obj = parse_object_editor("1063", EDITOR)
    assert obj.type == "Блок html (текст раздела)"
    assert obj.name == "основной" and obj.tags == "школа"
    assert obj.published is True
    assert obj.section_id == "1001" and obj.section_path == "Главная страница/"
    assert obj.languages == ["Русский"]
    assert obj.public_url == "http://school.example.edu.by/main.aspx?guid=1063"
    assert obj.text == "<p>Добро пожаловать</p>" and obj.dop == ""


def test_parse_object_editor_unpublished():
    html = EDITOR.replace(
        'name="ctl00$Main$CheckBoxStatusObject" checked="checked"',
        'name="ctl00$Main$CheckBoxStatusObject"',
    )
    assert parse_object_editor("1063", html).published is False


def test_treecache_roundtrip_and_stale_path(tmp_path):
    from edu_by.api import treecache
    from edu_by.api.explorer import ExplorerError, Section
    from edu_by.config import Settings

    s = Settings(session_dir=tmp_path, site="sch1.example.edu.by")
    page = WebFormPage(client=None, url="https://wp.example.edu.by/explorer.aspx")  # type: ignore[arg-type]
    page.fields["ctl00$Main_Left$GUID_CLASSIFIER"] = "1001"
    ex = Explorer(page)
    ex._learn(TREE)
    treecache.save(s, ex)
    assert treecache.cache_file(s).name == "tree-sch1.example.edu.by.json"
    cached = treecache.load(s)
    assert cached["1051"].path == ["1001", "1051"] and cached["1051"].parent_id == "1001"

    # A cached path is followed instead of walking; a dead one is marked stale.
    ex2 = Explorer(page)
    ex2._learn(TREE)
    ex2.cached = {"9999": Section("9999", "gone", "1001", ["1001", "9999"])}
    calls = []
    ex2.find_path = lambda path: calls.append(path) or (_ for _ in ()).throw(ExplorerError("x"))  # type: ignore[method-assign]
    ex2.walk = lambda *a, **k: iter(())  # type: ignore[method-assign]
    with pytest.raises(ExplorerError):
        ex2.find_section("9999")
    assert calls == [["1001", "9999"]] and ex2.stale == {"9999"}
    treecache.save(s, ex2)
    assert "9999" not in treecache.load(s)
