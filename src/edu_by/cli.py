"""`edu` command-line entry point."""

from __future__ import annotations

import contextlib
import getpass
import json
import sys
import time
from pathlib import Path
from typing import Annotated
from urllib.parse import urlsplit

import httpx
import typer

from edu_by import session as sess
from edu_by import shadowsocks
from edu_by.config import Settings, get_settings, mask_proxy
from edu_by.http import make_client

app = typer.Typer(help="Operate the edu.by site constructor.", no_args_is_help=True)
session_app = typer.Typer(
    help="Obtain, check and keep alive the constructor session.", no_args_is_help=True
)
proxy_app = typer.Typer(help="Proxy and Shadowsocks utilities.", no_args_is_help=True)
har_app = typer.Typer(help="Sanitize and summarize HAR captures.", no_args_is_help=True)
app.add_typer(session_app, name="session")
app.add_typer(proxy_app, name="proxy")
app.add_typer(har_app, name="har")
object_app = typer.Typer(
    help="Show and change objects (writes preview first; --yes applies).", no_args_is_help=True
)
section_app = typer.Typer(
    help="Show and change sections (writes preview first; --yes applies).", no_args_is_help=True
)
trash_app = typer.Typer(help="Object trash: list, restore, delete for good.", no_args_is_help=True)
app.add_typer(object_app, name="object")
app.add_typer(section_app, name="section")
app.add_typer(trash_app, name="trash")

ProxyOpt = Annotated[
    str | None,
    typer.Option("--proxy", help="Proxy URL (http://, socks5h://, ...), overrides EDU_PROXY."),
]


def _settings(proxy: str | None = None) -> Settings:
    s = get_settings()
    return s.model_copy(update={"proxy": proxy}) if proxy else s


def _fail(msg: str, code: int = 1) -> None:
    typer.secho(msg, fg="red", err=True)
    raise typer.Exit(code)


def _proxy_error(s: Settings, e: Exception) -> None:
    hint = (
        " Is the proxy container running (`./edu proxy up`)?"
        if not s.proxy and (s.interface or s.shadowsocks_configured)
        else ""
    )
    _fail(f"Connection failed via {mask_proxy(s.effective_proxy)}: {e}.{hint}")


# ---------- session ----------


@session_app.command("login")
def session_login(
    security: Annotated[
        str | None,
        typer.Option(
            help="Login security level, default Hight (recommended). Lower levels make the "
            "WJG cookie remember the site, username (Low) and probably the password (Zero)."
        ),
    ] = None,
    proxy: ProxyOpt = None,
) -> None:
    """Log in via a desktop browser: form prefilled from .env, you solve the captcha."""
    from edu_by.browser import check_browser_proxy

    s = _settings(proxy)
    if security:
        s = s.model_copy(update={"security": security})
    try:
        check_browser_proxy(s)
    except ValueError as e:
        _fail(str(e))
    typer.echo(f"Proxy: {mask_proxy(s.effective_proxy)}  Login: {s.login_url}")
    prefilled = [k for k in ("site", "username", "password") if getattr(s, k)]
    typer.echo(
        f"Prefilled from .env: {', '.join(prefilled)}. " if prefilled else "Fill in the form, "
    )
    typer.echo("Solve the captcha and click Авторизация – the window closes by itself.")
    try:
        n = sess.login_via_browser(s)
    except sess.SessionError as e:
        _fail(str(e))
    typer.echo(f"Saved {n} cookie(s) to {s.cookies_file}")
    _report_check(s)


@session_app.command("import")
def session_import(
    file: Annotated[Path | None, typer.Option(help="Read the Cookie header from a file.")] = None,
    proxy: ProxyOpt = None,
) -> None:
    """Save a Cookie header copied from browser DevTools (input is hidden)."""
    s = _settings(proxy)
    if file:
        raw = file.read_text()
    elif not sys.stdin.isatty():
        raw = sys.stdin.read()
    else:
        raw = getpass.getpass("Paste the Cookie header value: ")
    try:
        cookies = sess.parse_cookie_header(raw, s.site_host)
    except sess.SessionError as e:
        _fail(str(e))
    n = sess.save_cookies(s, cookies)
    typer.echo(f"Saved {n} cookie(s) to {s.cookies_file}")
    _report_check(s)


