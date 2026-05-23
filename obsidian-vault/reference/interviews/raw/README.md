# Interviews — RAW audio

Сюда кидать аудио интервью партнёров (Сайра, лиды, обратная связь).

## Поддерживаемые форматы
`.mp3` `.m4a` `.mp4` `.ogg` `.wav` `.webm` `.flac` `.mpga` `.mpeg`

## Лимиты
- **25 MB на файл** (OpenAI Whisper API). 30 мин mp3 ~ 14 MB. 40 мин m4a ~ 8 MB.
- Если больше — разрезать: `ffmpeg -i input.mp3 -f segment -segment_time 600 out_%03d.mp3`

## Naming
`SairaInterview_YYYY-MM-DD.m4a`
`LeadCall_<lead_id>_YYYY-MM-DD.mp3`

## Запуск транскрипции

```bash
# Все файлы которые ещё не транскрибированы
python scripts/transcribe_audio.py

# Конкретный файл
python scripts/transcribe_audio.py obsidian-vault/reference/interviews/raw/SairaInterview_2026-05-25.m4a

# Перетранскрибировать всё
python scripts/transcribe_audio.py --force
```

Результат → `obsidian-vault/reference/interviews/transcripts/<name>.md` с timestamp-сегментами.

## Cost
$0.006/мин (whisper-1). 40 мин = $0.24.

## Игнор в Git
Аудио-файлы НЕ коммитятся (см. `.gitignore`).
Транскрипты `.txt` — коммитятся (это полезный текст).
