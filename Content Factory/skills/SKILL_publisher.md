# SKILL: Publisher — Публикация контента

## Назначение
Этот skill описывает, как система публикует готовый контент в Instagram и YouTube без участия человека.

---

## Instagram Graph API

### Публикация фото/превью с подписью

**Шаг 1: Создание медиа-объекта**
```
POST https://graph.facebook.com/v19.0/{INSTAGRAM_BUSINESS_ACCOUNT_ID}/media
  ?image_url={thumbnail_url}
  &caption={full_post_text_url_encoded}
  &access_token={INSTAGRAM_ACCESS_TOKEN}
```

**Шаг 2: Публикация**
```
POST https://graph.facebook.com/v19.0/{INSTAGRAM_BUSINESS_ACCOUNT_ID}/media_publish
  ?creation_id={из шага 1}
  &access_token={INSTAGRAM_ACCESS_TOKEN}
```

**Важно:**
- `image_url` должен быть публично доступным URL (использовать thumbnail_url из YouTube)
- Длина `caption` — не более 2200 символов
- Между шагом 1 и 2 выждать 5-10 секунд

### Публикация Reels (видео)
⚠️ Instagram Graph API **не поддерживает** прямую загрузку чужих видео.  
Стратегия: публиковать **превью (thumbnail)** + ссылку в подписи → направлять в bio.

---

## YouTube — Community Post

### Создание Community Post (текст + изображение)
```
POST https://www.googleapis.com/youtube/v3/communityPosts
Authorization: Bearer {YOUTUBE_ACCESS_TOKEN}
Content-Type: application/json

{
  "snippet": {
    "type": "textPost",
    "textOriginalPost": "{full_post_text}"
  }
}
```

⚠️ **Community Post доступен только каналам с 500+ подписчиков.**  
Если канал не достиг порога — публиковать через YouTube Studio вручную до достижения порога.

### YouTube OAuth 2.0 (обязательно для публикации)
```
Scopes: https://www.googleapis.com/auth/youtube
Token endpoint: https://oauth2.googleapis.com/token
Refresh token: сохранить в .env как YOUTUBE_REFRESH_TOKEN
```

**Refresh токена в n8n:**
```
POST https://oauth2.googleapis.com/token
  client_id={YOUTUBE_CLIENT_ID}
  client_secret={YOUTUBE_CLIENT_SECRET}
  refresh_token={YOUTUBE_REFRESH_TOKEN}
  grant_type=refresh_token
```

---

## Расписание публикаций

| Платформа | Время публикаций       | Максимум/день |
|-----------|------------------------|---------------|
| Instagram | 09:00, 14:00, 19:00    | 3 поста       |
| YouTube   | 10:00, 17:00           | 2 поста       |

**Временная зона**: UTC+5 (Актобе, Казахстан)

---

## Алгоритм публикатора

```
1. Получить из Supabase контент со статусом 'approved'
   ORDER BY relevance_score DESC LIMIT 1
2. Проверить расписание:
   - Сколько постов опубликовано сегодня на платформе?
   - Прошло ли 3 часа с последней публикации?
3. Если да → публиковать:
   a. Вызвать API платформы
   b. Получить post_id
   c. Записать в published_posts
   d. Обновить content_items.status = 'published'
4. Если нет → поставить в очередь на следующий слот
```

---

## Запись результата в Supabase

```sql
INSERT INTO published_posts (
  content_item_id,
  platform,
  post_id,
  caption,
  published_at,
  status
) VALUES (
  '{content_item_id}',
  '{platform}',
  '{post_id}',
  '{caption}',
  now(),
  'success'
);

UPDATE content_items
SET status = 'published'
WHERE id = '{content_item_id}';
```

---

## Обработка ошибок публикации

| Ошибка                        | Действие                                    |
|-------------------------------|---------------------------------------------|
| Instagram 400 (bad request)   | Проверить длину caption, retry              |
| Instagram 190 (token expired) | Обновить access token, retry                |
| YouTube 401 (unauthorized)    | Refresh OAuth token, retry                  |
| YouTube 403 (quota exceeded)  | Остановить на 24 часа, уведомить            |
| Любая ошибка 3 раза подряд    | Записать status='failed', уведомить Сырыма  |

### Уведомление об ошибке (Telegram)
```
POST https://api.telegram.org/bot{TOKEN}/sendMessage
  chat_id={ADMIN_CHAT_ID}
  text="⚠️ Content Factory ERROR\nПлатформа: {platform}\nОшибка: {error}\nКонтент: {source_url}"
```

---

## Проверка лимитов перед публикацией

```sql
-- Сколько постов опубликовано сегодня
SELECT COUNT(*) FROM published_posts
WHERE platform = '{platform}'
AND published_at >= CURRENT_DATE
AND status = 'success';

-- Когда последняя публикация
SELECT published_at FROM published_posts
WHERE platform = '{platform}'
ORDER BY published_at DESC
LIMIT 1;
```