def _report_check(s: Settings) -> bool:
    try:
        r = sess.check(s)
    except sess.SessionError as e:
        _fail(str(e))
    except httpx.HTTPError as e:
        _proxy_error(s, e)
    color = "green" if r.valid else "red"
    typer.secho(
        f"Session {'valid' if r.valid else 'INVALID'}: {r.reason} ({r.final_url})", fg=color
    )
    return r.valid


@session_app.command("check")
def session_check(proxy: ProxyOpt = None) -> None:
    """Check whether the saved session is still logged in."""
    s = _settings(proxy)
    for line in sess.cookie_summary(s):
        typer.echo(f"  {line}")
    if not _report_check(s):
        raise typer.Exit(2)


@session_app.command("keepalive")
def session_keepalive(
    minutes: Annotated[
        float | None, typer.Option(help="Interval, default EDU_KEEPALIVE_MINUTES.")
    ] = None,
    proxy: ProxyOpt = None,
) -> None:
    """Ping the constructor periodically so the ~1 h idle timeout never hits."""
    s = _settings(proxy)
    interval = (minutes or s.keepalive_minutes) * 60
    while True:
        stamp = time.strftime("%H:%M:%S")
        try:
            r = sess.check(s)
        except sess.SessionError as e:
            _fail(str(e))
        except httpx.HTTPError as e:
            typer.secho(f"[{stamp}] network error, will retry: {e}", fg="yellow", err=True)
            time.sleep(min(interval, 60))
            continue
        if not r.valid:
            _fail(f"[{stamp}] session expired ({r.reason}). Run `edu session login`.", 2)
        typer.echo(f"[{stamp}] ok, next ping in {interval / 60:g} min")
        time.sleep(interval)


# ---------- proxy ----------


@proxy_app.command("up")
def proxy_up() -> None:
    """Run sslocal in the foreground, exposing Shadowsocks as a local SOCKS5 port."""
    s = get_settings()
    try:
        cmd = shadowsocks.build_command(s)
    except shadowsocks.ShadowsocksError as e:
        _fail(str(e))
    typer.echo(f"Starting {cmd[0]} on {s.ss_bind}:{s.ss_local_port} (Ctrl+C to stop)")
    raise typer.Exit(shadowsocks.run(s))


@proxy_app.command("direct")
def proxy_direct(
    interface: Annotated[
        str | None, typer.Option(help="Outgoing interface, default EDU_INTERFACE.")
    ] = None,
    port: Annotated[int | None, typer.Option(help="Listen port, default EDU_DIRECT_PORT.")] = None,
) -> None:
    """Run a local HTTP proxy that sends traffic out of one interface (bypasses VPN routes)."""
    from edu_by import direct_proxy

    s = get_settings()
    iface = interface or s.interface
    if not iface:
        _fail("Set EDU_INTERFACE (e.g. wlo1) or pass --interface.")
    listen = port or s.direct_port
    typer.echo(f"Direct proxy on http://127.0.0.1:{listen} -> out via {iface} (Ctrl+C to stop)")
    direct_proxy.run("127.0.0.1", listen, iface)


@proxy_app.command("check")
def proxy_check(proxy: ProxyOpt = None) -> None:
    """Check that the login and constructor pages are reachable through the proxy."""
    s = _settings(proxy)
    typer.echo(f"Proxy: {mask_proxy(s.effective_proxy)}")

    try:
        with make_client(s) as client:
            for url in (s.login_url, s.constructor_url):
                t = time.monotonic()
                resp = client.get(url)
                typer.echo(f"{url} -> HTTP {resp.status_code} in {time.monotonic() - t:.2f}s")
    except httpx.HTTPError as e:
        _proxy_error(s, e)


