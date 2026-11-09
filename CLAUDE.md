# edu-by-mcp

Tooling and knowledge that let agents operate the **edu.by site constructor** (the builder used to manage Belarusian education websites): create and edit pages, menus, news, documents and media through the same HTTP requests the constructor's web UI makes.

The repo has three layers, built in this order:

1. **Knowledge** (`knowledge/`) – verified facts about the constructor: endpoints, request/response shapes, auth flow, quirks.
2. **Skills** (`.claude/skills/`) – task-oriented instructions for agents ("publish a news item", "add a page to the menu") that call the CLI.
3. **CLI** (`src/edu_by/`, command `edu`) – Python utilities: session handling, proxy, and a thin request client. A later **MCP server** will wrap the same client; it must not duplicate logic.

## Layout

```
CLAUDE.md
pyproject.toml            # Python 3.10+ package
Dockerfile, compose.yaml  # the only supported runtime
edu                       # wrapper: ./edu <command>
.env.example              # template; real .env is git-ignored
src/edu_by/
  cli.py                  # `edu` entry point (typer)
  config.py               # settings from env / .env / flags
  http.py                 # shared httpx client: proxy, cookies, headers, retries
  session.py              # login via browser, import, check, keepalive
  api/                    # one module per constructor area (pages, news, media, ...)
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
./edu proxy up                   # start the Shadowsocks container (ss, SOCKS5 on 127.0.0.1:1080 too)
./edu proxy down | logs
./edu proxy check                # exit IP and whether the login/constructor pages are reachable
./edu proxy pac                  # PAC file routing *.edu.by via 127.0.0.1:1080, for your own browser
./edu browse [URL]               # any *.edu.by in a desktop Chromium window via the proxy (--all proxies everything)
./edu session login              # browser window: log in, solve captcha, press Enter -> session saved
./edu session import             # paste a Cookie header copied from DevTools instead
./edu session check              # exit 0 valid, 2 expired
./edu session keepalive          # ping every 45 min so the 1 h idle timeout never hits
./edu test                       # pytest
./edu lint | fmt                 # ruff check / fix + format
```

Desktop windows use the host X server (`/tmp/.X11-unix`, works with XWayland); `./edu` runs `xhost +SI:localuser:$USER` so only your UID may connect. Containers run as your UID/GID, so `.session/` files stay yours.

## Auth facts (do not try to automate around these)

- Login is protected by a **captcha**. Never try to solve, bypass or farm it. A human solves it once in a real browser window (`./edu session login` opens one through Playwright, using the configured proxy).
- The session **expires after ~1 hour without activity**. `keepalive` sends a cheap authenticated request on an interval below that (default 45 min). Every command checks the session first and tells the user to log in again on expiry, not retry blindly.
- The session cookie is stored in `.session/` (git-ignored, file mode 600). Never print full cookie values in logs, output, commits or knowledge files – mask all but the last 4 characters.

## Site URLs

Both URLs are configurable (`.env` or env vars); the defaults are the Brest region instance:

- `EDU_LOGIN_URL` – login page, default `https://wp.brest-region.edu.by/`
- `EDU_CONSTRUCTOR_URL` – constructor (admin) page, default `https://wp.brest-region.edu.by/explorer.aspx`

Never hardcode a host anywhere else – derive it from these settings. Other regions run the same constructor on other hosts.

## Proxy

edu.by may be reachable only from Belarusian IPs, so all traffic (httpx client **and** the Playwright login browser) goes through one proxy setting:

- `EDU_PROXY` in `.env`, or `--proxy` on any command. Accepts `http://`, `https://`, `socks5://`, `socks5h://` (use `socks5h` to resolve DNS through the proxy), with optional `user:pass@`.
- **Shadowsocks**: httpx and Chromium can't speak it, so `./edu proxy up` starts the `ss` container running `sslocal` (shadowsocks-rust, baked into the image) from `EDU_SS_URL` (an `ss://` link) or `EDU_SS_CONFIG` (path to a JSON config **inside the repo**, e.g. `secrets/shadowsocks.json`, git-ignored). Its own local listener is replaced by `EDU_SS_BIND:EDU_SS_LOCAL_PORT`. If `EDU_PROXY` is unset, the effective proxy is `socks5h://$EDU_SS_HOST:<port>` – `ss` inside compose, `127.0.0.1` on the host.
- No proxy configured means a direct connection. Never silently fall back to direct if a configured proxy fails – fail with a clear error.
- `ss://` links and passwords are secrets: never print, log or commit them.
- The proxy is **only** for edu.by traffic and downloads made by the containers (`edu`, `ss`). Never export it host-wide (`HTTP(S)_PROXY`, `ALL_PROXY`, system settings) or route Claude/Anthropic API traffic through it.

## Working rules

- **Never invent endpoints or parameters.** Everything in `knowledge/` and `api/` must come from observed traffic (HAR from DevTools, mitmproxy) or a real response. Mark anything unverified as `status: unverified` in the file's frontmatter.
- When you discover new behavior, update `knowledge/` in the same change as the code that uses it, and cite the capture in `knowledge/captures/`. Strip cookies, tokens, CSRF values and personal data from captures before saving.
- These are **live public school websites**. Read-only requests are fine. Before anything that publishes, deletes, overwrites or changes menus/permissions, show the user what will change and get confirmation – unless the skill they invoked says otherwise. Prefer a draft/unpublished state when the constructor offers one.
- Be gentle with the server: no parallel bulk requests, small delay between write calls, respect any rate limits seen.
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

Done: Docker runtime, `session`, `proxy` (incl. Shadowsocks) and `browse` commands, `edu-session` skill. Next: HAR captures of login and typical constructor actions to verify `knowledge/auth.md` and start `knowledge/endpoints/`.
