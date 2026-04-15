from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.telegram import TelegramAPIServer
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums.parse_mode import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from utils.db.postgres import Database
from utils.cache import Cache
from data.config import BOT_TOKEN, BOT_API_URL


def _make_session() -> AiohttpSession | None:
    if not BOT_API_URL:
        return None
    api_server = TelegramAPIServer.from_base(BOT_API_URL, is_local=True)
    return AiohttpSession(api=api_server)


db = Database()
cache = Cache()

_session = _make_session()
bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    session=_session,
)

storage = MemoryStorage()
dispatcher = Dispatcher(storage=storage)
