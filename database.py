import sqlite3
from datetime import datetime


DB_NAME = "krasavitsa.db"


def init_db():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            skin_type TEXT,
            budget TEXT,
            created_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS recommendations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            user_request TEXT,
            answer TEXT,
            feedback TEXT,
            created_at TEXT
        )
    """)

    conn.commit()
    conn.close()


def save_user(user_id: int, username: str = None):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("""
        INSERT OR IGNORE INTO users (user_id, username, created_at)
        VALUES (?, ?, ?)
    """, (user_id, username, datetime.now().isoformat()))

    conn.commit()
    conn.close()


def update_user_profile(user_id: int, skin_type: str = None, budget: str = None):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    if skin_type:
        cur.execute("UPDATE users SET skin_type = ? WHERE user_id = ?", (skin_type, user_id))

    if budget:
        cur.execute("UPDATE users SET budget = ? WHERE user_id = ?", (budget, user_id))

    conn.commit()
    conn.close()


def get_user_profile(user_id: int):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("SELECT skin_type, budget FROM users WHERE user_id = ?", (user_id,))
    result = cur.fetchone()

    conn.close()

    if not result:
        return None

    return {
        "skin_type": result[0],
        "budget": result[1],
    }


def save_recommendation(user_id: int, user_request: str, answer: str):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO recommendations (user_id, user_request, answer, created_at)
        VALUES (?, ?, ?, ?)
    """, (user_id, user_request, answer, datetime.now().isoformat()))

    rec_id = cur.lastrowid

    conn.commit()
    conn.close()

    return rec_id


def update_feedback(rec_id: int, feedback: str):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("UPDATE recommendations SET feedback = ? WHERE id = ?", (feedback, rec_id))

    conn.commit()
    conn.close()


def get_last_recommendations(user_id: int, limit: int = 5):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("""
        SELECT user_request, answer, feedback, created_at
        FROM recommendations
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT ?
    """, (user_id, limit))

    rows = cur.fetchall()
    conn.close()

    return rows