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

MAX_FILE_SIZE_MB = env.int("MAX_FILE_SIZE_MB", 50)
DOWNLOAD_DIR = env.str("DOWNLOAD_DIR", "downloads")

PAYMENT_CARD = env.str("PAYMENT_CARD", "8600 0000 0000 0000")
PAYMENT_OWNER = env.str("PAYMENT_OWNER", "Palonchiyev Pistonchi")
DOC_PRICE = env.int("DOC_PRICE", 15000)
