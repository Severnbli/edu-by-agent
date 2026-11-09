---
name: edu-session
description: Get, check and keep alive a logged-in edu.by constructor session, and route traffic through the configured proxy (HTTP, SOCKS5 or Shadowsocks). Use before any task that talks to the constructor, when a request fails with a login page or redirect, or when the user wants to open an edu.by site through the proxy.
---

# edu.by session and proxy

All commands run from the repo root: `uv run edu ...` (or `.venv/bin/edu ...`).

## 1. Make sure the proxy works

- Shadowsocks (`EDU_SS_URL` or `EDU_SS_CONFIG` set): the user must have `uv run edu proxy up` running in a separate terminal. Don't start it yourself in the background without asking.
- Then run `uv run edu proxy check`. Expect an exit IP and HTTP 200 for the login and constructor URLs.
- On connection errors, report the error to the user. Never fall back to a direct connection.

## 2. Check the session

`uv run edu session check` – exit code 0 means valid, 2 means expired or not logged in.

## 3. If invalid: the user logs in (captcha)

The captcha means **you can't log in yourself**. Ask the user to run one of these:

- `! uv run edu session login` – opens a browser; they log in, then press Enter in the terminal.
- `! uv run edu browse` – same browser; cookies are saved when they close it.
- `! uv run edu session import` – paste a `Cookie` header from DevTools.

Then run `edu session check` again.

## 4. Long tasks

The session dies after ~1 h idle. For long interactive work, suggest the user keep `uv run edu session keepalive` running in another terminal.

## Rules

- Never print cookie values or `ss://` links. `edu session check` already masks them.
- Opening another `*.edu.by` site for the user: `uv run edu browse <url>`. Non-edu.by sites go direct unless `--all` is passed.
