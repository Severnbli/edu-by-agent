"""Shared httpx client: proxy, saved session cookies, browser-like headers.

Only edu.by and its subdomains go through the proxy; every other host is direct.
Host proxy env vars (HTTP(S)_PROXY, ALL_PROXY) are ignored.
"""

from __future__ import annotations

import httpx

from edu_by.config import Settings

PROXIED_DOMAIN = "edu.by"

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/130.0.0.0 Safari/537.36"
)


def make_client(
    settings: Settings,
    cookies: httpx.Cookies | None = None,
    follow_redirects: bool = True,
) -> httpx.Client:
    proxy = settings.effective_proxy
    mounts = (
        {
            f"all://{PROXIED_DOMAIN}": httpx.HTTPTransport(proxy=proxy),
            f"all://*.{PROXIED_DOMAIN}": httpx.HTTPTransport(proxy=proxy),
        }
        if proxy
        else None
    )
    return httpx.Client(
        mounts=mounts,
        trust_env=False,
        cookies=cookies,
        follow_redirects=follow_redirects,
        timeout=settings.timeout,
        headers={
            "User-Agent": USER_AGENT,
            "Accept-Language": "ru-RU,ru;q=0.9,be;q=0.8,en;q=0.7",
        },
    )
