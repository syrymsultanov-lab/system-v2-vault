-- Content Factory — Supabase Schema
-- Проект: sairateam Content Factory (SYSTEM-v3.0)
-- Дата: 2026-05-05

-- ============================================================
-- Таблица 1: sources — источники контента
-- ============================================================
CREATE TABLE IF NOT EXISTS sources (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name        text NOT NULL,
  url         text NOT NULL UNIQUE,
  type        text NOT NULL CHECK (type IN ('youtube_channel', 'youtube_search', 'rss')),
  keywords    text[],               -- ключевые слова для youtube_search
  active      boolean DEFAULT true,
  last_parsed timestamptz,
  created_at  timestamptz DEFAULT now()
);

-- Начальные источники
INSERT INTO sources (name, url, type, keywords) VALUES
  ('YouTube: cruise review', 'youtube_search:cruise_review', 'youtube_search', ARRAY['cruise review 2025', 'luxury cruise tour']),
  ('YouTube: InCruises', 'youtube_search:incruises', 'youtube_search', ARRAY['InCruises review', 'InCruises отзыв']),
  ('YouTube: путешествия RU', 'youtube_search:travel_ru', 'youtube_search', ARRAY['круиз отзыв', 'отдых на море обзор']),
  ('Cruise Industry News RSS', 'https://cruiseindustrynews.com/feed/', 'rss', NULL),
  ('Cruise Critic RSS', 'https://www.cruisecritic.com/rss/news.xml', 'rss', NULL);

-- ============================================================
-- Таблица 2: content_items — найденный контент
-- ============================================================
CREATE TABLE IF NOT EXISTS content_items (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  source_id       uuid REFERENCES sources(id),
  source_url      text NOT NULL UNIQUE,
  source_type     text NOT NULL CHECK (source_type IN ('youtube', 'rss', 'manual')),
  title           text,
  author_name     text NOT NULL,
  author_url      text NOT NULL,
  thumbnail_url   text,
  description     text,
  license         text DEFAULT 'youtube' CHECK (license IN ('youtube', 'creativeCommon')),
  relevance_score float CHECK (relevance_score >= 0 AND relevance_score <= 1),
  status          text DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected', 'published', 'blocked')),
  reject_reason   text,
  created_at      timestamptz DEFAULT now(),
  updated_at      timestamptz DEFAULT now()
);

-- Индексы
CREATE INDEX IF NOT EXISTS idx_content_items_status ON content_items(status);
CREATE INDEX IF NOT EXISTS idx_content_items_source_url ON content_items(source_url);
CREATE INDEX IF NOT EXISTS idx_content_items_relevance ON content_items(relevance_score DESC);

-- ============================================================
-- Таблица 3: generated_posts — сгенерированные тексты постов
-- ============================================================
CREATE TABLE IF NOT EXISTS generated_posts (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  content_item_id uuid NOT NULL REFERENCES content_items(id),
  platform        text NOT NULL CHECK (platform IN ('instagram', 'youtube', 'telegram', 'facebook')),
  caption         text NOT NULL,
  hashtags        text,
  attribution     text NOT NULL,
  full_post       text NOT NULL,
  char_count      integer,
  created_at      timestamptz DEFAULT now()
);

-- ============================================================
-- Таблица 4: published_posts — опубликованные посты
-- ============================================================
CREATE TABLE IF NOT EXISTS published_posts (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  content_item_id uuid NOT NULL REFERENCES content_items(id),
  generated_post_id uuid REFERENCES generated_posts(id),
  platform        text NOT NULL CHECK (platform IN ('instagram', 'youtube', 'telegram', 'facebook')),
  post_id         text,             -- ID поста на платформе
  post_url        text,             -- прямая ссылка на пост
  published_at    timestamptz DEFAULT now(),
  status          text DEFAULT 'success' CHECK (status IN ('success', 'failed', 'deleted')),
  error_message   text,
  retry_count     integer DEFAULT 0
);

-- Индексы
CREATE INDEX IF NOT EXISTS idx_published_posts_platform ON published_posts(platform);
CREATE INDEX IF NOT EXISTS idx_published_posts_published_at ON published_posts(published_at DESC);

-- ============================================================
-- Таблица 5: pipeline_logs — логи работы системы
-- ============================================================
CREATE TABLE IF NOT EXISTS pipeline_logs (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  stage       text NOT NULL,        -- 'parser' | 'filter' | 'generator' | 'publisher'
  level       text DEFAULT 'info' CHECK (level IN ('info', 'warn', 'error')),
  message     text NOT NULL,
  meta        jsonb,                -- дополнительные данные
  created_at  timestamptz DEFAULT now()
);

-- ============================================================
-- View: pending_queue — очередь контента для публикации
-- ============================================================
CREATE OR REPLACE VIEW pending_queue AS
SELECT
  ci.id,
  ci.title,
  ci.author_name,
  ci.source_url,
  ci.thumbnail_url,
  ci.relevance_score,
  ci.status,
  ci.created_at
FROM content_items ci
WHERE ci.status = 'approved'
  AND ci.relevance_score >= 0.7
ORDER BY ci.relevance_score DESC, ci.created_at ASC;

-- ============================================================
-- View: daily_stats — статистика за сегодня
-- ============================================================
CREATE OR REPLACE VIEW daily_stats AS
SELECT
  platform,
  COUNT(*) AS posts_today,
  MAX(published_at) AS last_published_at
FROM published_posts
WHERE published_at >= CURRENT_DATE
  AND status = 'success'
GROUP BY platform;
