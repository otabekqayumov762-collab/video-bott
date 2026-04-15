from environs import Env

env = Env()
env.read_env()

BOT_TOKEN = env.str("BOT_TOKEN")
ADMINS = env.list("ADMINS")

DB_USER = env.str("DB_USER")
DB_PASS = env.str("DB_PASS")
DB_NAME = env.str("DB_NAME")
DB_HOST = env.str("DB_HOST")
DB_PORT = env.str("DB_PORT")

REDIS_URL = env.str("REDIS_URL", "redis://redis:6379/0")

# Local Telegram Bot API (for 2GB uploads). If set, bot uses local server.
# Get from https://my.telegram.org/apps
TELEGRAM_API_ID = env.int("TELEGRAM_API_ID", 0)
TELEGRAM_API_HASH = env.str("TELEGRAM_API_HASH", "")
BOT_API_URL = env.str("BOT_API_URL", "")  # e.g. http://bot_api:8081

# File size cap (MB). 50 = default Telegram API; ~1950 = local Bot API max.
MAX_FILE_SIZE_MB = env.int("MAX_FILE_SIZE_MB", 50)
DOWNLOAD_DIR = env.str("DOWNLOAD_DIR", "downloads")

# Cache TTL for url→file_id (seconds). Default 7 days.
CACHE_TTL = env.int("CACHE_TTL", 60 * 60 * 24 * 7)

PAYMENT_CARD = env.str("PAYMENT_CARD", "8600 0000 0000 0000")
PAYMENT_OWNER = env.str("PAYMENT_OWNER", "Palonchiyev Pistonchi")
DOC_PRICE = env.int("DOC_PRICE", 15000)
