---
project: system-v2
component: ai-agent
status: phase-c1-spec
updated: 2026-05-16
---

# AI Agent

## Статус

- **Phase A** (qualifier WF3) — production 2026-05-03
- **Phase B** (qualifier → ai_recommendations → WF4 → task) — production 2026-05-04
- **Phase C** (outbound + conversational + voice) — spec finalized 2026-05-16 ([[AI Agent Answers]])
- **C1 (text Q&A)** — implementation queued, 2-3 сессии

## Vision

Phase A/B = только intake (lead форма → qualifier → task для партнёра). Phase C добавляет **полный outbound + conversational агент**:

1. **Voice agent (созвон)** — звонит лидам/контактам (C6)
2. **Q&A агент** — отвечает на возражения и вопросы текстом (C1) и голосом (C6)
3. **Эскалация** — нестандартная ситуация → notify партнёра + meeting slot (C2)
4. **Outbound ranking** — ранжирует `contacts`, выбирает 3-5, approval партнёра, выкатывает промо (C3)
5. **Outbound dispatch** — реальная отправка по каналу (C4)

## C1 Specification (text Q&A MVP)

### Identity и тон ([[AI Agent Answers]] B, C)
- Бот: **«Ассистент»** / «помощница Сайры». Не имитирует партнёра
- Тон: **формальный «вы»**, короткие сообщения 1-2 предложения
- Языки: автодетект (RU/EN/KZ) по первому ответу лида, fallback RU

### Канал
- **TG only на MVP** (WABA не подключена → задача в Phase C параллельно). Новый conversation bot (не `60_Notify_TG_Group`)
- Deep-link `?start=partner_<id>_contact_<id>` для привязки

### Flow
1. Партнёр в дашборде жмёт «🤖 Запустить AI» на карточке контакта или bulk при импорте → `contacts.ai_consent=true, ai_consent_at=now()`
2. Опционально `ai_scheduled_at` (старт через N дней)
3. WF «AI Conversation Loop» (cron 1 мин) забирает контакты с `ai_consent=true AND (ai_scheduled_at IS NULL OR ai_scheduled_at <= now()) AND NOT do_not_contact AND not_in_quiet_hours`
4. Этапы (`contacts.ai_state`): `greeting` → `qualification` → `presentation` → `q_and_a` → `objection` → `close` → (`paused` | `escalated`)
5. Lead model: **контакт остаётся контактом**. AI работает с `contacts` напрямую через `ai_state`. Lead создаётся только если контакт сам пришёл через лендинг (Phase A path)

### LLM tech ([[AI Agent Answers]] N)
- Модель: `gpt-4.1-mini`, prompt caching обязателен (50% off на повтор системного промпта)
- Structured output JSON: `{action, text, intent, escalate, sentiment, confidence, next_state}`
- Temperature `0.3`
- DeepSeek-chat backup при rate-limit (отложен до первого инцидента)
- Каждый call → `ai_job_runs` (audit + cost tracking)

### Эскалация ([[AI Agent Answers]] E)
- Триггеры: `is_negative=true` (JSON + safety keywords), `intent=ready_to_pay`, `confidence<threshold`, вопрос вне БЗ, медиа от лида
- AI отвечает «секунду, передаю Сайре» и **ждёт** (не замолкает) → notify партнёру
- Партнёр пишет вручную → может вернуть AI в работу кнопкой
- При re-activate AI продолжает с того же `ai_state`

### Cool-down и follow-up ([[AI Agent Answers]] D3, K4)
- Между диалоговыми ответами AI: задержка 30-60 сек (имитация человека, P1)
- Если лид молчит: 3 follow-up — `+24ч`, `+72ч`, `+7д`, потом cold (`ai_state='cold'`)
- Между follow-up'ами AI решает интервал адаптивно по sentiment

### Edge cases ([[AI Agent Answers]] K)
- Картинка/голос/файл → эскалация (без Whisper/vision на MVP — бюджет $<50/мес)
- Длинное сообщение (>1000 симв) → summarize call → ответ (2 LLM call)
- STOP/НЕ ПИШИТЕ → `do_not_contact=true`, hard stop, notify
- Low confidence → честно «уточню у Сайры» + эскалация

### KB (templates на старте)
- Контент: FAQ InCruises, Comp Plan упрощённый, объекции (нет денег / нет времени / пирамида / не верю / советоваться с супругом / подумаю / не подхожу / слишком сложно) + истории успеха
- Tier1 (системные) — Сырым через vault MD-файлы → seed в `templates`
- Tier2 (партнёрские) — Сайра через UI (Phase C5)
- RAG (pgvector) — отложен до C5

