# edu.by session (MCP tools)

The server uses the session saved by the CLI (`.session/` of its repository). It never logs in itself, because the login has a captcha that only a human solves.

1. `edu_session_status`: `valid: true` means go on.
2. Not valid, or any tool says "Session expired": ask the user to run in the repository
   - `./edu session login`: a browser opens with the site, login and password prefilled. They type the captcha and click «Авторизация», and the window closes;
   - or `./edu browse --login` if they want the window to stay open.
3. Call `edu_session_status` again, then repeat the failed call. Its preview token stays valid only if the site didn't change.

The session ends after ~1 h without activity. For long work the user can keep `./edu session keepalive` running. If tools fail with connection errors, the proxy is down: the user runs `./edu proxy up` and `./edu proxy check`.
