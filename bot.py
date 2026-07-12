# ربات مدیر گروه هیوا - نسخه 6
# همه امکانات از پنل، چندزبانه آماده

import logging
import asyncio
import re
import random
from datetime import datetime, timedelta, timezone
from telegram import Update, ChatPermissions, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, ChatMemberHandler,
    CallbackQueryHandler, filters, ContextTypes
)
from telegram.error import TelegramError
import config
import database as db
from jalali import jalali_str
from languages import t


async def ask_gemini(prompt):
    """ارسال سوال به Gemini با google-genai"""
    try:
        import os
        from google import genai as _genai
        api_key = getattr(config, 'GEMINI_API_KEY', '') or os.environ.get('GEMINI_API_KEY', '')
        if not api_key:
            return "❌ کلید API Gemini تنظیم نشده. از config.py اضافه کنید."
        client = _genai.Client(api_key=api_key)
        interaction = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=prompt,
        )
        return interaction.text
    except ImportError:
        return "❌ کتابخانه google-genai نصب نیست."
    except Exception as e:
        return f"❌ خطا: {str(e)[:150]}"

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

IRAN_TZ = timezone(timedelta(hours=3, minutes=30))

def now_iran():
    return datetime.now(IRAN_TZ)

def now_time_str():
    return now_iran().strftime("%H:%M")

def now_date_full():
    dt = now_iran()
    return jalali_str(dt), dt.strftime("%Y/%m/%d")

PERSIAN_DIGITS = "۰۱۲۳۴۵۶۷۸۹"
ARABIC_DIGITS = "٠١٢٣٤٥٦٧٨٩"
ENGLISH_DIGITS = "0123456789"

def normalize_digits(text):
    if not text: return text
    for i in range(10):
        text = text.replace(PERSIAN_DIGITS[i], ENGLISH_DIGITS[i])
        text = text.replace(ARABIC_DIGITS[i], ENGLISH_DIGITS[i])
    return text

def is_owner(user_id): return user_id == config.ADMIN_ID

async def is_group_admin(context, chat_id, user_id):
    try:
        member = await context.bot.get_chat_member(chat_id, user_id)
        return member.status in ['administrator', 'creator']
    except: return False

def get_name(user):
    n = user.first_name or ""
    if user.last_name: n += f" {user.last_name}"
    return n

def is_in_quiet_range(f, tt, now=None):
    if now is None: now = now_time_str()
    if f <= tt: return f <= now <= tt
    else: return now >= f or now <= tt

def is_quiet_time_now(s):
    now = now_time_str()
    for i in range(1, 4):
        f = s.get(f'quiet_{i}_from'); tt = s.get(f'quiet_{i}_to')
        if f and tt and is_in_quiet_range(f, tt, now): return True
    return False

async def safe_delete(msg):
    try: await msg.delete()
    except: pass

async def bot_reply(context, chat_id, text, del_sec=0, **kwargs):
    try:
        msg = await context.bot.send_message(chat_id, text, **kwargs)
        if del_sec > 0:
            await asyncio.sleep(del_sec)
            try: await msg.delete()
            except: pass
        return msg
    except Exception as e:
        logger.error(f"bot_reply error: {e}")
        return None

def get_lang(group_id):
    s = db.get_settings(group_id)
    return s.get('lang', 'fa')

# ============================================
# JOB: چک ساعت خاموشی هر دقیقه
# ============================================

async def check_subscriptions_job(context: ContextTypes.DEFAULT_TYPE):
    """چک انقضای اشتراک‌ها - هر روز یه بار"""
    # غیرفعال کردن اشتراک‌های منقضی
    expired = db.check_expired_subscriptions()
    for g in expired:
        try:
            g_lang = db.get_settings(g['group_id']).get('lang', 'fa')
            await context.bot.send_message(g['group_id'], t("sub_expired_msg", g_lang))
        except: pass
        try:
            await context.bot.send_message(g['owner_id'],
                f"⚠️ اشتراک ربات در گروه {g['group_name']} منقضی شد. برای تمدید با سازنده تماس بگیرید.")
        except: pass
        try:
            await context.bot.send_message(config.ADMIN_ID,
                f"🔴 اشتراک گروه «{g['group_name']}» (آیدی: {g['group_id']}) منقضی شد.")
        except: pass

    # اطلاع‌رسانی انقضای نزدیک (3 روز مانده)
    expiring = db.get_expiring_soon(3)
    for g in expiring:
        try:
            g_lang = db.get_settings(g['group_id']).get('lang', 'fa')
            await context.bot.send_message(g['owner_id'], t("sub_expiring_soon", g_lang, name=g['group_name']))
        except: pass


async def check_quiet_hours_job(context: ContextTypes.DEFAULT_TYPE):
    now = now_time_str()
    rows = db.get_all_settings_rows()
    for s in rows:
        group_id = s['group_id']
        lang = s.get('lang', 'fa')
        for i in range(1, 4):
            f = s.get(f'quiet_{i}_from'); tt = s.get(f'quiet_{i}_to')
            state = s.get(f'quiet_{i}_state', 0)
            if not f or not tt: continue
            should_active = is_in_quiet_range(f, tt, now)
            if should_active and not state:
                db.update_setting(group_id, f'quiet_{i}_state', 1)
                await bot_reply(context, group_id, t("quiet_start", lang, from_t=f, to_t=tt))
            elif not should_active and state:
                db.update_setting(group_id, f'quiet_{i}_state', 0)
                await bot_reply(context, group_id, t("quiet_end", lang, from_t=f, to_t=tt))

# ============================================
# پنل کاربری
# ============================================

async def show_my_groups(target, context, user_id, edit=False, lang="fa"):
    all_groups = db.get_all_active_groups()
    user_groups = []
    for g in all_groups:
        try:
            member = await context.bot.get_chat_member(g['group_id'], user_id)
            if member.status in ['administrator', 'creator']:
                user_groups.append(g)
        except: pass

    if not user_groups:
        text = t("no_groups", lang)
        if edit: await target.edit_message_text(text)
        else: await target.reply_text(text)
        return

    keyboard = [[InlineKeyboardButton(f"🏠 {g.get('group_name','?')}", callback_data=f"grp:{g['group_id']}")] for g in user_groups]
    keyboard.append([InlineKeyboardButton(t("menu_lang", lang), callback_data="changelang")])
    keyboard.append([InlineKeyboardButton(t("menu_help", lang), callback_data="help:main:mygroups:0")])
    text = t("select_group", lang)
    if edit: await target.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    else: await target.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

# ============================================
# منوی اصلی گروه
# ============================================

async def show_group_menu(query, group_id):
    g = db.get_group(group_id)
    name = g.get('group_name','?') if g else '?'
    s = db.get_settings(group_id)
    lang = s.get('lang', 'fa')
    # نمایش وضعیت اشتراک
    sub = db.get_group_subscription(group_id)
    if sub and sub.get('expiry_date'):
        try:
            from datetime import datetime
            exp = datetime.strptime(sub['expiry_date'], "%Y-%m-%d %H:%M:%S")
            days_left = (exp - datetime.now()).days
            if days_left > 0:
                sub_status = f"✅ اشتراک: {days_left} روز مانده"
            else:
                sub_status = "❌ اشتراک منقضی شده"
        except:
            sub_status = "✅ اشتراک فعال"
    else:
        sub_status = "🟢 رایگان (دائمی)"

    keyboard = [
        [InlineKeyboardButton(t("menu_locks", lang), callback_data=f"locks:{group_id}"),
         InlineKeyboardButton(t("menu_quiet", lang), callback_data=f"quiet:{group_id}")],
        [InlineKeyboardButton(t("menu_welcome", lang), callback_data=f"welcome:{group_id}"),
         InlineKeyboardButton(t("menu_goodbye", lang), callback_data=f"goodbye:{group_id}")],
        [InlineKeyboardButton(t("menu_security", lang), callback_data=f"security:{group_id}"),
         InlineKeyboardButton(t("menu_warn", lang), callback_data=f"warn:{group_id}")],
        [InlineKeyboardButton(t("menu_force", lang), callback_data=f"force:{group_id}"),
         InlineKeyboardButton(t("menu_white", lang), callback_data=f"white:{group_id}")],
        [InlineKeyboardButton(t("menu_badwords", lang), callback_data=f"badwords:{group_id}"),
         InlineKeyboardButton(t("menu_dashboard", lang), callback_data=f"dashboard:{group_id}")],
        [InlineKeyboardButton(t("menu_users", lang), callback_data=f"users:{group_id}"),
         InlineKeyboardButton(t("menu_settings", lang), callback_data=f"other:{group_id}")],
        [InlineKeyboardButton(t("menu_contact", lang), callback_data=f"contact_owner:{group_id}")],
        [InlineKeyboardButton(t("menu_lang", lang), callback_data="changelang"),
         InlineKeyboardButton(t("menu_help", lang), callback_data=f"help:main:mygroups:0")],
        [InlineKeyboardButton(t("back", lang), callback_data="mygroups")],
    ]
    await query.edit_message_text(
        f"{t('group_settings', lang, name=name)}\n\n{sub_status}",
        reply_markup=InlineKeyboardMarkup(keyboard))

# ============================================
# قفل‌ها
# ============================================

async def show_locks(query, group_id):
    s = db.get_settings(group_id)
    g = db.get_group(group_id)
    name = g.get('group_name','?') if g else '?'
    lang = s.get('lang', 'fa')

    def btn(label_key, key):
        v = s.get(key, 0)
        ico = t("locked", lang) if v else t("unlocked", lang)
        nv = 0 if v else 1
        return InlineKeyboardButton(f"{ico} | {t(label_key, lang)}", callback_data=f"tog:{group_id}:{key}:{nv}")

    keyboard = [
        [btn("lock_telegram_link", "lock_link"), btn("lock_website", "lock_site")],
        [btn("lock_username", "lock_id"), btn("lock_hashtag_lbl", "lock_hashtag")],
        [btn("lock_photo_lbl", "lock_photo"), btn("lock_video_lbl", "lock_video")],
        [btn("lock_sticker_lbl", "lock_sticker"), btn("lock_gif_lbl", "lock_gif")],
        [btn("lock_voice_lbl", "lock_voice"), btn("lock_file_lbl", "lock_file")],
        [btn("lock_poll_lbl", "lock_poll"), btn("lock_location_lbl", "lock_location")],
        [btn("lock_phone_lbl", "lock_phone"), btn("lock_text_lbl", "lock_text")],
        [btn("lock_fwd_channel", "lock_forward_channel"), btn("lock_fwd_group", "lock_forward_group")],
        [btn("lock_fwd_user", "lock_forward_user"), btn("lock_badwords_lbl", "lock_bad_words")],
        [btn("lock_slash_lbl", "lock_slash"), btn("lock_pub_cmds", "public_commands")],
        [btn("lock_emoji_lbl", "lock_emoji"), btn("lock_full", "group_locked")],
        [InlineKeyboardButton(t("back", lang), callback_data=f"grp:{group_id}")],
    ]
    await query.edit_message_text(
        t("locks_title", lang, name=name),
        reply_markup=InlineKeyboardMarkup(keyboard))

