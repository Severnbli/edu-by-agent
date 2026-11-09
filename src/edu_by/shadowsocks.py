"""Run a local sslocal (shadowsocks-rust) that exposes a SOCKS5 port."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

from edu_by.config import Settings


class ShadowsocksError(RuntimeError):
    pass


LOCAL_KEYS = ("local_address", "local_port", "locals", "protocol")


def server_only_config(settings: Settings) -> Path:
    """Copy EDU_SS_CONFIG without its local listener, so ours (-b) is the only one.

    The copy holds the server password, so it lives in the session dir with mode 600.
    """
    path = settings.ss_config.expanduser()
    if not path.exists():
        raise ShadowsocksError(f"EDU_SS_CONFIG file not found: {path}")
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        raise ShadowsocksError(f"EDU_SS_CONFIG is not valid JSON: {e}") from e
    for key in LOCAL_KEYS:
        data.pop(key, None)
    settings.session_dir.mkdir(parents=True, exist_ok=True)
    out = settings.session_dir / "sslocal.json"
    fd = os.open(out, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(data, f)
    return out


def build_command(settings: Settings) -> list[str]:
    binary = shutil.which(settings.ss_bin)
    if not binary:
        raise ShadowsocksError(
            f"'{settings.ss_bin}' not found. Install shadowsocks-rust "
            "or use the Docker setup (`./edu proxy up`), which ships it."
        )
    bind = ["-b", f"{settings.ss_bind}:{settings.ss_local_port}"]
    if settings.ss_url:
        if not settings.ss_url.startswith("ss://"):
            raise ShadowsocksError("EDU_SS_URL must start with ss://")
        return [binary, *bind, "--server-url", settings.ss_url]
    if settings.ss_config:
        return [binary, "-c", str(server_only_config(settings)), *bind]
    raise ShadowsocksError("Shadowsocks is not configured: set EDU_SS_URL or EDU_SS_CONFIG.")


def run(settings: Settings) -> int:
    """Run sslocal in the foreground until interrupted."""
    cmd = build_command(settings)
    try:
        return subprocess.call(cmd)
    except KeyboardInterrupt:
        return 0
