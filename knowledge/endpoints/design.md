---
status: partially verified
updated: 2026-11-10
source: read-only GETs of RengerProvider.aspx and G_RengerProvider/* (2026-11-10), public pages of the site, capture edit-2026-11-10
---

# Site design (RengerProvider)

The site's look is made of page templates, modules (controls), style sets, scripts and resource strings. All are edited in the constructor under `RengerProvider.aspx`. **Everything here is site-wide** – a save changes every page at once, and there is no draft or preview.

## Category pages (read-only GET)

`GET /RengerProvider.aspx?guid=<category>&gs=<GuidSession>` (the `gs` value is the `ctl00$GuidSession` hidden field of explorer.aspx – a session secret, mask it). Categories (left tree labels verbatim):

| guid | Label | Items open in |
|---|---|---|
| `Master` | Мастер (master templates) | `Templates` |
| `Head` | Главный (home page templates) | `Templates` |
| `Normal` | Обычный (ordinary page templates) | `Templates` |
| `NotUseTemplate` | Не используемые (unused templates) | `Templates` |
| `404` | Документ не найден (404) | `Templates` |
| `Actual`, `Old`, `NotUse` | modules: current / old / unused | `Controls` |
| `TemplateGlobal` | object type templates | `TemplateGlobal` |
| `JavaScript` | scripts | `JavaScript` |
| `CssPacked` | style sets | `CssPacked` |
| `ResourceString` | resource strings | `ResourceString` |
| `Utility`, `ExportToXml` | tools – not explored |

Items are links calling `Open('<dialog>', this, '<id>')`, which opens `/G_RengerProvider/<dialog>.aspx?guid=<id>` (WebForms dialog, see dialogs.md). On the test site: 338 items (5+3+3+2+1 templates, 92 modules, 35 type templates, 25 scripts, 27 style sets, ~140 strings).

## Style sets – CssPacked.aspx?guid=<id>

Form: `ctl00$Title_1 = [<id>] Редактирование набора стилей` (editing a style set), CSS text in `ctl00$Main$TextBoxBody`. Public pages link the sets a template uses, in order: `<link href='css.aspx?guid=<id>' rel='stylesheet' data-name='<set name>'/>`. Saving a set is **not captured yet**.

Templates attach scripts through `ctl00$Main$HiddenFieldForSave` (`<js value="<id>"/>` list, see dialogs.md). How a template chooses its style sets is not known yet.

## Low-vision mode (version for the visually impaired)

The public «Версия для слабовидящих» button switches classes on `<body>`: `colorSiteBlack`, `colorSiteWhite`, `colorSiteBlue`, `colorSiteBeige` (and others from the same script). A new design style must not apply in that mode – scope its selectors with `body:not([class*="colorSite"])`.

## Public site from the container browser

Chromium with the PAC file timed out on the public school host (the httpx client reaches it through the same proxy). Working approach: route the page's edu.by requests through the httpx client (`page.route` + `route.fulfill`) and let other hosts go direct.
