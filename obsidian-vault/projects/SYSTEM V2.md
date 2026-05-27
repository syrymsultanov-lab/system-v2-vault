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
updated: 2026-05-27
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
- [x] **🔴 KB rewrite ЛИЧНО/КОМАНДНО/MIX format** (2026-05-22):
  - 11 Q&A блоков в `docs/InCruises Ranks.md` переписаны: ЛИЧНО (сам активируешь) / ЧЕРЕЗ КОМАНДУ (N веток, pkg cap) / MIX + recurring. Все упоминания «%» удалены, заменены на числа пакетов («не более 6 classic ИЛИ 2 premium на ветку»)
  - Q&A «Первый шаг после регистрации» добавлен (3 статуса)
  - `docs/Company Facts.md` создан — 4 Q&A корпоративных stats (193 страны, $350M DSN, 718K passengers, $500M+ бонусов, 4000+ Директоров, Mercy Ships)
  - Patch `80_Build_Prompt` v2 (`scripts/patch_inbound_format_packages.py`): rule «НИКОГДА не упоминай %», rule «ОБЯЗАТЕЛЬНО разделяй 3 пути», few-shot MD/SMD переписаны. 104RU compliance сохранён
  - KB reingest 242 → 257 chunks (Ranks 14→26, +Company Facts 3)
  - Smoke verify Сырым: AI теперь корректно разделяет ЛИЧНО/КОМАНДНО/MIX, проценты ушли
  - Commit `e0a1df0`, pushed → origin/main
- [x] **🔴 Reviews live + KB** (2026-05-23): 6 партнёров из официального журнала inCruises (Бактыгуль, Ботагоз, Сымбат, Надыра, Лаура, Мээрим). Webp конверсия PIL (smart top-crop, <100KB), `docs/Reviews.md` структурированный с compliance rules, `reviews.html` Grid 3-col RU/EN/KZ, KB reingest 257→267 chunks (+10 Reviews), FTP deploy 200 OK. Commit `122e473`
- [x] **🔴 Production launch gates** (2026-05-23): 4 техфикса перед real-traffic phase:
  - **Discovery: consent gate (ст.14-15) уже работал** — `claim_next_conversation` + `schedule_followups` фильтруют `WHERE ai_consent = true`, default `contacts.ai_consent=false`. Audit trigger `stamp_ai_consent_at` закрыл только timestamp consistency
  - Migration `contacts.country` + partial index (для geo-fence PL)
  - RPC `should_process_inbound_now(uuid)` — closes double-reply race (latest msg owns turn)
  - Trigger `reactivate_contact_on_inbound` (AFTER INS) — `/start`, `старт`, `реактив`, `reactivate`, `возобновить` → reset `ai_state=null`, `do_not_contact=false`
  - WF TG Inbound patch — 3 ноды: `42_Wait_Debounce(1.5s)` → `43_Debounce_Check(RPC)` → `44_If_Latest` (FALSE → workflow ends)
  - Smoke: consent_audit PASS, reactivate PASS. Commit `8978c6e`
- [x] **🔴 Launch v2 — Whisper + Interview + Templates + Channel split** (2026-05-23):
  - `scripts/transcribe_audio.py` (OpenAI Whisper API, .mp3/.m4a/.ogg → .md transcript, idempotent, 25MB limit + ffmpeg hint)
  - `obsidian-vault/projects/Saira Interview Plan.md` v2 — 7 блоков × 6-8 Q ≈ 50 Q, 40-60 мин (расширены возражения 4→10, новые блоки: идеальный кандидат + open Q for AI)
  - `obsidian-vault/projects/WhatsApp Outreach Template.md` v2 — 3 шаблона A/B/C с TG honesty (AI только в Telegram до WABA)
  - Migration `tasks.type` CHECK расширен + trigger `classify_task_by_messenger` (TG → `ai_lead_review`, WA/IG → `manual_outreach`, preserves explicit types)
  - Smoke classify PASS. Commit `f04b28d`
- [x] **🔴 Сайра interview записан** (2026-05-23 вечер): 8 m4a файлов (~58 MB / ~90 мин) по плану `Saira Interview Plan.md` v2 в `obsidian-vault/reference/interviews/raw/`. Транскрипция Block_2-8 запущена; Block_1 (8 MB) пропущен — ждёт ffmpeg downsample (winget Gyan.FFmpeg installed)
- [x] **🔴 TG bridge — open access для 160 партнёров** (2026-05-23 вечер):
  - Migration `tg_lead_to_contact_bridge`: trigger `create_contact_from_lead` (TG leads → contacts с form consent), RPC `link_tg_contact_by_handle` (atomic find-by-chat / link-by-handle / create-fresh), backfill 3 текущих кандидатов
  - WF patch `20_Find_Contact` GET → POST RPC (`patch_inbound_link_or_create_contact.py`)
  - **Open access mode:** любой TG user пишет бота → contact автосоздаётся с reactive consent → AI отвечает. Закрытие — одной строкой `ai_consent=FALSE` в RPC step 3, позже
