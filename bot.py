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
BOSH_HR_ID = int(os.environ["BOSH_HR_ID"])

logging.basicConfig(format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# Conversation steps
STEP_FISH, STEP_TELEFON, STEP_MAVZU, STEP_XABAR = range(4)

MAVZULAR = {
    "ish_haqi":  "Ish haqi masalalari",
    "hujjat":    "Hujjatlar va ma'lumotnoma",
    "shikoyat":  "Shikoyat va takliflar",
    "boshqa":    "Boshqa",
}

HOLATLAR = {
    "yangi":     "Yangi",
    "korildi":   "Ko'rildi",
    "jarayonda": "Jarayonda",
    "hal":       "Hal qilindi",
    "rad":       "Rad qilindi",
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
            InlineKeyboardButton("Ko'rildi",    callback_data=f"holat_korildi_{raqam}"),
            InlineKeyboardButton("Jarayonda",   callback_data=f"holat_jarayonda_{raqam}"),
        ],
        [
            InlineKeyboardButton("Hal qilindi", callback_data=f"holat_hal_{raqam}"),
            InlineKeyboardButton("Rad qilish",  callback_data=f"rad_{raqam}"),
        ],
        [
            InlineKeyboardButton("Javob berish", callback_data=f"javob_{raqam}"),
        ],
    ])


def hr_murojaat_matni(m: dict) -> str:
    holat = HOLATLAR.get(m["holat"], m["holat"])
    matn = (
        f"Murojaat {m['raqam']}\n"
        f"{'─' * 30}\n"
        f"Sana: {m['yaratilgan'][:16]}\n"
        f"Holat: {holat}\n"
        f"{'─' * 30}\n"
        f"FISH: {m['fish']}\n"
        f"Telefon: {m['telefon']}\n"
        f"Telegram: {m['telegram_ism']}"
        f"{' (@' + m['username'] + ')' if m['username'] else ''}\n"
        f"{'─' * 30}\n"
        f"Mavzu: {m['mavzu']}\n\n"
        f"Xabar:\n{m['matn']}"
    )
    if m.get("javob"):
        matn += f"\n{'─' * 30}\nJavob:\n{m['javob']}"
    return matn


def user_murojaat_matni(m: dict) -> str:
    holat = HOLATLAR.get(m["holat"], m["holat"])
    matn = (
        f"Murojaat {m['raqam']}\n"
        f"{'─' * 30}\n"
        f"Yuborilgan sana: {m['yaratilgan'][:16]}\n"
        f"Yangilangan: {m['yangilangan'][:16]}\n"
        f"Holat: {holat}\n"
        f"{'─' * 30}\n"
        f"Mavzu: {m['mavzu']}\n\n"
        f"Sizning xabaringiz:\n{m['matn']}"
    )
    if m.get("javob"):
        matn += f"\n{'─' * 30}\nHR javobi:\n{m['javob']}"
    return matn


async def hr_larga_yuborish(bot, matn: str, keyboard=None):
    xodimlar = hr_royxat()
    ids = {BOSH_HR_ID} | {x["user_id"] for x in xodimlar}
    for uid in ids:
        try:
            await bot.send_message(chat_id=uid, text=matn, reply_markup=keyboard)
        except Exception as e:
            logger.warning("HR ga yuborishda xato (ID %s): %s", uid, e)


# ─── FOYDALANUVCHI — MUROJAAT JARAYONI ───────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "Salom!\n\n"
        "HR bo'limiga murojaat qilish uchun /murojaat buyrug'ini yuboring.\n"
        "Murojaatlaringizni ko'rish uchun /murojaatlarim buyrug'ini yuboring."
    )


async def murojaat_boshlash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    context.user_data["step"] = STEP_FISH
    await update.message.reply_text(
        "Murojaat qilish uchun bir necha savol:\n\n"
        "1/4 — Familiya Ism Sharifingizni kiriting:\n"
        "(Masalan: Karimov Sardor Aliyevich)\n\n"
        "/bekor — bekor qilish"
    )


