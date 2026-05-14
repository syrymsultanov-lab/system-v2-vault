# Content Factory — SYSTEM-v3.0

Автономный контент-завод для бренда **Сайры Султановой** (sairateam.com).

## Что делает система

1. **Парсит** YouTube и RSS каждые 6 часов по темам: круизы, отели, InCruises
2. **Оценивает** релевантность через Claude API (порог: 0.7)
3. **Генерирует** русскоязычные подписи с хэштегами и атрибуцией автора
4. **Публикует** в Instagram (3×/день) и YouTube Community (2×/день)
5. **Логирует** всё в Supabase, уведомляет об ошибках в Telegram

## Быстрый старт

```bash
# 1. Клонировать репозиторий
git clone git@github.com:syrymsultanov-lab/content-factory.git
cd content-factory

# 2. Настроить переменные окружения
cp .env.example .env
# Заполнить .env своими ключами (см. docs/API_KEYS.md)

# 3. Применить схему в Supabase
# Открыть Supabase SQL Editor → скопировать src/db/schema.sql → выполнить

# 4. Импортировать workflows в n8n
# n8n → Import → выбрать файлы из n8n/workflows/

# 5. Запустить тест
bash scripts/test_pipeline.sh
```

## Документация

- [CLAUDE.md](./CLAUDE.md) — главный документ для AI-агентов
- [docs/SETUP.md](./docs/SETUP.md) — полная инструкция развёртывания
- [docs/API_KEYS.md](./docs/API_KEYS.md) — где взять каждый ключ
- [docs/TROUBLESHOOTING.md](./docs/TROUBLESHOOTING.md) — частые ошибки

## Skills (навыки AI-агента)

- [skills/SKILL_parser.md](./skills/SKILL_parser.md) — парсинг источников
- [skills/SKILL_generator.md](./skills/SKILL_generator.md) — генерация текста
- [skills/SKILL_publisher.md](./skills/SKILL_publisher.md) — публикация
- [skills/SKILL_legal.md](./skills/SKILL_legal.md) — юридические правила

## Стек

| Компонент    | Технология              |
|-------------|-------------------------|
| Оркестрация  | n8n (self-hosted)       |
| База данных  | Supabase                |
| AI           | Claude API (Anthropic)  |
| Хостинг      | Hostinger               |
| Платформы v1 | Instagram, YouTube      |
| Платформы v2 | Telegram, Facebook      |

## Контакты

- **Технический директор**: Сырым Султанов
- **Бренд**: ИП Султанова Сайра, г. Актобе
- **Email**: info@sairateam.com
