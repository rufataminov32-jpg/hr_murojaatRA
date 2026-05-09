import sqlite3

DB_FILE = "hr.db"


def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS murojaatlar (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            raqam       TEXT UNIQUE NOT NULL,
            user_id     INTEGER NOT NULL,
            ism         TEXT NOT NULL,
            username    TEXT,
            mavzu       TEXT NOT NULL,
            matn        TEXT NOT NULL,
            holat       TEXT NOT NULL DEFAULT 'yangi',
            javob       TEXT,
            yaratilgan  DATETIME DEFAULT CURRENT_TIMESTAMP,
            yangilangan DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS hr_xodimlar (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            ism     TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()


# ── Murojaat ─────────────────────────────────────────────────────────────────

def yangi_raqam() -> str:
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM murojaatlar")
    n = c.fetchone()[0] + 1
    conn.close()
    return f"№{n:04d}"


def murojaat_qoshish(user_id, ism, username, mavzu, matn) -> dict:
    raqam = yangi_raqam()
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        INSERT INTO murojaatlar (raqam, user_id, ism, username, mavzu, matn)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (raqam, user_id, ism, username, mavzu, matn))
    row_id = c.lastrowid
    conn.commit()
    conn.close()
    return murojaat_id(row_id)


def murojaat_id(row_id: int) -> dict:
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM murojaatlar WHERE id=?", (row_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def murojaat_raqam(raqam: str) -> dict:
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM murojaatlar WHERE raqam=?", (raqam,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def holat_yangilash(raqam: str, holat: str, javob: str = None):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    if javob is not None:
        c.execute("""
            UPDATE murojaatlar
            SET holat=?, javob=?, yangilangan=CURRENT_TIMESTAMP
            WHERE raqam=?
        """, (holat, javob, raqam))
    else:
        c.execute("""
            UPDATE murojaatlar
            SET holat=?, yangilangan=CURRENT_TIMESTAMP
            WHERE raqam=?
        """, (holat, raqam))
    conn.commit()
    conn.close()


def barcha_murojaatlar(holat: str = None) -> list:
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    if holat:
        c.execute("SELECT * FROM murojaatlar WHERE holat=? ORDER BY id DESC", (holat,))
    else:
        c.execute("SELECT * FROM murojaatlar ORDER BY id DESC")
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def foydalanuvchi_murojaatlari(user_id: int) -> list:
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM murojaatlar WHERE user_id=? ORDER BY id DESC LIMIT 10", (user_id,))
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── HR xodimlar ──────────────────────────────────────────────────────────────

def hr_qoshish(user_id: int, ism: str):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO hr_xodimlar (user_id, ism) VALUES (?, ?)", (user_id, ism))
    conn.commit()
    conn.close()


def hr_ochirish(user_id: int):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM hr_xodimlar WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()


def hr_royxat() -> list:
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM hr_xodimlar ORDER BY id")
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def hr_bormi(user_id: int) -> bool:
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT 1 FROM hr_xodimlar WHERE user_id=?", (user_id,))
    res = c.fetchone()
    conn.close()
    return res is not None
