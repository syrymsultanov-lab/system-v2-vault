# CLAUDE.md — SYSTEM V2.1

## Проект
SYSTEM V2.1 — AI-powered lead pipeline для MLM команды InCruises (250+ партнёров).
Домен: sairateam.com | Supabase ref: `njwraxmlzglmofxiwmxs` | 19 таблиц (max 25)

## Роли
- Сырым = owner, decision-maker
- Claude Code = имплементация (ты)
- Claude Chat = стратегия
- Сайра = team leader, конечный пользователь

## Стек
- Landing: static HTML/CSS/JS в корне репо → Hostinger `public_html`
- DB: Supabase PostgreSQL + RLS
- Automation: n8n на Hostinger VPS
- Dashboard: 9 вкладок на live данных, хостится на Hostinger

## 20 таблиц (актуально на 2026-05-17, сверено `list_tables`)

**Ядро (7):** `partners`, `leads`, `lead_messages`, `lead_channels`, `ai_jobs`, `templates`, `events_log`

**Партнёрские (7):** `contacts` (телефонная книга), `tasks`, `partner_settings` (1:1), `partner_integrations`, `training_modules`/`lessons`/`progress`

**Сообщения (2):** `inbound_messages` (Inbound + WF5/WF6 пишет/читает), `outbound_messages` (Inbound reactive пишет status=sent inline, WF9 диспатчит proactive cron)

**AI-pipeline (4):** `lead_events` (имеет `event_type` колонку!), `ai_recommendations` (Phase B bridge с `processed_at` idempotency), `ai_job_runs` (job_id nullable — Conversation Loop + Inbound reactive пишут cost), `kb_chunks` (RAG: vector(1536), RPC `match_kb_chunks`, 2289 chunks из 13 KB-источников)

**Для деталей колонок** — `mcp__supabase__list_tables(verbose=true)`. CLAUDE.md не источник истины по колонкам.

**Триггеры:**
- `auth.users INSERT → partners` (auto-create partner row)
- `partners INSERT → partner_settings` (дефолты)
- `leads INSERT → ai_jobs queued` (qualify_lead — WF3 cron подхватывает)

## AI-pipeline (Phase B production 2026-05-04, Plan B intake 2026-05-05, Phase C1 reactive+RAG 2026-05-17)
```
landing form (app.js POST) → WF1 webhook /system-v2/lead-intake →
  Normalize → Find Existing → If dup? Use Existing : Insert Lead →
  Extract Lead Id → lead_events INSERT → events_log INSERT → respond {ok:true}
  (триггер create_qualification_job создаёт ai_jobs queued автоматически)
WF3 cron 2 мин:  claim_next_ai_job RPC → OpenAI → score+temp+next_action+summary
                 → leads.status=qualified+score → ai_recommendations row → ai_jobs.succeeded
WF4 cron 2 мин:  fetch ai_recommendations[processed_at=null] → tasks INSERT → mark processed
                 → events_log row (actor='system') → TG notify (60_Notify_TG_Group, non-blocking)
WF13 cron 5 мин: reset_stuck_ai_jobs → running > 10 мин → failed

# Phase C1 — Conversational AI (sandbox 2026-05-17)
TG Conversation Inbound (webhook /tg-inbound, reactive ~3-5s end-to-end):
  parse update → claim chat_id → find contact → check consent →
  insert inbound_messages → touch contact (last_inbound_at) →
  fetch partner/settings/history → embed query (text-embedding-3-small) →
  match_kb_chunks(top_k=5) → build prompt with RAG context →
  OpenAI gpt-4.1-mini → parse JSON → if reply ok:
    TG sendMessage → insert outbound (status=sent) →
    log ai_job_runs (cost) → update contact (ai_state, last_outbound_at, updated_at)
AI Conversation Loop cron 2 мин (proactive — приветствия, followup):
  claim_next_conversation RPC → fetch ctx → OpenAI → outbound dry_run →
  WF9 dispatch picks up
WF9 dispatch cron 1 мин (proactive only): fetch outbound dry_run/queued →
  lookup contact tg_chat_id → TG sendMessage → mark sent / skipped
Outbound Followup Scheduler cron 1ч: schedule_followups RPC (+24h/+72h/+7d → cold)
AI Budget Watchdog cron daily 09:00: get_ai_cost_summary → TG alert if ≥80% или exceeded
```

