"""Settings loaded from environment variables (prefix EDU_) and .env."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="EDU_", env_file=".env", extra="ignore")

    login_url: str = "https://wp.brest-region.edu.by/"
    constructor_url: str = "https://wp.brest-region.edu.by/explorer.aspx"

    proxy: str | None = None
    ss_url: str | None = None
    ss_config: Path | None = None
    ss_local_port: int = 1080
    ss_bin: str = "sslocal"

    session_dir: Path = Path(".session")
    keepalive_minutes: float = 45
    ip_check_url: str = "https://api.ipify.org?format=json"
    timeout: float = 30

    @property
    def shadowsocks_configured(self) -> bool:
        return bool(self.ss_url or self.ss_config)

    @property
    def effective_proxy(self) -> str | None:
        """Explicit EDU_PROXY wins; otherwise the local Shadowsocks SOCKS port, if configured."""
        if self.proxy:
            return self.proxy
        if self.shadowsocks_configured:
            return f"socks5h://127.0.0.1:{self.ss_local_port}"
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
