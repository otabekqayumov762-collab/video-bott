import asyncio
import logging
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from loader import db, bot
from filters.admin import IsBotAdminFilter
from states import AdminStates
from keyboards.reply import admin_menu, main_menu, cancel_keyboard
from keyboards.inline import channel_delete_keyboard
from data.config import ADMINS

router = Router()
logger = logging.getLogger(__name__)

admin_filter = IsBotAdminFilter(ADMINS)


# ─── BEKOR QILISH (barcha admin state'lar uchun) ─────────────

@router.message(F.text == "❌ Bekor qilish", admin_filter)
async def admin_cancel(message: types.Message, state: FSMContext):
    current = await state.get_state()
    if current and current.startswith("AdminStates"):
        await state.clear()
        await message.answer("❌ Bekor qilindi.", reply_markup=admin_menu())
    else:
        await state.clear()
        await message.answer("❌ Bekor qilindi.", reply_markup=main_menu())


# ─── ADMIN MENU ──────────────────────────────────────────────

@router.message(Command("admin"), admin_filter)
async def admin_start(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("🔐 <b>Admin panel</b>", reply_markup=admin_menu())


@router.message(F.text == "🏠 Asosiy menyu", admin_filter)
async def back_to_main(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Asosiy menyu:", reply_markup=main_menu())


# ─── STATISTIKA ──────────────────────────────────────────────

@router.message(F.text == "📊 Statistika", admin_filter)
async def show_stats(message: types.Message):
    total_users = await db.count_users()
    total_dl = await db.count_total_downloads()
    today_dl = await db.count_today_downloads()
    today_pays = await db.count_today_payments()
    today_sum = await db.sum_today_payments()
    total_sum = await db.sum_all_payments()

    await message.answer(
        f"📊 <b>Statistika</b>\n\n"
        f"👥 Jami foydalanuvchilar: <b>{total_users}</b>\n"
        f"🎬 Jami yuklab olishlar: <b>{total_dl}</b>\n"
        f"📥 Bugungi yuklab olishlar: <b>{today_dl}</b>\n\n"
        f"✅ Bugungi tasdiqlangan to'lovlar: <b>{today_pays}</b>\n"
        f"💰 Bugungi tushum: <b>{today_sum:,} so'm</b>\n"
        f"💎 Jami tushum: <b>{total_sum:,} so'm</b>"
    )


# ─── BROADCAST ───────────────────────────────────────────────

@router.message(F.text == "📢 Xabar yuborish", admin_filter)
async def ask_broadcast(message: types.Message, state: FSMContext):
    await message.answer(
        "📢 Barcha foydalanuvchilarga yubormoqchi bo'lgan xabarni yuboring\n"
        "(matn, rasm yoki video):",
        reply_markup=cancel_keyboard()
    )
    await state.set_state(AdminStates.broadcast)


@router.message(AdminStates.broadcast, admin_filter, ~F.text.in_(["❌ Bekor qilish", "🏠 Asosiy menyu"]))
async def send_broadcast(message: types.Message, state: FSMContext):
    await state.clear()
    users = await db.get_all_users()
    success = 0
    fail = 0
    status_msg = await message.answer(f"📤 Yuborilmoqda... 0/{len(users)}")

    for i, user in enumerate(users):
        try:
            await message.send_copy(chat_id=user['tg_id'])
            success += 1
            await asyncio.sleep(0.05)
        except Exception:
            fail += 1
        if (i + 1) % 50 == 0:
            try:
                await status_msg.edit_text(f"📤 Yuborilmoqda... {i+1}/{len(users)}")
            except Exception:
                pass

    await status_msg.edit_text(
        f"✅ Xabar yuborildi!\n"
        f"✅ Muvaffaqiyatli: {success}\n"
        f"❌ Muvaffaqiyatsiz: {fail}"
    )
    await message.answer("Admin panel:", reply_markup=admin_menu())


# ─── KANAL SOZLAMALARI ───────────────────────────────────────

@router.message(F.text == "🔗 Obuna sozlamalari", admin_filter)
async def channel_settings(message: types.Message, state: FSMContext):
    channels = await db.get_all_channels()
    if channels:
        ch_list = "\n".join([f"• {ch['name']} — {ch['url']}" for ch in channels])
        text = f"📋 <b>Kanallar ro'yxati:</b>\n{ch_list}\n\n"
    else:
        text = "📭 Hozircha kanallar yo'q.\n\n"

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    back_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="admin_back")]
    ])

    text += (
        "➕ Yangi kanal qo'shish uchun:\n"
        "• Kanal username: <code>@mening_kanalim</code>\n"
        "• Yoki link: <code>https://t.me/mening_kanalim</code>\n"
        "• Yoki kanal ID: <code>-1001234567890</code>\n\n"
        "⚠️ Bot kanalda <b>admin</b> bo'lishi kerak!"
    )
    if channels:
        await message.answer(text, reply_markup=channel_delete_keyboard(channels))
    else:
        await message.answer(text, reply_markup=back_kb)
    await state.set_state(AdminStates.add_channel)


