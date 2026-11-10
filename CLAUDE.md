# edu-by-mcp

Tooling and knowledge that let agents operate the **edu.by site constructor** (the builder used to manage Belarusian education websites): create and edit pages, menus, news, documents and media through the same HTTP requests the constructor's web UI makes.

The repo has three layers, built in this order:

1. **Knowledge** (`knowledge/`) – verified facts about the constructor: endpoints, request/response shapes, auth flow, quirks.
2. **Skills** (`.claude/skills/`) – task-oriented instructions for agents ("publish a news item", "add a page to the menu") that call the CLI.
3. **CLI** (`src/edu_by/`, command `edu`) – Python utilities: session handling, proxy, and a thin request client. A later **MCP server** will wrap the same client; it must not duplicate logic.

## Layout

```
CLAUDE.md
TASKS.md                  # backlog for the next sessions
pyproject.toml            # Python 3.10+ package
Dockerfile, compose.yaml  # the only supported runtime
edu                       # wrapper: ./edu <command>
.env.example              # template; real .env is git-ignored
src/edu_by/
  cli.py                  # `edu` entry point (typer)
  config.py               # settings from env / .env / flags
  http.py                 # shared httpx client: proxy, cookies, headers, retries
  session.py              # login via browser, import, check, keepalive
  webforms.py             # WebForms form state, async postbacks, delta parsing
  har.py                  # live HAR recorder, sanitizer, summary
  direct_proxy.py         # interface-bound local HTTP proxy (direct mode)
  site.py                 # Site: one logged-in site (client, session check, explorer, path cache, lock) – shared by CLI and MCP
  api/                    # one module per constructor area:
                          #   reads: explorer (tree, lists, types), objects, treecache (section paths)
                          #   planned writes: changes (Change, token), dialogs, objects_write, sections, trash
docs/mcp.md               # MCP server design (task 5)
knowledge/
  README.md               # index of what is known and how confident
  auth.md                 # login, captcha, cookies, expiry
  endpoints/              # one file per area, documented from real traffic
  captures/               # sanitized HAR excerpts used as evidence (no secrets)
.claude/skills/<name>/SKILL.md
tests/
```

Directories are created as the work reaches them – don't add empty scaffolding.

## Commands

Everything runs in **Docker** – no local venv or Python install. `./edu` wraps `docker compose` (image `edu-by:dev`, repo bind-mounted at `/app`, so code edits apply without a rebuild; rebuild only after dependency changes).

```bash
./edu build                      # build the image (Playwright Chromium + sslocal + the package)
./edu --help
./edu proxy up                   # start the proxy container for the configured mode (direct or ss)
./edu proxy down | logs
./edu proxy check                # whether the login/constructor pages are reachable through the proxy
./edu proxy pac                  # PAC file routing *.edu.by via the proxy, for your own browser
./edu browse [URL]               # any *.edu.by in a desktop Chromium window via the proxy (other sites direct)
./edu browse --har NAME          # same, recording edu.by traffic live to .session/har/NAME.*
./edu har summary .session/har/NAME.sanitized.jsonl   # request shapes (read only sanitized files)
./edu session login              # browser window prefilled from .env: solve captcha, click login -> session saved, window closes
./edu session import             # paste a Cookie header copied from DevTools instead
./edu session check              # exit 0 valid, 2 expired
./edu session keepalive          # ping every 45 min so the 1 h idle timeout never hits
./edu tree | objects SEC | types # reads; `edu object show ID`, `edu section show SEC`, `edu trash list TYPE`
./edu object set ID --set name=… # writes preview by default; --yes applies, delete level needs --token
./edu section add PARENT --title …   (also object add|copy|move|sort|upload|trash, section set|move|delete, trash restore|purge)
./edu test                       # pytest
./edu lint | fmt                 # ruff check / fix + format
```

The browser is the **Chromium bundled in the image** (from the Playwright base image), not one installed on the host; its profile is `.session/browser-profile`. Desktop windows use the host X server (`/tmp/.X11-unix`, works with XWayland); `./edu` runs `xhost +SI:localuser:$USER` so only your UID may connect. Containers run as your UID/GID, so `.session/` files stay yours.

## Auth facts (do not try to automate around these)

- Login is protected by a **captcha**. Never try to solve, bypass or farm it. Site, login and password can be prefilled from `EDU_SITE`, `EDU_USERNAME`, `EDU_PASSWORD` (optional `EDU_SECURITY`) – the human only types the captcha. `EDU_PASSWORD` is a secret: never print, log or commit it. A human solves it once in a real browser window (`./edu session login` opens one through Playwright, using the configured proxy).
- The session **expires after ~1 hour without activity**. `keepalive` sends a cheap authenticated request on an interval below that (default 45 min). Every command checks the session first and tells the user to log in again on expiry, not retry blindly.
- The session cookie is stored in `.session/` (git-ignored, file mode 600). Never print full cookie values in logs, output, commits or knowledge files – mask all but the last 4 characters.

## Site URLs

Both URLs are configurable (`.env` or env vars); the defaults are the Brest region instance:

- `EDU_LOGIN_URL` – login page, default `https://wp.brest-region.edu.by/`
- `EDU_CONSTRUCTOR_URL` – constructor (admin) page, default `https://wp.brest-region.edu.by/explorer.aspx`

Never hardcode a host anywhere else – derive it from these settings. Other regions run the same constructor on other hosts.

## Proxy

