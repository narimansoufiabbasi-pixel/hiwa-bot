# ربات مدیر گروه هیوا - نسخه 4 (نهایی)

import logging
import asyncio
import re
from datetime import datetime, timedelta
from telegram import Update, ChatPermissions, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, ChatMemberHandler,
    CallbackQueryHandler, filters, ContextTypes
)
from telegram.error import TelegramError
import config
import database as db

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================
# توابع کمکی
# ============================================

def is_owner(user_id):
    return user_id == config.ADMIN_ID

async def is_group_admin(context, chat_id, user_id):
    try:
        member = await context.bot.get_chat_member(chat_id, user_id)
        return member.status in ['administrator', 'creator']
    except:
        return False

def get_name(user):
    n = user.first_name or ""
    if user.last_name:
        n += f" {user.last_name}"
    return n

def now_time():
    return datetime.now().strftime("%H:%M")

def now_datetime():
    return datetime.now().strftime("%Y/%m/%d"), datetime.now().strftime("%H:%M")

def is_quiet_time(s):
    now = now_time()
    for i in range(1, 4):
        f = s.get(f'quiet_{i}_from')
        t = s.get(f'quiet_{i}_to')
        if f and t:
            if f <= t:
                if f <= now <= t:
                    return True
            else:
                if now >= f or now <= t:
                    return True
    return False

async def safe_delete(msg):
    try:
        await msg.delete()
    except:
        pass

async def bot_reply(context, chat_id, text, del_sec=0, **kwargs):
    try:
        msg = await context.bot.send_message(chat_id, text, **kwargs)
        if del_sec > 0:
            await asyncio.sleep(del_sec)
            try:
                await msg.delete()
            except:
                pass
        return msg
    except:
        return None

# ============================================
# پنل کاربری - انتخاب گروه
# ============================================

async def show_my_groups(update_or_query, context, user_id, edit=False):
    all_groups = db.get_all_active_groups()
    user_groups = []
    for g in all_groups:
        try:
            member = await context.bot.get_chat_member(g['group_id'], user_id)
            if member.status in ['administrator', 'creator']:
                user_groups.append(g)
        except:
            pass

    if not user_groups:
        text = ("❌ هیچ گروهی پیدا نشد!\n\n"
                "📌 راهنما:\n"
                "۱. ربات را به گروه اضافه کنید\n"
                "۲. به ربات دسترسی ادمین بدهید\n"
                "۳. دوباره /start بزنید")
        if edit:
            await update_or_query.edit_message_text(text)
        else:
            await update_or_query.reply_text(text)
        return

    keyboard = []
    for g in user_groups:
        keyboard.append([InlineKeyboardButton(
            f"🏠 {g.get('group_name', 'نامشخص')}",
            callback_data=f"grp:{g['group_id']}"
        )])
    keyboard.append([InlineKeyboardButton("📖 راهنما", callback_data="help:main")])

    text = "👇 گروه خود را انتخاب کنید:"
    if edit:
        await update_or_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update_or_query.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

# ============================================
# منوهای پنل
# ============================================

async def show_group_menu(query, group_id):
    g = db.get_group(group_id)
    name = g.get('group_name', 'نامشخص') if g else 'نامشخص'
    keyboard = [
        [InlineKeyboardButton("🔒 قفل‌ها", callback_data=f"locks:{group_id}"),
         InlineKeyboardButton("🌙 خاموشی", callback_data=f"quiet:{group_id}")],
        [InlineKeyboardButton("👋 خوش‌آمد", callback_data=f"welcome:{group_id}"),
         InlineKeyboardButton("🚪 پیام خروج", callback_data=f"goodbye:{group_id}")],
        [InlineKeyboardButton("🛡 امنیت", callback_data=f"security:{group_id}"),
         InlineKeyboardButton("⚠️ اخطار", callback_data=f"warn:{group_id}")],
        [InlineKeyboardButton("📨 اد اجباری", callback_data=f"force:{group_id}"),
         InlineKeyboardButton("✅ لیست سفید", callback_data=f"white:{group_id}")],
        [InlineKeyboardButton("🚫 کلمات ممنوعه", callback_data=f"badwords:{group_id}"),
         InlineKeyboardButton("📊 آمار", callback_data=f"stats:{group_id}")],
        [InlineKeyboardButton("⚙️ تنظیمات دیگر", callback_data=f"other:{group_id}")],
        [InlineKeyboardButton("📖 راهنما", callback_data="help:main"),
         InlineKeyboardButton("🔙 برگشت", callback_data="mygroups")],
    ]
    await query.edit_message_text(
        f"⚙️ تنظیمات گروه «{name}»\n\nیک بخش را انتخاب کنید:",
        reply_markup=InlineKeyboardMarkup(keyboard))

async def show_locks(query, group_id):
    s = db.get_settings(group_id)
    g = db.get_group(group_id)
    name = g.get('group_name', 'نامشخص') if g else 'نامشخص'

    def btn(label, key):
        v = s.get(key, 0)
        ico = "🔒" if v else "🔓"
        nv = 0 if v else 1
        return InlineKeyboardButton(f"{ico} {label}", callback_data=f"tog:{group_id}:{key}:{nv}")

    keyboard = [
        [btn("لینک تلگرام", "lock_link"), btn("لینک سایت", "lock_site")],
        [btn("آیدی/منشن", "lock_id"), btn("هشتگ", "lock_hashtag")],
        [btn("عکس", "lock_photo"), btn("فیلم", "lock_video")],
        [btn("استیکر", "lock_sticker"), btn("گیف", "lock_gif")],
        [btn("صدا", "lock_voice"), btn("فایل", "lock_file")],
        [btn("نظرسنجی", "lock_poll"), btn("لوکیشن", "lock_location")],
        [btn("شماره تلفن", "lock_phone"), btn("فوروارد", "lock_forward")],
        [btn("فوروارد کانال", "lock_forward_channel"), btn("متن", "lock_text")],
        [btn("کلمات ممنوعه", "lock_bad_words"), btn("اسلش", "lock_slash")],
        [btn("دستورات عمومی", "public_commands")],
        [btn("🔒 قفل کامل گروه", "group_locked")],
        [InlineKeyboardButton("🔙 برگشت", callback_data=f"grp:{group_id}")],
    ]
    await query.edit_message_text(
        f"🔒 قفل‌های گروه «{name}»\n\n"
        "🔒 = فعال  |  🔓 = غیرفعال\n"
        "روی هر گزینه بزنید تا تغییر کند:",
        reply_markup=InlineKeyboardMarkup(keyboard))

