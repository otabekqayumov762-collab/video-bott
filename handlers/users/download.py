import asyncio
import logging
import os

from aiogram import Router, types, F
from aiogram.types import FSInputFile

from loader import db, bot, cache
from keyboards.reply import main_menu
from keyboards.inline import subscription_keyboard
from utils.downloader import download_media, is_supported_url, detect_platform
from handlers.users.start import check_subscription
from data.config import MAX_FILE_SIZE_MB

router = Router()
logger = logging.getLogger(__name__)


RESERVED_TEXTS = {
    "🆘 Yordam", "❌ Bekor qilish", "🏠 Asosiy menyu",
    "📊 Statistika", "📢 Xabar yuborish", "🔗 Obuna sozlamalari",
    "💳 Karta raqami", "💵 Narxni belgilash", "💰 To'lov holati",
    "📝 Start matni", "❓ Help matni",
}


async def _send_cached(message: types.Message, data: dict, caption: str) -> bool:
    kind = data.get("kind")
    file_id = data.get("file_id")
    if not file_id:
        return False
    try:
        if kind == "audio":
            await message.answer_audio(audio=file_id, caption=caption)
        else:
            await message.answer_video(
                video=file_id,
                caption=caption,
                supports_streaming=True,
            )
        return True
    except Exception as e:
        logger.warning(f"Cached file_id send failed: {e}")
        return False


@router.message(F.text & ~F.text.startswith("/"))
async def handle_link(message: types.Message):
    text = (message.text or "").strip()
    if text in RESERVED_TEXTS:
        return

    url = is_supported_url(text)
    if not url:
        await message.answer(
            "❌ Havola topilmadi.\n\n"
            "Iltimos, Instagram, YouTube yoki TikTok video havolasini yuboring.",
            reply_markup=main_menu(),
        )
        return

    not_sub = await check_subscription(message.from_user.id, bot)
    if not_sub:
        await message.answer(
            "Avval quyidagi kanallarga a'zo bo'ling:",
            reply_markup=subscription_keyboard(not_sub),
        )
        return

    user = await db.get_user(message.from_user.id)
    if not user:
        user = await db.add_user(
            tg_id=message.from_user.id,
            fullname=message.from_user.full_name,
            username=message.from_user.username,
        )

    platform = detect_platform(url)
    me = await bot.me()
    bot_tag = f"@{me.username}"

    # 1) Redis cache — instant send if we've delivered this URL before
    cached = await cache.get_file(url)
    if cached:
        caption = f"🎬 <b>{cached.get('title') or 'Video'}</b>\n📥 {bot_tag}"
        if await _send_cached(message, cached, caption):
            await db.create_download(user_id=user['id'], url=url, platform=platform)
            dl = await db.execute(
                "UPDATE downloads SET status='success', tg_file_id=$1 "
                "WHERE id=(SELECT MAX(id) FROM downloads WHERE user_id=$2 AND url=$3) "
                "RETURNING id",
                cached.get('file_id'), user['id'], url, fetchrow=True
            )
            return

    # 2) Prevent concurrent duplicate downloads for same URL
    got_lock = await cache.acquire_lock(url, ttl=600)
    if not got_lock:
        await asyncio.sleep(1.5)
        cached = await cache.get_file(url)
        if cached:
            caption = f"🎬 <b>{cached.get('title') or 'Video'}</b>\n📥 {bot_tag}"
            if await _send_cached(message, cached, caption):
                return

    dl_record = await db.create_download(user_id=user['id'], url=url, platform=platform)
    status = await message.answer("⏳ Yuklanmoqda... biroz kuting.")
    try:
        await bot.send_chat_action(message.chat.id, "upload_video")
    except Exception:
        pass

    try:
        result = await download_media(url)
    finally:
        await cache.release_lock(url)

    if not result.ok:
        await db.update_download_status(dl_record['id'], 'failed', error_text=result.error)
        try:
            await status.edit_text(result.error or "❌ Yuklab bo'lmadi.")
        except Exception:
            await message.answer(result.error or "❌ Yuklab bo'lmadi.")
        return

    file_path = result.file_path
    caption = f"🎬 <b>{result.title or 'Video'}</b>\n📥 {bot_tag}"

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
        err_msg = (
            f"❌ Yuborib bo'lmadi. Fayl: {result.filesize_mb:.1f} MB.\n"
            f"Limit: {MAX_FILE_SIZE_MB} MB."
        )
        try:
            await status.edit_text(err_msg)
        except Exception:
            await message.answer(err_msg)
        await db.update_download_status(dl_record['id'], 'failed', error_text=str(e))
    else:
        tg_file_id = None
        kind = "video"
        if sent_msg:
            if sent_msg.video:
                tg_file_id = sent_msg.video.file_id
                kind = "video"
            elif sent_msg.audio:
                tg_file_id = sent_msg.audio.file_id
                kind = "audio"
            elif sent_msg.document:
                tg_file_id = sent_msg.document.file_id
                kind = "document"
        await db.update_download_status(dl_record['id'], 'success', tg_file_id=tg_file_id)
        if tg_file_id:
            await cache.set_file(
                url=url,
                file_id=tg_file_id,
                kind=kind,
                title=result.title or "",
                duration=result.duration or 0,
                width=result.width or 0,
                height=result.height or 0,
            )
    finally:
        try:
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
        except OSError:
            pass
