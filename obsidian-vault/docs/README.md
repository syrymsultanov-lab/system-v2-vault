---
tags: [docs, canonical, kb-source]
project: system-v2
type: index
updated: 2026-05-24
---

# /docs — Эталонная документация

## Назначение

**Только проверенная и официально подтверждённая информация.** Содержимое этой папки (root) = единственный источник истины для KB AI-агента. Всё что AI цитирует фактически, должно приходить отсюда.

## Структура

- `docs/*.md` — **canonical KB**, ingest в `kb_chunks` через `push_kb_chunks_to_webhook.py`
- `docs/raw/*.md` — **staging для выжимки** (MLM-книги, сырые источники). **НЕ ingest as-is.** Используются для извлечения паттернов в canonical файлы

## Что сюда НЕ кладём (в root)

- Черновики, диалоги, гипотезы, заметки сессий → `daily/`, `sessions/`, корень vault
- Сырые экспорты с Google Диска → `Файлы с Google диска/` (НЕ эталон)
- **MLM-книги** (Big Al / Don Failla / Kalench / Rohn) → `docs/raw/`. Корпус общего MLM-контекста, не эталон по InCruises. После Saira interview обработки — выжать паттерны (рекрутинг, лидерство, возражения) в короткие compliance-safe canonical файлы
- Незаверенный AI-генерёный контент

## Правила приёма

1. Документ принят в `docs/` только если Сырым/Сайра подтвердили факты.
2. **YAML frontmatter обязателен:**
   ```yaml
   ---
   tags: [docs, <topic>]
   source: <official InCruises url / PDF / Comp Plan>
   verified_by: Сырым | Сайра
   verified_at: YYYY-MM-DD
   updated: YYYY-MM-DD
   ---
   ```
3. **Формат:** UTF-8, Markdown. Параграфы разделены blank line. Минимум 40 chars per параграф.
4. **Числа дохода/бонусов** — обязательно с указанием источника (PDF/slide). При цитировании в AI автоматически добавляется hedge через промпт.
5. **Без AI-галлюцинаций.** Если факт неизвестен — пишем `<TODO: confirm>`, не выдумываем.

## Ingest в RAG

После добавления/изменения файла:
1. Добавить путь в `scripts/push_kb_chunks_to_webhook.py` → `KB_SOURCES`
2. Запустить `python scripts/push_kb_chunks_to_webhook.py`
3. Идемпотентно — DELETE existing rows for source → re-embed → kb_chunks INSERT

## Текущие документы (canonical, в KB)

InCruises официальные (PDF→md):
- `101RU_SIMPLE_COMPANY_PRESENTATION.md`
- `104RU_3.2_INDEPENDENT_PARTNER_AGREEMENT.md`
- `106RU_3.2_MEMBER_AGREEMENT.md`
- `109RU_INCOME_AND_INCENTIVE_OVERVIEW.md`
- `214RU_INCOME_AND_INCENTIVE_GUIDE.md`
- `503RU_PAYMENT_AGREEMENT.md`

Сайра/команда verified:
- [[InCruises Ranks]] — 12 рангов + расчёты + ЛИЧНО/КОМАНДНО/MIX format
- [[Presentation Script]] — SOP + 45-сек скрипты
- [[Company Facts]] — корпоративные stats
- [[Reviews]] — 6 партнёров из inCruises magazine

## raw/ (staging, НЕ ingest)

- `DON_FAILA_s_10_LESSONS_ON_NAPKINS.md` — Дон Файла классика
- `BIG_ALL_SECRETS.md` — Том Шрайтер «Большой Эл» система рекрутирования
- `BIG_ALL_LEADERS.md` — Том Шрайтер «Лидеры»
- `JIM_ROHN_VITAMINS_FOR_THE_MIND.md` — Джим Рон mindset/philosophy

Workflow: после Saira interview → выжать паттерны (совпадающие с её voice + compliance-safe) в новые `docs/*.md` (типа `Recruiting Patterns.md`, `Leadership Principles.md`)

## Связи

- [[CLAUDE]] §AI-pipeline
- [[Business Rules]] §5 income guarantee