@router.message(AdminStates.add_channel, admin_filter,
                ~F.text.in_(["❌ Bekor qilish", "🏠 Asosiy menyu"]),
                ~F.text.startswith("/"))
async def add_channel(message: types.Message, state: FSMContext):
    text = message.text.strip() if message.text else ""

    if text.startswith("https://t.me/"):
        text = "@" + text.replace("https://t.me/", "").split("/")[0]
    elif text.startswith("t.me/"):
        text = "@" + text.replace("t.me/", "").split("/")[0]

    if not text:
        await message.answer("❌ Kanal username yoki ID yuboring.")
        return

    try:
        chat = await bot.get_chat(text)
    except Exception:
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        await message.answer(
            f"❌ <b>Kanal topilmadi:</b> <code>{text}</code>\n\n"
            "Tekshiring:\n"
            "1. Bot kanalda <b>admin</b> bo'lishi kerak\n"
            "2. Username to'g'ri bo'lishi kerak\n\n"
            "Qaytadan yuboring:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="admin_back")]
            ])
        )
        return

    channel_id = chat.id
    name = chat.title or chat.username or str(channel_id)

    if chat.username:
        url = f"https://t.me/{chat.username}"
    else:
        url = f"https://t.me/c/{str(channel_id).replace('-100', '')}"

    await db.add_channel(channel_id=channel_id, url=url, name=name)
    await state.clear()
    await message.answer(
        f"✅ Kanal qo'shildi!\n\n"
        f"📛 Nomi: <b>{name}</b>\n"
        f"🔗 Link: {url}\n"
        f"🆔 ID: <code>{channel_id}</code>",
        reply_markup=admin_menu()
    )


@router.callback_query(F.data.startswith("del_ch:"), admin_filter)
async def delete_channel(call: types.CallbackQuery, state: FSMContext):
    channel_id = int(call.data.split(":")[1])
    await db.delete_channel(channel_id=channel_id)
    await call.answer("✅ Kanal o'chirildi!")
    channels = await db.get_all_channels()
    if channels:
        await call.message.edit_reply_markup(reply_markup=channel_delete_keyboard(channels))
    else:
        await call.message.edit_reply_markup(reply_markup=None)


@router.callback_query(F.data == "admin_back", admin_filter)
async def admin_back_callback(call: types.CallbackQuery, state: FSMContext):
    await state.clear()
    try:
        await call.message.delete()
    except Exception:
        pass
    await call.message.answer("Admin panel:", reply_markup=admin_menu())


# ─── KARTA RAQAMI ────────────────────────────────────────────

@router.message(F.text == "💳 Karta raqami", admin_filter)
async def ask_card(message: types.Message, state: FSMContext):
    pay_info = await db.get_payment_info()
    await message.answer(
        f"💳 <b>Joriy karta:</b> <code>{pay_info['card']}</code>\n"
        f"👤 <b>Egasi:</b> {pay_info['owner']}\n\n"
        "Yangi karta ma'lumotlarini kiriting (format):\n"
        "<code>karta raqami|karta egasi</code>\n\n"
        "Masalan: <code>8600 1234 5678 9012|Aliyev Vali</code>",
        reply_markup=cancel_keyboard()
    )
    await state.set_state(AdminStates.set_card)