- [x] **🎉 First real traffic** (2026-05-23 вечер): рассылка Сырыма → 13+ inbound/outbound пар за 10 мин с 2 партнёрами (527728826, 2078661150). Sample: «Как сделать бизнес в Инкрузес» → AI ответил из KB. Латентность 4-7 сек. 3 кандидата с лендинга (Салтанат @Saltavipstar, Батима, Салтанат @Saltavip). Первый трафик с 2026-04-30
- [x] **🔴 KB balanced retrieval — MLM-классика добавлена** (2026-05-24): Approach B (kind separation), не повтор Bronze hallucination 2026-05-19
  - Migration `kb_chunks_add_kind_and_balanced_retrieval`: `kind` column (canonical|mlm_context) + RPC `match_kb_chunks` v2 балансом 3 canonical + 2 mlm_context (default ratio 0.6)
  - 4 файла в `docs/raw/`: Don Failla (45-сек / 10 уроков) + Big Al Secrets + Big Al Leaders + Jim Rohn Vitamins. Ingest → 610 chunks. KB total **267 canonical + 610 mlm_context = 877**
  - WF14 redeploy (принимает kind), `push_kb_chunks_to_webhook.py` обновлён (list[dict])
  - `80_Build_Prompt` patch — KB source boundaries секция, маркеры `[KB-N | canonical|mlm-context]`, запрет цитировать суммы из mlm-context, запрет имён авторов (Don Failla / Big Al / Jim Rohn), 2 новых few-shot («где заканчивается структура», «это пирамида»)
  - RPC smoke 8 Qs: balanced работает, философские Qs → mlm-context, factual Qs → canonical
  - End-to-end smoke через TG = next session
- [x] **🔴 Bug fix — debounce IF condition** (2026-05-23 вечер): мой вчерашний patch_inbound_debounce.py имел 2 бага: (1) `leftValue: $json.body` вместо `$json` (RPC возвращает скалярный true), (2) script не делал upsert при re-run. AI 24h не отвечал. Fixed: upsert logic + leftValue `$json`. Memory `feedback_wf_patch_upsert_pattern` создать
- [x] **🔴 Whisper transcribe — refactor curl+retry** (2026-05-23 вечер): urllib SSL абортил на 8MB Windows → curl 8.19.0 + retry 3x + max-time 900. Plus OPENAI_API_KEY rotation (Сырым revoked old). Block_2-8 транскрибируются background, Block_1 ждёт ffmpeg
- [x] **🔴 Close open-access TG bridge → DB-only mode** (2026-05-25):
  - Discovery: 3 form-лида (Салтанат @Saltavipstar, Батима, @Saltavip) сидят с `dry_run` outbound — TG Bot API не пишет первым без numeric chat_id (handle/phone не годятся)
  - 3 «пробившихся» партнёра через open-access (`527728826`/`2078661150`/`1525700315`) идентифицированы (рассылка Сырыма 2026-05-23)
  - Migration `link_tg_contact_db_only_no_autocreate`: RPC Step 3 (auto-create) удалён → unknown TG users → empty SETOF → `25_Check_Contact` allowed=false → silence
  - Patch `35_Log_Unhandled` jsonBody: `events_log` не имеет `partner_id` (есть `entity_type/entity_id/actor_id`) → schema fix, audit trail работает
  - Smoke E2E (chat_id 888777666) PASS: no contact, no outbound, events_log row `tg_inbound_unknown_sender`
  - Commit `78a94a2`
- [x] **🔴 KB smoke #1 + pricing canonical** (2026-05-25 вечер):
  - Сырым прогнал 4 Qs (5243912117) — Don Failla балланс ✅, ЛИЧНО/КОМАНДНО/MIX держится, 0 эскалаций, авторов MLM не палит
  - Audit 13+ пар у `527728826`/`2078661150`/`1525700315`: 🔴 2 critical bugs — PREMIUM/CLASSIC pricing hallucinate split ($200+$300 вместо $250+$250), 50% RP rule пропущен (AI согласился на 2000+600 из 2600 круиза)
  - **Корень bug 1**: `101RU` таблица товарооборота читалась как разбивка цены. Прямого canonical pricing с активацией/monthly split в KB не было
  - **Корень bug 2**: 50% правило только в табличной ячейке `101RU` без prose, RAG пропустил
  - Сырым подтвердил canonical: PREMIUM $500=$250+$250, CLASSIC $200=$100+$100, STARTER $50/мес (нет активации, нет двух половин). RP 800/500, 350/200, 100/50. Free Membership $100 waiver при обороте 1й линии ≥$500/мес. 100% RP бронирование = MD+ (не «3 Leadership Bonuses» как в 101RU)
  - Создан `obsidian-vault/docs/Membership Pricing.md` — canonical override с pricing + RP + 50% rule + few-shot. `push_kb_chunks_to_webhook.py` обновлён. KB ingest 5 chunks → kb_chunks **882** (277 canonical + 610 mlm_context)
