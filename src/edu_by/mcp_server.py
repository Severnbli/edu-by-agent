"""MCP server (`edu mcp`, stdio): the constructor's reads and planned writes as tools.

Design: docs/mcp.md. The server adds no request logic – every tool calls `edu_by.api` with
one shared `Site`. Writes follow the preview / `confirm_token` contract of `Change`.
Prompts are the skills' MCP scenarios (`.claude/skills/<name>/mcp.md`), resources are the
`knowledge/` files.

stdout carries the protocol: nothing here may print. Progress goes to stderr.
"""

from __future__ import annotations

import contextlib
import re
import sys
import threading
from collections.abc import Callable
from dataclasses import asdict
from functools import partial
from pathlib import Path
from typing import Any, Literal

import anyio
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.server.fastmcp.resources import FileResource
from mcp.types import ToolAnnotations

from edu_by import session as sess
from edu_by.config import Settings, get_settings

REPO = Path(__file__).resolve().parents[2]
SKILLS = REPO / ".claude" / "skills"
KNOWLEDGE = REPO / "knowledge"
MAX_TREE_DEPTH = 3
DEFAULT_LIST_PAGES = 3

INSTRUCTIONS = """\
Tools for the edu.by site constructor of one school website (a live public site).

- Every write tool works in two steps. Called without `confirm_token` it changes nothing
  and returns a preview: what changes (before/after), its level and a `token`. Show the
  preview to the user and ask. Only after their OK call the same tool with the same
  arguments and `confirm_token` = that token. Level `publish` is visible on the public site
  at once; `delete` moves to the trash or deletes for good.
- A `TokenMismatch` error means the site or the request changed: preview again.
- `result.verified` false means the write happened but the re-read differs: tell the user.
- "Session expired": the user must log in (`./edu session login`, they solve a captcha);
  never try to log in yourself. Then retry.
- Sections are given by id (`1041`) or id path (`1001/1041`); prefer paths – a bare id that
  isn't cached costs a walk of the whole tree.
- New objects are unpublished. Only images upload (≤ ~300 KB, `shrink` re-encodes);
  documents go on the site as links. Never purge objects the user didn't name.
- The prompts (`edu_publish_news`, …) are step-by-step scenarios; resources hold the
  constructor knowledge.
"""

READ = ToolAnnotations(readOnlyHint=True, openWorldHint=True)


def _write(level: Literal["edit", "publish", "delete"]) -> ToolAnnotations:
    return ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=level == "delete",
        idempotentHint=False,
        openWorldHint=True,
    )


CONTRACT = (
    " Without `confirm_token`: preview only (changes nothing) – show it to the user. "
    "With the preview's token after the user's OK: applies, re-reads and returns `result`."
)


class Runtime:
    """The server's one `Site`, opened on first use and dropped when the session expires."""

    def __init__(self, settings: Settings | None = None, site_factory: Callable | None = None):
        self.settings = settings or get_settings()
        self._factory = site_factory
        self._site = None
        self._open_lock = threading.Lock()

    def site(self):
        from edu_by.site import Site

        with self._open_lock:
            if self._site is None:
                if self._factory:
                    self._site = self._factory()
                else:
                    self._site = Site(self.settings, on_request=self._progress())
            return self._site

    def _progress(self):
        if not self.settings.verbose:
            return None
        return lambda n, what: print(f"[{n}] {what}", file=sys.stderr, flush=True)

    def drop(self) -> None:
        with self._open_lock:
            if self._site is not None:
                with contextlib.suppress(Exception):
                    self._site.close()
            self._site = None

    def call(self, fn: Callable, *args: Any) -> Any:
        """Run `fn(site, *args)` under the site lock, mapping errors to tool errors."""
        from edu_by.api.changes import TokenMismatch
        from edu_by.site import SessionExpired

        try:
            site = self.site()
            with site.lock:
                return fn(site, *args)
        except SessionExpired as e:
            self.drop()
            raise ToolError(_expired(str(e))) from e
        except TokenMismatch as e:
            raise ToolError(f"TokenMismatch: {e}") from e
        except ToolError:
            raise
        except Exception as e:  # ExplorerError, WriteError, ObjectError, HTTP errors
            text = str(e) or type(e).__name__
            if re.search(r"session expired|login page", text, re.I):
                self.drop()
                raise ToolError(_expired(text)) from e
            if self._site is not None:
                self._site.reset_explorer()  # a half-done postback: reload explorer next time
            raise ToolError(text) from e


def _expired(detail: str) -> str:
    return (
        f"Session expired ({detail}). Ask the user to run `./edu session login` "
        "(they solve the captcha), then retry."
    )


