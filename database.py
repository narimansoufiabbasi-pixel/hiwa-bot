# ============================================
# مدیریت پایگاه داده ربات هیوا
# ============================================

import sqlite3
import os
from datetime import datetime

DB_PATH = "hiwa_bot.db"

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """ساخت جداول دیتابیس"""
    conn = get_conn()
    c = conn.cursor()

    # جدول گروه‌ها و اشتراک‌ها
    c.execute("""
        CREATE TABLE IF NOT EXISTS groups (
            group_id INTEGER PRIMARY KEY,
            group_name TEXT,
            owner_id INTEGER,
            owner_username TEXT,
            is_active INTEGER DEFAULT 0,
            is_trial INTEGER DEFAULT 0,
            trial_used INTEGER DEFAULT 0,
            expiry_date TEXT,
            plan TEXT,
            group_link TEXT,
            group_info TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # جدول تنظیمات هر گروه
    c.execute("""
        CREATE TABLE IF NOT EXISTS group_settings (
            group_id INTEGER PRIMARY KEY,
            lock_link INTEGER DEFAULT 0,
            lock_id INTEGER DEFAULT 0,
            lock_site INTEGER DEFAULT 0,
            lock_bad_words INTEGER DEFAULT 0,
            lock_hashtag INTEGER DEFAULT 0,
            lock_text INTEGER DEFAULT 0,
            lock_forward INTEGER DEFAULT 0,
            lock_forward_channel INTEGER DEFAULT 0,
            lock_photo INTEGER DEFAULT 0,
            lock_video INTEGER DEFAULT 0,
            lock_sticker INTEGER DEFAULT 0,
            lock_location INTEGER DEFAULT 0,
            lock_phone INTEGER DEFAULT 0,
            lock_voice INTEGER DEFAULT 0,
            lock_file INTEGER DEFAULT 0,
            lock_software INTEGER DEFAULT 0,
            lock_gif INTEGER DEFAULT 0,
            lock_poll INTEGER DEFAULT 0,
            lock_slash INTEGER DEFAULT 0,
            public_commands INTEGER DEFAULT 1,
            quiet_1_from TEXT DEFAULT NULL,
            quiet_1_to TEXT DEFAULT NULL,
            quiet_2_from TEXT DEFAULT NULL,
            quiet_2_to TEXT DEFAULT NULL,
            quiet_3_from TEXT DEFAULT NULL,
            quiet_3_to TEXT DEFAULT NULL
        )
    """)

    # جدول آمار دعوت‌ها
    c.execute("""
        CREATE TABLE IF NOT EXISTS invites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER,
            inviter_id INTEGER,
            inviter_name TEXT,
            invitee_id INTEGER,
            invitee_name TEXT,
            invited_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # جدول وارن‌ها
    c.execute("""
        CREATE TABLE IF NOT EXISTS warnings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER,
            user_id INTEGER,
            user_name TEXT,
            reason TEXT,
            warned_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # جدول پرداخت‌ها
    c.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            group_id INTEGER,
            plan TEXT,
            amount INTEGER,
            tracking_code TEXT,
            status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            confirmed_at TEXT
        )
    """)

    # جدول پیام‌های حذف شده
    c.execute("""
        CREATE TABLE IF NOT EXISTS deleted_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER,
            user_id INTEGER,
            reason TEXT,
            deleted_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()
    print("✅ دیتابیس آماده شد")

# ============================================
# توابع گروه
# ============================================

def get_group(group_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM groups WHERE group_id=?", (group_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def add_group(group_id, group_name, owner_id, owner_username):
    conn = get_conn()
    conn.execute("""
        INSERT OR IGNORE INTO groups (group_id, group_name, owner_id, owner_username)
        VALUES (?, ?, ?, ?)
    """, (group_id, group_name, owner_id, owner_username))
    conn.execute("""
        INSERT OR IGNORE INTO group_settings (group_id) VALUES (?)
    """, (group_id,))
    conn.commit()
    conn.close()

def activate_group(group_id, days, plan, is_trial=False):
    from datetime import timedelta
    expiry = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    conn = get_conn()
    conn.execute("""
        UPDATE groups SET is_active=1, expiry_date=?, plan=?, is_trial=?
        WHERE group_id=?
    """, (expiry, plan, 1 if is_trial else 0, group_id))
    if is_trial:
        conn.execute("UPDATE groups SET trial_used=1 WHERE group_id=?", (group_id,))
    conn.commit()
    conn.close()
    return expiry

def activate_group_free(group_id):
    """فعال‌سازی رایگان و دائمی گروه"""
    conn = get_conn()
    conn.execute("""
        UPDATE groups SET is_active=1, expiry_date=NULL, plan='free', is_trial=0
        WHERE group_id=?
    """, (group_id,))
    conn.commit()
    conn.close()

def deactivate_group(group_id):
    conn = get_conn()
    conn.execute("UPDATE groups SET is_active=0 WHERE group_id=?", (group_id,))
    conn.commit()
    conn.close()

def is_group_active(group_id):
    group = get_group(group_id)
    if not group or not group['is_active']:
        return False
    if group['expiry_date']:
        expiry = datetime.strptime(group['expiry_date'], "%Y-%m-%d %H:%M:%S")
        if datetime.now() > expiry:
            deactivate_group(group_id)
            return False
    return True

def get_days_until_expiry(group_id):
    group = get_group(group_id)
    if not group or not group['expiry_date']:
        return None
    expiry = datetime.strptime(group['expiry_date'], "%Y-%m-%d %H:%M:%S")
    delta = expiry - datetime.now()
    return delta.days

def get_all_active_groups():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM groups WHERE is_active=1").fetchall()
    conn.close()
    return [dict(r) for r in rows]

# ============================================
# توابع تنظیمات
# ============================================

def get_settings(group_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM group_settings WHERE group_id=?", (group_id,)).fetchone()
    conn.close()
    return dict(row) if row else {}

def update_setting(group_id, key, value):
    conn = get_conn()
    conn.execute(f"UPDATE group_settings SET {key}=? WHERE group_id=?", (value, group_id))
    conn.commit()
    conn.close()

# ============================================
# توابع دعوت
# ============================================

def add_invite(group_id, inviter_id, inviter_name, invitee_id, invitee_name):
    conn = get_conn()
    conn.execute("""
        INSERT INTO invites (group_id, inviter_id, inviter_name, invitee_id, invitee_name)
        VALUES (?, ?, ?, ?, ?)
    """, (group_id, inviter_id, inviter_name, invitee_id, invitee_name))
    conn.commit()
    conn.close()

def get_invite_stats(group_id, hours=None):
    conn = get_conn()
    if hours:
        from datetime import timedelta
        since = (datetime.now() - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")
        rows = conn.execute("""
            SELECT inviter_id, inviter_name, COUNT(*) as count
            FROM invites WHERE group_id=? AND invited_at >= ?
            GROUP BY inviter_id ORDER BY count DESC
        """, (group_id, since)).fetchall()
    else:
        rows = conn.execute("""
            SELECT inviter_id, inviter_name, COUNT(*) as count
            FROM invites WHERE group_id=?
            GROUP BY inviter_id ORDER BY count DESC
        """, (group_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_who_invited(group_id, user_id):
    conn = get_conn()
    row = conn.execute("""
        SELECT inviter_name FROM invites
        WHERE group_id=? AND invitee_id=?
        ORDER BY invited_at DESC LIMIT 1
    """, (group_id, user_id)).fetchone()
    conn.close()
    return row['inviter_name'] if row else None

def get_user_invite_count(group_id, user_id):
    conn = get_conn()
    row = conn.execute("""
        SELECT COUNT(*) as count FROM invites
        WHERE group_id=? AND inviter_id=?
    """, (group_id, user_id)).fetchone()
    conn.close()
    return row['count'] if row else 0

# ============================================
# توابع وارن
# ============================================

def add_warning(group_id, user_id, user_name, reason=""):
    conn = get_conn()
    conn.execute("""
        INSERT INTO warnings (group_id, user_id, user_name, reason)
        VALUES (?, ?, ?, ?)
    """, (group_id, user_id, user_name, reason))
    conn.commit()
    count = conn.execute("""
        SELECT COUNT(*) as c FROM warnings WHERE group_id=? AND user_id=?
    """, (group_id, user_id)).fetchone()['c']
    conn.close()
    return count

def get_warnings(group_id, user_id):
    conn = get_conn()
    count = conn.execute("""
        SELECT COUNT(*) as c FROM warnings WHERE group_id=? AND user_id=?
    """, (group_id, user_id)).fetchone()['c']
    conn.close()
    return count

def reset_warnings(group_id, user_id):
    conn = get_conn()
    conn.execute("DELETE FROM warnings WHERE group_id=? AND user_id=?", (group_id, user_id))
    conn.commit()
    conn.close()

# ============================================
# توابع پرداخت
# ============================================

def add_payment(user_id, group_id, plan, amount, tracking_code):
    conn = get_conn()
    conn.execute("""
        INSERT INTO payments (user_id, group_id, plan, amount, tracking_code)
        VALUES (?, ?, ?, ?, ?)
    """, (user_id, group_id, plan, amount, tracking_code))
    conn.commit()
    pay_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    return pay_id

def confirm_payment(pay_id):
    conn = get_conn()
    conn.execute("""
        UPDATE payments SET status='confirmed', confirmed_at=CURRENT_TIMESTAMP
        WHERE id=?
    """, (pay_id,))
    conn.commit()
    conn.close()

def get_payment(pay_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM payments WHERE id=?", (pay_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def get_pending_payments():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM payments WHERE status='pending' ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

# ============================================
# توابع پیام حذف شده
# ============================================

def log_deleted_message(group_id, user_id, reason):
    conn = get_conn()
    conn.execute("""
        INSERT INTO deleted_messages (group_id, user_id, reason)
        VALUES (?, ?, ?)
    """, (group_id, user_id, reason))
    conn.commit()
    conn.close()

def get_last_delete_reason(group_id, user_id):
    conn = get_conn()
    row = conn.execute("""
        SELECT reason FROM deleted_messages
        WHERE group_id=? AND user_id=?
        ORDER BY deleted_at DESC LIMIT 1
    """, (group_id, user_id)).fetchone()
    conn.close()
    return row['reason'] if row else None

def get_all_groups():
    """لیست همه گروه‌ها"""
    conn = get_conn()
    rows = conn.execute("SELECT * FROM groups ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_all_active_groups():
    """لیست گروه‌های فعال"""
    conn = get_conn()
    rows = conn.execute("SELECT * FROM groups WHERE is_active=1").fetchall()
    conn.close()
    return [dict(r) for r in rows]