# ============================================
# ساعت خاموشی
# ============================================

async def show_quiet(query, group_id):
    s = db.get_settings(group_id)
    g = db.get_group(group_id)
    name = g.get('group_name','?') if g else '?'
    lang = s.get('lang', 'fa')
    text = t("quiet_title", lang, name=name)
    keyboard = []
    for i in range(1, 4):
        f = s.get(f'quiet_{i}_from'); tt = s.get(f'quiet_{i}_to')
        state = s.get(f'quiet_{i}_state', 0)
        if f and tt:
            status = t("quiet_active", lang) if state else t("quiet_inactive", lang)
            text += t("quiet_set", lang, num=i, from_t=f, to_t=tt) + f" — {status}\n"
            keyboard.append([
                InlineKeyboardButton(t("quiet_edit", lang, num=i), callback_data=f"editquiet:{group_id}:{i}"),
                InlineKeyboardButton(t("quiet_del", lang, num=i), callback_data=f"delquiet:{group_id}:{i}"),
            ])
        else:
            text += t("quiet_not_set", lang, num=i) + "\n"
            keyboard.append([InlineKeyboardButton(t("quiet_add", lang, num=i), callback_data=f"setquiet:{group_id}:{i}")])
    keyboard.append([InlineKeyboardButton(t("back", lang), callback_data=f"grp:{group_id}")])
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def show_quiet_from_picker(query, group_id, num):
    keyboard = []
    row = []
    for h in range(0, 24):
        row.append(InlineKeyboardButton(f"{h:02d}:00", callback_data=f"quietfrom:{group_id}:{num}:{h:02d}:00"))
        if len(row) == 4:
            keyboard.append(row); row = []
    if row: keyboard.append(row)
    keyboard.append([InlineKeyboardButton("🔙 برگشت", callback_data=f"quiet:{group_id}")])
    await query.edit_message_text(f"🌙 ساعت شروع خاموشی {num} را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(keyboard))

async def show_quiet_to_picker(query, group_id, num, from_t):
    keyboard = []
    row = []
    for h in range(0, 24):
        row.append(InlineKeyboardButton(f"{h:02d}:00", callback_data=f"quietto:{group_id}:{num}:{from_t}:{h:02d}:00"))
        if len(row) == 4:
            keyboard.append(row); row = []
    if row: keyboard.append(row)
    keyboard.append([InlineKeyboardButton("🔙 برگشت", callback_data=f"quiet:{group_id}")])
    await query.edit_message_text(f"🌙 ساعت پایان خاموشی {num} را انتخاب کنید (شروع: {from_t}):", reply_markup=InlineKeyboardMarkup(keyboard))

# ============================================
# خوش‌آمد و خروج
# ============================================

async def show_welcome(query, group_id):
    s = db.get_settings(group_id)
    g = db.get_group(group_id)
    name = g.get('group_name','?') if g else '?'
    lang = s.get('lang', 'fa')
    we = s.get('welcome_enabled', 1); wb = s.get('welcome_button', 0)
    wt = s.get('welcome_text', '') or t("welcome", lang, name="{name}")

    def tbtn(label_key, key, val):
        ico = t("enabled", lang) if val else t("disabled", lang)
        nv = 0 if val else 1
        return InlineKeyboardButton(f"{ico} | {t(label_key, lang)}", callback_data=f"tog:{group_id}:{key}:{nv}")

    keyboard = [
        [tbtn("welcome_enabled_lbl", "welcome_enabled", we)],
        [tbtn("welcome_button_lbl", "welcome_button", wb)],
        [InlineKeyboardButton(t("welcome_edit", lang), callback_data=f"setwelcome:{group_id}")],
        [InlineKeyboardButton(t("back", lang), callback_data=f"grp:{group_id}")],
    ]
    await query.edit_message_text(
        t("welcome_title", lang, name=name, text=wt[:80]),
        reply_markup=InlineKeyboardMarkup(keyboard))

async def show_goodbye(query, group_id):
    s = db.get_settings(group_id)
    g = db.get_group(group_id)
    name = g.get('group_name','?') if g else '?'
    lang = s.get('lang', 'fa')
    ge = s.get('goodbye_enabled', 0)

    def tbtn(label_key, key, val):
        ico = t("enabled", lang) if val else t("disabled", lang)
        nv = 0 if val else 1
        return InlineKeyboardButton(f"{ico} | {t(label_key, lang)}", callback_data=f"tog:{group_id}:{key}:{nv}")

    keyboard = [
        [tbtn("goodbye_enabled_lbl", "goodbye_enabled", ge)],
        [InlineKeyboardButton(t("back", lang), callback_data=f"grp:{group_id}")],
    ]
    await query.edit_message_text(
        t("goodbye_title", lang, name=name),
        reply_markup=InlineKeyboardMarkup(keyboard))

# ============================================
# امنیت
# ============================================

async def show_security(query, group_id):
    s = db.get_settings(group_id)
    g = db.get_group(group_id)
    name = g.get('group_name','?') if g else '?'
    lang = s.get('lang', 'fa')

    def tbtn(label_key, key):
        v = s.get(key, 0)
        ico = t("enabled", lang) if v else t("disabled", lang)
        nv = 0 if v else 1
        return InlineKeyboardButton(f"{ico} | {t(label_key, lang)}", callback_data=f"tog:{group_id}:{key}:{nv}")

    keyboard = [
        [tbtn("security_captcha", "captcha_enabled")],
        [tbtn("security_antispam", "anti_spam")],
        [tbtn("security_antiflood", "anti_flood")],
        [tbtn("security_antiraid", "anti_raid")],
        [tbtn("security_botdetect", "bot_detection")],
        [InlineKeyboardButton(t("security_help", lang), callback_data=f"help:security:security:{group_id}")],
        [InlineKeyboardButton(t("back", lang), callback_data=f"grp:{group_id}")],
    ]
    await query.edit_message_text(t("security_title", lang, name=name), reply_markup=InlineKeyboardMarkup(keyboard))

# ============================================
# اخطار
# ============================================

async def show_warn(query, group_id):
    s = db.get_settings(group_id)
    g = db.get_group(group_id)
    name = g.get('group_name','?') if g else '?'
    lang = s.get('lang', 'fa')
    auto = s.get('auto_warn', 0); limit = s.get('warn_limit', 3); action = s.get('warn_action', 'kick')
    action_lbl = t(f"warn_action_{action}", lang)

    keyboard = [
        [InlineKeyboardButton(
            f"{t('enabled',lang) if auto else t('disabled',lang)} | {t('warn_auto',lang)}",
            callback_data=f"tog:{group_id}:auto_warn:{0 if auto else 1}")],
        [InlineKeyboardButton(t("warn_limit_lbl", lang, limit=limit), callback_data=f"warnlimit:{group_id}")],
        [InlineKeyboardButton(t("warn_action_lbl", lang, action=action_lbl), callback_data=f"warnaction:{group_id}")],
        [InlineKeyboardButton(t("menu_help", lang), callback_data=f"help:warn:warn:{group_id}")],
        [InlineKeyboardButton(t("back", lang), callback_data=f"grp:{group_id}")],
    ]
    await query.edit_message_text(t("warn_title", lang, name=name), reply_markup=InlineKeyboardMarkup(keyboard))

async def show_warn_limit_picker(query, group_id):
    s = db.get_settings(group_id); lang = s.get('lang','fa')
    keyboard = []
    row = []
    for n in [1,2,3,4,5,6,7,8,9,10]:
        row.append(InlineKeyboardButton(str(n), callback_data=f"setwarnlimit:{group_id}:{n}"))
        if len(row) == 5: keyboard.append(row); row = []
    if row: keyboard.append(row)
    keyboard.append([InlineKeyboardButton(t("back",lang), callback_data=f"warn:{group_id}")])
    await query.edit_message_text(t("warn_pick_limit",lang), reply_markup=InlineKeyboardMarkup(keyboard))

async def show_warn_action_picker(query, group_id):
    s = db.get_settings(group_id); lang = s.get('lang','fa')
    keyboard = [
        [InlineKeyboardButton(f"🚫 {t('warn_action_kick',lang)}", callback_data=f"setwarnaction:{group_id}:kick")],
        [InlineKeyboardButton(f"⛔ {t('warn_action_ban',lang)}", callback_data=f"setwarnaction:{group_id}:ban")],
        [InlineKeyboardButton(f"🔇 {t('warn_action_mute',lang)}", callback_data=f"setwarnaction:{group_id}:mute")],
        [InlineKeyboardButton(t("back",lang), callback_data=f"warn:{group_id}")],
    ]
    await query.edit_message_text(t("warn_pick_action",lang), reply_markup=InlineKeyboardMarkup(keyboard))

# ============================================
# اد اجباری
# ============================================

async def show_force(query, group_id):
    s = db.get_settings(group_id)
    g = db.get_group(group_id)
    name = g.get('group_name','?') if g else '?'
    lang = s.get('lang','fa')
    fi = s.get('force_invite', 0); count = s.get('force_invite_count', 5); days = s.get('force_invite_days', 0)
    days_text = f"{days}" if days > 0 else t("force_days_permanent", lang)

    keyboard = [
        [InlineKeyboardButton(
            f"{t('enabled',lang) if fi else t('disabled',lang)} | {t('force_enabled_lbl',lang)}",
            callback_data=f"tog:{group_id}:force_invite:{0 if fi else 1}")],
        [InlineKeyboardButton(t("force_count_lbl",lang,count=count), callback_data=f"forcecount:{group_id}")],
        [InlineKeyboardButton(t("force_days_lbl",lang,days=days_text), callback_data=f"forcedays:{group_id}")],
        [InlineKeyboardButton(t("menu_help",lang), callback_data=f"help:force:force:{group_id}")],
        [InlineKeyboardButton(t("back",lang), callback_data=f"grp:{group_id}")],
    ]
    await query.edit_message_text(t("force_title",lang,name=name), reply_markup=InlineKeyboardMarkup(keyboard))

async def show_force_count_picker(query, group_id):
    s = db.get_settings(group_id); lang = s.get('lang','fa')
    keyboard = []
    row = []
    for n in [1,2,3,5,7,10,15,20,30,40,50,100]:
        row.append(InlineKeyboardButton(str(n), callback_data=f"setforcecount:{group_id}:{n}"))
        if len(row) == 4: keyboard.append(row); row = []
    if row: keyboard.append(row)
    keyboard.append([InlineKeyboardButton(t("back",lang), callback_data=f"force:{group_id}")])
    await query.edit_message_text(t("force_pick_count",lang), reply_markup=InlineKeyboardMarkup(keyboard))

async def show_force_days_picker(query, group_id):
    s = db.get_settings(group_id); lang = s.get('lang','fa')
    keyboard = [
        [InlineKeyboardButton("30", callback_data=f"setforcedays:{group_id}:30"),
         InlineKeyboardButton("60", callback_data=f"setforcedays:{group_id}:60")],
        [InlineKeyboardButton("90", callback_data=f"setforcedays:{group_id}:90"),
         InlineKeyboardButton(f"♾ {t('force_days_permanent',lang)}", callback_data=f"setforcedays:{group_id}:0")],
        [InlineKeyboardButton(t("back",lang), callback_data=f"force:{group_id}")],
    ]
    await query.edit_message_text(t("force_pick_days",lang), reply_markup=InlineKeyboardMarkup(keyboard))

# ============================================
# لیست سفید
# ============================================

async def show_whitelist(query, group_id):
    s = db.get_settings(group_id); lang = s.get('lang','fa')
    g = db.get_group(group_id)
    name = g.get('group_name','?') if g else '?'
    wl = db.get_whitelist(group_id)
    text = t("white_title", lang, name=name)
    if wl:
        text += t("white_list", lang, count=len(wl))
        for w in wl[:10]: text += f"• {w.get('user_name','?')}\n"
    else: text += t("white_empty", lang)
    text += t("white_help", lang)
    keyboard = [[InlineKeyboardButton(t("back",lang), callback_data=f"grp:{group_id}")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

# ============================================
# کلمات ممنوعه - از پنل
# ============================================

async def show_badwords(query, group_id):
    s = db.get_settings(group_id); lang = s.get('lang','fa')
    g = db.get_group(group_id)
    name = g.get('group_name','?') if g else '?'
    words = db.get_bad_words(group_id)
    text = t("badwords_title", lang, name=name)
    if words:
        text += t("badwords_list", lang, count=len(words))
        for i, w in enumerate(words[:20]): text += f"{i+1}. {w}\n"
    else: text += t("badwords_empty", lang)
    keyboard = [
        [InlineKeyboardButton(t("badwords_add",lang), callback_data=f"addbadword:{group_id}")],
    ]
    if words:
        keyboard.append([InlineKeyboardButton(t("badwords_del",lang), callback_data=f"delbadword:{group_id}")])
    keyboard.append([InlineKeyboardButton(t("back",lang), callback_data=f"grp:{group_id}")])
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def show_del_badword(query, group_id):
    words = db.get_bad_words(group_id)
    if not words:
        await query.edit_message_text("❌ لیست خالی است.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 برگشت", callback_data=f"badwords:{group_id}")]]))
        return
    keyboard = []
    for w in words[:20]:
        keyboard.append([InlineKeyboardButton(f"🗑 {w}", callback_data=f"confirmdelbw:{group_id}:{w}")])
    keyboard.append([InlineKeyboardButton("🔙 برگشت", callback_data=f"badwords:{group_id}")])
    await query.edit_message_text("🗑 کدام کلمه را حذف کنید؟", reply_markup=InlineKeyboardMarkup(keyboard))

