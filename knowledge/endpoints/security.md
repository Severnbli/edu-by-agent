---
status: partially verified
updated: 2026-11-10
source: guarded browser walk-through 2026-11-10 (read-only GETs, no saves)
---

# Security tab (security.aspx)

Pages `/Security.aspx?guid=<category>&gs=<GuidSession>`, category links in the left tree (`ctl00_Main_Left_TreeList`):

| Category | Label | Content |
|---|---|---|
| `Users` | «Пользователи» | user list, rows `Open('Users',this,'<id>')` |
| `SystemGroups` | «Группы» | groups: «Дизайнеры» (8), «Владельцы информации» (32), «Гости» (1024), «Редакторы разделов» (65536) – ids look like bit flags |
| `TemplateObject` | «Доступ / Объекты» | object types (same ids as model.md, 404 Опрос … 704 ЭСО) |
| `Classifier` | «Доступ / Классификаторы» | section tree `ctl00$Main_Right$TreeClassifier` |
| `MapAccess` | «Карта доступа» | table «Раздел на сайте:» / «Редакторы:» |
| `Audit` | «Настройка аудита» | text «Сайт работает в режиме 'Ограниченный аудит'.»; toolbar `ctl00$ContentSecondMenu$MyButtonSaveAuditToXML` «->XML», `MyButtonSaveAuditToCSV` «->CSV», `MyButtonClearAudit` «Очистить» (clear – never) |

Rows open `/G_Security/<category>.aspx?guid=<id>` (`Open(name, obj, guid)`). Per-section rights: `/G_Security/Classifier.aspx?guid=<section id>` – a select «Добавить пользователя...» + the usual Save buttons.

Nothing here is needed for content work. Never save in this area without an explicit user request – it changes who can edit the site.
