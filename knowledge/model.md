---
status: verified
updated: 2026-11-10
source: capture constructor-2026-11-09, read-only inspection of explorer.aspx / dialogs
---

# Constructor data model

One login works on **one site** (e.g. `sch1.example.edu.by`). The constructor host (e.g. `wp.brest-region.edu.by`) serves many sites; the site is picked at login (`SiteName`).

## Entities

| UI term (ru) | Meaning | Example IDs |
|---|---|---|
| Классификатор (classifier) | A **section / page** of the site, arranged as a tree | 1001 Главная страница (home), 1051, 1041 О школе |
| Объект (object) | A **content item** inside a section (text block, news, image, file link, ...) | 1303, 123693, 126653 |
| Шаблон / тип объекта (template / object type) | The **type** of an object, also a layout template | 524 Блок html, 534 Новость |
| Корзина (trash) | One trash bin per object type | 525, 535 |
| Шаблон страницы (page template) | Section layout, `fk_Template` in the section editor | 0 = inherit from parent, 1024 Базовый шаблон |

## ID suffix encodes the kind (from `DirectLinkEvent` in ExplorerA.js)

- `…1` – classifier (section): 1001, 1051, 59751
- `…3` – object: 1303, 126653
- `…4` – object type / template: 524, 534
- `…5` – trash bin of a type (type ID + 1): 535 is the trash for 534 Новость

## Object types (SelType in AddObject.aspx)

Стандартные (standard):

| ID | Type | | ID | Type |
|---|---|---|---|---|
| 524 | Блок html (текст раздела) – section HTML text | | 654 | Гиперссылка на html страницу – link to page |
| 534 | Новость – news | | 674 | Запись – record |
| 304 | Графический объект – image | | 694 | Баннер – banner |
| 544 | Аннотация фото-видео галереи – gallery annotation | | 704 | ЭСО (медиатека) – media library item |
| 554 | Объявление – announcement | | 734 | Гиперссылка на файл для скачивания – downloadable file |
| 564 | Административная процедура – administrative procedure | | 804 | Вкладка – tab |
| 574 | Карточка сотрудника – staff card | | 824 | Слайд – slide |
| 594 | Методический материал – teaching material | | 834 | Видеообъект – video |
| 644 | План 6-го дня – "6th day" plan | | 854 | Отчет по 6-му дню – "6th day" report |
| 404 | Опрос – poll | | 424 | Элемент дизайна – design element |
| 434 | Платная услуга – paid service | | 444 | Продукция собственного производства – own products |
| 454 | Профессия – profession | | | |

Системные (system, forms/requests): 414 Электронное обращение, 514 Оставить запись, 464 Заказ справки, 714 Заказ услуги, 764, 604, 614, 624, 634, 664, 814 (adm.edu.by requests). Не в группе (ungrouped): 844.

The list is per site/instance – read it from `AddObject.aspx` (elements with a `gg="<id>"` attribute) instead of hardcoding.

## Publication

Objects listed with CSS class `obj_not_published` are unpublished. In the object editor the flag is the `ctl00$Main$CheckBoxStatusObject` checkbox labelled «Разрешить публикацию» (allow publication), under «Доступ:» (access): **checked = published** (verified 2026-11-10: a listed-published object has it checked, an `obj_not_published` one unchecked).

## Object types in the tree

The explorer tree lists types under «Шаблоны объектов» grouped by `Стандартные` (standard), `Системные` (system), `Не в группе` (ungrouped): node value `sNodeTemplate\<group>\<id>`. `edu types` reads them from there (no extra request). `AddObject.aspx` shows the types for creating in two blocks: `#ls2` (big tiles: 524, 534, 304) and `#ls1` (the rest of the standard ones).
