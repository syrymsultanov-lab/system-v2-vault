# CLAUDE.md — Content Factory (SYSTEM-v3.0)

## Назначение проекта

Автономный контент-завод для бренда **ИП Султанова Сайра** (sairateam.com).  
Система без участия человека находит видео и материалы по темам круизов, отельного отдыха, путешествий → публикует на Instagram и YouTube с атрибуцией авторов.

**Владелец бренда**: Сайра Султанова — публичное лицо, дистрибьютор InCruises, г. Актобе, Казахстан.  
**Технический директор**: Сырым Султанов.  
**Контакт**: info@sairateam.com | +7 (701) 406-67-52

---

## Архитектура системы

```
[PARSER] → [FILTER] → [GENERATOR] → [PUBLISHER]
   ↓            ↓           ↓             ↓
YouTube API  Claude API  Claude API   Instagram
RSS/Scraper  Relevance   Captions     YouTube API
             Score       + Post text  Telegram (v2)
                         + Attribution Facebook (v2)
```

### Стек технологий

| Компонент       | Технология                          |
|----------------|--------------------------------------|
| Оркестрация     | n8n (self-hosted, Hostinger)         |
| База данных     | Supabase (`njwraxmlzglmofxiwmxs`)    |
| Генерация текста| Claude API (claude-sonnet-4-...)     |
| Изображения     | Leonardo AI                          |
| Хостинг         | Hostinger (sairateam.com)            |
| Репозиторий     | GitHub (private)                     |
| Публикация      | Instagram Graph API, YouTube Data API|

---

## Структура папок

```
content-factory/
├── CLAUDE.md                  ← этот файл
├── README.md                  ← обзор для разработчика
├── .env.example               ← все переменные окружения
├── .gitignore
│
├── config/
│   ├── topics.json            ← темы и ключевые слова для парсинга
│   ├── sources.json           ← список RSS и YouTube-каналов источников
│   ├── platforms.json         ← настройки каждой платформы
│   └── schedule.json          ← расписание публикаций
│
├── src/
│   ├── parser/
│   │   ├── youtube_parser.js  ← поиск видео через YouTube Data API
│   │   ├── rss_parser.js      ← парсинг RSS-лент новостей
│   │   └── dedup.js           ← проверка дублей через Supabase
│   │
│   ├── filter/
│   │   ├── relevance.js       ← оценка релевантности через Claude API
│   │   └── legal_check.js     ← проверка лицензии (CC, fair use)
│   │
│   ├── generator/
│   │   ├── caption.js         ← генерация подписей к постам (Claude API)
│   │   ├── attribution.js     ← формирование ссылок на авторов
│   │   └── hashtags.js        ← генерация хэштегов под платформу
│   │
│   ├── publisher/
│   │   ├── instagram.js       ← публикация в Instagram Graph API
│   │   ├── youtube.js         ← публикация / Community post YouTube
│   │   ├── telegram.js        ← (v2) публикация в Telegram
│   │   └── facebook.js        ← (v2) публикация в Facebook
│   │
│   ├── scheduler/
│   │   └── queue.js           ← очередь публикаций, контроль расписания
│   │
│   ├── db/
│   │   ├── supabase.js        ← клиент Supabase
│   │   ├── content_log.js     ← запись опубликованного контента
│   │   └── schema.sql         ← SQL-схема таблиц
│   │
│   └── utils/
│       ├── logger.js          ← логирование в файл и Supabase
│       └── retry.js           ← retry-логика для API-вызовов
│
├── n8n/
│   ├── workflows/
│   │   ├── main_pipeline.json      ← главный workflow (импорт в n8n)
│   │   ├── youtube_parser.json     ← отдельный workflow парсера
│   │   ├── instagram_publisher.json
│   │   └── youtube_publisher.json
│   └── templates/
│       ├── caption_ru.txt          ← промпт для генерации подписей (RU)
│       └── attribution_template.txt← шаблон атрибуции автора
│
├── skills/
│   ├── SKILL_parser.md        ← skill: как работает парсер
│   ├── SKILL_generator.md     ← skill: как генерировать контент
│   ├── SKILL_publisher.md     ← skill: как публиковать
│   └── SKILL_legal.md         ← skill: юридические правила атрибуции
│
├── docs/
│   ├── SETUP.md               ← полная инструкция развёртывания
│   ├── API_KEYS.md            ← где взять каждый API-ключ
│   └── TROUBLESHOOTING.md     ← частые ошибки и решения
│
├── scripts/
│   ├── setup.sh               ← первоначальная настройка сервера
│   └── test_pipeline.sh       ← тест всей цепочки
│
└── logs/                      ← локальные логи (в .gitignore)
```

