# ============================================
# ربات مدیر گروه هیوا
# فایل اصلی - نسخه سازگار
# ============================================

import logging
import re
from datetime import datetime, timedelta
from telegram import (
    Update, ChatPermissions, InlineKeyboardButton, InlineKeyboardMarkup, ParseMode
)
from telegram.ext import (
    Updater, CommandHandler, MessageHandler, CallbackQueryHandler,
    Filters, CallbackContext
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

def is_group_admin(bot, chat_id, user_id):
    try:
        member = bot.get_chat_member(chat_id, user_id)
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
# هندلر ورود اعضای جدید
# ============================================

def member_joined(update: Update, context: CallbackContext):
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
            db.add_invite(
                group_id,
                inviter.id, get_name(inviter),
                new_member.id, get_name(new_member)
            )

        msg = config.MSG_WELCOME.format(
            name=get_name(new_member),
            group=update.effective_chat.title or "گروه"
        )
        update.message.reply_text(msg)

# ============================================
# فیلتر پیام‌ها
# ============================================

def filter_messages(update: Update, context: CallbackContext):
    if not update.message or not update.effective_user:
        return

    group_id = update.effective_chat.id
    user = update.effective_user
    msg = update.message

    if not db.is_group_active(group_id):
        return

    if is_group_admin(context.bot, group_id, user.id):
        handle_admin_commands(update, context)
        return

    settings = db.get_settings(group_id)

    if is_quiet_time(group_id):
        try:
            msg.delete()
            db.log_deleted_message(group_id, user.id, "ساعت خاموشی گروه")
        except:
            pass
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
            msg.delete()
            db.log_deleted_message(group_id, user.id, reason)
            warn_msg = update.effective_chat.send_message(f"🚫 {get_name(user)}، {reason}.")
            import threading
            def delete_later():
                import time
                time.sleep(5)
                try:
                    warn_msg.delete()
                except:
                    pass
            threading.Thread(target=delete_later).start()
        except TelegramError:
            pass
        return

    handle_public_commands(update, context)

# ============================================
# دستورات عمومی
# ============================================

def handle_public_commands(update: Update, context: CallbackContext):
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
            msg.reply_text(config.MSG_GROUP_LINK.format(link=link))
        else:
            msg.reply_text("❌ لینک گروه تنظیم نشده است.")

    elif text == "این گروه برای چیه؟":
        group = db.get_group(group_id)
        info = group.get('group_info') if group else None
        if info:
            msg.reply_text(config.MSG_GROUP_INFO.format(info=info))
        else:
            msg.reply_text("❌ توضیحات گروه تنظیم نشده است.")

    elif text == "من را کی اد کرده است؟":
        inviter = db.get_who_invited(group_id, user.id)
        if inviter:
            msg.reply_text(f"👤 شما توسط {inviter} اضافه شدید.")
        else:
            msg.reply_text("❓ اطلاعاتی یافت نشد.")

    elif text == "این کاربر را کی اد کرده است؟" and msg.reply_to_message:
        target = msg.reply_to_message.from_user
        inviter = db.get_who_invited(group_id, target.id)
        if inviter:
            msg.reply_text(f"👤 {get_name(target)} توسط {inviter} اضافه شد.")
        else:
            msg.reply_text("❓ اطلاعاتی یافت نشد.")

    elif text == "گزارش" and msg.reply_to_message:
        reported_msg = msg.reply_to_message
        report_text = config.MSG_REPORT.format(
            name=get_name(user),
            message=reported_msg.text or "[محتوای غیر متنی]"
        )
        context.bot.send_message(config.ADMIN_ID, report_text)
        msg.reply_text("✅ گزارش شما ارسال شد.")

    elif text == "من چند نفر اد کردم؟":
        count = db.get_user_invite_count(group_id, user.id)
        msg.reply_text(f"📊 شما {count} نفر را اضافه کرده‌اید.")

    elif text == "این کاربر چند نفر اد کرده است؟" and msg.reply_to_message:
        target = msg.reply_to_message.from_user
        count = db.get_user_invite_count(group_id, target.id)
        msg.reply_text(f"📊 {get_name(target)} تعداد {count} نفر را اضافه کرده است.")

    elif text == "اطلاعات من":
        count = db.get_user_invite_count(group_id, user.id)
        warns = db.get_warnings(group_id, user.id)
        inviter = db.get_who_invited(group_id, user.id)
        text_out = f"👤 اطلاعات {get_name(user)}:\n📨 تعداد اد: {count}\n⚠️ اخطارها: {warns}/3\n👥 توسط: {inviter or 'نامشخص'}"
        msg.reply_text(text_out)

    elif text == "اطلاعات" and msg.reply_to_message:
        target = msg.reply_to_message.from_user
        count = db.get_user_invite_count(group_id, target.id)
        warns = db.get_warnings(group_id, target.id)
        inviter = db.get_who_invited(group_id, target.id)
        text_out = f"👤 اطلاعات {get_name(target)}:\n📨 تعداد اد: {count}\n⚠️ اخطارها: {warns}/3\n👥 توسط: {inviter or 'نامشخص'}"
        msg.reply_text(text_out)

    elif text == "پیام من چرا حذف شد؟":
        reason = db.get_last_delete_reason(group_id, user.id)
        if reason:
            msg.reply_text(f"❌ آخرین دلیل حذف پیام شما:\n{reason}")
        else:
            msg.reply_text("❓ اطلاعاتی یافت نشد.")

# ============================================
# دستورات ادمین
# ============================================

def handle_admin_commands(update: Update, context: CallbackContext):
    if not update.message or not update.message.text:
        return

    msg = update.message
    text = msg.text.strip()
    group_id = update.effective_chat.id

    if not (text.startswith('!') or text.startswith('.')):
        handle_public_commands(update, context)
        return

    cmd = text[1:].strip()

    if cmd.startswith('اخراج') and msg.reply_to_message:
        parts = cmd.split()
        hours = int(parts[1]) if len(parts) > 1 else 0
        target = msg.reply_to_message.from_user
        try:
            until = datetime.now() + timedelta(hours=hours) if hours and hours != 1000 else None
            context.bot.ban_chat_member(group_id, target.id, until_date=until)
            msg.reply_text(config.MSG_BAN.format(name=get_name(target)))
        except TelegramError as e:
            msg.reply_text(f"❌ خطا: {e}")

    elif cmd.startswith('ساکت') and msg.reply_to_message:
        parts = cmd.split()
        hours = int(parts[1]) if len(parts) > 1 else 1
        target = msg.reply_to_message.from_user
        try:
            until = None if hours == 1000 else datetime.now() + timedelta(hours=hours)
            context.bot.restrict_chat_member(
                group_id, target.id,
                ChatPermissions(can_send_messages=False),
                until_date=until
            )
            msg.reply_text(config.MSG_MUTE.format(name=get_name(target), duration=hours))
        except TelegramError as e:
            msg.reply_text(f"❌ خطا: {e}")

    elif cmd == 'آزاد' and msg.reply_to_message:
        target = msg.reply_to_message.from_user
        try:
            context.bot.restrict_chat_member(
                group_id, target.id,
                ChatPermissions(
                    can_send_messages=True, can_send_photos=True,
                    can_send_videos=True, can_send_other_messages=True
                )
            )
            msg.reply_text(config.MSG_FREE.format(name=get_name(target)))
        except TelegramError as e:
            msg.reply_text(f"❌ خطا: {e}")

    elif cmd == 'ریست' and msg.reply_to_message:
        target = msg.reply_to_message.from_user
        db.reset_warnings(group_id, target.id)
        msg.reply_text(f"✅ اخطارهای {get_name(target)} پاک شد.")

    elif 'کیا بیشتر از همه اد کردند' in cmd:
        hours = None
        if 'ساعت' in cmd:
            match = re.search(r'(\d+)\s*ساعت', cmd)
            if match:
                hours = int(match.group(1))
        elif 'روز' in cmd:
            match = re.search(r'(\d+)\s*روز', cmd)
            if match:
                hours = int(match.group(1)) * 24

        stats = db.get_invite_stats(group_id, hours)
        if not stats:
            msg.reply_text("❓ آماری یافت نشد.")
            return

        text_out = "📊 لیست بیشترین دعوت‌کنندگان:\n\n"
        for i, s in enumerate(stats[:10], 1):
            text_out += f"{i}. {s['inviter_name']}: {s['count']} نفر\n"
        msg.reply_text(text_out)

    # قفل‌ها
    elif cmd == 'لینک قفل': db.update_setting(group_id, 'lock_link', 1); msg.reply_text("🔒 لینک‌های تلگرام قفل شد.")
    elif cmd == 'لینک آزاد': db.update_setting(group_id, 'lock_link', 0); msg.reply_text("🔓 لینک‌های تلگرام آزاد شد.")
    elif cmd == 'آیدی قفل': db.update_setting(group_id, 'lock_id', 1); msg.reply_text("🔒 آیدی و منشن قفل شد.")
    elif cmd == 'آیدی آزاد': db.update_setting(group_id, 'lock_id', 0); msg.reply_text("🔓 آیدی و منشن آزاد شد.")
    elif cmd == 'سایت قفل': db.update_setting(group_id, 'lock_site', 1); msg.reply_text("🔒 لینک سایت قفل شد.")
    elif cmd == 'سایت آزاد': db.update_setting(group_id, 'lock_site', 0); msg.reply_text("🔓 لینک سایت آزاد شد.")
    elif cmd == 'مستهجن قفل': db.update_setting(group_id, 'lock_bad_words', 1); msg.reply_text("🔒 کلمات مستهجن قفل شد.")
    elif cmd == 'مستهجن آزاد': db.update_setting(group_id, 'lock_bad_words', 0); msg.reply_text("🔓 کلمات مستهجن آزاد شد.")
    elif cmd == 'هشتگ قفل': db.update_setting(group_id, 'lock_hashtag', 1); msg.reply_text("🔒 هشتگ قفل شد.")
    elif cmd == 'هشتگ آزاد': db.update_setting(group_id, 'lock_hashtag', 0); msg.reply_text("🔓 هشتگ آزاد شد.")
    elif cmd == 'متن قفل': db.update_setting(group_id, 'lock_text', 1); msg.reply_text("🔒 ارسال متن قفل شد.")
    elif cmd == 'متن آزاد': db.update_setting(group_id, 'lock_text', 0); msg.reply_text("🔓 ارسال متن آزاد شد.")
    elif cmd == 'فوروارد قفل': db.update_setting(group_id, 'lock_forward', 1); msg.reply_text("🔒 فوروارد قفل شد.")
    elif cmd == 'فوروارد آزاد': db.update_setting(group_id, 'lock_forward', 0); msg.reply_text("🔓 فوروارد آزاد شد.")
    elif cmd == 'فوروارد از کانال قفل': db.update_setting(group_id, 'lock_forward_channel', 1); msg.reply_text("🔒 فوروارد از کانال قفل شد.")
    elif cmd == 'فوروارد از کانال آزاد': db.update_setting(group_id, 'lock_forward_channel', 0); msg.reply_text("🔓 فوروارد از کانال آزاد شد.")
    elif cmd == 'عکس قفل': db.update_setting(group_id, 'lock_photo', 1); msg.reply_text("🔒 ارسال عکس قفل شد.")
    elif cmd == 'عکس آزاد': db.update_setting(group_id, 'lock_photo', 0); msg.reply_text("🔓 ارسال عکس آزاد شد.")
    elif cmd == 'فیلم قفل': db.update_setting(group_id, 'lock_video', 1); msg.reply_text("🔒 ارسال فیلم قفل شد.")
    elif cmd == 'فیلم آزاد': db.update_setting(group_id, 'lock_video', 0); msg.reply_text("🔓 ارسال فیلم آزاد شد.")
    elif cmd == 'استیکر قفل': db.update_setting(group_id, 'lock_sticker', 1); msg.reply_text("🔒 ارسال استیکر قفل شد.")
    elif cmd == 'استیکر آزاد': db.update_setting(group_id, 'lock_sticker', 0); msg.reply_text("🔓 ارسال استیکر آزاد شد.")
    elif cmd == 'لوکیشن قفل': db.update_setting(group_id, 'lock_location', 1); msg.reply_text("🔒 ارسال لوکیشن قفل شد.")
    elif cmd == 'لوکیشن آزاد': db.update_setting(group_id, 'lock_location', 0); msg.reply_text("🔓 ارسال لوکیشن آزاد شد.")
    elif cmd == 'شماره تلفن قفل': db.update_setting(group_id, 'lock_phone', 1); msg.reply_text("🔒 ارسال شماره تلفن قفل شد.")
    elif cmd == 'شماره تلفن آزاد': db.update_setting(group_id, 'lock_phone', 0); msg.reply_text("🔓 ارسال شماره تلفن آزاد شد.")
    elif cmd == 'صدای ضبط شده قفل': db.update_setting(group_id, 'lock_voice', 1); msg.reply_text("🔒 ارسال صدا قفل شد.")
    elif cmd == 'صدای ضبط شده آزاد': db.update_setting(group_id, 'lock_voice', 0); msg.reply_text("🔓 ارسال صدا آزاد شد.")
    elif cmd == 'فایل قفل': db.update_setting(group_id, 'lock_file', 1); msg.reply_text("🔒 ارسال فایل قفل شد.")
    elif cmd == 'فایل آزاد': db.update_setting(group_id, 'lock_file', 0); msg.reply_text("🔓 ارسال فایل آزاد شد.")
    elif cmd == 'گیف قفل': db.update_setting(group_id, 'lock_gif', 1); msg.reply_text("🔒 ارسال گیف قفل شد.")
    elif cmd == 'گیف آزاد': db.update_setting(group_id, 'lock_gif', 0); msg.reply_text("🔓 ارسال گیف آزاد شد.")
    elif cmd == 'نظرسنجی قفل': db.update_setting(group_id, 'lock_poll', 1); msg.reply_text("🔒 ارسال نظرسنجی قفل شد.")
    elif cmd == 'نظرسنجی آزاد': db.update_setting(group_id, 'lock_poll', 0); msg.reply_text("🔓 ارسال نظرسنجی آزاد شد.")
    elif cmd == 'اسلش قفل': db.update_setting(group_id, 'lock_slash', 1); msg.reply_text("🔒 اسلش کامند قفل شد.")
    elif cmd == 'اسلش آزاد': db.update_setting(group_id, 'lock_slash', 0); msg.reply_text("🔓 اسلش کامند آزاد شد.")
    elif cmd == 'دستورات عمومی قفل': db.update_setting(group_id, 'public_commands', 0); msg.reply_text("🔒 دستورات عمومی غیرفعال شد.")
    elif cmd == 'دستورات عمومی آزاد': db.update_setting(group_id, 'public_commands', 1); msg.reply_text("🔓 دستورات عمومی فعال شد.")

    elif cmd.startswith('خاموشی'):
        match = re.match(r'خاموشی\s*(\d)\s*از\s*(\d{1,2}:\d{2})\s*تا\s*(\d{1,2}:\d{2})', cmd)
        if match:
            num, from_t, to_t = match.group(1), match.group(2), match.group(3)
            db.update_setting(group_id, f'quiet_{num}_from', from_t)
            db.update_setting(group_id, f'quiet_{num}_to', to_t)
            msg.reply_text(f"✅ خاموشی {num} از {from_t} تا {to_t} تنظیم شد.")
        else:
            match2 = re.match(r'خاموشی\s*(\d)\s*غیرفعال', cmd)
            if match2:
                num = match2.group(1)
                db.update_setting(group_id, f'quiet_{num}_from', None)
                db.update_setting(group_id, f'quiet_{num}_to', None)
                msg.reply_text(f"✅ خاموشی {num} غیرفعال شد.")

# ============================================
# دستور /start
# ============================================

def cmd_start(update: Update, context: CallbackContext):
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

    update.message.reply_text(
        f"👋 سلام {get_name(user)}!\n\n"
        "به ربات مدیر گروه هیوا خوش اومدید 🤖\n\n"
        "با این ربات می‌تونید گروه تلگرامتون رو مدیریت کنید.\n\n"
        "یکی از گزینه‌های زیر رو انتخاب کنید:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ============================================
# هندلر دکمه‌ها
# ============================================

def button_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    try:
        query.answer()
    except:
        pass
    user = query.from_user
    data = query.data

    if data == "trial":
        query.edit_message_text(
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
        query.edit_message_text(plans_text, reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("plan_"):
        plan_key = data.split("_")[1]
        plan = config.PLANS[plan_key]
        context.user_data['selected_plan'] = plan_key
        context.user_data['action'] = 'payment'
        payment_text = config.MSG_PAYMENT_INFO.format(
            amount=format_price(plan['price']),
            card=config.CARD_NUMBER,
            owner=config.CARD_OWNER
        )
        payment_text += "\n\nبعد از واریز، شناسه پیگیری و آیدی گروه رو با فاصله بفرستید.\nمثال: 123456789 -1001234567890"
        query.edit_message_text(payment_text)

    elif data == "status":
        query.edit_message_text("آیدی عددی گروهتون رو بفرستید.")
        context.user_data['action'] = 'check_status'

    elif data == "admin_panel" and is_admin(user.id):
        pending = db.get_pending_payments()
        active = db.get_all_active_groups()
        text = f"⚙️ پنل مدیریت هیوا\n\n📊 گروه‌های فعال: {len(active)}\n💳 پرداخت‌های در انتظار: {len(pending)}"
        keyboard = []
        if pending:
            keyboard.append([InlineKeyboardButton("💳 بررسی پرداخت‌ها", callback_data="check_payments")])
        keyboard.append([InlineKeyboardButton("📋 لیست گروه‌ها", callback_data="list_groups")])
        query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "check_payments" and is_admin(user.id):
        pending = db.get_pending_payments()
        if not pending:
            query.edit_message_text("✅ پرداخت در انتظاری وجود ندارد.")
            return
        for p in pending[:5]:
            plan = config.PLANS.get(p['plan'], {})
            text = (f"💳 پرداخت #{p['id']}\n👤 کاربر: {p['user_id']}\n"
                   f"🏠 گروه: {p['group_id']}\n📦 پلن: {plan.get('name', p['plan'])}\n"
                   f"💰 مبلغ: {format_price(p['amount'])}\n🔢 شناسه: {p['tracking_code']}")
            keyboard = [[
                InlineKeyboardButton("✅ تأیید", callback_data=f"confirm_{p['id']}"),
                InlineKeyboardButton("❌ رد", callback_data=f"reject_{p['id']}")
            ]]
            context.bot.send_message(user.id, text, reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("confirm_") and is_admin(user.id):
        pay_id = int(data.split("_")[1])
        payment = db.get_payment(pay_id)
        if not payment:
            query.edit_message_text("❌ پرداخت یافت نشد.")
            return
        plan = config.PLANS.get(payment['plan'], {})
        expiry = db.activate_group(payment['group_id'], plan.get('days', 30), payment['plan'])
        db.confirm_payment(pay_id)
        query.edit_message_text(f"✅ پرداخت #{pay_id} تأیید شد.")
        try:
            context.bot.send_message(payment['user_id'],
                f"✅ پرداخت شما تأیید شد!\nاشتراک {plan.get('name', '')} فعال شد.\nانقضا: {expiry}")
        except:
            pass

    elif data.startswith("reject_") and is_admin(user.id):
        pay_id = int(data.split("_")[1])
        payment = db.get_payment(pay_id)
        query.edit_message_text(f"❌ پرداخت #{pay_id} رد شد.")
        try:
            context.bot.send_message(payment['user_id'],
                "❌ پرداخت شما تأیید نشد. لطفاً دوباره تلاش کنید.")
        except:
            pass

    elif data == "back":
        cmd_start(update, context)

# ============================================
# پیام‌های پیوی
# ============================================

def private_message(update: Update, context: CallbackContext):
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
                update.message.reply_text("❌ این گروه ثبت نشده. ابتدا ربات را به گروه اضافه کنید.")
                return
            if group.get('trial_used'):
                update.message.reply_text("❌ این گروه قبلاً از تست رایگان استفاده کرده.")
                return
            expiry = db.activate_group(group_id, config.FREE_TRIAL_DAYS, "trial", is_trial=True)
            update.message.reply_text(config.MSG_TRIAL_START.format(
                group=group.get('group_name', group_id), expiry=expiry))
            context.user_data.clear()
        except ValueError:
            update.message.reply_text("❌ آیدی وارد شده معتبر نیست.")

    elif action == 'payment':
        plan_key = context.user_data.get('selected_plan')
        plan = config.PLANS.get(plan_key, {})
        parts = text.strip().split()
        if len(parts) < 2:
            update.message.reply_text("لطفاً شناسه پیگیری و آیدی گروه را با فاصله بفرستید.\nمثال: 123456789 -1001234567890")
            return
        tracking = parts[0]
        try:
            group_id = int(parts[1])
        except ValueError:
            update.message.reply_text("❌ آیدی گروه معتبر نیست.")
            return
        pay_id = db.add_payment(user.id, group_id, plan_key, plan.get('price', 0), tracking)
        update.message.reply_text(f"✅ درخواست شما ثبت شد (شماره {pay_id})\nبعد از بررسی توسط ادمین، اشتراک فعال می‌شود.")
        try:
            context.bot.send_message(config.ADMIN_ID,
                f"💳 پرداخت جدید!\n👤 {get_name(user)} ({user.id})\n📦 {plan.get('name', plan_key)}\n"
                f"💰 {format_price(plan.get('price', 0))}\n🔢 {tracking}\n🏠 {group_id}",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("✅ تأیید", callback_data=f"confirm_{pay_id}"),
                    InlineKeyboardButton("❌ رد", callback_data=f"reject_{pay_id}")
                ]]))
        except:
            pass
        context.user_data.clear()

    elif action == 'check_status':
        try:
            group_id = int(text.strip())
            is_active = db.is_group_active(group_id)
            days = db.get_days_until_expiry(group_id)
            group = db.get_group(group_id)
            if not group:
                update.message.reply_text("❌ گروه یافت نشد.")
                return
            status = "✅ فعال" if is_active else "❌ غیرفعال"
            text_out = f"📊 وضعیت: {status}\n"
            if days is not None:
                text_out += f"روزهای باقیمانده: {days} روز\nانقضا: {group.get('expiry_date', 'نامشخص')}"
            update.message.reply_text(text_out)
            context.user_data.clear()
        except ValueError:
            update.message.reply_text("❌ آیدی معتبر نیست.")

# ============================================
# اضافه شدن ربات به گروه
# ============================================

def bot_added(update: Update, context: CallbackContext):
    msg = update.message
    if not msg:
        return
    chat = update.effective_chat
    user = update.effective_user

    if msg.new_chat_members:
        for m in msg.new_chat_members:
            if m.id == context.bot.id:
                db.add_group(chat.id, chat.title, user.id, user.username or "")
                try:
                    context.bot.send_message(user.id,
                        f"✅ ربات هیوا به گروه «{chat.title}» اضافه شد!\n"
                        f"آیدی گروه: {chat.id}\n\n"
                        f"برای فعال کردن تست رایگان یا خرید اشتراک به ربات پیام بدید و /start بزنید.")
                except:
                    pass

# ============================================
# بررسی انقضا
# ============================================

def check_expiries(context: CallbackContext):
    groups = db.get_all_active_groups()
    for group in groups:
        days = db.get_days_until_expiry(group['group_id'])
        if days is None:
            continue
        if days <= 0:
            db.deactivate_group(group['group_id'])
            try:
                context.bot.send_message(group['owner_id'],
                    config.MSG_SUB_EXPIRED.format(group=group.get('group_name', group['group_id'])))
            except:
                pass
        elif days <= config.EXPIRY_WARNING_DAYS:
            try:
                context.bot.send_message(group['owner_id'],
                    config.MSG_SUB_EXPIRY_WARNING.format(
                        group=group.get('group_name', group['group_id']), days=days))
            except:
                pass

# ============================================
# راه‌اندازی
# ============================================

def main():
    db.init_db()

    updater = Updater(config.BOT_TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", cmd_start))
    dp.add_handler(CallbackQueryHandler(button_handler))
    dp.add_handler(MessageHandler(Filters.status_update.new_chat_members, bot_added))
    dp.add_handler(MessageHandler(Filters.chat_type.private & Filters.text & ~Filters.command, private_message))
    dp.add_handler(MessageHandler(Filters.chat_type.groups & ~Filters.command, filter_messages))

    updater.job_queue.run_repeating(check_expiries, interval=21600, first=60)

    print("🤖 ربات هیوا در حال اجراست...")
    updater.start_polling(drop_pending_updates=True)
    updater.idle()

if __name__ == "__main__":
    main()
