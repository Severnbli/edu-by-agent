"""`edu` command-line entry point."""

from __future__ import annotations

import contextlib
import getpass
import json
import sys
import time
from pathlib import Path
from typing import Annotated

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
    from edu_by.http import make_client

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
    url: Annotated[str | None, typer.Argument(help="Page to open, default EDU_LOGIN_URL.")] = None,
    save_session: Annotated[
        bool, typer.Option(help="Save site cookies to the session when the browser closes.")
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
    """Open any *.edu.by site in a desktop browser through the configured proxy."""
    from edu_by.browser import (
        attach_login_prefill,
        check_browser_proxy,
        is_edu_by,
        open_browser,
        run_until_closed,
    )

    s = _settings(proxy)
    url = url or s.login_url
    if "://" not in url:
        url = "https://" + url
    if not is_edu_by(url):
        typer.secho(f"{url} is not under edu.by – it will open without the proxy.", fg="yellow")
    typer.echo(f"Proxy: {mask_proxy(s.effective_proxy)}. Close the browser window to finish.")
    try:
        check_browser_proxy(s)
    except ValueError as e:
        _fail(str(e))
    recorder = None
    if har:
        from edu_by import har as har_mod

        recorder = har_mod.Recorder(s.session_dir / "har" / har, is_edu_by)
        typer.echo(f"Recording edu.by traffic to {recorder.clean_path} (+ raw, never share it)")
    on_cookies = (lambda c: sess.save_cookies(s, c)) if save_session else None
    with open_browser(s) as context:
        if recorder:
            recorder.attach(context)
        attach_login_prefill(context, s)
        page = context.pages[0] if context.pages else context.new_page()
        page.goto(url)
        cookies = run_until_closed(context, on_cookies=on_cookies)
    if save_session and cookies:
        n = sess.save_cookies(s, cookies)
        typer.echo(f"Saved {n} site cookie(s) to {s.cookies_file}")
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


@contextlib.contextmanager
def _site(proxy: str | None):
    """An authenticated client after a session check; exits 2 if the session expired."""
    s = _settings(proxy)
    if not _session_ok(s):
        _fail("Session expired or missing. Run `./edu session login`, then retry.", 2)
    try:
        with make_client(s, cookies=sess.load_cookies(s)) as client:
            yield s, client
    except httpx.HTTPError as e:
        _proxy_error(s, e)
    except typer.Exit:
        raise
    except RuntimeError as e:  # ExplorerError, ObjectError, redirect to login
        _fail(str(e))


def _session_ok(s: Settings) -> bool:
    try:
        return sess.check(s).valid
    except sess.SessionError:
        return False
    except httpx.HTTPError as e:
        _proxy_error(s, e)
        return False


def _explorer(s: Settings, client: httpx.Client):
    from edu_by.api.explorer import Explorer

    ex = Explorer.open(client, s.constructor_url, delay=s.request_delay)
    if sys.stderr.isatty() or s.verbose:
        ex.on_request = lambda n, what: typer.echo(f"[{n}] {what}", err=True)
    return ex


def _print_json(data) -> None:
    typer.echo(json.dumps(data, ensure_ascii=False, indent=2))


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
    with _site(proxy) as (s, client):
        ex = _explorer(s, client)
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
    section: Annotated[
        str,
        typer.Argument(
            help="Section ID (e.g. 1041) or ID path (1001/1041/1201, faster for "
            "deep sections: an unseen bare ID is searched by walking the tree)."
        ),
    ],
    as_json: JsonOpt = False,
    proxy: ProxyOpt = None,
) -> None:
    """List the objects (content items) of a section, all pages."""
    from dataclasses import asdict

    with _site(proxy) as (s, client):
        rows = _explorer(s, client).objects(section)
    if as_json:
        _print_json([asdict(r) for r in rows])
        return
    for r in rows:
        mark = " " if r.published else "-"
        typer.echo(f"{mark} {r.id:>8}  {r.type_label}: {r.title}")
    typer.echo(f"{len(rows)} object(s); '-' = not published")


@app.command("object")
def object_(
    object_id: Annotated[str, typer.Argument(help="Object ID, e.g. 1063.")],
    as_json: JsonOpt = False,
    proxy: ProxyOpt = None,
) -> None:
    """Show one object: type, title, status, section and its HTML content."""
    from dataclasses import asdict

    from edu_by.api.objects import read_object

    with _site(proxy) as (s, client):
        obj = read_object(client, s.base_url, object_id)
    if as_json:
        _print_json(asdict(obj))
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
    typer.echo("-- text --")
    typer.echo(obj.text)
    if obj.dop.strip():
        typer.echo("-- dop --")
        typer.echo(obj.dop)


@app.command("types")
def types(as_json: JsonOpt = False, proxy: ProxyOpt = None) -> None:
    """List object types (templates) from the constructor tree."""
    from dataclasses import asdict

    from edu_by.api.explorer import types_from_tree

    with _site(proxy) as (s, client):
        found = types_from_tree(_explorer(s, client).nodes())
    if as_json:
        _print_json([asdict(t) for t in found])
        return
    for t in found:
        typer.echo(f"{t.id:>5}  {t.group:<12} {t.name}")


if __name__ == "__main__":
    app()
