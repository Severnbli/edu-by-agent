"""Run a local sslocal (shadowsocks-rust) that exposes a SOCKS5 port."""

from __future__ import annotations

import json
import shutil
import subprocess

from edu_by.config import Settings


class ShadowsocksError(RuntimeError):
    pass


def build_command(settings: Settings) -> list[str]:
    binary = shutil.which(settings.ss_bin)
    if not binary:
        raise ShadowsocksError(
            f"'{settings.ss_bin}' not found. Install shadowsocks-rust "
            "(https://github.com/shadowsocks/shadowsocks-rust/releases, or `cargo install "
            "shadowsocks-rust`) or set EDU_SS_BIN."
        )
    bind = ["-b", f"127.0.0.1:{settings.ss_local_port}"]
    if settings.ss_url:
        if not settings.ss_url.startswith("ss://"):
            raise ShadowsocksError("EDU_SS_URL must start with ss://")
        return [binary, *bind, "--server-url", settings.ss_url]
    if settings.ss_config:
        path = settings.ss_config.expanduser()
        if not path.exists():
            raise ShadowsocksError(f"EDU_SS_CONFIG file not found: {path}")
        try:
            data = json.loads(path.read_text())
        except json.JSONDecodeError as e:
            raise ShadowsocksError(f"EDU_SS_CONFIG is not valid JSON: {e}") from e
        # If the config defines its own local listener, don't add a second one.
        has_local = "local_port" in data or "locals" in data
        return [binary, "-c", str(path), *([] if has_local else bind)]
    raise ShadowsocksError("Shadowsocks is not configured: set EDU_SS_URL or EDU_SS_CONFIG.")


def run(settings: Settings) -> int:
    """Run sslocal in the foreground until interrupted."""
    cmd = build_command(settings)
    try:
        return subprocess.call(cmd)
    except KeyboardInterrupt:
        return 0