@proxy_app.command("pac")
def proxy_pac(
    out: Annotated[Path, typer.Option(help="Where to write the PAC file.")] = Path(
        ".session/edu-by.pac"
    ),
    proxy: ProxyOpt = None,
) -> None:
    """Write a PAC file routing *.edu.by via the proxy, for your own desktop browser.

    Containers use host networking, so the proxy address works from the host as is.
    """
    from edu_by.browser import pac_script

    s = _settings(proxy)
    if not s.effective_proxy:
        _fail("No proxy configured (EDU_PROXY or EDU_SS_URL / EDU_SS_CONFIG).")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(pac_script(s.effective_proxy))
    typer.echo(f"Wrote {out.resolve()}")
    typer.echo(f"Use it in your browser's proxy settings: file://<repo>/{out}")


# ---------- browse ----------


@app.command("browse")
def browse(
    url: Annotated[
        str | None,
        typer.Argument(
            help="Page to open. Default: the constructor if the saved session is valid, "
            "else the login page."
        ),
    ] = None,
    login: Annotated[
        bool,
        typer.Option(
            "--login",
            help="Open the login page (site, login, password filled from .env; you solve the "
            "captcha). The window stays open; the new session is saved.",
        ),
    ] = False,
    save_session: Annotated[
        bool, typer.Option(help="Save site cookies to the session while the browser runs.")
    ] = True,
    har: Annotated[
        str | None,
        typer.Option(
            help="Record edu.by traffic to .session/har/<NAME>.*.jsonl as it happens; "
            "<NAME>.sanitized.har is built when the browser closes."
        ),
    ] = None,
    proxy: ProxyOpt = None,
) -> None:
    """Open a desktop browser with edu.by routed through the proxy, logged in with the
    saved session (or on the prefilled login form)."""
    from edu_by.browser import (
        add_session_cookies,
        attach_login_prefill,
        check_browser_proxy,
        is_edu_by,
        open_browser,
        run_until_closed,
    )

    s = _settings(proxy)
    try:
        check_browser_proxy(s)
    except ValueError as e:
        _fail(str(e))
    use_session = not login and s.cookies_file.exists()
    if login:
        url = s.login_url
    elif not url:
        valid = False
        if use_session:
            try:
                valid = sess.check(s).valid
            except (sess.SessionError, httpx.HTTPError):
                valid = False
        url = s.constructor_url if valid else s.login_url
        typer.echo(
            "Saved session is valid – opening the constructor."
            if valid
            else "No valid session – opening the login page (fields from .env)."
        )
    if "://" not in url:
        url = "https://" + url
    if not is_edu_by(url):
        typer.secho(f"{url} is not under edu.by – it will open without the proxy.", fg="yellow")
    typer.echo(f"Proxy: {mask_proxy(s.effective_proxy)}. Close the browser window to finish.")
    recorder = None
    if har:
        from edu_by import har as har_mod

        recorder = har_mod.Recorder(s.session_dir / "har" / har, is_edu_by)
        typer.echo(f"Recording edu.by traffic to {recorder.clean_path} (+ raw, never share it)")
    constructor_path = urlsplit(s.constructor_url).path.lower()
    saved: list[int] = []
    with open_browser(s) as context:

        def on_cookies(cookies: list[dict]) -> None:
            # Only a logged-in browser (constructor page open) may replace the CLI session:
            # the login page's fresh cookies would otherwise overwrite a valid one.
            if any(urlsplit(p.url).path.lower() == constructor_path for p in context.pages):
                saved.append(sess.save_cookies(s, cookies))

        if recorder:
            recorder.attach(context)
        if use_session:
            add_session_cookies(context, s)
        attach_login_prefill(context, s)
        page = context.pages[0] if context.pages else context.new_page()
        page.goto(url)
        run_until_closed(context, on_cookies=on_cookies if save_session else None)
    if saved:
        typer.echo(f"Saved {saved[-1]} site cookie(s) to {s.cookies_file}")
    if recorder:
        out = recorder.finish()
        typer.echo(f"Recorded {recorder.count} request(s). Sanitized HAR: {out}")


