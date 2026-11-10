---
status: partially verified
updated: 2026-11-10
source: /SystemWJG.asmx/js (generated client), capture constructor-2026-11-09
---

# SystemWJG.asmx – JSON web service

ASP.NET AJAX web service. Call: `POST /SystemWJG.asmx/<Method>`, `Content-Type: application/json`, body = JSON object of parameters, reply `{"d": <result>}`. Methods are listed by `GET /SystemWJG.asmx/js`.

| Method | Params | Notes |
|---|---|---|
| `IsSession` | – | **verified**: `{"d": true}` when logged in. Used by `edu session check` |
| `IsDelClassifier` | `guid` | **verified**: `""` if the section is delete-protected, else `"Подклассификаторов: N<br/>Объектов: M<br/>"` (N subsections, M objects) |
| `ClearSession` | – | likely logout – don't call |
| `ClearCache` | `url` | **verified 2026-11-10**: body `{"url": "<site host>"}`, reply `{"d": "Cache сайта обновлен."}` (site cache refreshed) – clears the public site cache, harmless |
| `ClearHtml` | `source` | probably sanitizes HTML |
| `Name` | `SessionName` | unknown |
| `NameObject`, `NameObjectShort` | `obj_name` | unknown |
| `NewRulesClassifier` | `pos`, `guid_template` | unknown, likely a write |
| `ListUsers` | `name` | user lookup |
| `ShowHideInfo` | `status` | UI toggle |
| `GetNewPinGraphics` | – | new captcha image |
| `ListActiveSession`, `ListActiveSessionSendMessage(txt, ListUsers)`, `ListActiveSessionReadMessage`, `ListActiveSessionReadMessageOK` | | in-app messaging between active users |

Only `IsSession`, `IsDelClassifier` and `ClearCache` were called so far. Treat everything else as unverified, and anything that may write as a write.
