import sqlite3
from datetime import datetime, timedelta

DB_PATH = "hiwa_bot.db"

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
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS group_settings (
            group_id INTEGER PRIMARY KEY,
            lock_link INTEGER DEFAULT 0,
            lock_site INTEGER DEFAULT 0,
            lock_id INTEGER DEFAULT 0,
            lock_hashtag INTEGER DEFAULT 0,
            lock_photo INTEGER DEFAULT 0,
            lock_video INTEGER DEFAULT 0,
            lock_sticker INTEGER DEFAULT 0,
            lock_gif INTEGER DEFAULT 0,
            lock_voice INTEGER DEFAULT 0,
            lock_file INTEGER DEFAULT 0,
            lock_poll INTEGER DEFAULT 0,
            lock_location INTEGER DEFAULT 0,
            lock_phone INTEGER DEFAULT 0,
            lock_forward INTEGER DEFAULT 0,
            lock_forward_channel INTEGER DEFAULT 0,
            lock_text INTEGER DEFAULT 0,
            lock_bad_words INTEGER DEFAULT 0,
            lock_slash INTEGER DEFAULT 0,
            public_commands INTEGER DEFAULT 1,
            group_locked INTEGER DEFAULT 0,
            welcome_enabled INTEGER DEFAULT 1,
            welcome_text TEXT DEFAULT '',
            welcome_button INTEGER DEFAULT 0,
            goodbye_enabled INTEGER DEFAULT 0,
            goodbye_text TEXT DEFAULT '',
            anti_spam INTEGER DEFAULT 0,
            anti_flood INTEGER DEFAULT 0,
            anti_flood_count INTEGER DEFAULT 5,
            anti_flood_seconds INTEGER DEFAULT 10,
            anti_raid INTEGER DEFAULT 0,
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
            daily_stats INTEGER DEFAULT 0,
            auto_reminder INTEGER DEFAULT 0,
            reminder_text TEXT DEFAULT '',
            reminder_hour INTEGER DEFAULT 9,
            quiet_1_from TEXT,
            quiet_1_to TEXT,
            quiet_2_from TEXT,
            quiet_2_to TEXT,
            quiet_3_from TEXT,
            quiet_3_to TEXT
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
            reason TEXT,
            warned_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS deleted_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER,
            user_id INTEGER,
            reason TEXT,
            deleted_at TEXT DEFAULT (datetime('now'))
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

        CREATE TABLE IF NOT EXISTS unique_invite_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER,
            user_id INTEGER,
            user_name TEXT,
            link TEXT,
            created_at TEXT DEFAULT (datetime('now'))
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

def get_user_groups(user_id):
    conn = get_conn()
    rows = conn.execute("SELECT * FROM groups WHERE owner_id=? AND is_active=1", (user_id,)).fetchall()
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

# تنظیمات
def get_settings(group_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM group_settings WHERE group_id=?", (group_id,)).fetchone()
    conn.close()
    return dict(row) if row else {}

def update_setting(group_id, key, value):
    conn = get_conn()
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
def add_warning(group_id, user_id, reason=""):
    conn = get_conn()
    conn.execute("INSERT INTO warnings (group_id,user_id,reason) VALUES (?,?,?)", (group_id, user_id, reason))
    conn.commit(); conn.close()

def get_warnings(group_id, user_id):
    conn = get_conn()
    row = conn.execute("SELECT COUNT(*) as cnt FROM warnings WHERE group_id=? AND user_id=?",
        (group_id, user_id)).fetchone()
    conn.close()
    return row['cnt'] if row else 0

def reset_warnings(group_id, user_id):
    conn = get_conn()
    conn.execute("DELETE FROM warnings WHERE group_id=? AND user_id=?", (group_id, user_id))
    conn.commit(); conn.close()

# پیام‌های حذف شده
def log_deleted_message(group_id, user_id, reason):
    conn = get_conn()
    conn.execute("INSERT INTO deleted_messages (group_id,user_id,reason) VALUES (?,?,?)", (group_id, user_id, reason))
    conn.commit(); conn.close()

def get_last_delete_reason(group_id, user_id):
    conn = get_conn()
    row = conn.execute("SELECT reason FROM deleted_messages WHERE group_id=? AND user_id=? ORDER BY deleted_at DESC LIMIT 1",
        (group_id, user_id)).fetchone()
    conn.close()
    return row['reason'] if row else None

# فلود
def track_flood(group_id, user_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM flood_tracker WHERE group_id=? AND user_id=?", (group_id, user_id)).fetchone()
    if row:
        conn.execute("UPDATE flood_tracker SET msg_count=msg_count+1 WHERE group_id=? AND user_id=?", (group_id, user_id))
        count = row['msg_count'] + 1
        first_time = row['first_msg_at']
    else:
        conn.execute("INSERT INTO flood_tracker (group_id,user_id) VALUES (?,?)", (group_id, user_id))
        count = 1
        first_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
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