# ---------- har ----------


@har_app.command("sanitize")
def har_sanitize(src: Path, dst: Annotated[Path | None, typer.Argument()] = None) -> None:
    """Strip cookies, passwords, captcha, tokens and ViewState from a HAR."""
    from edu_by import har as har_mod

    dst = dst or src.with_suffix(".sanitized.har")
    n = har_mod.sanitize(src, dst)
    typer.echo(f"{n} request(s) -> {dst}")


@har_app.command("summary")
def har_summary(
    path: Path,
    static: Annotated[bool, typer.Option(help="Include css/js/images/fonts.")] = False,
) -> None:
    """List distinct request shapes in a (sanitized) HAR."""
    from edu_by import har as har_mod

    if ".sanitized." not in path.name:
        _fail(
            "Summarize the sanitized capture (*.sanitized.har / *.sanitized.jsonl), not the raw one."
        )
    for line in har_mod.summarize(path, include_static=static):
        typer.echo(line)


# ---------- read-only site access ----------

JsonOpt = Annotated[bool, typer.Option("--json", help="Print JSON instead of a table.")]
YesOpt = Annotated[
    bool,
    typer.Option("--yes", help="Apply the change (edit and publish level). Without it: preview."),
]
TokenOpt = Annotated[
    str | None,
    typer.Option(
        "--token",
        help="Apply only if the plan still has this token (from the preview). "
        "Required for delete-level changes.",
    ),
]
SectionArg = Annotated[
    str,
    typer.Argument(
        help="Section ID (e.g. 1041) or ID path (1001/1041/1201, faster for deep sections: "
        "an unseen bare ID that is not in the path cache is searched by walking the tree)."
    ),
]


@contextlib.contextmanager
def _site(proxy: str | None):
    """An open `Site` after a session check; exits 2 if the session expired."""
    from edu_by.site import SessionExpired, Site

    s = _settings(proxy)
    progress = (
        (lambda n, what: typer.echo(f"[{n}] {what}", err=True))
        if sys.stderr.isatty() or s.verbose
        else None
    )
    try:
        with Site(s, on_request=progress) as site:
            yield site
    except SessionExpired:
        _fail("Session expired or missing. Run `./edu session login`, then retry.", 2)
    except httpx.HTTPError as e:
        _proxy_error(s, e)
    except typer.Exit:
        raise
    except RuntimeError as e:  # ExplorerError, ObjectError, WriteError, redirect to login
        _fail(str(e))


def _print_json(data) -> None:
    typer.echo(json.dumps(data, ensure_ascii=False, indent=2, default=str))


def _run(site, change, yes: bool, token: str | None, as_json: bool) -> None:
    """Preview a planned change; apply it with --yes (or --token, required for deletes)."""
    from edu_by.api.changes import TokenMismatch

    preview = change.preview()
    apply = (yes or token) and not change.noop
    if change.level == "delete" and apply and token is None:
        _fail(
            change.describe() + "\nDelete-level change: rerun with --token "
            f"{change.token} after checking the preview.",
            3,
        )
    if not apply:
        if as_json:
            _print_json(preview)
        else:
            typer.echo(change.describe())
            if not change.noop:
                how = f"--token {change.token}" if change.level == "delete" else "--yes"
                typer.echo(f"Preview only. Rerun with {how} to apply.")
        return
    if not as_json:
        typer.echo(change.describe())
    try:
        result = change.apply(token)
    except TokenMismatch as e:
        _fail(str(e), 3)
    if as_json:
        _print_json({"plan": preview, "result": result})
        return
    ok = result.get("verified", True)
    typer.secho(
        "Applied and verified." if ok else "Applied, but the check failed:",
        fg="green" if ok else "yellow",
    )
    _print_json({k: v for k, v in result.items() if k not in ("action", "applied")})
    if not ok:
        raise typer.Exit(4)


