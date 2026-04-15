import logging
from aiogram import Router, types, F, Bot
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext

from loader import db, bot
from keyboards.reply import main_menu
from keyboards.inline import subscription_keyboard

router = Router()
logger = logging.getLogger(__name__)


async def check_subscription(user_id: int, bot: Bot) -> list:
    try:
        channels = await db.get_active_channels()
    except Exception as e:
        logger.error(f"DB dan kanallarni olishda xato: {e}")
        return []

    if not channels:
        return []

    not_subscribed = []
    for ch in channels:
        try:
            member = await bot.get_chat_member(chat_id=ch['channel_id'], user_id=user_id)
            if member.status in ("left", "kicked", "banned"):
                not_subscribed.append(dict(ch))
        except Exception as e:
            logger.warning(f"Kanal tekshirishda xato ({ch['channel_id']}): {e}")
    return not_subscribed


async def require_subscription(message: types.Message, bot: Bot) -> bool:
    not_sub = await check_subscription(message.from_user.id, bot)
    if not_sub:
        await message.answer(
            "Botdan foydalanish uchun quyidagi kanallarga a'zo bo'ling:",
            reply_markup=subscription_keyboard(not_sub)
        )
        return False
    return True


@router.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    tg_id = message.from_user.id
    fullname = message.from_user.full_name
    username = message.from_user.username

    await db.add_user(tg_id=tg_id, fullname=fullname, username=username)

    not_sub = await check_subscription(tg_id, bot)
    if not_sub:
        await message.answer(
            "Salom! Botdan foydalanish uchun quyidagi kanallarga a'zo bo'ling:",
            reply_markup=subscription_keyboard(not_sub)
        )
        return

    start_text = await db.get_setting('start_text')
    greeting = (
        start_text.replace("{name}", fullname)
        if start_text
        else (
            f"Assalomu alaykum, {fullname}! 👋\n\n"
            "Menga Instagram, YouTube yoki TikTok havolasini yuboring — "
            "men videoni yuklab beraman. 🎬"
        )
    )
    await message.answer(greeting, reply_markup=main_menu())


@router.callback_query(F.data == "check_subscription")
async def check_sub_callback(call: types.CallbackQuery, state: FSMContext):
    not_sub = await check_subscription(call.from_user.id, bot)
    if not_sub:
        await call.answer("Siz hali barcha kanallarga a'zo emassiz!", show_alert=True)
        try:
            await call.message.edit_reply_markup(reply_markup=subscription_keyboard(not_sub))
        except Exception:
            pass
    else:
        try:
            await call.message.delete()
        except Exception:
            pass
        await call.message.answer(
            "Tabriklaymiz! Endi havola yuboring va men videoni yuklab beraman. 🎬",
            reply_markup=main_menu()
        )


@router.message(F.text == "❌ Bekor qilish")
async def cancel_text(message: types.Message, state: FSMContext):
    current = await state.get_state()
    if current and current.startswith("AdminStates"):
        return
    await state.clear()
    await message.answer("Bekor qilindi.", reply_markup=main_menu())
