import json
from pathlib import Path

import httpx
import pytest

from edu_by import session as sess
from edu_by import shadowsocks
from edu_by.browser import is_edu_by, pac_script
from edu_by.config import Settings, mask, mask_proxy


@pytest.fixture(autouse=True)
def _no_edu_env(monkeypatch):
    """Tests must not see EDU_* from the container or the developer's shell."""
    import os

    for key in [k for k in os.environ if k.startswith("EDU_")]:
        monkeypatch.delenv(key)


def make(tmp_path: Path, **kw) -> Settings:
    return Settings(_env_file=None, session_dir=tmp_path / ".session", **kw)


def test_effective_proxy_prefers_explicit(tmp_path):
    s = make(tmp_path, proxy="http://p:3128", ss_url="ss://x")
    assert s.effective_proxy == "http://p:3128"


def test_effective_proxy_from_shadowsocks(tmp_path):
    s = make(tmp_path, ss_url="ss://x", ss_local_port=1090)
    assert s.effective_proxy == "socks5h://127.0.0.1:1090"


def test_default_urls_and_host(tmp_path):
    s = make(tmp_path)
    assert s.login_url == "https://wp.brest-region.edu.by/"
    assert s.site_host == "wp.brest-region.edu.by"


def test_masking():
    assert mask("abcdefgh") == "****efgh"
    assert mask_proxy("socks5h://u:secret@h:1080") == "socks5h://***@h:1080"
    assert "secret" not in mask_proxy("socks5h://u:secret@h:1080")


def test_pac_routes_only_edu_by():
    pac = pac_script("socks5h://127.0.0.1:1080")
    assert "SOCKS5 127.0.0.1:1080" in pac
    assert 'dnsDomainIs(host, ".edu.by")' in pac
    assert 'return "DIRECT"' in pac


@pytest.mark.parametrize(
    ("url", "ok"),
    [
        ("https://wp.brest-region.edu.by/", True),
        ("https://edu.by", True),
        ("https://notedu.by", False),
        ("https://edu.by.evil.com", False),
    ],
)
def test_is_edu_by(url, ok):
    assert is_edu_by(url) is ok


def test_cookie_import_roundtrip(tmp_path):
    s = make(tmp_path)
    cookies = sess.parse_cookie_header(
        "Cookie: ASP.NET_SessionId=abc123; .ASPXAUTH=zz", s.site_host
    )
    assert sess.save_cookies(s, cookies) == 2
    assert oct(s.cookies_file.stat().st_mode & 0o777) == "0o600"
    jar = sess.load_cookies(s)
    assert jar.get("ASP.NET_SessionId") == "abc123"
    assert all("abc123" not in line for line in sess.cookie_summary(s))


def test_save_filters_foreign_cookies(tmp_path):
    s = make(tmp_path)
    n = sess.save_cookies(
        s,
        [
            {"name": "a", "value": "1", "domain": "wp.brest-region.edu.by", "path": "/"},
            {"name": "b", "value": "2", "domain": ".google.com", "path": "/"},
        ],
    )
    assert n == 1
    assert [c["name"] for c in json.loads(s.cookies_file.read_text())] == ["a"]


def test_parse_empty_cookie_header_fails():
    with pytest.raises(sess.SessionError):
        sess.parse_cookie_header("   ", "h")


def _check_with(tmp_path, handler):
    s = make(tmp_path)
    transport = httpx.MockTransport(handler)
    import edu_by.session as mod

    orig = mod.make_client
    mod.make_client = lambda settings, cookies=None: httpx.Client(
        transport=transport, cookies=cookies, follow_redirects=True
    )
    try:
        return sess.check(s, cookies=httpx.Cookies())
    finally:
        mod.make_client = orig


def test_check_valid(tmp_path):
    r = _check_with(tmp_path, lambda req: httpx.Response(200, text="<html>explorer</html>"))
    assert r.valid


def test_check_redirect_to_login(tmp_path):
    def handler(req):
        if req.url.path == "/explorer.aspx":
            return httpx.Response(302, headers={"Location": "/?ReturnUrl=%2fexplorer.aspx"})
        return httpx.Response(200, text='<input type="password">')

    r = _check_with(tmp_path, handler)
    assert not r.valid


def test_shadowsocks_command_from_url(tmp_path, monkeypatch):
    monkeypatch.setattr(shadowsocks.shutil, "which", lambda b: "/usr/bin/sslocal")
    s = make(tmp_path, ss_url="ss://abc@host:8388", ss_local_port=1081)
    cmd = shadowsocks.build_command(s)
    assert cmd == ["/usr/bin/sslocal", "-b", "127.0.0.1:1081", "--server-url", "ss://abc@host:8388"]


def test_shadowsocks_config_drops_own_local(tmp_path, monkeypatch):
    monkeypatch.setattr(shadowsocks.shutil, "which", lambda b: "/usr/bin/sslocal")
    cfg = tmp_path / "ss.json"
    cfg.write_text(
        json.dumps({"server": "h", "server_port": 1, "password": "p", "local_port": 1080})
    )
    s = make(tmp_path, ss_config=cfg, ss_bind="0.0.0.0")
    cmd = shadowsocks.build_command(s)
    assert cmd[-2:] == ["-b", "0.0.0.0:1080"]
    written = json.loads(Path(cmd[2]).read_text())
    assert "local_port" not in written and written["server"] == "h"
    assert oct(Path(cmd[2]).stat().st_mode & 0o777) == "0o600"


def test_effective_proxy_uses_ss_host(tmp_path):
    s = make(tmp_path, ss_url="ss://x", ss_host="ss")
    assert s.effective_proxy == "socks5h://ss:1080"


def test_shadowsocks_missing_binary(tmp_path, monkeypatch):
    monkeypatch.setattr(shadowsocks.shutil, "which", lambda b: None)
    with pytest.raises(shadowsocks.ShadowsocksError):
        shadowsocks.build_command(make(tmp_path, ss_url="ss://x"))