---

## Supabase — таблицы

### `content_items` — найденный контент
```sql
id            uuid PRIMARY KEY DEFAULT gen_random_uuid()
source_url    text NOT NULL UNIQUE      -- оригинальная ссылка
source_type   text                      -- 'youtube' | 'rss' | 'manual'
title         text
author_name   text                      -- имя автора для атрибуции
author_url    text                      -- ссылка на канал/профиль автора
thumbnail_url text
relevance_score float                   -- оценка Claude (0.0–1.0)
status        text DEFAULT 'pending'    -- pending | approved | rejected | published
created_at    timestamptz DEFAULT now()
```

### `published_posts` — опубликованные посты
```sql
id              uuid PRIMARY KEY DEFAULT gen_random_uuid()
content_item_id uuid REFERENCES content_items(id)
platform        text NOT NULL           -- 'instagram' | 'youtube' | 'telegram'
post_id         text                    -- ID поста на платформе
caption         text                    -- итоговый текст поста
published_at    timestamptz DEFAULT now()
status          text DEFAULT 'success'  -- success | failed
error_message   text
```

### `sources` — источники для парсинга
```sql
id          uuid PRIMARY KEY DEFAULT gen_random_uuid()
name        text NOT NULL
url         text NOT NULL UNIQUE
type        text                        -- 'youtube_channel' | 'youtube_search' | 'rss'
active      boolean DEFAULT true
last_parsed timestamptz
```

---

## Ключевые правила для AI-агентов

### ⚠️ КРИТИЧНО: Атрибуция
- **ВСЕГДА** включать имя автора и ссылку на оригинал
- Формат: `📹 Видео: @{author} → {url}`
- Никогда не публиковать без поля `author_name` и `author_url`

### ⚠️ КРИТИЧНО: Антидублирование
- Перед публикацией проверить `source_url` в таблице `published_posts`
- Если URL уже есть — пропустить, не публиковать повторно

### ⚠️ КРИТИЧНО: Язык контента
- Все подписи к постам — **на русском языке**
- Хэштеги — смешанные: русские + английские (50/50)
- Тон: тёплый, вдохновляющий, как рекомендация подруги

### Лимиты публикаций
- Instagram: не более **3 постов в день**
- YouTube Community: не более **2 постов в день**
- Пауза между постами: минимум **3 часа**

### Оценка релевантности (Claude)
Контент считается релевантным если тема входит в список:
- Круизы (любые компании, маршруты, обзоры)
- InCruises (новости, отзывы, бизнес-возможности)
- Отельный отдых премиум-класса
- Путешествия (впечатления, лайфхаки, обзоры)
- Пассивный доход / travel-бизнес

Минимальный порог `relevance_score`: **0.7**

---

## Переменные окружения (.env)

```bash
# Supabase
SUPABASE_URL=https://njwraxmlzglmofxiwmxs.supabase.co
SUPABASE_SERVICE_KEY=your_service_key

# Claude API
ANTHROPIC_API_KEY=your_key

# YouTube Data API v3
YOUTUBE_API_KEY=your_key

# Instagram Graph API
INSTAGRAM_ACCESS_TOKEN=your_token
INSTAGRAM_BUSINESS_ACCOUNT_ID=your_account_id

# YouTube OAuth (для загрузки)
YOUTUBE_CLIENT_ID=your_client_id
YOUTUBE_CLIENT_SECRET=your_client_secret
YOUTUBE_REFRESH_TOKEN=your_refresh_token

# Leonardo AI
LEONARDO_API_KEY=your_key

# n8n
N8N_WEBHOOK_URL=https://your-n8n-instance.com
```

---

## Запрещено

- Публиковать контент без атрибуции автора
- Скачивать и перезаливать чужие видео без разрешения (только репост/ссылка)
- Публиковать контент с `relevance_score` ниже 0.7
- Публиковать дублирующийся контент (проверка по `source_url`)
- Изменять структуру таблиц Supabase без обновления этого файла

---

## Версия и история

| Версия | Дата       | Изменения                        |
|--------|------------|----------------------------------|
| 3.0    | 2026-05-05 | Создание нового проекта Content Factory |
| —      | —          | Отделён от SYSTEM-v2.1           |