# ============================================
# تابلو آمار
# ============================================

async def show_dashboard(query, group_id):
    g = db.get_group(group_id)
    name = g.get('group_name','نامشخص') if g else 'نامشخص'
    stats = db.get_group_stats(group_id)
    growth = db.get_member_growth(group_id, 7)
    active_users = db.get_active_users(group_id, 7)
    hourly = db.get_hourly_activity(group_id, 7)

    text = f"📊 تابلو آمار «{name}»\n\n"
    text += f"🗑 پیام‌های حذف شده: {stats['deleted']}\n"
    text += f"⚠️ اخطارها: {stats['warns']}\n"
    text += f"🚫 تخلفات: {stats['violations']}\n"
    text += f"👥 ورودی‌ها: {stats['joins']}\n"
    text += f"🚪 خروجی‌ها: {stats['lefts']}\n"
    text += f"📨 دعوت‌ها: {stats['invites']}\n\n"

    if growth:
        text += "📈 رشد 7 روز اخیر:\n"
        for row in growth[-5:]:
            text += f"  {row['day']}: +{row['joins']} -{row['lefts']}\n"
        text += "\n"

    if active_users:
        text += "🏆 کاربران فعال (7 روز):\n"
        for i, u in enumerate(active_users[:3], 1):
            text += f"  {i}. {u['user_name']}: {u['count']} پیام\n"
        text += "\n"

    if hourly:
        peak = max(hourly, key=lambda x: x['count'])
        text += f"⏰ پرترافیک‌ترین ساعت: {peak['hour']:02d}:00 ({peak['count']} پیام)\n"

    keyboard = [
        [InlineKeyboardButton("📈 رشد اعضا", callback_data=f"stats_growth:{group_id}"),
         InlineKeyboardButton("⏰ فعالیت ساعتی", callback_data=f"stats_hourly:{group_id}")],
        [InlineKeyboardButton("🏆 کاربران فعال", callback_data=f"stats_users:{group_id}"),
         InlineKeyboardButton("🚫 تخلفات", callback_data=f"stats_violations:{group_id}")],
        [InlineKeyboardButton("🔙 برگشت", callback_data=f"grp:{group_id}")],
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def show_stats_growth(query, group_id):
    g = db.get_group(group_id)
    name = g.get('group_name','نامشخص') if g else 'نامشخص'
    growth = db.get_member_growth(group_id, 30)
    text = f"📈 رشد اعضا «{name}» (30 روز)\n\n"
    if growth:
        for row in growth:
            text += f"📅 {row['day']}: ورود {row['joins']} | خروج {row['lefts']}\n"
    else: text += "❌ اطلاعاتی یافت نشد"
    keyboard = [[InlineKeyboardButton("🔙 برگشت", callback_data=f"dashboard:{group_id}")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def show_stats_hourly(query, group_id):
    g = db.get_group(group_id)
    name = g.get('group_name','نامشخص') if g else 'نامشخص'
    hourly = db.get_hourly_activity(group_id, 7)
    text = f"⏰ فعالیت ساعتی «{name}» (7 روز)\n\n"
    if hourly:
        for row in hourly:
            bar = "█" * min(int(row['count'] / 5), 10)
            text += f"{row['hour']:02d}:00 {bar} {row['count']}\n"
    else: text += "❌ اطلاعاتی یافت نشد"
    keyboard = [[InlineKeyboardButton("🔙 برگشت", callback_data=f"dashboard:{group_id}")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def show_stats_users(query, group_id):
    g = db.get_group(group_id)
    name = g.get('group_name','نامشخص') if g else 'نامشخص'
    users = db.get_active_users(group_id, 7)
    text = f"🏆 کاربران فعال «{name}» (7 روز)\n\n"
    if users:
        for i, u in enumerate(users, 1):
            text += f"{i}. {u['user_name']}: {u['count']} پیام\n"
    else: text += "❌ اطلاعاتی یافت نشد"
    keyboard = [[InlineKeyboardButton("🔙 برگشت", callback_data=f"dashboard:{group_id}")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def show_stats_violations(query, group_id):
    g = db.get_group(group_id)
    name = g.get('group_name','نامشخص') if g else 'نامشخص'
    conn = db.get_conn()
    rows = conn.execute("""
        SELECT user_name, action, reason, done_at FROM violations
        WHERE group_id=? ORDER BY done_at DESC LIMIT 20
    """, (group_id,)).fetchall()
    conn.close()
    text = f"🚫 تخلفات اخیر «{name}»\n\n"
    if rows:
        for r in rows:
            text += f"👤 {r['user_name']} | {r['action']} | {r['reason'][:20]}\n"
    else: text += "❌ تخلفی ثبت نشده"
    keyboard = [[InlineKeyboardButton("🔙 برگشت", callback_data=f"dashboard:{group_id}")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

# ============================================
# مدیریت کاربران
# ============================================

async def show_users_panel(query, group_id):
    g = db.get_group(group_id)
    name = g.get('group_name','نامشخص') if g else 'نامشخص'
    keyboard = [
        [InlineKeyboardButton("🔍 جستجوی کاربر", callback_data=f"searchuser:{group_id}")],
        [InlineKeyboardButton("🔙 برگشت", callback_data=f"grp:{group_id}")],
    ]
    await query.edit_message_text(
        f"👥 مدیریت کاربران «{name}»\n\n📌 برای مدیریت کاربر، آیدی عددی یا یوزرنیم او را وارد کنید",
        reply_markup=InlineKeyboardMarkup(keyboard))

# ============================================
# تنظیمات دیگر
# ============================================

async def show_other(query, group_id):
    s = db.get_settings(group_id)
    g = db.get_group(group_id)
    name = g.get('group_name','نامشخص') if g else 'نامشخص'
    gem = s.get('gemini_enabled', 0)
    del_bot = s.get('delete_bot_msg', 0)
    del_sec = s.get('delete_bot_msg_seconds', 30)

    def tbtn(label, key, val):
        ico = "🟢 فعال" if val else "🔴 غیرفعال"
        nv = 0 if val else 1
        return InlineKeyboardButton(f"{ico} | {label}", callback_data=f"tog:{group_id}:{key}:{nv}")

    keyboard = [
        [tbtn("🤖 هوش مصنوعی Gemini", "gemini_enabled", gem)],
        [tbtn(f"🗑 حذف خودکار پیام ربات", "delete_bot_msg", del_bot)],
        [InlineKeyboardButton(f"⏱ زمان حذف: {del_sec} ثانیه", callback_data=f"delsec:{group_id}")],
        [InlineKeyboardButton("🔗 لینک گروه", callback_data=f"setlink:{group_id}"),
         InlineKeyboardButton("📝 توضیحات", callback_data=f"setinfo:{group_id}")],
        [InlineKeyboardButton("📜 قوانین گروه", callback_data=f"setrules:{group_id}")],
        [InlineKeyboardButton("📩 ارتباط با سازنده", callback_data=f"contactowner:{group_id}")],
        [InlineKeyboardButton("🔙 برگشت", callback_data=f"grp:{group_id}")],
    ]
    await query.edit_message_text(f"⚙️ تنظیمات «{name}»", reply_markup=InlineKeyboardMarkup(keyboard))

async def show_delsec_picker(query, group_id):
    s = db.get_settings(group_id); lang = s.get('lang','fa')
    keyboard = [
        [InlineKeyboardButton("5s", callback_data=f"setdelsec:{group_id}:5"),
         InlineKeyboardButton("10s", callback_data=f"setdelsec:{group_id}:10")],
        [InlineKeyboardButton("30s", callback_data=f"setdelsec:{group_id}:30"),
         InlineKeyboardButton("1m", callback_data=f"setdelsec:{group_id}:60")],
        [InlineKeyboardButton("2m", callback_data=f"setdelsec:{group_id}:120"),
         InlineKeyboardButton("5m", callback_data=f"setdelsec:{group_id}:300")],
        [InlineKeyboardButton(t("back",lang), callback_data=f"other:{group_id}")],
    ]
    await query.edit_message_text(t("other_pick_delsec",lang), reply_markup=InlineKeyboardMarkup(keyboard))

# ============================================
# راهنما
# ============================================

HELP = {
    "main": ("📖 راهنمای ربات هیوا\n\n🔴🟢 قفل‌ها — کنترل محتوای گروه\n🌙 خاموشی — ساعت سکوت گروه\n👋 خوش‌آمد — پیام اعضای جدید\n🚪 پیام خروج — اطلاع خروج\n🛡 امنیت — کپچا، ضد اسپم\n⚠️ اخطار — مجازات خودکار\n📨 اد اجباری — شرط عضویت\n✅ لیست سفید — معافیت\n🚫 کلمات ممنوعه — فیلتر\n📊 تابلو آمار — آنالیتیکس\n👥 مدیریت کاربران\n\n📌 همه تنظیمات از پنل انجام می‌شود"),
    "security": ("🛡 راهنمای امنیت\n\n🤖 کپچا: عضو جدید باید دکمه بزند\n🚫 ضد اسپم: پیام فوروارد حذف می‌شود\n⚡ ضد فلود: پیام سریع = 5 دقیقه سکوت\n🔍 تشخیص ربات: اکانت مشکوک بلاک می‌شود"),
    "warn": ("⚠️ راهنمای اخطار\n\nبعد از رسیدن به حد اخطار، مجازات اعمال می‌شود\n\nاقدام‌ها:\nاخراج موقت / بن دائم / ساکت"),
    "force": ("📨 راهنمای اد اجباری\n\nاعضا باید تعداد مشخصی نفر اد کنند\n\nتعداد: چند نفر لازم است\nمدت: دائمی یا با انقضا"),
}

async def show_help(query, key, back_to, group_id=0):
    text = HELP.get(key, HELP["main"])
    if back_to == "mygroups" or group_id == 0:
        cb = "mygroups"
    else:
        cb = f"{back_to}:{group_id}"
    keyboard = [[InlineKeyboardButton("🔙 برگشت", callback_data=cb)]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

# ============================================
# /start
# ============================================

async def cmd_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """سازنده با این دستور به مدیر گروه پاسخ میده: /reply_USER_ID متن پاسخ"""
    if not is_owner(update.effective_user.id):
        return
    if update.effective_chat.type != 'private':
        return
    text = update.message.text
    # فرمت: /reply_123456789 متن پاسخ
    match = __import__('re').match(r'/reply_(\d+)\s+(.*)', text, __import__('re').DOTALL)
    if not match:
        await update.message.reply_text("فرمت اشتباه!\nمثال: /reply_123456789 متن پاسخ شما")
        return
    target_id = int(match.group(1))
    reply_text = match.group(2)
    try:
        await context.bot.send_message(target_id, f"📩 پاسخ از سازنده ربات هیوا:\n\n{reply_text}")
        await update.message.reply_text("✅ پاسخ ارسال شد.")
    except Exception as e:
        await update.message.reply_text(f"❌ خطا: {e}")


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != 'private': return
    user = update.effective_user

    # اگه کاربر هنوز زبان انتخاب نکرده
    user_lang = context.user_data.get('lang')
    if not user_lang and not is_owner(user.id):
        keyboard = [
            [InlineKeyboardButton("🇮🇷 فارسی", callback_data="setlang:fa"),
             InlineKeyboardButton("🇬🇧 English", callback_data="setlang:en")],
        ]
        await update.message.reply_text(
            t("select_lang"),
            reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if is_owner(user.id):
        ag = db.get_all_active_groups(); allg = db.get_all_groups()
        keyboard = [
            [InlineKeyboardButton("📋 لیست گروه‌ها", callback_data="admin:list")],
            [InlineKeyboardButton("📊 آمار کلی", callback_data="admin:stats")],
            [InlineKeyboardButton("📢 پیام به همه", callback_data="admin:broadcast")],
            [InlineKeyboardButton("💰 مدیریت اشتراک‌ها", callback_data="admin:subs")],
            [InlineKeyboardButton("👤 پنل مدیریت گروه‌ها", callback_data="mygroups")],
        ]
        await update.message.reply_text(
            f"👋 سلام {get_name(user)}!\n🤖 پنل سازنده ربات هیوا\n\n✅ فعال: {len(ag)} | 📁 کل: {len(allg)}",
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
        if data.startswith("setlang:"):
            lang = data.split(":")[1]
            context.user_data['lang'] = lang
            await query.edit_message_text(t("lang_saved", lang))
            # ذخیره زبان برای همه گروه‌های این مدیر
            all_groups = db.get_all_active_groups()
            for g in all_groups:
                try:
                    member = await context.bot.get_chat_member(g['group_id'], user.id)
                    if member.status in ['administrator', 'creator']:
                        db.update_setting(g['group_id'], 'lang', lang)
                except: pass
            # بعد از انتخاب زبان، پنل اصلی رو نشون بده
            await asyncio.sleep(1)
            user = query.from_user
            keyboard = []
            all_groups = db.get_all_active_groups()
            user_groups = []
            for g in all_groups:
                try:
                    member = await context.bot.get_chat_member(g['group_id'], user.id)
                    if member.status in ['administrator', 'creator']:
                        user_groups.append(g)
                except: pass
            if not user_groups:
                await context.bot.send_message(user.id, t("no_groups", lang))
                return
            for g in user_groups:
                keyboard.append([InlineKeyboardButton(
                    f"🏠 {g.get('group_name','?')}",
                    callback_data=f"grp:{g['group_id']}")])
            keyboard.append([InlineKeyboardButton(t("menu_lang", lang), callback_data="changelang")])
            await context.bot.send_message(user.id, t("select_group", lang),
                reply_markup=InlineKeyboardMarkup(keyboard))
            return

        elif data == "changelang":
            keyboard = [
                [InlineKeyboardButton("🇮🇷 فارسی", callback_data="setlang:fa"),
                 InlineKeyboardButton("🇬🇧 English", callback_data="setlang:en")],
            ]
            await query.edit_message_text(t("select_lang"), reply_markup=InlineKeyboardMarkup(keyboard))
            return

        elif data == "mygroups":
            lang = context.user_data.get('lang', 'fa')
            await show_my_groups(query, context, user.id, edit=True, lang=lang)
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
        elif data.startswith("dashboard:"):
            await show_dashboard(query, int(data.split(":")[1]))
        elif data.startswith("stats_growth:"):
            await show_stats_growth(query, int(data.split(":")[1]))
        elif data.startswith("stats_hourly:"):
            await show_stats_hourly(query, int(data.split(":")[1]))
        elif data.startswith("stats_users:"):
            await show_stats_users(query, int(data.split(":")[1]))
        elif data.startswith("stats_violations:"):
            await show_stats_violations(query, int(data.split(":")[1]))
        elif data.startswith("users:"):
            await show_users_panel(query, int(data.split(":")[1]))
        elif data.startswith("other:"):
            await show_other(query, int(data.split(":")[1]))

        elif data.startswith("help:"):
            parts = data.split(":")
            key = parts[1]; back_to = parts[2]; group_id = int(parts[3]) if len(parts) > 3 else 0
            await show_help(query, key, back_to, group_id)

        # ساعت خاموشی از پنل
        elif data.startswith("setquiet:") or data.startswith("editquiet:"):
            parts = data.split(":"); group_id = int(parts[1]); num = parts[2]
            await show_quiet_from_picker(query, group_id, num)

        elif data.startswith("delquiet:"):
            parts = data.split(":"); group_id = int(parts[1]); num = parts[2]
            db.update_setting(group_id, f'quiet_{num}_from', None)
            db.update_setting(group_id, f'quiet_{num}_to', None)
            db.update_setting(group_id, f'quiet_{num}_state', 0)
            await show_quiet(query, group_id)

        elif data.startswith("quietfrom:"):
            parts = data.split(":"); group_id = int(parts[1]); num = parts[2]; from_t = f"{parts[3]}:{parts[4]}"
            await show_quiet_to_picker(query, group_id, num, from_t)

        elif data.startswith("quietto:"):
            parts = data.split(":"); group_id = int(parts[1]); num = parts[2]
            from_t = f"{parts[3]}:{parts[4]}"; to_t = f"{parts[5]}:{parts[6]}"
            db.update_setting(group_id, f'quiet_{num}_from', from_t)
            db.update_setting(group_id, f'quiet_{num}_to', to_t)
            db.update_setting(group_id, f'quiet_{num}_state', 0)
            jalali, miladi = now_date_full()
            try:
                await context.bot.send_message(
                    int(data.split(":")[1]),
                    f"✅ خاموشی {num} از {from_t} تا {to_t} تنظیم شد.\n📅 {jalali} | {miladi}")
            except: pass
            await show_quiet(query, group_id)

        # کلمات ممنوعه از پنل
        elif data.startswith("addbadword:"):
            group_id = int(data.split(":")[1])
            context.user_data['action'] = f'addbadword:{group_id}'
            s = db.get_settings(group_id); lang = s.get('lang','fa')
            await query.edit_message_text(t("badwords_add_prompt", lang))

        elif data.startswith("delbadword:"):
            await show_del_badword(query, int(data.split(":")[1]))

        elif data.startswith("confirmdelbw:"):
            parts = data.split(":"); group_id = int(parts[1]); word = parts[2]
            db.remove_bad_word(group_id, word)
            await show_badwords(query, group_id)

        # تنظیمات دیگر
        elif data.startswith("warnlimit:"):
            await show_warn_limit_picker(query, int(data.split(":")[1]))
        elif data.startswith("setwarnlimit:"):
            parts = data.split(":"); group_id = int(parts[1]); n = int(parts[2])
            db.update_setting(group_id, 'warn_limit', n)
            await show_warn(query, group_id)
        elif data.startswith("warnaction:"):
            await show_warn_action_picker(query, int(data.split(":")[1]))
        elif data.startswith("setwarnaction:"):
            parts = data.split(":"); group_id = int(parts[1]); action = parts[2]
            db.update_setting(group_id, 'warn_action', action)
            await show_warn(query, group_id)

        elif data.startswith("forcecount:"):
            await show_force_count_picker(query, int(data.split(":")[1]))
        elif data.startswith("setforcecount:"):
            parts = data.split(":"); group_id = int(parts[1]); n = int(parts[2])
            db.update_setting(group_id, 'force_invite_count', n)
            await show_force(query, group_id)
        elif data.startswith("forcedays:"):
            await show_force_days_picker(query, int(data.split(":")[1]))
        elif data.startswith("setforcedays:"):
            parts = data.split(":"); group_id = int(parts[1]); n = int(parts[2])
            db.update_setting(group_id, 'force_invite_days', n)
            await show_force(query, group_id)

        elif data.startswith("delsec:"):
            await show_delsec_picker(query, int(data.split(":")[1]))
        elif data.startswith("setdelsec:"):
            parts = data.split(":"); group_id = int(parts[1]); n = int(parts[2])
            db.update_setting(group_id, 'delete_bot_msg_seconds', n)
            await show_other(query, group_id)

        elif data.startswith("contactowner:"):
            group_id = int(data.split(":")[1])
            context.user_data['action'] = f'contactowner:{group_id}'
            await query.edit_message_text(
                "📩 پیام خود را بنویسید (سوال، مشکل یا فیش واریز):\n\n"
                "پیام شما مستقیم به سازنده ربات ارسال می‌شود.\n\n"
                "برای لغو: /cancel")

        elif data.startswith("setlink:"):
            group_id = int(data.split(":")[1])
            context.user_data['action'] = f'setlink:{group_id}'
            await query.edit_message_text("✏️ لینک گروه را وارد کنید:\n\nمثال: https://t.me/groupname\n\nبرای لغو: /cancel")

        elif data.startswith("setinfo:"):
            group_id = int(data.split(":")[1])
            context.user_data['action'] = f'setinfo:{group_id}'
            await query.edit_message_text("✏️ توضیحات گروه را بنویسید:\n\nبرای لغو: /cancel")

        elif data.startswith("setrules:"):
            group_id = int(data.split(":")[1])
            context.user_data['action'] = f'setrules:{group_id}'
            await query.edit_message_text("✏️ قوانین گروه را بنویسید:\n\nبرای لغو: /cancel")

        elif data.startswith("setwelcome:"):
            group_id = int(data.split(":")[1])
            context.user_data['action'] = f'setwelcome:{group_id}'
            await query.edit_message_text("✏️ متن پیام خوش‌آمد را بنویسید:\n\nمتغیرها:\n{name} = نام کاربر\n{group} = نام گروه\n\nبرای لغو: /cancel")

        elif data.startswith("searchuser:"):
            group_id = int(data.split(":")[1])
            context.user_data['action'] = f'searchuser:{group_id}'
            await query.edit_message_text("🔍 آیدی عددی یا یوزرنیم کاربر را وارد کنید:\n\nبرای لغو: /cancel")

        elif data.startswith("tog:"):
            parts = data.split(":"); group_id = int(parts[1]); key = parts[2]; val = int(parts[3])
            db.update_setting(group_id, key, val)
            if key.startswith("lock_") or key in ["group_locked","public_commands"]:
                await show_locks(query, group_id)
            elif key in ["welcome_enabled","welcome_button"]:
                await show_welcome(query, group_id)
            elif key == "goodbye_enabled":
                await show_goodbye(query, group_id)
            elif key in ["captcha_enabled","anti_spam","anti_flood","anti_raid","bot_detection"]:
                await show_security(query, group_id)
            elif key == "auto_warn":
                await show_warn(query, group_id)
            elif key == "force_invite":
                await show_force(query, group_id)
            elif key in ["gemini_enabled","delete_bot_msg"]:
                await show_other(query, group_id)

        elif data.startswith("captcha_ok:"):
            parts = data.split(":"); group_id = int(parts[1]); user_id = int(parts[2])
            if query.from_user.id == user_id:
                db.remove_captcha_pending(group_id, user_id)
                await query.edit_message_text("✅ تأیید شدید! می‌توانید پیام بفرستید.")
            else:
                await query.answer("این دکمه برای شما نیست!", show_alert=True)

        elif data.startswith("rules_ok:"):
            await query.answer("✅ ممنون! خوش آمدید.", show_alert=True)

        elif data.startswith("userban:"):
            parts = data.split(":"); group_id = int(parts[1]); uid = int(parts[2])
            try:
                await context.bot.ban_chat_member(group_id, uid)
                await query.edit_message_text(f"✅ کاربر {uid} بن شد.")
            except Exception as e:
                await query.edit_message_text(f"❌ خطا: {e}")

        elif data.startswith("userunban:"):
            parts = data.split(":"); group_id = int(parts[1]); uid = int(parts[2])
            try:
                await context.bot.unban_chat_member(group_id, uid)
                await query.edit_message_text(f"✅ کاربر {uid} آنبن شد.")
            except Exception as e:
                await query.edit_message_text(f"❌ خطا: {e}")

        elif data.startswith("usermute:"):
            parts = data.split(":"); group_id = int(parts[1]); uid = int(parts[2])
            try:
                await context.bot.restrict_chat_member(group_id, uid, ChatPermissions(can_send_messages=False))
                await query.edit_message_text(f"✅ کاربر {uid} ساکت شد.")
            except Exception as e:
                await query.edit_message_text(f"❌ خطا: {e}")

        elif data.startswith("userunmute:"):
            parts = data.split(":"); group_id = int(parts[1]); uid = int(parts[2])
            try:
                await context.bot.restrict_chat_member(group_id, uid,
                    ChatPermissions(can_send_messages=True, can_send_photos=True, can_send_videos=True, can_send_other_messages=True))
                await query.edit_message_text(f"✅ کاربر {uid} آزاد شد.")
            except Exception as e:
                await query.edit_message_text(f"❌ خطا: {e}")

        elif data.startswith("userwarnreset:"):
            parts = data.split(":"); group_id = int(parts[1]); uid = int(parts[2])
            db.reset_warnings(group_id, uid)
            await query.edit_message_text(f"✅ اخطارهای کاربر {uid} ریست شد.")

        # پنل سازنده
        elif data == "admin:subs":
            if not is_owner(user.id): return
            allg = db.get_all_groups()
            keyboard = []
            for g in allg[:20]:
                sub = db.get_group_subscription(g['group_id'])
                if sub and sub.get('expiry_date'):
                    try:
                        exp = datetime.strptime(sub['expiry_date'], "%Y-%m-%d %H:%M:%S")
                        days_left = (exp - datetime.now()).days
                        status = f"⏳ {days_left}روز" if days_left > 0 else "❌ منقضی"
                    except:
                        status = "✅"
                else:
                    status = "🆓 رایگان"
                keyboard.append([InlineKeyboardButton(
                    f"{status} | {g.get('group_name','نامشخص')}",
                    callback_data=f"admin:grp:{g['group_id']}")])
            keyboard.append([InlineKeyboardButton("🔙 برگشت", callback_data="admin:back")])
            await query.edit_message_text(
                "💰 مدیریت اشتراک‌ها\n\n📌 روی هر گروه بزنید تا اشتراک تنظیم کنید:",
                reply_markup=InlineKeyboardMarkup(keyboard))

        elif data.startswith("admin:grp:"):
            if not is_owner(user.id): return
            group_id = int(data.split(":")[2])
            g = db.get_group(group_id)
            stats = db.get_group_stats(group_id)
            if not g:
                await query.edit_message_text("❌ یافت نشد.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 برگشت", callback_data="admin:list")]]))
                return
            st = "✅ فعال" if g.get('is_active') else "❌ غیرفعال"
            tl = "❌ غیرفعال کردن" if g.get('is_active') else "✅ فعال کردن"
            td = f"admin:deact:{group_id}" if g.get('is_active') else f"admin:act:{group_id}"
            # اشتراک
            sub = db.get_group_subscription(group_id)
            if sub and sub.get('expiry_date'):
                try:
                    exp = datetime.strptime(sub['expiry_date'], "%Y-%m-%d %H:%M:%S")
                    days_left = (exp - datetime.now()).days
                    sub_text = f"📅 اشتراک: {days_left} روز مانده"
                except:
                    sub_text = "📅 اشتراک: نامشخص"
            else:
                sub_text = "📅 اشتراک: رایگان (دائم)"
            keyboard = [
                [InlineKeyboardButton(tl, callback_data=td)],
                [InlineKeyboardButton("📢 پیام به گروه", callback_data=f"admin:sendmsg:{group_id}"),
                 InlineKeyboardButton("👤 پیام به مدیر", callback_data=f"admin:sendowner:{group_id}")],
                [InlineKeyboardButton("⏱ تنظیم اشتراک", callback_data=f"admin:setsub:{group_id}"),
                 InlineKeyboardButton("🚪 حذف ربات", callback_data=f"admin:leave:{group_id}")],
                [InlineKeyboardButton("🔙 برگشت", callback_data="admin:subs")]
            ]
            text_out = (
                f"📌 {g.get('group_name','نامشخص')}\n"
                f"🆔 {group_id}\n📊 {st}\n"
                f"👤 @{g.get('owner_username','-')}\n{sub_text}\n\n"
                f"🗑 پیام حذف: {stats['deleted']}\n"
                f"⚠️ اخطار: {stats['warns']}\n"
                f"👥 ورودی: {stats['joins']} | خروجی: {stats['lefts']}"
            )
            await query.edit_message_text(text_out, reply_markup=InlineKeyboardMarkup(keyboard))

        elif data.startswith("admin:sendowner:"):
            if not is_owner(user.id): return
            group_id = int(data.split(":")[2])
            g = db.get_group(group_id)
            owner_id = g.get('owner_id') if g else None
            if owner_id:
                context.user_data['action'] = f'sendowner:{owner_id}:{group_id}'
                await query.edit_message_text("📢 پیام خود را برای مدیر این گروه بنویسید:\n\nبرای لغو: /cancel")
            else:
                await query.edit_message_text("❌ اطلاعات مدیر یافت نشد.")

        elif data.startswith("admin:setsub:"):
            if not is_owner(user.id): return
            group_id = int(data.split(":")[2])
            keyboard = [
                [InlineKeyboardButton("30 روز", callback_data=f"admin:sub:{group_id}:30"),
                 InlineKeyboardButton("60 روز", callback_data=f"admin:sub:{group_id}:60")],
                [InlineKeyboardButton("90 روز", callback_data=f"admin:sub:{group_id}:90"),
                 InlineKeyboardButton("♾ دائم رایگان", callback_data=f"admin:sub:{group_id}:0")],
                [InlineKeyboardButton("🔙 برگشت", callback_data=f"admin:grp:{group_id}")],
            ]
            await query.edit_message_text("⏱ مدت اشتراک را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(keyboard))

        elif data.startswith("admin:sub:"):
            if not is_owner(user.id): return
            parts = data.split(":"); group_id = int(parts[2]); days = int(parts[3])
            db.set_group_subscription(group_id, days)
            if days > 0:
                g = db.get_group(group_id)
                owner_id = g.get('owner_id') if g else None
                if owner_id:
                    try:
                        exp_date = (datetime.now() + timedelta(days=days)).strftime("%Y/%m/%d")
                        exp_shamsi = jalali_str(__import__('datetime').datetime.strptime(exp_date, "%Y-%m-%d %H:%M:%S"))
                        exp_miladi = __import__('datetime').datetime.strptime(exp_date, "%Y-%m-%d %H:%M:%S").strftime("%Y/%m/%d")
                        g_lang = db.get_settings(group_id).get('lang', 'fa')
                        await context.bot.send_message(owner_id,
                            t("sub_activated", g_lang, days=days, shamsi=exp_shamsi, miladi=exp_miladi))
                    except: pass
                await query.edit_message_text(
                    f"✅ اشتراک {days} روزه فعال شد.",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 برگشت", callback_data="admin:subs")]]))
            else:
                await query.edit_message_text(
                    "✅ گروه رایگان و دائمی شد.",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 برگشت", callback_data="admin:subs")]]))

        elif data.startswith("admin:act:"):
            if not is_owner(user.id): return
            db.activate_group_free(int(data.split(":")[2]))
            await query.edit_message_text("✅ فعال شد.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 برگشت", callback_data="admin:subs")]]))

        elif data.startswith("admin:deact:"):
            if not is_owner(user.id): return
            db.deactivate_group(int(data.split(":")[2]))
            await query.edit_message_text("❌ غیرفعال شد.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 برگشت", callback_data="admin:subs")]]))

        elif data.startswith("admin:sendmsg:"):
            if not is_owner(user.id): return
            group_id = int(data.split(":")[2])
            context.user_data['action'] = f'sendmsg:{group_id}'
            await query.edit_message_text("📢 پیام خود را برای این گروه بنویسید:\n\nبرای لغو: /cancel")

        elif data.startswith("admin:leave:"):
            if not is_owner(user.id): return
            group_id = int(data.split(":")[2])
            try:
                await context.bot.leave_chat(group_id)
                db.deactivate_group(group_id)
                await query.edit_message_text("✅ ربات از گروه خارج شد.")
            except Exception as e:
                await query.edit_message_text(f"❌ خطا: {e}")

    except Exception as e:
        logger.error(f"Button error: {e}", exc_info=True)
        try: await query.edit_message_text("❌ خطایی رخ داد. /start بزنید.")
        except: pass

# ============================================
# پیام‌های پیوی
# ============================================

async def private_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != 'private': return
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
            except: fail += 1
        await update.message.reply_text(f"✅ موفق: {ok} | ❌ ناموفق: {fail}")
        context.user_data.clear()

    elif action.startswith('sendmsg:'):
        group_id = int(action.split(':')[1])
        try:
            await context.bot.send_message(group_id, text)
            await update.message.reply_text("✅ پیام ارسال شد.")
        except Exception as e:
            await update.message.reply_text(f"❌ خطا: {e}")
        context.user_data.clear()

    elif action.startswith('setwelcome:'):
        group_id = int(action.split(':')[1])
        db.update_setting(group_id, 'welcome_text', text)
        context.user_data.clear()
        await update.message.reply_text("✅ متن خوش‌آمد ذخیره شد.")

    elif action.startswith('contactowner:'):
        group_id = int(action.split(':')[1])
        g = db.get_group(group_id)
        group_name = g.get('group_name', 'نامشخص') if g else 'نامشخص'
        try:
            await context.bot.send_message(
                config.ADMIN_ID,
                f"📩 پیام از مدیر گروه\n\n"
                f"👤 {get_name(user)} (@{user.username or '-'})\n"
                f"🏠 گروه: {group_name}\n"
                f"🆔 آیدی گروه: {group_id}\n\n"
                f"💬 پیام:\n{text}")
            await update.message.reply_text("✅ پیام شما به سازنده ارسال شد.")
        except Exception as e:
            await update.message.reply_text(f"❌ خطا: {e}")
        context.user_data.clear()

    elif action.startswith('setlink:'):
        group_id = int(action.split(':')[1])
        db.update_group_field(group_id, 'group_link', text)
        context.user_data.clear()
        await update.message.reply_text("✅ لینک گروه ذخیره شد.")

    elif action.startswith('setinfo:'):
        group_id = int(action.split(':')[1])
        db.update_group_field(group_id, 'group_info', text)
        context.user_data.clear()
        await update.message.reply_text("✅ توضیحات گروه ذخیره شد.")

    elif action.startswith('setrules:'):
        group_id = int(action.split(':')[1])
        db.update_group_field(group_id, 'group_rules', text)
        context.user_data.clear()
        await update.message.reply_text("✅ قوانین گروه ذخیره شد.")

    elif action.startswith('addbadword:'):
        group_id = int(action.split(':')[1])
        db.add_bad_word(group_id, text.strip())
        context.user_data.clear()
        s = db.get_settings(group_id); lang = s.get('lang','fa')
        await update.message.reply_text(t("badwords_added", lang, word=text.strip()))

    elif action.startswith('contact_owner:'):
        group_id = int(action.split(':')[1])
        g = db.get_group(group_id)
        group_name = g.get('group_name', 'نامشخص') if g else 'نامشخص'
        owner_id = user.id
        try:
            # ارسال با اطلاعات برای امکان پاسخ
            sent = await context.bot.send_message(
                config.ADMIN_ID,
                f"📞 پیام از مدیر گروه\n"
                f"👤 مدیر: {get_name(user)} (آیدی: {owner_id})\n"
                f"🏠 گروه: {group_name} (آیدی: {group_id})\n\n"
                f"💬 پیام:\n{text}\n\n"
                f"📌 برای پاسخ به این مدیر: /reply_{owner_id} [متن پاسخ]"
            )
            await update.message.reply_text("✅ پیام شما به سازنده ارسال شد.")
        except Exception as e:
            await update.message.reply_text(f"❌ خطا: {e}")
        context.user_data.clear()

    elif action.startswith('sendowner:'):
        parts = action.split(':'); owner_id = int(parts[1]); group_id = int(parts[2])
        g = db.get_group(group_id)
        name = g.get('group_name', 'نامشخص') if g else 'نامشخص'
        try:
            await context.bot.send_message(
                owner_id,
                f"📢 پیام از سازنده ربات هیوا برای گروه {name}:\n\n{text}"
            )
            await update.message.reply_text("✅ پیام به مدیر گروه ارسال شد.")
        except Exception as e:
            await update.message.reply_text(f"❌ خطا در ارسال: {e}")
        context.user_data.clear()

    elif action.startswith('searchuser:'):
        group_id = int(action.split(':')[1])
        uid_text = text.strip().replace('@', '')
        try:
            if uid_text.isdigit():
                uid = int(uid_text)
                member = await context.bot.get_chat_member(group_id, uid)
            else:
                member = await context.bot.get_chat_member(group_id, f"@{uid_text}")
                uid = member.user.id

            warns = db.get_warnings(group_id, uid)
            violations = db.get_user_violations(group_id, uid)
            invites = db.get_user_invite_count(group_id, uid)
            name = get_name(member.user)
            status = member.status

            text_out = (f"👤 اطلاعات کاربر\n\nنام: {name}\n"
                f"آیدی: {uid}\nوضعیت: {status}\n"
                f"⚠️ اخطار: {warns}\n"
                f"📨 دعوت: {invites}\n"
                f"🚫 تخلفات: {len(violations)}\n")

            if violations:
                text_out += "\nآخرین تخلفات:\n"
                for v in violations[:3]:
                    text_out += f"• {v['action']}: {v['reason'][:20]}\n"

            keyboard = [
                [InlineKeyboardButton("🚫 بن", callback_data=f"userban:{group_id}:{uid}"),
                 InlineKeyboardButton("🔓 آنبن", callback_data=f"userunban:{group_id}:{uid}")],
                [InlineKeyboardButton("🔇 میوت", callback_data=f"usermute:{group_id}:{uid}"),
                 InlineKeyboardButton("🔊 آنمیوت", callback_data=f"userunmute:{group_id}:{uid}")],
                [InlineKeyboardButton("🔄 ریست اخطار", callback_data=f"userwarnreset:{group_id}:{uid}")],
                [InlineKeyboardButton("🔙 برگشت", callback_data=f"users:{group_id}")],
            ]
            await update.message.reply_text(text_out, reply_markup=InlineKeyboardMarkup(keyboard))
        except Exception as e:
            await update.message.reply_text(f"❌ کاربر یافت نشد: {e}")
        context.user_data.clear()

# ============================================
# ورود اعضا
# ============================================

async def member_joined(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.new_chat_members: return
    group_id = update.effective_chat.id
    if not db.is_group_active(group_id): return
    s = db.get_settings(group_id)
    lang = s.get('lang', 'fa')
    inviter = update.message.from_user

    for new_member in update.message.new_chat_members:
        if new_member.is_bot: continue
        name = get_name(new_member)
        db.log_member(group_id, new_member.id, name, 'join')

        # تشخیص ربات مزاحم
        if s.get('bot_detection'):
            suspicious = False
            if not new_member.username and not new_member.last_name:
                fn = new_member.first_name or ""
                if len(fn) < 3 or fn.replace(' ','').isdigit():
                    suspicious = True
            if suspicious:
                try:
                    await context.bot.ban_chat_member(group_id, new_member.id)
                    await bot_reply(context, group_id, t("suspicious_bot", lang, name=name), 30)
                    db.log_violation(group_id, new_member.id, name, 'bot_ban', 'تشخیص ربات مشکوک')
                except: pass
                continue

        if inviter and inviter.id != new_member.id:
            db.add_invite(group_id, inviter.id, get_name(inviter), new_member.id, name)
            if s.get('force_invite'):
                db.init_force_status(group_id, inviter.id)
                db.increment_force_invite(group_id, inviter.id)
                status = db.get_force_status(group_id, inviter.id)
                need = s.get('force_invite_count', 5)
                if status and status['invite_count'] >= need and not status['is_free']:
                    db.set_force_free(group_id, inviter.id, 1)

        del_sec = s.get('delete_bot_msg_seconds', 30) if s.get('delete_bot_msg') else 0

        if s.get('captcha_enabled'):
            db.add_captcha_pending(group_id, new_member.id, name)
            keyboard = [[InlineKeyboardButton(t("captcha_btn", lang), callback_data=f"captcha_ok:{group_id}:{new_member.id}")]]
            await bot_reply(context, group_id, t("captcha_msg", lang, name=name), del_sec, reply_markup=InlineKeyboardMarkup(keyboard))
            continue

        if s.get('force_invite') and not db.is_whitelisted(group_id, new_member.id):
            db.init_force_status(group_id, new_member.id)
            status = db.get_force_status(group_id, new_member.id)
            need = s.get('force_invite_count', 5)
            if status and not status['is_free'] and status['invite_count'] < need:
                remaining = need - status['invite_count']
                await bot_reply(context, group_id, t("force_invite_msg", lang, name=name, count=remaining), del_sec)
                continue

        if s.get('welcome_enabled', 1):
            wt = s.get('welcome_text', '')
            if wt:
                try: msg_text = wt.format(name=name, group=update.effective_chat.title or '')
                except: msg_text = wt
            else:
                msg_text = t("welcome", lang, name=name)

            if s.get('welcome_button'):
                keyboard = [[InlineKeyboardButton(t("rules_btn", lang), callback_data=f"rules_ok:{group_id}:{new_member.id}")]]
                await bot_reply(context, group_id, msg_text, del_sec, reply_markup=InlineKeyboardMarkup(keyboard))
            else:
                await bot_reply(context, group_id, msg_text, del_sec)

async def member_left(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.left_chat_member: return
    group_id = update.effective_chat.id
    if not db.is_group_active(group_id): return
    s = db.get_settings(group_id)
    member = update.message.left_chat_member
    if member.is_bot: return
    name = get_name(member)
    db.log_member(group_id, member.id, name, 'left')
    if not s.get('goodbye_enabled'): return
    lang = s.get('lang', 'fa')
    del_sec = s.get('delete_bot_msg_seconds', 30) if s.get('delete_bot_msg') else 0
    await bot_reply(context, group_id, t("goodbye", lang, name=name), del_sec)

# ============================================
# فیلتر پیام‌های گروه
# ============================================

async def filter_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_user: return
    group_id = update.effective_chat.id
    user = update.effective_user
    msg = update.message
    if not db.is_group_active(group_id): return

    # اگه command بود رد کن
    if msg.text and msg.text.startswith('/'):
        return

    if await is_group_admin(context, group_id, user.id):
        await handle_public_commands(update, context)
        return

    s = db.get_settings(group_id)
    lang = s.get('lang', 'fa')
    name = get_name(user)

    # ثبت فعالیت
    db.log_message_activity(group_id, user.id, name)

    if s.get('captcha_enabled') and db.is_captcha_pending(group_id, user.id):
        await safe_delete(msg); return

    if s.get('force_invite') and not db.is_whitelisted(group_id, user.id):
        db.init_force_status(group_id, user.id)
        status = db.get_force_status(group_id, user.id)
        need = s.get('force_invite_count', 5)
        if status and not status['is_free']:
            if s.get('force_invite_days', 0) > 0:
                try:
                    period_start = datetime.strptime(status['period_start'], "%Y-%m-%d %H:%M:%S")
                    if datetime.now() - period_start > timedelta(days=s['force_invite_days']):
                        db.reset_force_status(group_id, user.id)
                        status = db.get_force_status(group_id, user.id)
                except: pass
            if status and not status['is_free'] and status['invite_count'] < need:
                await safe_delete(msg)
                remaining = need - status['invite_count']
                del_sec = 10
                await bot_reply(context, group_id, t("force_invite_msg", lang, name=name, count=remaining), del_sec)
                return

    if s.get('group_locked'):
        await safe_delete(msg); return

    if is_quiet_time_now(s):
        await safe_delete(msg)
        db.log_deleted_message(group_id, user.id, name, "ساعت خاموشی")
        return

    if s.get('anti_flood'):
        count, first_time = db.track_flood(group_id, user.id)
        limit = s.get('anti_flood_count', 5); flood_secs = s.get('anti_flood_seconds', 10)
        try:
            first_dt = datetime.strptime(first_time, "%Y-%m-%d %H:%M:%S")
            if (datetime.now() - first_dt).seconds <= flood_secs:
                if count >= limit:
                    await safe_delete(msg)
                    try:
                        await context.bot.restrict_chat_member(group_id, user.id,
                            ChatPermissions(can_send_messages=False),
                            until_date=datetime.now() + timedelta(minutes=5))
                        del_sec = s.get('delete_bot_msg_seconds', 30) if s.get('delete_bot_msg') else 30
                        await bot_reply(context, group_id, t("flood_mute", lang, name=name), del_sec)
                        db.log_violation(group_id, user.id, name, 'mute', 'ضد فلود')
                    except: pass
                    db.reset_flood(group_id, user.id)
                    return
            else:
                db.reset_flood(group_id, user.id)
        except: pass

    reason = None

    if msg.text:
        txt = msg.text
        txt_norm = normalize_digits(txt)
        if s.get('lock_link') and ('t.me/' in txt or 'telegram.me/' in txt):
            reason = t("lock_link", lang)
        elif data.startswith("admin:"):
            if not is_owner(user.id):
                await query.answer("❌ دسترسی ندارید!", show_alert=True); return
            cmd = data[6:]
            if cmd == "stats":
                ag = db.get_all_active_groups(); allg = db.get_all_groups()
                keyboard = [[InlineKeyboardButton("🔙 برگشت", callback_data="admin:back")]]
                await query.edit_message_text(f"📊 آمار کلی\n\n📁 کل: {len(allg)}\n✅ فعال: {len(ag)}\n❌ غیرفعال: {len(allg)-len(ag)}",
                    reply_markup=InlineKeyboardMarkup(keyboard))
            elif cmd == "list":
                allg = db.get_all_groups()
                keyboard = []
                for g in allg[:20]:
                    s = "✅" if g.get('is_active') else "❌"
                    keyboard.append([InlineKeyboardButton(f"{s} {g.get('group_name','نامشخص')}", callback_data=f"admin:grp:{g['group_id']}")])
                keyboard.append([InlineKeyboardButton("🔙 برگشت", callback_data="admin:back")])
                await query.edit_message_text("📋 لیست گروه‌ها:", reply_markup=InlineKeyboardMarkup(keyboard))
            elif cmd == "broadcast":
                context.user_data['action'] = 'broadcast'
                await query.edit_message_text("📢 پیام خود را بنویسید:\n\nبرای لغو: /cancel")
            elif cmd == "back":
                ag = db.get_all_active_groups(); allg = db.get_all_groups()
                keyboard = [
                    [InlineKeyboardButton("📋 لیست گروه‌ها", callback_data="admin:list")],
                    [InlineKeyboardButton("📊 آمار کلی", callback_data="admin:stats")],
                    [InlineKeyboardButton("📢 پیام به همه", callback_data="admin:broadcast")],
                    [InlineKeyboardButton("💰 مدیریت اشتراک‌ها", callback_data="admin:subs")],
                    [InlineKeyboardButton("👤 پنل مدیریت گروه‌ها", callback_data="mygroups")],
                ]
                await query.edit_message_text(f"🤖 پنل سازنده\n\n✅ فعال: {len(ag)} | 📁 کل: {len(allg)}",
                    reply_markup=InlineKeyboardMarkup(keyboard))


        elif data.startswith("contact_owner:"):
            group_id = int(data.split(":")[1])
            context.user_data['action'] = f'contact_owner:{group_id}'
            await query.edit_message_text("📞 ارتباط با سازنده\n\nپیام یا فیش واریز خود را بفرستید:\n\nبرای لغو: /cancel")








        elif s.get('lock_site') and any(x in txt for x in ['http://','https://','www.']):
            reason = t("lock_site", lang)
        elif s.get('lock_id') and '@' in txt:
            reason = t("lock_id", lang)
        elif s.get('lock_hashtag') and '#' in txt:
            reason = t("lock_hashtag", lang)
        elif s.get('lock_phone') and re.search(r'(\+?\d{1,3}[\s-]?)?0?9\d{9}|\d{10,}', txt_norm):
            reason = t("lock_phone", lang)
        elif s.get('lock_slash') and txt.startswith('/'):
            reason = t("lock_slash", lang)
        elif s.get('lock_text'):
            reason = t("lock_text", lang)
        elif s.get('lock_bad_words'):
            bad_words = db.get_bad_words(group_id)
            if bad_words and any(w in txt.lower() for w in bad_words):
                reason = t("lock_bad_words", lang)
        if not reason and s.get('anti_spam') and msg.forward_date:
            reason = t("anti_spam", lang)
        if not reason and s.get('lock_emoji') and txt:
            # تشخیص ایموجی - کاراکترهای unicode بالای U+1F000
            import unicodedata
            has_emoji = any(
                unicodedata.category(c) in ('So', 'Sm') or
                0x1F000 <= ord(c) <= 0x1FFFF or
                0x2600 <= ord(c) <= 0x27BF or
                0xFE00 <= ord(c) <= 0xFE0F
                for c in txt
            )
            if has_emoji:
                reason = "ارسال ایموجی ممنوع است" 

    elif msg.photo and s.get('lock_photo'): reason = t("lock_photo", lang)
    elif msg.video and s.get('lock_video'): reason = t("lock_video", lang)
    elif msg.video_note and s.get('lock_video'): reason = t("lock_video", lang)
    elif msg.sticker and s.get('lock_sticker'): reason = t("lock_sticker", lang)
    elif msg.animation and s.get('lock_gif'): reason = t("lock_gif", lang)
    elif msg.document and msg.document.mime_type and 'gif' in msg.document.mime_type.lower() and s.get('lock_gif'):
        reason = t("lock_gif", lang)
    elif msg.voice and s.get('lock_voice'): reason = t("lock_voice", lang)
    elif msg.document and s.get('lock_file'): reason = t("lock_file", lang)
    elif msg.poll and s.get('lock_poll'): reason = t("lock_poll", lang)
    elif msg.location and s.get('lock_location'): reason = t("lock_location", lang)
    elif msg.contact and s.get('lock_phone'): reason = t("lock_phone", lang)

    if not reason:
        if msg.forward_from_chat:
            chat_type = msg.forward_from_chat.type if msg.forward_from_chat else None
            if chat_type == 'channel' and s.get('lock_forward_channel'):
                reason = t("lock_forward_channel", lang)
            elif chat_type in ['group','supergroup'] and s.get('lock_forward_group'):
                reason = t("lock_forward_group", lang)
        elif msg.forward_from and s.get('lock_forward_user'):
            reason = t("lock_forward_user", lang)
        elif msg.forward_date and s.get('lock_forward'):
            reason = t("lock_forward", lang)

    if reason:
        await safe_delete(msg)
        db.log_deleted_message(group_id, user.id, name, reason)
        del_sec = s.get('delete_bot_msg_seconds', 30) if s.get('delete_bot_msg') else 0

        if s.get('auto_warn'):
            db.add_warning(group_id, user.id, name, reason)
            warns = db.get_warnings(group_id, user.id)
            warn_limit = s.get('warn_limit', 3)
            await bot_reply(context, group_id, t("warn_msg", lang, name=name, reason=reason, count=warns, limit=warn_limit), del_sec)
            if warns >= warn_limit:
                await do_warn_action(context, group_id, user, s.get('warn_action','kick'), lang, name)
                db.reset_warnings(group_id, user.id)
                db.log_violation(group_id, user.id, name, s.get('warn_action','kick'), reason)
        else:
            await bot_reply(context, group_id, t("delete_msg", lang, name=name, reason=reason), del_sec)
        return

    await handle_public_commands(update, context)

async def do_warn_action(context, group_id, user, action, lang='fa', name=''):
    try:
        if action == 'kick':
            await context.bot.ban_chat_member(group_id, user.id)
            await asyncio.sleep(1)
            await context.bot.unban_chat_member(group_id, user.id)
            await context.bot.send_message(group_id, t("kick_msg", lang, name=name))
        elif action == 'ban':
            await context.bot.ban_chat_member(group_id, user.id)
            await context.bot.send_message(group_id, t("ban_msg", lang, name=name))
        elif action == 'mute':
            await context.bot.restrict_chat_member(group_id, user.id, ChatPermissions(can_send_messages=False))
            await context.bot.send_message(group_id, t("mute_msg", lang, name=name))
    except: pass

# ============================================
# دستورات عمومی گروه
# ============================================

async def handle_public_commands(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
    msg = update.message; txt = msg.text.strip()
    group_id = update.effective_chat.id; user = update.effective_user
    s = db.get_settings(group_id)
    lang = s.get('lang', 'fa')
    if not s.get('public_commands', 1): return

    # دستورات هر دو زبان پشتیبانی میشه
    cmd_link = [t("cmd_link", "fa"), t("cmd_link", "en")]
    cmd_info = [t("cmd_info", "fa"), t("cmd_info", "en")]
    cmd_rules = [t("cmd_rules", "fa"), t("cmd_rules", "en")]
    cmd_who = [t("cmd_who_invited", "fa"), t("cmd_who_invited", "en")]
    cmd_count = [t("cmd_invite_count", "fa"), t("cmd_invite_count", "en")]
    cmd_myinfo = [t("cmd_my_info", "fa"), t("cmd_my_info", "en")]
    cmd_report = [t("cmd_report", "fa"), t("cmd_report", "en")]
    cmd_why = [t("cmd_why_deleted", "fa"), t("cmd_why_deleted", "en")]

    if txt.lower() in cmd_link:
        g = db.get_group(group_id)
        link = g.get('group_link') if g else None
        await msg.reply_text(f"🔗 {link}" if link else t("no_link", lang))
    elif txt.lower() in cmd_info:
        g = db.get_group(group_id)
        info = g.get('group_info') if g else None
        await msg.reply_text(info if info else t("no_info", lang))
    elif txt.lower() in cmd_rules:
        g = db.get_group(group_id)
        rules = g.get('group_rules') if g else None
        await msg.reply_text(t("rules_title", lang, rules=rules) if rules else t("no_rules", lang))
    elif txt.lower() in cmd_who:
        inv = db.get_who_invited(group_id, user.id)
        await msg.reply_text(t("who_invited", lang, name=inv) if inv else t("not_found", lang))
    elif txt.lower() in cmd_count:
        c = db.get_user_invite_count(group_id, user.id)
        await msg.reply_text(t("invite_count", lang, count=c))
    elif txt.lower() in cmd_myinfo:
        c = db.get_user_invite_count(group_id, user.id)
        w = db.get_warnings(group_id, user.id)
        inv = db.get_who_invited(group_id, user.id)
        await msg.reply_text(t("my_info", lang, name=get_name(user), invites=c, warns=w, invited_by=inv or t("unknown", lang)))
    elif txt.lower() in cmd_report and msg.reply_to_message:
        rm = msg.reply_to_message
        await context.bot.send_message(config.ADMIN_ID,
            f"🚨 Report from {get_name(user)} in {update.effective_chat.title}:\n\n{rm.text or '[non-text]'}")
        await msg.reply_text(t("report_sent", lang))
    elif txt.lower() in cmd_why:
        r = db.get_last_delete_reason(group_id, user.id)
        await msg.reply_text(t("why_deleted", lang, reason=r) if r else t("not_found", lang))
    elif txt.strip() in ["!شرشر", "!سنگ", "!کاغذ", "!قیچی", "/rps", "!rps"]:
        choices = {"سنگ": "🪨", "کاغذ": "📄", "قیچی": "✂️"}
        user_choice = None
        if "سنگ" in txt:
            user_choice = "سنگ"
        elif "کاغذ" in txt:
            user_choice = "کاغذ"
        elif "قیچی" in txt:
            user_choice = "قیچی"

        if not user_choice:
            await msg.reply_text(
                "🎮 بازی سنگ کاغذ قیچی!\n\n"
                "یکی از این‌ها رو بفرست:\n"
                "!سنگ 🪨\n!کاغذ 📄\n!قیچی ✂️"
            )
        else:
            bot_choice = random.choice(list(choices.keys()))
            if user_choice == bot_choice:
                result = "🤝 مساوی شد!"
            elif (
                (user_choice == "سنگ" and bot_choice == "قیچی") or
                (user_choice == "کاغذ" and bot_choice == "سنگ") or
                (user_choice == "قیچی" and bot_choice == "کاغذ")
            ):
                result = "🎉 بردی!"
            else:
                result = "😅 باختی!"
            await msg.reply_text(
                f"شما: {choices[user_choice]} {user_choice}\n"
                f"ربات: {choices[bot_choice]} {bot_choice}\n\n"
                f"{result}"
            )
    else:
        # Gemini AI
        bot_username = (await context.bot.get_me()).username
        if bot_username and f"@{bot_username}" in txt and s.get('gemini_enabled'):
            question = txt.replace(f"@{bot_username}", "").strip()
            if question:
                await context.bot.send_chat_action(group_id, "typing")
                answer = await ask_gemini(question, group_id)
                await msg.reply_text(f"🤖 {answer}")

# ============================================
# اضافه شدن ربات به گروه
# ============================================

async def bot_added_to_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.my_chat_member: return
    chat = update.effective_chat; user = update.my_chat_member.from_user
    new_status = update.my_chat_member.new_chat_member.status

    if new_status in ['member','administrator'] and chat.type in ['group','supergroup']:
        db.add_group(chat.id, chat.title, user.id, user.username or "")
        db.activate_group_free(chat.id)
        try:
            await context.bot.send_message(chat.id,
    t("bot_added", "fa") + "\n" + t("bot_added", "en"))
        except: pass
        try:
            await context.bot.send_message(config.ADMIN_ID,
                f"🆕 گروه جدید:\n🏠 {chat.title}\n🆔 {chat.id}\n👤 @{user.username or '-'}")
        except: pass

    elif new_status in ['left','kicked'] and chat.type in ['group','supergroup']:
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
    app.add_handler(MessageHandler(
        filters.ChatType.PRIVATE & filters.Regex(r'^/reply_\d+'),
        cmd_reply
    ))
    app.add_handler(ChatMemberHandler(bot_added_to_group, ChatMemberHandler.MY_CHAT_MEMBER))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.ChatType.PRIVATE & filters.TEXT & ~filters.COMMAND, private_message))
    app.add_handler(MessageHandler(filters.ChatType.GROUPS & filters.StatusUpdate.NEW_CHAT_MEMBERS, member_joined))
    app.add_handler(MessageHandler(filters.ChatType.GROUPS & filters.StatusUpdate.LEFT_CHAT_MEMBER, member_left))
    # handler اصلی گروه - همه پیام‌ها بجز StatusUpdate
    app.add_handler(MessageHandler(
        filters.ChatType.GROUPS & ~filters.StatusUpdate.ALL,
        filter_messages
    ))

    job_queue = app.job_queue
    job_queue.run_repeating(check_quiet_hours_job, interval=60, first=10)
    job_queue.run_repeating(check_subscriptions_job, interval=86400, first=300)  # هر 24 ساعت

    print("🤖 ربات هیوا نسخه 6 آماده است...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
