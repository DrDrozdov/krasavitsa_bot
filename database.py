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

        cur.execute("""
        CREATE TABLE IF NOT EXISTS product_feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            product_name TEXT,
            feedback TEXT,
            created_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS recommended_products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            product_name TEXT,
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

def save_feedback(rec_id, feedback):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("""
        UPDATE recommendations
        SET feedback = ?
        WHERE id = ?
    """, (feedback, rec_id))

    conn.commit()
    conn.close()

def get_user_recommendations(user_id: int, limit: int = 5):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("""
        SELECT user_request, feedback, created_at
        FROM recommendations
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT ?
    """, (user_id, limit))

    rows = cur.fetchall()

    conn.close()

    return rows

    def save_product_feedback(user_id: int, product_name: str, feedback: str):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO product_feedback (user_id, product_name, feedback, created_at)
        VALUES (?, ?, ?, ?)
    """, (
        user_id,
        product_name,
        feedback,
        datetime.now().isoformat()
    ))

    conn.commit()
    conn.close()

    def get_product_stats(limit: int = 10):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("""
        SELECT
            product_name,
            SUM(CASE WHEN feedback = 'good' THEN 1 ELSE 0 END) as likes,
            SUM(CASE WHEN feedback = 'bad' THEN 1 ELSE 0 END) as dislikes
        FROM product_feedback
        GROUP BY product_name
        ORDER BY likes DESC, dislikes ASC
        LIMIT ?
    """, (limit,))

    rows = cur.fetchall()

    conn.close()

    return rows

    def save_recommended_product(user_id: int, product_name: str):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO recommended_products (user_id, product_name, created_at)
        VALUES (?, ?, ?)
    """, (
        user_id,
        product_name,
        datetime.now().isoformat()
    ))

    product_id = cur.lastrowid

    conn.commit()
    conn.close()

    return product_id


def get_recommended_product_name(product_id: int):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("""
        SELECT product_name
        FROM recommended_products
        WHERE id = ?
    """, (product_id,))

    row = cur.fetchone()

    conn.close()

    if not row:
        return None

    return row[0]


def get_product_rating(product_name: str):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("""
        SELECT
            SUM(CASE WHEN feedback = 'good' THEN 1 ELSE 0 END),
            SUM(CASE WHEN feedback = 'bad' THEN 1 ELSE 0 END),
            COUNT(*)
        FROM product_feedback
        WHERE product_name = ?
    """, (product_name,))

    row = cur.fetchone()
    conn.close()

    likes = row[0] or 0
    dislikes = row[1] or 0
    total = row[2] or 0

    if total == 0:
        return {
            "text": "⭐ Новинка: пока нет оценок",
            "likes": 0,
            "dislikes": 0,
            "total": 0,
            "percent": None
        }

    percent = round((likes / total) * 100)

    return {
        "text": f"⭐ {percent}% положительных оценок · 👍 {likes} / 👎 {dislikes}",
        "likes": likes,
        "dislikes": dislikes,
        "total": total,
        "percent": percent
    }