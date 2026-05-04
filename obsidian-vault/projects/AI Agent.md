---
project: system-v2
component: ai-agent
status: phase-b-done, phase-c-planning
updated: 2026-05-04
---

# AI Agent

## Статус

- **Phase A** (qualifier WF3) — production 2026-05-03
- **Phase B** (qualifier → ai_recommendations → WF4 → task) — production 2026-05-04
- **Phase C** (outreach + conversational + voice) — planning 2026-05-04, выполнение 12-18 сессий

## Vision (от Сырыма, 2026-05-04)

Целевая система — не только intake. Это **полный outbound + conversational агент**:

1. **Voice agent (созвон)** — звонит лидам / контактам партнёра
2. **Q&A агент** — отвечает на возражения и вопросы (текст+голос)
3. **Эскалация** — при нестандартной ситуации назначает встречу + предупреждает партнёра
4. **Outbound ranking** — ранжирует `contacts` партнёра, выбирает 3-5, **берёт approval**, потом отправляет промо + ссылку на лендинг
5. **Outbound dispatch** — реальная отправка по каналу (TG/WA/SMS)

Текущая Phase A/B — **только intake side**. Phase C добавляет outreach.

## 5 компонентов → tech stack

| # | Компонент | Stack |
|---|---|---|
| 1 | Voice | Vapi / Retell AI / Bland / ElevenLabs Conversational / custom (Twilio + OpenAI Realtime). RU/KZ TTS критичен. ~$0.05-0.15/мин |
| 2 | Q&A с памятью | n8n AI Agent node (`n8n-nodes-langchain.agent`) + Postgres memory + RAG tool (Vector Store) |
| 3 | Эскалация | Tools `notify_partner(reason)`, `schedule_meeting(slot)` (Google Calendar). LLM-judge на «нестандартность» |
| 4 | Ranking + approval | Outbound Selection Agent (cron) → LLM rank `contacts` → top 3-5 → `ai_recommendations(type='outbound_targets')` → партнёр approve в dashboard |
| 5 | Dispatch | `outbound_messages` + WF9 (existing). Каналы: TG / WA Business API / SMS |

## MVP rollout (~12-18 сессий)

| Фаза | Скоп | Сессий |
|---|---|---|
| **C1** Text-only Q&A | AI Agent node + Postgres memory + KB-stub. WF6 переписать на Agent. Канал: TG | 2-3 |
| **C2** Эскалация | Tools `notify_partner` + `schedule_meeting`. LLM-judge | 1-2 |
| **C3** Outbound Selection | Ranking agent + dashboard approval UI + миграция `ai_recommendations.status` | 2-3 |
| **C4** Outbound dispatch | Approved rec → outbound_messages → WF9 sends. Промо-шаблон + UTM | 1-2 |
| **C5** RAG | pgvector + KB ingestion (WF10) + retrieval tool | 2-3 |
| **C6** Voice | Voice platform (Vapi/Retell) + bridge в n8n. RU/KZ TTS validation | 3-5 |

Принцип: text → escalation → outbound → RAG → voice. Voice последним (5-10x complexity).

## Gaps

**DB-схема:**
- `calls` — нет
- `conversations` — нет (или расширить `ai_job_runs`)
- `knowledge_sources`, `knowledge_chunks` (RAG vectorstore) — placeholder в WF8/10/11, не созданы
- `ai_recommendations.status` — нет (нужно для approval flow)
- `recommendation_type` варианты — будут: `outbound_targets`, `reply_draft`, `meeting_proposed`, `escalation`

**Инфра:**
- Voice platform не выбрана
- pgvector extension не enabled (доступен в Supabase)
- WA Business API не настроен (`partner_integrations.provider='wa'` placeholder)
- KB-источник (InCruises product / comp plan / FAQ) — формат и локация неизвестны

**Compliance:**
- Согласие контактов на AI outreach — кто валидирует?
- Identity disclosure: AI / Сайра / ассистент?
- Recording disclosure для звонков (TCPA + RU/KZ телеком)
- InCruises policy enforcement в промпте + KB

## Открытые вопросы (блокируют C1)

1. **Канал MVP** — TG или WA? Рекомендую TG (Bot API без onboarding)
2. **KB источник** — где контент? PDF / Notion / голос Сайры?
3. **Identity** — «AI-ассистент Сайры» / «Сайра» (deception risk) / прозрачно «AI-bot»?
4. **Языки** — RU/KZ/EN mix?
5. **Consent tracking** — партнёрский self-attestation на onboarding?
6. **Бюджет** — voice $0.05-0.15/мин, LLM $0.001-0.01/reply. Рамки?

## Роль AI (старая, актуальна)

- **Исполнитель**, не архитектор
- Все действия логируются в `events_log`
- Не пишет без разрешения партнёра
- Не гарантирует доход (InCruises policy)

## Текущие правила работы (полуавтомат, 2026-04-18)

«🤖 Передать AI-агенту» — flow с человеческим надзором:
1. Партнёр жмёт → INSERT `ai_jobs` job_type='draft'
2. n8n LLM формирует **черновик** по шаблону + контексту лида
3. Черновик возвращается партнёру → **редактирует и подтверждает**
4. После approval — n8n отправляет через WABA/TG → запись в `lead_messages`
5. Ответ лида → следующий раунд черновика → снова approval
6. Статус new → contacted → qualified/rejected меняется автоматом, отправки — только с approval

**Почему полуавтомат:** WABA банит за нарушения Meta policy + LLM может пообещать гарантированный доход → нарушение InCruises. Полный автомат — отдельная зрелость.

## Phase C изменит правила

После C1-C2: AI Agent ведёт Q&A автономно, эскалирует на партнёра только нестандартное. После C3-C4: outbound тоже автоматизирован, но с approval-gate на rank.

## Связи

- [[n8n Workflows]]
- [[SYSTEM V2]]
- [[Dashboard]]
- [[InCruises Compensation Plan]] (для KB)
- memory: `project_ai_agent_vision.md`, `project_phase_b_chain.md`
