"""Read-only access to explorer.aspx: section tree, object types, objects of a section.

How the tree behaves (verified live, see knowledge/endpoints/explorer.md):
- The tree is revealed lazily: a section's children appear only after it is selected.
- Only a node that is visible in the current tree can be selected; selecting a hidden
  node, or the node that is already current, answers with an `error|500|` record.
- The server remembers the current node (and what is expanded) per session.

Nothing here writes: selecting nodes and paging only change the UI state of the session.
"""

from __future__ import annotations

import re
import time
from collections.abc import Callable, Iterator
from dataclasses import asdict, dataclass, field
from html.parser import HTMLParser

import httpx

from edu_by.webforms import DeltaRecord, WebFormPage, strip_tags

SCRIPT_MANAGER = "ctl00$ScriptManagerWindow"
TREE_PANEL = "ctl00$Main_Left$UpdatePanel1"
TREE_TARGET = "ctl00$Main_Left$TreeClassifier"
PAGER_PANEL = "ctl00$ContentSecondMenu$UpdatePanel3"
PAGER_TARGET = "ctl00$ContentSecondMenu$PageList"
CURRENT_FIELD = "ctl00$Main_Left$GUID_CLASSIFIER"

TREE_PANEL_ID = "ctl00_Main_Left_UpdatePanel1"
LIST_PANEL_ID = "ctl00_Main_Right_UpdatePanelMainList"
PAGER_PANEL_ID = "ctl00_ContentSecondMenu_UpdatePanel3"

SECTION = "sNodeClassifier"
TEMPLATE = "sNodeTemplate"
TRASH = "sNodeTrashe"


class ExplorerError(RuntimeError):
    pass


# ---------- tree parsing ----------


@dataclass
class TreeNode:
    index: int  # position in the rendered TreeView (t<N>), only stable within one render
    kind: str | None  # SECTION / TEMPLATE / TRASH, None for grouping nodes
    value: str | None  # postback argument, e.g. sNodeClassifier\1001\1051; None if not a link
    id: str | None
    title: str
    parent_index: int | None
    has_children: bool  # a toggle is rendered (children may still be unloaded if False)
    selected: bool


_NODE_ID = re.compile(r"TreeClassifiert(\d+)$")
_TOGGLE_ID = re.compile(r"TreeClassifiern(\d+)$")
_CHILDREN_ID = re.compile(r"TreeClassifiern(\d+)Nodes$")
_POSTBACK_ARG = re.compile(r"__doPostBack\('[^']*','(.*)'\)")


class _TreeParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.nodes: dict[int, TreeNode] = {}
        self.toggles: set[int] = set()
        self._divs: list[int | None] = []
        self._cur: TreeNode | None = None
        self._cur_tag = ""
        self._depth = 0
        self._text: list[str] = []

    def _parent(self) -> int | None:
        return next((d for d in reversed(self._divs) if d is not None), None)

    def handle_starttag(self, tag, attrs):
        a = {k: (v or "") for k, v in attrs}
        if tag == "div":
            m = _CHILDREN_ID.search(a.get("id", ""))
            self._divs.append(int(m.group(1)) if m else None)
            return
        if self._cur is not None:
            if tag == self._cur_tag:
                self._depth += 1
            if tag == "img" and a.get("guid") and self._cur.id is None:
                self._cur.id = a["guid"]
            return
        if tag == "a" and _TOGGLE_ID.search(a.get("id", "")):
            self.toggles.add(int(_TOGGLE_ID.search(a["id"]).group(1)))
            return
        m = _NODE_ID.search(a.get("id", ""))
        if tag in ("a", "span") and m:
            value = None
            pb = _POSTBACK_ARG.search(a.get("href", ""))
            if pb:
                value = pb.group(1).replace("\\\\", "\\")
            idx = int(m.group(1))
            self._cur = TreeNode(idx, None, value, None, "", self._parent(), False, tag == "span")
            self._cur_tag, self._depth, self._text = tag, 0, []

    def handle_endtag(self, tag):
        if tag == "div" and self._divs:
            self._divs.pop()
            return
        if self._cur is not None and tag == self._cur_tag:
            if self._depth:
                self._depth -= 1
                return
            node = self._cur
            node.title = re.sub(r"\s+", " ", "".join(self._text)).strip()
            if node.value:
                parts = node.value.split("\\")
                node.kind, node.id = parts[0], parts[-1]
            elif node.id:  # the selected node is a span; only sections carry a guid icon
                node.kind = SECTION
            self.nodes[node.index] = node
            self._cur = None

    def handle_data(self, data):
        if self._cur is not None:
            self._text.append(data)


def parse_tree(fragment: str) -> list[TreeNode]:
    p = _TreeParser()
    p.feed(fragment)
    for idx in p.toggles:
        if idx in p.nodes:
            p.nodes[idx].has_children = True
    return [p.nodes[i] for i in sorted(p.nodes)]