def _plan_or_apply(change, confirm_token: str | None) -> dict:
    preview = change.preview()
    if confirm_token is None or change.noop:
        return {
            "preview": preview,
            "applied": False,
            "next": "nothing to change"
            if change.noop
            else "show this preview to the user; after their OK call again with "
            f"confirm_token={change.token!r}",
        }
    result = change.apply(confirm_token)
    return {"plan": preview, "result": result}


def _inside_repo(path: str) -> Path:
    p = Path(path)
    p = (REPO / p).resolve() if not p.is_absolute() else p.resolve()
    if not p.is_relative_to(REPO):
        raise ToolError(f"{path}: files must be inside the repository ({REPO})")
    if not p.is_file():
        raise ToolError(f"{path}: no such file")
    return p


# ---------- prompts from the skills ----------


def skill_prompts() -> list[tuple[str, str, str]]:
    """(prompt name, description, text) for every skill that has an MCP scenario."""
    out = []
    for f in sorted(SKILLS.glob("*/mcp.md")):
        text = f.read_text(encoding="utf-8")
        desc = ""
        skill = f.parent / "SKILL.md"
        if skill.exists():
            m = re.search(r"^description:\s*(.+)$", skill.read_text(encoding="utf-8"), re.M)
            desc = m.group(1).strip() if m else ""
        out.append((f.parent.name.replace("-", "_"), desc, text))
    return out


def knowledge_files() -> list[Path]:
    return sorted(p for p in KNOWLEDGE.rglob("*.md") if "captures" not in p.parts)


# ---------- the server ----------


