# 🎬 Video Yukla Bot

Telegram bot — Instagram, YouTube, TikTok va boshqa platformalardan video yuklab beradi.
Foydalanuvchi faqat havolani yuboradi, bot avtomatik aniqlaydi va yuklab beradi.

## Stack

- Python 3.11 + aiogram 3
- PostgreSQL (asyncpg)
- yt-dlp + ffmpeg
- Docker + docker-compose

## Foydalanish

```bash
cp .env.example .env
# .env faylni tahrirlang (BOT_TOKEN, ADMINS, DB_*)

docker compose up -d --build
```

## Loyiha tuzilishi

```
videoyukla-bot/
├── app.py                  # Entry point
├── loader.py               # Bot, dispatcher, db
├── data/config.py          # .env o'qish
├── filters/                # admin / chat type
├── handlers/
│   ├── admin/panel.py      # Admin menu (statistika, broadcast, kanal, ...)
│   ├── users/start.py      # /start, kanal a'zoligi
│   ├── users/help.py       # /help
│   └── users/download.py   # Link → video yuklab berish
├── keyboards/              # Reply va inline
├── middlewares/throttling.py
├── states/admin_states.py
├── utils/
│   ├── db/postgres.py      # Asyncpg pool, jadvallar
│   ├── downloader/ytdlp.py # yt-dlp wrapper
│   ├── notify_admins.py
│   └── set_bot_commands.py
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

## Asosiy oqim

1. Foydalanuvchi `/start` bosadi
2. Bot kanal a'zoligini tekshiradi (agar admin kanal qo'shgan bo'lsa)
3. Foydalanuvchi har qanday video havolani yuboradi
4. Bot platformani avtomatik aniqlaydi (YouTube/Instagram/TikTok/...) — so'ramaydi
5. yt-dlp orqali yuklab oladi va Telegramga yuboradi

## Admin paneli

`/admin` orqali kiriladi. Tugmalar:

- 📊 Statistika
- 📢 Xabar yuborish (broadcast)
- 🔗 Obuna sozlamalari (majburiy kanallar)
- 💳 Karta raqami
- 💵 Narxni belgilash
- 💰 To'lov holati (yoq/o'chir)
- 📝 Start matni
- ❓ Help matni
- 🏠 Asosiy menyu

# video-bott