def _kv(pairs: list[str] | None) -> dict[str, str]:
    out = {}
    for p in pairs or []:
        k, sep, v = p.partition("=")
        if not sep:
            _fail(f"--set expects field=value, got {p!r}")
        if v.startswith("@"):
            v = Path(v[1:]).read_text(encoding="utf-8")
        out[k.strip()] = v
    return out


# ---------- read ----------


@app.command("tree")
def tree(
    root: Annotated[
        str | None, typer.Option(help="Start from this section (ID or ID path 1001/1041).")
    ] = None,
    depth: Annotated[
        int,
        typer.Option(
            help="Levels below the root(s) to list. Each listed level costs "
            "one request (~1 s) per section above it."
        ),
    ] = 1,
    all_levels: Annotated[
        bool, typer.Option("--all", help="Walk the whole tree (one request per section).")
    ] = False,
    as_json: JsonOpt = False,
    proxy: ProxyOpt = None,
) -> None:
    """List the site's sections (classifiers) as a tree."""
    with _site(proxy) as site:
        ex = site.explorer()
        root_id = ex.find_section(root).id if root else None
        found = list(ex.walk(root_id, None if all_levels else depth))
    if as_json:
        _print_json([sec.as_dict() for sec in found])
        return
    base = len(found[0].path) if found else 0
    for sec in found:
        typer.echo(f"{'  ' * (len(sec.path) - base)}{sec.id}  {sec.title}")


@app.command("objects")
def objects(
    section: SectionArg,
    pages: Annotated[
        int | None,
        typer.Option(help="Read only the first N list pages (big news archives), default all."),
    ] = None,
    as_json: JsonOpt = False,
    proxy: ProxyOpt = None,
) -> None:
    """List the objects (content items) of a section in their order, all pages by default."""
    from dataclasses import asdict

    with _site(proxy) as site:
        ex = site.explorer()
        rows = ex.objects(section) if pages is None else ex.objects(section, max_pages=pages - 1)
    if as_json:
        _print_json([asdict(r) for r in rows])
        return
    for r in rows:
        mark = " " if r.published else "-"
        typer.echo(f"{mark} {r.id:>8}  {r.type_label}: {r.title}")
    typer.echo(f"{len(rows)} object(s); '-' = not published")


@app.command("types")
def types(as_json: JsonOpt = False, proxy: ProxyOpt = None) -> None:
    """List object types (templates) from the constructor tree."""
    from dataclasses import asdict

    from edu_by.api.explorer import types_from_tree

    with _site(proxy) as site:
        found = types_from_tree(site.explorer().nodes())
    if as_json:
        _print_json([asdict(t) for t in found])
        return
    for t in found:
        typer.echo(f"{t.id:>5}  {t.group:<12} {t.name}")


# ---------- objects ----------


@object_app.command("show")
def object_show(
    object_id: Annotated[str, typer.Argument(help="Object ID, e.g. 1063.")],
    as_json: JsonOpt = False,
    proxy: ProxyOpt = None,
) -> None:
    """Show one object: type, title, status, section, HTML and its editable fields."""
    from dataclasses import asdict

    from edu_by.api import dialogs
    from edu_by.api.objects import EDITOR_PATH, parse_object_editor
    from edu_by.api.objects_write import editable_fields

    with _site(proxy) as site:
        page = dialogs.open_dialog(site.client, site.base_url, EDITOR_PATH, object_id)
        obj = parse_object_editor(object_id, page.html)
        editable = editable_fields(page.fields)
        values = {k: page.fields.get(f"ctl00$Main${k}", "").strip("\r\n") for k in editable}
    if as_json:
        _print_json({**asdict(obj), "editable_fields": editable, "fields": values})
        return
    for key in (
        "id",
        "type",
        "name",
        "published",
        "section_id",
        "section_path",
        "tags",
        "languages",
        "public_url",
    ):
        typer.echo(f"{key:>13}: {getattr(obj, key)}")
    typer.echo(f"{'editable':>13}: {', '.join(editable)}")
    for k, v in values.items():
        if k == "Tags" or not v.strip():
            continue
        if "\n" in v or len(v) > 80:
            typer.echo(f"-- {k} --")
            typer.echo(v)
        else:
            typer.echo(f"{k:>13}: {v}")


