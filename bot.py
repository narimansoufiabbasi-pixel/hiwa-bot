# ============================================
# ربات مدیر گروه هیوا
# نسخه کامل با پنل کاربری و ادمین
# ============================================

import logging
import asyncio
import re
from datetime import datetime, timedelta
from telegram import (
    Update, ChatPermissions, InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, ChatMemberHandler,
    CallbackQueryHandler, filters, ContextTypes
)
from telegram.error import TelegramError

import config
import database as db

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ============================================
# ابزارها
# ============================================

def is_admin(user_id):
    return user_id == config.ADMIN_ID

async def is_group_admin(update: Update, user_id: int) -> bool:
    try:
        member = await update.effective_chat.get_member(user_id)
        return member.status in ['administrator', 'creator']
    except:
        return False

def get_name(user):
    name = user.first_name or ""
    if user.last_name:
        name += f" {user.last_name}"
    return name

def is_quiet_time(group_id):
    settings = db.get_settings(group_id)
    now = datetime.now().strftime("%H:%M")
    for i in range(1, 4):
        from_time = settings.get(f'quiet_{i}_from')
        to_time = settings.get(f'quiet_{i}_to')
        if from_time and to_time:
            if from_time <= to_time:
                if from_time <= now <= to_time:
                    return True
            else:
                if now >= from_time or now <= to_time:
                    return True
    return False

# ============================================
# پنل کاربری - انتخاب گروه
# ============================================

