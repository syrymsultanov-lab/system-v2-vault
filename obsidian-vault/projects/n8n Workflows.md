---
project: system-v2
component: n8n
status: phase-b-production
hosting: hostinger-vps
updated: 2026-05-16
---

# n8n Workflows

## Статус: Phase A/B production (2026-05-04). Phase C placeholders inactive

## Хостинг
- Hostinger VPS, docker-compose в `/docker/n8n/`
- URL: https://n8n.sairateam.com
- Naming: `NN_node_name` для всех нод (memory `feedback_n8n_node_naming`)
- Секреты: `.env` VPS + `environment:` секция `docker-compose.yml` + `compose up -d` (memory `reference_n8n_docker_env_proxy`)

## Реальный inventory (сверено 2026-05-16, после WF2 cleanup)

### Active (5)

| WF | id | Назначение | Триггер |
|----|----|-----------|---------|
| **WF1** Lead Intake | `BLf7zJhSslBPBxwN` | webhook `/system-v2/lead-intake`: Normalize → Find Existing dedup → Insert Lead → lead_events INSERT → events_log → respond `{ok:true}`. Триггер `create_qualification_job` сам кладёт ai_jobs queued | webhook (landing app.js POST) |
| **WF3** AI Lead Qualification | `0Jcp6O31CJhMdpex` | `claim_next_ai_job` RPC → OpenAI score+temp+next_action+summary → leads.status=qualified+score → `ai_recommendations` row → ai_jobs.succeeded. Mark Failed единая branch для 5 нод | cron 2 мин |
| **WF4** AI Recommendation → Task | `MYYNmEnQ6mVI1dih` | fetch `ai_recommendations[processed_at=null]` → tasks INSERT → mark processed → events_log (actor='system') → `60_Notify_TG_Group` (continueOnFail=true) | cron 2 мин |
| **WF9** Outbound Message Dispatcher | `I6m8cSqkX1M3zpyC` | fetch `outbound_messages[status='approved']` → отправка по каналу → status='sent' | cron / event |
| **WF13** Stuck AI Jobs Watchdog | `SBzh4cIzNKTSz25s` | `reset_stuck_ai_jobs(10)` — running > 10 мин → failed | cron 5 мин |

### Inactive / placeholders (3)

| WF | id | Статус |
|----|----|--------|
| **WF5** Inbound Message Capture | `dFDgavZyMIQgYlKO` | Placeholder для Phase C C1 (text Q&A inbound). webhookId UUID assigned 2026-05-05 |
| **WF6** AI Reply Draft | `NssZBVrm2uvi8DzH` | Placeholder для Phase C C1 (n8n AI Agent node + Postgres memory). Перепишется |
| **WF12** AI Error & Retry Handler | `z08w5OTjaVEfkSsl` | Placeholder. Текущая Mark Failed branch в WF3 покрывает базовый случай |

### Удалённые / несуществующие
- **WF2** Lead Dedup & Normalize — удалён 2026-05-16 (логика переехала в WF1 Plan B 2026-05-05). JSON-бэкап в репо `SYSTEM_V2_n8n_workflows_JSON/workflows/WF2_Lead_Dedup_Normalize.json`
- **WF7** — конвертация lead→contact удалена 2026-05-06 (memory `project_lead_contact_directionality`)
- **WF8/10/11/14/15** — упомянуты в планах (AI Agent.md, старый SYSTEM V2.md), но не созданы

## Phase A/B production pipeline (диаграмма)

```
landing form (app.js POST)
  ↓
WF1 webhook /system-v2/lead-intake
  ↓
Normalize → Find Existing → If dup ? Use Existing : Insert Lead
  ↓
Extract Lead Id → lead_events INSERT → events_log INSERT → respond {ok:true}
  ↓ (триггер create_qualification_job)
ai_jobs (status='queued')
  ↓
WF3 cron 2 мин: claim_next_ai_job → OpenAI → leads.status=qualified+score
  ↓
ai_recommendations (processed_at=null)
  ↓
WF4 cron 2 мин: tasks INSERT → mark processed → events_log → TG notify
```

WF13 параллельно сбрасывает зависшие running > 10 мин в failed.

## Phase C TODO (не имплементировано)

| Фаза | WF | Скоп |
|------|----|------|
| C1 | WF5/WF6 переписать | n8n AI Agent node + Postgres memory + KB tool. Канал TG (Bot API) |
| C2 | Tools в WF6 | `notify_partner(reason)`, `schedule_meeting(slot)`. LLM-judge на нестандартность |
| C3 | Новый WF (Outbound Selection) | cron → rank `contacts` → top 3-5 → `ai_recommendations(type='outbound_targets')` |
| C4 | WF9 расширить | promo template + UTM. Channels: TG / WA / SMS |
| C5 | Новый WF (KB ingestion) | pgvector + chunking |
| C6 | Voice bridge | Vapi/Retell webhook → n8n → tools |

## Принципы

- Каждый workflow начинается событием (webhook / cron / trigger)
- Каждый workflow заканчивается логом (events_log актор `system`)
- Error branch на каждой критической ноде → ai_jobs.result.error JSON
- Все секреты через `$env.X` (НЕ credentials), переносимый JSON (memory `feedback_n8n_secrets_via_env`)
- nested `{}` в jsonBody → literal template + `{{ JSON.stringify(...) }}` (memory `feedback_n8n_jsonbody_expression`)

## Деплой

- Python: `scripts/upsert_wf.py WFN` (DEACT → PUT → ACTIVE)
- JSON источник: `SYSTEM_V2_n8n_workflows_JSON/workflows/`
- n8n REST quirk: после PUT webhook node остаётся `webhookId=null` → 404. Назначать UUID перед PUT (memory `reference_n8n_webhook_id_quirk`)

## Связи
- [[AI Agent]] — Phase C scope
- [[SYSTEM V2]] — overall status
- memory: `project_phase_b_chain`, `feedback_n8n_node_naming`, `feedback_n8n_jsonbody_expression`, `feedback_n8n_secrets_via_env`, `reference_n8n_docker_env_proxy`, `reference_n8n_webhook_id_quirk`, `reference_n8n_vps_layout`, `feedback_n8n_json_after_http_node`, `feedback_n8n_deploy_no_inline_env`
