---
project: system-v2
status: active
supabase-ref: njwraxmlzglmofxiwmxs
tables: 20
max-tables: 25
hosting: hostinger
domain: sairateam.com
stack: static HTML/CSS/JS
created: 2025-11-01
updated: 2026-05-21
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

## 20 таблиц (актуально на 2026-05-17, см. CLAUDE.md для полного списка)

**Ядро (7):** `partners`, `leads`, `lead_messages`, `lead_channels` (переименованная старая `contacts`), `ai_jobs` (11 cols), `templates`, `events_log` (с actor whitelist)

**Партнёрские (7):** `contacts` (новая телефонная книга), `tasks` (15 cols, type/source/priority/done — **нет status**), `partner_settings` (1:1), `partner_integrations`, `training_modules`/`lessons`/`progress`

**Сообщения (2):** `inbound_messages` (WF5/WF6), `outbound_messages` (WF9)

**AI-pipeline (4):** `lead_events` (имеет колонку `event_type`!), `ai_recommendations` (Phase B bridge с `processed_at` idempotency, 2026-05-04), `ai_job_runs` (job_id nullable с 2026-05-17 — Conversation Loop пишет без ai_jobs), **`kb_chunks`** (RAG, 1536-dim vectors, RPC `match_kb_chunks`, 2026-05-17)

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
- [x] **Notify-WF Phase 1** production-ready (2026-05-15): WF4 нода `60_Notify_TG_Group` шлёт уведомления в TG group `AI&Incruises` при создании AI-task. continueOnFail=true. Bot `@incruises_ai_bot`, chat_id `-5110729354`. E2E smoke PASS (msg_id=27). Урок — env для контейнера нужен в `docker-compose.yml` `environment:` секции + `compose up -d`, не restart
- [x] **Phase C1 — Reactive AI assistant + RAG** production-ready (2026-05-17):
  - TG Conversation Inbound теперь делает полный AI-cycle inline (13 новых нод после `50_Touch_Contact`): fetch partner/settings/history → embed query → RAG retrieve → OpenAI → TG sendMessage → insert outbound (status=sent) → log AI run (cost) → update contact (включая `updated_at` bump для предотвращения Loop double-fire)
  - **Latency 3 мин → 3-5 сек** (cron polling убран для reactive)
  - WF9 переписан с placeholder на реальный TG dispatch (proactive путь, cron 1мин)
  - Conversation Loop патчена: `85_Log_AI_Job_Run` (cost tracking реально работает), `80_Update_Contact +last_outbound_at` (Followup Scheduler видит outbound)
  - **RAG full** (Phase C5 досрочно): pgvector + `kb_chunks` (20-я таблица) + RPC `match_kb_chunks` + WF14 KB Ingest (batch embed) + **2289 chunks** из 13 источников (5 MLM книг ~1.6K, 3 InCruises PDF, KB/Comp Plan/Business Rules/Answers, Google txt)
  - Prompt: state-aware length, anti-hallucination (нет в КБ→escalate no_kb), anti-question fatigue (q_and_a/presentation/objection без обязательного вопроса)
- [x] **Sandbox прогон #1 + 8 bug fixes** (2026-05-18):
  - InCruises FAQ ingested → 14 sources / **2314 chunks**
  - Bugs fixed in TG Conversation Inbound WF: media→escalation (нода 45-49), structured output logging в `ai_job_runs`, race Inbound↔Loop double-fire (`50_Touch_Contact` + `115_Update_Contact` bump `updated_at`), income hedge в промпте (обязательная оговорка при цитировании сумм), no-repeat-greeting, STOP intent case-insensitive с 13 синонимами, `95_If_Reply_OK` пропускает `action='stop'`, **history fetch unified на `tg_chat_id`** (был broken на контактах без `messenger_handle`)
  - Backfill 77+77 строк Сырыма и 13+10 Сайры под единый numeric identifier
  - Сайрин прогон 13/14 broken (history fetch) до фикса → ждёт повторного прогона на чистом стенде
- [x] **Sandbox прогон #2 Сайры** (2026-05-18 after-fix 08:08-09:34): 16 диалогов, conf 0.91, 0 эскалаций. Audit 2026-05-19 показал критический KB gap: 🔴 **Bronze rank hallucination**, 4 generic loops на SOP первых шагов, 7 generic на презентациях, 0/16 эскалаций при минимум 2 явных no_kb. Phase C1 НЕ готов к C2 — нужен KB gap fill
- [x] **Создана `obsidian-vault/docs/` — эталонная KB-папка** (2026-05-19). 5 файлов: README + InCruises Ranks (12 рангов + расчёты товарооборота) + Presentation Script (4 готовых 45-сек + структура SOP) + Questions for Saira (35 открытых Q) + 101RU_SIMPLE_COMPANY_PRESENTATION (официальный PDF InCruises конвертация). `Файлы с Google диска/` определён как сырьё (не эталон)
- [x] **101RU официальный источник интегрирован** (2026-05-19 вечер): 12 рангов InCruises подтверждены (Marketing Director → Royal Ambassador BoD), Bronze/Silver hallucination закрыта, удержание ранга = ежемесячный пересчёт, статусы Партнёр vs Член-Партнёр уточнены, расчёт товарооборота команды (Premium $500/$250, Classic $200/$100)
- [x] **6 официальных InCruises документов в `docs/`** (2026-05-20): 104RU Партнёрское Соглашение, 106RU Членское Соглашение, 109RU Обзор доходов, 214RU Руководство по доходам, 503RU Платёжное Соглашение (плюс 101RU из вчера). Audit: ~25/35 Q to Saira закрыты документами. STARTER $50/$50 подтверждён (Сайру не дёргать), DAB = $20-$50 (101RU $20-$150 = ошибка перевода). Новое в KB: Active vol requirement для MD+ ($200/30д..$2400/365д), ИКБ ≥65%, Quick Start $500
- [x] **🔴 Compliance fixes Приоритет 1 — промпт `80_Build_Prompt`** (2026-05-20 vечер): patch v1+v2 deployed через `scripts/patch_inbound_compliance_hard_rules.py` (idempotent). 6 правил живы в проде:
  - ст.17(в) запрет персональных прогнозов «ты заработаешь $X»
  - ст.17(в) hand-off для проекций «если приведу N — сколько»
  - ст.17(г) template-отказ на «сколько Сайра/Сырым зарабатывает» + цитата плана + hedge
  - ст.13 hand-off Membership closing (escalate=ready_to_pay)
  - Pass-through citation pattern «(по 109RU/214RU)»
  - 106RU geo-fence PL (⚠ требует миграцию `contacts.country`)
  - Smoke v1 5/5 PASS (после поправки vердикта по Q4), smoke v2 3/3 compliance-safe
