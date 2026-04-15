from aiogram import Router, types, F
from aiogram.filters import Command

from loader import db

router = Router()

DEFAULT_HELP = (
    "📌 <b>Yordam</b>\n\n"
    "Botdan foydalanish juda oson:\n"
    "1. Instagram, YouTube yoki TikTok'dan video havolasini nusxalang\n"
    "2. Havolani shu botga yuboring\n"
    "3. Bot videoni yuklab beradi\n\n"
    "Muammo bo'lsa admin bilan bog'laning."
)


@router.message(F.text == "🆘 Yordam")
@router.message(Command("help"))
async def bot_help(message: types.Message):
    help_text = await db.get_setting('help_text')
    await message.answer(help_text or DEFAULT_HELP)
