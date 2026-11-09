---
status: partially verified
updated: 2026-11-09
---

# Authentication

## Verified (reported by the site owner)

- Login page: `EDU_LOGIN_URL`, for Brest region `https://wp.brest-region.edu.by/`.
- Constructor: `EDU_CONSTRUCTOR_URL`, for Brest region `https://wp.brest-region.edu.by/explorer.aspx`.
- Login form has a **captcha** – a human must log in in a real browser (`edu session login` / `edu browse`).
- The session expires after **~1 hour without activity**.
- Login page title: `Вход в систему` (Log in to the system). (observed 2026-11-09)
- Without a session, `GET /explorer.aspx` returns **302 → `/login_end.aspx`**. `edu session check` treats any redirect away from `explorer.aspx` as logged out. (observed 2026-11-09)

## Network (observed 2026-11-09)

- Reachable directly from a Belarusian ISP uplink (`wlo1`). Not reachable through the WireGuard VPN `wg2`, nor through the provided Shadowsocks exit (TCP connects time out).

## Unverified (needs a HAR capture)

- The `.aspx` pages suggest ASP.NET WebForms: expect cookies such as `ASP.NET_SessionId` and possibly `.ASPXAUTH`, and form posts carrying `__VIEWSTATE` / `__EVENTVALIDATION`.
- `edu session check` treats the session as valid if `explorer.aspx` returns 200, stays on `explorer.aspx` (no `ReturnUrl` redirect) and shows no password field. Confirm what an expired session actually returns.
- Assumed: a plain GET of `explorer.aspx` counts as activity and resets the idle timer (what `keepalive` relies on). Confirm by keeping a session alive past 1 h.

## To capture next

1. DevTools → Network → "Preserve log", log in, then "Save all as HAR".
2. Note which cookies are set after login and which of them disappear or change on expiry.
3. Sanitize (remove cookie values, tokens, ViewState, personal data) before saving excerpts to `knowledge/captures/`.
