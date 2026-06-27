# ============================================
# ربات مدیر گروه هیوا
# فایل اصلی
# ============================================

import logging
import asyncio
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

# تنظیم لاگ
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

def format_price(amount):
    return f"{amount:,} تومان"

# ============================================
# بررسی ساعت خاموشی
# ============================================

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
            else:  # شب گذشته از نیمه شب
                if now >= from_time or now <= to_time:
                    return True
    return False

# ============================================
# هندلر ورود اعضای جدید
# ============================================

async def member_joined(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.new_chat_members:
        return

    group_id = update.effective_chat.id
    if not db.is_group_active(group_id):
        return

    group = db.get_group(group_id)
    inviter = update.message.from_user

    for new_member in update.message.new_chat_members:
        if new_member.is_bot:
            continue

        # ثبت دعوت
        if inviter and inviter.id != new_member.id:
            db.add_invite(
                group_id,
                inviter.id, get_name(inviter),
                new_member.id, get_name(new_member)
            )

        # پیام خوش‌آمدگویی
        msg = config.MSG_WELCOME.format(
            name=get_name(new_member),
            group=update.effective_chat.title or "گروه"
        )
        await update.message.reply_text(msg)

# ============================================
# فیلتر پیام‌ها
# ============================================

async def filter_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_user:
        return

    group_id = update.effective_chat.id
    user = update.effective_user
    msg = update.message

    if not db.is_group_active(group_id):
        return

    # ادمین‌ها معاف هستند
    if await is_group_admin(update, user.id):
        await handle_commands(update, context)
        return

    settings = db.get_settings(group_id)

    # بررسی ساعت خاموشی
    if is_quiet_time(group_id):
        await msg.delete()
        db.log_deleted_message(group_id, user.id, "ساعت خاموشی گروه")
        return

    reason = None

    # بررسی انواع قفل
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
            bad_words = ['فحش1', 'فحش2']  # لیست کلمات ممنوع
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
            warn_msg = await update.effective_chat.send_message(
                f"🚫 {get_name(user)}، {reason}."
            )
            await asyncio.sleep(5)
            await warn_msg.delete()
        except TelegramError:
            pass
        return

    # بررسی دستورات عمومی
    await handle_public_commands(update, context)

# ============================================
# دستورات عمومی (بدون !)
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
        if link:
            await msg.reply_text(config.MSG_GROUP_LINK.format(link=link))
        else:
            await msg.reply_text("❌ لینک گروه تنظیم نشده است.")

    elif text == "این گروه برای چیه؟":
        group = db.get_group(group_id)
        info = group.get('group_info') if group else None
        if info:
            await msg.reply_text(config.MSG_GROUP_INFO.format(info=info))
        else:
            await msg.reply_text("❌ توضیحات گروه تنظیم نشده است.")

    elif text == "من را کی اد کرده است؟":
        inviter = db.get_who_invited(group_id, user.id)
        if inviter:
            await msg.reply_text(f"👤 شما توسط {inviter} اضافه شدید.")
        else:
            await msg.reply_text("❓ اطلاعاتی یافت نشد.")

    elif text == "این کاربر را کی اد کرده است؟" and msg.reply_to_message:
        target = msg.reply_to_message.from_user
        inviter = db.get_who_invited(group_id, target.id)
        if inviter:
            await msg.reply_text(f"👤 {get_name(target)} توسط {inviter} اضافه شد.")
        else:
            await msg.reply_text("❓ اطلاعاتی یافت نشد.")

    elif text == "گزارش" and msg.reply_to_message:
        reported_msg = msg.reply_to_message
        report_text = config.MSG_REPORT.format(
            name=get_name(user),
            message=reported_msg.text or "[محتوای غیر متنی]"
        )
        await context.bot.send_message(config.ADMIN_ID, report_text)
        await msg.reply_text("✅ گزارش شما ارسال شد.")

    elif text == "من چند نفر اد کردم؟":
        count = db.get_user_invite_count(group_id, user.id)
        await msg.reply_text(f"📊 شما {count} نفر را اضافه کرده‌اید.")

    elif text == "این کاربر چند نفر اد کرده است؟" and msg.reply_to_message:
        target = msg.reply_to_message.from_user
        count = db.get_user_invite_count(group_id, target.id)
        await msg.reply_text(f"📊 {get_name(target)} تعداد {count} نفر را اضافه کرده است.")

    elif text == "اطلاعات من":
        count = db.get_user_invite_count(group_id, user.id)
        warns = db.get_warnings(group_id, user.id)
        inviter = db.get_who_invited(group_id, user.id)
        text_out = f"👤 اطلاعات {get_name(user)}:\n"
        text_out += f"📨 تعداد اد: {count}\n"
        text_out += f"⚠️ اخطارها: {warns}/3\n"
        text_out += f"👥 توسط: {inviter or 'نامشخص'}"
        await msg.reply_text(text_out)

    elif text == "اطلاعات" and msg.reply_to_message:
        target = msg.reply_to_message.from_user
        count = db.get_user_invite_count(group_id, target.id)
        warns = db.get_warnings(group_id, target.id)
        inviter = db.get_who_invited(group_id, target.id)
        text_out = f"👤 اطلاعات {get_name(target)}:\n"
        text_out += f"📨 تعداد اد: {count}\n"
        text_out += f"⚠️ اخطارها: {warns}/3\n"
        text_out += f"👥 توسط: {inviter or 'نامشخص'}"
        await msg.reply_text(text_out)

    elif text == "پیام من چرا حذف شد؟":
        reason = db.get_last_delete_reason(group_id, user.id)
        if reason:
            await msg.reply_text(f"❌ آخرین دلیل حذف پیام شما:\n{reason}")
        else:
            await msg.reply_text("❓ اطلاعاتی یافت نشد.")

# ============================================
# دستورات ادمین (با ! یا .)
# ============================================

async def handle_commands(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    msg = update.message
    text = msg.text.strip()
    group_id = update.effective_chat.id
    user = update.effective_user

    if not (text.startswith('!') or text.startswith('.')):
        await handle_public_commands(update, context)
        return

    cmd = text[1:].strip()

    # --- مدیریت کاربران ---
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
            await context.bot.restrict_chat_member(
                group_id, target.id,
                ChatPermissions(can_send_messages=False),
                until_date=until
            )
            await msg.reply_text(config.MSG_MUTE.format(name=get_name(target), duration=hours))
        except TelegramError as e:
            await msg.reply_text(f"❌ خطا: {e}")

    elif cmd == 'آزاد' and msg.reply_to_message:
        target = msg.reply_to_message.from_user
        try:
            await context.bot.restrict_chat_member(
                group_id, target.id,
                ChatPermissions(
                    can_send_messages=True, can_send_photos=True,
                    can_send_videos=True, can_send_other_messages=True
                )
            )
            await msg.reply_text(config.MSG_FREE.format(name=get_name(target)))
        except TelegramError as e:
            await msg.reply_text(f"❌ خطا: {e}")

    elif cmd == 'ریست' and msg.reply_to_message:
        target = msg.reply_to_message.from_user
        db.reset_warnings(group_id, target.id)
        await msg.reply_text(f"✅ اخطارهای {get_name(target)} پاک شد.")

    # --- آمار دعوت ---
    elif 'کیا بیشتر از همه اد کردند' in cmd:
        hours = None
        if 'ساعت' in cmd:
            import re
            match = re.search(r'(\d+)\s*ساعت', cmd)
            if match:
                hours = int(match.group(1))
        elif 'روز' in cmd:
            import re
            match = re.search(r'(\d+)\s*روز', cmd)
            if match:
                hours = int(match.group(1)) * 24

        stats = db.get_invite_stats(group_id, hours)
        if not stats:
            await msg.reply_text("❓ آماری یافت نشد.")
            return

        text_out = "📊 لیست بیشترین دعوت‌کنندگان:\n\n"
        for i, s in enumerate(stats[:10], 1):
            text_out += f"{i}. {s['inviter_name']}: {s['count']} نفر\n"
        await msg.reply_text(text_out)

    # --- قفل‌ها ---
    elif cmd == 'لینک قفل':
        db.update_setting(group_id, 'lock_link', 1)
        await msg.reply_text("🔒 لینک‌های تلگرام قفل شد.")
    elif cmd == 'لینک آزاد':
        db.update_setting(group_id, 'lock_link', 0)
        await msg.reply_text("🔓 لینک‌های تلگرام آزاد شد.")

    elif cmd == 'آیدی قفل':
        db.update_setting(group_id, 'lock_id', 1)
        await msg.reply_text("🔒 آیدی و منشن قفل شد.")
    elif cmd == 'آیدی آزاد':
        db.update_setting(group_id, 'lock_id', 0)
        await msg.reply_text("🔓 آیدی و منشن آزاد شد.")

    elif cmd == 'سایت قفل':
        db.update_setting(group_id, 'lock_site', 1)
        await msg.reply_text("🔒 لینک سایت قفل شد.")
    elif cmd == 'سایت آزاد':
        db.update_setting(group_id, 'lock_site', 0)
        await msg.reply_text("🔓 لینک سایت آزاد شد.")

    elif cmd == 'مستهجن قفل':
        db.update_setting(group_id, 'lock_bad_words', 1)
        await msg.reply_text("🔒 کلمات مستهجن قفل شد.")
    elif cmd == 'مستهجن آزاد':
        db.update_setting(group_id, 'lock_bad_words', 0)
        await msg.reply_text("🔓 کلمات مستهجن آزاد شد.")

    elif cmd == 'هشتگ قفل':
        db.update_setting(group_id, 'lock_hashtag', 1)
        await msg.reply_text("🔒 هشتگ قفل شد.")
    elif cmd == 'هشتگ آزاد':
        db.update_setting(group_id, 'lock_hashtag', 0)
        await msg.reply_text("🔓 هشتگ آزاد شد.")

    elif cmd == 'متن قفل':
        db.update_setting(group_id, 'lock_text', 1)
        await msg.reply_text("🔒 ارسال متن قفل شد.")
    elif cmd == 'متن آزاد':
        db.update_setting(group_id, 'lock_text', 0)
        await msg.reply_text("🔓 ارسال متن آزاد شد.")

    elif cmd == 'فوروارد قفل':
        db.update_setting(group_id, 'lock_forward', 1)
        await msg.reply_text("🔒 فوروارد قفل شد.")
    elif cmd == 'فوروارد آزاد':
        db.update_setting(group_id, 'lock_forward', 0)
        await msg.reply_text("🔓 فوروارد آزاد شد.")

    elif cmd == 'فوروارد از کانال قفل':
        db.update_setting(group_id, 'lock_forward_channel', 1)
        await msg.reply_text("🔒 فوروارد از کانال قفل شد.")
    elif cmd == 'فوروارد از کانال آزاد':
        db.update_setting(group_id, 'lock_forward_channel', 0)
        await msg.reply_text("🔓 فوروارد از کانال آزاد شد.")

    elif cmd == 'عکس قفل':
        db.update_setting(group_id, 'lock_photo', 1)
        await msg.reply_text("🔒 ارسال عکس قفل شد.")
    elif cmd == 'عکس آزاد':
        db.update_setting(group_id, 'lock_photo', 0)
        await msg.reply_text("🔓 ارسال عکس آزاد شد.")

    elif cmd == 'فیلم قفل':
        db.update_setting(group_id, 'lock_video', 1)
        await msg.reply_text("🔒 ارسال فیلم قفل شد.")
    elif cmd == 'فیلم آزاد':
        db.update_setting(group_id, 'lock_video', 0)
        await msg.reply_text("🔓 ارسال فیلم آزاد شد.")

    elif cmd == 'استیکر قفل':
        db.update_setting(group_id, 'lock_sticker', 1)
        await msg.reply_text("🔒 ارسال استیکر قفل شد.")
    elif cmd == 'استیکر آزاد':
        db.update_setting(group_id, 'lock_sticker', 0)
        await msg.reply_text("🔓 ارسال استیکر آزاد شد.")

    elif cmd == 'لوکیشن قفل':
        db.update_setting(group_id, 'lock_location', 1)
        await msg.reply_text("🔒 ارسال لوکیشن قفل شد.")
    elif cmd == 'لوکیشن آزاد':
        db.update_setting(group_id, 'lock_location', 0)
        await msg.reply_text("🔓 ارسال لوکیشن آزاد شد.")

    elif cmd == 'شماره تلفن قفل':
        db.update_setting(group_id, 'lock_phone', 1)
        await msg.reply_text("🔒 ارسال شماره تلفن قفل شد.")
    elif cmd == 'شماره تلفن آزاد':
        db.update_setting(group_id, 'lock_phone', 0)
        await msg.reply_text("🔓 ارسال شماره تلفن آزاد شد.")

    elif cmd == 'صدای ضبط شده قفل':
        db.update_setting(group_id, 'lock_voice', 1)
        await msg.reply_text("🔒 ارسال صدا قفل شد.")
    elif cmd == 'صدای ضبط شده آزاد':
        db.update_setting(group_id, 'lock_voice', 0)
        await msg.reply_text("🔓 ارسال صدا آزاد شد.")

    elif cmd == 'فایل قفل':
        db.update_setting(group_id, 'lock_file', 1)
        await msg.reply_text("🔒 ارسال فایل قفل شد.")
    elif cmd == 'فایل آزاد':
        db.update_setting(group_id, 'lock_file', 0)
        await msg.reply_text("🔓 ارسال فایل آزاد شد.")

    elif cmd == 'نرم افزار قفل':
        db.update_setting(group_id, 'lock_software', 1)
        await msg.reply_text("🔒 ارسال نرم افزار قفل شد.")
    elif cmd == 'نرم افزار آزاد':
        db.update_setting(group_id, 'lock_software', 0)
        await msg.reply_text("🔓 ارسال نرم افزار آزاد شد.")

    elif cmd == 'گیف قفل':
        db.update_setting(group_id, 'lock_gif', 1)
        await msg.reply_text("🔒 ارسال گیف قفل شد.")
    elif cmd == 'گیف آزاد':
        db.update_setting(group_id, 'lock_gif', 0)
        await msg.reply_text("🔓 ارسال گیف آزاد شد.")

    elif cmd == 'نظرسنجی قفل':
        db.update_setting(group_id, 'lock_poll', 1)
        await msg.reply_text("🔒 ارسال نظرسنجی قفل شد.")
    elif cmd == 'نظرسنجی آزاد':
        db.update_setting(group_id, 'lock_poll', 0)
        await msg.reply_text("🔓 ارسال نظرسنجی آزاد شد.")

    elif cmd == 'اسلش قفل':
        db.update_setting(group_id, 'lock_slash', 1)
        await msg.reply_text("🔒 اسلش کامند قفل شد.")
    elif cmd == 'اسلش آزاد':
        db.update_setting(group_id, 'lock_slash', 0)
        await msg.reply_text("🔓 اسلش کامند آزاد شد.")

    elif cmd == 'دستورات عمومی قفل':
        db.update_setting(group_id, 'public_commands', 0)
        await msg.reply_text("🔒 دستورات عمومی غیرفعال شد.")
    elif cmd == 'دستورات عمومی آزاد':
        db.update_setting(group_id, 'public_commands', 1)
        await msg.reply_text("🔓 دستورات عمومی فعال شد.")

    # --- ساعت خاموشی ---
    elif cmd.startswith('خاموشی'):
        import re
        match = re.match(r'خاموشی\s*(\d)\s*از\s*(\d{1,2}:\d{2})\s*تا\s*(\d{1,2}:\d{2})', cmd)
        if match:
            num = match.group(1)
            from_t = match.group(2)
            to_t = match.group(3)
            db.update_setting(group_id, f'quiet_{num}_from', from_t)
            db.update_setting(group_id, f'quiet_{num}_to', to_t)
            await msg.reply_text(f"✅ خاموشی {num} از {from_t} تا {to_t} تنظیم شد.")
        elif re.match(r'خاموشی\s*(\d)\s*غیرفعال', cmd):
            match2 = re.match(r'خاموشی\s*(\d)\s*غیرفعال', cmd)
            num = match2.group(1)
            db.update_setting(group_id, f'quiet_{num}_from', None)
            db.update_setting(group_id, f'quiet_{num}_to', None)
            await msg.reply_text(f"✅ خاموشی {num} غیرفعال شد.")

    # --- تنظیمات گروه ---
    elif cmd.startswith('لینک گروه '):
        link = cmd.replace('لینک گروه ', '').strip()
        db.get_conn().execute("UPDATE groups SET group_link=? WHERE group_id=?", (link, group_id))
        db.get_conn().commit()
        await msg.reply_text(f"✅ لینک گروه تنظیم شد: {link}")

    elif cmd.startswith('توضیحات گروه '):
        info = cmd.replace('توضیحات گروه ', '').strip()
        conn = db.get_conn()
        conn.execute("UPDATE groups SET group_info=? WHERE group_id=?", (info, group_id))
        conn.commit()
        conn.close()
        await msg.reply_text("✅ توضیحات گروه تنظیم شد.")

# ============================================
# دستور /start در پیوی
# ============================================

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat

    if chat.type != 'private':
        return

    keyboard = [
        [InlineKeyboardButton("🆓 تست رایگان ۳ روزه", callback_data="trial")],
        [InlineKeyboardButton("💳 خرید اشتراک", callback_data="subscribe")],
        [InlineKeyboardButton("📊 وضعیت اشتراک", callback_data="status")],
    ]

    if is_admin(user.id):
        keyboard.append([InlineKeyboardButton("⚙️ پنل مدیریت", callback_data="admin_panel")])

    await update.message.reply_text(
        f"👋 سلام {get_name(user)}!\n\n"
        "به ربات مدیر گروه هیوا خوش اومدید 🤖\n\n"
        "با این ربات می‌تونید گروه تلگرامتون رو مدیریت کنید.\n\n"
        "یکی از گزینه‌های زیر رو انتخاب کنید:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ============================================
# هندلر دکمه‌ها
# ============================================

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    data = query.data

    if data == "trial":
        await query.edit_message_text(
            "برای فعال کردن تست رایگان، آیدی عددی گروهتون رو بفرستید.\n\n"
            "برای پیدا کردن آیدی گروه، ربات @userinfobot رو به گروه اضافه کنید."
        )
        context.user_data['action'] = 'trial'

    elif data == "subscribe":
        plans_text = "💳 پلن‌های اشتراک:\n\n"
        keyboard = []
        for key, plan in config.PLANS.items():
            plans_text += f"• {plan['name']}: {format_price(plan['price'])}\n"
            keyboard.append([InlineKeyboardButton(
                f"{plan['name']} - {format_price(plan['price'])}",
                callback_data=f"plan_{key}"
            )])
        keyboard.append([InlineKeyboardButton("🔙 برگشت", callback_data="back")])
        await query.edit_message_text(plans_text, reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("plan_"):
        plan_key = data.split("_")[1]
        plan = config.PLANS[plan_key]
        context.user_data['selected_plan'] = plan_key
        payment_text = config.MSG_PAYMENT_INFO.format(
            amount=format_price(plan['price']),
            card=config.CARD_NUMBER,
            owner=config.CARD_OWNER
        )
        payment_text += f"\n\nبعد از واریز، شناسه پیگیری و آیدی گروه رو بفرستید."
        context.user_data['action'] = 'payment'
        await query.edit_message_text(payment_text)

    elif data == "status":
        await query.edit_message_text(
            "آیدی عددی گروهتون رو بفرستید تا وضعیت اشتراک رو ببینید."
        )
        context.user_data['action'] = 'check_status'

    elif data == "admin_panel" and is_admin(user.id):
        pending = db.get_pending_payments()
        active = db.get_all_active_groups()
        text = f"⚙️ پنل مدیریت هیوا\n\n"
        text += f"📊 گروه‌های فعال: {len(active)}\n"
        text += f"💳 پرداخت‌های در انتظار: {len(pending)}\n\n"

        keyboard = []
        if pending:
            keyboard.append([InlineKeyboardButton("💳 بررسی پرداخت‌ها", callback_data="check_payments")])
        keyboard.append([InlineKeyboardButton("📋 لیست گروه‌ها", callback_data="list_groups")])

        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "check_payments" and is_admin(user.id):
        pending = db.get_pending_payments()
        if not pending:
            await query.edit_message_text("✅ پرداخت در انتظاری وجود ندارد.")
            return

        for p in pending[:5]:
            plan = config.PLANS.get(p['plan'], {})
            text = (
                f"💳 پرداخت #{p['id']}\n"
                f"👤 کاربر: {p['user_id']}\n"
                f"🏠 گروه: {p['group_id']}\n"
                f"📦 پلن: {plan.get('name', p['plan'])}\n"
                f"💰 مبلغ: {format_price(p['amount'])}\n"
                f"🔢 شناسه: {p['tracking_code']}\n"
                f"📅 تاریخ: {p['created_at']}"
            )
            keyboard = [[
                InlineKeyboardButton("✅ تأیید", callback_data=f"confirm_{p['id']}"),
                InlineKeyboardButton("❌ رد", callback_data=f"reject_{p['id']}")
            ]]
            await context.bot.send_message(
                user.id, text,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

    elif data.startswith("confirm_") and is_admin(user.id):
        pay_id = int(data.split("_")[1])
        payment = db.get_payment(pay_id)
        if not payment:
            await query.edit_message_text("❌ پرداخت یافت نشد.")
            return

        plan = config.PLANS.get(payment['plan'], {})
        expiry = db.activate_group(payment['group_id'], plan.get('days', 30), payment['plan'])
        db.confirm_payment(pay_id)

        await query.edit_message_text(f"✅ پرداخت #{pay_id} تأیید شد. گروه فعال شد تا {expiry}")

        try:
            await context.bot.send_message(
                payment['user_id'],
                f"✅ پرداخت شما تأیید شد!\n"
                f"اشتراک {plan.get('name', '')} فعال شد.\n"
                f"انقضا: {expiry}"
            )
        except:
            pass

    elif data.startswith("reject_") and is_admin(user.id):
        pay_id = int(data.split("_")[1])
        payment = db.get_payment(pay_id)
        await query.edit_message_text(f"❌ پرداخت #{pay_id} رد شد.")
        try:
            await context.bot.send_message(
                payment['user_id'],
                "❌ متأسفانه پرداخت شما تأیید نشد.\nلطفاً دوباره تلاش کنید یا با پشتیبانی تماس بگیرید."
            )
        except:
            pass

    elif data == "back":
        await cmd_start(update, context)

# ============================================
# هندلر پیام‌های پیوی
# ============================================

async def private_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != 'private':
        return

    user = update.effective_user
    text = update.message.text
    action = context.user_data.get('action')

    if action == 'trial':
        try:
            group_id = int(text.strip())
            group = db.get_group(group_id)
            if not group:
                await update.message.reply_text("❌ این گروه ثبت نشده. ابتدا ربات را به گروه اضافه کنید.")
                return
            if group.get('trial_used'):
                await update.message.reply_text("❌ این گروه قبلاً از تست رایگان استفاده کرده.")
                return
            expiry = db.activate_group(group_id, config.FREE_TRIAL_DAYS, "trial", is_trial=True)
            await update.message.reply_text(
                config.MSG_TRIAL_START.format(
                    group=group.get('group_name', group_id),
                    expiry=expiry
                )
            )
            context.user_data.clear()
        except ValueError:
            await update.message.reply_text("❌ آیدی وارد شده معتبر نیست.")

    elif action == 'payment':
        plan_key = context.user_data.get('selected_plan')
        plan = config.PLANS.get(plan_key, {})
        parts = text.strip().split()
        if len(parts) < 2:
            await update.message.reply_text("لطفاً شناسه پیگیری و آیدی گروه را با فاصله بفرستید.\nمثال: 123456789 -1001234567890")
            return
        tracking = parts[0]
        try:
            group_id = int(parts[1])
        except ValueError:
            await update.message.reply_text("❌ آیدی گروه معتبر نیست.")
            return

        pay_id = db.add_payment(user.id, group_id, plan_key, plan.get('price', 0), tracking)
        await update.message.reply_text(
            f"✅ درخواست شما ثبت شد (شماره {pay_id})\n"
            "بعد از بررسی توسط ادمین، اشتراک فعال می‌شود."
        )

        # اطلاع به ادمین
        await context.bot.send_message(
            config.ADMIN_ID,
            f"💳 پرداخت جدید!\n"
            f"👤 کاربر: {get_name(user)} ({user.id})\n"
            f"📦 پلن: {plan.get('name', plan_key)}\n"
            f"💰 مبلغ: {format_price(plan.get('price', 0))}\n"
            f"🔢 شناسه: {tracking}\n"
            f"🏠 گروه: {group_id}\n\n"
            f"برای بررسی: /admin",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("✅ تأیید", callback_data=f"confirm_{pay_id}"),
                InlineKeyboardButton("❌ رد", callback_data=f"reject_{pay_id}")
            ]])
        )
        context.user_data.clear()

    elif action == 'check_status':
        try:
            group_id = int(text.strip())
            is_active = db.is_group_active(group_id)
            days = db.get_days_until_expiry(group_id)
            group = db.get_group(group_id)
            if not group:
                await update.message.reply_text("❌ گروه یافت نشد.")
                return
            status = "✅ فعال" if is_active else "❌ غیرفعال"
            text_out = f"📊 وضعیت گروه:\nوضعیت: {status}\n"
            if days is not None:
                text_out += f"روزهای باقیمانده: {days} روز\nانقضا: {group.get('expiry_date', 'نامشخص')}"
            await update.message.reply_text(text_out)
            context.user_data.clear()
        except ValueError:
            await update.message.reply_text("❌ آیدی معتبر نیست.")

# ============================================
# زمانبند بررسی انقضا
# ============================================

async def check_expiries(context: ContextTypes.DEFAULT_TYPE):
    groups = db.get_all_active_groups()
    for group in groups:
        days = db.get_days_until_expiry(group['group_id'])
        if days is None:
            continue

        if days <= 0:
            db.deactivate_group(group['group_id'])
            try:
                await context.bot.send_message(
                    group['owner_id'],
                    config.MSG_SUB_EXPIRED.format(
                        group=group.get('group_name', group['group_id'])
                    )
                )
            except:
                pass

        elif days <= config.EXPIRY_WARNING_DAYS:
            try:
                await context.bot.send_message(
                    group['owner_id'],
                    config.MSG_SUB_EXPIRY_WARNING.format(
                        group=group.get('group_name', group['group_id']),
                        days=days
                    )
                )
            except:
                pass

# ============================================
# هندلر اضافه شدن ربات به گروه
# ============================================

async def bot_added_to_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.my_chat_member:
        chat = update.effective_chat
        user = update.my_chat_member.from_user
        new_status = update.my_chat_member.new_chat_member.status

        if new_status in ['member', 'administrator'] and chat.type in ['group', 'supergroup']:
            db.add_group(chat.id, chat.title, user.id, user.username or "")
            try:
                await context.bot.send_message(
                    user.id,
                    f"✅ ربات هیوا به گروه «{chat.title}» اضافه شد!\n\n"
                    f"آیدی گروه: {chat.id}\n\n"
                    f"برای فعال کردن تست رایگان ۳ روزه یا خرید اشتراک:\n"
                    f"به ربات پیام بدید و /start بزنید."
                )
            except:
                pass

# ============================================
# راه‌اندازی ربات
# ============================================

def main():
    db.init_db()

    app = Application.builder().token(config.BOT_TOKEN).build()

    # هندلرها
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(ChatMemberHandler(bot_added_to_group, ChatMemberHandler.MY_CHAT_MEMBER))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.ChatType.PRIVATE & filters.TEXT & ~filters.COMMAND, private_message))
    app.add_handler(MessageHandler(filters.ChatType.GROUPS & filters.StatusUpdate.NEW_CHAT_MEMBERS, member_joined))
    app.add_handler(MessageHandler(filters.ChatType.GROUPS & ~filters.COMMAND, filter_messages))

    # زمانبند بررسی انقضا (هر ۶ ساعت)
    app.job_queue.run_repeating(check_expiries, interval=21600, first=60)

    print("🤖 ربات هیوا در حال اجراست...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
