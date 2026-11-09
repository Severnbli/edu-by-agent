---
name: edu-session
description: Get, check and keep alive a logged-in edu.by constructor session, and route traffic through the configured proxy (HTTP, SOCKS5 or Shadowsocks). Use before any task that talks to the constructor, when a request fails with a login page or redirect, or when the user wants to open an edu.by site through the proxy.
---

# edu.by session and proxy

All commands run from the repo root through Docker: `./edu ...`.

## 1. Make sure the proxy works

- Direct mode (`EDU_INTERFACE`) or Shadowsocks (`EDU_SS_URL` / `EDU_SS_CONFIG`): the `direct` or `ss` container must be running – `./edu proxy up` starts the right one (detached), `docker compose ps` shows it.
- Then run `./edu proxy check`. Expect HTTP 200 for the login and constructor URLs.
- On connection errors, report the error to the user. Never fall back to a direct connection.

## 2. Check the session

`./edu session check` – exit code 0 means valid, 2 means expired or not logged in.

## 3. If invalid: the user logs in (captcha)

The captcha means **you can't log in yourself**. Ask the user to run one of these:

- `! ./edu session login` – opens a browser with site/login/password prefilled from `.env` (`EDU_SITE`, `EDU_USERNAME`, `EDU_PASSWORD`); they solve the captcha and click Авторизация, the window closes by itself. You may also start it yourself in the background and wait.
- `! ./edu browse` – same browser; cookies are saved when they close it.
- `! ./edu session import` – paste a `Cookie` header from DevTools.

Then run `edu session check` again.

## 4. Long tasks

The session dies after ~1 h idle. For long interactive work, suggest the user keep `./edu session keepalive` running in another terminal.

## Rules

- Never print cookie values or `ss://` links. `edu session check` already masks them.
- Opening another `*.edu.by` site for the user: `./edu browse <url>`. Non-edu.by sites always go direct.
