"""Section path cache (`.session/tree-<site>.json`): lets a bare section ID be reached
with one request per ancestor instead of a tree walk.

Only IDs, titles and ID paths are stored – nothing secret. A stale entry (section moved
or deleted) is dropped by the explorer when its path no longer leads to it.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

from edu_by.api.explorer import Explorer, Section
from edu_by.config import Settings


def cache_file(s: Settings) -> Path:
    name = re.sub(r"[^\w.-]", "_", s.site or s.site_host or "default")
    return s.session_dir / f"tree-{name}.json"


def load(s: Settings) -> dict[str, Section]:
    f = cache_file(s)
    try:
        data = json.loads(f.read_text())
    except (OSError, ValueError):
        return {}
    out = {}
    for sid, d in data.get("sections", {}).items():
        path = d["path"].split("/")
        out[sid] = Section(sid, d.get("title", ""), path[-2] if len(path) > 1 else None, path)
    return out


def save(s: Settings, ex: Explorer) -> None:
    """Merge what this explorer learned into the cache; forget sections it found stale."""
    known = {**load(s), **ex.cached}
    for sid in ex.stale:
        known.pop(sid, None)
    known.update(ex.sections)
    data = {
        "updated": time.strftime("%Y-%m-%d %H:%M:%S"),
        "sections": {
            sid: {"title": sec.title, "path": "/".join(sec.path)}
            for sid, sec in sorted(known.items(), key=lambda kv: kv[1].path)
        },
    }
    f = cache_file(s)
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1))
    tmp.replace(f)
