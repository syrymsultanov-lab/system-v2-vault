---
project: system-v2
status: active
supabase-ref: njwraxmlzglmofxiwmxs
tables: 15
max-tables: 20
hosting: hostinger
domain: sairateam.com
stack: static HTML/CSS/JS
created: 2025-11-01
updated: 2026-04-19
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

## 15 таблиц (после обкатки 2026-04-19)

**Ядро (8, обновлены):**
1. `partners` (19) — +user_id→auth.users, bio, city, country, timezone, upline_id, rank, volumes
2. `leads` (21) — +priority, notes, budget, tags jsonb
3. `lead_messages` (6)
4. `lead_status_log` (6)
5. `lead_channels` (5) — **переименованная старая `contacts`**, каналы связи лида
6. `ai_jobs` (7)
7. `templates` (16) — +title, category, channel, author, active, ai_enabled, vars, uses_count, partner_id
8. `events_log` (8) — +actor, actor_id

**Новые (7):**
9. `contacts` (14) — новая «телефонная книга партнёра»
10. `tasks` (15) — to-do
11. `partner_settings` (18) — 1:1, AI/уведомления/quiet hours
12. `partner_integrations` (8) — N:1, мессенджеры/интеграции
13. `training_modules` (10)
14. `training_lessons` (9)
15. `training_progress` (4)

**Триггеры:** `auth.users → partners`, `partners → partner_settings`. RLS own-only для всех 15.

## Текущий этап
- [x] [[Landing Page]] — live на sairateam.com
- [x] [[Referral System]] — ref_code работает
- [x] [[Dashboard]] — 9 вкладок заполнены на mock-данных
- [x] DB-схема под все 9 вкладок (2026-04-19, 9 миграций)
- [x] Верификация формы → Supabase leads write (end-to-end, 2026-04-19)
- [x] Переключение вкладок на live (9/9: leads, contacts, tasks, structure, history, training, templates, settings, dashboard — E2E прогон пройден 2026-04-20)
- [ ] AI Agent + n8n workflows
- [ ] Contact import (CSV/VCF/Google)

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