SetOpt = Annotated[
    list[str] | None,
    typer.Option(
        "--set",
        help="field=value (repeatable); value @file.html reads a file. Fields: see `object show`.",
    ),
]


@object_app.command("set")
def object_set(
    object_id: str,
    values: SetOpt = None,
    text_file: Annotated[
        Path | None, typer.Option("--text-file", help="New main HTML (`text`, news: `txt`).")
    ] = None,
    publish: Annotated[
        bool | None, typer.Option("--publish/--unpublish", help="Change «Разрешить публикацию».")
    ] = None,
    yes: YesOpt = False,
    token: TokenOpt = None,
    as_json: JsonOpt = False,
    proxy: ProxyOpt = None,
) -> None:
    """Change an object's fields and/or publication (other fields keep their values)."""
    from edu_by.api import objects_write as ow

    vals = _kv(values)
    with _site(proxy) as site:
        if text_file is not None:
            from edu_by.api import dialogs
            from edu_by.api.objects import EDITOR_PATH

            page = dialogs.open_dialog(site.client, site.base_url, EDITOR_PATH, object_id)
            key = "txt" if "ctl00$Main$txt" in page.fields else "text"
            vals[key] = text_file.read_text(encoding="utf-8")
        _run(site, ow.plan_update(site, object_id, vals, publish), yes, token, as_json)


@object_app.command("publish")
def object_publish(
    object_id: str,
    yes: YesOpt = False,
    token: TokenOpt = None,
    as_json: JsonOpt = False,
    proxy: ProxyOpt = None,
) -> None:
    """Publish an object (tick «Разрешить публикацию»)."""
    from edu_by.api import objects_write as ow

    with _site(proxy) as site:
        _run(site, ow.plan_update(site, object_id, published=True), yes, token, as_json)


@object_app.command("unpublish")
def object_unpublish(
    object_id: str,
    yes: YesOpt = False,
    token: TokenOpt = None,
    as_json: JsonOpt = False,
    proxy: ProxyOpt = None,
) -> None:
    """Take an object off the public site (untick «Разрешить публикацию»)."""
    from edu_by.api import objects_write as ow

    with _site(proxy) as site:
        _run(site, ow.plan_update(site, object_id, published=False), yes, token, as_json)


@object_app.command("add")
def object_add(
    section: SectionArg,
    type_id: Annotated[str, typer.Option("--type", help="Object type id (`edu types`), e.g. 524.")],
    count: Annotated[int, typer.Option(help="How many empty objects to create.")] = 1,
    values: SetOpt = None,
    yes: YesOpt = False,
    token: TokenOpt = None,
    as_json: JsonOpt = False,
    proxy: ProxyOpt = None,
) -> None:
    """Create unpublished objects of a type in a section, optionally filling their fields."""
    from edu_by.api import objects_write as ow

    with _site(proxy) as site:
        sec = site.explorer().find_section(section)
        _run(site, ow.plan_create(site, sec.id, type_id, count, _kv(values)), yes, token, as_json)


@object_app.command("copy")
def object_copy(
    object_id: str,
    yes: YesOpt = False,
    token: TokenOpt = None,
    as_json: JsonOpt = False,
    proxy: ProxyOpt = None,
) -> None:
    """«Создать копию»: an unpublished copy in the same section."""
    from edu_by.api import objects_write as ow

    with _site(proxy) as site:
        _run(site, ow.plan_copy(site, object_id), yes, token, as_json)


