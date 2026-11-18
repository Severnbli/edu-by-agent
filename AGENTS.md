# edu-by-agent

Tooling and knowledge that let agents operate the **edu.by site constructor** (the builder used to manage Belarusian education websites): create and edit pages, menus, news, documents and media through the same HTTP requests the constructor's web UI makes.

The repo has three layers, built in this order:

1. **Knowledge** (`knowledge/`) – verified facts about the constructor: endpoints, request/response shapes, auth flow, quirks.
2. **Skills** (`.agents/skills/`) – task-oriented instructions for agents ("publish a news item", "add a page to the menu") that call the CLI.
3. **CLI** (`src/edu_by/`, command `edu`) – Python utilities: session handling, proxy, and a thin request client. The **MCP server** (`edu mcp`) wraps the same `api/`; it must not duplicate logic.

Codex discovers skills in `.agents/skills/` and registers MCP via `.codex/config.toml` in trusted workspaces. Claude Code uses `CLAUDE.md`, skill directory symlinks, and `.mcp.json`. See the [MCP guide](docs/mcp.md) for setup.

## Development

Run commands from the repository root. Docker and Docker Compose are required. Run `./edu build` for the first build and after dependency changes. For Python changes, run `./edu lint` and focused tests such as `./edu test tests/test_mcp.py`. Run `./edu test` for the full suite.

- Read [the development guide](docs/development.md) before changing runtime, authentication, proxy, or capture behavior.
- Read [the knowledge index](knowledge/README.md) before changing constructor behavior, and [the MCP guide](docs/mcp.md) before changing MCP tools or prompts.
- Consult [the backlog](TASKS.md) for pending work and update it as tasks are completed.
- Login requires a human to solve the captcha. Keep passwords and session cookies out of output and commits. Route only edu.by traffic through the configured proxy and surface proxy failures.


- **Never read raw captures** (`*.raw.jsonl`) – only `*.sanitized.*`. Before relying on a new sanitized capture, check that no cookie values or `GuidSession` UUIDs from the raw one remain.
- Never put real tokens, cookies or `GuidSession` values from captures into tests or docs – use made-up values.
- **Never invent endpoints or parameters.** Everything in `knowledge/` and `api/` must come from observed traffic (HAR from DevTools, mitmproxy) or a real response. Mark anything unverified as `status: unverified` in the file's frontmatter.
- When you discover new behavior, update `knowledge/` in the same change as the code that uses it, and cite the capture in `knowledge/captures/`. Strip cookies, tokens, CSRF values and personal data from captures before saving.
- These are **live public school websites**. Read-only requests are fine. Before anything that publishes, deletes, overwrites or changes menus/permissions, show the user what will change and get confirmation – unless the skill they invoked says otherwise. Prefer a draft/unpublished state when the constructor offers one.
- Be gentle with the server: no parallel bulk requests, small delay between write calls, respect any rate limits seen.
- **Every write goes through a plan** (`edu_by.api.changes.Change`): plan functions only read and return before/after values and a token; `apply()` writes, then re-reads to verify. Don't add a write that skips this – the CLI and the MCP server both rely on it for the confirmation step.
- Skills call the `edu` CLI (or the `edu_by` package). They don't hand-write curl with cookies. If a skill needs something the CLI lacks, add it to the CLI first.
- Each skill's `SKILL.md`: when to use it, required inputs, exact commands, how to verify the result, and what to do on common errors (expired session, validation error). Its `mcp.md` says the same with MCP tool calls – keep the two in step (`tests/test_mcp.py` checks the pairing and the tool names).

## Site data

This repo is **public** and holds only what is true of the constructor itself: endpoints, fields, quirks, tools, skills. Anything about a particular school site – its host, e-mail, section / template / module ids as facts about that site, redesign plans and status, screenshots, content – goes to the git-ignored `.session/notes/` (`.session/notes/site.md`: plan, status, live facts; larger files under `.session/design/…`). Examples in tracked files use `sch1.example.edu.by`. Before committing, `git grep` the diff for the site's host and e-mail.

## Git

- All work is committed directly on the `dev` branch – no feature branches. `main` is updated only through a pull request from `dev` to `main`.
- Commit after each logical step – don't batch unrelated changes or leave work uncommitted at the end of a task.
- Before committing, check the diff for secrets (cookies, `ss://` links, passwords, raw HAR files).

## Style

- Python 3.10 (the base image's), type hints, `ruff` for lint and format, `httpx` for HTTP, `typer` for CLI, `pydantic-settings` for config.
- Playwright's pip version must equal the base image tag (`Dockerfile`), or Chromium won't be found.
- Never use the em dash anywhere – write the en dash (–) instead, in code, docs, commit messages.
- Constructor UI text is in Russian/Belarusian. Keep original UI labels verbatim in `knowledge/` (with a translation in parentheses) so agents can match them.
