# Reviews — фото лендинга

Назначение: оптимизированные фото партнёров для `reviews.html` на sairateam.com.

## Требования
- Формат: `.webp` (или `.jpg` fallback)
- Размер: 400×400 (аватар) или 800×600 (горизонтальный)
- Вес: < 100 KB на фото
- Optimize: `cwebp -q 75` или squoosh.app

## Формат имени
`partner-slug.webp` — например `anna-k.webp`, `azamat-b.webp`

## Деплой
Фото игнорятся в `.gitignore` (`assets/images/*.jpg|png|webp`). На хостинг попадают через FTP-deploy скрипт.

## Источник
`obsidian-vault/reference/reviews/raw/` → ручная обработка (crop + compress) → сюда.
