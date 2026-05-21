---
tags: [docs, canonical, kb-source]
project: system-v2
type: index
updated: 2026-05-19
---

# /docs — Эталонная документация

## Назначение

**Только проверенная и официально подтверждённая информация.** Содержимое этой папки = единственный источник истины для KB AI-агента (наряду с `reference/`). Всё что AI цитирует фактически, должно приходить отсюда.

## Что сюда НЕ кладём

- Черновики, диалоги, гипотезы, заметки сессий → `daily/`, `sessions/`, корень vault
- Сырые экспорты с Google Диска → остаются в `Файлы с Google диска/` (НЕ эталон)
- MLM-книги Big Al / Don Failla / Kalench / Rohn — это **корпус для общего MLM-контекста**, не эталон по InCruises. Остаются в `Файлы с Google диска/`
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

## Текущие документы

- [[InCruises Ranks]] — все ранги InCruises с условиями достижения
- [[Presentation Script]] — SOP проведения презентации + 45-сек скрипты

## Связи

- [[CLAUDE]] §AI-pipeline
- [[Business Rules]] §5 income guarantee
