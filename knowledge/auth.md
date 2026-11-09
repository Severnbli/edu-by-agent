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
  - `ctl00$ContentMain$ListSecurity` – Безопасность (security) level, see below
  - `ctl00$ContentMain$LoginStart = Авторизация` (Log in)
- Then the browser loads `/explorer.aspx`.
- A human solves the captcha (`./edu session login` or `./edu browse`). Never automate it.

## Session (verified)

- **`ASP.NET_SessionId` alone is the login credential** (httpOnly, browser-session cookie). Requests with only this cookie work; with only `WJG` they don't. No User-Agent binding (a different UA still works). Several sessions of one user can be active at once – a new login does not end the old one. (verified 2026-11-09)
- `WJG` (not httpOnly, expires in 30 days) holds **UI preferences**, not auth: `ListSecurity`, `SelectExplorer` (last opened section) and, depending on the level, remembered login form values. The public site host gets its own `ASP.NET_SessionId`.
- Pages carry a per-login token `ctl00$GuidSession` (UUID) in a hidden field. It is also sent as `gs=` to `RengerProvider.aspx`. Treat it as a secret (the HAR sanitizer redacts it).
- Check: `POST /SystemWJG.asmx/IsSession` with `{}` returns `{"d": true}` when logged in.
- Without a session, `GET /explorer.aspx` returns **302 → `/login_end.aspx`**.
- Idle expiry ~1 hour (reported by the site owner).

## Security level (ListSecurity) – verified 2026-11-09

Options: `Hight` Высокая (high, default), `Medium` Средняя (medium), `Low` Низкая (low), `Zero` Нулевая (zero). Logging in at Hight, Medium and Low gave identical sessions (same cookie dependence, no UA binding, parallel sessions allowed). The only difference is what the `WJG` cookie remembers for the login form:

| Level | WJG keys |
|---|---|
| Hight | `ListSecurity`, `SelectExplorer` |
| Medium | + `SiteName` |
| Low | + `SiteName`, `UserName` |
| Zero | not tested – very likely + the password, in a script-readable 30-day cookie |

Use **Hight** (the `EDU_SECURITY` default). With `.env` prefill the lower levels give no benefit. Not tested: whether the level changes the idle timeout.

## Unverified

- Whether `IsSession` or a GET of `explorer.aspx` resets the idle timer (`keepalive` uses the `explorer.aspx` GET). Confirm by keeping a session alive past 1 h.
- Whether the security level affects the ~1 h idle timeout.

## Network (observed 2026-11-09)

- Reachable directly from a Belarusian ISP uplink (`wlo1`). Not reachable through the WireGuard VPN `wg2`, nor through the provided Shadowsocks exit (TCP connects time out).
