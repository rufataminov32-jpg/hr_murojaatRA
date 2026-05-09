import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters,
)
from database import (
    init_db, murojaat_qoshish, murojaat_raqam, holat_yangilash,
    barcha_murojaatlar, foydalanuvchi_murojaatlari,
    hr_qoshish, hr_ochirish, hr_royxat, hr_bormi,
)

# ─── SOZLAMALAR ──────────────────────────────────────────────────────────────

TOKEN      = os.environ["BOT_TOKEN"]
BOSH_HR_ID = int(os.environ["BOSH_HR_ID"])   # Siz — asosiy admin

logging.basicConfig(format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

MAVZULAR = {
    "ish_haqi":  "💰 Ish haqi masalalari",
    "hujjat":    "📄 Hujjatlar va ma'lumotnoma",
    "shikoyat":  "📢 Shikoyat va takliflar",
    "boshqa":    "💬 Boshqa",
}

HOLATLAR = {
    "yangi":      "🆕 Yangi",
    "korildi":    "👁 Ko'rildi",
    "jarayonda":  "⏳ Jarayonda",
    "hal":        "✅ Hal qilindi",
}


# ─── YORDAMCHI ───────────────────────────────────────────────────────────────

def is_hr(user_id: int) -> bool:
    return user_id == BOSH_HR_ID or hr_bormi(user_id)


def mavzu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(nom, callback_data=f"mvz_{k}")]
        for k, nom in MAVZULAR.items()
    ])


def holat_keyboard(raqam: str):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("👁 Ko'rildi",    callback_data=f"holat_korildi_{raqam}"),
            InlineKeyboardButton("⏳ Jarayonda",   callback_data=f"holat_jarayonda_{raqam}"),
        ],
        [
            InlineKeyboardButton("✅ Hal qilindi", callback_data=f"holat_hal_{raqam}"),
            InlineKeyboardButton("💬 Javob berish",callback_data=f"javob_{raqam}"),
        ],
    ])


def murojaat_matni(m: dict, hr_uchun: bool = True) -> str:
    holat = HOLATLAR.get(m["holat"], m["holat"])
    matn = (
        f"📋 Murojaat {m['raqam']}\n"
        f"📌 Mavzu: {m['mavzu']}\n"
        f"🕐 Sana: {m['yaratilgan'][:16]}\n"
        f"📊 Holat: {holat}\n"
    )
    if hr_uchun:
        matn += (
            f"\n👤 {m['ism']}"
            f"{' (@' + m['username'] + ')' if m['username'] else ''}\n"
            f"🆔 ID: {m['user_id']}\n"
        )
    matn += f"\n💬 Xabar:\n{m['matn']}"
    if m.get("javob"):
        matn += f"\n\n📩 Javob:\n{m['javob']}"
    return matn


async def hr_larga_yuborish(bot, matn: str, keyboard=None):
    """Barcha HR xodimlarga xabar yuborish"""
    xodimlar = hr_royxat()
    ids = {BOSH_HR_ID} | {x["user_id"] for x in xodimlar}
    for uid in ids:
        try:
            await bot.send_message(chat_id=uid, text=matn, reply_markup=keyboard)
        except Exception as e:
            logger.warning("HR ga yuborishda xato (ID %s): %s", uid, e)


# ─── FOYDALANUVCHI ───────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "Salom! 👋\n\nHR bo'limiga murojaat qilish uchun mavzuni tanlang:",
        reply_markup=mavzu_keyboard(),
    )


