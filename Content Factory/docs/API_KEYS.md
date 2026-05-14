# Инструкция по получению API-ключей

## 1. Claude API (Anthropic)
1. Перейти: https://console.anthropic.com
2. Зарегистрироваться / войти
3. API Keys → Create Key
4. Скопировать в `.env` → `ANTHROPIC_API_KEY`

---

## 2. YouTube Data API v3

### API Key (для поиска и парсинга)
1. https://console.cloud.google.com
2. Создать новый проект (например: `content-factory-sairateam`)
3. APIs & Services → Enable APIs → найти "YouTube Data API v3" → Enable
4. Credentials → Create Credentials → API Key
5. Скопировать в `.env` → `YOUTUBE_API_KEY`

### OAuth 2.0 (для публикации Community Posts)
1. Credentials → Create Credentials → OAuth 2.0 Client ID
2. Application type: Web application
3. Authorized redirect URIs: `https://your-n8n.hostinger.com/rest/oauth2-credential/callback`
4. Скопировать Client ID и Client Secret в `.env`
5. Для получения Refresh Token — использовать OAuth Playground:
   - https://developers.google.com/oauthplayground
   - Scope: `https://www.googleapis.com/auth/youtube`
   - Exchange authorization code for tokens
   - Скопировать `refresh_token` в `.env` → `YOUTUBE_REFRESH_TOKEN`

---

## 3. Instagram Graph API

### Требования
- Facebook Business Manager аккаунт
- Instagram Business или Creator аккаунт (не личный!)
- Подключить Instagram к Facebook Page

### Шаги
1. https://developers.facebook.com → My Apps → Create App
2. Тип: Business
3. Добавить продукт: Instagram Graph API
4. Permissions: `instagram_basic`, `instagram_content_publish`, `pages_read_engagement`
5. Получить Long-lived Access Token:
   ```
   GET https://graph.facebook.com/v19.0/oauth/access_token
     ?grant_type=fb_exchange_token
     &client_id={app_id}
     &client_secret={app_secret}
     &fb_exchange_token={short_lived_token}
   ```
6. Найти Instagram Business Account ID:
   ```
   GET https://graph.facebook.com/v19.0/me/accounts?access_token={token}
   ```
7. Скопировать в `.env`

⚠️ Long-lived token действует 60 дней. Нужно настроить автообновление в n8n.

---

## 4. Leonardo AI
1. https://app.leonardo.ai
2. Зарегистрироваться
3. Settings → API Access → Generate API Key
4. Скопировать в `.env` → `LEONARDO_API_KEY`

---

## 5. Telegram Bot (для уведомлений)
1. Открыть @BotFather в Telegram
2. `/newbot` → задать имя (например: `SairaTeam Monitor`)
3. Скопировать токен в `.env` → `TELEGRAM_BOT_TOKEN`
4. Получить свой Chat ID:
   - Написать боту любое сообщение
   - https://api.telegram.org/bot{TOKEN}/getUpdates
   - Найти `message.chat.id`
5. Скопировать в `.env` → `TELEGRAM_ADMIN_CHAT_ID`