@object_app.command("move")
def object_move(
    object_ids: Annotated[list[str], typer.Argument(help="Object IDs (all from one section).")],
    to: Annotated[str, typer.Option("--to", help="Target section ID or ID path.")],
    yes: YesOpt = False,
    token: TokenOpt = None,
    as_json: JsonOpt = False,
    proxy: ProxyOpt = None,
) -> None:
    """Move objects to another section."""
    from edu_by.api import objects_write as ow

    with _site(proxy) as site:
        target = site.explorer().find_section(to)
        _run(site, ow.plan_move(site, object_ids, target.id), yes, token, as_json)


@object_app.command("sort")
def object_sort(
    section: SectionArg,
    order: Annotated[list[str], typer.Argument(help="All object IDs of the section, new order.")],
    yes: YesOpt = False,
    token: TokenOpt = None,
    as_json: JsonOpt = False,
    proxy: ProxyOpt = None,
) -> None:
    """Set the order of a section's objects."""
    from edu_by.api import objects_write as ow

    with _site(proxy) as site:
        sec = site.explorer().find_section(section)
        _run(site, ow.plan_sort(site, sec.id, order), yes, token, as_json)


@object_app.command("upload")
def object_upload(
    object_id: str,
    file: Annotated[Path, typer.Argument(help="Image file (≤ ~300 000 bytes, or use --shrink).")],
    shrink: Annotated[
        bool,
        typer.Option(
            "--shrink", help="Re-encode a bigger photo as JPEG under the limit first (≤1600 px)."
        ),
    ] = False,
    yes: YesOpt = False,
    token: TokenOpt = None,
    as_json: JsonOpt = False,
    proxy: ProxyOpt = None,
) -> None:
    """Upload an image into an image object (type 304) or a news item."""
    from edu_by.api import objects_write as ow

    if shrink:
        settings = _settings(proxy)
        try:
            small = ow.shrink_image(file, settings.session_dir / "upload")
        except ow.WriteError as e:
            _fail(str(e))
        if small != file:
            typer.echo(f"Shrunk {file.name}: {file.stat().st_size} B -> {small.stat().st_size} B")
        file = small
    with _site(proxy) as site:
        _run(site, ow.plan_upload_image(site, object_id, file), yes, token, as_json)


@object_app.command("trash")
def object_trash(
    object_ids: Annotated[list[str], typer.Argument(help="Object IDs (all from one section).")],
    token: TokenOpt = None,
    as_json: JsonOpt = False,
    proxy: ProxyOpt = None,
) -> None:
    """Move objects to the trash (restorable with `edu trash restore`)."""
    from edu_by.api import objects_write as ow

    with _site(proxy) as site:
        _run(site, ow.plan_trash(site, object_ids), False, token, as_json)


# ---------- sections ----------


@section_app.command("show")
def section_show(section: SectionArg, as_json: JsonOpt = False, proxy: ProxyOpt = None) -> None:
    """Section properties: title, internal name, protection, template, redirect, path."""
    from edu_by.api.sections import read_section

    with _site(proxy) as site:
        sec = site.explorer().find_section(section)
        props = {**read_section(site, sec.id), "path": "/".join(sec.path)}
    if as_json:
        _print_json(props)
        return
    for k, v in props.items():
        typer.echo(f"{k:>13}: {v}")


@section_app.command("add")
def section_add(
    parent: SectionArg,
    title: Annotated[str, typer.Option(help="Title of the new section (Russian).")],
    unprotected: Annotated[
        bool, typer.Option("--unprotected", help="Create without protection from deletion.")
    ] = False,
    yes: YesOpt = False,
    token: TokenOpt = None,
    as_json: JsonOpt = False,
    proxy: ProxyOpt = None,
) -> None:
    """Add a child section at the end of PARENT."""
    from edu_by.api import sections

    with _site(proxy) as site:
        _run(site, sections.plan_add(site, parent, title, not unprotected), yes, token, as_json)


