---
project: system-v2
status: infra-ready-impl-pending
created: 2026-05-06
updated: 2026-05-06
---

# Notify-WF — дизайн (parked после setup)

Уведомления партнёру когда AI создал task / пришёл новый лид / другое событие.

## Статус
**Parked 2026-05-06 после setup'а инфраструктуры.** Bot и группа работают, тестовое сообщение отправлено успешно. Имплементация WF4-хука и Email digest — следующая сессия.

## Принятые решения

### Архитектура
- **Trigger pattern:** WF4 hook (синхронный fan-out после `30_Insert_Task`)
- **Каналы MVP:**
  - **TG group** — вся команда видит уведомления о task'ах в реалтайме
  - **Email digest** — раз в неделю Сайре на `saira.sultanova@gmail.com` (отдельный cron WF15, **email backend не выбран**)
- **Quiet hours игнорируем в MVP** (target сам мьютит на устройстве)
- **Events MVP:** только `notify_task` (`notify_new_lead` потом)

### Bot
- Создан 2026-05-06: `@incruises_ai_bot`, имя "InCruises AI Agent"
- Token revoked + перевыдан 2026-05-06 (первый засветился в чате)
- Текущий токен в локальном `.env` как `TG_BOT_TOKEN`
- Privacy mode: ON (стандарт). Видит `/команды`, `@mention`, reply на свои сообщения, admin-режим. Для notify-only нам этого хватает (бот шлёт, не читает).

### Group
- Создана 2026-05-06: `AI&Incruises`
- chat_id: `-5110729354`
- В локальном `.env` как `TG_GROUP_CHAT_ID`
- Test message `message_id=26` отправлен 2026-05-06 — бот пишет в группу OK ✓

### Storage
- `partner_integrations` schema готова (provider='telegram', config.chat_id), **но не используется в MVP** (один общий group chat в env)
- Per-partner личные TG → Phase 2+ (нужен onboarding flow с pairing code)

### Email backend
- **Не выбран.** Опции: Hostinger SMTP (`noreply@sairateam.com`), Gmail SMTP (app password), Resend API. Решать при старте Phase 2.

## Что осталось — имплементация

### Phase 1 (TG notify on task creation)
1. **VPS env** — добавить `TG_BOT_TOKEN` + `TG_GROUP_CHAT_ID` в `/docker/n8n/.env` через Hostinger Browser Terminal, restart `docker compose restart n8n`
2. **WF4 patch** — новая нода `40_Notify_TG_Group` после `30_Insert_Task`:
   ```
   POST https://api.telegram.org/bot{{$env.TG_BOT_TOKEN}}/sendMessage
   body: {chat_id: $env.TG_GROUP_CHAT_ID, text: "🆕 AI создал задачу: {title}\nЛид: {lead_name}\nПартнёр: {partner_name}"}
   ```
   - Если notify падает — task всё равно создан (WF4 идёт дальше)
3. **Redeploy** через `python scripts/upsert_wf.py WF4`
4. **E2E smoke** — создать тест-лид через webhook → AI квалификация → проверить что в TG group пришло сообщение
5. **Cleanup test data**

### Phase 2 (Email weekly digest)
1. Выбрать email backend (Hostinger SMTP / Resend / Gmail)
2. Если Hostinger SMTP — настроить `noreply@sairateam.com`
3. WF15 (новый) — cron weekly, fetch tasks created за неделю, render HTML/text email, send
4. Schedule: суббота утро? день недели + время = решить

## Открытые вопросы Phase 2
- Email backend (Hostinger / Gmail / Resend)
- Day + time digest (Sat 9:00? Mon 8:00?)
- Содержимое digest: только tasks или + leads + reply-counts?
- Footer: ссылка на dashboard, контакт Сырыма для unsubscribe?

## Заметки
- Bot username: `@incruises_ai_bot`
- Group title: `AI&Incruises`
- Test sent: `message_id=26` (2026-05-06)
- VPS env layout: `/docker/n8n/.env` (см. `reference_n8n_vps_layout.md`)
