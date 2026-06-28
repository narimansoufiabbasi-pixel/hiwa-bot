# ============================================
# ربات مدیر گروه هیوا
# فایل اصلی - نسخه رایگان
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
            else:
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
            warn_msg = await update.effective_chat.send_message(
                f"🚫 {get_name(user)}، {reason}."
            )
            await asyncio.sleep(5)
            await warn_msg.delete()
        except TelegramError:
            pass
        return

    await handle_public_commands(update, context)

# ============================================
# دستورات عمومی
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

    elif 'کیا بیشتر از همه اد کردند' in cmd:
        hours = None
        import re
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
            await msg.reply_text("❓ آماری یافت نشد.")
            return

        text_out = "📊 لیست بیشترین دعوت‌کنندگان:\n\n"
        for i, s in enumerate(stats[:10], 1):
            text_out += f"{i}. {s['inviter_name']}: {s['count']} نفر\n"
        await msg.reply_text(text_out)

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

    elif cmd.startswith('لینک گروه '):
        link = cmd.replace('لینک گروه ', '').strip()
        conn = db.get_conn()
        conn.execute("UPDATE groups SET group_link=? WHERE group_id=?", (link, group_id))
        conn.commit()
        conn.close()
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

    await update.message.reply_text(
        f"👋 سلام {get_name(user)}!\n\n"
        "به ربات مدیر گروه هیوا خوش اومدید 🤖\n\n"
        "برای استفاده از ربات، کافیه ربات رو به گروهتون اضافه کنید و بهش دسترسی ادمین بدید.\n"
        "ربات بلافاصله فعال می‌شه! ✅"
    )

# ============================================
# هندلر اضافه شدن ربات به گروه
# ============================================

async def bot_added_to_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.my_chat_member:
        chat = update.effective_chat
        user = update.my_chat_member.from_user
        new_status = update.my_chat_member.new_chat_member.status

        if new_status in ['member', 'administrator'] and chat.type in ['group', 'supergroup']:
            # ثبت گروه در دیتابیس
            db.add_group(chat.id, chat.title, user.id, user.username or "")
            # فعال‌سازی خودکار و رایگان - بدون نیاز به پرداخت
            db.activate_group_free(chat.id)

            try:
                await context.bot.send_message(
                    chat.id,
                    f"✅ ربات هیوا به گروه «{chat.title}» اضافه شد و فعال است!\n\n"
                    f"برای مشاهده دستورات، ادمین‌های گروه می‌توانند از ! یا . استفاده کنند."
                )
            except:
                pass

            try:
                await context.bot.send_message(
                    user.id,
                    f"✅ ربات هیوا به گروه «{chat.title}» اضافه شد!\n"
                    f"ربات فعال و آماده استفاده است 🎉"
                )
            except:
                pass

# ============================================
# راه‌اندازی ربات
# ============================================

def main():
    db.init_db()

    app = Application.builder().token(config.BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(ChatMemberHandler(bot_added_to_group, ChatMemberHandler.MY_CHAT_MEMBER))
    app.add_handler(MessageHandler(filters.ChatType.GROUPS & filters.StatusUpdate.NEW_CHAT_MEMBERS, member_joined))
    app.add_handler(MessageHandler(filters.ChatType.GROUPS & ~filters.COMMAND, filter_messages))

    print("🤖 ربات هیوا در حال اجراست...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
