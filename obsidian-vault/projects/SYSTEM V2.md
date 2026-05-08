---
project: system-v2
status: active
supabase-ref: njwraxmlzglmofxiwmxs
tables: 19
max-tables: 25
hosting: hostinger
domain: sairateam.com
stack: static HTML/CSS/JS
created: 2025-11-01
updated: 2026-05-06
---

# SYSTEM V2.1 — AI-Powered MLM Pipeline

## Суть
AI-powered lead pipeline и partner management для MLM команды Сайры (InCruises, 250+ партнёров). Цель — минимизировать ручную работу партнёров, делегируя квалификацию, презентацию и follow-up ИИ-агенту.

## Роли
- **Сырым** — владелец, decision-maker
- **Claude Chat** — оркестратор/стратег
- **Claude Code** — имплементация
- **Сайра** — team leader, конечный пользователь

## Архитектура
```
Landing (sairateam.com) → Supabase (leads) → n8n (VPS) → AI Agent → Channels
```

- **Landing**: static HTML/CSS/JS, Hostinger `public_html`
- **DB**: Supabase, ref `njwraxmlzglmofxiwmxs`
- **Automation**: n8n на Hostinger VPS
- **Dashboard**: строится в Antigravity, хостится на Hostinger

## 19 таблиц (актуально на 2026-05-04, см. CLAUDE.md для полного списка)

**Ядро (7):** `partners`, `leads`, `lead_messages`, `lead_channels` (переименованная старая `contacts`), `ai_jobs` (11 cols), `templates`, `events_log` (с actor whitelist)

**Партнёрские (7):** `contacts` (новая телефонная книга), `tasks` (15 cols, type/source/priority/done — **нет status**), `partner_settings` (1:1), `partner_integrations`, `training_modules`/`lessons`/`progress`

**Сообщения (2):** `inbound_messages` (WF5/WF6), `outbound_messages` (WF9)

**AI-pipeline (3):** `lead_events` (имеет колонку `event_type`!), `ai_recommendations` (Phase B bridge с `processed_at` idempotency, добавлен 2026-05-04), `ai_job_runs` (не используется активно)

**Триггеры:** `auth.users → partners`, `partners → partner_settings`, `leads INSERT → ai_jobs queued`. RLS own-only для всех 19.

**Security:** все 6 SECURITY DEFINER функций закрыты от anon/authenticated миграцией `lockdown_security_definer_functions` 2026-05-04. n8n работает через `SUPABASE_SERVICE_ROLE_KEY`.

## Текущий этап
- [x] [[Landing Page]] — live на sairateam.com
- [x] [[Referral System]] — ref_code работает
- [x] [[Dashboard]] — 9 вкладок заполнены на mock-данных
- [x] DB-схема под все 9 вкладок (2026-04-19, 9 миграций)
- [x] Верификация формы → Supabase leads write (end-to-end, 2026-04-19)
- [x] Переключение вкладок на live (9/9: leads, contacts, tasks, structure, history, training, templates, settings, dashboard — E2E прогон пройден 2026-04-20)
- [x] **FTP-деплой на Hostinger** (2026-04-29): актуальные `app.js`, `api.js` (новый), 9 вкладок дашборда, `index.html` с фонами картинок. Форма пишет напрямую в Supabase (без n8n)
- [x] **E2E прогон формы на проде** (2026-04-30): лид Вячеслав Чернобровкин — форма → leads → триггер → ai_jobs queued → виден в дашборде
- [x] **WF3 — AI Lead Qualification** production-ready (2026-05-03):
  - 2026-05-02: первый E2E на лиде Чернобровкин → score 75, status qualified
  - 2026-05-03: WF3 v2 переписан на атомарный `claim_next_ai_job(p_job_type)` RPC (race window закрыт), Complete Job пишет полный AI-ответ в `ai_jobs.result` (score/temperature/next_action/summary/raw), Mark Failed единая error-branch для 5 нод записывает диагностику в result.error
  - WF13 Watchdog (5-мин cron, `reset_stuck_ai_jobs(10)`) сбрасывает зависшие running > 10 мин в failed
  - Smoke 2026-05-03: тест-лид (synthetic 35 y.o. female из Алматы) → score=30, temperature=cold, lead qualified — корректно отрабатывает cold-сегмент
- [x] **Phase B — qualifier → task chain** production-ready (2026-05-04):
  - WF3 v3: вставлена нода `65_Insert_Recommendation` → пишет в `ai_recommendations`
  - WF4 v2: переписан на `NN_node_name` конвенцию, idempotency через `processed_at IS NULL` filter, `actor='system'` (whitelist), удалён `status:'todo'` (колонки нет)
  - Миграция `ai_recommendations.processed_at` + partial index
  - E2E smoke на 2 синтетических лидах: `lead → ai_jobs → ai_recommendations → tasks → events_log` цепочка работает
  - Bag fixes WF1/2/12 events_log (`event_type → event`, `actor='system'`) deployed на VPS
- [x] **Security lockdown** (2026-05-04): REVOKE EXECUTE FROM anon/authenticated на 6 SECURITY DEFINER функций. Advisor 16 → 3 WARN (3 intentional/Free Plan)
- [x] **WF1 Plan B switchover** (2026-05-05): landing `app.js` теперь POST на `/webhook/system-v2/lead-intake`. WF1 интейк-канал работает: Normalize → dedup check → Insert Lead → lead_events → events_log → respond. Queue AI Job нода удалена (dedup триггер). E2E через webhook curl PASS. WF5 webhookId UUID assigned (был null → 404).
- [x] **WF7 удалён** (2026-05-06): конвертация lead→contact отменена. Decision: лид навсегда остаётся лидом. Будущая фича — обратное направление (contact → lead) когда партнёр инициирует презентацию для существующего контакта
- [ ] Phase C — outbound + conversational + voice (planning, 12-18 сессий, см. [[AI Agent]])
- [ ] Contact import (CSV/VCF/Google)
- [ ] **Future:** contact → lead path (когда партнёр запускает презентацию для контакта из телефонной книги, нужен workflow для создания связанного лида)

## Build Plan (порядок)
1. Финализировать CLAUDE.md
2. Claude Code prompt для лендинга (3 страницы)
3. Claude Code prompt для дашборда (9 вкладок)
4. AI agent + n8n (после стабилизации)

## Ссылки
- [[Design System]]
- [[Business Rules]]
- [[Referral System]]
- [[Landing Page]]
- [[Dashboard]]
- [[AI Agent]]
- [[n8n Workflows]]
- [[InCruises Compensation Plan]]
