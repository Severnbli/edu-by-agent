"""Session cookies: obtain (browser login or import), store, validate, keep alive.

How validity is detected is a heuristic until confirmed by captures (see knowledge/auth.md):
the constructor page must load with 200, without a redirect to a login/ReturnUrl page and
without a password field in the body.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from urllib.parse import urlsplit

import httpx

from edu_by.config import Settings
from edu_by.http import make_client


class SessionError(RuntimeError):
    pass


def _is_site_cookie(domain: str, host: str) -> bool:
    domain = domain.lstrip(".").lower()
    host = host.lower()
    return host == domain or host.endswith("." + domain) or domain.endswith(".edu.by")


def save_cookies(settings: Settings, cookies: list[dict]) -> int:
    """Persist cookies (Playwright-style dicts) for the site. Returns how many were kept."""
    kept = [
        {k: c.get(k) for k in ("name", "value", "domain", "path", "expires", "secure", "httpOnly")}
        for c in cookies
        if _is_site_cookie(c.get("domain", ""), settings.site_host)
    ]
    settings.session_dir.mkdir(parents=True, exist_ok=True)
    settings.session_dir.chmod(0o700)
    path = settings.cookies_file
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(kept, f, indent=2)
    return len(kept)


def parse_cookie_header(header: str, host: str) -> list[dict]:
    """Turn 'a=1; b=2' (as copied from DevTools) into cookie dicts for `host`."""
    header = header.strip()
    if header.lower().startswith("cookie:"):
        header = header[len("cookie:") :]
    cookies = []
    for part in header.split(";"):
        name, sep, value = part.strip().partition("=")
        if sep and name:
            cookies.append(
                {"name": name.strip(), "value": value.strip(), "domain": host, "path": "/"}
            )
    if not cookies:
        raise SessionError("No cookies found – expected the form 'name=value; name2=value2'.")
    return cookies


def load_cookies(settings: Settings) -> httpx.Cookies:
    path = settings.cookies_file
    if not path.exists():
        raise SessionError("No saved session. Run `edu session login` (or `edu session import`).")
    jar = httpx.Cookies()
    for c in json.loads(path.read_text()):
        jar.set(
            c["name"],
            c["value"],
            domain=c.get("domain") or settings.site_host,
            path=c.get("path") or "/",
        )
    return jar


def cookie_summary(settings: Settings) -> list[str]:
    """Cookie names with masked values, safe to print."""
    from edu_by.config import mask

    if not settings.cookies_file.exists():
        return []
    return [
        f"{c['name']}={mask(c['value'])}" for c in json.loads(settings.cookies_file.read_text())
    ]


@dataclass
class CheckResult:
    valid: bool
    status: int
    final_url: str
    reason: str


def check(settings: Settings, cookies: httpx.Cookies | None = None) -> CheckResult:
    """Request the constructor page and decide whether we're logged in."""
    cookies = cookies if cookies is not None else load_cookies(settings)
    with make_client(settings, cookies=cookies) as client:
        resp = client.get(settings.constructor_url)
    final = str(resp.url)
    target_path = urlsplit(settings.constructor_url).path.lower()
    body = resp.text.lower()

    if resp.status_code != 200:
        return CheckResult(False, resp.status_code, final, f"HTTP {resp.status_code}")
    if "returnurl=" in final.lower() or urlsplit(final).path.lower() != target_path:
        return CheckResult(False, resp.status_code, final, "redirected away from the constructor")
    if 'type="password"' in body or "type='password'" in body:
        return CheckResult(False, resp.status_code, final, "login form shown")
    return CheckResult(True, resp.status_code, final, "constructor page loaded")


def login_via_browser(settings: Settings) -> int:
    """Open the login page in a desktop browser; the user logs in, then presses Enter."""
    from edu_by.browser import open_browser

    with open_browser(settings) as context:
        page = context.pages[0] if context.pages else context.new_page()
        page.goto(settings.login_url)
        input("Log in in the browser window (solve the captcha), then press Enter here... ")
        if urlsplit(page.url).path.lower() != urlsplit(settings.constructor_url).path.lower():
            page.goto(settings.constructor_url)
        return save_cookies(settings, context.cookies())
