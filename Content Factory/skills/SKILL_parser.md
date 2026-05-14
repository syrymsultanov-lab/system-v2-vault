# SKILL: Parser — Поиск и сбор контента

## Назначение
Этот skill описывает, как система находит релевантные видео и материалы из внешних источников без участия человека.

---

## Источники данных

### 1. YouTube Data API v3

**Поиск по ключевым словам:**
```
GET https://www.googleapis.com/youtube/v3/search
  ?part=snippet
  &q={keyword}
  &type=video
  &order=date
  &publishedAfter={24h ago ISO8601}
  &maxResults=10
  &key={YOUTUBE_API_KEY}
```

**Ключевые слова для поиска** (из `config/topics.json`):
- `cruise review 2025`
- `InCruises отзыв`
- `luxury cruise vlog`
- `hotel review luxury`
- `cruise ship tour`
- `путешествие круиз`
- `отдых на море обзор`

**Что брать из ответа:**
```json
{
  "id": { "videoId": "abc123" },
  "snippet": {
    "title": "...",
    "channelTitle": "...",
    "channelId": "...",
    "publishedAt": "...",
    "thumbnails": { "high": { "url": "..." } }
  }
}
```

**Формировать `source_url`**: `https://youtube.com/watch?v={videoId}`  
**Формировать `author_url`**: `https://youtube.com/channel/{channelId}`

---

### 2. RSS-парсинг новостных сайтов

**Список источников** (из `config/sources.json`):
- `https://cruiseindustrynews.com/feed/`
- `https://www.cruisecritic.com/rss/news.xml`
- `https://www.travelweekly.com/rss`

**Парсинг RSS в n8n**: использовать ноду `RSS Feed Read`  
**Поля для извлечения**: `title`, `link`, `author`, `pubDate`, `description`

---

## Алгоритм работы парсера

```
1. Получить список активных источников из Supabase (sources WHERE active=true)
2. Для каждого источника:
   a. Запросить новые материалы (за последние 24 часа)
   b. Для каждого материала:
      - Проверить source_url на дубль в content_items
      - Если дубль → пропустить
      - Если новый → сохранить в content_items со статусом 'pending'
3. Обновить sources.last_parsed = now()
4. Передать список новых ID в модуль Filter
```

---

## Защита от дублей

Перед сохранением выполнить:
```sql
SELECT id FROM content_items WHERE source_url = '{url}' LIMIT 1;
```
Если результат не пустой — пропустить материал.

---

## Лимиты API

| API              | Лимит              | Стратегия                        |
|------------------|--------------------|----------------------------------|
| YouTube Data API | 10,000 units/day   | Не более 5 поисков × 10 результатов = 500 units |
| RSS              | Без лимита         | Парсить каждые 6 часов           |

---

## Расписание запуска

```
Парсер YouTube: каждые 6 часов (00:00, 06:00, 12:00, 18:00)
Парсер RSS:     каждые 6 часов (смещение +1 час от YouTube)
```

---

## Ошибки и обработка

| Ошибка                  | Действие                              |
|-------------------------|---------------------------------------|
| YouTube API 403         | Остановить, записать в лог, уведомить |
| YouTube API 429         | Ждать 1 час, retry                    |
| RSS недоступен          | Пропустить источник, retry через 3 ч  |
| Supabase ошибка записи  | Retry 3 раза, затем лог               |

---

## Выходные данные

После работы парсера в таблице `content_items` появляются записи:
```
status = 'pending'
source_url = 'https://youtube.com/watch?v=...'
author_name = 'Channel Name'
author_url = 'https://youtube.com/channel/...'
title = 'Video Title'
thumbnail_url = 'https://...'
relevance_score = NULL (заполняет модуль Filter)
```