# ---------- object list parsing ----------


@dataclass
class ObjectRow:
    id: str
    type_label: str  # short label shown in the list, e.g. "Блок html", "Граф объект"
    title: str
    published: bool


_ROW = re.compile(r"<tr([^>]*)\sguid='(\d+)'[^>]*>(.*?)</tr>", re.S)


def parse_object_list(fragment: str) -> list[ObjectRow]:
    i = fragment.find("id='ListElements'")
    if i < 0:
        return []
    table = fragment[i : fragment.find("</table>", i)]
    rows = []
    for attrs, guid, body in _ROW.findall(table):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", body, re.S)
        text = strip_tags(cells[-1]) if cells else ""
        label, sep, title = text.partition(":")
        if not sep:
            label, title = "", text
        rows.append(ObjectRow(guid, label.strip(), title.strip(), "obj_not_published" not in attrs))
    return rows


def parse_pages(fragment: str) -> tuple[int | None, list[int]]:
    """Current page index and the page indexes offered by the pager (`PageList` select)."""
    m = re.search(
        r'<select[^>]*name="ctl00\$ContentSecondMenu\$PageList".*?</select>', fragment, re.S
    )
    if not m:
        return None, []
    opts = re.findall(r'<option( selected="selected")? value="(\d+)"', m.group(0))
    current = next((int(v) for sel, v in opts if sel), None)
    return current, sorted({int(v) for _, v in opts})


# ---------- types ----------


@dataclass
class ObjectType:
    id: str
    name: str
    group: str  # tree group, e.g. Стандартные, Системные, Не в группе


def types_from_tree(nodes: list[TreeNode]) -> list[ObjectType]:
    seen: dict[str, ObjectType] = {}
    for n in nodes:
        if n.kind == TEMPLATE and n.value and n.id and n.title:
            group = n.value.split("\\")[1] if n.value.count("\\") >= 2 else ""
            seen.setdefault(n.id, ObjectType(n.id, n.title, group))
    return list(seen.values())


# ---------- the explorer session ----------


@dataclass
class Section:
    id: str
    title: str
    parent_id: str | None
    path: list[str]  # IDs from the root, e.g. ["1001", "1051"]
    children_loaded: bool = False

    def as_dict(self) -> dict:
        d = asdict(self)
        d["path"] = "/".join(self.path)
        return d