async def mening_murojaatlarim(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    murojaatlar = foydalanuvchi_murojaatlari(user_id)
    if not murojaatlar:
        await update.message.reply_text(
            "Sizda hali murojaatlar yo'q.\n\n"
            "Murojaat qilish uchun /murojaat yuboring."
        )
        return

    keyboard = []
    for m in murojaatlar:
        holat = HOLATLAR.get(m["holat"], m["holat"])
        tugma = f"{holat} | {m['raqam']} — {m['mavzu'][:20]}"
        keyboard.append([InlineKeyboardButton(tugma, callback_data=f"men_mko_{m['raqam']}")])

    await update.message.reply_text(
        f"Sizning murojaatlaringiz ({len(murojaatlar)} ta):\n"
        f"Batafsil ko'rish uchun bosing:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def men_murojaat_ko(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    raqam = query.data.replace("men_mko_", "")
    m = murojaat_raqam(raqam)

    if not m or m["user_id"] != query.from_user.id:
        await query.edit_message_text("Murojaat topilmadi.")
        return

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Orqaga", callback_data="men_orqaga")]
    ])
    await query.edit_message_text(user_murojaat_matni(m), reply_markup=keyboard)


async def men_orqaga_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    murojaatlar = foydalanuvchi_murojaatlari(query.from_user.id)
    keyboard = []
    for m in murojaatlar:
        holat = HOLATLAR.get(m["holat"], m["holat"])
        tugma = f"{holat} | {m['raqam']} — {m['mavzu'][:20]}"
        keyboard.append([InlineKeyboardButton(tugma, callback_data=f"men_mko_{m['raqam']}")])

    await query.edit_message_text(
        f"Sizning murojaatlaringiz ({len(murojaatlar)} ta):",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def mavzu_tanlandi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    kalit = query.data.replace("mvz_", "")
    if kalit not in MAVZULAR:
        return
    context.user_data["mavzu"] = MAVZULAR[kalit]
    context.user_data["step"] = STEP_XABAR
    await query.edit_message_text(
        f"Mavzu: {MAVZULAR[kalit]}\n\n"
        f"4/4 — Murojaatingizni batafsil yozing:\n\n"
        f"/bekor — bekor qilish"
    )


async def xabar_dispatcher(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    # HR javob berish
    if context.user_data.get("javob_kutilmoqda") and is_hr(uid):
        await javob_matn_qabul(update, context)
        return

    # HR rad qilish sababi
    if context.user_data.get("rad_kutilmoqda") and is_hr(uid):
        await rad_sabab_qabul(update, context)
        return

    # Murojaat jarayoni
    step = context.user_data.get("step")

    if step == STEP_FISH:
        await fish_qabul(update, context)
    elif step == STEP_TELEFON:
        await telefon_qabul(update, context)
    elif step == STEP_XABAR:
        await xabar_qabul(update, context)
    else:
        await update.message.reply_text(
            "Murojaat qilish uchun /murojaat yuboring.\n"
            "Murojaatlaringizni ko'rish uchun /murojaatlarim yuboring."
        )


async def fish_qabul(update: Update, context: ContextTypes.DEFAULT_TYPE):
    fish = update.message.text.strip()
    if len(fish) < 5:
        await update.message.reply_text(
            "Iltimos, to'liq Familiya Ism Sharifingizni kiriting.\n\n"
            "(Masalan: Karimov Sardor Aliyevich)"
        )
        return
    context.user_data["fish"] = fish
    context.user_data["step"] = STEP_TELEFON
    await update.message.reply_text(
        f"FISH: {fish}\n\n"
        f"2/4 — Telefon raqamingizni kiriting:\n"
        f"(Masalan: +998901234567)\n\n"
        f"/bekor — bekor qilish"
    )


async def telefon_qabul(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telefon = update.message.text.strip()
    if len(telefon) < 7:
        await update.message.reply_text(
            "Iltimos, to'g'ri telefon raqam kiriting.\n"
            "(Masalan: +998901234567)"
        )
        return
    context.user_data["telefon"] = telefon
    context.user_data["step"] = STEP_MAVZU
    await update.message.reply_text(
        f"Telefon: {telefon}\n\n"
        f"3/4 — Murojaat mavzusini tanlang:",
        reply_markup=mavzu_keyboard(),
    )


async def xabar_qabul(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("step") != STEP_XABAR:
        return

    foydalanuvchi = update.effective_user
    matn     = update.message.text
    fish     = context.user_data.get("fish", "")
    telefon  = context.user_data.get("telefon", "")
    mavzu    = context.user_data.get("mavzu", "Noma'lum")

    m = murojaat_qoshish(
        user_id      = foydalanuvchi.id,
        telegram_ism = foydalanuvchi.full_name,
        username     = foydalanuvchi.username,
        fish         = fish,
        telefon      = telefon,
        mavzu        = mavzu,
        matn         = matn,
    )
    context.user_data.clear()
    logger.info("Yangi murojaat %s: %s", m["raqam"], fish)

    await update.message.reply_text(
        f"Murojaatingiz qabul qilindi!\n\n"
        f"Murojaat raqami: {m['raqam']}\n"
        f"Yuborilgan sana: {m['yaratilgan'][:16]}\n"
        f"Holat: {HOLATLAR['yangi']}\n\n"
        f"Murojaatlaringizni kuzatish: /murojaatlarim\n\n"
        f"Yana murojaat qilmoqchimisiz? /murojaat"
    )

    await hr_larga_yuborish(
        context.bot,
        hr_murojaat_matni(m),
        holat_keyboard(m["raqam"]),
    )


# ─── HR PANEL ────────────────────────────────────────────────────────────────

async def hr_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_hr(update.effective_user.id):
        await update.message.reply_text("Sizda ruxsat yo'q.")
        return

    murojaatlar = barcha_murojaatlar()
    yangi   = sum(1 for m in murojaatlar if m["holat"] == "yangi")
    jarayon = sum(1 for m in murojaatlar if m["holat"] == "jarayonda")
    hal     = sum(1 for m in murojaatlar if m["holat"] == "hal")
    rad     = sum(1 for m in murojaatlar if m["holat"] == "rad")

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"Yangi ({yangi})",          callback_data="hr_list_yangi"),
         InlineKeyboardButton(f"Jarayonda ({jarayon})",    callback_data="hr_list_jarayonda")],
        [InlineKeyboardButton(f"Hal qilingan ({hal})",     callback_data="hr_list_hal"),
         InlineKeyboardButton(f"Rad qilingan ({rad})",     callback_data="hr_list_rad")],
        [InlineKeyboardButton(f"Hammasi ({len(murojaatlar)})", callback_data="hr_list_all")],
        [InlineKeyboardButton("HR xodimlar",               callback_data="hr_xodimlar")],
    ])

    await update.message.reply_text(
        "HR Panel\n\nMurojaatlar statistikasi:",
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
        await query.edit_message_text(
            "Bu holatta murojaatlar yo'q.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("Orqaga", callback_data="hr_orqaga")
            ]])
        )
        return

    keyboard = []
    for m in murojaatlar[:20]:
        holat_nomi = HOLATLAR.get(m["holat"], "")
        tugma = f"{holat_nomi} | {m['raqam']} — {m['fish'][:20]}"
        keyboard.append([InlineKeyboardButton(tugma, callback_data=f"mko_{m['raqam']}")])
    keyboard.append([InlineKeyboardButton("Orqaga", callback_data="hr_orqaga")])

    await query.edit_message_text(
        f"Murojaatlar ({len(murojaatlar)} ta):",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def murojaat_ko(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not is_hr(query.from_user.id):
        return

    raqam = query.data.replace("mko_", "")
    m = murojaat_raqam(raqam)
    if not m:
        await query.edit_message_text("Murojaat topilmadi.")
        return

    kb = holat_keyboard(raqam)
    kb.inline_keyboard.append([InlineKeyboardButton("Orqaga", callback_data="hr_list_all")])
    await query.edit_message_text(hr_murojaat_matni(m), reply_markup=kb)


async def holat_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not is_hr(query.from_user.id):
        return

    parts = query.data.split("_", 2)
    yangi_holat = parts[1]
    raqam = parts[2]

    m = murojaat_raqam(raqam)
    if not m:
        return

    holat_yangilash(raqam, yangi_holat)
    m = murojaat_raqam(raqam)
    holat_nomi = HOLATLAR.get(yangi_holat, yangi_holat)

    await query.edit_message_text(
        hr_murojaat_matni(m),
        reply_markup=holat_keyboard(raqam),
    )

    try:
        await context.bot.send_message(
            chat_id=m["user_id"],
            text=f"Murojaatingiz holati yangilandi!\n\n"
                 f"Raqam: {raqam}\n"
                 f"Mavzu: {m['mavzu']}\n"
                 f"Sana: {m['yaratilgan'][:16]}\n"
                 f"Holat: {holat_nomi}\n\n"
                 f"Batafsil: /murojaatlarim"
        )
    except Exception as e:
        logger.warning("Foydalanuvchiga xabar yuborishda xato: %s", e)


async def rad_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not is_hr(query.from_user.id):
        return

    raqam = query.data.replace("rad_", "")
    context.user_data["rad_raqam"] = raqam
    context.user_data["rad_kutilmoqda"] = True

    m = murojaat_raqam(raqam)
    await query.edit_message_text(
        f"{raqam} ni rad qilish uchun sabab yozing:\n\n"
        f"Murojaat: {m['matn'][:150]}\n\n"
        f"/bekor — bekor qilish"
    )


async def rad_sabab_qabul(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raqam = context.user_data.pop("rad_raqam", None)
    context.user_data.pop("rad_kutilmoqda", None)
    sabab = update.message.text

    if not raqam:
        return

    holat_yangilash(raqam, "rad", sabab)
    m = murojaat_raqam(raqam)
    await update.message.reply_text(f"Murojaat {raqam} rad qilindi.")

    try:
        await context.bot.send_message(
            chat_id=m["user_id"],
            text=f"Murojaatingiz rad qilindi.\n\n"
                 f"Raqam: {raqam}\n"
                 f"Mavzu: {m['mavzu']}\n"
                 f"Sana: {m['yaratilgan'][:16]}\n\n"
                 f"Sabab:\n{sabab}\n\n"
                 f"Batafsil: /murojaatlarim"
        )
    except Exception as e:
        logger.warning("Foydalanuvchiga rad xabari yuborishda xato: %s", e)


async def javob_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        f"Murojaatchi: {m['fish']}\n"
        f"Mavzu: {m['mavzu']}\n"
        f"Xabar: {m['matn'][:150]}\n\n"
        f"/bekor — bekor qilish"
    )


async def javob_matn_qabul(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raqam = context.user_data.pop("javob_raqam", None)
    context.user_data.pop("javob_kutilmoqda", None)
    javob = update.message.text

    if not raqam:
        return

    holat_yangilash(raqam, "hal", javob)
    m = murojaat_raqam(raqam)
    await update.message.reply_text(f"Javob yuborildi! {raqam} — Hal qilindi.")

    try:
        await context.bot.send_message(
            chat_id=m["user_id"],
            text=f"Murojaatingizga HR bo'limidan javob keldi!\n\n"
                 f"Raqam: {raqam}\n"
                 f"Mavzu: {m['mavzu']}\n"
                 f"Yuborilgan sana: {m['yaratilgan'][:16]}\n\n"
                 f"Javob:\n{javob}\n\n"
                 f"Batafsil: /murojaatlarim"
        )
    except Exception as e:
        logger.warning("Foydalanuvchiga javob yuborishda xato: %s", e)


# ─── HR XODIMLAR ─────────────────────────────────────────────────────────────

async def hr_xodimlar_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.from_user.id != BOSH_HR_ID:
        await query.answer("Faqat bosh admin boshqara oladi!", show_alert=True)
        return

    xodimlar = hr_royxat()
    matn = "HR xodimlar:\n\n"
    keyboard = []
    for x in xodimlar:
        matn += f"• {x['ism']} (ID: {x['user_id']})\n"
        keyboard.append([InlineKeyboardButton(
            f"O'chirish: {x['ism']}",
            callback_data=f"hr_del_{x['user_id']}"
        )])
    if not xodimlar:
        matn += "Hozircha qo'shimcha HR xodimlar yo'q.\n"
    matn += "\nYangi HR qo'shish: /hr_qosh <user_id> <ism>"
    keyboard.append([InlineKeyboardButton("Orqaga", callback_data="hr_orqaga")])
    await query.edit_message_text(matn, reply_markup=InlineKeyboardMarkup(keyboard))


async def hr_del_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.from_user.id != BOSH_HR_ID:
        return
    user_id = int(query.data.replace("hr_del_", ""))
    hr_ochirish(user_id)
    await query.edit_message_text("HR xodim o'chirildi.")


async def hr_qosh_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != BOSH_HR_ID:
        await update.message.reply_text("Faqat bosh admin qo'sha oladi.")
        return
    args = context.args
    if not args or len(args) < 2:
        await update.message.reply_text(
            "Foydalanish: /hr_qosh <user_id> <ism>\n\nMasalan: /hr_qosh 123456789 Nilufar"
        )
        return
    try:
        uid = int(args[0])
        ism = " ".join(args[1:])
        hr_qoshish(uid, ism)
        await update.message.reply_text(f"{ism} HR xodimlar ro'yxatiga qo'shildi!")
    except ValueError:
        await update.message.reply_text("User ID raqam bo'lishi kerak.")


async def hr_orqaga_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    murojaatlar = barcha_murojaatlar()
    yangi   = sum(1 for m in murojaatlar if m["holat"] == "yangi")
    jarayon = sum(1 for m in murojaatlar if m["holat"] == "jarayonda")
    hal     = sum(1 for m in murojaatlar if m["holat"] == "hal")
    rad     = sum(1 for m in murojaatlar if m["holat"] == "rad")

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"Yangi ({yangi})",          callback_data="hr_list_yangi"),
         InlineKeyboardButton(f"Jarayonda ({jarayon})",    callback_data="hr_list_jarayonda")],
        [InlineKeyboardButton(f"Hal qilingan ({hal})",     callback_data="hr_list_hal"),
         InlineKeyboardButton(f"Rad qilingan ({rad})",     callback_data="hr_list_rad")],
        [InlineKeyboardButton(f"Hammasi ({len(murojaatlar)})", callback_data="hr_list_all")],
        [InlineKeyboardButton("HR xodimlar",               callback_data="hr_xodimlar")],
    ])

    await query.edit_message_text(
        "HR Panel\n\nMurojaatlar statistikasi:",
        reply_markup=keyboard,
    )


