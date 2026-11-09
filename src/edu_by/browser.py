"""Desktop Chromium (Playwright) that routes *.edu.by through the configured proxy.

Routing uses a PAC script: hosts under edu.by go through the proxy, everything else
(browser updates, third-party assets, ...) is direct. Proxies with credentials can't be
expressed in PAC, so they're refused rather than proxying all traffic.
"""

from __future__ import annotations

import base64
import time
from collections.abc import Iterator
from contextlib import contextmanager
from urllib.parse import urlsplit

from playwright.sync_api import BrowserContext, sync_playwright

from edu_by.config import Settings
from edu_by.http import PROXIED_DOMAIN


def pac_script(proxy_url: str | None, domain: str = PROXIED_DOMAIN) -> str:
    """PAC that sends `domain` and its subdomains to the proxy, the rest direct."""
    if not proxy_url:
        target = "DIRECT"
    else:
        parts = urlsplit(proxy_url)
        hostport = f"{parts.hostname}:{parts.port}"
        scheme = parts.scheme.lower()
        if scheme.startswith("socks"):
            target = f"SOCKS5 {hostport}; SOCKS {hostport}"
        elif scheme == "https":
            target = f"HTTPS {hostport}"
        else:
            target = f"PROXY {hostport}"
    return (
        "function FindProxyForURL(url, host) {\n"
        f'  if (host === "{domain}" || dnsDomainIs(host, ".{domain}")) {{\n'
        f'    return "{target}";\n'
        "  }\n"
        '  return "DIRECT";\n'
        "}\n"
    )


def is_edu_by(url: str) -> bool:
    host = (urlsplit(url).hostname or "").lower()
    return host == PROXIED_DOMAIN or host.endswith("." + PROXIED_DOMAIN)


def check_browser_proxy(settings: Settings) -> None:
    """Raise ValueError if the browser can't route only edu.by through this proxy."""
    proxy_url = settings.effective_proxy
    if proxy_url and urlsplit(proxy_url).username:
        raise ValueError(
            "The browser can't use a proxy with credentials while proxying only edu.by. "
            "Use direct mode, Shadowsocks or a proxy without auth."
        )


@contextmanager
def open_browser(settings: Settings) -> Iterator[BrowserContext]:
    check_browser_proxy(settings)
    proxy_url = settings.effective_proxy
    args: list[str] = []
    if proxy_url:
        pac = base64.b64encode(pac_script(proxy_url).encode()).decode()
        args.append(f"--proxy-pac-url=data:application/x-ns-proxy-autoconfig;base64,{pac}")

    profile = settings.session_dir / "browser-profile"
    profile.mkdir(parents=True, exist_ok=True)
    settings.session_dir.chmod(0o700)

    with sync_playwright() as pw:
        context = pw.chromium.launch_persistent_context(
            str(profile),
            headless=False,
            args=args,
            no_viewport=True,
            locale="ru-RU",
        )
        try:
            yield context
        finally:
            context.close()


def run_until_closed(context: BrowserContext, poll_seconds: float = 2) -> list[dict]:
    """Block until the user closes the browser; return the last cookie snapshot.

    Cookies can't be read once the browser is gone, so they're snapshotted while it runs.
    """
    closed: list[bool] = []
    context.on("close", lambda _: closed.append(True))
    snapshot: list[dict] = []
    while not closed:
        try:
            snapshot = context.cookies()
        except Exception:
            break
        time.sleep(poll_seconds)
    return snapshot
