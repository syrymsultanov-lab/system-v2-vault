---
project: system-v2
component: ai-agent
type: questionnaire-answers
source: AI Agent Questionnaire.md
created: 2026-05-16
status: complete
---

# AI Agent — Ответы Сырыма на Questionnaire

> Источник вопросов: [[AI Agent Questionnaire]] (created 2026-04-25)
> Закрыто полностью 2026-05-16. Формат: A1..R3 + ответ. «(R)» = accept «Моей рекомендации».

---

## A. Compliance
- **A1** **Снять правило 9 → полный автомат.** Партнёр одобряет один раз старт диалога с лидом → AI шлёт автономно. Эскалация на партнёра только при триггерах (негатив/готов оплатить/не знает ответа)
- **A2** **Gate-обучение оставить (правило 9b).** Партнёр обязан пройти модули перед активацией AI. Модуль «редактирование черновиков» → переименовать в «как AI эскалирует тебе диалог»
- **A3** **«InCruises» в личной переписке AI с лидом (после согласия) — можно прямо.** Compliance-обход не требуется

## B. Identity
- **B1** **(b)** «Я помощница Сайры» (ассистент)
- **B2** Один общий стиль для всех партнёров (НЕ имитация конкретного)
- **B3** Имя бота: **«Ассистент»**

## C. Тон/язык
- **C1** **Формальный «вы»** (НЕ дефолт «ты»; отклонение от рекомендации Questionnaire)
- **C2** Короткие 1-2 предложения (R)
- **C3** Автодетект языка по первому ответу + fallback RU (R)

## D. Каналы
- **D1** WA первым, TG fallback при недоставке через 24ч (R)
- **D2** Только WA при отсутствии TG-username (TG bot не может lookup по номеру через API)
- **D3** **Адаптивно** — AI решает интервал по контексту и sentiment
- **D4** Да, quiet hours по `contacts.timezone`, fallback Almaty/UTC+5

## E. Эскалация
- **E1** JSON-output `is_negative` + safety net ключевые слова (R)
- **E2** Сразу честно сказать «не знаю» + эскалация (без 3-х попыток)
- **E3** JSON `intent: ready_to_pay` (R)
- **E4** AI пишет «секунду, передаю Сайре» и ждёт (прозрачная handoff)
- **E5** Да, кнопка «Передать обратно AI» в дашборде (R)

## F. База знаний
- **F1** Templates на старте, RAG позже (Phase C5) (R)
- **F2** В БЗ: FAQ InCruises + Compensation Plan + Объекции с ответами + Истории успеха/кейсы
- **F3** Tier1 (системные) — Сырым через vault MD-файлы; Tier2 (партнёрские) — Сайра через UI

## G. Сценарии
- **G1** Подтверждаю 6 этапов: Greeting → Qualification → Presentation → Q&A → Objection → Close
- **G2** Готовых текстов нет, пишем с нуля по промпт-каркасу
- **G3** Все 8 объекций из Questionnaire: нет денег, нет времени, пирамида/MLM, не верю, советоваться с супругом, подумаю, не подхожу, слишком сложно
- **G4** Гибрид — greet/present/close = шаблон, объекции/Q&A = LLM (R)

## H. UX согласия
- **H1** Обе опции: кнопка «🤖 Запустить AI» на карточке + bulk-чекбокс при импорте
- **H2** Можно отложить старт (поле `scheduled_at`)
- **H3** Да, отмена возможна; AI замолкает, уже отправленные сообщения остаются
- **H4** **Contact остаётся contact, AI работает с `contacts` напрямую** + флаги `ai_consent`/`ai_consent_at`. Сохраняет правило 1 (Contact ≠ Lead). Lead рождается только когда лид сам пришёл через лендинг

## I. Дашборд
- **I1** Все 4 канала: лента «Активность AI» + TG личный партнёру + Email digest 1р/день + Browser Push (PWA)
- **I2** Полная карточка: этап + last message preview + sentiment + кнопка «Открыть переписку»
- **I3** AI пауза, партнёр может вернуть (R) — согласуется с E5
- **I4** Supabase Realtime (R)

## J. Лимиты
- **J1** **Глобальный бюджет проекта** (не per-lead, не per-partner)
- **J2** AI стоп + уведомление Сырыму при превышении (admin alert)
- **J3** Сырым (центральный кошелёк, один OpenAI key)
- **J4** **<$50/мес (tight)** — критично определяет архитектуру: gpt-4.1-mini + prompt caching + structured output обязательны

## K. Edge cases
- **K1** Картинка/голос/файл → эскалация партнёру (Whisper/vision ломает бюджет J4)
- **K2** Длинное сообщение → summarize вызовом (2 LLM call: сжать + ответить)
- **K3** STOP/НЕ ПИШИТЕ → AI навсегда тихий, `do_not_contact=true`, notify партнёра (R)
- **K4** 3 follow-up: +24ч, +72ч, +7д. Потом cold (R)
- **K5** AI не уверен → честно «уточню» + эскалация (без retry на дорогой модели)