### Бюджет
- **<$50/мес** на старте. Реализуемо через mini + cache + JSON output + media эскалация
- Hard stop + alert Сырыму при превышении (см. Business Rules 14)
- Reviewable после первых 20-30 диалогов

### Dashboard UI ([[AI Agent Answers]] I)
- Вкладка «Активность AI» (лента событий)
- Карточка AI-контакта: `ai_state`, last message preview, sentiment, кнопка «Открыть переписку», кнопка «Забрать у AI» (пауза)
- Realtime через Supabase Realtime
- Notify каналы: лента + TG лично партнёру + Email digest + Browser Push (PWA)

### Testing ([[AI Agent Answers]] O)
- Sandbox `dry_run` флаг — AI работает, `outbound_messages.status='dry_run'`, реально не шлёт
- Live тестовые контакты: мой номер + Сайры
- Pre-launch: 20-30 диалогов ревью (Сырым + Сайра)

## Required DB migrations

| # | Table.column | Type | Source |
|---|---|---|---|
| 1 | `partners.referral_url` | TEXT | L1 |
| 2 | `contacts.ai_consent` | BOOLEAN DEFAULT false | H1/H4 |
| 3 | `contacts.ai_consent_at` | TIMESTAMPTZ | H4 |
| 4 | `contacts.ai_scheduled_at` | TIMESTAMPTZ | H2 |
| 5 | `contacts.ai_state` | TEXT | G1 |
| 6 | `contacts.do_not_contact` | BOOLEAN DEFAULT false | K3 |
| 7 | `contacts.timezone` | TEXT (если ещё нет — проверить) | D4 |
| 8 | `partner_settings.ai_config` | JSONB | R3 (имя/язык/тон override) |
| 9 | `outbound_messages.status` | расширить значением `'dry_run'` | O2 |

## n8n workflows changes

- **Удалить** WF6 (старая черновик-модель, [[AI Agent Answers]] Q2)
- **Создать** WF «AI Conversation Loop» (cron 1 мин, replaces WF6)
- **Создать** WF «Outbound Followup Scheduler» (cron 1ч, K4 follow-up интервалы)
- **Создать** WF «AI Budget Watchdog» (cron daily, J2)
- **Создать** WF «TG Conversation Inbound» (webhook от TG Bot API на входящие)
- Сохранить WF3/WF4/WF13 (intake side, не трогаем)
- Сохранить `60_Notify_TG_Group` (group notify, переиспользуем для эскалаций)

## Roadmap C1-C6

| Фаза | Скоп | Сессий |
|---|---|---|
| **C1** Text Q&A на TG | DB migration + WF AI Conversation Loop + AI System Prompt + TG bot setup + sandbox testing | 2-3 |
| **C2** Эскалация | Tools `notify_partner` + `schedule_meeting` (Google Calendar MCP). Email digest backend | 1-2 |
| **C3** Outbound Selection | Ranking agent + dashboard approval UI + `ai_recommendations.status` | 2-3 |
| **C4** Outbound dispatch | Approved rec → outbound_messages → WF9. Промо-шаблон + UTM | 1-2 |
| **C5** RAG + KB UI | pgvector + ingestion + KB editor для Сайры | 2-3 |
| **C6** Voice | Vapi/Retell bridge. RU/KZ TTS validation | 3-5 |
| **+ Параллельно** | WABA подключение (Meta verification, templates), Browser Push (PWA), номер Сайры решение (M3) | как окно |

Принцип: text → escalation → outbound → RAG → voice. Voice последним (5-10x complexity).

## Открытые вопросы (не блокируют C1)

- **M3** — номер WhatsApp Сайры (бизнес vs личный). Блокирует WABA-задачу, не C1
- **L2** — InCruises webhook на оплату? На MVP partner-manual mark в дашборде
- **Бюджет review** — после 20-30 диалогов в sandbox можно пересмотреть J4 (см. memory `project_ai_agent_vision`)

## Что НЕ покрыто Phase C (future Phase D?)

- Multi-agent specialization (R2 = единый агент)
- Per-partner кастомный system prompt (R3 = только имя/язык/тон override)
- A/B тестирование промптов
- KPI dashboard для AI performance (response time, escalation rate, conversion)

## Связи

- [[AI Agent Answers]] — full questionnaire с решениями
- [[Business Rules]] — rules 9-14, 16-17 derived from here
- [[n8n Workflows]]
- [[SYSTEM V2]]
- [[Dashboard]]
- [[InCruises Knowledge Base]] — KB seed для templates
- [[InCruises Compensation Plan]] — Comp Plan content
- memory: `project_ai_agent_vision.md`, `project_phase_b_chain.md`
