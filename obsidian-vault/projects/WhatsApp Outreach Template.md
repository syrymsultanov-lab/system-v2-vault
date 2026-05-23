---
type: project-template
status: ready-to-send
version: 3
for: Сайра
prepared_at: 2026-05-23
purpose: Привлечь первых 10-15 живых кандидатов на sairateam.com + TG install instruction для AI engagement
---

# Шаблон рассылки v3 — WhatsApp / TG / Instagram

## Зачем

С 2026-04-30 на лендинг **0 реальных кандидатов**. Tech-stack готов, но непротестирован на живых людях. Цель — 10-15 знакомых Сайры → форма → leads + AI-разговор → audit.

**Это закрытое тестирование, не продажа.** Никаких обещаний дохода.

---

## ⚠ Telegram = обязательное условие для AI

**AI-агент работает ТОЛЬКО в Telegram** (бот `@incruises_ai_bot`). WhatsApp Business API (WABA) и Instagram — будущие фазы.

**Решение:** в каждом шаблоне просим установить Telegram если у кандидата его нет. Это бесплатно (2 минуты, App Store / Google Play). Без TG — Сайра пишет вручную, но AI не подключается.

**Ссылки для установки (включай в сообщение):**
- iOS: https://apps.apple.com/app/telegram-messenger/id686449807
- Android: https://play.google.com/store/apps/details?id=org.telegram.messenger
- Веб: https://web.telegram.org

**После установки** кандидат заходит на лендинг, выбирает Telegram в форме, указывает свой `@username`. AI пишет ему через 1-2 часа.

---

## Кому слать (целевая аудитория)

✅ **Хорошо:**
- Знакомые, которые **уже путешествуют** или хотят
- Мамы в декрете / на удалёнке (доп. доход)
- Бывшие коллеги из банковской / финансовой сферы
- Подруги Сайры из её круга
- Партнёры команды Сайры (UX feedback)

❌ **Плохо:**
- Польша (compliance 106RU — InCruises там не работает)
- Случайные холодные insta-инфлюенсеры
- Подписчики каналов без знакомства

**Цель: 15 контактов → ~10 заполнят форму → 5-7 продолжат разговор.**

---

## Шаблон A — тёплый круг (друзья / знакомые)

```
[Имя], привет 👋

Я запустила свою систему для команды — там есть AI-помощник,
он ведёт первые разговоры с теми, кому интересны путешествия
и доп. возможности.

Сейчас тестирую — нужна твоя обратная связь как живого человека.
Зайди по ссылке, оставь заявку (1 минута):

https://sairateam.com

📱 ВАЖНО: общение с AI идёт только в Telegram.
Если у тебя ещё не установлен TG — поставь, это бесплатно
и быстро:
   iOS: https://apps.apple.com/app/telegram-messenger/id686449807
   Android: https://play.google.com/store/apps/details?id=org.telegram.messenger
В форме укажи свой Telegram-username (@что-то) — мой AI
напишет тебе сам через час-два после заявки.

Если совсем нет возможности поставить TG — выбери WhatsApp
в форме, тогда напишу сама.

Без обязательств и продажи — мне важно увидеть как система
работает с живыми людьми. Спасибо! 🌊
```

---

## Шаблон B — бывшие коллеги / клиенты банка

```
[Имя], привет!

Помнишь, мы обсуждали путешествия / финансовую свободу?
Я сейчас в проекте, который объединяет это с системным подходом.

Запустила свою CRM-систему с AI-помощником. Хочу показать как
работает — он расскажет про возможности команды и ответит
на вопросы.

Зайди: https://sairateam.com
Заполни форму (1 мин) — там укажешь свой удобный канал.

📱 AI-помощник работает в Telegram. Если у тебя его ещё нет —
поставь приложение, это занимает 2 минуты:
   iOS: https://apps.apple.com/app/telegram-messenger/id686449807
   Android: https://play.google.com/store/apps/details?id=org.telegram.messenger

В форме укажи свой Telegram-username. AI напишет первым
через 1-2 часа после заявки — попробуй пообщаться, это
бесплатно и без обязательств.

Если по каким-то причинам TG не подходит — выбери WhatsApp,
я свяжусь сама.

Если зайдёт — пообщаемся живьём после.
```

---

## Шаблон C — партнёры команды (UX feedback)

```
[Имя], мне нужна твоя помощь как партнёра.

Я тестирую AI-агента для нашей команды — он будет вести
первые касания с новыми кандидатами, чтоб мы подключались
только к горячим.

Зайди как «кандидат»: https://sairateam.com
Заполни форму как обычный человек — имя, страна, контакт.
Обязательно выбери Telegram в поле «мессенджер» и укажи
свой @username — это нужно для теста AI.

📱 Если у тебя нет Telegram — поставь, без него тест не
получится:
   iOS: https://apps.apple.com/app/telegram-messenger/id686449807
   Android: https://play.google.com/store/apps/details?id=org.telegram.messenger

После формы — найди бот @incruises_ai_bot в Telegram и
нажми /start. AI начнёт диалог. Пообщайся с ним 4-5
сообщений как реальный кандидат.

Потом скинь мне screenshot — что было хорошо, что косячно,
что бы ты иначе ответила.

Это не для тебя — это чтоб научить AI правильно говорить
с твоими будущими кандидатами. Спасибо! 💪
```

---

## Как Сырым отслеживает

1. **Дашборд:** https://sairateam.com/login.html → вкладка «Заявки»
2. **DB-query:**
   ```sql
   SELECT name, country, messenger, messenger_handle, status, created_at
   FROM leads WHERE created_at > '2026-05-23' ORDER BY created_at DESC;
   ```
3. **TG-уведомление:** WF4 шлёт в группу `AI&Incruises` при new task
4. **AI-разговор (только TG):**
   ```sql
   SELECT direction, body, created_at FROM inbound_messages
   WHERE channel = 'telegram'
   AND created_at > '2026-05-23' ORDER BY created_at;
   ```

После 5-10 кандидатов делаем audit:
- Сколько указали Telegram vs WhatsApp/Insta?
- Какие score AI дал (для TG-кандидатов)?
- AI ответил адекватно?
- Где косяки в формулировках?
- Сколько manual outreach пошло на Сайру (для не-TG)?

---

## Compliance check перед рассылкой

✅ **Можно говорить:** «AI-помощник», «команда», «путешествия», «возможности», «система», «партнёры», «кандидаты»
❌ **Нельзя:** конкретные суммы дохода, гарантии, проценты, «заработай $X», обещания ранга

Лендинг УЖЕ compliance-safe (рерайт 2026-05-21).

---

## Когда отправлять — green light

🟢 **Можно слать прямо сейчас.** 4 техфикса закрыты 2026-05-23:
1. ✅ Consent gate (proactive AI требует `ai_consent = true`)
2. ✅ Reactivate `/start` keyword (trigger `reactivate_contact_on_inbound`)
3. ✅ Double-reply debounce (WF Wait + RPC `should_process_inbound_now`)
4. ✅ `contacts.country` миграция (для geo-fence PL)

🟡 **Опционально перед стартом:**
- Whisper транскрипция Сайра interview (после ротации OPENAI_API_KEY)

---

## Связи

- [[SYSTEM V2]] — Phase C1 launch readiness
- [[Saira Interview Plan]] — параллельный track для KB voice
- [[Landing Page]] — sairateam.com (live с 2026-04-29)
- [[Reviews]] — 6 партнёров уже на reviews.html