edu.by may be reachable only from Belarusian IPs, so **edu.by traffic** (`edu.by` and `*.edu.by`, from the httpx client **and** the Playwright browser) goes through one proxy setting. Everything else is direct:

- `EDU_PROXY` in `.env`, or `--proxy` on any command. Accepts `http://`, `https://`, `socks5://`, `socks5h://` (use `socks5h` to resolve DNS through the proxy), with optional `user:pass@`.
- **Direct mode** (`EDU_INTERFACE=wlo1`, the current setup): the host's default route goes through a WireGuard VPN (`wg2`) that can't reach the site, while the physical uplink can. `./edu proxy up` starts the `direct` container – a small built-in HTTP proxy (`edu proxy direct`, `src/edu_by/direct_proxy.py`) on `127.0.0.1:$EDU_DIRECT_PORT` (1081) whose outgoing sockets are bound to that interface (`SO_BINDTODEVICE`, no root needed). Takes priority over Shadowsocks.
- **Shadowsocks**: httpx and Chromium can't speak it, so `./edu proxy up` starts the `ss` container running `sslocal` (shadowsocks-rust, baked into the image) from `EDU_SS_URL` (an `ss://` link) or `EDU_SS_CONFIG` (path to a JSON config **inside the repo**, e.g. `secrets/shadowsocks.json`, git-ignored). Its own local listener is replaced by `127.0.0.1:$EDU_SS_LOCAL_PORT` (1080). Note: in testing (2026-11-09) the provided Shadowsocks exit could not reach wp.brest-region.edu.by.
- Priority: `EDU_PROXY` > direct mode > Shadowsocks. All containers use **host networking**, so these `127.0.0.1` proxies work from the containers and from your own browser alike.
- No proxy configured means a direct connection. Never silently fall back to direct if a configured proxy fails – fail with a clear error.
- `ss://` links and passwords are secrets: never print, log or commit them.
- The proxy is **only** for edu.by traffic. Enforced in code: the httpx client mounts the proxy only for `edu.by` / `*.edu.by` (and ignores host proxy env vars), and the browser uses a PAC that sends only those hosts to the proxy.
- Everything else is **local (direct)**: image builds, package and binary downloads, IP/diagnostic lookups, third-party assets in the browser, and Claude/Anthropic API traffic. Never send non-edu.by requests through the proxy, never export it host-wide (`HTTP(S)_PROXY`, `ALL_PROXY`, system settings), and don't add a "proxy everything" option.
- A proxy with credentials can't be expressed in PAC, so the browser refuses it instead of proxying all traffic.

## Working rules

- **Never read raw captures** (`*.raw.jsonl`) – only `*.sanitized.*`. Before relying on a new sanitized capture, check that no cookie values or `GuidSession` UUIDs from the raw one remain.
- Never put real tokens, cookies or `GuidSession` values from captures into tests or docs – use made-up values.
- **Never invent endpoints or parameters.** Everything in `knowledge/` and `api/` must come from observed traffic (HAR from DevTools, mitmproxy) or a real response. Mark anything unverified as `status: unverified` in the file's frontmatter.
- When you discover new behavior, update `knowledge/` in the same change as the code that uses it, and cite the capture in `knowledge/captures/`. Strip cookies, tokens, CSRF values and personal data from captures before saving.
- These are **live public school websites**. Read-only requests are fine. Before anything that publishes, deletes, overwrites or changes menus/permissions, show the user what will change and get confirmation – unless the skill they invoked says otherwise. Prefer a draft/unpublished state when the constructor offers one.
- Be gentle with the server: no parallel bulk requests, small delay between write calls, respect any rate limits seen.
- **Every write goes through a plan** (`edu_by.api.changes.Change`): plan functions only read and return before/after values and a token; `apply()` writes, then re-reads to verify. Don't add a write that skips this – the CLI and the MCP server both rely on it for the confirmation step.
- Skills call the `edu` CLI (or the `edu_by` package). They don't hand-write curl with cookies. If a skill needs something the CLI lacks, add it to the CLI first.
- Each skill's `SKILL.md`: when to use it, required inputs, exact commands, how to verify the result, and what to do on common errors (expired session, validation error).

## Git

- All work is committed directly on the `dev` branch – no feature branches. `main` is updated only through a pull request from `dev` to `main`.
- Commit after each logical step – don't batch unrelated changes or leave work uncommitted at the end of a task.
- Before committing, check the diff for secrets (cookies, `ss://` links, passwords, raw HAR files).

## Style

- Python 3.10 (the base image's), type hints, `ruff` for lint and format, `httpx` for HTTP, `typer` for CLI, `pydantic-settings` for config.\n- Playwright's pip version must equal the base image tag (`Dockerfile`), or Chromium won't be found.
- Never use the em dash (—) anywhere – write the en dash (–) instead, in code, docs, commit messages.
- Constructor UI text is in Russian/Belarusian. Keep original UI labels verbatim in `knowledge/` (with a translation in parentheses) so agents can match them.

## Status

Done: Docker runtime, `session` (login prefilled from `.env`, security level Hight), `proxy` (direct mode + Shadowsocks), `browse` (with live HAR recording) and `har` commands, WebForms helper (`edu_by.webforms`), `edu-session` skill, read-only `api/` + `edu tree | objects | types`, shared `Site`, planned writes in `api/` with CLI commands (previews live-tested, apply not yet), MCP SDK in the image. Captures are mapped in `knowledge/`.
**Next work is listed in [`TASKS.md`](TASKS.md)** – start there, and update it as you finish tasks.
