# CLAUDE.md — SYSTEM V2.1

## Проект
SYSTEM V2.1 — AI-powered lead pipeline для MLM команды InCruises (250+ партнёров).
Домен: sairateam.com | Supabase ref: `njwraxmlzglmofxiwmxs` | 21 таблица (max 25)

## Роли
- Сырым = owner, decision-maker
- Claude Code = имплементация (ты)
- Claude Chat = стратегия
- Сайра = team leader, конечный пользователь

## Стек
- Landing: static HTML/CSS/JS → Hostinger `public_html`
- DB: Supabase PostgreSQL + RLS
- Automation: n8n на Hostinger VPS
- Dashboard: Antigravity → Hostinger

## 19 таблиц (актуально на 2026-05-04 — сверено с `mcp__supabase__list_tables`)

**Ядро (7, `contacts` переосмыслена, `lead_status_log` дропнута 2026-04-29 — оставлен только `events_log`):**
- `partners` — партнёры (19 кол.): +user_id→auth.users, bio, city, country, timezone, language, avatar_url, upline_id, rank, is_active, personal_volume, group_volume
- `leads` — заявки (22): +priority, notes, budget, tags jsonb, assigned_at, updated_at, score
- `lead_messages` — сообщения лидам (6)
- `lead_channels` — **переименованная старая contacts** — каналы связи лида (tg/wa/email/phone/value)
- `ai_jobs` — задачи AI (11): +partner_id, target_type, target_id, payload jsonb. Триггер `create_qualification_job` ставит status='queued', RPC `claim_next_ai_job` атомарно переводит в running
- `templates` — шаблоны сообщений (16): +title, category (8 cat), channel (5 ch), author, active, ai_enabled, vars jsonb, uses_count, last_used_at, partner_id, updated_at
- `events_log` — журнал событий (8): +actor, actor_id (единственный журнал событий)

**Новые (7 созданы 2026-04-19):**
- `contacts` — **новая** «телефонная книга партнёра» (14): partner_id, name, phone, email, messenger, tag, notes, source, imported_from, invited_at
- `tasks` — to-do партнёра (15): title, type, source, priority, due_at, done, lead_id?, contact_id?, ai_job_id?
- `partner_settings` — 1:1 с partners (18): AI-режим, тон, язык, quiet hours, 6 флагов уведомлений, канал, marketing consent
- `partner_integrations` — N:1 (8): provider (wa/tg/ig/email/n8n/supabase), connected, config jsonb
- `training_modules` (10), `training_lessons` (9), `training_progress` (4)

**Сообщения (2, добавлены 2026-04-24):**
- `inbound_messages` (9) — входящие сообщения: partner_id, channel, external_message_id, from_address, to_address, body, direction. WF5 пишет, WF6 читает
- `outbound_messages` (9) — исходящие: partner_id, channel, to_address, body, status (draft/approved/sent/failed), sent_at. WF9 читает approved и отправляет

**AI-pipeline (3, обнаружены 2026-05-04 — раньше не в списке):**
- `lead_events` (6) — `lead_id, partner_id, event_type, payload, created_at`. **Имеет `event_type` колонку** (в отличие от events_log с `event`!). Журнал событий лидов. WF1/WF2 пишут.
- `ai_recommendations` (9) — `partner_id, target_type, target_id, recommendation_type, recommendation_payload jsonb, confidence numeric, processed_at, created_at`. Bridge между qualifier (WF3) и task creator (WF4). Idempotency через `processed_at IS NULL` filter.
- `ai_job_runs` (6) — `job_id, status, input, output, created_at`. Лог прогонов задач. Не используется активно.

**Триггеры:**
- `auth.users INSERT → partners` (auto-create partner row, backfill готов)
- `partners INSERT → partner_settings` (дефолты создаются автоматом)
- `leads INSERT → ai_jobs queued` (qualify_lead — WF3 cron подхватывает)

## AI-pipeline (Phase B production 2026-05-04, Plan B intake 2026-05-05)
```
landing form (app.js POST) → WF1 webhook /system-v2/lead-intake →
  Normalize → Find Existing → If dup? Use Existing : Insert Lead →
  Extract Lead Id → lead_events INSERT → events_log INSERT → respond {ok:true}
  (триггер create_qualification_job создаёт ai_jobs queued автоматически)
WF3 cron 2 мин:  claim_next_ai_job RPC → OpenAI → score+temp+next_action+summary
                 → leads.status=qualified+score → ai_recommendations row → ai_jobs.succeeded
WF4 cron 2 мин:  fetch ai_recommendations[processed_at=null] → tasks INSERT → mark processed
                 → events_log row (actor='system')
WF13 cron 5 мин: reset_stuck_ai_jobs → running > 10 мин → failed
```