async def show_user_groups(update, context, user_id, message_func):
    groups = db.get_user_groups(user_id)
    if not groups:
        await message_func(
            "❌ شما هیچ گروهی ندارید که ربات در آن فعال باشد.\n\n"
            "ابتدا ربات را به گروه خود اضافه کنید و ادمین کنید."
        )
        return

    keyboard = []
    for g in groups:
        keyboard.append([InlineKeyboardButton(
            f"🏠 {g.get('group_name', 'نامشخص')}",
            callback_data=f"user_group_{g['group_id']}"
        )])
    keyboard.append([InlineKeyboardButton("📖 راهنما", callback_data="user_help")])

    await message_func(
        f"👋 سلام!\n\n"
        "یکی از گروه‌های خود را انتخاب کنید:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def show_group_panel(query, group_id):
    group = db.get_group(group_id)
    settings = db.get_settings(group_id)
    if not group:
        await query.edit_message_text("❌ گروه یافت نشد.")
        return

    name = group.get('group_name', 'نامشخص')
    keyboard = [
        [InlineKeyboardButton("🔒 مدیریت قفل‌ها", callback_data=f"user_locks_{group_id}")],
        [InlineKeyboardButton("🌙 ساعت خاموشی", callback_data=f"user_quiet_{group_id}")],
        [InlineKeyboardButton("🔗 لینک گروه", callback_data=f"user_link_{group_id}"),
         InlineKeyboardButton("📝 توضیحات گروه", callback_data=f"user_info_{group_id}")],
        [InlineKeyboardButton("📊 آمار گروه", callback_data=f"user_stats_{group_id}")],
        [InlineKeyboardButton("📖 راهنمای دستورات", callback_data="user_help")],
        [InlineKeyboardButton("🔙 برگشت به گروه‌ها", callback_data="user_back")],
    ]
    await query.edit_message_text(
        f"⚙️ تنظیمات گروه «{name}»\n\nچه کاری می‌خواهید انجام دهید؟",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def show_locks_panel(query, group_id):
    settings = db.get_settings(group_id)
    group = db.get_group(group_id)
    name = group.get('group_name', 'نامشخص') if group else 'نامشخص'

    def lock_btn(label, key, gid):
        val = settings.get(key, 0)
        icon = "🔒" if val else "🔓"
        new_val = 0 if val else 1
        return InlineKeyboardButton(f"{icon} {label}", callback_data=f"user_toggle_{gid}_{key}_{new_val}")

    keyboard = [
        [lock_btn("لینک تلگرام", "lock_link", group_id), lock_btn("لینک سایت", "lock_site", group_id)],
        [lock_btn("آیدی و منشن", "lock_id", group_id), lock_btn("هشتگ", "lock_hashtag", group_id)],
        [lock_btn("عکس", "lock_photo", group_id), lock_btn("فیلم", "lock_video", group_id)],
        [lock_btn("استیکر", "lock_sticker", group_id), lock_btn("گیف", "lock_gif", group_id)],
        [lock_btn("صدا", "lock_voice", group_id), lock_btn("فایل", "lock_file", group_id)],
        [lock_btn("نظرسنجی", "lock_poll", group_id), lock_btn("لوکیشن", "lock_location", group_id)],
        [lock_btn("شماره تلفن", "lock_phone", group_id), lock_btn("فوروارد", "lock_forward", group_id)],
        [lock_btn("متن", "lock_text", group_id), lock_btn("کلمات بد", "lock_bad_words", group_id)],
        [lock_btn("دستورات عمومی", "public_commands", group_id)],
        [InlineKeyboardButton("🔙 برگشت", callback_data=f"user_group_{group_id}")],
    ]
    await query.edit_message_text(
        f"🔒 مدیریت قفل‌های گروه «{name}»\n\n"
        "🔒 = قفل است  |  🔓 = آزاد است\n"
        "روی هر گزینه بزنید تا تغییر کند:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ============================================
# هندلر /start
# ============================================

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    if chat.type != 'private':
        return

    if is_admin(user.id):
        active_groups = db.get_all_active_groups()
        all_groups = db.get_all_groups()
        keyboard = [
            [InlineKeyboardButton("📋 لیست گروه‌ها", callback_data="admin_list_groups")],
            [InlineKeyboardButton("📊 آمار کلی", callback_data="admin_stats")],
            [InlineKeyboardButton("📢 پیام به همه گروه‌ها", callback_data="admin_broadcast")],
        ]
        await update.message.reply_text(
            f"👋 سلام {get_name(user)}!\n\n"
            f"🤖 پنل مدیریت ربات هیوا\n\n"
            f"✅ گروه‌های فعال: {len(active_groups)}\n"
            f"📁 کل گروه‌ها: {len(all_groups)}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await show_user_groups(update, context, user.id, update.message.reply_text)

# ============================================
# هندلر دکمه‌ها
# ============================================

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    data = query.data

    # ============ پنل کاربری ============

    if data == "user_back":
        groups = db.get_user_groups(user.id)
        if not groups:
            await query.edit_message_text("❌ هیچ گروهی یافت نشد.")
            return
        keyboard = []
        for g in groups:
            keyboard.append([InlineKeyboardButton(
                f"🏠 {g.get('group_name', 'نامشخص')}",
                callback_data=f"user_group_{g['group_id']}"
            )])
        keyboard.append([InlineKeyboardButton("📖 راهنما", callback_data="user_help")])
        await query.edit_message_text(
            "یکی از گروه‌های خود را انتخاب کنید:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data.startswith("user_group_"):
        group_id = int(data.split("_")[2])
        await show_group_panel(query, group_id)

    elif data.startswith("user_locks_"):
        group_id = int(data.split("_")[2])
        await show_locks_panel(query, group_id)

    elif data.startswith("user_toggle_"):
        parts = data.split("_")
        group_id = int(parts[2])
        key = parts[3]
        val = int(parts[4])
        db.update_setting(group_id, key, val)
        await show_locks_panel(query, group_id)

    elif data.startswith("user_stats_"):
        group_id = int(data.split("_")[2])
        group = db.get_group(group_id)
        name = group.get('group_name', 'نامشخص') if group else 'نامشخص'
        stats = db.get_invite_stats(group_id, None)
        total_invites = sum(s['count'] for s in stats) if stats else 0
        text = (
            f"📊 آمار گروه «{name}»\n\n"
            f"👥 تعداد دعوت‌شدگان: {total_invites}\n"
        )
        if stats:
            text += "\n🏆 برترین دعوت‌کنندگان:\n"
            for i, s in enumerate(stats[:5], 1):
                text += f"{i}. {s['inviter_name']}: {s['count']} نفر\n"
        keyboard = [[InlineKeyboardButton("🔙 برگشت", callback_data=f"user_group_{group_id}")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("user_quiet_"):
        group_id = int(data.split("_")[2])
        group = db.get_group(group_id)
        name = group.get('group_name', 'نامشخص') if group else 'نامشخص'
        settings = db.get_settings(group_id)
        text = f"🌙 ساعت خاموشی گروه «{name}»\n\n"
        for i in range(1, 4):
            f = settings.get(f'quiet_{i}_from')
            t = settings.get(f'quiet_{i}_to')
            if f and t:
                text += f"خاموشی {i}: {f} تا {t} ✅\n"
            else:
                text += f"خاموشی {i}: تنظیم نشده ❌\n"
        text += (
            "\n📌 برای تنظیم، در گروه بنویسید:\n"
            "!خاموشی 1 از 23:00 تا 07:00\n\n"
            "برای غیرفعال کردن:\n"
            "!خاموشی 1 غیرفعال"
        )
        keyboard = [[InlineKeyboardButton("🔙 برگشت", callback_data=f"user_group_{group_id}")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("user_link_"):
        group_id = int(data.split("_")[2])
        group = db.get_group(group_id)
        name = group.get('group_name', 'نامشخص') if group else 'نامشخص'
        link = group.get('group_link') if group else None
        text = f"🔗 لینک گروه «{name}»\n\n"
        text += f"لینک فعلی: {link or 'تنظیم نشده'}\n\n"
        text += "برای تنظیم، در گروه بنویسید:\n!لینک گروه https://t.me/xxx"
        keyboard = [[InlineKeyboardButton("🔙 برگشت", callback_data=f"user_group_{group_id}")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("user_info_"):
        group_id = int(data.split("_")[2])
        group = db.get_group(group_id)
        name = group.get('group_name', 'نامشخص') if group else 'نامشخص'
        info = group.get('group_info') if group else None
        text = f"📝 توضیحات گروه «{name}»\n\n"
        text += f"توضیحات فعلی: {info or 'تنظیم نشده'}\n\n"
        text += "برای تنظیم، در گروه بنویسید:\n!توضیحات گروه متن توضیحات شما"
        keyboard = [[InlineKeyboardButton("🔙 برگشت", callback_data=f"user_group_{group_id}")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "user_help":
        text = (
            "📖 راهنمای دستورات ربات هیوا\n\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "🔑 دستورات ادمین گروه\n"
            "(با ! یا . شروع می‌شوند)\n\n"
            "👤 مدیریت کاربران:\n"
            "!اخراج — اخراج دائم (ریپلای)\n"
            "!اخراج 24 — اخراج 24 ساعته\n"
            "!ساکت 1 — ساکت 1 ساعته\n"
            "!ساکت 1000 — ساکت دائم\n"
            "!آزاد — آزاد کردن\n"
            "!ریست — پاک کردن اخطارها\n\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "💬 دستورات عمومی اعضا:\n"
            "لینک گروه را بفرست\n"
            "این گروه برای چیه؟\n"
            "اطلاعات من\n"
            "من چند نفر اد کردم؟\n"
            "گزارش (ریپلای روی پیام)\n"
            "پیام من چرا حذف شد؟\n\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "⚙️ تنظیمات قفل‌ها از پنل بالا انجام می‌شود"
        )
        keyboard = [[InlineKeyboardButton("🔙 برگشت", callback_data="user_back")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    # ============ پنل ادمین اصلی ============

    elif not is_admin(user.id) and data.startswith("admin_"):
        await query.edit_message_text("❌ شما دسترسی ندارید.")
        return

    elif data == "admin_stats":
        active_groups = db.get_all_active_groups()
        all_groups = db.get_all_groups()
        text = (
            f"📊 آمار کلی ربات هیوا\n\n"
            f"📁 کل گروه‌ها: {len(all_groups)}\n"
            f"✅ فعال: {len(active_groups)}\n"
            f"❌ غیرفعال: {len(all_groups) - len(active_groups)}\n"
        )
        keyboard = [[InlineKeyboardButton("🔙 برگشت", callback_data="admin_back")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "admin_list_groups":
        all_groups = db.get_all_groups()
        if not all_groups:
            await query.edit_message_text("❌ هیچ گروهی ثبت نشده.")
            return
        keyboard = []
        for g in all_groups[:20]:
            status = "✅" if g.get('is_active') else "❌"
            keyboard.append([InlineKeyboardButton(
                f"{status} {g.get('group_name', 'نامشخص')}",
                callback_data=f"admin_group_{g['group_id']}"
            )])
        keyboard.append([InlineKeyboardButton("🔙 برگشت", callback_data="admin_back")])
        await query.edit_message_text("📋 لیست گروه‌ها:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("admin_group_"):
        group_id = int(data.split("_")[2])
        group = db.get_group(group_id)
        if not group:
            await query.edit_message_text("❌ گروه یافت نشد.")
            return
        status = "✅ فعال" if group.get('is_active') else "❌ غیرفعال"
        text = (
            f"📌 اطلاعات گروه\n\n"
            f"🏠 نام: {group.get('group_name', 'نامشخص')}\n"
            f"🆔 آیدی: {group['group_id']}\n"
            f"📊 وضعیت: {status}\n"
            f"👤 مالک: {group.get('owner_username', 'نامشخص')}\n"
        )
        toggle_label = "❌ غیرفعال کردن" if group.get('is_active') else "✅ فعال کردن"
        toggle_data = f"admin_deactivate_{group_id}" if group.get('is_active') else f"admin_activate_{group_id}"
        keyboard = [
            [InlineKeyboardButton(toggle_label, callback_data=toggle_data)],
            [InlineKeyboardButton("🔙 برگشت", callback_data="admin_list_groups")]
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("admin_activate_"):
        group_id = int(data.split("_")[2])
        db.activate_group_free(group_id)
        await query.edit_message_text(f"✅ گروه فعال شد.")

    elif data.startswith("admin_deactivate_"):
        group_id = int(data.split("_")[2])
        db.deactivate_group(group_id)
        await query.edit_message_text(f"❌ گروه غیرفعال شد.")

    elif data == "admin_broadcast":
        await query.edit_message_text(
            "📢 پیام خود را بنویسید و بفرستید تا به همه گروه‌ها ارسال شود.\n\n"
            "برای لغو: /cancel"
        )
        context.user_data['action'] = 'broadcast'

    elif data == "admin_back":
        active_groups = db.get_all_active_groups()
        all_groups = db.get_all_groups()
        keyboard = [
            [InlineKeyboardButton("📋 لیست گروه‌ها", callback_data="admin_list_groups")],
            [InlineKeyboardButton("📊 آمار کلی", callback_data="admin_stats")],
            [InlineKeyboardButton("📢 پیام به همه گروه‌ها", callback_data="admin_broadcast")],
        ]
        await query.edit_message_text(
            f"🤖 پنل مدیریت ربات هیوا\n\n"
            f"✅ گروه‌های فعال: {len(active_groups)}\n"
            f"📁 کل گروه‌ها: {len(all_groups)}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

# ============================================
# پیام‌های پیوی
# ============================================

async def private_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != 'private':
        return
    user = update.effective_user
    text = update.message.text
    action = context.user_data.get('action')

    if text == '/cancel':
        context.user_data.clear()
        await update.message.reply_text("❌ لغو شد.")
        return

    if action == 'broadcast' and is_admin(user.id):
        groups = db.get_all_active_groups()
        success = 0
        fail = 0
        for group in groups:
            try:
                await context.bot.send_message(group['group_id'], f"📢 پیام از سازنده:\n\n{text}")
                success += 1
            except:
                fail += 1
        await update.message.reply_text(f"✅ ارسال شد!\nموفق: {success} | ناموفق: {fail}")
        context.user_data.clear()

# ============================================
# ورود اعضای جدید
# ============================================

async def member_joined(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.new_chat_members:
        return
    group_id = update.effective_chat.id
    if not db.is_group_active(group_id):
        return
    inviter = update.message.from_user
    for new_member in update.message.new_chat_members:
        if new_member.is_bot:
            continue
        if inviter and inviter.id != new_member.id:
            db.add_invite(group_id, inviter.id, get_name(inviter), new_member.id, get_name(new_member))
        msg = config.MSG_WELCOME.format(
            name=get_name(new_member),
            group=update.effective_chat.title or "گروه"
        )
        await update.message.reply_text(msg)

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
    if await is_group_admin(update, user.id):
        await handle_commands(update, context)
        return
    settings = db.get_settings(group_id)
    if is_quiet_time(group_id):
        await msg.delete()
        db.log_deleted_message(group_id, user.id, "ساعت خاموشی گروه")
        return
    reason = None
    if msg.text:
        text = msg.text
        if settings.get('lock_link') and ('t.me/' in text or 'telegram.me/' in text):
            reason = "ارسال لینک تلگرام ممنوع است"
        elif settings.get('lock_site') and ('http://' in text or 'https://' in text or 'www.' in text):
            reason = "ارسال لینک سایت ممنوع است"
        elif settings.get('lock_id') and '@' in text:
            reason = "ارسال آیدی و منشن ممنوع است"
        elif settings.get('lock_hashtag') and '#' in text:
            reason = "ارسال هشتگ ممنوع است"
        elif settings.get('lock_slash') and text.startswith('/'):
            reason = "ارسال دستور ممنوع است"
        elif settings.get('lock_bad_words'):
            bad_words = ['فحش1', 'فحش2']
            if any(w in text.lower() for w in bad_words):
                reason = "استفاده از کلمات نامناسب ممنوع است"
        elif settings.get('lock_text'):
            reason = "ارسال متن ممنوع است"
    elif msg.photo and settings.get('lock_photo'):
        reason = "ارسال عکس ممنوع است"
    elif msg.video and settings.get('lock_video'):
        reason = "ارسال فیلم ممنوع است"
    elif msg.sticker and settings.get('lock_sticker'):
        reason = "ارسال استیکر ممنوع است"
    elif msg.location and settings.get('lock_location'):
        reason = "ارسال موقعیت مکانی ممنوع است"
    elif msg.contact and settings.get('lock_phone'):
        reason = "ارسال شماره تلفن ممنوع است"
    elif msg.voice and settings.get('lock_voice'):
        reason = "ارسال صدا ممنوع است"
    elif msg.document and settings.get('lock_file'):
        reason = "ارسال فایل ممنوع است"
    elif msg.animation and settings.get('lock_gif'):
        reason = "ارسال گیف ممنوع است"
    elif msg.poll and settings.get('lock_poll'):
        reason = "ارسال نظرسنجی ممنوع است"
    elif msg.forward_from_chat and settings.get('lock_forward_channel'):
        reason = "فوروارد از کانال ممنوع است"
    elif msg.forward_date and settings.get('lock_forward'):
        reason = "فوروارد پیام ممنوع است"
    if reason:
        try:
            await msg.delete()
            db.log_deleted_message(group_id, user.id, reason)
            warn_msg = await update.effective_chat.send_message(f"🚫 {get_name(user)}، {reason}.")
            await asyncio.sleep(5)
            await warn_msg.delete()
        except TelegramError:
            pass
        return
    await handle_public_commands(update, context)

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
    settings = db.get_settings(group_id)
    if not settings.get('public_commands', 1):
        return
    if text == "لینک گروه را بفرست":
        group = db.get_group(group_id)
        link = group.get('group_link') if group else None
        await msg.reply_text(config.MSG_GROUP_LINK.format(link=link) if link else "❌ لینک تنظیم نشده.")
    elif text == "این گروه برای چیه؟":
        group = db.get_group(group_id)
        info = group.get('group_info') if group else None
        await msg.reply_text(config.MSG_GROUP_INFO.format(info=info) if info else "❌ توضیحات تنظیم نشده.")
    elif text == "من را کی اد کرده است؟":
        inviter = db.get_who_invited(group_id, user.id)
        await msg.reply_text(f"👤 توسط {inviter} اضافه شدید." if inviter else "❓ اطلاعاتی یافت نشد.")
    elif text == "این کاربر را کی اد کرده است؟" and msg.reply_to_message:
        target = msg.reply_to_message.from_user
        inviter = db.get_who_invited(group_id, target.id)
        await msg.reply_text(f"👤 {get_name(target)} توسط {inviter} اضافه شد." if inviter else "❓ یافت نشد.")
    elif text == "گزارش" and msg.reply_to_message:
        reported_msg = msg.reply_to_message
        await context.bot.send_message(config.ADMIN_ID, config.MSG_REPORT.format(
            name=get_name(user), message=reported_msg.text or "[غیر متنی]"))
        await msg.reply_text("✅ گزارش ارسال شد.")
    elif text == "من چند نفر اد کردم؟":
        count = db.get_user_invite_count(group_id, user.id)
        await msg.reply_text(f"📊 شما {count} نفر را اضافه کرده‌اید.")
    elif text == "اطلاعات من":
        count = db.get_user_invite_count(group_id, user.id)
        warns = db.get_warnings(group_id, user.id)
        inviter = db.get_who_invited(group_id, user.id)
        await msg.reply_text(f"👤 {get_name(user)}\n📨 اد: {count}\n⚠️ اخطار: {warns}/3\n👥 توسط: {inviter or 'نامشخص'}")
    elif text == "پیام من چرا حذف شد؟":
        reason = db.get_last_delete_reason(group_id, user.id)
        await msg.reply_text(f"❌ دلیل: {reason}" if reason else "❓ یافت نشد.")

# ============================================
# دستورات ادمین گروه
# ============================================

async def handle_commands(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    msg = update.message
    text = msg.text.strip()
    group_id = update.effective_chat.id
    if not (text.startswith('!') or text.startswith('.')):
        await handle_public_commands(update, context)
        return
    cmd = text[1:].strip()
    if cmd.startswith('اخراج') and msg.reply_to_message:
        parts = cmd.split()
        hours = int(parts[1]) if len(parts) > 1 else 0
        target = msg.reply_to_message.from_user
        try:
            until = datetime.now() + timedelta(hours=hours) if hours and hours != 1000 else None
            await context.bot.ban_chat_member(group_id, target.id, until_date=until)
            await msg.reply_text(config.MSG_BAN.format(name=get_name(target)))
        except TelegramError as e:
            await msg.reply_text(f"❌ خطا: {e}")
    elif cmd.startswith('ساکت') and msg.reply_to_message:
        parts = cmd.split()
        hours = int(parts[1]) if len(parts) > 1 else 1
        target = msg.reply_to_message.from_user
        try:
            until = None if hours == 1000 else datetime.now() + timedelta(hours=hours)
            await context.bot.restrict_chat_member(group_id, target.id,
                ChatPermissions(can_send_messages=False), until_date=until)
            await msg.reply_text(config.MSG_MUTE.format(name=get_name(target), duration=hours))
        except TelegramError as e:
            await msg.reply_text(f"❌ خطا: {e}")
    elif cmd == 'آزاد' and msg.reply_to_message:
        target = msg.reply_to_message.from_user
        try:
            await context.bot.restrict_chat_member(group_id, target.id,
                ChatPermissions(can_send_messages=True, can_send_photos=True,
                    can_send_videos=True, can_send_other_messages=True))
            await msg.reply_text(config.MSG_FREE.format(name=get_name(target)))
        except TelegramError as e:
            await msg.reply_text(f"❌ خطا: {e}")
    elif cmd == 'ریست' and msg.reply_to_message:
        target = msg.reply_to_message.from_user
        db.reset_warnings(group_id, target.id)
        await msg.reply_text(f"✅ اخطارهای {get_name(target)} پاک شد.")
    elif cmd.startswith('خاموشی'):
        match = re.match(r'خاموشی\s*(\d)\s*از\s*(\d{1,2}:\d{2})\s*تا\s*(\d{1,2}:\d{2})', cmd)
        if match:
            num, from_t, to_t = match.group(1), match.group(2), match.group(3)
            db.update_setting(group_id, f'quiet_{num}_from', from_t)
            db.update_setting(group_id, f'quiet_{num}_to', to_t)
            await msg.reply_text(f"✅ خاموشی {num} از {from_t} تا {to_t} تنظیم شد.")
        else:
            match2 = re.match(r'خاموشی\s*(\d)\s*غیرفعال', cmd)
            if match2:
                num = match2.group(1)
                db.update_setting(group_id, f'quiet_{num}_from', None)
                db.update_setting(group_id, f'quiet_{num}_to', None)
                await msg.reply_text(f"✅ خاموشی {num} غیرفعال شد.")
    elif cmd.startswith('لینک گروه '):
        link = cmd.replace('لینک گروه ', '').strip()
        conn = db.get_conn()
        conn.execute("UPDATE groups SET group_link=? WHERE group_id=?", (link, group_id))
        conn.commit(); conn.close()
        await msg.reply_text(f"✅ لینک گروه تنظیم شد.")
    elif cmd.startswith('توضیحات گروه '):
        info = cmd.replace('توضیحات گروه ', '').strip()
        conn = db.get_conn()
        conn.execute("UPDATE groups SET group_info=? WHERE group_id=?", (info, group_id))
        conn.commit(); conn.close()
        await msg.reply_text("✅ توضیحات گروه تنظیم شد.")

# ============================================
# اضافه شدن ربات به گروه
# ============================================

async def bot_added_to_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.my_chat_member:
        chat = update.effective_chat
        user = update.my_chat_member.from_user
        new_status = update.my_chat_member.new_chat_member.status
        if new_status in ['member', 'administrator'] and chat.type in ['group', 'supergroup']:
            db.add_group(chat.id, chat.title, user.id, user.username or "")
            db.activate_group_free(chat.id)
            try:
                await context.bot.send_message(chat.id,
                    f"✅ ربات هیوا به گروه «{chat.title}» اضافه شد!\n\n"
                    f"برای تنظیمات، به پیوی ربات بروید و /start بزنید.")
            except: pass
            try:
                await context.bot.send_message(config.ADMIN_ID,
                    f"🆕 گروه جدید:\n🏠 {chat.title}\n🆔 {chat.id}\n"
                    f"👤 {get_name(user)} (@{user.username or '-'})")
            except: pass
        elif new_status in ['left', 'kicked'] and chat.type in ['group', 'supergroup']:
            db.deactivate_group(chat.id)
            try:
                await context.bot.send_message(config.ADMIN_ID,
                    f"⚠️ ربات از گروه خارج شد:\n🏠 {chat.title}\n🆔 {chat.id}")
            except: pass

# ============================================
# راه‌اندازی
# ============================================

def main():
    db.init_db()
    app = Application.builder().token(config.BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(ChatMemberHandler(bot_added_to_group, ChatMemberHandler.MY_CHAT_MEMBER))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.ChatType.PRIVATE & filters.TEXT & ~filters.COMMAND, private_message))
    app.add_handler(MessageHandler(filters.ChatType.GROUPS & filters.StatusUpdate.NEW_CHAT_MEMBERS, member_joined))
    app.add_handler(MessageHandler(filters.ChatType.GROUPS & ~filters.COMMAND, filter_messages))
    print("🤖 ربات هیوا در حال اجراست...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