@router.message(AdminStates.set_card, admin_filter, ~F.text.in_(["❌ Bekor qilish", "🏠 Asosiy menyu"]))
async def set_card(message: types.Message, state: FSMContext):
    if message.text and "|" in message.text:
        parts = message.text.split("|", 1)
        card = parts[0].strip()
        owner = parts[1].strip()
        await db.set_setting('payment_card', card)
        await db.set_setting('payment_owner', owner)
        await state.clear()
        await message.answer(
            f"✅ Karta yangilandi!\n"
            f"Karta: <code>{card}</code>\n"
            f"Egasi: <b>{owner}</b>",
            reply_markup=admin_menu()
        )
    else:
        await message.answer("❌ Noto'g'ri format! <code>karta raqami|karta egasi</code>")


# ─── TO'LOV HOLATI TOGGLE ────────────────────────────────────

@router.message(F.text == "💰 To'lov holati", admin_filter)
async def toggle_payment(message: types.Message):
    current = await db.get_setting('payment_enabled')
    if current is None or current == '1':
        await db.set_setting('payment_enabled', '0')
        await message.answer(
            "🔴 <b>To'lov tizimi o'chirildi!</b>\n\n"
            "Foydalanuvchilar botdan <b>bepul</b> foydalanishadi.\n"
            "Qayta yoqish uchun «💰 To'lov holati» tugmasini bosing.",
            reply_markup=admin_menu()
        )
    else:
        await db.set_setting('payment_enabled', '1')
        await message.answer(
            "🟢 <b>To'lov tizimi yoqildi!</b>",
            reply_markup=admin_menu()
        )


# ─── NARX ────────────────────────────────────────────────────

@router.message(F.text == "💵 Narxni belgilash", admin_filter)
async def ask_price(message: types.Message, state: FSMContext):
    pay_info = await db.get_payment_info()
    await message.answer(
        f"💵 <b>Joriy narx:</b> {pay_info['price']:,} so'm\n\n"
        "Yangi narxni kiriting (faqat raqam, so'mda):",
        reply_markup=cancel_keyboard()
    )
    await state.set_state(AdminStates.set_price)


@router.message(AdminStates.set_price, admin_filter, ~F.text.in_(["❌ Bekor qilish", "🏠 Asosiy menyu"]))
async def set_price(message: types.Message, state: FSMContext):
    if message.text and message.text.isdigit():
        price = int(message.text)
        await db.set_setting('doc_price', str(price))
        await state.clear()
        await message.answer(
            f"✅ Narx yangilandi: <b>{price:,} so'm</b>",
            reply_markup=admin_menu()
        )
    else:
        await message.answer("❌ Faqat raqam kiriting! Masalan: <code>15000</code>")


# ─── START MATNI ─────────────────────────────────────────────

@router.message(F.text == "📝 Start matni", admin_filter)
async def ask_start_text(message: types.Message, state: FSMContext):
    current = await db.get_setting('start_text') or ""
    await message.answer(
        f"📝 <b>Joriy start matni:</b>\n\n<blockquote>{current}</blockquote>\n\n"
        "Yangi matnni kiriting.\n"
        "<i>Foydalanuvchi ismi uchun: <code>{name}</code></i>",
        reply_markup=cancel_keyboard()
    )
    await state.set_state(AdminStates.set_start_text)


@router.message(AdminStates.set_start_text, admin_filter, ~F.text.in_(["❌ Bekor qilish", "🏠 Asosiy menyu"]))
async def save_start_text(message: types.Message, state: FSMContext):
    await db.set_setting('start_text', message.text)
    await state.clear()
    await message.answer("✅ Start matni yangilandi!", reply_markup=admin_menu())


# ─── HELP MATNI ──────────────────────────────────────────────

@router.message(F.text == "❓ Help matni", admin_filter)
async def ask_help_text(message: types.Message, state: FSMContext):
    current = await db.get_setting('help_text') or ""
    await message.answer(
        f"❓ <b>Joriy help matni:</b>\n\n<blockquote>{current}</blockquote>\n\n"
        "Yangi matnni kiriting:",
        reply_markup=cancel_keyboard()
    )
    await state.set_state(AdminStates.set_help_text)


@router.message(AdminStates.set_help_text, admin_filter, ~F.text.in_(["❌ Bekor qilish", "🏠 Asosiy menyu"]))
async def save_help_text(message: types.Message, state: FSMContext):
    await db.set_setting('help_text', message.text)
    await state.clear()
    await message.answer("✅ Help matni yangilandi!", reply_markup=admin_menu())
