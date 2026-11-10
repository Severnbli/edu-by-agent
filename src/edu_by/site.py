"""One logged-in constructor site: settings, the HTTP client, the explorer page, the path cache.

Shared by the CLI (one `Site` per command) and the MCP server (one `Site` kept open between
tool calls). All reads and planned writes in `edu_by.api` take a `Site`, so neither front
end holds request logic of its own.
"""

from __future__ import annotations

import threading
from collections.abc import Callable

import httpx

from edu_by import session as sess
from edu_by.config import Settings
from edu_by.http import make_client


class SessionExpired(RuntimeError):
    """No valid session: a human has to run `./edu session login` (captcha)."""


class Site:
    def __init__(
        self,
        settings: Settings,
        on_request: Callable[[int, str], None] | None = None,
        check: bool = True,
    ) -> None:
        self.settings = settings
        self.on_request = on_request
        self.lock = threading.RLock()  # the server keeps one UI state per session: serialize
        if check:
            self.check_session()
        self.client: httpx.Client = make_client(settings, cookies=sess.load_cookies(settings))
        self._explorer = None

    # ---------- session ----------

    def check_session(self) -> None:
        try:
            ok = sess.check(self.settings).valid
        except sess.SessionError as e:
            raise SessionExpired(str(e)) from e
        if not ok:
            raise SessionExpired("Session expired or missing. Run `./edu session login`.")

    @property
    def base_url(self) -> str:
        return self.settings.base_url

    @property
    def delay(self) -> float:
        return self.settings.request_delay

    # ---------- explorer ----------

    def explorer(self):
        """The explorer page, opened on first use; knows section paths from the cache."""
        from edu_by.api import treecache
        from edu_by.api.explorer import Explorer

        if self._explorer is None:
            ex = Explorer.open(self.client, self.settings.constructor_url, delay=self.delay)
            ex.cached = treecache.load(self.settings)
            ex.on_request = self.on_request
            self._explorer = ex
        return self._explorer

    def reset_explorer(self) -> None:
        """Forget the explorer page (after an error); the next use reloads it."""
        self.save_cache()
        self._explorer = None

    def save_cache(self) -> None:
        from edu_by.api import treecache

        if self._explorer is not None:
            treecache.save(self.settings, self._explorer)

    # ---------- lifetime ----------

    def close(self) -> None:
        try:
            self.save_cache()
        finally:
            self.client.close()

    def __enter__(self) -> Site:
        return self

    def __exit__(self, *exc) -> None:
        self.close()