**RLS:** все 21 таблица own-only через `partner_id IN (SELECT id FROM partners WHERE user_id = auth.uid())`. Исключение: `partners` SELECT открыт всем authenticated (для структуры/ref). `templates` с `partner_id IS NULL` — системные, видны всем.

## Критические правила
1. Contact ≠ Lead. Лиды только через форму. Контакты = телефонная книга
2. Никаких гарантий дохода (InCruises policy + Meta/WABA)
3. Один запрос = один выход. Не расширять scope
4. DB first — **всегда `mcp__supabase__list_tables` + `information_schema.columns` перед SQL**. Не доверять заявленному числу таблиц в этом файле — реальность по `list_tables`.
5. RLS: пустые результаты anon → проверь политики, не данные
6. Lovable `types.ts` НЕ описывает реальную БД
7. Старый проект (66 таблиц, ap-southeast-2) — мёртв!!!
8. Прежде чем начать работу, скажи, как ты будешь её проверять. Если не можешь придумать способ проверить результат — скажи об этом и попроси уточнить задачу!!!
9. **events_log.actor — whitelist**: только `me|ai|system|partner|lead|anon` (или NULL). Кастомные значения отвергаются CHECK constraint. Для cron/n8n использовать `'system'`.
10. **n8n jsonBody с nested `{}`**: использовать literal JSON template + `{{ JSON.stringify(...) }}` вместо `={{ {a:1, b:{nested}} }}` — последнее ломает parser. См. `feedback_n8n_jsonbody_expression`.

## Дизайн
Premium Marine: Deep Emerald `#0B3D2E`, Midnight Navy `#0E1A2B`, Base Dark `#1C1F26`, Pale Aqua `#A8C5BC`, CTA Copper `#C97D4E`. Video hero: `hero-bg.mp4`

## Локальная разработка
```bash
npx http-server . -p 3000
# Открывать: http://127.0.0.1:3000/landing/?ref=TEST001
# НЕ через file:// (CORS)
```

## TODO для следующей сессии
- **Notify-WF Phase 1** ✅ DONE 2026-05-15 (WF4 шлёт в TG group, msg_id=27 smoke PASS). Phase 2 (email weekly digest) — backend не выбран
- `git push origin main` — локально несколько коммитов впереди (растёт)
- Hostinger токен ротация (засветлён в чате 2026-05-02)
- **Phase C unblock** — ответить на `obsidian-vault/projects/AI Agent Questionnaire.md` (17 разделов A-R, ждут с 2026-04-25). Отдельная сессия 1-2 часа
- CLAUDE.md гигиена через `obsidian-vault/PROMT_CLEAN_CLAUDE_WEEKLE.md` (еженедельная чистка)

## Build Plan (порядок)
1. ✅ Финализировать CLAUDE.md
2. Claude Code prompt для лендинга (3 страницы: main+form, testimonials, legal)
3. Claude Code prompt для дашборда (9 вкладок)
4. AI agent + n8n (после стабилизации)

## Obsidian Vault (долговременная память)

Путь: `./obsidian-vault/`

### Структура
```
obsidian-vault/
├── projects/          # Заметки по компонентам системы
│   ├── SYSTEM V2.md   # Главная заметка (читай первой)
│   ├── Landing Page.md
│   ├── Dashboard.md
│   ├── Referral System.md
│   ├── AI Agent.md
│   └── n8n Workflows.md
├── daily/             # Итоги сессий (YYYY-MM-DD.md)
├── sessions/          # Детальные логи (по необходимости)
├── prompts/           # Сохранённые промты для повторного использования
├── reference/         # Справочники
│   ├── Design System.md
│   ├── Business Rules.md
│   ├── Tech Stack.md
│   └── InCruises Compensation Plan.md
└── .claude-commands/  # Промты для slash-команд
    ├── session-start.md
    ├── session-end.md
    ├── recall.md
    └── save-decision.md
```

### Правила работы с vault
1. В начале сессии — прочитай последний файл из `daily/`
2. В конце сессии — создай/обнови daily note с итогами
3. Новые решения и инсайты — сохраняй в `projects/` или `reference/`
4. Промты, которые хорошо сработали — в `prompts/`
5. Используй `[[wiki-links]]` для связей между заметками
6. Перед ответом на вопрос о проекте — ищи в vault через grep

### Slash-команды
Файлы в `.claude-commands/` содержат промты. Копируй в `.claude/commands/` если нужны slash-команды:
- `session-start` — загрузка контекста
- `session-end` — сохранение итогов
- `recall` — поиск по vault
- `save-decision` — сохранение решения