async def show_quiet(query, group_id):
    s = db.get_settings(group_id)
    g = db.get_group(group_id)
    name = g.get('group_name', 'نامشخص') if g else 'نامشخص'
    text = (f"🌙 ساعت خاموشی گروه «{name}»\n\n"
            "📌 در ساعت خاموشی پیام‌های اعضا حذف می‌شود\n\n")
    for i in range(1, 4):
        f = s.get(f'quiet_{i}_from')
        t = s.get(f'quiet_{i}_to')
        if f and t:
            text += f"خاموشی {i}: {f} تا {t} ✅\n"
        else:
            text += f"خاموشی {i}: تنظیم نشده ❌\n"
    text += ("\n📝 برای تنظیم در گروه بنویسید:\n"
             "!خاموشی 1 از 22 تا 8\n\n"
             "برای غیرفعال:\n"
             "!خاموشی 1 غیرفعال")
    keyboard = [[InlineKeyboardButton("🔙 برگشت", callback_data=f"grp:{group_id}")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def show_welcome(query, group_id):
    s = db.get_settings(group_id)
    g = db.get_group(group_id)
    name = g.get('group_name', 'نامشخص') if g else 'نامشخص'
    we = s.get('welcome_enabled', 1)
    wb = s.get('welcome_button', 0)
    wt = s.get('welcome_text', '') or 'پیش‌فرض'

    def tbtn(label, key, val):
        ico = "✅" if val else "❌"
        nv = 0 if val else 1
        return InlineKeyboardButton(f"{ico} {label}", callback_data=f"tog:{group_id}:{key}:{nv}")

    keyboard = [
        [tbtn("پیام خوش‌آمد فعال", "welcome_enabled", we)],
        [tbtn("دکمه 'قوانین را خواندم'", "welcome_button", wb)],
        [InlineKeyboardButton("✏️ تغییر متن", callback_data=f"setwelcome:{group_id}")],
        [InlineKeyboardButton("🔙 برگشت", callback_data=f"grp:{group_id}")],
    ]
    await query.edit_message_text(
        f"👋 پیام خوش‌آمد «{name}»\n\n"
        f"متن فعلی: {wt[:80]}\n\n"
        "📌 متغیرها: {name} = نام کاربر، {group} = نام گروه",
        reply_markup=InlineKeyboardMarkup(keyboard))

async def show_goodbye(query, group_id):
    s = db.get_settings(group_id)
    g = db.get_group(group_id)
    name = g.get('group_name', 'نامشخص') if g else 'نامشخص'
    ge = s.get('goodbye_enabled', 0)
    gt = s.get('goodbye_text', '') or 'پیش‌فرض'

    def tbtn(label, key, val):
        ico = "✅" if val else "❌"
        nv = 0 if val else 1
        return InlineKeyboardButton(f"{ico} {label}", callback_data=f"tog:{group_id}:{key}:{nv}")

    keyboard = [
        [tbtn("پیام خروج فعال", "goodbye_enabled", ge)],
        [InlineKeyboardButton("✏️ تغییر متن", callback_data=f"setgoodbye:{group_id}")],
        [InlineKeyboardButton("🔙 برگشت", callback_data=f"grp:{group_id}")],
    ]
    await query.edit_message_text(
        f"🚪 پیام خروج «{name}»\n\n"
        f"متن فعلی: {gt[:80]}\n\n"
        "📌 وقتی کاربری گروه را ترک کند این پیام فرستاده می‌شود\n"
        "متغیر: {name} = نام کاربر",
        reply_markup=InlineKeyboardMarkup(keyboard))

async def show_security(query, group_id):
    s = db.get_settings(group_id)
    g = db.get_group(group_id)
    name = g.get('group_name', 'نامشخص') if g else 'نامشخص'

    def tbtn(label, key, desc):
        v = s.get(key, 0)
        ico = "✅" if v else "❌"
        nv = 0 if v else 1
        return InlineKeyboardButton(f"{ico} {label}", callback_data=f"tog:{group_id}:{key}:{nv}")

    keyboard = [
        [tbtn("🤖 کپچا ورود", "captcha_enabled", "")],
        [tbtn("🚫 ضد اسپم", "anti_spam", "")],
        [tbtn("⚡ ضد فلود", "anti_flood", "")],
        [tbtn("🛡 ضد ریود", "anti_raid", "")],
        [InlineKeyboardButton("📖 راهنمای امنیت", callback_data="help:security")],
        [InlineKeyboardButton("🔙 برگشت", callback_data=f"grp:{group_id}")],
    ]
    await query.edit_message_text(
        f"🛡 امنیت گروه «{name}»\n\n"
        "✅ = فعال  |  ❌ = غیرفعال\n\n"
        "🤖 کپچا: عضو جدید باید دکمه بزند تا تایید شود\n"
        "🚫 ضد اسپم: پیام‌های فوروارد شده حذف می‌شود\n"
        "⚡ ضد فلود: جلوگیری از ارسال سریع پیام\n"
        "🛡 ضد ریود: جلوگیری از ورود انبوه",
        reply_markup=InlineKeyboardMarkup(keyboard))

async def show_warn(query, group_id):
    s = db.get_settings(group_id)
    g = db.get_group(group_id)
    name = g.get('group_name', 'نامشخص') if g else 'نامشخص'
    auto = s.get('auto_warn', 0)
    limit = s.get('warn_limit', 3)
    action = s.get('warn_action', 'kick')
    action_fa = {'kick': 'اخراج موقت', 'ban': 'بن دائم', 'mute': 'ساکت'}.get(action, action)

    keyboard = [
        [InlineKeyboardButton(
            f"{'✅' if auto else '❌'} اخطار خودکار",
            callback_data=f"tog:{group_id}:auto_warn:{0 if auto else 1}")],
        [InlineKeyboardButton(f"⚠️ حد اخطار: {limit} بار",
            callback_data=f"warnlimit:{group_id}")],
        [InlineKeyboardButton(f"🎯 اقدام بعد از اخطار: {action_fa}",
            callback_data=f"warnaction:{group_id}")],
        [InlineKeyboardButton("📖 راهنما", callback_data="help:warn")],
        [InlineKeyboardButton("🔙 برگشت", callback_data=f"grp:{group_id}")],
    ]
    await query.edit_message_text(
        f"⚠️ تنظیمات اخطار «{name}»\n\n"
        "📌 با فعال کردن اخطار خودکار، بعد از رسیدن به حد اخطار\n"
        "ربات کاربر را مجازات می‌کند\n\n"
        "دستور اخطار دستی: !اخطار (روی پیام ریپلای کنید)",
        reply_markup=InlineKeyboardMarkup(keyboard))

async def show_force(query, group_id):
    s = db.get_settings(group_id)
    g = db.get_group(group_id)
    name = g.get('group_name', 'نامشخص') if g else 'نامشخص'
    fi = s.get('force_invite', 0)
    count = s.get('force_invite_count', 5)
    days = s.get('force_invite_days', 0)
    days_text = f"{days} روز" if days > 0 else "دائمی"

    keyboard = [
        [InlineKeyboardButton(
            f"{'✅' if fi else '❌'} اد اجباری",
            callback_data=f"tog:{group_id}:force_invite:{0 if fi else 1}")],
        [InlineKeyboardButton(f"👥 تعداد اد لازم: {count} نفر",
            callback_data=f"forcecount:{group_id}")],
        [InlineKeyboardButton(f"⏱ مدت اعتبار: {days_text}",
            callback_data=f"forcedays:{group_id}")],
        [InlineKeyboardButton("📖 راهنما", callback_data="help:force")],
        [InlineKeyboardButton("🔙 برگشت", callback_data=f"grp:{group_id}")],
    ]
    await query.edit_message_text(
        f"📨 اد اجباری «{name}»\n\n"
        "📌 اعضای جدید باید تعداد مشخصی نفر اد کنند\n"
        "تا بتوانند پیام بفرستند\n\n"
        "برای معاف کردن: !معاف (روی پیام ریپلای کنید)",
        reply_markup=InlineKeyboardMarkup(keyboard))

async def show_whitelist(query, group_id):
    g = db.get_group(group_id)
    name = g.get('group_name', 'نامشخص') if g else 'نامشخص'
    wl = db.get_whitelist(group_id)
    text = (f"✅ لیست سفید «{name}»\n\n"
            "📌 کاربران لیست سفید از اد اجباری معاف هستند\n\n")
    if wl:
        text += f"اعضای معاف ({len(wl)} نفر):\n"
        for w in wl[:10]:
            text += f"• {w.get('user_name', 'نامشخص')}\n"
    else:
        text += "❌ لیست خالی است\n"
    text += ("\n📝 برای اضافه کردن در گروه:\n"
             "!معاف (روی پیام ریپلای کنید)\n\n"
             "برای حذف:\n"
             "!حذف معاف (روی پیام ریپلای کنید)")
    keyboard = [[InlineKeyboardButton("🔙 برگشت", callback_data=f"grp:{group_id}")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def show_badwords(query, group_id):
    g = db.get_group(group_id)
    name = g.get('group_name', 'نامشخص') if g else 'نامشخص'
    words = db.get_bad_words(group_id)
    text = (f"🚫 کلمات ممنوعه «{name}»\n\n"
            "📌 پیام‌هایی که این کلمات را داشته باشند حذف می‌شوند\n\n")
    if words:
        text += f"کلمات فعلی ({len(words)} کلمه):\n"
        for w in words[:15]:
            text += f"• {w}\n"
    else:
        text += "❌ هیچ کلمه‌ای ثبت نشده\n"
    text += ("\n📝 برای اضافه کردن در گروه:\n"
             "!کلمه ممنوع [کلمه]\n\n"
             "برای حذف:\n"
             "!حذف کلمه [کلمه]")
    keyboard = [[InlineKeyboardButton("🔙 برگشت", callback_data=f"grp:{group_id}")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def show_stats(query, group_id):
    g = db.get_group(group_id)
    name = g.get('group_name', 'نامشخص') if g else 'نامشخص'
    stats = db.get_invite_stats(group_id)
    total = sum(s['count'] for s in stats) if stats else 0
    text = f"📊 آمار گروه «{name}»\n\n👥 کل دعوت‌ها: {total}\n"
    if stats:
        text += "\n🏆 برترین دعوت‌کنندگان:\n"
        for i, s in enumerate(stats[:5], 1):
            text += f"{i}. {s['inviter_name']}: {s['count']} نفر\n"
    keyboard = [[InlineKeyboardButton("🔙 برگشت", callback_data=f"grp:{group_id}")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def show_other(query, group_id):
    s = db.get_settings(group_id)
    g = db.get_group(group_id)
    name = g.get('group_name', 'نامشخص') if g else 'نامشخص'
    gem = s.get('gemini_enabled', 0)
    del_bot = s.get('delete_bot_msg', 0)
    del_sec = s.get('delete_bot_msg_seconds', 30)

    def tbtn(label, key, val):
        ico = "✅" if val else "❌"
        nv = 0 if val else 1
        return InlineKeyboardButton(f"{ico} {label}", callback_data=f"tog:{group_id}:{key}:{nv}")

    keyboard = [
        [tbtn("🤖 هوش مصنوعی Gemini", "gemini_enabled", gem)],
        [tbtn(f"🗑 حذف خودکار پیام ربات ({del_sec}ث)", "delete_bot_msg", del_bot)],
        [InlineKeyboardButton("🔙 برگشت", callback_data=f"grp:{group_id}")],
    ]
    await query.edit_message_text(
        f"⚙️ تنظیمات دیگر «{name}»\n\n"
        "🤖 Gemini: اعضا می‌توانند سوال بپرسند\n"
        "🗑 حذف پیام ربات: پیام‌های ربات بعد از چند ثانیه حذف می‌شوند",
        reply_markup=InlineKeyboardMarkup(keyboard))

# راهنما
HELP = {
    "main": (
        "📖 راهنمای ربات هیوا\n\n"
        "🔒 قفل‌ها — جلوگیری از ارسال انواع محتوا\n"
        "🌙 خاموشی — ساعت‌هایی که گروه ساکت است\n"
        "👋 خوش‌آمد — پیام برای اعضای جدید\n"
        "🚪 پیام خروج — پیام هنگام ترک گروه\n"
        "🛡 امنیت — کپچا، ضد اسپم و فلود\n"
        "⚠️ اخطار — سیستم اخطار خودکار\n"
        "📨 اد اجباری — شرط اد کردن برای پیام\n"
        "✅ لیست سفید — معافیت از اد اجباری\n"
        "🚫 کلمات ممنوعه — حذف کلمات بد\n\n"
        "📝 دستورات ادمین گروه با ! شروع می‌شوند"
    ),
    "security": (
        "🛡 راهنمای امنیت\n\n"
        "🤖 کپچا: عضو جدید باید دکمه بزند تا تایید شود\n"
        "اگر دکمه نزند پیام‌هایش حذف می‌شود\n\n"
        "🚫 ضد اسپم: پیام‌های فوروارد شده حذف می‌شود\n\n"
        "⚡ ضد فلود: اگر کسی در 10 ثانیه بیش از 5 پیام\n"
        "بفرستد 5 دقیقه ساکت می‌شود\n\n"
        "🛡 ضد ریود: در حال توسعه"
    ),
    "warn": (
        "⚠️ راهنمای اخطار\n\n"
        "با فعال کردن اخطار خودکار:\n"
        "بعد از رسیدن به حد اخطار، کاربر مجازات می‌شود\n\n"
        "دستورات:\n"
        "!اخطار — دادن اخطار (ریپلای روی پیام)\n"
        "!ریست — پاک کردن اخطارها\n\n"
        "اقدام‌ها:\n"
        "اخراج موقت — خارج می‌شود ولی می‌تواند برگردد\n"
        "بن دائم — برای همیشه بلاک می‌شود\n"
        "ساکت — نمی‌تواند پیام بدهد"
    ),
    "force": (
        "📨 راهنمای اد اجباری\n\n"
        "اعضای جدید باید تعداد مشخصی نفر اد کنند\n"
        "تا بتوانند پیام بفرستند\n\n"
        "تعداد اد: چند نفر باید اد کنند\n"
        "مدت اعتبار: دائمی یا با تاریخ انقضا\n\n"
        "برای معاف کردن:\n"
        "!معاف (روی پیام کاربر ریپلای کنید)"
    ),
}

# ============================================
# /start
# ============================================

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != 'private':
        return
    user = update.effective_user

    if is_owner(user.id):
        ag = db.get_all_active_groups()
        allg = db.get_all_groups()
        keyboard = [
            [InlineKeyboardButton("📋 لیست گروه‌ها", callback_data="admin:list")],
            [InlineKeyboardButton("📊 آمار کلی", callback_data="admin:stats")],
            [InlineKeyboardButton("📢 پیام به همه", callback_data="admin:broadcast")],
            [InlineKeyboardButton("👤 پنل کاربری", callback_data="mygroups")],
        ]
        await update.message.reply_text(
            f"👋 سلام {get_name(user)}!\n"
            f"🤖 پنل سازنده ربات هیوا\n\n"
            f"✅ فعال: {len(ag)} گروه\n"
            f"📁 کل: {len(allg)} گروه",
            reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await show_my_groups(update.message, context, user.id, edit=False)

# ============================================
# هندلر دکمه‌ها
# ============================================

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    data = query.data

    try:
        # پنل کاربری
        if data == "mygroups":
            await show_my_groups(query, context, user.id, edit=True)

        elif data.startswith("grp:"):
            await show_group_menu(query, int(data.split(":")[1]))

        elif data.startswith("locks:"):
            await show_locks(query, int(data.split(":")[1]))

        elif data.startswith("quiet:"):
            await show_quiet(query, int(data.split(":")[1]))

        elif data.startswith("welcome:"):
            await show_welcome(query, int(data.split(":")[1]))

        elif data.startswith("goodbye:"):
            await show_goodbye(query, int(data.split(":")[1]))

        elif data.startswith("security:"):
            await show_security(query, int(data.split(":")[1]))

        elif data.startswith("warn:"):
            await show_warn(query, int(data.split(":")[1]))

        elif data.startswith("force:"):
            await show_force(query, int(data.split(":")[1]))

        elif data.startswith("white:"):
            await show_whitelist(query, int(data.split(":")[1]))

        elif data.startswith("badwords:"):
            await show_badwords(query, int(data.split(":")[1]))

        elif data.startswith("stats:"):
            await show_stats(query, int(data.split(":")[1]))

        elif data.startswith("other:"):
            await show_other(query, int(data.split(":")[1]))

        elif data.startswith("help:"):
            key = data.split(":")[1]
            text = HELP.get(key, HELP["main"])
            keyboard = [[InlineKeyboardButton("🔙 برگشت", callback_data="mygroups")]]
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

        elif data.startswith("tog:"):
            parts = data.split(":")
            group_id = int(parts[1])
            key = parts[2]
            val = int(parts[3])
            db.update_setting(group_id, key, val)
            # برگشت به صفحه مناسب
            if key.startswith("lock_") or key in ["group_locked", "public_commands"]:
                await show_locks(query, group_id)
            elif key in ["welcome_enabled", "welcome_button"]:
                await show_welcome(query, group_id)
            elif key == "goodbye_enabled":
                await show_goodbye(query, group_id)
            elif key in ["captcha_enabled", "anti_spam", "anti_flood", "anti_raid"]:
                await show_security(query, group_id)
            elif key == "auto_warn":
                await show_warn(query, group_id)
            elif key == "force_invite":
                await show_force(query, group_id)
            elif key in ["gemini_enabled", "delete_bot_msg"]:
                await show_other(query, group_id)

        elif data.startswith("setwelcome:"):
            group_id = int(data.split(":")[1])
            context.user_data['action'] = f'setwelcome:{group_id}'
            await query.edit_message_text(
                "✏️ متن پیام خوش‌آمد را بنویسید:\n\n"
                "متغیرها:\n"
                "{name} = نام کاربر\n"
                "{group} = نام گروه\n\n"
                "برای لغو: /cancel")

        elif data.startswith("setgoodbye:"):
            group_id = int(data.split(":")[1])
            context.user_data['action'] = f'setgoodbye:{group_id}'
            await query.edit_message_text(
                "✏️ متن پیام خروج را بنویسید:\n\n"
                "متغیر: {name} = نام کاربر\n\n"
                "برای لغو: /cancel")

        elif data.startswith("captcha_ok:"):
            parts = data.split(":")
            group_id = int(parts[1])
            user_id = int(parts[2])
            if query.from_user.id == user_id:
                db.remove_captcha_pending(group_id, user_id)
                await query.edit_message_text("✅ تأیید شدید! می‌توانید پیام بفرستید.")
            else:
                await query.answer("این دکمه برای شما نیست!", show_alert=True)

        elif data.startswith("rules_ok:"):
            await query.answer("✅ ممنون! خوش آمدید.", show_alert=True)

        # پنل ادمین (سازنده)
        elif data.startswith("admin:"):
            if not is_owner(user.id):
                await query.answer("❌ دسترسی ندارید!", show_alert=True)
                return
            cmd = data[6:]

            if cmd == "stats":
                ag = db.get_all_active_groups()
                allg = db.get_all_groups()
                keyboard = [[InlineKeyboardButton("🔙 برگشت", callback_data="admin:back")]]
                await query.edit_message_text(
                    f"📊 آمار کلی\n\n"
                    f"📁 کل گروه‌ها: {len(allg)}\n"
                    f"✅ فعال: {len(ag)}\n"
                    f"❌ غیرفعال: {len(allg) - len(ag)}",
                    reply_markup=InlineKeyboardMarkup(keyboard))

            elif cmd == "list":
                allg = db.get_all_groups()
                if not allg:
                    await query.edit_message_text("❌ هیچ گروهی ثبت نشده.",
                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 برگشت", callback_data="admin:back")]]))
                    return
                keyboard = []
                for g in allg[:20]:
                    s = "✅" if g.get('is_active') else "❌"
                    keyboard.append([InlineKeyboardButton(
                        f"{s} {g.get('group_name', 'نامشخص')}",
                        callback_data=f"admin:grp:{g['group_id']}")])
                keyboard.append([InlineKeyboardButton("🔙 برگشت", callback_data="admin:back")])
                await query.edit_message_text("📋 لیست گروه‌ها:", reply_markup=InlineKeyboardMarkup(keyboard))

            elif cmd == "broadcast":
                context.user_data['action'] = 'broadcast'
                await query.edit_message_text(
                    "📢 پیام خود را بنویسید:\n\nبرای لغو: /cancel")

            elif cmd == "back":
                ag = db.get_all_active_groups()
                allg = db.get_all_groups()
                keyboard = [
                    [InlineKeyboardButton("📋 لیست گروه‌ها", callback_data="admin:list")],
                    [InlineKeyboardButton("📊 آمار کلی", callback_data="admin:stats")],
                    [InlineKeyboardButton("📢 پیام به همه", callback_data="admin:broadcast")],
                    [InlineKeyboardButton("👤 پنل کاربری", callback_data="mygroups")],
                ]
                await query.edit_message_text(
                    f"🤖 پنل سازنده\n\n✅ فعال: {len(ag)} | 📁 کل: {len(allg)}",
                    reply_markup=InlineKeyboardMarkup(keyboard))

        elif data.startswith("admin:grp:"):
            if not is_owner(user.id):
                return
            group_id = int(data.split(":")[2])
            g = db.get_group(group_id)
            if not g:
                await query.edit_message_text("❌ یافت نشد.",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 برگشت", callback_data="admin:list")]]))
                return
            st = "✅ فعال" if g.get('is_active') else "❌ غیرفعال"
            tl = "❌ غیرفعال کردن" if g.get('is_active') else "✅ فعال کردن"
            td = f"admin:deact:{group_id}" if g.get('is_active') else f"admin:act:{group_id}"
            keyboard = [
                [InlineKeyboardButton(tl, callback_data=td)],
                [InlineKeyboardButton("🔙 برگشت", callback_data="admin:list")]
            ]
            await query.edit_message_text(
                f"📌 {g.get('group_name', 'نامشخص')}\n"
                f"🆔 {group_id}\n"
                f"📊 {st}\n"
                f"👤 @{g.get('owner_username', '-')}",
                reply_markup=InlineKeyboardMarkup(keyboard))

        elif data.startswith("admin:act:"):
            if not is_owner(user.id): return
            db.activate_group_free(int(data.split(":")[2]))
            await query.edit_message_text("✅ فعال شد.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 برگشت", callback_data="admin:list")]]))

        elif data.startswith("admin:deact:"):
            if not is_owner(user.id): return
            db.deactivate_group(int(data.split(":")[2]))
            await query.edit_message_text("❌ غیرفعال شد.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 برگشت", callback_data="admin:list")]]))

    except Exception as e:
        logger.error(f"Button handler error: {e}")
        try:
            await query.edit_message_text("❌ خطایی رخ داد. دوباره /start بزنید.")
        except:
            pass

# ============================================
# پیام‌های پیوی
# ============================================

async def private_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != 'private':
        return
    user = update.effective_user
    text = update.message.text
    action = context.user_data.get('action', '')

    if text == '/cancel':
        context.user_data.clear()
        await update.message.reply_text("❌ لغو شد.")
        return

    if action == 'broadcast' and is_owner(user.id):
        groups = db.get_all_active_groups()
        ok = fail = 0
        for g in groups:
            try:
                await context.bot.send_message(g['group_id'], f"📢 پیام سازنده:\n\n{text}")
                ok += 1
            except:
                fail += 1
        await update.message.reply_text(f"✅ موفق: {ok} | ❌ ناموفق: {fail}")
        context.user_data.clear()

    elif action.startswith('setwelcome:'):
        group_id = int(action.split(':')[1])
        db.update_setting(group_id, 'welcome_text', text)
        context.user_data.clear()
        await update.message.reply_text("✅ متن خوش‌آمد ذخیره شد.")

    elif action.startswith('setgoodbye:'):
        group_id = int(action.split(':')[1])
        db.update_setting(group_id, 'goodbye_text', text)
        context.user_data.clear()
        await update.message.reply_text("✅ متن خروج ذخیره شد.")

# ============================================
# ورود اعضا
# ============================================

async def member_joined(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.new_chat_members:
        return
    group_id = update.effective_chat.id
    if not db.is_group_active(group_id):
        return
    s = db.get_settings(group_id)
    inviter = update.message.from_user

    for new_member in update.message.new_chat_members:
        if new_member.is_bot:
            continue
        name = get_name(new_member)

        # ثبت دعوت
        if inviter and inviter.id != new_member.id:
            db.add_invite(group_id, inviter.id, get_name(inviter), new_member.id, name)
            # آپدیت اد اجباری دعوت‌کننده
            if s.get('force_invite'):
                db.init_force_status(group_id, inviter.id)
                db.increment_force_invite(group_id, inviter.id)
                status = db.get_force_status(group_id, inviter.id)
                need = s.get('force_invite_count', 5)
                if status and status['invite_count'] >= need and not status['is_free']:
                    db.set_force_free(group_id, inviter.id, 1)

        del_sec = s.get('delete_bot_msg_seconds', 30) if s.get('delete_bot_msg') else 0

        # کپچا
        if s.get('captcha_enabled'):
            db.add_captcha_pending(group_id, new_member.id, name)
            keyboard = [[InlineKeyboardButton(
                "✅ من ربات نیستم!",
                callback_data=f"captcha_ok:{group_id}:{new_member.id}")]]
            await bot_reply(context, group_id,
                f"👋 {name} خوش آمدید!\n\n"
                "⚠️ برای ارسال پیام روی دکمه زیر بزنید:",
                del_sec, reply_markup=InlineKeyboardMarkup(keyboard))
            continue

        # اد اجباری
        if s.get('force_invite') and not db.is_whitelisted(group_id, new_member.id):
            db.init_force_status(group_id, new_member.id)
            status = db.get_force_status(group_id, new_member.id)
            need = s.get('force_invite_count', 5)
            if status and not status['is_free'] and status['invite_count'] < need:
                remaining = need - status['invite_count']
                await bot_reply(context, group_id,
                    f"👋 {name} خوش آمدید!\n\n"
                    f"⚠️ برای ارسال پیام باید {remaining} نفر اد کنید.",
                    del_sec)
                continue

        # پیام خوش‌آمد
        if s.get('welcome_enabled', 1):
            wt = s.get('welcome_text', '')
            if wt:
                try:
                    msg_text = wt.format(name=name, group=update.effective_chat.title or '')
                except:
                    msg_text = wt
            else:
                msg_text = f"👋 {name} به گروه خوش آمدید! 🎉"

            if s.get('welcome_button'):
                keyboard = [[InlineKeyboardButton(
                    "✅ قوانین را خواندم",
                    callback_data=f"rules_ok:{group_id}:{new_member.id}")]]
                await bot_reply(context, group_id, msg_text, del_sec,
                    reply_markup=InlineKeyboardMarkup(keyboard))
            else:
                await bot_reply(context, group_id, msg_text, del_sec)

# ============================================
# خروج اعضا
# ============================================

async def member_left(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.left_chat_member:
        return
    group_id = update.effective_chat.id
    if not db.is_group_active(group_id):
        return
    s = db.get_settings(group_id)
    if not s.get('goodbye_enabled'):
        return
    member = update.message.left_chat_member
    if member.is_bot:
        return
    name = get_name(member)
    gt = s.get('goodbye_text', '')
    try:
        text = gt.format(name=name) if gt else f"👋 {name} گروه را ترک کرد."
    except:
        text = f"👋 {name} گروه را ترک کرد."
    date, time = now_datetime()
    text += f"\n📅 {date} | ⏰ {time}"
    del_sec = s.get('delete_bot_msg_seconds', 30) if s.get('delete_bot_msg') else 0
    await bot_reply(context, group_id, text, del_sec)

# ============================================
# فیلتر پیام‌های گروه
# ============================================

async def filter_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_user:
        return
    group_id = update.effective_chat.id
    user = update.effective_user
    msg = update.message

    if not db.is_group_active(group_id):
        return

    # ادمین‌ها از فیلتر معاف هستند
    if await is_group_admin(context, group_id, user.id):
        await handle_admin_commands(update, context)
        return

    s = db.get_settings(group_id)

    # کپچا
    if s.get('captcha_enabled') and db.is_captcha_pending(group_id, user.id):
        await safe_delete(msg)
        return

    # اد اجباری
    if s.get('force_invite') and not db.is_whitelisted(group_id, user.id):
        db.init_force_status(group_id, user.id)
        status = db.get_force_status(group_id, user.id)
        need = s.get('force_invite_count', 5)
        if status and not status['is_free']:
            # چک انقضا
            if s.get('force_invite_days', 0) > 0:
                try:
                    period_start = datetime.strptime(status['period_start'], "%Y-%m-%d %H:%M:%S")
                    if datetime.now() - period_start > timedelta(days=s['force_invite_days']):
                        db.reset_force_status(group_id, user.id)
                        status = db.get_force_status(group_id, user.id)
                except:
                    pass
            if status and not status['is_free'] and status['invite_count'] < need:
                await safe_delete(msg)
                remaining = need - status['invite_count']
                del_sec = 10
                await bot_reply(context, group_id,
                    f"⚠️ {get_name(user)}، برای پیام دادن باید {remaining} نفر دیگر اد کنید.",
                    del_sec)
                return

    # قفل کامل گروه
    if s.get('group_locked'):
        await safe_delete(msg)
        return

    # ساعت خاموشی
    if is_quiet_time(s):
        await safe_delete(msg)
        db.log_deleted_message(group_id, user.id, "ساعت خاموشی")
        return

    # ضد فلود
    if s.get('anti_flood'):
        count, first_time = db.track_flood(group_id, user.id)
        limit = s.get('anti_flood_count', 5)
        flood_secs = s.get('anti_flood_seconds', 10)
        try:
            first_dt = datetime.strptime(first_time, "%Y-%m-%d %H:%M:%S")
            if (datetime.now() - first_dt).seconds <= flood_secs:
                if count >= limit:
                    await safe_delete(msg)
                    try:
                        await context.bot.restrict_chat_member(
                            group_id, user.id,
                            ChatPermissions(can_send_messages=False),
                            until_date=datetime.now() + timedelta(minutes=5))
                        del_sec = s.get('delete_bot_msg_seconds', 30) if s.get('delete_bot_msg') else 30
                        await bot_reply(context, group_id,
                            f"⚡ {get_name(user)} به دلیل ارسال سریع 5 دقیقه ساکت شد.",
                            del_sec)
                    except:
                        pass
                    db.reset_flood(group_id, user.id)
                    return
            else:
                db.reset_flood(group_id, user.id)
        except:
            pass

    # بررسی قفل‌ها
    reason = None

    if msg.text:
        text = msg.text
        if s.get('lock_link') and ('t.me/' in text or 'telegram.me/' in text):
            reason = "ارسال لینک تلگرام ممنوع است"
        elif s.get('lock_site') and any(x in text for x in ['http://', 'https://', 'www.']):
            reason = "ارسال لینک سایت ممنوع است"
        elif s.get('lock_id') and '@' in text:
            reason = "ارسال آیدی ممنوع است"
        elif s.get('lock_hashtag') and '#' in text:
            reason = "ارسال هشتگ ممنوع است"
        elif s.get('lock_slash') and text.startswith('/'):
            reason = "ارسال دستور ممنوع است"
        elif s.get('lock_text'):
            reason = "ارسال متن ممنوع است"
        elif s.get('lock_bad_words'):
            bad_words = db.get_bad_words(group_id)
            if bad_words and any(w in text.lower() for w in bad_words):
                reason = "استفاده از کلمات ممنوعه"
        if not reason and s.get('anti_spam') and msg.forward_date:
            reason = "فوروارد پیام ممنوع است"

    elif msg.photo and s.get('lock_photo'):
        reason = "ارسال عکس ممنوع است"
    elif msg.video and s.get('lock_video'):
        reason = "ارسال فیلم ممنوع است"
    elif msg.sticker and s.get('lock_sticker'):
        reason = "ارسال استیکر ممنوع است"
    elif msg.animation and s.get('lock_gif'):
        reason = "ارسال گیف ممنوع است"
    elif msg.voice and s.get('lock_voice'):
        reason = "ارسال صدا ممنوع است"
    elif msg.document and s.get('lock_file'):
        reason = "ارسال فایل ممنوع است"
    elif msg.poll and s.get('lock_poll'):
        reason = "ارسال نظرسنجی ممنوع است"
    elif msg.location and s.get('lock_location'):
        reason = "ارسال لوکیشن ممنوع است"
    elif msg.contact and s.get('lock_phone'):
        reason = "ارسال شماره تلفن ممنوع است"
    elif msg.forward_from_chat and s.get('lock_forward_channel'):
        reason = "فوروارد از کانال ممنوع است"
    elif msg.forward_date and s.get('lock_forward'):
        reason = "فوروارد پیام ممنوع است"

    if reason:
        await safe_delete(msg)
        db.log_deleted_message(group_id, user.id, reason)
        del_sec = s.get('delete_bot_msg_seconds', 30) if s.get('delete_bot_msg') else 0

        if s.get('auto_warn'):
            db.add_warning(group_id, user.id, reason)
            warns = db.get_warnings(group_id, user.id)
            warn_limit = s.get('warn_limit', 3)
            await bot_reply(context, group_id,
                f"⚠️ {get_name(user)}، {reason}.\nاخطار {warns}/{warn_limit}",
                del_sec)
            if warns >= warn_limit:
                await do_warn_action(context, group_id, user, s.get('warn_action', 'kick'))
                db.reset_warnings(group_id, user.id)
        else:
            await bot_reply(context, group_id,
                f"🚫 {get_name(user)}، {reason}.",
                del_sec)
        return

    await handle_public_commands(update, context)

async def do_warn_action(context, group_id, user, action):
    try:
        if action == 'kick':
            await context.bot.ban_chat_member(group_id, user.id)
            await asyncio.sleep(1)
            await context.bot.unban_chat_member(group_id, user.id)
            await context.bot.send_message(group_id,
                f"🚫 {get_name(user)} به دلیل تکرار تخلف اخراج شد.")
        elif action == 'ban':
            await context.bot.ban_chat_member(group_id, user.id)
            await context.bot.send_message(group_id,
                f"🚫 {get_name(user)} برای همیشه بن شد.")
        elif action == 'mute':
            await context.bot.restrict_chat_member(group_id, user.id,
                ChatPermissions(can_send_messages=False))
            await context.bot.send_message(group_id,
                f"🔇 {get_name(user)} ساکت شد.")
    except:
        pass

# ============================================
# دستورات عمومی گروه
# ============================================

async def handle_public_commands(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    msg = update.message
    text = msg.text.strip()
    group_id = update.effective_chat.id
    user = update.effective_user
    s = db.get_settings(group_id)

    if not s.get('public_commands', 1):
        return

    if text == "لینک گروه را بفرست":
        g = db.get_group(group_id)
        link = g.get('group_link') if g else None
        await msg.reply_text(f"🔗 {link}" if link else "❌ لینک تنظیم نشده.")
    elif text == "این گروه برای چیه؟":
        g = db.get_group(group_id)
        info = g.get('group_info') if g else None
        await msg.reply_text(info if info else "❌ توضیحات تنظیم نشده.")
    elif text == "قوانین":
        g = db.get_group(group_id)
        rules = g.get('group_rules') if g else None
        await msg.reply_text(f"📜 قوانین:\n\n{rules}" if rules else "❌ قوانین تنظیم نشده.")
    elif text == "من را کی اد کرده است؟":
        inv = db.get_who_invited(group_id, user.id)
        await msg.reply_text(f"👤 توسط {inv} اضافه شدید." if inv else "❓ اطلاعاتی یافت نشد.")
    elif text == "من چند نفر اد کردم؟":
        c = db.get_user_invite_count(group_id, user.id)
        await msg.reply_text(f"📊 شما {c} نفر را اضافه کرده‌اید.")
    elif text == "اطلاعات من":
        c = db.get_user_invite_count(group_id, user.id)
        w = db.get_warnings(group_id, user.id)
        inv = db.get_who_invited(group_id, user.id)
        await msg.reply_text(
            f"👤 {get_name(user)}\n"
            f"📨 اد کرده: {c} نفر\n"
            f"⚠️ اخطار: {w}\n"
            f"👥 اد شده توسط: {inv or 'نامشخص'}")
    elif text == "گزارش" and msg.reply_to_message:
        rm = msg.reply_to_message
        await context.bot.send_message(config.ADMIN_ID,
            f"🚨 گزارش از {get_name(user)} در گروه {update.effective_chat.title}:\n\n"
            f"{rm.text or '[غیر متنی]'}")
        await msg.reply_text("✅ گزارش ارسال شد.")
    elif text == "پیام من چرا حذف شد؟":
        r = db.get_last_delete_reason(group_id, user.id)
        await msg.reply_text(f"❌ دلیل: {r}" if r else "❓ اطلاعاتی یافت نشد.")

# ============================================
# دستورات ادمین گروه
# ============================================

async def handle_admin_commands(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    msg = update.message
    text = msg.text.strip()
    group_id = update.effective_chat.id

    if not (text.startswith('!') or text.startswith('.')):
        await handle_public_commands(update, context)
        return

    cmd = text[1:].strip()
    s = db.get_settings(group_id)
    del_sec = s.get('delete_bot_msg_seconds', 30) if s.get('delete_bot_msg') else 0

    async def reply(t):
        m = await msg.reply_text(t)
        if del_sec > 0:
            await asyncio.sleep(del_sec)
            try:
                await m.delete()
            except:
                pass

    if cmd.startswith('اخراج') and msg.reply_to_message:
        parts = cmd.split()
        hours = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
        target = msg.reply_to_message.from_user
        try:
            until = datetime.now() + timedelta(hours=hours) if hours and hours != 1000 else None
            await context.bot.ban_chat_member(group_id, target.id, until_date=until)
            await reply(f"🚫 {get_name(target)} اخراج شد.")
        except TelegramError as e:
            await reply(f"❌ خطا: {e}")

    elif cmd.startswith('ساکت') and msg.reply_to_message:
        parts = cmd.split()
        hours = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 1
        target = msg.reply_to_message.from_user
        try:
            until = None if hours == 1000 else datetime.now() + timedelta(hours=hours)
            await context.bot.restrict_chat_member(group_id, target.id,
                ChatPermissions(can_send_messages=False), until_date=until)
            await reply(f"🔇 {get_name(target)} {hours} ساعت ساکت شد.")
        except TelegramError as e:
            await reply(f"❌ خطا: {e}")

    elif cmd == 'آزاد' and msg.reply_to_message:
        target = msg.reply_to_message.from_user
        try:
            await context.bot.restrict_chat_member(group_id, target.id,
                ChatPermissions(can_send_messages=True, can_send_photos=True,
                    can_send_videos=True, can_send_other_messages=True,
                    can_send_documents=True, can_send_voice_notes=True))
            await reply(f"✅ {get_name(target)} آزاد شد.")
        except TelegramError as e:
            await reply(f"❌ خطا: {e}")

    elif cmd == 'اخطار' and msg.reply_to_message:
        target = msg.reply_to_message.from_user
        db.add_warning(group_id, target.id, "اخطار دستی")
        warns = db.get_warnings(group_id, target.id)
        warn_limit = s.get('warn_limit', 3)
        await reply(f"⚠️ {get_name(target)} اخطار {warns}/{warn_limit} گرفت.")
        if warns >= warn_limit and s.get('auto_warn'):
            await do_warn_action(context, group_id, target, s.get('warn_action', 'kick'))
            db.reset_warnings(group_id, target.id)

    elif cmd == 'ریست' and msg.reply_to_message:
        target = msg.reply_to_message.from_user
        db.reset_warnings(group_id, target.id)
        await reply(f"✅ اخطارهای {get_name(target)} پاک شد.")

    elif cmd == 'معاف' and msg.reply_to_message:
        target = msg.reply_to_message.from_user
        db.add_to_whitelist(group_id, target.id, get_name(target))
        db.set_force_free(group_id, target.id, 1)
        await reply(f"✅ {get_name(target)} از اد اجباری معاف شد.")

    elif cmd == 'حذف معاف' and msg.reply_to_message:
        target = msg.reply_to_message.from_user
        db.remove_from_whitelist(group_id, target.id)
        await reply(f"✅ {get_name(target)} از لیست سفید حذف شد.")

    elif cmd.startswith('کلمه ممنوع '):
        word = cmd.replace('کلمه ممنوع ', '').strip()
        db.add_bad_word(group_id, word)
        await reply(f"✅ کلمه «{word}» اضافه شد.")

    elif cmd.startswith('حذف کلمه '):
        word = cmd.replace('حذف کلمه ', '').strip()
        db.remove_bad_word(group_id, word)
        await reply(f"✅ کلمه «{word}» حذف شد.")

    elif cmd.startswith('خاموشی'):
        match = re.match(r'خاموشی\s*(\d)\s*از\s*(\d{1,2})\s*تا\s*(\d{1,2})', cmd)
        if match:
            num = match.group(1)
            f = match.group(2).zfill(2) + ":00"
            t = match.group(3).zfill(2) + ":00"
            db.update_setting(group_id, f'quiet_{num}_from', f)
            db.update_setting(group_id, f'quiet_{num}_to', t)
            await reply(f"✅ خاموشی {num} از {f} تا {t} تنظیم شد.")
        else:
            match2 = re.match(r'خاموشی\s*(\d)\s*غیرفعال', cmd)
            if match2:
                num = match2.group(1)
                db.update_setting(group_id, f'quiet_{num}_from', None)
                db.update_setting(group_id, f'quiet_{num}_to', None)
                date, time = now_datetime()
                await reply(f"✅ خاموشی {num} غیرفعال شد.\n📅 {date} | ⏰ {time}")

    elif cmd.startswith('لینک گروه '):
        link = cmd.replace('لینک گروه ', '').strip()
        db.update_group_field(group_id, 'group_link', link)
        await reply("✅ لینک گروه تنظیم شد.")

    elif cmd.startswith('توضیحات گروه '):
        info = cmd.replace('توضیحات گروه ', '').strip()
        db.update_group_field(group_id, 'group_info', info)
        await reply("✅ توضیحات گروه تنظیم شد.")

    elif cmd.startswith('قوانین '):
        rules = cmd.replace('قوانین ', '').strip()
        db.update_group_field(group_id, 'group_rules', rules)
        await reply("✅ قوانین گروه تنظیم شد.")

    elif 'کیا بیشتر اد کردند' in cmd:
        stats = db.get_invite_stats(group_id)
        if not stats:
            await reply("❓ آماری یافت نشد.")
            return
        t = "📊 برترین دعوت‌کنندگان:\n\n"
        for i, st in enumerate(stats[:10], 1):
            t += f"{i}. {st['inviter_name']}: {st['count']} نفر\n"
        await reply(t)

# ============================================
# اضافه شدن ربات به گروه
# ============================================

async def bot_added_to_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.my_chat_member:
        return
    chat = update.effective_chat
    user = update.my_chat_member.from_user
    new_status = update.my_chat_member.new_chat_member.status

    if new_status in ['member', 'administrator'] and chat.type in ['group', 'supergroup']:
        db.add_group(chat.id, chat.title, user.id, user.username or "")
        db.activate_group_free(chat.id)
        try:
            await context.bot.send_message(chat.id,
                f"✅ ربات هیوا فعال شد!\n\n"
                f"📌 برای تنظیمات، در پیوی ربات /start بزنید.")
        except:
            pass
        try:
            await context.bot.send_message(config.ADMIN_ID,
                f"🆕 گروه جدید:\n"
                f"🏠 {chat.title}\n"
                f"🆔 {chat.id}\n"
                f"👤 @{user.username or '-'}")
        except:
            pass

    elif new_status in ['left', 'kicked'] and chat.type in ['group', 'supergroup']:
        db.deactivate_group(chat.id)
        try:
            await context.bot.send_message(config.ADMIN_ID,
                f"⚠️ ربات از گروه خارج شد:\n"
                f"🏠 {chat.title}\n"
                f"🆔 {chat.id}")
        except:
            pass

# ============================================
# راه‌اندازی
# ============================================

def main():
    db.init_db()
    app = Application.builder().token(config.BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(ChatMemberHandler(bot_added_to_group, ChatMemberHandler.MY_CHAT_MEMBER))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(
        filters.ChatType.PRIVATE & filters.TEXT & ~filters.COMMAND, private_message))
    app.add_handler(MessageHandler(
        filters.ChatType.GROUPS & filters.StatusUpdate.NEW_CHAT_MEMBERS, member_joined))
    app.add_handler(MessageHandler(
        filters.ChatType.GROUPS & filters.StatusUpdate.LEFT_CHAT_MEMBER, member_left))
    app.add_handler(MessageHandler(
        filters.ChatType.GROUPS & ~filters.COMMAND & ~filters.StatusUpdate.ALL, filter_messages))
    print("🤖 ربات هیوا نسخه 4 آماده است...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
