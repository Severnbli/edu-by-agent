---
status: partially verified
updated: 2026-11-09
source: capture constructor-2026-11-09 (#86 login), read-only checks
---

# Authentication

## Login (verified)

- Login page: `EDU_LOGIN_URL`, for Brest region `https://wp.brest-region.edu.by/`, title `Вход в систему` (Log in to the system).
- Async postback to `/` with `ctl00$ScriptManagerWindow = ctl00$ScriptManagerWindow|ctl00$ContentMain$LoginStart` and fields:
  - `ctl00$ContentMain$SiteName` – the site to manage (e.g. `sch12.baranovichi.edu.by`)
  - `ctl00$ContentMain$UserName`, `ctl00$ContentMain$UserPwd`
  - `ctl00$ContentMain$TextBoxPin` – **captcha** answer, image `/RandomKey.aspx?guid=<uuid>` (new one: `SystemWJG.GetNewPinGraphics`)
  - `ctl00$ContentMain$ListSecurity` – `Hight` [sic] in the capture (security level option)
  - `ctl00$ContentMain$LoginStart = Авторизация` (Log in)
- Then the browser loads `/explorer.aspx`.
- A human solves the captcha (`./edu session login` or `./edu browse`). Never automate it.

## Session (verified)

- Cookies on the constructor host: `ASP.NET_SessionId` (session cookie) and `WJG` (persistent, ~1 year). The public site host gets its own `ASP.NET_SessionId`.
- Pages carry a per-login token `ctl00$GuidSession` (UUID) in a hidden field. It is also sent as `gs=` to `RengerProvider.aspx`. Treat it as a secret (the HAR sanitizer redacts it).
- Check: `POST /SystemWJG.asmx/IsSession` with `{}` returns `{"d": true}` when logged in.
- Without a session, `GET /explorer.aspx` returns **302 → `/login_end.aspx`**.
- Idle expiry ~1 hour (reported by the site owner).

## Unverified

- Whether `IsSession` or a GET of `explorer.aspx` resets the idle timer (`keepalive` uses the `explorer.aspx` GET). Confirm by keeping a session alive past 1 h.
- What `ListSecurity` options mean, and whether `WJG` alone restores a session.

## Network (observed 2026-11-09)

- Reachable directly from a Belarusian ISP uplink (`wlo1`). Not reachable through the WireGuard VPN `wg2`, nor through the provided Shadowsocks exit (TCP connects time out).