async def mening_murojaatlarim(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    murojaatlar = foydalanuvchi_murojaatlari(user_id)
    if not murojaatlar:
        await update.message.reply_text("Sizda hali murojaatlar yo'q.")
        return
    matn = "📋 Sizning so'nggi murojaatlaringiz:\n\n"
    for m in murojaatlar:
        holat = HOLATLAR.get(m["holat"], m["holat"])
        matn += f"{m['raqam']} — {m['mavzu']}\n{holat} | {m['yaratilgan'][:16]}\n\n"
    await update.message.reply_text(matn)


async def mavzu_tanlandi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    kalit = query.data.replace("mvz_", "")
    if kalit not in MAVZULAR:
        return
    context.user_data["mavzu"] = MAVZULAR[kalit]
    context.user_data["kutilmoqda"] = True
    await query.edit_message_text(
        f"Mavzu: {MAVZULAR[kalit]}\n\n"
        f"Murojaatingizni yozing. Xabaringiz HR bo'limiga yuboriladi. ✍️",
    )


async def xabar_qabul(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("kutilmoqda"):
        await update.message.reply_text(
            "Murojaat qilish uchun avval mavzuni tanlang 👇",
            reply_markup=mavzu_keyboard(),
        )
        return

    foydalanuvchi = update.effective_user
    mavzu = context.user_data.get("mavzu", "Noma'lum")
    matn  = update.message.text

    ism      = foydalanuvchi.full_name
    username = foydalanuvchi.username
    user_id  = foydalanuvchi.id

    # Bazaga saqlash
    m = murojaat_qoshish(user_id, ism, username, mavzu, matn)
    context.user_data.clear()
    logger.info("Yangi murojaat %s: %s (%s)", m["raqam"], ism, user_id)

    # Foydalanuvchiga tasdiqlash
    await update.message.reply_text(
        f"✅ Murojaatingiz qabul qilindi!\n\n"
        f"Murojaat raqamingiz: {m['raqam']}\n"
        f"Holat: {HOLATLAR['yangi']}\n\n"
        f"Murojaatlaringizni ko'rish: /murojaatlarim\n\n"
        f"Yana murojaat qilmoqchimisiz? Mavzuni tanlang:",
        reply_markup=mavzu_keyboard(),
    )

    # HR larga yuborish
    hr_matn = murojaat_matni(m, hr_uchun=True)
    keyboard = holat_keyboard(m["raqam"])
    await hr_larga_yuborish(context.bot, hr_matn, keyboard)


# ─── HR PANEL ────────────────────────────────────────────────────────────────

async def hr_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_hr(update.effective_user.id):
        await update.message.reply_text("⛔ Sizda ruxsat yo'q.")
        return

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🆕 Yangi",      callback_data="hr_list_yangi"),
         InlineKeyboardButton("⏳ Jarayonda",  callback_data="hr_list_jarayonda")],
        [InlineKeyboardButton("✅ Hal qilingan", callback_data="hr_list_hal"),
         InlineKeyboardButton("📋 Hammasi",    callback_data="hr_list_all")],
        [InlineKeyboardButton("👥 HR xodimlar", callback_data="hr_xodimlar")],
    ])
    murojaatlar = barcha_murojaatlar()
    yangi     = sum(1 for m in murojaatlar if m["holat"] == "yangi")
    jarayon   = sum(1 for m in murojaatlar if m["holat"] == "jarayonda")
    hal       = sum(1 for m in murojaatlar if m["holat"] == "hal")

    await update.message.reply_text(
        f"👨‍💼 HR Panel\n\n"
        f"🆕 Yangi: {yangi}\n"
        f"⏳ Jarayonda: {jarayon}\n"
        f"✅ Hal qilingan: {hal}\n"
        f"📋 Jami: {len(murojaatlar)}",
        reply_markup=keyboard,
    )


