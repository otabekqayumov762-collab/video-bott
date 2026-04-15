import logging
import os

from aiogram import Router, types, F, Bot
from aiogram.types import FSInputFile

from loader import db, bot
from keyboards.reply import main_menu
from keyboards.inline import subscription_keyboard
from utils.downloader import download_media, is_supported_url, detect_platform
from handlers.users.start import check_subscription
from data.config import MAX_FILE_SIZE_MB

router = Router()
logger = logging.getLogger(__name__)


@router.message(F.text & ~F.text.startswith("/"))
async def handle_link(message: types.Message):
    text = (message.text or "").strip()

    # Reserved menu / button texts — ignore here so admin/help handlers run
    reserved = {
        "🆘 Yordam", "❌ Bekor qilish", "🏠 Asosiy menyu",
        "📊 Statistika", "📢 Xabar yuborish", "🔗 Obuna sozlamalari",
        "💳 Karta raqami", "💵 Narxni belgilash", "💰 To'lov holati",
        "📝 Start matni", "❓ Help matni",
    }
    if text in reserved:
        return

    url = is_supported_url(text)
    if not url:
        await message.answer(
            "❌ Havola topilmadi.\n\n"
            "Iltimos, Instagram, YouTube yoki TikTok video havolasini yuboring.",
            reply_markup=main_menu(),
        )
        return

    # Subscription check
    not_sub = await check_subscription(message.from_user.id, bot)
    if not_sub:
        await message.answer(
            "Avval quyidagi kanallarga a'zo bo'ling:",
            reply_markup=subscription_keyboard(not_sub),
        )
        return

    # Ensure user exists in DB
    user = await db.get_user(message.from_user.id)
    if not user:
        user = await db.add_user(
            tg_id=message.from_user.id,
            fullname=message.from_user.full_name,
            username=message.from_user.username,
        )

    platform = detect_platform(url)
    dl_record = await db.create_download(user_id=user['id'], url=url, platform=platform)

    status = await message.answer("⏳ Yuklanmoqda... biroz kuting.")

    try:
        await bot.send_chat_action(message.chat.id, "upload_video")
    except Exception:
        pass

    result = await download_media(url)

    if not result.ok:
        await db.update_download_status(dl_record['id'], 'failed', error_text=result.error)
        try:
            await status.edit_text(f"❌ {result.error}")
        except Exception:
            await message.answer(f"❌ {result.error}")
        return

    file_path = result.file_path
    caption = (
        f"🎬 <b>{result.title or 'Video'}</b>\n"
        f"📥 @{(await bot.me()).username}"
    )

    sent_msg = None
    try:
        media = FSInputFile(file_path)
        if result.is_audio:
            sent_msg = await message.answer_audio(
                audio=media,
                caption=caption,
                title=result.title or None,
                duration=result.duration or None,
            )
        else:
            sent_msg = await message.answer_video(
                video=media,
                caption=caption,
                duration=result.duration or None,
                width=result.width or None,
                height=result.height or None,
                supports_streaming=True,
            )
        try:
            await status.delete()
        except Exception:
            pass
    except Exception as e:
        logger.exception(f"Send failed: {e}")
        size_mb = 0
        try:
            size_mb = os.path.getsize(file_path) / (1024 * 1024)
        except OSError:
            pass
        err_msg = (
            f"❌ Yuborib bo'lmadi. Fayl hajmi: {size_mb:.1f} MB.\n"
            f"Telegram cheklovi: {MAX_FILE_SIZE_MB} MB."
        )
        try:
            await status.edit_text(err_msg)
        except Exception:
            await message.answer(err_msg)
        await db.update_download_status(dl_record['id'], 'failed', error_text=str(e))
    else:
        tg_file_id = None
        if sent_msg:
            if sent_msg.video:
                tg_file_id = sent_msg.video.file_id
            elif sent_msg.audio:
                tg_file_id = sent_msg.audio.file_id
            elif sent_msg.document:
                tg_file_id = sent_msg.document.file_id
        await db.update_download_status(dl_record['id'], 'success', tg_file_id=tg_file_id)
    finally:
        try:
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
        except OSError:
            pass