def build_server(runtime: Runtime | None = None) -> FastMCP:
    rt = runtime or Runtime()
    mcp = FastMCP("edu-by", instructions=INSTRUCTIONS, log_level="WARNING")

    async def run(fn: Callable, *args: Any) -> Any:
        return await anyio.to_thread.run_sync(partial(rt.call, fn, *args))

    def tool(name: str, title: str, annotations: ToolAnnotations, description: str):
        return mcp.tool(name=name, title=title, annotations=annotations, description=description)

    # ----- reads -----

    @tool(
        "edu_session_status",
        "Session status",
        READ,
        "Whether the saved constructor session is valid (IsSession), with masked cookies. "
        "Check before a batch of work.",
    )
    async def edu_session_status() -> dict:
        def check() -> dict:
            s = rt.settings
            try:
                res = sess.check(s)
            except sess.SessionError as e:
                return {"valid": False, "reason": str(e)}
            return {
                "valid": res.valid,
                "reason": res.reason,
                "site": s.site_host,
                "cookies": sess.cookie_summary(s),
            }

        return await anyio.to_thread.run_sync(check)

    @tool(
        "edu_tree",
        "Section tree",
        READ,
        f"Sections (pages of the menu) under `root` (default: all roots), `depth` levels deep "
        f"(1..{MAX_TREE_DEPTH}). Each level costs one request (~1 s) per section above it.",
    )
    async def edu_tree(root: str | None = None, depth: int = 1) -> dict:
        if not 1 <= depth <= MAX_TREE_DEPTH:
            raise ToolError(f"depth must be 1..{MAX_TREE_DEPTH}")

        def f(site) -> dict:
            ex = site.explorer()
            root_id = ex.find_section(root).id if root else None
            return {"sections": [s.as_dict() for s in ex.walk(root_id, depth)]}

        return await run(f)

    @tool(
        "edu_find_section",
        "Find a section",
        READ,
        "Locate a section by id or id path: id, title, parent, path.",
    )
    async def edu_find_section(section: str) -> dict:
        return await run(lambda site: site.explorer().find_section(section).as_dict())

    @tool(
        "edu_section",
        "Section properties",
        READ,
        "A section's properties: title, internal name, protection from deletion, tags, "
        "template, redirect.",
    )
    async def edu_section(section: str) -> dict:
        from edu_by.api import sections

        def f(site) -> dict:
            sec = site.explorer().find_section(section)
            return {**sections.read_section(site, sec.id), "path": "/".join(sec.path)}

        return await run(f)

    @tool(
        "edu_objects",
        "Objects of a section",
        READ,
        "The objects (content items) of a section in their order: id, type, title, published. "
        f"Reads the first `pages` list pages (default {DEFAULT_LIST_PAGES}); `more` tells "
        "whether the list goes on.",
    )
    async def edu_objects(section: str, pages: int = DEFAULT_LIST_PAGES) -> dict:
        from edu_by.api.explorer import parse_pages

        if pages < 1:
            raise ToolError("pages must be ≥ 1")

        def f(site) -> dict:
            ex = site.explorer()
            sec = ex.find_section(section)
            rows = ex.objects(sec.id, max_pages=pages - 1)
            current, offered = parse_pages(ex.pager_html)
            more = bool(offered) and max(offered) > (current or 0)
            return {
                "section": sec.as_dict(),
                "objects": [asdict(r) for r in rows],
                "more": more,
            }

        return await run(f)

    @tool(
        "edu_object",
        "Read an object",
        READ,
        "One object: type, section, published, public_url, the editable field names and "
        "their current values (full HTML).",
    )
    async def edu_object(id: str) -> dict:
        from edu_by.api.objects_write import read_object_fields

        return await run(read_object_fields, id)

    @tool("edu_types", "Object types", READ, "Object type ids (524 Блок html, 534 Новость, …).")
    async def edu_types() -> dict:
        from edu_by.api.explorer import types_from_tree

        return await run(
            lambda site: {"types": [asdict(t) for t in types_from_tree(site.explorer().nodes())]}
        )

    @tool(
        "edu_trash_list",
        "Trash of a type",
        READ,
        "One page (from 0, newest first) of a type's trash. It also holds other people's "
        "deleted objects.",
    )
    async def edu_trash_list(type_id: str, page: int = 0) -> dict:
        from edu_by.api.trash import list_trash

        return await run(list_trash, type_id, page)

    # ----- writes -----

    @tool(
        "edu_object_update",
        "Edit an object",
        _write("publish"),
        "Set text fields of an object (`values`: short names from edu_object, e.g. name, "
        "text, zag, txt, dt_text dd.mm.yyyy, url, tags) and/or `published`. Other fields "
        "keep their values." + CONTRACT,
    )
    async def edu_object_update(
        id: str,
        values: dict[str, str] | None = None,
        published: bool | None = None,
        confirm_token: str | None = None,
    ) -> dict:
        from edu_by.api import objects_write as ow

        return await run(
            lambda site: _plan_or_apply(ow.plan_update(site, id, values, published), confirm_token)
        )

    @tool(
        "edu_object_create",
        "Create objects",
        _write("edit"),
        "Create `count` (1..20) unpublished objects of `type_id` in a section, with optional "
        "field `values`. The result lists the new ids (ids are reused – take them from "
        "here)." + CONTRACT,
    )
    async def edu_object_create(
        section: str,
        type_id: str,
        count: int = 1,
        values: dict[str, str] | None = None,
        confirm_token: str | None = None,
    ) -> dict:
        from edu_by.api import objects_write as ow

        def f(site) -> dict:
            sec = site.explorer().find_section(section)
            return _plan_or_apply(
                ow.plan_create(site, sec.id, type_id, count, values), confirm_token
            )

        return await run(f)

    @tool(
        "edu_object_copy",
        "Copy an object",
        _write("edit"),
        "An unpublished copy of an object in the same section." + CONTRACT,
    )
    async def edu_object_copy(id: str, confirm_token: str | None = None) -> dict:
        from edu_by.api import objects_write as ow

        return await run(lambda site: _plan_or_apply(ow.plan_copy(site, id), confirm_token))

    @tool(
        "edu_object_move",
        "Move objects",
        _write("publish"),
        "Move objects (all from one section) to another section." + CONTRACT,
    )
    async def edu_object_move(
        ids: list[str], target_section: str, confirm_token: str | None = None
    ) -> dict:
        from edu_by.api import objects_write as ow

        def f(site) -> dict:
            target = site.explorer().find_section(target_section)
            return _plan_or_apply(ow.plan_move(site, ids, target.id), confirm_token)

        return await run(f)

    @tool(
        "edu_object_sort",
        "Reorder objects",
        _write("publish"),
        "New order of a section's objects: `order` lists all their ids." + CONTRACT,
    )
    async def edu_object_sort(
        section: str, order: list[str], confirm_token: str | None = None
    ) -> dict:
        from edu_by.api import objects_write as ow

        def f(site) -> dict:
            sec = site.explorer().find_section(section)
            return _plan_or_apply(ow.plan_sort(site, sec.id, order), confirm_token)

        return await run(f)

    @tool(
        "edu_object_upload_image",
        "Upload an image",
        _write("publish"),
        "Upload an image file (path inside the repository) into an image object (type 304) "
        "or a news item. `shrink` (default) re-encodes a bigger photo as JPEG under the "
        "~300 KB limit. Documents can't be uploaded – link them instead." + CONTRACT,
    )
    async def edu_object_upload_image(
        id: str, path: str, shrink: bool = True, confirm_token: str | None = None
    ) -> dict:
        from edu_by.api import objects_write as ow

        file = _inside_repo(path)

        def f(site) -> dict:
            src = ow.shrink_image(file, rt.settings.session_dir / "upload") if shrink else file
            return _plan_or_apply(ow.plan_upload_image(site, id, src), confirm_token)

        return await run(f)

    @tool(
        "edu_object_trash",
        "Move objects to the trash",
        _write("delete"),
        "Move objects (all from one section) to the trash of their types (restorable)." + CONTRACT,
    )
    async def edu_object_trash(ids: list[str], confirm_token: str | None = None) -> dict:
        from edu_by.api import objects_write as ow

        return await run(lambda site: _plan_or_apply(ow.plan_trash(site, ids), confirm_token))

    @tool(
        "edu_section_add",
        "Add a section",
        _write("publish"),
        "A new section (menu page) at the end of `parent`, with a title; protected from "
        "deletion unless `protected` is false. It appears in the site menu at once." + CONTRACT,
    )
    async def edu_section_add(
        parent: str, title: str, protected: bool = True, confirm_token: str | None = None
    ) -> dict:
        from edu_by.api import sections

        return await run(
            lambda site: _plan_or_apply(
                sections.plan_add(site, parent, title, protected), confirm_token
            )
        )

    @tool(
        "edu_section_update",
        "Edit a section",
        _write("publish"),
        "Change a section's title, internal name, tags, protection from deletion or page "
        "template (`template`: a «Обычный» template id, `0` = inherit)." + CONTRACT,
    )
    async def edu_section_update(
        section: str,
        title: str | None = None,
        name: str | None = None,
        protected: bool | None = None,
        tags: str | None = None,
        template: str | None = None,
        confirm_token: str | None = None,
    ) -> dict:
        from edu_by.api import sections

        def f(site) -> dict:
            sec = site.explorer().find_section(section)
            change = sections.plan_update(site, sec.id, title, name, protected, tags, template)
            return _plan_or_apply(change, confirm_token)

        return await run(f)

    @tool(
        "edu_section_move",
        "Move a section",
        _write("publish"),
        "Put a section `above` / `below` the target section (same parent) or `inside` it, "
        "with its subsections and objects." + CONTRACT,
    )
    async def edu_section_move(
        section: str,
        target: str,
        position: Literal["above", "inside", "below"] = "inside",
        confirm_token: str | None = None,
    ) -> dict:
        from edu_by.api import sections

        return await run(
            lambda site: _plan_or_apply(
                sections.plan_move(site, section, target, position), confirm_token
            )
        )

    @tool(
        "edu_section_delete",
        "Delete a section",
        _write("delete"),
        "Delete a section without subsections; its objects go to the trash, the section "
        "itself can't be restored. A protected section is refused (unprotect it first)." + CONTRACT,
    )
    async def edu_section_delete(section: str, confirm_token: str | None = None) -> dict:
        from edu_by.api import sections

        return await run(
            lambda site: _plan_or_apply(sections.plan_delete(site, section), confirm_token)
        )

    @tool(
        "edu_trash_restore",
        "Restore from the trash",
        _write("edit"),
        "Move named objects from a type's trash into a section." + CONTRACT,
    )
    async def edu_trash_restore(
        type_id: str, ids: list[str], section: str, confirm_token: str | None = None
    ) -> dict:
        from edu_by.api import trash

        def f(site) -> dict:
            sec = site.explorer().find_section(section)
            return _plan_or_apply(trash.plan_restore(site, type_id, ids, sec.id), confirm_token)

        return await run(f)

    @tool(
        "edu_trash_purge",
        "Delete for good",
        _write("delete"),
        "IRREVERSIBLE: permanently delete named objects (≤ 50) from a type's trash. Only "
        "objects the user named – never other people's." + CONTRACT,
    )
    async def edu_trash_purge(
        type_id: str, ids: list[str], confirm_token: str | None = None
    ) -> dict:
        from edu_by.api import trash

        return await run(
            lambda site: _plan_or_apply(trash.plan_purge(site, type_id, ids), confirm_token)
        )

    # ----- design (site-wide) -----

    @tool(
        "edu_design_list",
        "Design items of a category",
        READ,
        "Items of a design category: Master | Head | Normal | 404 | NotUseTemplate (templates), "
        "Actual | Old | NotUse (modules), CssPacked, JavaScript, ResourceString, TemplateGlobal.",
    )
    async def edu_design_list(category: str) -> dict:
        from edu_by.api import design

        return await run(lambda site: {"items": design.list_category(site, category)})

    @tool(
        "edu_design_item",
        "Design item",
        READ,
        "One design item (`kind`: template | control | css | js | string): its fields – the "
        "names `edu_design_update` takes – and for a template its master and attached CSS / JS. "
        "`full` returns long values (HTML) in full.",
    )
    async def edu_design_item(kind: str, id: str, full: bool = False) -> dict:
        from edu_by.api import design

        return await run(lambda site: design.read_item(site, kind, id).summary(full=full))

    @tool(
        "edu_design_update",
        "Change a design item",
        _write("publish"),
        "SITE-WIDE: save fields of a template / module / style set / script / resource string "
        "(`values`: field -> new value, others keep theirs); for a template also attach (as "
        "last) or detach style sets and scripts by id. Every page using the item changes at "
        "once – prefer working on a copy." + CONTRACT,
    )
    async def edu_design_update(
        kind: str,
        id: str,
        values: dict[str, str] | None = None,
        attach_css: list[str] | None = None,
        detach_css: list[str] | None = None,
        attach_js: list[str] | None = None,
        detach_js: list[str] | None = None,
        confirm_token: str | None = None,
    ) -> dict:
        from edu_by.api import design

        return await run(
            lambda site: _plan_or_apply(
                design.plan_set(
                    site, kind, id, values, attach_css, detach_css, attach_js, detach_js
                ),
                confirm_token,
            )
        )

    @tool(
        "edu_design_copy",
        "Copy a design item",
        _write("edit"),
        "«Создать копию» of a template / module / style set / script / resource string, named "
        "`name` (e.g. «Редизайн 2026. …»). The copy is used nowhere yet." + CONTRACT,
    )
    async def edu_design_copy(
        kind: str, id: str, name: str, confirm_token: str | None = None
    ) -> dict:
        from edu_by.api import design

        return await run(
            lambda site: _plan_or_apply(design.plan_copy(site, kind, id, name), confirm_token)
        )

    @tool(
        "edu_design_create",
        "New style set or script",
        _write("edit"),
        "A new style set (`kind` css) or script (js) with `name` and `body`; used nowhere "
        "until a template attaches it (edu_design_update attach_css)." + CONTRACT,
    )
    async def edu_design_create(
        kind: str, name: str, body: str = "", confirm_token: str | None = None
    ) -> dict:
        from edu_by.api import design

        return await run(
            lambda site: _plan_or_apply(design.plan_create(site, kind, name, body), confirm_token)
        )

    @tool(
        "edu_design_delete",
        "Delete a design item",
        _write("delete"),
        "IRREVERSIBLE (no trash): delete a design item. Only items named «Редизайн…» / «Тест…» "
        "unless `force` – and force only for an item the user named." + CONTRACT,
    )
    async def edu_design_delete(
        kind: str, id: str, force: bool = False, confirm_token: str | None = None
    ) -> dict:
        from edu_by.api import design

        return await run(
            lambda site: _plan_or_apply(design.plan_delete(site, kind, id, force), confirm_token)
        )

    @tool(
        "edu_cache_clear",
        "Clear the site cache",
        _write("publish"),
        "Clear the public site cache so pages are rebuilt from the current design (harmless)."
        + CONTRACT,
    )
    async def edu_cache_clear(confirm_token: str | None = None) -> dict:
        from edu_by.api import design

        return await run(lambda site: _plan_or_apply(design.plan_clear_cache(site), confirm_token))

    # ----- prompts and resources -----

    for name, desc, text in skill_prompts():
        _add_prompt(mcp, name, desc, text)

    for path in knowledge_files():
        rel = path.relative_to(KNOWLEDGE).as_posix()
        mcp.add_resource(
            FileResource(
                uri=f"edu://knowledge/{rel}",
                name=f"knowledge/{rel}",
                description=_first_heading(path),
                mime_type="text/markdown",
                path=path,
            )
        )

    return mcp


def _add_prompt(mcp: FastMCP, name: str, desc: str, text: str) -> None:
    def prompt(request: str = "") -> str:
        return text + (f"\n\n## The user's request\n\n{request}\n" if request else "")

    mcp.prompt(name=name, description=desc)(prompt)


def _first_heading(path: Path) -> str:
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return path.stem


def serve() -> None:
    """Run on stdio (the `edu mcp` command)."""
    s = get_settings()
    print(
        f"edu-by MCP server: site {s.site_host}, cookies "
        f"{', '.join(sess.cookie_summary(s)) or 'none'}",
        file=sys.stderr,
    )
    build_server(Runtime(s)).run("stdio")
