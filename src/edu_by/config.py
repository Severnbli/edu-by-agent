"""Settings loaded from environment variables (prefix EDU_) and .env."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="EDU_", env_file=".env", extra="ignore")

    login_url: str = "https://wp.brest-region.edu.by/"
    constructor_url: str = "https://wp.brest-region.edu.by/explorer.aspx"

    # Login form prefill: the user then only solves the captcha.
    site: str | None = None  # e.g. sch12.baranovichi.edu.by
    username: str | None = None
    password: SecretStr | None = None
    # ListSecurity: how much the 30-day WJG cookie remembers. Hight = nothing from the form
    # (Medium + site, Low + username, Zero probably + password). Keep Hight.
    security: str = "Hight"

    proxy: str | None = None
    # Direct mode: reach the site over this interface (e.g. wlo1), bypassing a VPN route.
    interface: str | None = None
    direct_port: int = 1081
    ss_url: str | None = None
    ss_config: Path | None = None
    ss_local_port: int = 1080
    ss_bind: str = "127.0.0.1"  # where sslocal listens
    ss_host: str = "127.0.0.1"  # where clients reach sslocal
    ss_bin: str = "sslocal"

    session_dir: Path = Path(".session")
    keepalive_minutes: float = 45
    timeout: float = 30
    # Pause between consecutive requests of one command (be gentle with the server).
    request_delay: float = 0.5
    verbose: bool = False  # print each request of a command to stderr

    @property
    def base_url(self) -> str:
        """Constructor root, e.g. https://wp.brest-region.edu.by (no trailing slash)."""
        return self.constructor_url.rsplit("/", 1)[0]

    @property
    def shadowsocks_configured(self) -> bool:
        return bool(self.ss_url or self.ss_config)

    @property
    def effective_proxy(self) -> str | None:
        """EDU_PROXY wins, then direct mode (EDU_INTERFACE), then Shadowsocks."""
        if self.proxy:
            return self.proxy
        if self.interface:
            return f"http://127.0.0.1:{self.direct_port}"
        if self.shadowsocks_configured:
            return f"socks5h://{self.ss_host}:{self.ss_local_port}"
        return None

    @property
    def site_host(self) -> str:
        return urlsplit(self.constructor_url).hostname or ""

    @property
    def cookies_file(self) -> Path:
        return self.session_dir / "cookies.json"


@lru_cache
def get_settings() -> Settings:
    return Settings()


def mask(value: str, keep: int = 4) -> str:
    """Hide a secret, keeping only the last `keep` characters."""
    if len(value) <= keep:
        return "*" * len(value)
    return "*" * (len(value) - keep) + value[-keep:]


def mask_proxy(url: str | None) -> str:
    """Show a proxy URL with any credentials hidden."""
    if not url:
        return "direct (no proxy)"
    parts = urlsplit(url)
    if parts.username or parts.password:
        host = parts.hostname or ""
        port = f":{parts.port}" if parts.port else ""
        return f"{parts.scheme}://***@{host}{port}"
    return url