async def bekor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "Bekor qilindi.\n\n"
        "Murojaat qilish uchun /murojaat yuboring."
    )


# ─── MAIN ────────────────────────────────────────────────────────────────────

def main():
    init_db()
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start",         start))
    app.add_handler(CommandHandler("murojaat",      murojaat_boshlash))
    app.add_handler(CommandHandler("murojaatlarim", mening_murojaatlarim))
    app.add_handler(CommandHandler("hr",            hr_panel))
    app.add_handler(CommandHandler("hr_qosh",       hr_qosh_command))
    app.add_handler(CommandHandler("bekor",         bekor))

    app.add_handler(CallbackQueryHandler(mavzu_tanlandi,       pattern="^mvz_"))
    app.add_handler(CallbackQueryHandler(hr_list_callback,     pattern="^hr_list_"))
    app.add_handler(CallbackQueryHandler(murojaat_ko,          pattern="^mko_"))
    app.add_handler(CallbackQueryHandler(holat_callback,       pattern="^holat_"))
    app.add_handler(CallbackQueryHandler(rad_callback,         pattern="^rad_"))
    app.add_handler(CallbackQueryHandler(javob_callback,       pattern="^javob_"))
    app.add_handler(CallbackQueryHandler(hr_xodimlar_callback, pattern="^hr_xodimlar$"))
    app.add_handler(CallbackQueryHandler(hr_del_callback,      pattern="^hr_del_"))
    app.add_handler(CallbackQueryHandler(hr_orqaga_callback,   pattern="^hr_orqaga$"))
    app.add_handler(CallbackQueryHandler(men_murojaat_ko,      pattern="^men_mko_"))
    app.add_handler(CallbackQueryHandler(men_orqaga_callback,  pattern="^men_orqaga$"))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, xabar_dispatcher))

    logger.info("HR Bot ishga tushdi")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