## L. Закрытие
- **L1** **Добавить колонку `partners.referral_url`** (миграция)
- **L2** Партнёр вручную помечает «оплатил» в дашборде (нет webhook от InCruises)
- **L3** AI помогает с регистрацией — отвечает на вопросы после отправки ссылки

## M. Каналы инфра
- **M1** WABA НЕ подключена. Отдельная задача (Meta verification + templates approval = серьёзный onboarding)
- **M2** Один общий бот системы (R) — `@SairaAssistantBot` или подобное, `partner_id` через deep-link
- **M3** **TBD** — личный vs бизнес-номер Сайры решить позже

## N. LLM tech
- **N1** gpt-4.1-mini как default + DeepSeek-chat backup при rate-limit (R)
- **N2** Prompt cache обязателен (R) — 50% off на повтор системного промпта, критично для J4
- **N3** Structured output JSON всегда (R) — `{action, text, intent, escalate, sentiment, confidence}`
- **N4** Temperature 0.3 (R)
- **N5** Логирование каждого LLM-call в `ai_job_runs` (R) — аудит + budget tracking

## O. Тестирование
- **O1** Тестовые контакты: мой номер + номер Сайры (минимум фрикции)
- **O2** Sandbox `dry_run` флаг на этап разработки (R) — AI обрабатывает, `outbound_messages.status='dry_run'`, реально не шлём
- **O3** Сырым + Сайра ревьюят 20-30 диалогов вручную перед запуском на живых

## P. Скорость
- **P1** Задержка 30-60 сек между типингом и отправкой (R) — имитация человека
- **P2** Quiet hours: AI замолкает 22:00–08:00 локального времени лида (R), согласуется с D4

## Q. Vault архив
- **Q1** Переписывать файлы напрямую (git log = история)
- **Q2** WF6 удалить, создать новый WF «AI Conversation Loop» (старый WF6 проектировался под полуавтомат-модель)

## R. Future
- **R1** Voice (TTS, возможно voice clone Сайры) — да, Phase C6 по roadmap
- **R2** Один универсальный агент (R) — не multi-agent
- **R3** Минимальные настройки per-partner: имя, язык, тон (через `partner_settings.ai_config` JSONB)

---

## Критические импликации (что меняется в системе)

### Новые миграции БД
1. `partners.referral_url TEXT` — L1
2. `contacts.ai_consent BOOLEAN DEFAULT false` — H1/H4
3. `contacts.ai_consent_at TIMESTAMPTZ` — H4
4. `contacts.ai_scheduled_at TIMESTAMPTZ` — H2 (отложенный старт)
5. `contacts.ai_state TEXT` — этап диалога (greeting/qualification/presentation/q_and_a/objection/close/paused/escalated) — G1
6. `contacts.do_not_contact BOOLEAN DEFAULT false` — K3
7. `contacts.timezone TEXT` (если ещё нет) — D4
8. `partner_settings.ai_config JSONB` — R3 (имя/язык/тон override)
9. `outbound_messages.status` расширить значением `'dry_run'` — O2 (или отдельная колонка)

### Удаления / реструктуризация
- WF6 удалить полностью (Q2)
- Старая модель «AI пишет черновик → партнёр редактирует» — выпиливаем из Business Rules (правило 9) — A1
- Обучающий модуль «редактирование черновиков» → переименовать «как AI эскалирует тебе диалог» — A2

### Новые компоненты
- WF «AI Conversation Loop» — основной conversation agent
- WF «Outbound Followup Scheduler» — K4 (+24/+72/+7д cron)
- WF «AI Budget Watchdog» — J2 (стоп + alert при превышении)
- Dashboard вкладка «Активность AI» — I1/I2
- TG личный bot для уведомлений партнёру (отделить от group bot 60_Notify_TG_Group) — I1
- Email digest backend (Resend/SMTP) — I1
- Browser Push (PWA subscription) — I1
- Промпт-каркас в `obsidian-vault/prompts/AI System Prompt.md` — G2/G4

### Блокеры C1 (text Q&A MVP)
1. **Канал**: WABA не подключена + номер Сайры TBD → **C1 MVP стартует на TG only** (потом WABA на C2/C3)
2. **KB-контент**: InCruises FAQ/Comp Plan/объекции тексты нужно собрать — сейчас только `InCruises Knowledge Base.md` stub
3. **TG bot** — проверить существование (`.env` может содержать токен)
4. **Бюджет $<50** — нужна конкретная оценка токенов на 250 партнёров × N лидов (мониторим в `ai_job_runs`)

### Открытые вопросы (не блокируют C1)
- M3 номер WhatsApp Сайры (блокирует WABA задачу, не C1)
- L2 нет webhook InCruises — partner-manual только на старте, future-OK
