"""Sanitize and summarize HAR captures of the constructor.

Raw HARs contain session cookies, the login password and captcha answers. `sanitize`
removes them (and ASP.NET ViewState blobs) so the result can be read by agents and
excerpted into knowledge/captures/. Never read or commit a raw HAR.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit

REDACTED = "<redacted>"
SENSITIVE_NAME = re.compile(
    r"pass|pwd|pin|captcha|token|secret|viewstate|eventvalidation|session|auth|cookie|key|csrf|^gs$",
    re.I,
)
SENSITIVE_HEADER = re.compile(
    r"^(cookie|set-cookie|authorization|proxy-authorization|x-csrf.*|x-xsrf.*)$", re.I
)
HIDDEN_INPUT_VALUE = re.compile(
    r'(<input[^>]*name="(?:__VIEWSTATE\w*|__EVENTVALIDATION|__PREVIOUSPAGE)"[^>]*value=")[^"]*(")',
    re.I,
)
# Per-login GuidSession token: hidden input, gs= URL parameter, JS/JSON strings.
GUID_SESSION = re.compile(
    r'((?:name="ctl00\$GuidSession"[^>]*value="|[?&](?:amp;)?gs=|GuidSession\W{1,6}))'
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    re.I,
)
# ASP.NET AJAX delta responses: |length|hiddenField|__VIEWSTATE|<value>|
DELTA_HIDDEN = re.compile(r"(\|hiddenField\|(?:__VIEWSTATE\w*|__EVENTVALIDATION)\|)[^|]*(\|)")


def _redact_pairs(pairs: list[tuple[str, str]]) -> list[tuple[str, str]]:
    return [(k, REDACTED if SENSITIVE_NAME.search(k) and v else v) for k, v in pairs]


def _redact_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            k: (
                REDACTED
                if SENSITIVE_NAME.search(str(k)) and v not in (None, "")
                else _redact_json(v)
            )
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [_redact_json(v) for v in value]
    return value


def _redact_text(text: str, mime: str) -> str:
    mime = (mime or "").lower()
    if "x-www-form-urlencoded" in mime:
        return urlencode(_redact_pairs(parse_qsl(text, keep_blank_values=True)))
    if "json" in mime:
        try:
            return json.dumps(_redact_json(json.loads(text)), ensure_ascii=False)
        except ValueError:
            pass
    text = HIDDEN_INPUT_VALUE.sub(rf"\1{REDACTED}\2", text)
    text = GUID_SESSION.sub(rf"\1{REDACTED}", text)
    return DELTA_HIDDEN.sub(rf"\1{REDACTED}\2", text)


def _redact_url(url: str) -> str:
    parts = urlsplit(url)
    if not parts.query:
        return url
    query = urlencode(_redact_pairs(parse_qsl(parts.query, keep_blank_values=True)))
    return parts._replace(query=query).geturl()


def _redact_cookie_header(name: str, value: str) -> str:
    """Keep cookie names and attributes, drop values."""
    if name.lower() == "cookie":
        return "; ".join(
            f"{p.split('=', 1)[0].strip()}={REDACTED}" for p in value.split(";") if p.strip()
        )
    # Set-Cookie: one cookie per line (Playwright joins multiple with newlines)
    out = []
    for line in value.split("\n"):
        first, _, attrs = line.partition(";")
        cname = first.split("=", 1)[0].strip()
        out.append(f"{cname}={REDACTED}" + (f";{attrs}" if attrs else ""))
    return "\n".join(out)


def _headers(headers: list[dict]) -> list[dict]:
    result = []
    for h in headers:
        name = h.get("name", "")
        if name.lower() in ("cookie", "set-cookie"):
            result.append({**h, "value": _redact_cookie_header(name, h.get("value", ""))})
        elif SENSITIVE_HEADER.match(name):
            result.append({**h, "value": REDACTED})
        else:
            result.append({**h, "value": GUID_SESSION.sub(rf"\1{REDACTED}", h.get("value", ""))})
    return result


def sanitize_entry(entry: dict) -> dict:
    req, resp = entry.get("request", {}), entry.get("response", {})
    req["url"] = _redact_url(req.get("url", ""))
    req["headers"] = _headers(req.get("headers", []))
    req["cookies"] = [{"name": c.get("name"), "value": REDACTED} for c in req.get("cookies", [])]
    req["queryString"] = [
        {**q, "value": REDACTED} if SENSITIVE_NAME.search(q.get("name", "")) else q
        for q in req.get("queryString", [])
    ]
    post = req.get("postData")
    if post:
        if post.get("params"):
            post["params"] = [
                {**p, "value": REDACTED} if SENSITIVE_NAME.search(p.get("name", "")) else p
                for p in post["params"]
            ]
        if post.get("text"):
            post["text"] = _redact_text(post["text"], post.get("mimeType", ""))
    resp["headers"] = _headers(resp.get("headers", []))
    resp["cookies"] = [{"name": c.get("name"), "value": REDACTED} for c in resp.get("cookies", [])]
    content = resp.get("content", {})
    if content.get("text"):
        if content.get("encoding") == "base64":
            content["text"] = "<binary omitted>"
            content.pop("encoding")
        else:
            content["text"] = _redact_text(content["text"], content.get("mimeType", ""))
    return entry


def sanitize(src: Path, dst: Path) -> int:
    har = json.loads(src.read_text(encoding="utf-8"))
    entries = har.get("log", {}).get("entries", [])
    har["log"]["entries"] = [sanitize_entry(e) for e in entries]
    dst.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(dst, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(har, f, ensure_ascii=False, indent=1)
    return len(entries)


STATIC = re.compile(r"\.(css|js|png|jpe?g|gif|svg|ico|woff2?|ttf|eot|map)$", re.I)


def load_entries(path: Path) -> list[dict]:
    """Entries from a .har file or a .jsonl stream written by Recorder."""
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".jsonl":
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    return json.loads(text).get("log", {}).get("entries", [])


def write_har(entries: list[dict], dst: Path) -> None:
    har = {
        "log": {
            "version": "1.2",
            "creator": {"name": "edu-by", "version": "0.1"},
            "entries": entries,
        }
    }
    fd = os.open(dst, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(har, f, ensure_ascii=False, indent=1)


def summarize(path: Path, include_static: bool = False) -> list[str]:
    """One line per distinct request shape: method path [query keys] -> status, body fields."""
    har = {"log": {"entries": load_entries(path)}}
    counts: Counter[str] = Counter()
    order: list[str] = []
    for e in har.get("log", {}).get("entries", []):
        req, resp = e["request"], e.get("response") or {"status": "FAILED"}
        parts = urlsplit(req["url"])
        if not include_static and STATIC.search(parts.path):
            continue
        qkeys = sorted({k for k, _ in parse_qsl(parts.query, keep_blank_values=True)})
        post = req.get("postData") or {}
        if post.get("text") and "urlencoded" in post.get("mimeType", ""):
            fields = [k for k, _ in parse_qsl(post["text"], keep_blank_values=True)]
        else:
            fields = [p["name"] for p in post.get("params", [])]
        rmime = (resp.get("content", {}).get("mimeType") or "").split(";")[0]
        line = (
            f"{req['method']} {parts.netloc}{parts.path}"
            + (f" ?{','.join(qkeys)}" if qkeys else "")
            + f" -> {resp.get('status')} {rmime}"
            + (
                f" | {post.get('mimeType', '').split(';')[0]} fields={','.join(fields)}"
                if post
                else ""
            )
        )
        if line not in counts:
            order.append(line)
        counts[line] += 1
    return [f"{counts[k]:>3}x {k}" for k in order]


TEXT_MIME = re.compile(r"html|json|xml|text/plain|x-www-form-urlencoded", re.I)
MAX_BODY = 2 * 1024 * 1024


def _open_append(path: Path):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    return os.fdopen(fd, "a", encoding="utf-8")


class Recorder:
    """Writes each finished request immediately, so closing the browser loses nothing.

    <base>.raw.jsonl holds secrets (never read it); <base>.sanitized.jsonl is safe to read.
    """

    def __init__(self, base: Path, url_filter) -> None:
        base.parent.mkdir(parents=True, exist_ok=True)
        self.raw_path = base.with_suffix(".raw.jsonl")
        self.clean_path = base.with_suffix(".sanitized.jsonl")
        self.url_filter = url_filter
        self.count = 0
        self._raw = _open_append(self.raw_path)
        self._clean = _open_append(self.clean_path)

    def attach(self, context) -> None:
        context.on("requestfinished", self._on_request)
        context.on("requestfailed", self._on_request)

    def _on_request(self, request) -> None:
        if not self.url_filter(request.url):
            return
        try:
            entry = self._entry(request)
        except Exception as e:  # never break the user's browsing
            entry = {"request": {"method": request.method, "url": request.url}, "error": str(e)}
        import copy

        self._raw.write(json.dumps(entry, ensure_ascii=False) + "\n")
        self._raw.flush()
        clean = sanitize_entry(copy.deepcopy(entry)) if "response" in entry else entry
        self._clean.write(json.dumps(clean, ensure_ascii=False) + "\n")
        self._clean.flush()
        self.count += 1

    @staticmethod
    def _entry(request) -> dict:
        from datetime import datetime, timezone

        parts = urlsplit(request.url)
        req_headers = request.headers_array()
        post_text = request.post_data
        req_mime = next(
            (h["value"] for h in req_headers if h["name"].lower() == "content-type"), ""
        )
        entry: dict = {
            "startedDateTime": datetime.now(timezone.utc).isoformat(),
            "resourceType": request.resource_type,
            "request": {
                "method": request.method,
                "url": request.url,
                "httpVersion": "HTTP/1.1",
                "headers": req_headers,
                "cookies": [],
                "queryString": [
                    {"name": k, "value": v}
                    for k, v in parse_qsl(parts.query, keep_blank_values=True)
                ],
                **({"postData": {"mimeType": req_mime, "text": post_text}} if post_text else {}),
            },
        }
        resp = request.response()
        if resp is None:
            entry["response"] = {"status": 0, "headers": [], "cookies": [], "content": {}}
            entry["failure"] = request.failure
            return entry
        resp_headers = resp.headers_array()
        mime = next((h["value"] for h in resp_headers if h["name"].lower() == "content-type"), "")
        content: dict = {"mimeType": mime}
        if TEXT_MIME.search(mime) and not STATIC.search(parts.path):
            try:
                body = resp.body()
                content["size"] = len(body)
                content["text"] = body[:MAX_BODY].decode("utf-8", errors="replace")
            except Exception:
                content["text"] = "<body unavailable>"
        entry["response"] = {
            "status": resp.status,
            "statusText": resp.status_text,
            "headers": resp_headers,
            "cookies": [],
            "content": content,
        }
        return entry

    def finish(self) -> Path:
        """Close streams and build <base>.sanitized.har from the sanitized stream."""
        for f in (self._raw, self._clean):
            with contextlib.suppress(Exception):
                f.close()
        har_path = self.clean_path.with_suffix(".har")
        write_har(load_entries(self.clean_path), har_path)
        return har_path
