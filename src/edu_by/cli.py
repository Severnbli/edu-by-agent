"""`edu` command-line entry point."""

from __future__ import annotations

import getpass
import sys
import time
from pathlib import Path
from typing import Annotated

import httpx
import typer

from edu_by import session as sess
from edu_by import shadowsocks
from edu_by.config import Settings, get_settings, mask_proxy

app = typer.Typer(help="Operate the edu.by site constructor.", no_args_is_help=True)
session_app = typer.Typer(
    help="Obtain, check and keep alive the constructor session.", no_args_is_help=True
)
proxy_app = typer.Typer(help="Proxy and Shadowsocks utilities.", no_args_is_help=True)
app.add_typer(session_app, name="session")
app.add_typer(proxy_app, name="proxy")

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
    hint = " Is the ss container running (`./edu proxy up`)?" if s.shadowsocks_configured and not s.proxy else ""
    _fail(f"Connection failed via {mask_proxy(s.effective_proxy)}: {e}.{hint}")


# ---------- session ----------


@session_app.command("login")
def session_login(proxy: ProxyOpt = None) -> None:
    """Open the login page in a desktop browser, log in by hand, save the session."""
    s = _settings(proxy)
    typer.echo(f"Proxy: {mask_proxy(s.effective_proxy)}  Login: {s.login_url}")
    n = sess.login_via_browser(s)
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


@proxy_app.command("check")
def proxy_check(proxy: ProxyOpt = None) -> None:
    """Show the exit IP and whether the login and constructor pages are reachable."""
    s = _settings(proxy)
    typer.echo(f"Proxy: {mask_proxy(s.effective_proxy)}")
    from edu_by.http import make_client

    try:
        with make_client(s) as client:
            ip = client.get(s.ip_check_url).json().get("ip", "?")
            typer.echo(f"Exit IP: {ip}")
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

    With Shadowsocks it points at 127.0.0.1:<EDU_SS_LOCAL_PORT>, the port the ss
    container publishes on the host.
    """
    from edu_by.browser import pac_script

    s = _settings(proxy)
    if not s.proxy and s.shadowsocks_configured:
        s = s.model_copy(update={"ss_host": "127.0.0.1"})
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
    all_traffic: Annotated[
        bool, typer.Option("--all", help="Proxy all sites, not just *.edu.by.")
    ] = False,
    save_session: Annotated[
        bool, typer.Option(help="Save site cookies to the session when the browser closes.")
    ] = True,
    proxy: ProxyOpt = None,
) -> None:
    """Open any *.edu.by site in a desktop browser through the configured proxy."""
    from edu_by.browser import is_edu_by, open_browser, run_until_closed

    s = _settings(proxy)
    url = url or s.login_url
    if "://" not in url:
        url = "https://" + url
    if not is_edu_by(url) and not all_traffic:
        typer.secho(
            f"{url} is not under edu.by – it will NOT go through the proxy "
            "(use --all to proxy everything).",
            fg="yellow",
        )
    typer.echo(f"Proxy: {mask_proxy(s.effective_proxy)}. Close the browser window to finish.")
    with open_browser(s, proxy_all=all_traffic) as context:
        page = context.pages[0] if context.pages else context.new_page()
        page.goto(url)
        cookies = run_until_closed(context)
    if save_session and cookies:
        n = sess.save_cookies(s, cookies)
        typer.echo(f"Saved {n} site cookie(s) to {s.cookies_file}")


if __name__ == "__main__":
    app()
