import sqlite3
import os
from datetime import datetime, timedelta

# اگه Railway Volume در /data وصل باشه از اونجا استفاده کن، وگرنه محلی
DB_DIR = "/data" if os.path.isdir("/data") else "."
DB_PATH = os.path.join(DB_DIR, "hiwa_bot.db")

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS groups (
            group_id INTEGER PRIMARY KEY,
            group_name TEXT,
            owner_id INTEGER,
            owner_username TEXT,
            is_active INTEGER DEFAULT 1,
            group_link TEXT,
            group_info TEXT,
            group_rules TEXT,
            member_count INTEGER DEFAULT 0,
            expiry_date TEXT,
            plan TEXT DEFAULT 'free',
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS group_settings (
            group_id INTEGER PRIMARY KEY,
            lang TEXT DEFAULT 'fa',
            lock_link INTEGER DEFAULT 0,
            lock_site INTEGER DEFAULT 0,
            lock_id INTEGER DEFAULT 0,
            lock_hashtag INTEGER DEFAULT 0,
            lock_photo INTEGER DEFAULT 0,
            lock_video INTEGER DEFAULT 0,
            lock_video_note INTEGER DEFAULT 0,
            lock_sticker INTEGER DEFAULT 0,
            lock_gif INTEGER DEFAULT 0,
            lock_voice INTEGER DEFAULT 0,
            lock_file INTEGER DEFAULT 0,
            lock_poll INTEGER DEFAULT 0,
            lock_location INTEGER DEFAULT 0,
            lock_phone INTEGER DEFAULT 0,
            lock_forward INTEGER DEFAULT 0,
            lock_forward_channel INTEGER DEFAULT 0,
            lock_forward_group INTEGER DEFAULT 0,
            lock_forward_user INTEGER DEFAULT 0,
            lock_text INTEGER DEFAULT 0,
            lock_bad_words INTEGER DEFAULT 0,
            lock_slash INTEGER DEFAULT 0,
            lock_emoji INTEGER DEFAULT 0,
            public_commands INTEGER DEFAULT 1,
            group_locked INTEGER DEFAULT 0,
            welcome_enabled INTEGER DEFAULT 1,
            welcome_text TEXT DEFAULT '',
            welcome_button INTEGER DEFAULT 0,
            goodbye_enabled INTEGER DEFAULT 0,
            anti_spam INTEGER DEFAULT 0,
            anti_flood INTEGER DEFAULT 0,
            anti_flood_count INTEGER DEFAULT 5,
            anti_flood_seconds INTEGER DEFAULT 10,
            anti_raid INTEGER DEFAULT 0,
            bot_detection INTEGER DEFAULT 0,
            auto_warn INTEGER DEFAULT 0,
            warn_limit INTEGER DEFAULT 3,
            warn_action TEXT DEFAULT 'kick',
            force_invite INTEGER DEFAULT 0,
            force_invite_count INTEGER DEFAULT 5,
            force_invite_days INTEGER DEFAULT 0,
            captcha_enabled INTEGER DEFAULT 0,
            delete_bot_msg INTEGER DEFAULT 0,
            delete_bot_msg_seconds INTEGER DEFAULT 30,
            gemini_enabled INTEGER DEFAULT 0,
            quiet_1_from TEXT,
            quiet_1_to TEXT,
            quiet_1_state INTEGER DEFAULT 0,
            quiet_2_from TEXT,
            quiet_2_to TEXT,
            quiet_2_state INTEGER DEFAULT 0,
            quiet_3_from TEXT,
            quiet_3_to TEXT,
            quiet_3_state INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS bad_words (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER,
            word TEXT,
            UNIQUE(group_id, word)
        );

        CREATE TABLE IF NOT EXISTS white_list (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER,
            user_id INTEGER,
            user_name TEXT,
            UNIQUE(group_id, user_id)
        );

        CREATE TABLE IF NOT EXISTS force_invite_status (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER,
            user_id INTEGER,
            invite_count INTEGER DEFAULT 0,
            period_start TEXT DEFAULT (datetime('now')),
            is_free INTEGER DEFAULT 0,
            UNIQUE(group_id, user_id)
        );

        CREATE TABLE IF NOT EXISTS invites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER,
            inviter_id INTEGER,
            inviter_name TEXT,
            invited_id INTEGER,
            invited_name TEXT,
            invited_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS warnings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER,
            user_id INTEGER,
            user_name TEXT,
            reason TEXT,
            warned_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS violations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER,
            user_id INTEGER,
            user_name TEXT,
            action TEXT,
            reason TEXT,
            done_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS deleted_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER,
            user_id INTEGER,
            user_name TEXT,
            reason TEXT,
            deleted_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS member_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER,
            user_id INTEGER,
            user_name TEXT,
            action TEXT,
            done_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS message_activity (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER,
            user_id INTEGER,
            user_name TEXT,
            hour INTEGER,
            msg_date TEXT DEFAULT (date('now')),
            done_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS flood_tracker (
            group_id INTEGER,
            user_id INTEGER,
            msg_count INTEGER DEFAULT 1,
            first_msg_at TEXT DEFAULT (datetime('now')),
            PRIMARY KEY(group_id, user_id)
        );

        CREATE TABLE IF NOT EXISTS captcha_pending (
            group_id INTEGER,
            user_id INTEGER,
            user_name TEXT,
            joined_at TEXT DEFAULT (datetime('now')),
            PRIMARY KEY(group_id, user_id)
        );
    """)
    conn.commit()
    conn.close()

# گروه‌ها
def add_group(group_id, group_name, owner_id, owner_username):
    conn = get_conn()
    conn.execute("INSERT OR IGNORE INTO groups (group_id,group_name,owner_id,owner_username) VALUES (?,?,?,?)",
        (group_id, group_name, owner_id, owner_username))
    conn.execute("INSERT OR IGNORE INTO group_settings (group_id) VALUES (?)", (group_id,))
    conn.commit(); conn.close()

def get_group(group_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM groups WHERE group_id=?", (group_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def get_all_groups():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM groups ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_all_active_groups():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM groups WHERE is_active=1").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def activate_group_free(group_id):
    conn = get_conn()
    conn.execute("UPDATE groups SET is_active=1 WHERE group_id=?", (group_id,))
    conn.execute("INSERT OR IGNORE INTO group_settings (group_id) VALUES (?)", (group_id,))
    conn.commit(); conn.close()

def deactivate_group(group_id):
    conn = get_conn()
    conn.execute("UPDATE groups SET is_active=0 WHERE group_id=?", (group_id,))
    conn.commit(); conn.close()

def is_group_active(group_id):
    conn = get_conn()
    row = conn.execute("SELECT is_active FROM groups WHERE group_id=?", (group_id,)).fetchone()
    conn.close()
    return bool(row['is_active']) if row else False

def update_group_field(group_id, field, value):
    conn = get_conn()
    conn.execute(f"UPDATE groups SET {field}=? WHERE group_id=?", (value, group_id))
    conn.commit(); conn.close()

def get_all_settings_rows():
    conn = get_conn()
    rows = conn.execute("""
        SELECT gs.*, g.group_name, g.is_active FROM group_settings gs
        JOIN groups g ON gs.group_id = g.group_id
        WHERE g.is_active = 1
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]

# تنظیمات
def get_settings(group_id):
    conn = get_conn()
    conn.execute("INSERT OR IGNORE INTO group_settings (group_id) VALUES (?)", (group_id,))
    conn.commit()
    row = conn.execute("SELECT * FROM group_settings WHERE group_id=?", (group_id,)).fetchone()
    conn.close()
    return dict(row) if row else {}

def update_setting(group_id, key, value):
    conn = get_conn()
    conn.execute("INSERT OR IGNORE INTO group_settings (group_id) VALUES (?)", (group_id,))
    conn.execute(f"UPDATE group_settings SET {key}=? WHERE group_id=?", (value, group_id))
    conn.commit(); conn.close()

# کلمات بد
def add_bad_word(group_id, word):
    conn = get_conn()
    conn.execute("INSERT OR IGNORE INTO bad_words (group_id,word) VALUES (?,?)", (group_id, word.lower()))
    conn.commit(); conn.close()

def remove_bad_word(group_id, word):
    conn = get_conn()
    conn.execute("DELETE FROM bad_words WHERE group_id=? AND word=?", (group_id, word.lower()))
    conn.commit(); conn.close()

def get_bad_words(group_id):
    conn = get_conn()
    rows = conn.execute("SELECT word FROM bad_words WHERE group_id=?", (group_id,)).fetchall()
    conn.close()
    return [r['word'] for r in rows]

# لیست سفید
def add_to_whitelist(group_id, user_id, user_name=""):
    conn = get_conn()
    conn.execute("INSERT OR IGNORE INTO white_list (group_id,user_id,user_name) VALUES (?,?,?)",
        (group_id, user_id, user_name))
    conn.commit(); conn.close()

def remove_from_whitelist(group_id, user_id):
    conn = get_conn()
    conn.execute("DELETE FROM white_list WHERE group_id=? AND user_id=?", (group_id, user_id))
    conn.commit(); conn.close()

def is_whitelisted(group_id, user_id):
    conn = get_conn()
    row = conn.execute("SELECT 1 FROM white_list WHERE group_id=? AND user_id=?", (group_id, user_id)).fetchone()
    conn.close()
    return bool(row)

def get_whitelist(group_id):
    conn = get_conn()
    rows = conn.execute("SELECT * FROM white_list WHERE group_id=?", (group_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

# اد اجباری
def get_force_status(group_id, user_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM force_invite_status WHERE group_id=? AND user_id=?",
        (group_id, user_id)).fetchone()
    conn.close()
    return dict(row) if row else None

def init_force_status(group_id, user_id):
    conn = get_conn()
    conn.execute("INSERT OR IGNORE INTO force_invite_status (group_id,user_id) VALUES (?,?)",
        (group_id, user_id))
    conn.commit(); conn.close()

def increment_force_invite(group_id, inviter_id):
    conn = get_conn()
    conn.execute("UPDATE force_invite_status SET invite_count=invite_count+1 WHERE group_id=? AND user_id=?",
        (group_id, inviter_id))
    conn.commit(); conn.close()

def set_force_free(group_id, user_id, is_free):
    conn = get_conn()
    conn.execute("UPDATE force_invite_status SET is_free=?,period_start=datetime('now') WHERE group_id=? AND user_id=?",
        (is_free, group_id, user_id))
    conn.commit(); conn.close()

def reset_force_status(group_id, user_id):
    conn = get_conn()
    conn.execute("UPDATE force_invite_status SET invite_count=0,period_start=datetime('now'),is_free=0 WHERE group_id=? AND user_id=?",
        (group_id, user_id))
    conn.commit(); conn.close()

# دعوت‌ها
def add_invite(group_id, inviter_id, inviter_name, invited_id, invited_name):
    conn = get_conn()
    conn.execute("INSERT INTO invites (group_id,inviter_id,inviter_name,invited_id,invited_name) VALUES (?,?,?,?,?)",
        (group_id, inviter_id, inviter_name, invited_id, invited_name))
    conn.commit(); conn.close()

def get_who_invited(group_id, user_id):
    conn = get_conn()
    row = conn.execute("SELECT inviter_name FROM invites WHERE group_id=? AND invited_id=? ORDER BY invited_at DESC LIMIT 1",
        (group_id, user_id)).fetchone()
    conn.close()
    return row['inviter_name'] if row else None

def get_user_invite_count(group_id, user_id):
    conn = get_conn()
    row = conn.execute("SELECT COUNT(*) as cnt FROM invites WHERE group_id=? AND inviter_id=?",
        (group_id, user_id)).fetchone()
    conn.close()
    return row['cnt'] if row else 0

def get_invite_stats(group_id, hours=None):
    conn = get_conn()
    if hours:
        since = (datetime.now() - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")
        rows = conn.execute("SELECT inviter_id,inviter_name,COUNT(*) as count FROM invites WHERE group_id=? AND invited_at>=? GROUP BY inviter_id ORDER BY count DESC",
            (group_id, since)).fetchall()
    else:
        rows = conn.execute("SELECT inviter_id,inviter_name,COUNT(*) as count FROM invites WHERE group_id=? GROUP BY inviter_id ORDER BY count DESC",
            (group_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

# اخطارها
def add_warning(group_id, user_id, user_name, reason=""):
    conn = get_conn()
    conn.execute("INSERT INTO warnings (group_id,user_id,user_name,reason) VALUES (?,?,?,?)",
        (group_id, user_id, user_name, reason))
    conn.commit(); conn.close()

def get_warnings(group_id, user_id):
    conn = get_conn()
    row = conn.execute("SELECT COUNT(*) as cnt FROM warnings WHERE group_id=? AND user_id=?",
        (group_id, user_id)).fetchone()
    conn.close()
    return row['cnt'] if row else 0

def get_user_warnings(group_id, user_id):
    conn = get_conn()
    rows = conn.execute("SELECT * FROM warnings WHERE group_id=? AND user_id=? ORDER BY warned_at DESC",
        (group_id, user_id)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def reset_warnings(group_id, user_id):
    conn = get_conn()
    conn.execute("DELETE FROM warnings WHERE group_id=? AND user_id=?", (group_id, user_id))
    conn.commit(); conn.close()

# تخلفات
def log_violation(group_id, user_id, user_name, action, reason=""):
    conn = get_conn()
    conn.execute("INSERT INTO violations (group_id,user_id,user_name,action,reason) VALUES (?,?,?,?,?)",
        (group_id, user_id, user_name, action, reason))
    conn.commit(); conn.close()

def get_user_violations(group_id, user_id):
    conn = get_conn()
    rows = conn.execute("SELECT * FROM violations WHERE group_id=? AND user_id=? ORDER BY done_at DESC LIMIT 20",
        (group_id, user_id)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_group_violations_count(group_id):
    conn = get_conn()
    row = conn.execute("SELECT COUNT(*) as cnt FROM violations WHERE group_id=?", (group_id,)).fetchone()
    conn.close()
    return row['cnt'] if row else 0

# پیام‌های حذف شده
def log_deleted_message(group_id, user_id, user_name, reason):
    conn = get_conn()
    conn.execute("INSERT INTO deleted_messages (group_id,user_id,user_name,reason) VALUES (?,?,?,?)",
        (group_id, user_id, user_name, reason))
    conn.commit(); conn.close()

def get_last_delete_reason(group_id, user_id):
    conn = get_conn()
    row = conn.execute("SELECT reason FROM deleted_messages WHERE group_id=? AND user_id=? ORDER BY deleted_at DESC LIMIT 1",
        (group_id, user_id)).fetchone()
    conn.close()
    return row['reason'] if row else None

def get_deleted_count(group_id):
    conn = get_conn()
    row = conn.execute("SELECT COUNT(*) as cnt FROM deleted_messages WHERE group_id=?", (group_id,)).fetchone()
    conn.close()
    return row['cnt'] if row else 0

# تاریخچه ورود/خروج
def log_member(group_id, user_id, user_name, action):
    conn = get_conn()
    conn.execute("INSERT INTO member_history (group_id,user_id,user_name,action) VALUES (?,?,?,?)",
        (group_id, user_id, user_name, action))
    conn.commit(); conn.close()

def get_member_growth(group_id, days=7):
    conn = get_conn()
    since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    rows = conn.execute("""
        SELECT date(done_at) as day,
            SUM(CASE WHEN action='join' THEN 1 ELSE 0 END) as joins,
            SUM(CASE WHEN action='left' THEN 1 ELSE 0 END) as lefts
        FROM member_history WHERE group_id=? AND date(done_at) >= ?
        GROUP BY day ORDER BY day
    """, (group_id, since)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

# فعالیت ساعتی
def log_message_activity(group_id, user_id, user_name):
    hour = datetime.now().hour
    conn = get_conn()
    conn.execute("INSERT INTO message_activity (group_id,user_id,user_name,hour) VALUES (?,?,?,?)",
        (group_id, user_id, user_name, hour))
    conn.commit(); conn.close()

def get_hourly_activity(group_id, days=7):
    conn = get_conn()
    since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    rows = conn.execute("""
        SELECT hour, COUNT(*) as count FROM message_activity
        WHERE group_id=? AND msg_date >= ? GROUP BY hour ORDER BY hour
    """, (group_id, since)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_active_users(group_id, days=7):
    conn = get_conn()
    since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    rows = conn.execute("""
        SELECT user_id, user_name, COUNT(*) as count FROM message_activity
        WHERE group_id=? AND msg_date >= ? GROUP BY user_id ORDER BY count DESC LIMIT 10
    """, (group_id, since)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

# فلود
def track_flood(group_id, user_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM flood_tracker WHERE group_id=? AND user_id=?", (group_id, user_id)).fetchone()
    if row:
        conn.execute("UPDATE flood_tracker SET msg_count=msg_count+1 WHERE group_id=? AND user_id=?", (group_id, user_id))
        count = row['msg_count'] + 1; first_time = row['first_msg_at']
    else:
        conn.execute("INSERT INTO flood_tracker (group_id,user_id) VALUES (?,?)", (group_id, user_id))
        count = 1; first_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.commit(); conn.close()
    return count, first_time

def reset_flood(group_id, user_id):
    conn = get_conn()
    conn.execute("DELETE FROM flood_tracker WHERE group_id=? AND user_id=?", (group_id, user_id))
    conn.commit(); conn.close()

# کپچا
def add_captcha_pending(group_id, user_id, user_name):
    conn = get_conn()
    conn.execute("INSERT OR REPLACE INTO captcha_pending (group_id,user_id,user_name) VALUES (?,?,?)",
        (group_id, user_id, user_name))
    conn.commit(); conn.close()

def remove_captcha_pending(group_id, user_id):
    conn = get_conn()
    conn.execute("DELETE FROM captcha_pending WHERE group_id=? AND user_id=?", (group_id, user_id))
    conn.commit(); conn.close()

def is_captcha_pending(group_id, user_id):
    conn = get_conn()
    row = conn.execute("SELECT 1 FROM captcha_pending WHERE group_id=? AND user_id=?", (group_id, user_id)).fetchone()
    conn.close()
    return bool(row)

# آمار گروه
def get_group_stats(group_id):
    conn = get_conn()
    deleted = conn.execute("SELECT COUNT(*) as cnt FROM deleted_messages WHERE group_id=?", (group_id,)).fetchone()
    warns = conn.execute("SELECT COUNT(*) as cnt FROM warnings WHERE group_id=?", (group_id,)).fetchone()
    violations = conn.execute("SELECT COUNT(*) as cnt FROM violations WHERE group_id=?", (group_id,)).fetchone()
    joins = conn.execute("SELECT COUNT(*) as cnt FROM member_history WHERE group_id=? AND action='join'", (group_id,)).fetchone()
    lefts = conn.execute("SELECT COUNT(*) as cnt FROM member_history WHERE group_id=? AND action='left'", (group_id,)).fetchone()
    invites = conn.execute("SELECT COUNT(*) as cnt FROM invites WHERE group_id=?", (group_id,)).fetchone()
    conn.close()
    return {
        'deleted': deleted['cnt'] if deleted else 0,
        'warns': warns['cnt'] if warns else 0,
        'violations': violations['cnt'] if violations else 0,
        'joins': joins['cnt'] if joins else 0,
        'lefts': lefts['cnt'] if lefts else 0,
        'invites': invites['cnt'] if invites else 0,
    }

# اشتراک
def get_group_subscription(group_id):
    conn = get_conn()
    row = conn.execute("SELECT expiry_date, plan, is_active FROM groups WHERE group_id=?", (group_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def set_group_subscription(group_id, days):
    conn = get_conn()
    if days > 0:
        expiry = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        conn.execute("UPDATE groups SET expiry_date=?, plan='paid', is_active=1 WHERE group_id=?", (expiry, group_id))
    else:
        conn.execute("UPDATE groups SET expiry_date=NULL, plan='free', is_active=1 WHERE group_id=?", (group_id,))
    conn.commit(); conn.close()

def check_expired_subscriptions():
    """چک می‌کنه کدوم اشتراک‌ها منقضی شدن"""
    conn = get_conn()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    rows = conn.execute("""
        SELECT group_id, group_name, owner_id FROM groups 
        WHERE plan='paid' AND expiry_date IS NOT NULL AND expiry_date < ? AND is_active=1
    """, (now,)).fetchall()
    if rows:
        conn.execute("""
            UPDATE groups SET is_active=0 
            WHERE plan='paid' AND expiry_date IS NOT NULL AND expiry_date < ?
        """, (now,))
        conn.commit()
    conn.close()
    return [dict(r) for r in rows]

def get_expiring_soon(days=3):
    """گروه‌هایی که ظرف چند روز آینده منقضی میشن"""
    conn = get_conn()
    future = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    rows = conn.execute("""
        SELECT group_id, group_name, owner_id, expiry_date FROM groups
        WHERE plan='paid' AND expiry_date IS NOT NULL AND expiry_date > ? AND expiry_date < ? AND is_active=1
    """, (now, future)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

# Gemini
def get_gemini_context(group_id):
    conn = get_conn()
    rows = conn.execute(
        "SELECT role, content FROM message_activity WHERE group_id=? AND hour=-1 ORDER BY id DESC LIMIT 5",
        (group_id,)).fetchall()
    conn.close()
    return [dict(r) for r in reversed(rows)]