**RLS:** все 19 own-only через `partner_id IN (SELECT id FROM partners WHERE user_id = auth.uid())`. Исключение: `partners` SELECT открыт authenticated. `templates` с `partner_id IS NULL` системные, видны всем.

**Security:** все 6 SECURITY DEFINER функций закрыты от anon/authenticated (миграция `lockdown_security_definer_functions` 2026-05-04). n8n работает через `SUPABASE_SERVICE_ROLE_KEY`.

## Критические правила
1. Contact ≠ Lead. Лиды только через форму. Контакты = телефонная книга
2. Никаких гарантий дохода (InCruises policy + Meta/WABA)
3. Один запрос = один выход. Не расширять scope
4. DB first — **всегда `mcp__supabase__list_tables` + `information_schema.columns` перед SQL**. Не доверять числу таблиц в этом файле — реальность по `list_tables`
5. RLS: пустые результаты anon → проверь политики, не данные
6. Lovable `types.ts` НЕ описывает реальную БД
7. Старый проект (66 таблиц, ap-southeast-2) — мёртв
8. Прежде чем начать работу, скажи как проверишь результат. Не можешь — спрашивай уточнение
9. **events_log.actor whitelist**: `me|ai|system|partner|lead|anon` (или NULL). CHECK constraint отвергает кастом. Cron/n8n → `'system'`
10. **n8n jsonBody с nested `{}`**: literal JSON template + `{{ JSON.stringify(...) }}` вместо `={{ {a:1, b:{nested}} }}` — последнее ломает parser
11. **n8n $env в Docker**: env нужна в ДВУХ местах — `.env` + `environment:` секции `docker-compose.yml`. После `compose up -d` (не restart) — иначе контейнер не видит. См. memory `reference_n8n_docker_env_proxy`

## Дизайн
Premium Marine: Deep Emerald `#0B3D2E`, Midnight Navy `#0E1A2B`, Base Dark `#1C1F26`, Pale Aqua `#A8C5BC`, CTA Copper `#C97D4E`. Video hero: `hero-bg.mp4`

## Локальная разработка
Файлы лендинга в корне репо (не `landing/`).
```bash
npx http-server . -p 3000
# Открывать: http://127.0.0.1:3000/?ref=TEST001
# НЕ через file:// (CORS)
```

## Live Phase C блокеры
- **AI Agent Questionnaire** (`obsidian-vault/projects/AI Agent Questionnaire.md`, 17 разделов A-R) — ждёт ответов Сырыма с 2026-04-25. Блокер всего Phase C. Нужна 1-2 часовая сессия
- **InCruises Knowledge Base** (`obsidian-vault/reference/InCruises Knowledge Base.md`) — готов; засев в `templates` или RAG после Questionnaire
- **Notify Phase 2** (email weekly digest) — backend (Hostinger SMTP / Gmail / Resend) не выбран
- **CLAUDE.md еженедельная гигиена** — `obsidian-vault/PROMT_CLEAN_CLAUDE_WEEKLE.md`

## Phase C scope (per `projects/AI Agent.md`)

12-18 сессий: C1 Text Q&A (2-3) → C2 Эскалация (1-2) → C3 Outbound ranking + approval UI (2-3) → C4 Dispatch (1-2) → C5 RAG (2-3) → C6 Voice (3-5).

## Obsidian Vault

Путь: `./obsidian-vault/`

### Структура (актуальная)
```
obsidian-vault/
├── projects/    # SYSTEM V2.md, AI Agent.md, n8n Workflows.md, Landing Page.md, Dashboard.md, Referral System.md
├── daily/       # YYYY-MM-DD.md итоги сессий
└── reference/   # Design System.md, Business Rules.md, Tech Stack.md, InCruises Compensation Plan.md, InCruises Knowledge Base.md
```

### Правила работы
1. Начало сессии — прочитай последний `daily/`
2. Конец сессии — создай/обнови daily note
3. Новые решения/инсайты → `projects/` или `reference/`
4. `[[wiki-links]]` для связей
5. Перед ответом о проекте — grep по vault
