"""Sanitize and summarize HAR captures of the constructor.

Raw HARs contain session cookies, the login password and captcha answers. `sanitize`
removes them (and ASP.NET ViewState blobs) so the result can be read by agents and
excerpted into knowledge/captures/. Never read or commit a raw HAR.
"""

from __future__ import annotations

import json
import os
import re
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit

REDACTED = "<redacted>"
SENSITIVE_NAME = re.compile(
    r"pass|pwd|captcha|token|secret|viewstate|eventvalidation|session|auth|cookie|key|csrf",
    re.I,
)
SENSITIVE_HEADER = re.compile(
    r"^(cookie|set-cookie|authorization|proxy-authorization|x-csrf.*|x-xsrf.*)$", re.I
)
HIDDEN_INPUT_VALUE = re.compile(
    r'(<input[^>]*name="(?:__VIEWSTATE\w*|__EVENTVALIDATION|__PREVIOUSPAGE)"[^>]*value=")[^"]*(")',
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
    return DELTA_HIDDEN.sub(rf"\1{REDACTED}\2", text)


def _redact_url(url: str) -> str:
    parts = urlsplit(url)
    if not parts.query:
        return url
    query = urlencode(_redact_pairs(parse_qsl(parts.query, keep_blank_values=True)))
    return parts._replace(query=query).geturl()


def _headers(headers: list[dict]) -> list[dict]:
    return [
        {**h, "value": REDACTED} if SENSITIVE_HEADER.match(h.get("name", "")) else h
        for h in headers
    ]


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


def summarize(path: Path, include_static: bool = False) -> list[str]:
    """One line per distinct request shape: method path [query keys] -> status, body fields."""
    har = json.loads(path.read_text(encoding="utf-8"))
    counts: Counter[str] = Counter()
    order: list[str] = []
    for e in har.get("log", {}).get("entries", []):
        req, resp = e["request"], e["response"]
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
