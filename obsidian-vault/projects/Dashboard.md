---
project: system-v2
component: dashboard
status: live
tabs: 9
tabs-done: 9
tabs-live: 9
updated: 2026-04-20
---

# Dashboard (9 вкладок)

## Статус: Live на Supabase (9/9 вкладок, E2E 2026-04-20)

Все вкладки переведены с mock-данных на реальный Supabase через raw-fetch паттерн (`assets/js/api.js`). RLS own-only. Без SDK, токен в sessionStorage.

## 9 вкладок (все на live)
1. ✅ **Дашборд** — `leads/contacts/tasks/events_log` (счётчики + сегодня), chart за 7 дней, лидерборд `partners` по `group_volume` с пометкой «ВЫ», компас PV/GV/ранг
2. ✅ **Лиды** — `SELECT leads WHERE partner_id` через RLS, PATCH status с optimistic rollback, фильтры/поиск, XSS-защита через `esc()`
3. ✅ **Контакты** — `SELECT contacts`, приглашение через `PATCH invited_at=now()`, DELETE, ref_code из `currentPartner`
4. ✅ **Задачи** — `SELECT tasks` с embedded `lead`/`contact`, CRUD (markDone/reopen/snooze/delete) через PATCH/DELETE
5. ✅ **Моя структура** — `SELECT partners`, BFS-дерево от `me.id`, team_size рекурсивно, ref_code в карточке
6. ✅ **История** — `events_log?actor_id=eq.me&order=created_at.desc&limit=500`, actors me/ai/system/partner/lead/anon
7. ✅ **Обучение** — `training_modules?select=*,lessons:training_lessons(*)` + `training_progress`, toggle урока через POST/DELETE
8. ✅ **Шаблоны** — `SELECT templates` (own + системные через RLS), POST duplicate, PATCH activate, DELETE own
9. ✅ **Настройки** — load `partners+partner_settings+partner_integrations+upline`, profile PATCH, AI/notify autosave, messengers upsert, `/auth/v1/user` для смены пароля

## Общий паттерн

- Общий REST-клиент `assets/js/api.js`: `sb(method, path, body)` + `sbAuth()` для `/auth/v1`
- `getCurrentPartner()` с кешем в sessionStorage
- Все мутации с optimistic rollback при 4xx/5xx
- `requireAuth()` редиректит на `../login.html` если токена нет

## Единый UX-паттерн (применён во всех заполненных вкладках)
1. `.welcome` — заголовок + краткое описание + правый бейдж счётчика
2. `.stats` (4 sc-карточки) — ключевые метрики раздела
3. Ряды pill-фильтров (`.pnl-tabs > .pt`) — несколько срезов параллельно
4. `.sch > .sch-i` — поиск по основным полям
5. `.tl > .ti` (rows) или `.mod-grid > .mod` (cards) — список объектов
6. Модалка (`.modal/.modal-box/.modal-head/.modal-grid/.modal-actions`) с детальным просмотром и действиями
7. `.toast` — глобальные уведомления (clipboard, успех/ошибка)

## Общий UX
- Header (`renderHeader` в `dashboard.js`) — един для всех вкладок, клик по логотипу и кнопке «🏠 На лендинг» ведут на `../index.html`
- Toast-уведомления (`.toast`) — глобальный компонент
- Модалки по единому шаблону (`.modal/.modal-box/.modal-head/.modal-grid/.modal-actions`)
- Бейджи статусов/тегов через `.tg/.tg1../.tg-g/.tg-r`

## Особые компоненты
- **Team Ranking Leaderboard** — рейтинг партнёров
- **MLM Growth Calculator** — визуализация 3×3×3=39
- **Прогресс рангов** — до следующего ранга

## Принципы UI
- Минимализм
- Единый header
- Hover-подсказки везде
- [[Design System]] цвета

## Связи
- [[SYSTEM V2]]
- [[AI Agent]]
- [[Design System]]
