# ============================================
# فایل تنظیمات ربات هیوا
# ============================================

# توکن ربات (از BotFather گرفتی)
import os
BOT_TOKEN = os.environ.get("BOT_TOKEN")

# آیدی عددی ادمین اصلی
ADMIN_ID = 728288408

# پیام‌های ربات
MSG_WELCOME = """
👋 سلام {name} عزیز!
به گروه {group} خوش اومدی 🎉
لطفاً قوانین گروه رو مطالعه کن.
"""

MSG_GROUP_INFO = """
📌 این گروه برای چیه؟
{info}
"""

MSG_GROUP_LINK = "🔗 لینک گروه: {link}"

MSG_WARN = "⚠️ {name} عزیز، این اخطار {count}/3 توئه. مراقب باش!"
MSG_BAN = "🚫 {name} از گروه اخراج شد."
MSG_MUTE = "🔇 {name} به مدت {duration} ساعت ساکت شد."
MSG_FREE = "✅ {name} آزاد شد."

MSG_REPORT = "🚨 گزارش از {name}:\nپیام: {message}\n\nادمین‌ها بررسی کنید."

MSG_QUIET_START = "🔕 گروه از ساعت {from_time} تا {to_time} در حالت سکوت است."
MSG_QUIET_END = "🔔 گروه از حالت سکوت خارج شد."

MSG_LINK_FILTER = "🚫 {name} ارسال لینک در این گروه ممنوع است."
MSG_SPAM_FILTER = "🚫 {name} این نوع محتوا در گروه مجاز نیست."