- [x] **🔴 Salt­анат Кенигесова дедуп-аудит + WF1 phone E.164** (2026-05-27):
  - Кейс: партнёр Сайры зарегилась через форму, AI не вышел. Discovery: 2 лида с одинаковым телефоном но разными форматами (`77080277396` vs `+77080277396`), 2 контакта auto-created, 2 outbound `dry_run` (handle ≠ chat_id, deep-link не реализован)
  - **WF1 fix**: `scripts/patch_wf1_phone_e164_dedup.py` — Normalize Input jsCode теперь strip non-digits + KZ 8→7 + `+` prepend. 5/5 phone форматов schлoпываются в `+77080277396`. Idempotent
  - Backfill: leads_to_fix=0 (после удаления `b84e8627` Сырымом вручную), contacts.phone=NULL у form-derived (trigger bug — `create_contact_from_lead` не копирует phone)
  - Discovery schema bug: contact Батимы получил `messenger_handle='+77089419616'` — phone в handle field из-за trigger
- [x] **🟢 Dashboard contact import — feature implementation** (2026-05-27): `openImport()` был stub, теперь полный CSV/VCF import
  - 3 итерации deploy: (v1) modal + parser + preview + dedup → (v2) editable preview rows + bulk-skip → (v3) Saira workflow для 5700 контактов
  - **v3 включает**: multi-filter chip row (`🚫 без имени/фамилии/тел/email/handle/тега`), checkbox на каждой строке, bulk-bar (`✓ Всё видимое · ↕ Инвертировать · ✕ Снять · 🗑 Удалить N`), chunked POST 500/batch с progress, chunked DELETE 500/batch, GET limit=20000
  - Parsers: CSV (RU+EN headers, quoted fields, `,;\t`), VCF (FN/N/TEL/EMAIL/X-TELEGRAM, params strip)
  - E.164 phone normalize (same logic как WF1)
  - "Нет фамилии" парсится из `name.split(/\s+/).length < 2` (schema contacts не имеет `last_name`)
  - Smoke parsers PASS (Node-локально), end-to-end Сырым PASS (4 CSV контакта Сайре в БД), 5700 VCF тест Сайры — next session
- [ ] **🔴 Smoke retest 3 pricing Qs**: PREMIUM split, 2000 RP/2600$, STARTER активация. Если AI всё ещё путает — patch `80_Build_Prompt` чтобы поднять Membership Pricing в few-shot
- [ ] **🔴 Saira VCF import smoke** (5700 контактов): Сайра экспортирует с iPhone/Android → загружает → проверяет фильтры → выборочно удаляет. Если рендер 5700 лагает — добавить virtualization
- [ ] **🔴 Form → TG deep-link bridge (вариант C)**: критично для всех form-лидов в `dry_run` (Салтанат×2, Батима + будущие). После submit → redirect `t.me/incruises_ai_bot?start=<lead_uuid>` → bot ловит `/start`, UPDATE contact `tg_chat_id+handle` → WF9 dispatch
- [ ] **🟡 Templates + Training seed** (0 rows в обеих таблицах, UI stubs). Ждёт диктовки от Сырыма ИЛИ pull из vault (`WhatsApp Outreach Template.md` есть)
- [ ] **🟡 Trigger `create_contact_from_lead` bugs**: не копирует phone; phone Батимы попал в messenger_handle
- [ ] **🔴 Saira interview processing** (next session): дождаться завершения транскрипции Block_2-8 (background task `bbo7vnowc`), ffmpeg-fix Block_1, разобрать по 7 блокам → 5 новых doc файлов (About Saira, Ideal Candidate, Saira AI Rules + дополнить InCruises Ranks/Presentation Script/Company Facts), patch few-shot, KB reingest
- [ ] **🟡 Audit реальных диалогов** (next session): 13+ пар с 527728826/2078661150 + новые с рассылки. Читать полные ответы AI, найти косяки/паттерны для patch few-shot
- [ ] **🟡 Compliance redact on ingest** (если live-smoke покажет нарушение): regex по «$N млн/тыс/dollars» для mlm-context, либо metadata flag `contains_income_claim` с фильтром в RPC
- [ ] **🟡 RAG improvements** (top_k 5→10, query expansion, anti-loop, escalation на self-detected no_kb)
- [ ] **🟡 Form → TG bot bridge deep-link** (вариант C, было пропущено): сейчас полу-bridge есть через handle-link. Полный путь: после submit → redirect `t.me/incruises_ai_bot?start=<uuid>` → бот по UUID lookup lead → contact UPDATE handle+chat_id+attribution к ref-партнёру. Сейчас все random → Сайрин partner_id default
- [ ] **🟡 Schema-related:** trigger `create_contact_from_lead` только TG. Если WhatsApp/Insta — добавить позже
- [ ] **🟡 Dashboard visual separation**: filter `task.type='manual_outreach'` vs `ai_lead_review` (UI работа)
- [ ] **🟡 Schema drift cleanup** (CLAUDE.md vs DB): `ai_job_runs.cost_usd` отсутствует (нет AI Budget Watchdog source), `leads.full_name` не существует, `contacts.ai_consent_at` (не `consent_at` как в memories)
- [ ] Phase C2 — Эскалация (1-2 сессии). Блокеры теперь только Сайра interview (для AI voice quality)
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