async def hr_list_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not is_hr(query.from_user.id):
        return

    data = query.data.replace("hr_list_", "")
    holat = None if data == "all" else data
    murojaatlar = barcha_murojaatlar(holat)

    if not murojaatlar:
        await query.edit_message_text("Bu holatta murojaatlar yo'q.")
        return

    # Har bir murojaatni tugma sifatida ko'rsatish
    keyboard = []
    for m in murojaatlar[:20]:  # Max 20 ta
        holat_emoji = HOLATLAR.get(m["holat"], "")
        tugma_matn = f"{holat_emoji} {m['raqam']} — {m['mavzu'][:25]}"
        keyboard.append([InlineKeyboardButton(tugma_matn, callback_data=f"mko_{m['raqam']}")])
    keyboard.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="hr_orqaga")])

    await query.edit_message_text(
        f"Murojaatlar ({len(murojaatlar)} ta):",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def murojaat_ko(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Murojaat tafsilotlarini ko'rsatish"""
    query = update.callback_query
    await query.answer()

    if not is_hr(query.from_user.id):
        return

    raqam = query.data.replace("mko_", "")
    m = murojaat_raqam(raqam)
    if not m:
        await query.edit_message_text("Murojaat topilmadi.")
        return

    keyboard = holat_keyboard(raqam)
    keyboard.inline_keyboard.append(
        [InlineKeyboardButton("⬅️ Orqaga", callback_data="hr_list_all")]
    )
    await query.edit_message_text(
        murojaat_matni(m, hr_uchun=True),
        reply_markup=keyboard,
    )


async def holat_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not is_hr(query.from_user.id):
        return

    parts = query.data.split("_", 2)  # holat_<holat>_<raqam>
    yangi_holat = parts[1]
    raqam = parts[2]

    m = murojaat_raqam(raqam)
    if not m:
        await query.edit_message_text("Murojaat topilmadi.")
        return

    holat_yangilash(raqam, yangi_holat)
    m = murojaat_raqam(raqam)  # Yangilangan

    holat_nomi = HOLATLAR.get(yangi_holat, yangi_holat)
    await query.edit_message_text(
        f"✅ {raqam} holati: {holat_nomi}\n\n" + murojaat_matni(m, hr_uchun=True),
        reply_markup=holat_keyboard(raqam),
    )

    # Foydalanuvchiga xabar berish
    try:
        await context.bot.send_message(
            chat_id=m["user_id"],
            text=f"📊 Murojaatingiz holati yangilandi!\n\n"
                 f"Raqam: {raqam}\n"
                 f"Mavzu: {m['mavzu']}\n"
                 f"Holat: {holat_nomi}",
        )
    except Exception as e:
        logger.warning("Foydalanuvchiga xabar yuborishda xato: %s", e)


async def javob_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Javob berish tugmasi bosilganda"""
    query = update.callback_query
    await query.answer()

    if not is_hr(query.from_user.id):
        return

    raqam = query.data.replace("javob_", "")
    context.user_data["javob_raqam"] = raqam
    context.user_data["javob_kutilmoqda"] = True

    m = murojaat_raqam(raqam)
    await query.edit_message_text(
        f"{raqam} ga javob yozing:\n\n"
        f"Murojaat: {m['matn'][:100]}...\n\n"
        f"/bekor — bekor qilish",
    )


async def javob_matn_qabul(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """HR javob matnini kiritganda"""
    if not context.user_data.get("javob_kutilmoqda"):
        return
    if not is_hr(update.effective_user.id):
        return

    raqam = context.user_data.pop("javob_raqam", None)
    context.user_data.pop("javob_kutilmoqda", None)
    javob = update.message.text

    if not raqam:
        return

    holat_yangilash(raqam, "hal", javob)
    m = murojaat_raqam(raqam)

    await update.message.reply_text(f"✅ Javob yuborildi! {raqam} holati: Hal qilindi.")

    # Foydalanuvchiga javob yuborish
    try:
        await context.bot.send_message(
            chat_id=m["user_id"],
            text=f"📩 Murojaatingizga HR bo'limidan javob!\n\n"
                 f"Raqam: {raqam}\n"
                 f"Mavzu: {m['mavzu']}\n\n"
                 f"Javob:\n{javob}",
        )
    except Exception as e:
        logger.warning("Foydalanuvchiga javob yuborishda xato: %s", e)


# ─── HR XODIMLAR BOSHQARUVI ──────────────────────────────────────────────────

async def hr_xodimlar_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.from_user.id != BOSH_HR_ID:
        await query.answer("Faqat bosh admin boshqara oladi!", show_alert=True)
        return

    xodimlar = hr_royxat()
    matn = "👥 HR xodimlar:\n\n"
    keyboard = []
    for x in xodimlar:
        matn += f"• {x['ism']} (ID: {x['user_id']})\n"
        keyboard.append([InlineKeyboardButton(
            f"❌ {x['ism']}ni o'chirish",
            callback_data=f"hr_del_{x['user_id']}"
        )])
    if not xodimlar:
        matn += "Hozircha qo'shimcha HR xodimlar yo'q.\n"

    matn += "\nYangi HR xodim qo'shish:\n/hr_qosh <user_id> <ism>"
    keyboard.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="hr_orqaga")])

    await query.edit_message_text(matn, reply_markup=InlineKeyboardMarkup(keyboard))


async def hr_del_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.from_user.id != BOSH_HR_ID:
        return

    user_id = int(query.data.replace("hr_del_", ""))
    hr_ochirish(user_id)
    await query.edit_message_text("✅ HR xodim o'chirildi.")


async def hr_qosh_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != BOSH_HR_ID:
        await update.message.reply_text("⛔ Faqat bosh admin qo'sha oladi.")
        return
    args = context.args
    if not args or len(args) < 2:
        await update.message.reply_text(
            "Foydalanish: /hr_qosh <user_id> <ism>\n\n"
            "Masalan: /hr_qosh 123456789 Nilufar"
        )
        return
    try:
        uid  = int(args[0])
        ism  = " ".join(args[1:])
        hr_qoshish(uid, ism)
        await update.message.reply_text(f"✅ {ism} HR xodimlar ro'yxatiga qo'shildi!")
    except ValueError:
        await update.message.reply_text("❌ User ID raqam bo'lishi kerak.")


async def hr_orqaga_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    murojaatlar = barcha_murojaatlar()
    yangi   = sum(1 for m in murojaatlar if m["holat"] == "yangi")
    jarayon = sum(1 for m in murojaatlar if m["holat"] == "jarayonda")
    hal     = sum(1 for m in murojaatlar if m["holat"] == "hal")

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🆕 Yangi",       callback_data="hr_list_yangi"),
         InlineKeyboardButton("⏳ Jarayonda",   callback_data="hr_list_jarayonda")],
        [InlineKeyboardButton("✅ Hal qilingan", callback_data="hr_list_hal"),
         InlineKeyboardButton("📋 Hammasi",     callback_data="hr_list_all")],
        [InlineKeyboardButton("👥 HR xodimlar", callback_data="hr_xodimlar")],
    ])
    await query.edit_message_text(
        f"👨‍💼 HR Panel\n\n"
        f"🆕 Yangi: {yangi}\n"
        f"⏳ Jarayonda: {jarayon}\n"
        f"✅ Hal qilingan: {hal}\n"
        f"📋 Jami: {len(murojaatlar)}",
        reply_markup=keyboard,
    )


async def bekor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "❌ Bekor qilindi.",
        reply_markup=mavzu_keyboard(),
    )


# ─── MAIN ────────────────────────────────────────────────────────────────────

def main():
    init_db()
    app = ApplicationBuilder().token(TOKEN).build()

    # Buyruqlar
    app.add_handler(CommandHandler("start",          start))
    app.add_handler(CommandHandler("murojaatlarim",  mening_murojaatlarim))
    app.add_handler(CommandHandler("hr",             hr_panel))
    app.add_handler(CommandHandler("hr_qosh",        hr_qosh_command))
    app.add_handler(CommandHandler("bekor",          bekor))

    # Callbacklar
    app.add_handler(CallbackQueryHandler(mavzu_tanlandi,       pattern="^mvz_"))
    app.add_handler(CallbackQueryHandler(hr_list_callback,     pattern="^hr_list_"))
    app.add_handler(CallbackQueryHandler(murojaat_ko,          pattern="^mko_"))
    app.add_handler(CallbackQueryHandler(holat_callback,       pattern="^holat_"))
    app.add_handler(CallbackQueryHandler(javob_callback,       pattern="^javob_"))
    app.add_handler(CallbackQueryHandler(hr_xodimlar_callback, pattern="^hr_xodimlar$"))
    app.add_handler(CallbackQueryHandler(hr_del_callback,      pattern="^hr_del_"))
    app.add_handler(CallbackQueryHandler(hr_orqaga_callback,   pattern="^hr_orqaga$"))

    # Matn xabarlar
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, xabar_dispatcher))

    logger.info("HR Bot v2 ishga tushdi ✅")
    app.run_polling(drop_pending_updates=True)


async def xabar_dispatcher(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Matn xabarlarni to'g'ri handlerga yo'naltirish"""
    if context.user_data.get("javob_kutilmoqda") and is_hr(update.effective_user.id):
        await javob_matn_qabul(update, context)
    else:
        await xabar_qabul(update, context)


if __name__ == "__main__":
    main()
