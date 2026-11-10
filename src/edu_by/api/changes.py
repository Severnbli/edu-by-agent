"""Planned writes: every change to the site is first described, then applied on request.

A write operation is split in two:

1. `plan_*()` reads the current state (GET / tree selection only) and returns a `Change`:
   what will be touched, each field's value before and after, warnings, and a `token`.
2. `Change.apply()` performs the requests, re-reads the result and reports what is there now.

The `token` is a short hash of the action, the target and the before/after values. A caller
that previews a change (CLI dry run, MCP tool without a token) shows it to the human; the
apply step re-plans and refuses if the token differs – the site changed in between, or the
request is not the one that was shown. This is the confirmation step of CLAUDE.md, the same
for the CLI and the MCP server.

Levels: `edit` (content, unpublished objects, new sections), `publish` (visible on the public
site), `delete` (trash, permanent delete, section delete). Callers may ask for a stronger
confirmation for `publish` and `delete`.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal

Level = Literal["edit", "publish", "delete"]
LEVELS: tuple[Level, ...] = ("edit", "publish", "delete")
PREVIEW_CHARS = 400  # long values (HTML) are shortened in previews, the token covers them in full


class WriteError(RuntimeError):
    pass


class TokenMismatch(WriteError):
    pass


def _short(v: Any) -> Any:
    if isinstance(v, str) and len(v) > PREVIEW_CHARS:
        return f"{v[:PREVIEW_CHARS]}… ({len(v)} chars)"
    return v


@dataclass
class Change:
    action: str  # e.g. "object.update", "section.add"
    target: str  # human-readable target, e.g. "object 126733 «Новость: …» in 1011/59791"
    level: Level
    fields: dict[str, tuple[Any, Any]] = field(default_factory=dict)  # name -> (before, after)
    notes: list[str] = field(default_factory=list)  # warnings and side effects
    params: dict[str, Any] = field(default_factory=dict)  # what the caller asked for
    _do: Callable[[], dict] | None = field(default=None, repr=False, compare=False)

    @property
    def token(self) -> str:
        blob = json.dumps(
            [self.action, self.target, self.level, sorted(self.fields.items()), self.params],
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        )
        return hashlib.sha256(blob.encode()).hexdigest()[:12]

    @property
    def noop(self) -> bool:
        """Nothing would change (all fields already have the wanted values)."""
        return bool(self.fields) and all(b == a for b, a in self.fields.values())

    def preview(self) -> dict:
        return {
            "action": self.action,
            "target": self.target,
            "level": self.level,
            "changes": {
                k: {"before": _short(b), "after": _short(a)}
                for k, (b, a) in self.fields.items()
                if b != a
            },
            "notes": self.notes,
            "noop": self.noop,
            "token": self.token,
        }

    def describe(self) -> str:
        lines = [f"{self.action}  [{self.level}]  {self.target}"]
        for k, (b, a) in self.fields.items():
            if b != a:
                lines.append(f"  {k}: {_short(b)!r} -> {_short(a)!r}")
        lines += [f"  ! {n}" for n in self.notes]
        if self.noop:
            lines.append("  (nothing to change)")
        lines.append(f"  token: {self.token}")
        return "\n".join(lines)

    def apply(self, token: str | None = None) -> dict:
        """Run the change. With `token`, refuse unless it matches this plan."""
        if token is not None and token != self.token:
            raise TokenMismatch(
                f"token {token} does not match the current plan {self.token}: the site "
                "changed since the preview, or the request differs. Preview again."
            )
        if self._do is None:
            raise WriteError(f"{self.action}: nothing to apply")
        if self.noop:
            return {"action": self.action, "applied": False, "reason": "nothing to change"}
        result = self._do()
        return {"action": self.action, "applied": True, **result}