@dataclass
class Explorer:
    """One loaded explorer.aspx page, kept current across tree selections and paging."""

    page: WebFormPage
    delay: float = 0.5
    tree_html: str = ""
    list_html: str = ""
    pager_html: str = ""
    sections: dict[str, Section] = field(default_factory=dict)
    on_request: Callable[[int, str], None] | None = None  # progress hook: (count, what)
    cached: dict[str, Section] = field(
        default_factory=dict
    )  # paths from an earlier run (treecache)
    stale: set[str] = field(default_factory=set)  # cached sections whose path no longer works
    max_requests: int = 3000  # safety stop for one command
    _requests: int = 0

    @classmethod
    def open(cls, client: httpx.Client, url: str, delay: float = 0.5) -> Explorer:
        page = WebFormPage.load(client, url)
        if 'type="password"' in page.html.lower() or CURRENT_FIELD not in page.fields:
            raise ExplorerError("explorer.aspx did not load (session expired?)")
        ex = cls(page, delay, page.html, page.html, page.html)
        ex._learn(page.html)
        return ex

    @property
    def current(self) -> str:
        return self.page.fields.get(CURRENT_FIELD, "")

    def nodes(self) -> list[TreeNode]:
        return parse_tree(self.tree_html)

    def _learn(self, fragment: str) -> None:
        """Record every section visible in a tree render."""
        nodes = parse_tree(fragment)
        by_index = {n.index: n for n in nodes}
        for n in nodes:
            if n.kind != SECTION or not n.id:
                continue
            path = n.value.split("\\")[1:] if n.value else None
            if path is None:  # selected node: rebuild the path from its ancestors
                chain, p = [n.id], by_index.get(n.parent_index)
                while p is not None and p.kind == SECTION and p.id:
                    chain.insert(0, p.id)
                    p = by_index.get(p.parent_index)
                path = chain
            known = self.sections.get(n.id)
            parent = path[-2] if len(path) > 1 else None
            if known is None:
                self.sections[n.id] = Section(n.id, n.title, parent, path)
            elif n.title:
                known.title = n.title

    def _postback(self, panel: str, target: str, arg: str = "", extra=None) -> list[DeltaRecord]:
        if self._requests >= self.max_requests:
            raise ExplorerError(f"stopped after {self._requests} requests (max_requests)")
        if self._requests:
            time.sleep(self.delay)
        self._requests += 1
        if self.on_request:
            self.on_request(self._requests, arg or f"{target}={extra}")
        records = self.page.async_postback(SCRIPT_MANAGER, panel, target, arg, extra)
        for r in records:
            if r.type == "updatePanel" and r.id == TREE_PANEL_ID:
                self.tree_html = r.content
                self._learn(r.content)
            elif r.type == "updatePanel" and r.id == LIST_PANEL_ID:
                self.list_html = r.content
            elif r.type == "updatePanel" and r.id == PAGER_PANEL_ID:
                self.pager_html = r.content
        return records

    def _visible(self, value: str) -> bool:
        return any(n.value == value for n in self.nodes())

    @staticmethod
    def _value(sec: Section) -> str:
        return SECTION + "\\" + "\\".join(sec.path)

    def _reveal(self, sec: Section) -> None:
        """Make a known section visible by selecting its ancestors, nearest visible first."""
        if self._visible(self._value(sec)):
            return
        parent = self.sections.get(sec.parent_id or "")
        if parent is None or parent.id == self.current:
            raise ExplorerError(f"section {sec.id} is not visible in the tree")
        self._reveal(parent)
        self._select_value(self._value(parent))
        if not self._visible(self._value(sec)):
            raise ExplorerError(f"section {sec.id} did not appear under {parent.id}")

    def select_section(self, section_id: str) -> Section:
        """Make a section current (its children and objects become visible)."""
        sec = self.sections.get(section_id)
        if sec is None:
            raise ExplorerError(f"section {section_id} is not known yet – find it first")
        if section_id == self.current:  # re-selecting the current node is a server error
            return sec
        self._reveal(sec)
        self._select_value(self._value(sec))
        return sec

    def _select_value(self, value: str) -> None:
        records = self._postback(TREE_PANEL, TREE_TARGET, value)
        if any(r.type == "error" for r in records):
            raise ExplorerError(f"selecting {value} failed (server error)")
        sid = value.split("\\")[-1]
        if value.startswith(SECTION) and sid in self.sections:
            self.sections[sid].children_loaded = True

    def children(self, section_id: str) -> list[Section]:
        return [s for s in self.sections.values() if s.parent_id == section_id]

    def walk(self, root_id: str | None = None, depth: int | None = None) -> Iterator[Section]:
        """Yield sections depth-first, selecting each one to reveal its children.

        `depth` = how many levels below the root(s) to descend (0 = only the roots),
        None = the whole subtree. Each section is selected at most once.
        """
        if root_id:
            roots = [self.sections[root_id]]
        else:
            roots = [s for s in self.sections.values() if s.parent_id is None]
        stack = [(r, 0) for r in reversed(roots)]
        while stack:
            sec, level = stack.pop()
            yield sec
            if depth is not None and level >= depth:
                continue
            if not sec.children_loaded:
                self.select_section(sec.id)
                sec.children_loaded = True
            stack.extend((c, level + 1) for c in reversed(self.children(sec.id)))

    def find_path(self, path: list[str]) -> Section:
        """Locate a section by its ID path from the root (one request per ancestor)."""
        for i, sid in enumerate(path):
            if sid not in self.sections and i:
                self.select_section(path[i - 1])
            if sid not in self.sections:
                raise ExplorerError(f"section {sid} not found under {'/'.join(path[:i]) or 'root'}")
        return self.sections[path[-1]]

    def find_section(self, section_id: str, max_selects: int = 500) -> Section:
        """Locate a section by ID, or by an ID path like 1001/1041/1201.

        A bare ID that is not visible yet is searched by walking the tree (slow);
        a path needs one request per ancestor.
        """
        if "/" in section_id:
            return self.find_path([p for p in section_id.strip("/").split("/") if p])
        if section_id in self.sections:
            return self.sections[section_id]
        hit = self.cached.get(section_id)
        if hit is not None:
            try:
                return self.find_path(hit.path)
            except ExplorerError:  # moved or deleted since it was cached: walk instead
                self.stale.add(section_id)
                self.cached.pop(section_id, None)
        for i, _ in enumerate(self.walk()):
            if section_id in self.sections:
                return self.sections[section_id]
            if i >= max_selects:
                break
        raise ExplorerError(f"section {section_id} not found in the tree")

    def objects(self, section_id: str, max_pages: int = 200) -> list[ObjectRow]:
        """All objects of a section, following the pager."""
        section_id = self.find_section(section_id).id
        self.select_section(section_id)  # no request if it is already current
        current, pages = parse_pages(self.pager_html)
        if current:  # the server kept another page of this list open: start from the first
            self._postback(PAGER_PANEL, PAGER_TARGET, "", {PAGER_TARGET: "0"})
            current, pages = parse_pages(self.pager_html)
        current = current or 0
        rows = parse_object_list(self.list_html)
        for _ in range(max_pages):
            nxt = current + 1
            if not pages or max(pages) < nxt:
                break
            self._postback(PAGER_PANEL, PAGER_TARGET, "", {PAGER_TARGET: str(nxt)})
            rows += parse_object_list(self.list_html)
            current, pages = parse_pages(self.pager_html)
            current = nxt if current is None else current
        return rows