- [x] **🔴 Compliance Приоритет 2 — audit лендинга** (2026-05-21):
  - `index.html` audit найдено: H1 «пока ты отдыхаешь» soft passive earnings, fictitious testimonials в reviews.html (особенно «команда выросла в 2 раза»)
  - `legal.html:43` спасает ст.13 явным disclosure «не является официальным сайтом InCruises»
  - 3 disclaimer ст.17 на месте (comparison + 2 footer)
- [x] **🔴 УТП-rewrite лендинга** (2026-05-21): compliance leverage заменил time leverage.
  - H1 «обученный правилам твоей MLM-компании», badge «Compliance-safe AI»
  - feature #4 заменён на «Compliance-safe общение», +2 строки compare table
  - fictitious reviews удалены (placeholder + CTA на форму)
  - FTP deploy через Python wrapper (escape-safe для спецсимволов в FTP_PASS)
- [x] **🔴 KB canonical /docs (Сырым жёстко 2026-05-21)**: KB строится ИСКЛЮЧИТЕЛЬНО из `obsidian-vault/docs/`. Reference/, Google диска/, .kb_extracted/ — НЕ источник
  - `kb_chunks` PURGE 2314 → 0, reingest из 8 /docs файлов → 242 chunks
  - 6 PDF (101/104/106/109/214/503RU) + InCruises Ranks.md + Presentation Script.md
  - 90% noise (MLM-книги корпус + битые PDF→txt extracts) удалены
  - Matching-бонус теперь в KB с конкретикой (100% / $200 личный / $600 командный)
  - Правило 3 веток в KB (40%-cap → floor=3 ноги для SMD+)
- [x] **🔴 Правило 3 веток** (Сырым 2026-05-21): для ЛЮБОЙ квалификации SMD+ — минимум 3 активные ветки (Правило 40% → 40+40+20=100%). Floor одинаковый для всех рангов, не градирован
- [x] **🔴 Cleanup репо** (2026-05-21): 101MB → 69MB (-32MB). 6 PDF в корне, 4 abandoned worktrees, .tmp, .kb_extracted, пустая sessions, 10 файлов archive
- [x] **🔴 Сайра TG reactivate** (2026-05-21): Сайра написала Stop 2026-05-20 (тестировала intent, не opt-out). Reset `ai_state=NULL`, `do_not_contact=false` + cleanup history. 4 turns smoke после: 3/4 PASS, 1 double-reply bug, 1 generic Matching (закрыто KB reingest)
- [ ] **🔴 Compliance Приоритет 2.1 — Consent flow audit** (отложено):
  - WF9 dispatch + Followup Scheduler + Conversation Loop на `consent_at IS NOT NULL` gate перед proactive AI-сообщением (ст.14-15)
  - ст.18 2-летний NDA — информационно (offboard scenario не реализуется сейчас)
- [ ] **🔴 Smoke verify KB reingest** (next session): Сырым/Сайра через TG: «Матчинг-бонус?», «Сколько веток?», «Первый ранг?». Если AI generic — patch промпт на «cite plan rates verbatim»
- [ ] **🔴 Reactivate-feature TG** (Phase C2 блокер): команда `/start` или partner-facing UI reactivate. Иначе любой тест STOP = выпадение из системы навсегда
- [ ] **🟡 Double-reply bug**: 2 inbound от same chat_id в <10 sec → 2 ответа. Debounce в WF или lock в RPC
- [ ] **🟡 Сайре 10 Q + 6 reviews** (опросник готов в `docs/Saira Interview Questions.md`): структура веток (квалификация на каждой), 7-12 касаний, цифры InCruises corp, личная история, 4 возражения, настоящие отзывы вместо fictitious
- [ ] **🟡 Миграция `contacts.country`** — `ALTER TABLE contacts ADD COLUMN country TEXT` для geo-fence PL по структуре, не только AI-text detection. Опциональный backfill из `leads.country` по lead_id
- [ ] **🟡 RAG improvements** (top_k 5→10, query expansion, anti-loop, escalation на self-detected no_kb)
- [ ] Phase C2 — Эскалация (1-2 сессии). Блокеры: reactivate-feature + double-reply
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