@section_app.command("set")
def section_set(
    section: SectionArg,
    title: Annotated[str | None, typer.Option(help="New title (Russian).")] = None,
    name: Annotated[str | None, typer.Option(help="New internal name.")] = None,
    tags: Annotated[str | None, typer.Option(help="New tags.")] = None,
    protect: Annotated[
        bool | None, typer.Option("--protect/--unprotect", help="Protection from deletion.")
    ] = None,
    yes: YesOpt = False,
    token: TokenOpt = None,
    as_json: JsonOpt = False,
    proxy: ProxyOpt = None,
) -> None:
    """Change a section's title, internal name, tags or delete protection."""
    from edu_by.api import sections

    with _site(proxy) as site:
        sec = site.explorer().find_section(section)
        change = sections.plan_update(site, sec.id, title, name, protect, tags)
        _run(site, change, yes, token, as_json)


@section_app.command("move")
def section_move(
    section: SectionArg,
    target: Annotated[str, typer.Option("--to", help="Target section ID or ID path.")],
    position: Annotated[
        str, typer.Option(help="inside (as last child), above or below the target.")
    ] = "inside",
    yes: YesOpt = False,
    token: TokenOpt = None,
    as_json: JsonOpt = False,
    proxy: ProxyOpt = None,
) -> None:
    """Move a section inside, above or below another section (also sorts sections)."""
    from edu_by.api import sections

    with _site(proxy) as site:
        _run(site, sections.plan_move(site, section, target, position), yes, token, as_json)  # type: ignore[arg-type]


@section_app.command("delete")
def section_delete(
    section: SectionArg, token: TokenOpt = None, as_json: JsonOpt = False, proxy: ProxyOpt = None
) -> None:
    """Delete a section without subsections; its objects go to the trash."""
    from edu_by.api import sections

    with _site(proxy) as site:
        _run(site, sections.plan_delete(site, section), False, token, as_json)


# ---------- trash ----------


@trash_app.command("list")
def trash_list(
    type_id: Annotated[str, typer.Argument(help="Object type id, e.g. 304 (images).")],
    page: Annotated[int, typer.Option(help="Page index, 0 = newest.")] = 0,
    as_json: JsonOpt = False,
    proxy: ProxyOpt = None,
) -> None:
    """One page of a type's trash (other users' deleted objects are there too)."""
    from edu_by.api.trash import list_trash

    with _site(proxy) as site:
        data = list_trash(site, type_id, page)
    if as_json:
        _print_json(data)
        return
    for r in data["objects"]:
        typer.echo(f"  {r['id']:>8}  {r['type_label']}: {r['title']}")
    typer.echo(f"page {data['page']} of 0..{data['last_page']}")


@trash_app.command("restore")
def trash_restore(
    type_id: Annotated[str, typer.Argument(help="Object type id, e.g. 304.")],
    object_ids: Annotated[list[str], typer.Argument(help="Object IDs to restore.")],
    to: Annotated[str, typer.Option("--to", help="Target section ID or ID path.")],
    yes: YesOpt = False,
    token: TokenOpt = None,
    as_json: JsonOpt = False,
    proxy: ProxyOpt = None,
) -> None:
    """Restore named objects from a type's trash into a section."""
    from edu_by.api.trash import plan_restore

    with _site(proxy) as site:
        _run(site, plan_restore(site, type_id, object_ids, to), yes, token, as_json)


@trash_app.command("purge")
def trash_purge(
    type_id: Annotated[str, typer.Argument(help="Object type id, e.g. 304.")],
    object_ids: Annotated[list[str], typer.Argument(help="Object IDs to delete for good.")],
    token: TokenOpt = None,
    as_json: JsonOpt = False,
    proxy: ProxyOpt = None,
) -> None:
    """Delete named objects from a type's trash for good (irreversible)."""
    from edu_by.api.trash import plan_purge

    with _site(proxy) as site:
        _run(site, plan_purge(site, type_id, object_ids), False, token, as_json)


if __name__ == "__main__":
    app()
