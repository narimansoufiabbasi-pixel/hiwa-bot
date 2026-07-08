# ============================================
# فایل زبان‌ها - فارسی و انگلیسی
# ============================================

LANG = {
    "fa": {
        # انتخاب زبان
        "select_lang": "🌐 زبان خود را انتخاب کنید:\nPlease select your language:",
        "lang_fa": "🇮🇷 فارسی",
        "lang_en": "🇬🇧 English",
        "lang_saved": "✅ زبان فارسی انتخاب شد.",

        # پیام‌های عمومی
        "welcome": "👋 {name} به گروه خوش آمدید! 🎉",
        "goodbye": "👋 {name} از گروه خارج شد.",
        "captcha_msg": "👋 {name} خوش آمدید!\n\n⚠️ برای ارسال پیام روی دکمه زیر بزنید:",
        "captcha_btn": "✅ من ربات نیستم!",
        "captcha_ok": "✅ تأیید شدید! می‌توانید پیام بفرستید.",
        "captcha_not_yours": "این دکمه برای شما نیست!",
        "rules_btn": "✅ قوانین را خواندم",
        "rules_ok": "✅ ممنون! خوش آمدید.",

        # پیام‌های فیلتر
        "lock_link": "ارسال لینک تلگرام ممنوع است",
        "lock_site": "ارسال لینک سایت ممنوع است",
        "lock_id": "ارسال آیدی ممنوع است",
        "lock_hashtag": "ارسال هشتگ ممنوع است",
        "lock_phone": "ارسال شماره تلفن ممنوع است",
        "lock_slash": "ارسال دستور ممنوع است",
        "lock_text": "ارسال متن ممنوع است",
        "lock_bad_words": "استفاده از کلمات ممنوعه",
        "lock_emoji": "ارسال ایموجی ممنوع است",
        "lock_photo": "ارسال عکس ممنوع است",
        "lock_video": "ارسال فیلم ممنوع است",
        "lock_sticker": "ارسال استیکر ممنوع است",
        "lock_gif": "ارسال گیف ممنوع است",
        "lock_voice": "ارسال صدا ممنوع است",
        "lock_file": "ارسال فایل ممنوع است",
        "lock_poll": "ارسال نظرسنجی ممنوع است",
        "lock_location": "ارسال لوکیشن ممنوع است",
        "lock_forward": "فوروارد پیام ممنوع است",
        "lock_forward_channel": "فوروارد از کانال ممنوع است",
        "lock_forward_group": "فوروارد از گروه ممنوع است",
        "lock_forward_user": "فوروارد از کاربر ممنوع است",
        "anti_spam": "فوروارد پیام ممنوع است",

        # اخطار و مجازات
        "warn_msg": "⚠️ {name}، {reason}.\nاخطار {count}/{limit}",
        "delete_msg": "🚫 {name}، {reason}.",
        "flood_mute": "⚡ {name} به دلیل ارسال سریع 5 دقیقه ساکت شد.",
        "kick_msg": "🚫 {name} به دلیل تکرار تخلف اخراج شد.",
        "ban_msg": "🚫 {name} برای همیشه بن شد.",
        "mute_msg": "🔇 {name} ساکت شد.",
        "force_invite_msg": "⚠️ {name}، برای پیام دادن باید {count} نفر دیگر اد کنید.",
        "suspicious_bot": "🤖 کاربر مشکوک {name} شناسایی و بلاک شد.",

        # ساعت خاموشی
        "quiet_start": "🤖 ربات هوشمند هیوا:\n⏰😴 ساعت خاموشی فعال شد.\nاین گروه از {from_t} تا {to_t} در حالت خاموشی است.\nلطفا از ارسال پیام خودداری کنید.",
        "quiet_end": "🤖 ربات هوشمند هیوا:\n👮 ساعت خاموشی پایان یافت.\nساعت خاموشی بعدی در {from_t} آغاز می‌شود.",

        # پنل
        "select_group": "👇 گروه خود را انتخاب کنید:",
        "no_groups": "❌ هیچ گروهی پیدا نشد!\n\n📌 راهنما:\n۱. ربات را به گروه اضافه کنید\n۲. ادمین کنید\n۳. دوباره /start بزنید",
        "group_settings": "⚙️ تنظیمات گروه «{name}»\n\nیک بخش را انتخاب کنید:",
        "back": "🔙 برگشت",
        "save": "✅ ذخیره",
        "cancel_btn": "❌ لغو",
        "saved": "✅ ذخیره شد.",
        "error": "❌ خطایی رخ داد. /start بزنید.",
        "locked": "🔴 قفل",
        "unlocked": "🟢 آزاد",
        "enabled": "🟢 فعال",
        "disabled": "🔴 غیرفعال",

        # منوی گروه
        "menu_locks": "🔴🟢 قفل‌ها",
        "menu_quiet": "🌙 خاموشی",
        "menu_welcome": "👋 خوش‌آمد",
        "menu_goodbye": "🚪 پیام خروج",
        "menu_security": "🛡 امنیت",
        "menu_warn": "⚠️ اخطار",
        "menu_force": "📨 اد اجباری",
        "menu_white": "✅ لیست سفید",
        "menu_badwords": "🚫 کلمات ممنوعه",
        "menu_dashboard": "📊 تابلو آمار",
        "menu_users": "👥 مدیریت کاربران",
        "menu_settings": "⚙️ تنظیمات",
        "menu_help": "📖 راهنما",
        "menu_contact": "📞 ارتباط با سازنده",
        "menu_lang": "🌐 تغییر زبان",

        # ربات اضافه شد
        "bot_added": "✅ ربات هیوا فعال شد!\n\n📌 برای تنظیمات، در پیوی ربات /start بزنید.",

        # دستورات عمومی
        "cmd_link": "لینک گروه را بفرست",
        "cmd_info": "این گروه برای چیه؟",
        "cmd_rules": "قوانین",
        "cmd_who_invited": "من را کی اد کرده است؟",
        "cmd_invite_count": "من چند نفر اد کردم؟",
        "cmd_my_info": "اطلاعات من",
        "cmd_report": "گزارش",
        "cmd_why_deleted": "پیام من چرا حذف شد؟",

        # پاسخ دستورات
        "no_link": "❌ لینک تنظیم نشده.",
        "no_info": "❌ توضیحات تنظیم نشده.",
        "no_rules": "❌ قوانین تنظیم نشده.",
        "rules_title": "📜 قوانین:\n\n{rules}",
        "who_invited": "👤 توسط {name} اضافه شدید.",
        "not_found": "❓ اطلاعاتی یافت نشد.",
        "invite_count": "📊 شما {count} نفر را اضافه کرده‌اید.",
        "my_info": "👤 {name}\n📨 اد کرده: {invites} نفر\n⚠️ اخطار: {warns}\n👥 توسط: {invited_by}",
        "report_sent": "✅ گزارش ارسال شد.",
        "why_deleted": "❌ دلیل: {reason}",
        "unknown": "نامشخص",

        # اشتراک
        "sub_free": "🟢 رایگان (دائمی)",
        "sub_days_left": "⏳ {days} روز مانده",
        "sub_expired": "❌ منقضی شده",
        "sub_activated": "✅ اشتراک {days} روزه فعال شد!\n📅 انقضا: {shamsi} (شمسی) | {miladi} (میلادی)",
        "sub_free_set": "✅ گروه رایگان و دائمی شد.",
        "sub_expiring_soon": "⚠️ اشتراک ربات در گروه «{name}» تا 3 روز دیگر منقضی می‌شود.\nبرای تمدید با سازنده تماس بگیرید.",
        "locks_title": "🔴🟢 قفل‌های گروه «{name}»\n\n🔴 قفل = فعال | 🟢 آزاد = غیرفعال",
        "quiet_title": "🌙 ساعت خاموشی «{name}»\n\n📌 در ساعت خاموشی پیام اعضا حذف می‌شود\n\n",
        "quiet_set": "خاموشی {num}: {from_t} تا {to_t}",
        "quiet_not_set": "خاموشی {num}: تنظیم نشده ❌",
        "quiet_active": "🔴 فعال",
        "quiet_inactive": "🟢 غیرفعال",
        "quiet_edit": "✏️ ویرایش خاموشی {num}",
        "quiet_del": "🗑 حذف خاموشی {num}",
        "quiet_add": "➕ تنظیم خاموشی {num}",
        "welcome_title": "👋 پیام خوش‌آمد «{name}»\n\nمتن فعلی:\n{text}\n\n📌 متغیرها: {{name}} نام کاربر، {{group}} نام گروه",
        "welcome_edit": "✏️ تغییر متن",
        "goodbye_title": "🚪 اطلاع خروج اعضا «{name}»\n\n📌 وقتی فعال باشد با خروج هر عضو، ربات اطلاع می‌دهد",
        "security_title": "🛡 امنیت «{name}»\n\n🤖 کپچا: عضو جدید باید دکمه بزند\n🚫 ضد اسپم: پیام فوروارد حذف می‌شود\n⚡ ضد فلود: پیام سریع = سکوت موقت\n🔍 تشخیص ربات: اکانت مشکوک بلاک می‌شود",
        "security_help": "📖 راهنما",
        "warn_title": "⚠️ اخطار «{name}»\n\n📌 بعد از رسیدن به حد اخطار، کاربر مجازات می‌شود",
        "warn_limit_lbl": "⚠️ حد اخطار: {limit} بار",
        "warn_action_lbl": "🎯 اقدام: {action}",
        "warn_pick_limit": "⚠️ تعداد اخطار مجاز را انتخاب کنید:",
        "warn_pick_action": "🎯 اقدام بعد از رسیدن به حد اخطار:",
        "force_title": "📨 اد اجباری «{name}»\n\n📌 اعضا باید تعداد مشخصی نفر اد کنند",
        "force_count_lbl": "👥 تعداد اد: {count} نفر",
        "force_days_lbl": "⏱ مدت: {days}",
        "force_days_permanent": "دائمی",
        "force_pick_count": "👥 تعداد اد لازم را انتخاب کنید:",
        "force_pick_days": "⏱ مدت اعتبار اد را انتخاب کنید:",
        "other_pick_delsec": "⏱ زمان حذف پیام ربات را انتخاب کنید:",
        "badwords_title": "🚫 کلمات ممنوعه «{name}»\n\n📌 پیام‌های حاوی این کلمات حذف می‌شوند\n\n",
        "badwords_list": "کلمات ({count}):\n",
        "badwords_empty": "❌ هیچ کلمه‌ای ثبت نشده\n",
        "badwords_add": "➕ اضافه کردن کلمه",
        "badwords_del": "🗑 حذف کلمه",
        "badwords_add_prompt": "✏️ کلمه ممنوعه را بنویسید:\n\nبرای لغو: /cancel",
        "badwords_added": "✅ کلمه «{word}» اضافه شد.",
        "white_title": "✅ لیست سفید «{name}»\n\n📌 از اد اجباری معاف هستند\n\n",
        "white_list": "اعضای معاف ({count}):\n",
        "white_empty": "❌ لیست خالی\n",
        "white_help": "\n📝 معاف کردن: !معاف (ریپلای)\nحذف: !حذف معاف (ریپلای)",
        "sub_expired_msg": "⚠️ اشتراک ربات در این گروه منقضی شد.\nبرای تمدید با سازنده تماس بگیرید.",
    },

    "en": {
        # Language selection
        "select_lang": "🌐 زبان خود را انتخاب کنید:\nPlease select your language:",
        "lang_fa": "🇮🇷 فارسی",
        "lang_en": "🇬🇧 English",
        "lang_saved": "✅ English language selected.",

        # General messages
        "welcome": "👋 Welcome {name} to the group! 🎉",
        "goodbye": "👋 {name} has left the group.",
        "captcha_msg": "👋 Welcome {name}!\n\n⚠️ Please tap the button below to verify:",
        "captcha_btn": "✅ I'm not a robot!",
        "captcha_ok": "✅ Verified! You can now send messages.",
        "captcha_not_yours": "This button is not for you!",
        "rules_btn": "✅ I've read the rules",
        "rules_ok": "✅ Thank you! Welcome.",

        # Filter messages
        "lock_link": "Sending Telegram links is not allowed",
        "lock_site": "Sending website links is not allowed",
        "lock_id": "Sending usernames is not allowed",
        "lock_hashtag": "Sending hashtags is not allowed",
        "lock_phone": "Sending phone numbers is not allowed",
        "lock_slash": "Sending commands is not allowed",
        "lock_text": "Sending text is not allowed",
        "lock_bad_words": "Use of forbidden words",
        "lock_emoji": "Sending emojis is not allowed",
        "lock_photo": "Sending photos is not allowed",
        "lock_video": "Sending videos is not allowed",
        "lock_sticker": "Sending stickers is not allowed",
        "lock_gif": "Sending GIFs is not allowed",
        "lock_voice": "Sending voice messages is not allowed",
        "lock_file": "Sending files is not allowed",
        "lock_poll": "Sending polls is not allowed",
        "lock_location": "Sending locations is not allowed",
        "lock_forward": "Forwarding messages is not allowed",
        "lock_forward_channel": "Forwarding from channels is not allowed",
        "lock_forward_group": "Forwarding from groups is not allowed",
        "lock_forward_user": "Forwarding from users is not allowed",
        "anti_spam": "Forwarding messages is not allowed",

        # Warnings and actions
        "warn_msg": "⚠️ {name}, {reason}.\nWarning {count}/{limit}",
        "delete_msg": "🚫 {name}, {reason}.",
        "flood_mute": "⚡ {name} was muted for 5 minutes due to flooding.",
        "kick_msg": "🚫 {name} was kicked for repeated violations.",
        "ban_msg": "🚫 {name} was permanently banned.",
        "mute_msg": "🔇 {name} was muted.",
        "force_invite_msg": "⚠️ {name}, you need to invite {count} more people to send messages.",
        "suspicious_bot": "🤖 Suspicious account {name} detected and blocked.",

        # Quiet hours
        "quiet_start": "🤖 Hiwa Bot:\n⏰😴 Quiet hours activated.\nThis group is in quiet mode from {from_t} to {to_t}.\nPlease avoid sending messages during this time.",
        "quiet_end": "🤖 Hiwa Bot:\n👮 Quiet hours ended.\nNext quiet period starts at {from_t}.",

        # Panel
        "select_group": "👇 Select your group:",
        "no_groups": "❌ No groups found!\n\n📌 Guide:\n1. Add bot to your group\n2. Make it admin\n3. Press /start again",
        "group_settings": "⚙️ Settings for «{name}»\n\nSelect a section:",
        "back": "🔙 Back",
        "save": "✅ Save",
        "cancel_btn": "❌ Cancel",
        "saved": "✅ Saved.",
        "error": "❌ An error occurred. Press /start.",
        "locked": "🔴 Locked",
        "unlocked": "🟢 Unlocked",
        "enabled": "🟢 Enabled",
        "disabled": "🔴 Disabled",

        # Group menu
        "menu_locks": "🔴🟢 Locks",
        "menu_quiet": "🌙 Quiet Hours",
        "menu_welcome": "👋 Welcome",
        "menu_goodbye": "🚪 Goodbye",
        "menu_security": "🛡 Security",
        "menu_warn": "⚠️ Warnings",
        "menu_force": "📨 Force Invite",
        "menu_white": "✅ Whitelist",
        "menu_badwords": "🚫 Forbidden Words",
        "menu_dashboard": "📊 Dashboard",
        "menu_users": "👥 User Management",
        "menu_settings": "⚙️ Settings",
        "menu_help": "📖 Help",
        "menu_contact": "📞 Contact Owner",
        "menu_lang": "🌐 Change Language",

        # Bot added
        "bot_added": "✅ Hiwa Bot activated!\n\n📌 For settings, message the bot privately with /start.",

        # Public commands
        "cmd_link": "send group link",
        "cmd_info": "what is this group for?",
        "cmd_rules": "rules",
        "cmd_who_invited": "who invited me?",
        "cmd_invite_count": "how many did i invite?",
        "cmd_my_info": "my info",
        "cmd_report": "report",
        "cmd_why_deleted": "why was my message deleted?",

        # Command responses
        "no_link": "❌ Group link not set.",
        "no_info": "❌ Group info not set.",
        "no_rules": "❌ Group rules not set.",
        "rules_title": "📜 Rules:\n\n{rules}",
        "who_invited": "👤 You were added by {name}.",
        "not_found": "❓ No information found.",
        "invite_count": "📊 You have invited {count} people.",
        "my_info": "👤 {name}\n📨 Invited: {invites} people\n⚠️ Warnings: {warns}\n👥 Invited by: {invited_by}",
        "report_sent": "✅ Report sent.",
        "why_deleted": "❌ Reason: {reason}",
        "unknown": "Unknown",

        # Subscription
        "sub_free": "🟢 Free (Permanent)",
        "sub_days_left": "⏳ {days} days left",
        "sub_expired": "❌ Expired",
        "sub_activated": "✅ {days}-day subscription activated!\n📅 Expires: {shamsi} (Jalali) | {miladi} (Gregorian)",
        "sub_free_set": "✅ Group set to free (permanent).",
        "sub_expiring_soon": "⚠️ Bot subscription for «{name}» expires in 3 days.\nContact the owner to renew.",
        "sub_expired_msg": "⚠️ Bot subscription for this group has expired.\nContact the owner to renew.",
        "locks_title": "🔴🟢 Locks for «{name}»\n\n🔴 Locked = Active | 🟢 Unlocked = Inactive",
        "quiet_title": "🌙 Quiet Hours «{name}»\n\n📌 During quiet hours, member messages are deleted\n\n",
        "quiet_set": "Quiet {num}: {from_t} to {to_t}",
        "quiet_not_set": "Quiet {num}: Not set ❌",
        "quiet_active": "🔴 Active",
        "quiet_inactive": "🟢 Inactive",
        "quiet_edit": "✏️ Edit Quiet {num}",
        "quiet_del": "🗑 Delete Quiet {num}",
        "quiet_add": "➕ Set Quiet {num}",
        "welcome_title": "👋 Welcome Message «{name}»\n\nCurrent text:\n{text}\n\n📌 Variables: {{name}} username, {{group}} group name",
        "welcome_edit": "✏️ Edit Text",
        "goodbye_title": "🚪 Member Leave Notification «{name}»\n\n📌 When enabled, bot notifies on member leave",
        "security_title": "🛡 Security «{name}»\n\n🤖 Captcha: new member must press button\n🚫 Anti-spam: forwarded messages deleted\n⚡ Anti-flood: fast messages = temp mute\n🔍 Bot detection: suspicious accounts blocked",
        "security_help": "📖 Help",
        "warn_title": "⚠️ Warnings «{name}»\n\n📌 After reaching the limit, user is punished",
        "warn_limit_lbl": "⚠️ Warning limit: {limit} times",
        "warn_action_lbl": "🎯 Action: {action}",
        "warn_pick_limit": "⚠️ Select warning limit:",
        "warn_pick_action": "🎯 Select action after reaching limit:",
        "force_title": "📨 Force Invite «{name}»\n\n📌 Members must invite a set number of people",
        "force_count_lbl": "👥 Invite count: {count} people",
        "force_days_lbl": "⏱ Duration: {days}",
        "force_days_permanent": "Permanent",
        "force_pick_count": "👥 Select required invite count:",
        "force_pick_days": "⏱ Select invite validity duration:",
        "other_pick_delsec": "⏱ Select bot message delete time:",
        "badwords_title": "🚫 Forbidden Words «{name}»\n\n📌 Messages containing these words are deleted\n\n",
        "badwords_list": "Words ({count}):\n",
        "badwords_empty": "❌ No words added\n",
        "badwords_add": "➕ Add Word",
        "badwords_del": "🗑 Remove Word",
        "badwords_add_prompt": "✏️ Enter the forbidden word:\n\nTo cancel: /cancel",
        "badwords_added": "✅ Word «{word}» added.",
        "white_title": "✅ Whitelist «{name}»\n\n📌 Exempt from force invite\n\n",
        "white_list": "Exempt members ({count}):\n",
        "white_empty": "❌ List is empty\n",
        "white_help": "\n📝 To exempt: !exempt (reply)\nTo remove: !remove exempt (reply)",

    }
}

def t(key, lang="fa", **kwargs):
    text = LANG.get(lang, LANG["fa"]).get(key, LANG["fa"].get(key, key))
    if kwargs:
        try:
            text = text.format(**kwargs)
        except:
            pass
    return text

def get_lock_btn(lang, label_key, key, val):
    """ساختن دکمه قفل با وضعیت"""
    status = t("locked", lang) if val else t("unlocked", lang)
    return f"{status} | {t(label_key, lang)}"
